"""
NAV fetcher — downloads NAV history from AMFI MF API.

Optimized with asyncio/aiohttp, persistent pooling, and bulk DB inserts for extreme speed.
Includes resumable progress tracking and Windows Proactor loop stabilization.
"""

import asyncio
import logging
import sys
from datetime import datetime, date
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import AMFI_API_BASE, NAV_FETCH_CONCURRENCY
from app.models import Fund, Nav, IngestionStatus
from app.utils.signals import should_stop

logger = logging.getLogger(__name__)

async def _fetch_single_nav_async(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, amfi_code: int) -> dict | None:
    """Fetch NAV data for a single fund asynchronously."""
    url = f"{AMFI_API_BASE}/{amfi_code}"
    try:
        async with semaphore:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

        if data.get("status") == "SUCCESS" or "data" in data:
            return {
                "amfi_code": amfi_code,
                "meta": data.get("meta", {}),
                "navs": data.get("data", []),
            }
    except Exception as e:
        logger.debug(f"Failed to fetch NAV for {amfi_code}: {e}")
    return None

def _fast_parse_date(date_str: str) -> date | None:
    """Fast parse DD-MM-YYYY without strptime overhead."""
    try:
        parts = date_str.strip().split('-')
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        pass
    return None

async def _fetch_all_async(funds, status, db, total_in_db, already_done_count):
    """Main async orchestrator with persistent connection pooling."""
    pending_total = len(funds)
    completed = already_done_count
    failed = 0
    chunk_size = 50  # Balanced chunk size for reliability

    connector = aiohttp.TCPConnector(limit=NAV_FETCH_CONCURRENCY)
    semaphore = asyncio.Semaphore(NAV_FETCH_CONCURRENCY)
    
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "MFAnalysis/1.0"}) as session:
        for i in range(0, pending_total, chunk_size):
            if should_stop("fetch_navs"):
                current_status = db.query(IngestionStatus).filter(IngestionStatus.task_name == "fetch_navs").first()
                if current_status:
                    current_status.status = "stopped"
                    db.commit()
                logger.info("NAV fetch stopped by user via signal.")
                break

            chunk = funds[i:i + chunk_size]
            fund_map = {f.amfi_code: f for f in chunk}
            
            tasks = [_fetch_single_nav_async(session, semaphore, code) for code in fund_map.keys()]
            # return_exceptions=True prevents the whole gather from failing if one fund hits a network error
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            nav_records = []
            
            for index, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Task exception in batch: {result}")
                    failed += 1
                    continue
                
                if result and result["navs"]:
                    fund = fund_map[result["amfi_code"]]
                    
                    # Update fund metadata
                    meta = result["meta"]
                    if meta:
                        fund.fund_house = meta.get("fund_house")
                        fund.scheme_type = meta.get("scheme_type")
                        fund.scheme_category = meta.get("scheme_category")
                        fund.isin_growth = meta.get("isin_growth")
                        fund.isin_div_reinvestment = meta.get("isin_div_reinvestment")

                    for nav_entry in result["navs"]:
                        nav_date = _fast_parse_date(nav_entry.get("date", ""))
                        if not nav_date: continue
                        
                        try:
                            nav_value = float(nav_entry.get("nav", 0))
                        except (ValueError, TypeError):
                            continue

                        if nav_value > 0:
                            nav_records.append({
                                "fund_id": fund.id,
                                "nav_date": nav_date,
                                "nav_value": nav_value,
                            })
                    
                    fund.nav_fetched = True
                    completed += 1
                else:
                    failed += 1

            # Bulk Insert
            if nav_records:
                try:
                    db.execute(
                        text("INSERT OR IGNORE INTO navs (fund_id, nav_date, nav_value) VALUES (:fund_id, :nav_date, :nav_value)"),
                        nav_records
                    )
                except Exception as e:
                    logger.error(f"Bulk insert failed: {e}")
                    
            status.completed_items = completed
            status.failed_items = failed
            db.commit()
            logger.info(f"Progress: {completed}/{total_in_db} (Already done: {already_done_count})")

    return completed, failed

def fetch_navs_for_funds(db: Session, fund_ids: list[int] | None = None, force_refresh: bool = False) -> dict:
    """
    Fetch NAV data with resumable progress and optional force refresh.
    If force_refresh=True, we reset nav_fetched flags for all funds.
    """
    if force_refresh:
        logger.info("Force refresh triggered: Resetting nav_fetched flags for all funds.")
        # We don't delete data, INSERT OR IGNORE will handle skipping existing records.
        db.execute(text("UPDATE funds SET nav_fetched = 0"))
        db.commit()

    # 1. Calculate overall progress for resumability
    total_funds = db.query(Fund).count()
    completed_funds = db.query(Fund).filter(Fund.nav_fetched == True).count()
    
    # 2. Get funds still needing data
    query = db.query(Fund).filter(Fund.nav_fetched == False)
    if fund_ids:
        query = query.filter(Fund.id.in_(fund_ids))

    funds = query.all()
    pending_count = len(funds)
    
    if pending_count == 0:
        # Update status to reflecting overall completion
        status = _get_or_create_status(db, "fetch_navs")
        status.total_items = total_funds
        status.completed_items = total_funds
        status.status = "completed"
        db.commit()
        return {"message": "All funds already fetched", "total": total_funds}

    # 3. Update status to reflect CURRENT overall progress
    status = _get_or_create_status(db, "fetch_navs")
    status.status = "running"
    status.total_items = total_funds
    status.completed_items = completed_funds
    status.failed_items = 0
    status.started_at = datetime.utcnow()
    db.commit()

    # 4. Handle Windows Proactor Loop issue (fixes 'select' exhaustion error)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        completed, failed = loop.run_until_complete(_fetch_all_async(funds, status, db, total_funds, completed_funds))
    except Exception as e:
        status.status = "failed"
        status.error_message = str(e)
        db.commit()
        logger.error(f"Fatal error in NAV fetcher: {e}")
        raise e
    finally:
        loop.close()

    if status.status != "failed" and status.status != "stopped":
        status.status = "completed"
        status.completed_at = datetime.utcnow()
        db.commit()

    return {"total": total_funds, "completed": completed, "failed": failed}

def _get_or_create_status(db: Session, task_name: str) -> IngestionStatus:
    status = db.query(IngestionStatus).filter(IngestionStatus.task_name == task_name).first()
    if not status:
        status = IngestionStatus(task_name=task_name)
        db.add(status)
        db.flush()
    return status
