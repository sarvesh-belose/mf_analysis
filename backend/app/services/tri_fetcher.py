"""
TRI data refresh prompt generator.

Generates Browser-Use agent prompts for incremental TRI data refresh,
based on existing data coverage gaps.
"""

from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Benchmark, TriData, TriFetchLog
from app.config import AGENT_DIR


def get_tri_coverage(db: Session) -> list[dict]:
    """Get TRI data coverage for all mapped benchmarks."""
    benchmarks = (
        db.query(Benchmark)
        .filter(Benchmark.tri_file_name.isnot(None))
        .all()
    )

    coverage = []
    for b in benchmarks:
        min_date = db.query(func.min(TriData.tri_date)).filter(
            TriData.benchmark_id == b.id
        ).scalar()
        max_date = db.query(func.max(TriData.tri_date)).filter(
            TriData.benchmark_id == b.id
        ).scalar()
        row_count = db.query(func.count(TriData.id)).filter(
            TriData.benchmark_id == b.id
        ).scalar()

        coverage.append({
            "benchmark_id": b.id,
            "name": b.name_in_excel,
            "tri_file": b.tri_file_name,
            "exchange": b.exchange,
            "min_date": str(min_date) if min_date else None,
            "max_date": str(max_date) if max_date else None,
            "row_count": row_count or 0,
            "needs_refresh": max_date is not None and max_date < date.today(),
        })

    return coverage


def generate_refresh_prompt(db: Session, exchange: str = "NSE") -> str:
    """
    Generate a Browser-Use agent prompt for refreshing TRI data.
    Only includes date ranges that are missing.
    """
    # Find the latest date across all benchmarks for this exchange
    latest_date = (
        db.query(func.max(TriData.tri_date))
        .join(Benchmark)
        .filter(Benchmark.exchange == exchange)
        .scalar()
    )

    if not latest_date:
        # No data at all — use full prompt
        template_file = "bse_autonomous_agent.md" if exchange == "BSE" else "nse_autonomous_agent.md"
        template_path = AGENT_DIR / template_file
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return f"No template found for {exchange}"

    # Generate date ranges from latest_date + 1 day to today
    start_date = latest_date + __import__("datetime").timedelta(days=1)
    end_date = date.today()

    if start_date >= end_date:
        return f"TRI data for {exchange} is up to date (latest: {latest_date})."

    # Read the template
    template_file = "bse_autonomous_agent.md" if exchange == "BSE" else "nse_autonomous_agent.md"
    template_path = AGENT_DIR / template_file

    if not template_path.exists():
        return f"Template file not found: {template_file}"

    template = template_path.read_text(encoding="utf-8")

    # Build the date ranges section
    date_ranges = _build_incremental_date_ranges(start_date, end_date)
    date_ranges_text = "\n".join(
        f"{i+1}. {d['start']} to {d['end']}"
        for i, d in enumerate(date_ranges)
    )

    # Modify the template to replace date ranges
    import re
    # Find the date ranges section and replace it
    prompt = re.sub(
        r"For each index, download data for these date ranges:.*?(?=\nMain rules:)",
        f"For each index, download data for these date ranges:\n{date_ranges_text}\n\n",
        template,
        flags=re.DOTALL,
    )

    return prompt


def _build_incremental_date_ranges(start: date, end: date) -> list[dict]:
    """Build year-chunked date ranges for incremental fetch."""
    ranges = []
    current_start = start

    while current_start < end:
        year_end = date(current_start.year, 12, 31)
        if year_end > end:
            year_end = end

        ranges.append({
            "start": current_start.strftime("%d-%b-%Y"),
            "end": year_end.strftime("%d-%b-%Y"),
        })

        current_start = date(current_start.year + 1, 1, 1)

    return ranges
