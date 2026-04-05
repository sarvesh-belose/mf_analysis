from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, Date, DateTime, Text,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class Benchmark(Base):
    """TRI benchmark index mapping."""
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_in_excel = Column(String(500), unique=True, nullable=False)
    tri_file_name = Column(String(255), nullable=True)
    matched_index_name = Column(String(500), nullable=True)
    match_score = Column(Float, default=0.0)
    manually_verified = Column(Boolean, default=False)
    exchange = Column(String(10), nullable=True)  # NSE or BSE
    status = Column(String(50), default="mapped")  # mapped, no_tri, composite, international

    # Relationships
    funds = relationship("Fund", back_populates="benchmark")
    tri_data = relationship("TriData", back_populates="benchmark", cascade="all, delete-orphan")
    fetch_logs = relationship("TriFetchLog", back_populates="benchmark", cascade="all, delete-orphan")


class Fund(Base):
    """Mutual fund master record."""
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    amfi_code = Column(Integer, unique=True, nullable=False, index=True)
    fund_name = Column(String(500), nullable=False)
    benchmark_name_raw = Column(String(500), nullable=True)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id"), nullable=True)

    # Metadata from AMFI API
    fund_house = Column(String(300), nullable=True)
    scheme_type = Column(String(200), nullable=True)
    scheme_category = Column(String(300), nullable=True)
    isin_growth = Column(String(50), nullable=True)
    isin_div_reinvestment = Column(String(50), nullable=True)

    # Status
    nav_fetched = Column(Boolean, default=False)
    metrics_computed = Column(Boolean, default=False)

    # Relationships
    benchmark = relationship("Benchmark", back_populates="funds")
    navs = relationship("Nav", back_populates="fund", cascade="all, delete-orphan")
    metrics = relationship("FundMetrics", back_populates="fund", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_funds_benchmark_id", "benchmark_id"),
        Index("ix_funds_scheme_category", "scheme_category"),
        Index("ix_funds_fund_house", "fund_house"),
    )


class Nav(Base):
    """Daily NAV data for a fund."""
    __tablename__ = "navs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    nav_date = Column(Date, nullable=False)
    nav_value = Column(Float, nullable=False)

    fund = relationship("Fund", back_populates="navs")

    __table_args__ = (
        UniqueConstraint("fund_id", "nav_date", name="uq_nav_fund_date"),
        Index("ix_navs_fund_date", "fund_id", "nav_date"),
    )


class TriData(Base):
    """Daily TRI (Total Returns Index) data for a benchmark."""
    __tablename__ = "tri_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id"), nullable=False)
    tri_date = Column(Date, nullable=False)
    tri_value = Column(Float, nullable=False)

    benchmark = relationship("Benchmark", back_populates="tri_data")

    __table_args__ = (
        UniqueConstraint("benchmark_id", "tri_date", name="uq_tri_benchmark_date"),
        Index("ix_tri_benchmark_date", "benchmark_id", "tri_date"),
    )


class TriFetchLog(Base):
    """Tracks TRI data fetch history for incremental refresh."""
    __tablename__ = "tri_fetch_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id"), nullable=True)
    exchange = Column(String(10), nullable=False)  # NSE or BSE
    index_name = Column(String(255), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(50), nullable=False)  # downloaded, no_data, failed
    source_file = Column(String(500), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    benchmark = relationship("Benchmark", back_populates="fetch_logs")


class FundMetrics(Base):
    """Computed financial metrics for a fund."""
    __tablename__ = "fund_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=False)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id"), nullable=False)
    period = Column(String(10), nullable=False)  # 3Y, 5Y, 7Y

    rolling_return_avg = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    alpha = Column(Float, nullable=True)
    beta = Column(Float, nullable=True)
    up_capture = Column(Float, nullable=True)
    down_capture = Column(Float, nullable=True)
    fund_cagr = Column(Float, nullable=True)
    benchmark_cagr = Column(Float, nullable=True)
    benchmark_rolling_return_avg = Column(Float, nullable=True)
    benchmark_sharpe_ratio = Column(Float, nullable=True)
    benchmark_sortino_ratio = Column(Float, nullable=True)
    data_sufficiency = Column(String(50), default="sufficient")  # sufficient, insufficient

    computed_at = Column(DateTime, default=datetime.utcnow)

    fund = relationship("Fund", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("fund_id", "period", name="uq_metrics_fund_period"),
        Index("ix_metrics_period", "period"),
    )


class SystemConfig(Base):
    """System-wide configuration (key-value store)."""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IngestionStatus(Base):
    """Tracks data ingestion pipeline status."""
    __tablename__ = "ingestion_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False)  # load_master, load_tri, fetch_navs, compute_metrics
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
