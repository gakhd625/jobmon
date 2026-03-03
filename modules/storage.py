"""
modules/storage.py
──────────────────
SQLite-backed store for tracking which job IDs have already been
processed.  Using SQLite (instead of a plain text file) makes
concurrent access safe and supports future querying/reporting.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Absolute path so the DB is always found regardless of CWD
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seen_jobs.db"


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite DB, creating it if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id   TEXT PRIMARY KEY,
            seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


def is_seen(job_id: str) -> bool:
    """Return True if this job_id was already processed."""
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return row is not None
    except Exception as exc:
        logger.error("storage.is_seen error: %s", exc)
        return False  # Fail open: process the job rather than silently skip


def mark_seen(job_id: str) -> None:
    """Persist job_id so it won't be processed again."""
    try:
        with _get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_jobs (job_id) VALUES (?)", (job_id,)
            )
            conn.commit()
    except Exception as exc:
        logger.error("storage.mark_seen error: %s", exc)


def seen_count() -> int:
    """Return total number of jobs recorded (useful for diagnostics)."""
    try:
        with _get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
    except Exception as exc:
        logger.error("storage.seen_count error: %s", exc)
        return -1
