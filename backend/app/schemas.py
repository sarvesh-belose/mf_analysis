"""Pydantic schemas for API request/response."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# ── Fund Schemas ──────────────────────────────────────────────────────────

class FundBase(BaseModel):
    amfi_code: int
    fund_name: str
    benchmark_name_raw: Optional[str] = None
    fund_house: Optional[str] = None
    scheme_type: Optional[str] = None
    scheme_category: Optional[str] = None


class FundSummary(FundBase):
    id: int
    benchmark_id: Optional[int] = None
    nav_fetched: bool = False
    metrics_computed: bool = False

    class Config:
        from_attributes = True


class FundDetail(FundSummary):
    isin_growth: Optional[str] = None
    isin_div_reinvestment: Optional[str] = None
    metrics: list["MetricOut"] = []

    class Config:
        from_attributes = True


# ── Benchmark Schemas ─────────────────────────────────────────────────────

class BenchmarkOut(BaseModel):
    id: int
    name_in_excel: str
    tri_file_name: Optional[str] = None
    matched_index_name: Optional[str] = None
    match_score: float = 0.0
    manually_verified: bool = False
    exchange: Optional[str] = None
    status: str = "mapped"
    fund_count: int = 0

    class Config:
        from_attributes = True


class BenchmarkUpdate(BaseModel):
    tri_file_name: Optional[str] = None
    manually_verified: bool = True


# ── Metrics Schemas ───────────────────────────────────────────────────────

class MetricOut(BaseModel):
    id: int
    fund_id: int
    benchmark_id: int
    period: str
    rolling_return_avg: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    up_capture: Optional[float] = None
    down_capture: Optional[float] = None
    fund_cagr: Optional[float] = None
    benchmark_cagr: Optional[float] = None
    data_sufficiency: str = "sufficient"

    class Config:
        from_attributes = True


class FundWithMetrics(BaseModel):
    id: int
    amfi_code: int
    fund_name: str
    fund_house: Optional[str] = None
    scheme_category: Optional[str] = None
    benchmark_name: Optional[str] = None
    benchmark_status: Optional[str] = None

    # 3Y metrics
    rolling_return_3y: Optional[float] = None
    sharpe_3y: Optional[float] = None
    sortino_3y: Optional[float] = None
    alpha_3y: Optional[float] = None
    beta_3y: Optional[float] = None
    up_capture_3y: Optional[float] = None
    down_capture_3y: Optional[float] = None
    fund_cagr_3y: Optional[float] = None

    # 5Y metrics
    rolling_return_5y: Optional[float] = None
    sharpe_5y: Optional[float] = None
    sortino_5y: Optional[float] = None
    alpha_5y: Optional[float] = None
    beta_5y: Optional[float] = None
    up_capture_5y: Optional[float] = None
    down_capture_5y: Optional[float] = None
    fund_cagr_5y: Optional[float] = None

    # 7Y metrics
    rolling_return_7y: Optional[float] = None
    sharpe_7y: Optional[float] = None
    sortino_7y: Optional[float] = None
    alpha_7y: Optional[float] = None
    beta_7y: Optional[float] = None
    up_capture_7y: Optional[float] = None
    down_capture_7y: Optional[float] = None
    fund_cagr_7y: Optional[float] = None


# ── Ingestion Schemas ─────────────────────────────────────────────────────

class IngestionStatusOut(BaseModel):
    task_name: str
    status: str
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Dashboard Schemas ─────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_funds: int = 0
    funds_with_benchmark: int = 0
    funds_with_nav: int = 0
    funds_with_metrics: int = 0
    total_benchmarks: int = 0
    mapped_benchmarks: int = 0
    avg_sharpe_3y: Optional[float] = None
    avg_alpha_3y: Optional[float] = None
    top_fund_sharpe: Optional[FundSummary] = None


# ── System Config Schemas ─────────────────────────────────────────────────

class SystemConfigOut(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    value: str


# ── NAV Schemas ───────────────────────────────────────────────────────────

class NavPoint(BaseModel):
    date: date
    nav: float


# ── Comparison Schema ────────────────────────────────────────────────────

class ComparisonRequest(BaseModel):
    fund_ids: list[int]
    period: str = "3Y"


# Forward ref update
FundDetail.model_rebuild()
