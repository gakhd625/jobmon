"""
modules/notifier.py
Sends job alert messages to a Telegram group/channel via the Bot API.
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_job_alert(
    bot_token: str,
    chat_id: str,
    job: dict,
    score: Optional[int] = None,
) -> bool:
    """
    Send a formatted job notification to Telegram.

    Parameters
    ----------
    bot_token : Telegram bot token from @BotFather
    chat_id   : Target group/channel ID (negative for groups)
    job       : Dict with title, link, posted_date keys
    score     : Optional LLM score (1-10); omitted from message if None

    Returns True on success, False on failure.
    """
    if not bot_token or not chat_id:
        logger.error("Telegram bot_token or chat_id is missing -- cannot send alert.")
        return False

    # Build the message
    score_line = f"Score: {score}/10\n" if score is not None else ""
    title      = job.get("title", "Untitled Job")
    link       = job.get("link", "")
    posted     = job.get("posted_date", "Unknown")

    safe_title = _escape_md(title)

    message = (
        "New Job Match!\n\n"
        f"Job: {safe_title}\n"
        f"{score_line}"
        f"Posted: {posted}\n"
        f"Link: {link}"
    )

    url = TELEGRAM_API.format(token=bot_token)
    payload = {
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Telegram alert sent for job: %s", title)
        return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Telegram API HTTP error %s: %s", exc.response.status_code, exc.response.text
        )
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)

    return False


def _escape_md(text: str) -> str:
    """Escape Telegram MarkdownV1 special characters."""
    for ch in ["_", "*", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text
