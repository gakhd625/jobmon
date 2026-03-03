"""
modules/scraper.py
──────────────────
Playwright-based scraper for OnlineJobsPH.

Flow:
  1. Launch a headless Chromium browser.
  2. Log in with credentials from .env.
  3. Navigate to the employer job listings page.
  4. Extract the top N newest jobs (job_id, title, description, link, posted_date).
  5. Return a list of dicts.

Anti-detection measures:
  • Random delay between page actions.
  • Realistic user-agent string.
  • Viewport mimics a real laptop screen.
"""

import asyncio
import logging
import random
import re
from typing import Optional
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)

# ── Selectors ────────────────────────────────────────────────────────────────
LOGIN_URL       = "https://www.onlinejobs.ph/login"
JOBS_URL        = "https://www.onlinejobs.ph/jobseekers/joblist"

# Update these if login selectors change
EMAIL_SEL       = "input[name='info[email]'], #login_username"
PASSWORD_SEL    = "input[name='password'], input[type='password']"
SUBMIT_SEL      = "button[type='submit']"

JOB_CARD_SEL    = ".jobpost-item, .job-post-item, article.job-item"

# ── Random delay to mimic human browsing
async def _random_delay(min_s: float = 1.2, max_s: float = 3.5) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


# ── Login function
async def _login(page: Page, email: str, password: str) -> bool:
    try:
        logger.info("Navigating to login page …")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
        await _random_delay()

        # DEBUG: save screenshot to check if form loaded
        await page.screenshot(path="login_debug.png")

        # Fill credentials
        await page.fill(EMAIL_SEL, email)
        await _random_delay(0.4, 1.0)
        await page.fill(PASSWORD_SEL, password)
        await _random_delay(0.4, 1.0)

        # Submit and wait for navigation
        await page.click(SUBMIT_SEL)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        await _random_delay()

        # Verify login succeeded by checking URL
        current_url = page.url
        if "login" in current_url.lower():
            logger.error("Login appears to have failed (still on login page).")
            await page.screenshot(path="login_failed.png")
            return False

        logger.info("Login successful.")
        await page.screenshot(path="login_success.png")
        return True

    except Exception as exc:
        logger.error("Login error: %s", exc)
        await page.screenshot(path="login_exception.png")
        return False


# ── Extract numeric job ID from URL
def _extract_job_id(href: str) -> Optional[str]:
    match = re.search(r"/(\d{5,})", href)
    return match.group(1) if match else None


# ── Scrape job cards
async def _scrape_job_cards(page: Page, limit: int) -> list[dict]:
    jobs: list[dict] = []
    try:
        logger.info("Navigating to job listings …")
        await page.goto(JOBS_URL, wait_until="networkidle", timeout=30_000)
        await _random_delay()

        await page.wait_for_selector(JOB_CARD_SEL, timeout=15_000)
        cards = await page.query_selector_all(JOB_CARD_SEL)
        logger.info("Found %d job cards on page (limiting to %d).", len(cards), limit)

        for card in cards[:limit]:
            try:
                title_el = await card.query_selector("h2, h3, .job-title, .jobpost-title")
                title = (await title_el.inner_text()).strip() if title_el else "No title"

                link_el = await card.query_selector("a[href*='/jobseekers/info/'], a[href*='/job/']")
                if not link_el:
                    link_el = await card.query_selector("a")
                href = await link_el.get_attribute("href") if link_el else ""
                link = f"https://www.onlinejobs.ph{href}" if href.startswith("/") else href

                job_id = _extract_job_id(href) or f"unknown_{random.randint(100000, 999999)}"

                desc_el = await card.query_selector(".job-description, .jobpost-description, p.description, .job-excerpt")
                description = (await desc_el.inner_text()).strip() if desc_el else ""

                date_el = await card.query_selector(".posted-date, .job-date, time, [class*='date']")
                posted_date = (await date_el.inner_text()).strip() if date_el else "Unknown"

                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "description": description[:800],
                    "link": link,
                    "posted_date": posted_date,
                })

                await _random_delay(0.3, 0.8)

            except Exception as exc:
                logger.warning("Error parsing a job card: %s", exc)
                continue

    except Exception as exc:
        logger.error("Error scraping job cards: %s", exc)

    return jobs


# ── Main scraping entry
async def scrape_jobs(email: str, password: str, limit: int = 5) -> list[dict]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,  # ← IMPORTANT: must be True on EC2
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )

        page = await context.new_page()

        try:
            logged_in = await _login(page, email, password)
            if not logged_in:
                return []

            jobs = await _scrape_job_cards(page, limit)
            return jobs

        finally:
            await browser.close()