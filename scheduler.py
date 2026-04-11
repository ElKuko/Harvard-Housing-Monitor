"""
APScheduler-based daily scheduler for the Harvard Housing Monitor.

Runs `main.run()` immediately on startup, then again every day at
the time configured by DAILY_RUN_TIME (e.g. "08:00").
"""
import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import DAILY_RUN_TIME

logger = logging.getLogger(__name__)


def start_scheduler():
    """Start the blocking scheduler. Runs until interrupted."""
    from main import run  # local import to avoid circular

    scheduler = BlockingScheduler()

    # Parse HH:MM
    try:
        hour, minute = [int(x) for x in DAILY_RUN_TIME.split(":")]
    except ValueError:
        logger.error("Invalid DAILY_RUN_TIME '%s' – must be HH:MM", DAILY_RUN_TIME)
        sys.exit(1)

    scheduler.add_job(
        run,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_run",
        name="Harvard Housing Daily Scrape",
        replace_existing=True,
    )

    logger.info("Scheduler started – daily run at %02d:%02d UTC", hour, minute)

    # Graceful shutdown on Ctrl-C / SIGTERM
    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler …")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Run once immediately, then on schedule
    logger.info("Running initial scrape …")
    run()

    scheduler.start()
