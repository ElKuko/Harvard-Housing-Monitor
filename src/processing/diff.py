"""
Computes the diff between today's snapshot and yesterday's snapshot.

new_units  = today_ids - yesterday_ids
gone_units = yesterday_ids - today_ids  (tracked but not alerted on currently)
"""
import logging
import sqlite3
from datetime import date, timedelta

from src.database.db import get_snapshot_ids, get_previous_snapshot_date, get_unit

logger = logging.getLogger(__name__)


def compute_new_units(conn: sqlite3.Connection, today: str) -> list[dict]:
    """
    Return full unit dicts for every unit that appears today but not yesterday.

    `today` is an ISO date string (YYYY-MM-DD).
    """
    today_ids = get_snapshot_ids(conn, today)
    logger.info("Today's snapshot: %d units", len(today_ids))

    prev_date = get_previous_snapshot_date(conn, today)

    if prev_date is None:
        logger.info(
            "No previous snapshot found – treating all %d units as new", len(today_ids)
        )
        new_ids = today_ids
    else:
        yesterday_ids = get_snapshot_ids(conn, prev_date)
        logger.info("Previous snapshot (%s): %d units", prev_date, len(yesterday_ids))
        new_ids = today_ids - yesterday_ids
        logger.info("New units: %d", len(new_ids))

    new_units: list[dict] = []
    for uid in sorted(new_ids):
        row = get_unit(conn, uid)
        if row:
            new_units.append(dict(row))

    return new_units
