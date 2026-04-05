"""Dashboard & System Config API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Fund, Benchmark, FundMetrics, SystemConfig, Nav
from app.schemas import DashboardSummary, SystemConfigOut, SystemConfigUpdate
from app.config import DEFAULT_RISK_FREE_RATE

router = APIRouter(tags=["Dashboard & Config"])


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    """Get aggregate dashboard stats."""
    total_funds = db.query(func.count(Fund.id)).scalar() or 0
    funds_with_benchmark = db.query(func.count(Fund.id)).filter(
        Fund.benchmark_id.isnot(None)
    ).scalar() or 0
    funds_with_nav = db.query(func.count(Fund.id)).filter(
        Fund.nav_fetched == True  # noqa
    ).scalar() or 0
    funds_with_metrics = db.query(func.count(Fund.id)).filter(
        Fund.metrics_computed == True  # noqa
    ).scalar() or 0

    total_benchmarks = db.query(func.count(Benchmark.id)).scalar() or 0
    mapped_benchmarks = db.query(func.count(Benchmark.id)).filter(
        Benchmark.status == "mapped"
    ).scalar() or 0

    # Average Sharpe for 3Y period
    avg_sharpe = db.query(func.avg(FundMetrics.sharpe_ratio)).filter(
        FundMetrics.period == "3Y",
        FundMetrics.sharpe_ratio.isnot(None),
    ).scalar()

    avg_alpha = db.query(func.avg(FundMetrics.alpha)).filter(
        FundMetrics.period == "3Y",
        FundMetrics.alpha.isnot(None),
    ).scalar()

    # Category distribution
    category_dist = (
        db.query(Fund.scheme_category, func.count(Fund.id))
        .filter(Fund.scheme_category.isnot(None))
        .group_by(Fund.scheme_category)
        .order_by(func.count(Fund.id).desc())
        .limit(20)
        .all()
    )

    # Sharpe distribution for histogram (3Y)
    sharpe_data = (
        db.query(FundMetrics.sharpe_ratio)
        .filter(
            FundMetrics.period == "3Y",
            FundMetrics.sharpe_ratio.isnot(None),
        )
        .all()
    )

    return {
        "total_funds": total_funds,
        "funds_with_benchmark": funds_with_benchmark,
        "funds_with_nav": funds_with_nav,
        "funds_with_metrics": funds_with_metrics,
        "total_benchmarks": total_benchmarks,
        "mapped_benchmarks": mapped_benchmarks,
        "avg_sharpe_3y": round(avg_sharpe, 3) if avg_sharpe else None,
        "avg_alpha_3y": round(avg_alpha, 3) if avg_alpha else None,
        "category_distribution": [
            {"category": cat, "count": cnt} for cat, cnt in category_dist
        ],
        "sharpe_distribution": [s[0] for s in sharpe_data if s[0] is not None],
    }


# ── System Config ─────────────────────────────────────────────────────────

@router.get("/api/config", response_model=list[SystemConfigOut])
def list_config(db: Session = Depends(get_db)):
    """List all system configuration."""
    configs = db.query(SystemConfig).order_by(SystemConfig.key).all()

    # Add defaults if not set
    if not any(c.key == "risk_free_rate" for c in configs):
        default = SystemConfig(
            key="risk_free_rate",
            value=str(DEFAULT_RISK_FREE_RATE),
            description="Annual risk-free rate (%) for Sharpe/Sortino/Alpha calculations",
        )
        db.add(default)
        db.commit()
        configs = db.query(SystemConfig).order_by(SystemConfig.key).all()

    return configs


@router.put("/api/config/{key}")
def update_config(key: str, update: SystemConfigUpdate, db: Session = Depends(get_db)):
    """Update a system configuration value."""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")

    config.value = update.value
    db.commit()
    return {"status": "updated", "key": key, "value": update.value}
