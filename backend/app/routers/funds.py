"""Funds API — listing, filtering, detail, NAV history."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

import numpy as np
from datetime import datetime
import pandas as pd
from app.database import get_db
from app.models import Fund, Benchmark, Nav, FundMetrics, TriData
from app.schemas import FundSummary, FundDetail, FundWithMetrics, NavPoint

router = APIRouter(prefix="/api/funds", tags=["Funds"])


@router.get("", response_model=dict)
def list_funds(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    search: Optional[str] = None,
    fund_house: Optional[str] = None,
    scheme_category: Optional[str] = None,
    benchmark_id: Optional[int] = None,
    has_metrics: Optional[bool] = None,
    sort_by: str = Query("fund_name", regex="^(fund_name|amfi_code|fund_house|scheme_category)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List funds with pagination, search, and filters."""
    query = db.query(Fund)

    # Filters
    if search:
        query = query.filter(
            or_(
                Fund.fund_name.ilike(f"%{search}%"),
                Fund.fund_house.ilike(f"%{search}%"),
            )
        )
    if fund_house:
        query = query.filter(Fund.fund_house == fund_house)
    if scheme_category:
        query = query.filter(Fund.scheme_category == scheme_category)
    if benchmark_id:
        query = query.filter(Fund.benchmark_id == benchmark_id)
    if has_metrics is True:
        query = query.filter(Fund.metrics_computed == True)  # noqa
    elif has_metrics is False:
        query = query.filter(Fund.metrics_computed == False)  # noqa

    # Count
    total = query.count()

    # Sort
    sort_col = getattr(Fund, sort_by, Fund.fund_name)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Paginate
    offset = (page - 1) * page_size
    funds = query.offset(offset).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data": [FundSummary.model_validate(f) for f in funds],
    }


@router.get("/filters")
def get_filter_options(db: Session = Depends(get_db)):
    """Get available filter options for fund house and category."""
    fund_houses = (
        db.query(Fund.fund_house)
        .filter(Fund.fund_house.isnot(None))
        .distinct()
        .order_by(Fund.fund_house)
        .all()
    )
    categories = (
        db.query(Fund.scheme_category)
        .filter(Fund.scheme_category.isnot(None))
        .distinct()
        .order_by(Fund.scheme_category)
        .all()
    )
    return {
        "fund_houses": [fh[0] for fh in fund_houses],
        "categories": [c[0] for c in categories],
    }


@router.get("/{fund_id}")
def get_fund_detail(fund_id: int, db: Session = Depends(get_db)):
    """Get detailed fund info with metrics."""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    metrics = db.query(FundMetrics).filter(FundMetrics.fund_id == fund_id).all()
    benchmark = db.query(Benchmark).filter(Benchmark.id == fund.benchmark_id).first() if fund.benchmark_id else None

    return {
        "fund": FundSummary.model_validate(fund),
        "benchmark": {
            "name": benchmark.name_in_excel if benchmark else None,
            "status": benchmark.status if benchmark else None,
            "exchange": benchmark.exchange if benchmark else None,
        } if benchmark else None,
        "metrics": {m.period: {
            "rolling_return_avg": m.rolling_return_avg,
            "sharpe_ratio": m.sharpe_ratio,
            "sortino_ratio": m.sortino_ratio,
            "alpha": m.alpha,
            "beta": m.beta,
            "up_capture": m.up_capture,
            "down_capture": m.down_capture,
            "fund_cagr": m.fund_cagr,
            "benchmark_cagr": m.benchmark_cagr,
            "benchmark_rolling_return_avg": m.benchmark_rolling_return_avg,
            "benchmark_sharpe_ratio": m.benchmark_sharpe_ratio,
            "benchmark_sortino_ratio": m.benchmark_sortino_ratio,
            "data_sufficiency": m.data_sufficiency,
        } for m in metrics},
    }


@router.get("/{fund_id}/nav-history")
def get_nav_history(fund_id: int, db: Session = Depends(get_db)):
    """Get NAV time series for a fund."""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    navs = (
        db.query(Nav.nav_date, Nav.nav_value)
        .filter(Nav.fund_id == fund_id)
        .order_by(Nav.nav_date)
        .all()
    )

    return {
        "fund_id": fund_id,
        "fund_name": fund.fund_name,
        "data": [{"date": str(n[0]), "nav": n[1]} for n in navs],
    }


@router.get("/{fund_id}/rolling-returns")
def get_rolling_returns(
    fund_id: int, 
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    window_years: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """Dynamically compute rolling returns from a specific start date."""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    # Fetch NAVs
    navs = db.query(Nav.nav_date, Nav.nav_value).filter(
        Nav.fund_id == fund_id, Nav.nav_date >= start_dt
    ).order_by(Nav.nav_date).all()

    # Fetch TRIs if benchmark exists
    tris = []
    if fund.benchmark_id:
        tris = db.query(TriData.tri_date, TriData.tri_value).filter(
            TriData.benchmark_id == fund.benchmark_id, TriData.tri_date >= start_dt
        ).order_by(TriData.tri_date).all()

    if not navs:
        return {"data": [], "fund_avg": None, "benchmark_avg": None, "message": "No NAV data found"}

    n_df = pd.DataFrame(navs, columns=['date', 'value'])
    n_df['date'] = pd.to_datetime(n_df['date'])
    n_df.set_index('date', inplace=True)

    t_df = None
    if tris:
        t_df = pd.DataFrame(tris, columns=['date', 'value'])
        t_df['date'] = pd.to_datetime(t_df['date'])
        t_df.set_index('date', inplace=True)

    # Use exact D-day lookback for daily rolling returns for accuracy matching tools like AdvisorKhoj
    start_dates = n_df.index - pd.DateOffset(years=window_years)
    valid_mask = start_dates >= n_df.index[0]
    
    end_dates_valid = n_df.index[valid_mask]
    start_dates_valid = start_dates[valid_mask]
    
    if len(end_dates_valid) == 0:
        return {"data": [], "fund_avg": None, "benchmark_avg": None, "message": f"Need at least {window_years} years of data"}

    start_locs = n_df.index.get_indexer(start_dates_valid, method='pad')
    f_start_vals = n_df.iloc[start_locs]['value'].values
    f_end_vals = n_df.loc[end_dates_valid]['value'].values
    
    f_cagrs = ((f_end_vals / f_start_vals) ** (1.0 / window_years) - 1.0) * 100
    
    b_cagrs = [None] * len(end_dates_valid)
    if t_df is not None and not t_df.empty:
        b_start_locs = t_df.index.get_indexer(start_dates_valid, method='pad')
        b_end_locs = t_df.index.get_indexer(end_dates_valid, method='pad')
        
        for i in range(len(end_dates_valid)):
            if b_start_locs[i] != -1 and b_end_locs[i] != -1:
                b_s = t_df.iloc[b_start_locs[i]]['value']
                b_e = t_df.iloc[b_end_locs[i]]['value']
                if b_s > 0:
                    b_cagrs[i] = ((b_e / b_s) ** (1.0 / window_years) - 1.0) * 100

    data_points = []
    fund_cagrs_clean = []
    bench_cagrs_clean = []

    # Downsample points for frontend charting (keep max ~400 points) but calculate averages on ALL daily points natively
    step = max(1, len(end_dates_valid) // 400)
    
    for i in range(len(end_dates_valid)):
        fc = f_cagrs[i]
        bc = b_cagrs[i]
        
        if not np.isnan(fc):
            fund_cagrs_clean.append(fc)
        if bc is not None and not np.isnan(bc):
            bench_cagrs_clean.append(bc)
            
        if i % step == 0 or i == len(end_dates_valid) - 1:
            data_points.append({
                "date": end_dates_valid[i].strftime("%Y-%m-%d"),
                "fund_rolling_cagr": round(float(fc), 2) if not np.isnan(fc) else None,
                "benchmark_rolling_cagr": round(float(bc), 2) if bc is not None and not np.isnan(bc) else None
            })

    f_avg = sum(fund_cagrs_clean) / len(fund_cagrs_clean) if fund_cagrs_clean else None
    b_avg = sum(bench_cagrs_clean) / len(bench_cagrs_clean) if bench_cagrs_clean else None

    return {
        "fund_avg": round(f_avg, 2) if f_avg is not None else None,
        "benchmark_avg": round(b_avg, 2) if b_avg is not None else None,
        "data": data_points
    }
