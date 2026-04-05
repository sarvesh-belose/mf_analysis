"""Ingestion API — data loading and computation triggers."""

import threading
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IngestionStatus
from app.schemas import IngestionStatusOut
from app.services.data_loader import load_master_data, load_tri_data
from app.services.nav_fetcher import fetch_navs_for_funds
from app.services.calculator import compute_all_metrics
from app.utils.signals import signal_stop, reset_signal

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])


def _run_in_thread(target, db_factory):
    """Run a function in a background thread with its own DB session."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        target(db)
    finally:
        db.close()


@router.post("/load-master")
def api_load_master(db: Session = Depends(get_db)):
    """Load fund master data from Excel and map benchmarks."""
    result = load_master_data(db)
    return {"status": "completed", "result": result}


@router.post("/load-tri")
def api_load_tri(db: Session = Depends(get_db)):
    """Load all TRI CSV data into the database."""
    result = load_tri_data(db)
    return {"status": "completed", "result": result}


@router.post("/fetch-navs")
def api_fetch_navs(background_tasks: BackgroundTasks, force: bool = False):
    """Fetch NAV data from AMFI API (runs in background thread)."""
    # Clean up signal before starting
    reset_signal("fetch_navs")
    def _run():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            fetch_navs_for_funds(db, force_refresh=force)
        finally:
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "NAV fetching started in background. Check /api/ingest/status for progress."}


@router.post("/compute-metrics")
def api_compute_metrics(background_tasks: BackgroundTasks, force: bool = False):
    """Compute all financial metrics (runs in background thread)."""
    # Clean up signal before starting
    reset_signal("compute_metrics")
    def _run():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            compute_all_metrics(db, force_refresh=force)
        finally:
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "Metrics computation started. Check /api/ingest/status for progress."}


@router.get("/status", response_model=list[IngestionStatusOut])
def api_ingestion_status(db: Session = Depends(get_db)):
    """Get status of all ingestion tasks."""
    statuses = db.query(IngestionStatus).all()
    return statuses


@router.get("/status/{task_name}", response_model=IngestionStatusOut)
def api_task_status(task_name: str, db: Session = Depends(get_db)):
    """Get status of a specific ingestion task."""
    status = db.query(IngestionStatus).filter(
        IngestionStatus.task_name == task_name
    ).first()
    if not status:
        return IngestionStatusOut(task_name=task_name, status="not_started")
    return status

@router.post("/stop/{task_name}")
def api_stop_task(task_name: str, db: Session = Depends(get_db)):
    """Signal a running task to stop in the next chunk."""
    # Always set signal even if DB is not updated yet (prevents orphans)
    signal_stop(task_name)
    
    status = db.query(IngestionStatus).filter(
        IngestionStatus.task_name == task_name
    ).first()
    if status and (status.status == "running" or status.status == "stopping"):
        status.status = "stopping"
        db.commit()
        return {"status": "success", "message": f"{task_name} signaled to stop."}
    return {"status": "error", "message": f"Task {task_name} is not running or already stopping."}
