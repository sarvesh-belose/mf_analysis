"""Benchmarks API — listing, mapping, override, TRI management."""

import os
import csv
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Benchmark, Fund, TriData, TriFetchLog
from app.schemas import BenchmarkOut, BenchmarkUpdate
from app.services.tri_fetcher import get_tri_coverage, generate_refresh_prompt
from app.config import TRI_DATA_DIR

router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks"])


@router.get("")
def list_benchmarks(db: Session = Depends(get_db)):
    """List all benchmarks with fund counts."""
    benchmarks = db.query(Benchmark).order_by(Benchmark.name_in_excel).all()

    data = []
    for b in benchmarks:
        fund_count = db.query(func.count(Fund.id)).filter(
            Fund.benchmark_id == b.id
        ).scalar()

        data.append({
            "id": b.id,
            "name_in_excel": b.name_in_excel,
            "tri_file_name": b.tri_file_name,
            "matched_index_name": b.matched_index_name,
            "match_score": b.match_score,
            "manually_verified": b.manually_verified,
            "exchange": b.exchange,
            "status": b.status,
            "fund_count": fund_count or 0,
        })

    return {"data": data}


@router.put("/{benchmark_id}")
def update_benchmark(
    benchmark_id: int,
    update: BenchmarkUpdate,
    db: Session = Depends(get_db),
):
    """Override benchmark TRI file mapping."""
    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    if update.tri_file_name:
        benchmark.tri_file_name = update.tri_file_name
        benchmark.manually_verified = True
        benchmark.status = "mapped"

        # Detect exchange
        if update.tri_file_name.upper().startswith("BSE"):
            benchmark.exchange = "BSE"
        elif update.tri_file_name.upper().startswith("NIFTY"):
            benchmark.exchange = "NSE"

        benchmark.match_score = 100.0

    db.commit()
    return {"status": "updated", "benchmark_id": benchmark_id}


@router.get("/{benchmark_id}/tri-data")
def get_tri_data(
    benchmark_id: int,
    db: Session = Depends(get_db),
):
    """Get TRI time series for a benchmark."""
    benchmark = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    tris = (
        db.query(TriData.tri_date, TriData.tri_value)
        .filter(TriData.benchmark_id == benchmark_id)
        .order_by(TriData.tri_date)
        .all()
    )

    return {
        "benchmark_id": benchmark_id,
        "benchmark_name": benchmark.name_in_excel,
        "data": [{"date": str(t[0]), "value": t[1]} for t in tris],
    }


@router.get("/tri/available-files")
def list_tri_files():
    """List all available TRI CSV files."""
    if not TRI_DATA_DIR.exists():
        return {"files": []}

    files = sorted(f for f in os.listdir(TRI_DATA_DIR) if f.endswith(".csv"))
    return {"files": files}


# ── TRI Data Management ───────────────────────────────────────────────────

@router.get("/tri/coverage")
def tri_coverage(db: Session = Depends(get_db)):
    """Get TRI data coverage for all mapped benchmarks."""
    coverage = get_tri_coverage(db)
    return {"data": coverage}


@router.get("/tri/refresh-prompt")
def tri_refresh_prompt(
    exchange: str = Query("NSE", regex="^(NSE|BSE)$"),
    db: Session = Depends(get_db),
):
    """Generate browser-use agent prompt for TRI data refresh."""
    prompt = generate_refresh_prompt(db, exchange)
    return {"exchange": exchange, "prompt": prompt}


@router.post("/tri/upload")
async def upload_tri_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a new TRI CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    dest_path = TRI_DATA_DIR / file.filename
    content = await file.read()

    with open(dest_path, "wb") as f:
        f.write(content)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "message": "File uploaded. Run 'Load TRI Data' to import into database.",
    }


@router.get("/tri/fetch-log")
def tri_fetch_log(db: Session = Depends(get_db)):
    """Get TRI data fetch history."""
    logs = (
        db.query(TriFetchLog)
        .order_by(TriFetchLog.fetched_at.desc())
        .limit(100)
        .all()
    )

    return {
        "data": [{
            "id": l.id,
            "benchmark_id": l.benchmark_id,
            "exchange": l.exchange,
            "index_name": l.index_name,
            "period_start": str(l.period_start) if l.period_start else None,
            "period_end": str(l.period_end) if l.period_end else None,
            "status": l.status,
            "source_file": l.source_file,
            "fetched_at": str(l.fetched_at) if l.fetched_at else None,
        } for l in logs],
    }
