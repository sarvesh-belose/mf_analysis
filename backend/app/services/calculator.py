"""
Financial metrics calculator.

Computes: Rolling Returns, Sharpe, Sortino, Alpha, Beta, Up/Down Capture.
All metrics across 3Y, 5Y, 7Y periods.

Optimized with benchmark caching and multi-processing for speed.
"""

import logging
import traceback
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress
from sqlalchemy.orm import Session
from sqlalchemy import func, text, bindparam

from app.models import Fund, Nav, Benchmark, TriData, FundMetrics, IngestionStatus, SystemConfig
from app.config import DEFAULT_RISK_FREE_RATE
from app.utils.signals import should_stop

logger = logging.getLogger(__name__)

PERIODS = {"3Y": 3, "5Y": 5, "7Y": 7}

# ----------------- REUSABLE CALC CORE (Standalone for Pickling) -----------------

def _to_monthly_returns(series: pd.Series) -> pd.Series:
    monthly = series.resample("ME").last().dropna()
    return monthly.pct_change().dropna()

def _compute_rolling_return_avg(nav_series: pd.Series, rolling_years: int = 3) -> float | None:
    monthly = nav_series.resample("ME").last().dropna()
    window = rolling_years * 12
    if len(monthly) < window + 1: return None
    cagrs = []
    for i in range(len(monthly) - window):
        start_val = monthly.iloc[i]
        end_val = monthly.iloc[i + window]
        if start_val > 0:
            cagrs.append((end_val / start_val) ** (1.0 / rolling_years) - 1.0)
    return float(np.mean(cagrs)) * 100 if cagrs else None

def _compute_metrics_single_fund(nav_series, tri_series, fund_id, benchmark_id, risk_free_annual):
    if nav_series.empty or tri_series.empty: return []
    risk_free_monthly = risk_free_annual / 1200.0
    latest_date = min(nav_series.index.max(), tri_series.index.max())
    results = []
    
    for label, years in PERIODS.items():
        start_date = latest_date - pd.DateOffset(years=years)
        nav_p = nav_series[nav_series.index >= start_date]
        tri_p = tri_series[tri_series.index >= start_date]
        
        fund_months = len(nav_p.resample("ME").last().dropna())
        data_sufficiency = "sufficient" if fund_months >= (years * 12 * 0.75) else "insufficient"
        
        m_dict = {
            "fund_id": fund_id, "benchmark_id": benchmark_id, "period": label,
            "data_sufficiency": data_sufficiency, "computed_at": datetime.utcnow(),
            "rolling_return_avg": None, "sharpe_ratio": None, "sortino_ratio": None,
            "alpha": None, "beta": None, "up_capture": None, "down_capture": None,
            "fund_cagr": None, "benchmark_cagr": None,
            "benchmark_rolling_return_avg": None, "benchmark_sharpe_ratio": None,
            "benchmark_sortino_ratio": None
        }
        
        if fund_months >= 12:
            f_ret = _to_monthly_returns(nav_p)
            b_ret = _to_monthly_returns(tri_p)
            
            # Basic stats
            m_dict["rolling_return_avg"] = _compute_rolling_return_avg(nav_p, 3)
            m_dict["benchmark_rolling_return_avg"] = _compute_rolling_return_avg(tri_p, 3)
            
            # Sharpe/Sortino
            excess = f_ret - risk_free_monthly
            std = excess.std()
            m_dict["sharpe_ratio"] = float((excess.mean() / std) * np.sqrt(12)) if std and std != 0 else None
            
            b_excess = b_ret - risk_free_monthly
            b_std = b_excess.std()
            m_dict["benchmark_sharpe_ratio"] = float((b_excess.mean() / b_std) * np.sqrt(12)) if b_std and b_std != 0 else None
            
            downside = excess[excess < 0]
            d_std = downside.std()
            m_dict["sortino_ratio"] = float((excess.mean() / d_std) * np.sqrt(12)) if d_std and d_std != 0 else None
            
            b_downside = b_excess[b_excess < 0]
            b_d_std = b_downside.std()
            m_dict["benchmark_sortino_ratio"] = float((b_excess.mean() / b_d_std) * np.sqrt(12)) if b_d_std and b_d_std != 0 else None
            
            # Alpha/Beta
            aligned = pd.DataFrame({"fund": f_ret, "bench": b_ret}).dropna()
            if len(aligned) >= 12:
                try:
                    slope, intercept, _, _, _ = linregress(aligned["bench"] - risk_free_monthly, aligned["fund"] - risk_free_monthly)
                    m_dict["alpha"] = float(intercept * 1200)
                    m_dict["beta"] = float(slope)
                except: pass
                
                # Capture Ratios
                up_m = aligned[aligned["bench"] > 0]
                if len(up_m) > 0:
                    f_compound = np.prod(1 + up_m["fund"])**(1/len(up_m)) - 1
                    b_compound = np.prod(1 + up_m["bench"])**(1/len(up_m)) - 1
                    m_dict["up_capture"] = float((f_compound / b_compound) * 100) if b_compound else None
                
                down_m = aligned[aligned["bench"] < 0]
                if len(down_m) > 0:
                    f_compound = np.prod(1 + down_m["fund"])**(1/len(down_m)) - 1
                    b_compound = np.prod(1 + down_m["bench"])**(1/len(down_m)) - 1
                    m_dict["down_capture"] = float((f_compound / b_compound) * 100) if b_compound else None

            # CAGRs
            actual_y = (nav_p.index[-1] - nav_p.index[0]).days / 365.25
            if actual_y > 0 and nav_p.iloc[0] > 0:
                m_dict["fund_cagr"] = float(((nav_p.iloc[-1] / nav_p.iloc[0])**(1/actual_y)-1)*100)
            
            actual_y_b = (tri_p.index[-1] - tri_p.index[0]).days / 365.25
            if actual_y_b > 0 and tri_p.iloc[0] > 0:
                m_dict["benchmark_cagr"] = float(((tri_p.iloc[-1] / tri_p.iloc[0])**(1/actual_y_b)-1)*100)
                
        results.append(m_dict)
    return results

# ----------------- MAIN PIPELINE -----------------

def compute_all_metrics(db: Session, force_refresh: bool = False) -> dict:
    """Compute metrics for all funds with speed optimization and user stop signal."""
    status = _get_or_create_status(db, "compute_metrics")
    status.status = "running"
    status.started_at = datetime.utcnow()
    db.commit()

    # Pre-fetch ALL Benchmarks to memory
    logger.info("Caching benchmark TRI data...")
    benchmarks = db.query(Benchmark).all()
    benchmark_cache = {}
    for b in benchmarks:
        tris = db.execute(text("SELECT tri_date, tri_value FROM tri_data WHERE benchmark_id = :bid ORDER BY tri_date"), {"bid": b.id}).fetchall()
        if tris:
            dates, vals = zip(*tris)
            benchmark_cache[b.id] = pd.Series(vals, index=pd.DatetimeIndex(dates))
    
    # Get funds needing computation
    query = db.query(Fund).filter(Fund.benchmark_id.isnot(None), Fund.nav_fetched == True)
    if not force_refresh:
        query = query.filter(Fund.metrics_computed == False)
    funds = query.all()
    
    total = len(funds)
    status.total_items = total
    db.commit()

    risk_free_annual = _get_risk_free_rate(db)
    computed = 0
    failed = 0
    failed_empty_data = 0
    failed_error = 0
    
    # Process in smaller chunks for more frequent stop checks
    chunk_size = 20
    for i in range(0, total, chunk_size):
        # CHECK FOR STOP SIGNAL (Check memory flag first, then update DB)
        if should_stop("compute_metrics"):
            # Update DB to 'stopped' so the UI sees it's locked in
            current_status = db.query(IngestionStatus).filter(IngestionStatus.task_name == "compute_metrics").first()
            if current_status:
                current_status.status = "stopped"
                current_status.error_message = None
                db.commit()
            logger.info("Metric calculation stopped by user via signal.")
            break
            
        chunk = funds[i:i + chunk_size]
        
        # NOTE: For maximum speed on 14k funds, we loop and calculate. 
        # Using multiprocessing is possible but overhead of pickling large pandas series might be high here.
        # We'll use a direct loop but fetch NAVs in a single query per chunk.
        
        fund_ids = [f.id for f in chunk]
        if not fund_ids:
            continue
        nav_data = db.execute(text("SELECT fund_id, nav_date, nav_value FROM navs WHERE fund_id IN :ids ORDER BY nav_date").bindparams(bindparam("ids", expanding=True)), {"ids": fund_ids}).fetchall()
        nav_groups = {}
        for fid, ndate, nval in nav_data:
            if fid not in nav_groups: nav_groups[fid] = ([], [])
            nav_groups[fid][0].append(ndate)
            nav_groups[fid][1].append(nval)
            
        for fund in chunk:
            try:
                # Get cached nav series
                if fund.id not in nav_groups: continue
                dates, vals = nav_groups[fund.id]
                nav_series = pd.Series(vals, index=pd.DatetimeIndex(dates))
                tri_series = benchmark_cache.get(fund.benchmark_id, pd.Series(dtype=float))
                
                # Delete existing
                db.execute(text("DELETE FROM fund_metrics WHERE fund_id = :fid"), {"fid": fund.id})
                
                results = _compute_metrics_single_fund(nav_series, tri_series, fund.id, fund.benchmark_id, risk_free_annual)
                
                if results:
                    for r in results:
                        db.execute(text("""
                            INSERT INTO fund_metrics (
                                fund_id, benchmark_id, period, rolling_return_avg, sharpe_ratio, sortino_ratio, alpha, beta, 
                                up_capture, down_capture, fund_cagr, benchmark_cagr, benchmark_rolling_return_avg, 
                                benchmark_sharpe_ratio, benchmark_sortino_ratio, data_sufficiency, computed_at
                            )
                            VALUES (
                                :fund_id, :benchmark_id, :period, :rolling_return_avg, :sharpe_ratio, :sortino_ratio, :alpha, :beta, 
                                :up_capture, :down_capture, :fund_cagr, :benchmark_cagr, :benchmark_rolling_return_avg,
                                :benchmark_sharpe_ratio, :benchmark_sortino_ratio, :data_sufficiency, :computed_at
                            )
                        """), r)
                    fund.metrics_computed = True
                    computed += 1
                else:
                    failed += 1
                    failed_empty_data += 1
            except Exception:
                failed += 1
                failed_error += 1
                logger.error(traceback.format_exc())

        status.completed_items = computed
        status.failed_items = failed
        sys_msgs = []
        if failed_empty_data > 0:
            sys_msgs.append(f"{failed_empty_data} lacked sufficient NAV/TRI history")
        if failed_error > 0:
            sys_msgs.append(f"{failed_error} calculation errors")
        status.error_message = "; ".join(sys_msgs) if sys_msgs else None
            
        db.commit()
        logger.info(f"Metrics progress: {computed + failed}/{total}")

    if status.status != "failed":
        status.status = "completed"
        status.completed_at = datetime.utcnow()
        db.commit()

    return {"total": total, "computed": computed, "failed": failed}

def _get_risk_free_rate(db: Session) -> float:
    config = db.query(SystemConfig).filter(SystemConfig.key == "risk_free_rate").first()
    return float(config.value) if config and config.value else DEFAULT_RISK_FREE_RATE

def _get_or_create_status(db: Session, task_name: str) -> IngestionStatus:
    status = db.query(IngestionStatus).filter(IngestionStatus.task_name == task_name).first()
    if not status:
        status = IngestionStatus(task_name=task_name)
        db.add(status)
        db.flush()
    return status
