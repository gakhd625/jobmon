# OnlineJobsPH Job Monitor Bot

A production-ready job monitoring system that:
- Scrapes new jobs from [OnlineJobsPH](https://www.onlinejobs.ph) using Playwright
- Filters jobs by configurable keywords (zero API cost)
- Optionally scores relevant jobs with **gpt-4o-mini** (1-10 relevance score)
- Sends Telegram alerts for high-scoring matches
- Prevents duplicate alerts with a local SQLite database
- Auto-runs every 30 minutes via systemd on AWS EC2

---

## Project Structure

```
jobmon/
├── monitor.py               # Main entry point / orchestrator
├── requirements.txt
├── .env.example             # Template – copy to .env and fill in secrets
├── .gitignore
│
├── modules/
│   ├── scraper.py           # Playwright login + job scraping
│   ├── filter.py            # Keyword filter (edit KEYWORDS list here)
│   ├── scorer.py            # gpt-4o-mini relevance scoring
│   ├── notifier.py          # Telegram Bot API notifications
│   └── storage.py           # SQLite duplicate-prevention store
│
├── deploy/
│   ├── setup_ec2.sh         # One-shot EC2 bootstrap script
│   ├── jobmon.service       # systemd service file
│   └── jobmon.timer         # systemd timer (runs every 30 min)
│
├── data/                    # SQLite DB lives here (git-ignored)
└── logs/                    # Rotating log files (git-ignored)
```

---

## Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/YOUR_USER/jobmon.git && cd jobmon

# 2. Create venv
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
playwright install chromium
playwright install-deps chromium

# 5. Configure secrets
cp .env.example .env
nano .env          # fill in your credentials

# 6. Run once
python monitor.py
```

---

## Deploy to AWS EC2 (Ubuntu 22.04)

```bash
# On your EC2 instance:
git clone https://github.com/YOUR_USER/jobmon.git
cd jobmon
chmod +x deploy/setup_ec2.sh
./deploy/setup_ec2.sh

# Edit your secrets
nano .env

# Test run
./venv/bin/python monitor.py

# Check the timer is running
systemctl list-timers --all | grep jobmon

# Watch live logs
journalctl -u jobmon -f
```

The script installs dependencies, sets up the systemd service + timer,
and enables auto-start on boot. The bot will run every 30 minutes.

---

## Configuration

### Credentials (`.env`)

| Variable | Description |
|---|---|
| `OJPH_EMAIL` | Your OnlineJobsPH login email |
| `OJPH_PASSWORD` | Your OnlineJobsPH password |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Group/channel ID (get via @userinfobot) |
| `OPENAI_API_KEY` | Optional – leave blank to disable LLM scoring |
| `SCRAPE_LIMIT` | Jobs to check per run (default: 5) |
| `LLM_SCORE_THRESHOLD` | Minimum score to send alert (default: 6) |
| `ENABLE_LLM` | `true` / `false` (default: true) |

### Keywords (`modules/filter.py`)

Edit the `KEYWORDS` list to match the roles you want:

```python
KEYWORDS = [
    "python",
    "automation",
    "data engineer",
    # add your own...
]
```

---

## How LLM Cost Is Minimised

1. **Keyword filter runs first** – only jobs mentioning your keywords reach OpenAI.
2. **gpt-4o-mini** – cheapest capable model (~$0.00015 per 1K input tokens).
3. **max_tokens=50** – forces a short answer (score + one-sentence reason).
4. **temperature=0** – deterministic, no wasted creativity budget.
5. **Duplicate prevention** – jobs never scored twice.

At 5 jobs/run × 48 runs/day, assuming 20% keyword match rate = ~48 API calls/day.
Estimated cost: < $0.01/day.

---

## Redeployment (after EC2 replacement)

```bash
git clone https://github.com/YOUR_USER/jobmon.git
cd jobmon
./deploy/setup_ec2.sh
nano .env   # paste your secrets
```

Done. The SQLite DB starts fresh (no old job IDs), but that's fine —
the bot will just re-alert on recent jobs once, then never again.

---

## Troubleshooting

**Login fails**
- Check OJPH_EMAIL / OJPH_PASSWORD in `.env`
- OnlineJobsPH may have updated their login form selectors — update `scraper.py`

**No jobs scraped**
- The site's HTML structure may have changed — update `JOB_CARD_SEL` in `scraper.py`
- Run with `logging.DEBUG` to see full Playwright output

**Telegram message not arriving**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Make sure the bot is a member of the group
- For private groups, the chat ID must start with `-100`

**LLM not scoring**
- Check `OPENAI_API_KEY` is set and valid
- Set `ENABLE_LLM=false` to disable and skip scoring entirely
