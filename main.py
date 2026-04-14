"""
Harvard Housing Daily Listing Monitor – main entry point.

Usage:
    python main.py            # run once immediately
    python main.py --schedule # run once now, then daily at DAILY_RUN_TIME
"""
import argparse
import logging
import sys
import uuid
from datetime import date, datetime

from pathlib import Path
from playwright.sync_api import sync_playwright

import config
from src.database import db
from src.scraper.login import login
from src.scraper.listing_extractor import extract_listings
from src.scraper.detail_extractor import extract_detail
from src.processing.normalizer import normalise
from src.processing.diff import compute_new_units
from src.processing.distance import compute_distance
from src.notifier.email_sender import send_daily_email

Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/monitor.log"),
    ],
)
logger = logging.getLogger(__name__)


def run() -> None:
    """Execute one full scrape-process-notify cycle."""
    run_id   = str(uuid.uuid4())
    run_date = date.today().isoformat()

    logger.info("=" * 60)
    logger.info("Starting run %s on %s", run_id, run_date)
    logger.info("=" * 60)

    # ── Initialise DB ────────────────────────────────────────────────────────
    db.init_db()

    with db.transaction() as conn:
        db.create_run(conn, run_id, run_date)

    # ── Browser session ──────────────────────────────────────────────────────
    units_today: list[dict] = []
    run_errors: list[str]   = []

    try:
        with sync_playwright() as pw:
            # Use a persistent context so Cloudflare cookies (cf_clearance)
            # are saved between runs and the browser challenge only appears once.
            Path(config.BROWSER_USER_DATA_DIR).mkdir(parents=True, exist_ok=True)
            context = pw.chromium.launch_persistent_context(
                user_data_dir=config.BROWSER_USER_DATA_DIR,
                headless=config.HEADLESS,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
            )
            # Apply stealth to hide Playwright automation signals
            try:
                from playwright_stealth import stealth_sync
                stealth_sync(context.pages[0] if context.pages else context.new_page())
            except ImportError:
                logger.warning("playwright-stealth not installed – skipping stealth mode")

            browser = context
            page    = context.new_page()

            # ── 1. Login ─────────────────────────────────────────────────────
            try:
                login(page)
            except RuntimeError as exc:
                _fail_run(run_id, run_date, str(exc))
                return

            # ── 2. Extract listings ──────────────────────────────────────────
            try:
                raw_rows = extract_listings(page)
            except RuntimeError as exc:
                _fail_run(run_id, run_date, str(exc))
                return

            logger.info("Raw rows extracted: %d", len(raw_rows))

            # ── 3. Normalise ─────────────────────────────────────────────────
            for raw in raw_rows:
                unit = normalise(raw)
                if unit:
                    units_today.append(unit)

            logger.info("Units after normalisation: %d", len(units_today))

            # ── 4. Detail pages ──────────────────────────────────────────────
            for unit in units_today:
                url = unit.get("details_url")
                if url:
                    try:
                        unit["detail_text"] = extract_detail(browser, url)
                    except Exception as exc:
                        logger.warning("Detail extraction failed for %s: %s", unit["unique_id"], exc)
                        run_errors.append(f"detail:{unit['unique_id']}:{exc}")

            browser.close()

    except Exception as exc:
        logger.exception("Unexpected browser error")
        _fail_run(run_id, run_date, str(exc))
        return

    # ── 5. Distance calculation ──────────────────────────────────────────────
    logger.info("Computing distances to HDS …")
    for unit in units_today:
        try:
            unit["distance_to_hds"] = compute_distance(unit["property_name"])
        except Exception as exc:
            logger.warning("Distance failed for %s: %s", unit["property_name"], exc)
            run_errors.append(f"distance:{unit['unique_id']}:{exc}")

    # ── 6. Persist to DB ─────────────────────────────────────────────────────
    active_ids: list[str] = []
    new_count = 0

    with db.transaction() as conn:
        for unit in units_today:
            is_new = db.upsert_unit(conn, unit)
            db.insert_snapshot(conn, run_date, unit)
            active_ids.append(unit["unique_id"])
            if is_new:
                new_count += 1

        db.mark_inactive_units(conn, active_ids)

    logger.info(
        "DB updated: %d total, %d new, %d marked inactive",
        len(units_today),
        new_count,
        len(active_ids),
    )

    # ── 7. Diff ──────────────────────────────────────────────────────────────
    with db.transaction() as conn:
        new_units = compute_new_units(conn, run_date)

    logger.info("New units detected: %d", len(new_units))

    # ── 8. Send email ─────────────────────────────────────────────────────────
    subject, body, email_ok = send_daily_email(
        new_units=new_units,
        total_scanned=len(units_today),
        run_id=run_id,
    )

    sent_at = datetime.utcnow().isoformat() if email_ok else None
    email_status = "sent" if email_ok else "failed"

    with db.transaction() as conn:
        db.log_email(
            conn,
            run_id=run_id,
            recipient=config.EMAIL_TO,
            subject=subject,
            status=email_status,
            sent_at=sent_at,
        )

        db.update_run(
            conn,
            run_id=run_id,
            status="success",
            properties_seen=len(units_today),
            new_properties=len(new_units),
            errors="; ".join(run_errors) if run_errors else None,
        )

    logger.info("Run %s completed successfully", run_id)


def _fail_run(run_id: str, run_date: str, error: str) -> None:
    logger.error("Run %s FAILED: %s", run_id, error)
    try:
        with db.transaction() as conn:
            db.update_run(conn, run_id, status="failed", errors=error)
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harvard Housing Monitor")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run once now, then schedule daily at DAILY_RUN_TIME",
    )
    args = parser.parse_args()

    if args.schedule:
        from scheduler import start_scheduler
        start_scheduler()
    else:
        run()
