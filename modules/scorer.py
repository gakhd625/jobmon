"""
modules/scorer.py
─────────────────
Optional LLM-based job relevance scorer using gpt-4o-mini.

Design choices to minimise API spend:
  • Only called AFTER keyword filter passes  (most jobs never reach here).
  • Temperature 0  → deterministic, no wasted tokens on creativity.
  • max_tokens 50  → single-number answer + brief reason is all we need.
  • Prompt is short and tightly scoped.

Returns an integer score 1–10, or None if scoring is disabled / fails.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Prompt template ──────────────────────────────────────────────────────────
# The model must reply with ONLY a JSON object: {"score": N, "reason": "…"}
# Keeping the output structured lets us parse it reliably.
SYSTEM_PROMPT = """\
You are a job relevance evaluator. Given a job title and description,
rate how relevant the role is to a skilled Python developer / automation
engineer who specialises in web scraping, data pipelines, and DevOps.

Reply with ONLY a JSON object in this exact format (no markdown, no extra text):
{"score": <integer 1-10>, "reason": "<one sentence max>"}

Scoring guide:
  9-10 = Perfect fit (Python, automation, scraping, DevOps)
  7-8  = Good fit (adjacent tech, software engineer, data roles)
  5-6  = Possible fit (some overlap, but unclear)
  1-4  = Not relevant (unrelated field)
"""


def score_job(job: dict, api_key: str) -> Optional[int]:
    """
    Call gpt-4o-mini to score the job.
    Returns an integer 1–10, or None on error / disabled.

    Parameters
    ----------
    job     : dict with 'title' and 'description' keys
    api_key : OpenAI API key string
    """
    if not api_key:
        logger.info("No OpenAI API key configured – skipping LLM scoring.")
        return None

    try:
        # Import here so the module loads even if openai isn't installed
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        user_message = (
            f"Job title: {job.get('title', 'N/A')}\n\n"
            f"Job description:\n{job.get('description', 'N/A')[:600]}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=50,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
        )

        raw = response.choices[0].message.content.strip()
        logger.debug("LLM raw response for '%s': %s", job.get("title"), raw)

        # Parse {"score": N, "reason": "…"}
        match = re.search(r'"score"\s*:\s*(\d+)', raw)
        if match:
            score = int(match.group(1))
            score = max(1, min(10, score))  # clamp to 1–10

            reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', raw)
            reason = reason_match.group(1) if reason_match else ""
            logger.info(
                "LLM score for '%s': %d/10  (%s)", job.get("title"), score, reason
            )
            return score
        else:
            logger.warning("Could not parse LLM response: %s", raw)
            return None

    except Exception as exc:
        logger.error("LLM scoring error for '%s': %s", job.get("title"), exc)
        return None
