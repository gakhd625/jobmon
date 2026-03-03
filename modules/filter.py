"""
modules/filter.py
─────────────────
Keyword-based job filter.

Customize KEYWORDS below to match the types of work you want.
A job passes the filter if ANY keyword appears in its title or description
(case-insensitive).

This runs locally (zero API cost) before the optional LLM scoring step,
so only genuinely relevant jobs are sent to OpenAI.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── ✏️  CONFIGURE YOUR KEYWORDS HERE ────────────────────────────────────────
# Add / remove keywords to match the roles you care about.
# All comparisons are case-insensitive.
KEYWORDS: list[str] = [
    # Python / Backend
    "python",
    "django",
    "fastapi",
    "flask",
    "backend",
    "back-end",
    "back end",

    # Data / ML
    "data analyst",
    "data engineer",
    "machine learning",
    "automation",
    "scraping",
    "web scraper",

    # DevOps / Cloud
    "devops",
    "aws",
    "cloud",
    "linux",
    "docker",

    # General remote / virtual assistant roles
    "virtual assistant",
    "remote developer",
    "software engineer",
]
# ─────────────────────────────────────────────────────────────────────────────


def matches_keywords(job: dict) -> bool:
    """
    Return True if the job's title or description contains at least one
    keyword from KEYWORDS.

    `job` is expected to have 'title' and 'description' keys.
    """
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()

    for kw in KEYWORDS:
        # Use word-boundary matching to avoid false positives
        # e.g. "aws" should not match "drawstring"
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, text):
            logger.debug("Job '%s' matched keyword: '%s'", job.get("title"), kw)
            return True

    logger.debug("Job '%s' did not match any keywords – skipping.", job.get("title"))
    return False
