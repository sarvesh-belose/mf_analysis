"""Metrics API — fund metrics listing, top/bottom, comparison."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.database import get_db
from app.models import Fund, Benchmark, FundMetrics
from app.schemas import FundWithMetrics
from app.services.nl_search import parse_query

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


VALID_METRIC_COLUMNS = [
    "rolling_return_avg", "sharpe_ratio", "sortino_ratio",
    "alpha", "beta", "up_capture", "down_capture",
    "fund_cagr", "benchmark_cagr",
]
VALID_FUND_COLUMNS = ["fund_name", "fund_house", "scheme_category"]

# Operator -> SQLAlchemy comparison applied to a FundMetrics column.
_OP_APPLY = {
    "gte": lambda col, val: col >= val,
    "lte": lambda col, val: col <= val,
    "eq": lambda col, val: col == val,
}


@router.get("")
def list_metrics(
    period: str = Query("3Y", regex="^(3Y|5Y|7Y)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    sort_by: str = Query("sharpe_ratio"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    q: Optional[str] = Query(None, description="Natural-language query, e.g. 'sortino more, alpha over 2'"),
    search: Optional[str] = Query(None),
    fund_house: Optional[str] = Query(None),
    scheme_category: Optional[str] = Query(None),
    min_sharpe: Optional[float] = Query(None),
    max_sharpe: Optional[float] = Query(None),
    min_alpha: Optional[float] = Query(None),
    min_sortino: Optional[float] = Query(None),
    min_rolling_return: Optional[float] = Query(None),
    min_up_capture: Optional[float] = Query(None),
    max_down_capture: Optional[float] = Query(None),
    data_sufficiency: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List fund metrics with sorting, filtering, pagination."""
    query = (
        db.query(Fund, FundMetrics, Benchmark)
        .join(FundMetrics, Fund.id == FundMetrics.fund_id)
        .outerjoin(Benchmark, Fund.benchmark_id == Benchmark.id)
        .filter(FundMetrics.period == period)
    )

    # Natural-language query: parse into metric filters + sort preferences.
    nl_result = None
    if q and q.strip():
        nl_result = parse_query(q)
        for cond in nl_result["filters"]:
            col = getattr(FundMetrics, cond["column"], None)
            if col is not None:
                query = query.filter(_OP_APPLY[cond["op"]](col, cond["value"]))
        # A parsed sort preference overrides the default sort_by/sort_order.
        if nl_result["sorts"]:
            first = nl_result["sorts"][0]
            sort_by = first["column"]
            sort_order = first["direction"]
        # Free-text fallback (e.g. fund / AMC name) when nothing metric matched.
        if nl_result["search"] and not search:
            search = nl_result["search"]

    # Filters
    if search:
        query = query.filter(
            or_(
                Fund.fund_name.ilike(f"%{search}%"),
                Fund.fund_house.ilike(f"%{search}%")
            )
        )
    if fund_house:
        query = query.filter(Fund.fund_house == fund_house)
    if scheme_category:
        query = query.filter(Fund.scheme_category == scheme_category)
    if min_sharpe is not None:
        query = query.filter(FundMetrics.sharpe_ratio >= min_sharpe)
    if max_sharpe is not None:
        query = query.filter(FundMetrics.sharpe_ratio <= max_sharpe)
    if min_alpha is not None:
        query = query.filter(FundMetrics.alpha >= min_alpha)
    if min_sortino is not None:
        query = query.filter(FundMetrics.sortino_ratio >= min_sortino)
    if min_rolling_return is not None:
        query = query.filter(FundMetrics.rolling_return_avg >= min_rolling_return)
    if min_up_capture is not None:
        query = query.filter(FundMetrics.up_capture >= min_up_capture)
    if max_down_capture is not None:
        query = query.filter(FundMetrics.down_capture <= max_down_capture)
    if data_sufficiency:
        query = query.filter(FundMetrics.data_sufficiency == data_sufficiency)

    # When ranking by an NL metric preference (no threshold), exclude rows where
    # that metric is NULL so they don't pollute the "top" results.
    if nl_result and nl_result["sorts"]:
        primary = nl_result["sorts"][0]["column"]
        if primary in VALID_METRIC_COLUMNS:
            query = query.filter(getattr(FundMetrics, primary).isnot(None))

    total = query.count()

    # Sort
    if sort_by in VALID_METRIC_COLUMNS:
        sort_col = getattr(FundMetrics, sort_by)
    elif sort_by in VALID_FUND_COLUMNS:
        sort_col = getattr(Fund, sort_by)
    else:
        sort_col = FundMetrics.sharpe_ratio

    # SQLite doesn't support nullslast() natively in the same way, but SQLAlchemy emulates it.
    # However, to be safe for SQLite we can just use the column directly.
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Apply any secondary NL sort preferences as tie-breakers.
    if nl_result:
        for extra in nl_result["sorts"][1:]:
            col = getattr(FundMetrics, extra["column"], None)
            if col is not None:
                query = query.order_by(col.desc() if extra["direction"] == "desc" else col.asc())

    offset = (page - 1) * page_size
    results = query.offset(offset).limit(page_size).all()

    data = []
    for fund, metrics, benchmark in results:
        data.append({
            "id": fund.id,
            "amfi_code": fund.amfi_code,
            "fund_name": fund.fund_name,
            "fund_house": fund.fund_house,
            "scheme_category": fund.scheme_category,
            "benchmark_name": benchmark.name_in_excel if benchmark else None,
            "period": metrics.period,
            "rolling_return_avg": _round(metrics.rolling_return_avg),
            "sharpe_ratio": _round(metrics.sharpe_ratio),
            "sortino_ratio": _round(metrics.sortino_ratio),
            "alpha": _round(metrics.alpha),
            "beta": _round(metrics.beta),
            "up_capture": _round(metrics.up_capture),
            "down_capture": _round(metrics.down_capture),
            "fund_cagr": _round(metrics.fund_cagr),
            "benchmark_cagr": _round(metrics.benchmark_cagr),
            "data_sufficiency": metrics.data_sufficiency,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "period": period,
        "data": data,
        "nl": {
            "interpreted": nl_result["interpreted"],
            "matched": nl_result["matched"],
        } if nl_result else None,
    }


@router.get("/top")
def top_funds(
    metric: str = Query("sharpe_ratio"),
    period: str = Query("3Y", regex="^(3Y|5Y|7Y)$"),
    n: int = Query(10, ge=1, le=50),
    direction: str = Query("top", regex="^(top|bottom)$"),
    scheme_category: str = Query(None),
    db: Session = Depends(get_db),
):
    """Get top or bottom N funds by a specific metric."""
    if metric not in VALID_METRIC_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")

    sort_col = getattr(FundMetrics, metric)
    query = (
        db.query(Fund, FundMetrics, Benchmark)
        .join(FundMetrics, Fund.id == FundMetrics.fund_id)
        .outerjoin(Benchmark, Fund.benchmark_id == Benchmark.id)
        .filter(FundMetrics.period == period)
        .filter(sort_col.isnot(None))
    )

    if scheme_category:
        query = query.filter(Fund.scheme_category == scheme_category)

    if direction == "top":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    results = query.limit(n).all()

    data = []
    for fund, metrics, benchmark in results:
        data.append({
            "rank": len(data) + 1,
            "id": fund.id,
            "amfi_code": fund.amfi_code,
            "fund_name": fund.fund_name,
            "fund_house": fund.fund_house,
            "scheme_category": fund.scheme_category,
            "benchmark_name": benchmark.name_in_excel if benchmark else None,
            "metric_value": _round(getattr(metrics, metric)),
            "sharpe_ratio": _round(metrics.sharpe_ratio),
            "alpha": _round(metrics.alpha),
            "fund_cagr": _round(metrics.fund_cagr),
        })

    return {"metric": metric, "period": period, "direction": direction, "data": data}


@router.get("/compare")
def compare_funds(
    fund_ids: str = Query(..., description="Comma-separated fund IDs"),
    period: str = Query("3Y", regex="^(3Y|5Y|7Y)$"),
    db: Session = Depends(get_db),
):
    """Compare multiple funds side-by-side."""
    ids = [int(x.strip()) for x in fund_ids.split(",") if x.strip()]
    if len(ids) < 2 or len(ids) > 10:
        raise HTTPException(status_code=400, detail="Provide 2-10 fund IDs")

    results = (
        db.query(Fund, FundMetrics, Benchmark)
        .join(FundMetrics, Fund.id == FundMetrics.fund_id)
        .outerjoin(Benchmark, Fund.benchmark_id == Benchmark.id)
        .filter(Fund.id.in_(ids), FundMetrics.period == period)
        .all()
    )

    data = []
    for fund, metrics, benchmark in results:
        data.append({
            "id": fund.id,
            "fund_name": fund.fund_name,
            "fund_house": fund.fund_house,
            "scheme_category": fund.scheme_category,
            "benchmark_name": benchmark.name_in_excel if benchmark else None,
            "rolling_return_avg": _round(metrics.rolling_return_avg),
            "sharpe_ratio": _round(metrics.sharpe_ratio),
            "sortino_ratio": _round(metrics.sortino_ratio),
            "alpha": _round(metrics.alpha),
            "beta": _round(metrics.beta),
            "up_capture": _round(metrics.up_capture),
            "down_capture": _round(metrics.down_capture),
            "fund_cagr": _round(metrics.fund_cagr),
            "benchmark_cagr": _round(metrics.benchmark_cagr),
            "data_sufficiency": metrics.data_sufficiency,
        })

    return {"period": period, "data": data}


def _round(val, decimals=2):
    """Round a value safely."""
    if val is None:
        return None
    return round(val, decimals)
