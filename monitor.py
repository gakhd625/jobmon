#!/usr/bin/env python3
"""
monitor.py
──────────
OnlineJobsPH Job Monitor - Main Orchestrator
=============================================

This is the single entry point for the monitoring bot.

Run once:
    python monitor.py

Run on a schedule (recommended):
    Use the systemd service + timer defined in deploy/jobmon.service
    and deploy/jobmon.timer (runs every 30 minutes by default).

Full flow:
    1. Load credentials from .env
    2. Scrape newest jobs from OnlineJobsPH (Playwright)
    3. Skip jobs already seen (SQLite)
    4. Filter by keywords (local, zero cost)
    5. Optionally score with gpt-4o-mini (only if keywords matched)
    6. Send Telegram alert if score >= threshold
    7. Mark job as seen
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env BEFORE importing modules that read env vars ────────────────────
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE)

# ── Project modules ──────────────────────────────────────────────────────────
from modules.scraper   import scrape_jobs
from modules.storage   import is_seen, mark_seen, seen_count
from modules.filter    import matches_keywords
from modules.scorer    import score_job
from modules.notifier  import send_job_alert

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        # Console output (captured by systemd journal)
        logging.StreamHandler(sys.stdout),
        # Rotating log file on disk
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "monitor.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

# Import after basicConfig so the handler is set up
import logging.handlers

logger = logging.getLogger("monitor")


# ── Configuration from environment ──────────────────────────────────────────
def _require_env(key: str) -> str:
    """Read a required env var; exit with a clear error if missing."""
    val = os.getenv(key, "").strip()
    if not val:
        logger.critical("Missing required environment variable: %s  (check .env)", key)
        sys.exit(1)
    return val


def _optional_env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Main pipeline ────────────────────────────────────────────────────────────

async def run() -> None:
    logger.info("=" * 60)
    logger.info("JobMon starting  |  seen jobs in DB: %d", seen_count())

    # ── 1. Load config ───────────────────────────────────────────────────────
    ojph_email      = _require_env("OJPH_EMAIL")
    ojph_password   = _require_env("OJPH_PASSWORD")
    telegram_token  = _require_env("TELEGRAM_BOT_TOKEN")
    telegram_chatid = _require_env("TELEGRAM_CHAT_ID")

    openai_key      = _optional_env("OPENAI_API_KEY")
    enable_llm      = _optional_env("ENABLE_LLM", "true").lower() == "true"
    scrape_limit    = int(_optional_env("SCRAPE_LIMIT", "5"))
    score_threshold = int(_optional_env("LLM_SCORE_THRESHOLD", "6"))

    logger.info(
        "Config loaded  |  scrape_limit=%d  enable_llm=%s  score_threshold=%d",
        scrape_limit, enable_llm, score_threshold,
    )

    # ── 2. Scrape ────────────────────────────────────────────────────────────
    logger.info("Scraping OnlineJobsPH …")
    jobs = await scrape_jobs(
        email=ojph_email,
        password=ojph_password,
        limit=scrape_limit,
    )

    if not jobs:
        logger.warning("No jobs returned from scraper. Exiting.")
        return

    logger.info("Scraped %d job(s).", len(jobs))

    # ── 3-7. Process each job ────────────────────────────────────────────────
    new_jobs_found  = 0
    alerts_sent     = 0

    for job in jobs:
        job_id = job["job_id"]
        title  = job["title"]

        # 3. Duplicate check
        if is_seen(job_id):
            logger.debug("Already seen: [%s] %s – skipping.", job_id, title)
            continue

        new_jobs_found += 1
        logger.info("New job: [%s] %s", job_id, title)

        # 4. Keyword filter
        if not matches_keywords(job):
            logger.info("  -> Filtered out (no keyword match).")
            mark_seen(job_id)   # still mark to avoid reprocessing
            continue

        logger.info("  -> Keyword match!")

        # 5. Optional LLM scoring
        score: int | None = None
        if enable_llm and openai_key:
            score = score_job(job, api_key=openai_key)

            if score is not None and score < score_threshold:
                logger.info(
                    "  -> LLM score %d < threshold %d – skipping alert.",
                    score, score_threshold,
                )
                mark_seen(job_id)
                continue

        # 6. Send Telegram alert
        sent = send_job_alert(
            bot_token=telegram_token,
            chat_id=telegram_chatid,
            job=job,
            score=score,
        )

        if sent:
            alerts_sent += 1

        # 7. Mark as seen (only after successful processing)
        mark_seen(job_id)

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info(
        "Run complete  |  new=%d  alerts_sent=%d  total_seen=%d",
        new_jobs_found, alerts_sent, seen_count(),
    )
    logger.info("=" * 60)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run())
