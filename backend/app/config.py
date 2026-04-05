import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # mf_analysis root
DATA_DIR = BASE_DIR
TRI_DATA_DIR = DATA_DIR / "tri_benchmark_data"
AGENT_DIR = DATA_DIR / "agent"
EXCEL_FILE = DATA_DIR / "Final_AMFI_with_Benchmarks.xlsx"

# Database
DB_PATH = BASE_DIR / "mf_analysis.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# AMFI API
AMFI_API_BASE = "https://api.mfapi.in/mf"
NAV_FETCH_CONCURRENCY = 20  # concurrent threads for NAV download
NAV_FETCH_RATE_LIMIT = 10   # requests per second

# Defaults
DEFAULT_RISK_FREE_RATE = 6.0  # % per annum

# Static Files
STATIC_DIR = BASE_DIR / "frontend" / "dist"

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
