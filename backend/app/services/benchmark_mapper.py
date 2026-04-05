"""
Fuzzy benchmark name mapper.

Maps benchmark names from the Excel file to TRI CSV file names
using multi-stage matching: exact → token-based fuzzy → manual override.
"""

import os
import re
from typing import Optional
from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from app.config import TRI_DATA_DIR
from app.models import Benchmark


# ── Manual overrides for complex/composite benchmarks ──────────────────────
MANUAL_OVERRIDES: dict[str, dict] = {
    "Benchmark Not Found": {
        "tri_file_name": None,
        "status": "no_benchmark",
        "exchange": None,
    },
    "S&P 500 TRI": {
        "tri_file_name": None,
        "status": "international",
        "exchange": None,
    },
    "S&P 500 International": {
        "tri_file_name": None,
        "status": "international",
        "exchange": None,
    },
    "S&P Global 1200 TRI": {
        "tri_file_name": None,
        "status": "international",
        "exchange": None,
    },
    "S&P Japan 500 TRI": {
        "tri_file_name": None,
        "status": "international",
        "exchange": None,
    },
    "Taiwan Capitalization Weighted Stock Index": {
        "tri_file_name": None,
        "status": "international",
        "exchange": None,
    },
    "75% MSCI Asia (Ex-Japan) Standard Index + 25% Nifty 500 Index": {
        "tri_file_name": None,
        "status": "composite",
        "exchange": None,
    },
}


def _normalize_benchmark_name(name: str) -> str:
    """Normalize a benchmark name for matching."""
    s = name.strip()
    # Remove common suffixes
    for suffix in [" Total Return Index", " TRI", " Index"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    # Replace special chars with underscores
    s = re.sub(r"[&]", "_and_", s)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()


def _normalize_filename(filename: str) -> str:
    """Normalize a TRI CSV filename for matching."""
    s = filename.replace(".csv", "")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()


def _detect_exchange(filename: str) -> str:
    """Detect if a TRI file is from BSE or NSE."""
    if filename.upper().startswith("BSE"):
        return "BSE"
    elif filename.upper().startswith("NIFTY") or filename.upper().startswith("NIFTY"):
        return "NSE"
    return "UNKNOWN"


def _get_tri_files() -> list[str]:
    """Get all TRI CSV files from the data directory."""
    if not TRI_DATA_DIR.exists():
        return []
    return [f for f in os.listdir(TRI_DATA_DIR) if f.endswith(".csv")]


def match_benchmark_to_tri(benchmark_name: str) -> dict:
    """
    Match a benchmark name to a TRI CSV file.

    Returns dict with: tri_file_name, matched_index_name, match_score, exchange, status
    """
    # Stage 0: Manual overrides
    for pattern, override in MANUAL_OVERRIDES.items():
        if benchmark_name.strip().startswith(pattern) or benchmark_name.strip() == pattern:
            return {
                "tri_file_name": override["tri_file_name"],
                "matched_index_name": benchmark_name,
                "match_score": 100.0 if override["tri_file_name"] else 0.0,
                "exchange": override["exchange"],
                "status": override["status"],
            }

    # Also check if the benchmark name contains composite markers
    if "%" in benchmark_name and "+" in benchmark_name:
        return {
            "tri_file_name": None,
            "matched_index_name": benchmark_name,
            "match_score": 0.0,
            "exchange": None,
            "status": "composite",
        }

    tri_files = _get_tri_files()
    if not tri_files:
        return {
            "tri_file_name": None,
            "matched_index_name": None,
            "match_score": 0.0,
            "exchange": None,
            "status": "no_tri_files",
        }

    normalized_benchmark = _normalize_benchmark_name(benchmark_name)

    # Stage 1: Exact match after normalization
    for tri_file in tri_files:
        normalized_file = _normalize_filename(tri_file)
        if normalized_benchmark == normalized_file:
            return {
                "tri_file_name": tri_file,
                "matched_index_name": tri_file.replace(".csv", "").replace("_", " "),
                "match_score": 100.0,
                "exchange": _detect_exchange(tri_file),
                "status": "mapped",
            }

    # Stage 2: Fuzzy match using token_sort_ratio
    file_names_normalized = {_normalize_filename(f): f for f in tri_files}
    choices = list(file_names_normalized.keys())

    result = process.extractOne(
        normalized_benchmark,
        choices,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=60,
    )

    if result:
        matched_normalized, score, _ = result
        matched_file = file_names_normalized[matched_normalized]
        return {
            "tri_file_name": matched_file,
            "matched_index_name": matched_file.replace(".csv", "").replace("_", " "),
            "match_score": score,
            "exchange": _detect_exchange(matched_file),
            "status": "mapped" if score >= 75 else "low_confidence",
        }

    # Stage 3: No match found
    return {
        "tri_file_name": None,
        "matched_index_name": None,
        "match_score": 0.0,
        "exchange": None,
        "status": "unmapped",
    }


def map_all_benchmarks(db: Session, benchmark_names: list[str]) -> dict[str, Benchmark]:
    """
    Map all unique benchmark names to TRI files and persist to DB.
    Returns dict of benchmark_name -> Benchmark ORM object.
    """
    result = {}
    unique_names = sorted(set(n.strip() for n in benchmark_names if n))

    for name in unique_names:
        # Check if already exists in DB
        existing = db.query(Benchmark).filter(Benchmark.name_in_excel == name).first()
        if existing:
            result[name] = existing
            continue

        # Perform matching
        match = match_benchmark_to_tri(name)
        benchmark = Benchmark(
            name_in_excel=name,
            tri_file_name=match["tri_file_name"],
            matched_index_name=match["matched_index_name"],
            match_score=match["match_score"],
            exchange=match["exchange"],
            status=match["status"],
            manually_verified=False,
        )
        db.add(benchmark)
        db.flush()  # Get the ID
        result[name] = benchmark

    db.commit()
    return result
