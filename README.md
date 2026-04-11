# Harvard Housing Daily Listing Monitor

Automated system that logs into the Harvard Housing portal daily, extracts all apartment listings, detects new units, and sends an email summary.

---

## Features

- Multi-step browser login via Playwright (handles JavaScript-rendered UI)
- Full listing extraction with pagination support
- Detail page content extraction per unit
- Geodesic distance from each property to Harvard Divinity School
- Daily snapshot comparison to identify new listings
- SMTP email notification (plain text + HTML)
- SQLite database with full history
- APScheduler-based daily automation

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your Harvard Housing credentials, SMTP settings, and preferences.

### 3. Run once

```bash
python main.py
```

### 4. Run on a daily schedule

```bash
python main.py --schedule
```

The scheduler runs an immediate scrape on startup, then repeats at `DAILY_RUN_TIME` (UTC) every day.

---

## Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `HH_EMAIL` | Harvard Housing portal email | required |
| `HH_PASSWORD` | Harvard Housing portal password | required |
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP authentication username | required |
| `SMTP_PASSWORD` | SMTP app password | required |
| `EMAIL_FROM` | Sender address | required |
| `EMAIL_TO` | Recipient address | required |
| `DB_PATH` | SQLite database path | `data/housing.db` |
| `DAILY_RUN_TIME` | Daily run time (HH:MM UTC) | `08:00` |
| `HEADLESS` | Run browser headlessly | `true` |

---

## Database Schema

| Table | Purpose |
|---|---|
| `units` | One row per unique property+unit, with full history |
| `daily_snapshot` | Every unit seen on each run date |
| `scraper_runs` | Audit log of each run |
| `email_log` | Record of emails sent |

---

## Project Structure

```
├── main.py                      # Entry point / runner
├── scheduler.py                 # APScheduler wrapper
├── config.py                    # Centralised config
├── requirements.txt
├── .env.example
└── src/
    ├── database/
    │   ├── models.py            # SQL DDL
    │   └── db.py                # Data access layer
    ├── scraper/
    │   ├── login.py             # Multi-step portal login
    │   ├── listing_extractor.py # Parse listing table
    │   └── detail_extractor.py  # Fetch individual detail pages
    ├── processing/
    │   ├── normalizer.py        # Clean raw scraped values
    │   ├── diff.py              # New-unit detection logic
    │   └── distance.py          # Geocode + distance to HDS
    └── notifier/
        └── email_sender.py      # Build and send daily email
```
