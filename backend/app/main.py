"""MF Analysis — FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.database import init_db
from app.routers import ingestion, funds, metrics, benchmarks, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables and cleanup orphaned tasks on startup."""
    logger.info("Initializing database...")
    init_db()
    
    # Cleanup task status: if "running" or "stopping", set to "stopped"
    from app.database import SessionLocal
    from app.models import IngestionStatus
    from sqlalchemy import update
    
    db = SessionLocal()
    try:
        db.execute(update(IngestionStatus).where(IngestionStatus.status.in_(["running", "stopping"])).values(status="stopped", error_message="Service restarted during execution."))
        db.commit()
        logger.info("Cleaned up orphaned task statuses.")
    except Exception as e:
        logger.error(f"Failed to cleanup task statuses: {e}")
    finally:
        db.close()
        
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="MF Analysis API",
    description="Mutual Fund Analysis — Rolling Returns, Sharpe, Sortino, Alpha, Capture Ratios",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import STATIC_DIR

# Routers
app.include_router(ingestion.router)
app.include_router(funds.router)
app.include_router(metrics.router)
app.include_router(benchmarks.router)
app.include_router(dashboard.router)

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mf-analysis-api"}

# Serve static files in production if dist directory exists
if STATIC_DIR.exists():
    
    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def serve_home():
        return FileResponse(STATIC_DIR / "index.html")

    # Vite puts assets in /assets folder
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def catch_all(full_path: str):
        """Catch-all for SPA routing."""
        # Check if the requested path exists as a static file first
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
            
        # Otherwise, return index.html for SPA routing
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built yet. Run `npm run build` in the frontend directory."}
