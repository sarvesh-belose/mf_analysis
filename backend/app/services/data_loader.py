"""
Excel data loader and TRI CSV loader.

Loads the AMFI fund master from Excel and TRI benchmark data from CSVs.
"""

import csv
import logging
from datetime import datetime, date
from pathlib import Path

import openpyxl
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import EXCEL_FILE, TRI_DATA_DIR
from app.models import Fund, Benchmark, TriData, TriFetchLog, IngestionStatus
from app.services.benchmark_mapper import map_all_benchmarks

logger = logging.getLogger(__name__)


def load_master_data(db: Session) -> dict:
    """
    Load fund master data from Excel and map benchmarks.
    Returns summary stats.
    """
    # Update ingestion status
    status = _get_or_create_status(db, "load_master")
    status.status = "running"
    status.started_at = datetime.utcnow()
    db.commit()

    try:
        wb = openpyxl.load_workbook(str(EXCEL_FILE), read_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        total = len(rows)
        status.total_items = total
        db.commit()

        # Extract unique benchmark names
        benchmark_names = list(set(
            str(row[2]).strip() for row in rows if row[2]
        ))

        # Map all benchmarks
        benchmark_map = map_all_benchmarks(db, benchmark_names)

        # Load funds
        loaded = 0
        skipped = 0
        for row in rows:
            amfi_code, fund_name, benchmark_name = row[0], row[1], row[2]
            if not amfi_code or not fund_name:
                skipped += 1
                continue

            amfi_code = int(amfi_code)

            # Check if fund already exists
            existing = db.query(Fund).filter(Fund.amfi_code == amfi_code).first()
            if existing:
                skipped += 1
                status.completed_items = loaded + skipped
                continue

            benchmark_name_str = str(benchmark_name).strip() if benchmark_name else None
            benchmark = benchmark_map.get(benchmark_name_str) if benchmark_name_str else None

            fund = Fund(
                amfi_code=amfi_code,
                fund_name=str(fund_name).strip(),
                benchmark_name_raw=benchmark_name_str,
                benchmark_id=benchmark.id if benchmark else None,
            )
            db.add(fund)
            loaded += 1

            if loaded % 500 == 0:
                db.flush()
                status.completed_items = loaded + skipped
                db.commit()

        db.commit()
        wb.close()

        status.status = "completed"
        status.completed_items = total
        status.completed_at = datetime.utcnow()
        db.commit()

        return {
            "total_rows": total,
            "funds_loaded": loaded,
            "funds_skipped": skipped,
            "benchmarks_mapped": len(benchmark_map),
        }

    except Exception as e:
        status.status = "failed"
        status.error_message = str(e)
        db.commit()
        raise


def _parse_tri_date(date_str: str) -> date:
    """Parse date from TRI CSV (format: YYYY-MM-DD)."""
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()


def _parse_tri_value(value_str: str, exchange: str, headers: list[str], row: list[str]) -> float | None:
    """Extract TRI value based on exchange type."""
    try:
        if exchange == "NSE":
            # NSE has TotalReturnsIndex column
            idx = headers.index("TotalReturnsIndex")
            val = row[idx].strip()
            if val == "-" or val == "":
                return None
            return float(val)
        else:
            # BSE has OHLC — use Close
            idx = headers.index("Close")
            val = row[idx].strip()
            if val == "-" or val == "":
                return None
            return float(val)
    except (ValueError, IndexError):
        return None


def load_tri_data(db: Session) -> dict:
    """
    Load all TRI CSV files into the database.
    Returns summary stats.
    """
    status = _get_or_create_status(db, "load_tri")
    status.status = "running"
    status.started_at = datetime.utcnow()

    tri_files = sorted(f for f in TRI_DATA_DIR.iterdir() if f.suffix == ".csv")
    status.total_items = len(tri_files)
    db.commit()

    loaded_files = 0
    total_rows = 0
    errors = []

    for tri_file in tri_files:
        try:
            filename = tri_file.name

            # Find matching benchmark
            benchmark = db.query(Benchmark).filter(
                Benchmark.tri_file_name == filename
            ).first()

            if not benchmark:
                # Try to find by checking if this file is used
                logger.debug(f"No benchmark mapped to {filename}, skipping")
                continue

            exchange = benchmark.exchange or ("NSE" if filename.startswith("NIFTY") else "BSE")

            with open(tri_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)

                date_idx = headers.index("Date")
                rows_loaded = 0

                for csv_row in reader:
                    try:
                        tri_date = _parse_tri_date(csv_row[date_idx])
                        tri_value = _parse_tri_value(csv_row[date_idx], exchange, headers, csv_row)

                        if tri_value is None:
                            continue

                        # Use raw SQL for upsert performance
                        db.execute(
                            text("""
                                INSERT OR IGNORE INTO tri_data (benchmark_id, tri_date, tri_value)
                                VALUES (:bid, :tdate, :tval)
                            """),
                            {"bid": benchmark.id, "tdate": tri_date, "tval": tri_value},
                        )
                        rows_loaded += 1
                    except Exception:
                        continue

                db.commit()
                total_rows += rows_loaded

                # Log this fetch
                _log_tri_fetch(db, benchmark.id, exchange, tri_file, rows_loaded)

            loaded_files += 1
            status.completed_items = loaded_files
            db.commit()

        except Exception as e:
            errors.append({"file": tri_file.name, "error": str(e)})
            logger.error(f"Error loading {tri_file.name}: {e}")

    status.status = "completed"
    status.completed_at = datetime.utcnow()
    if errors:
        status.failed_items = len(errors)
        status.error_message = str(errors[:10])
    db.commit()

    return {
        "files_processed": loaded_files,
        "total_files": len(tri_files),
        "total_rows_loaded": total_rows,
        "errors": errors,
    }


def _log_tri_fetch(db: Session, benchmark_id: int, exchange: str, file_path: Path, row_count: int):
    """Log a TRI data fetch for tracking."""
    # Extract date range from filename pattern: INDEX_NAME_YYYY-MM-DD_to_YYYY-MM-DD.csv
    # But our files are consolidated, so use data dates
    from sqlalchemy import func
    min_date = db.query(func.min(TriData.tri_date)).filter(
        TriData.benchmark_id == benchmark_id
    ).scalar()
    max_date = db.query(func.max(TriData.tri_date)).filter(
        TriData.benchmark_id == benchmark_id
    ).scalar()

    if min_date and max_date:
        log = TriFetchLog(
            benchmark_id=benchmark_id,
            exchange=exchange,
            index_name=file_path.stem,
            period_start=min_date,
            period_end=max_date,
            status="downloaded",
            source_file=file_path.name,
            fetched_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()


def _get_or_create_status(db: Session, task_name: str) -> IngestionStatus:
    """Get or create an ingestion status entry."""
    status = db.query(IngestionStatus).filter(
        IngestionStatus.task_name == task_name
    ).first()
    if not status:
        status = IngestionStatus(task_name=task_name)
        db.add(status)
        db.flush()
    return status
