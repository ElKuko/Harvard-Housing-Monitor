"""
Database access layer for Harvard Housing Monitor.
"""
import sqlite3
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from config import DB_PATH
from src.database.models import ALL_TABLES

logger = logging.getLogger(__name__)


def _ensure_db_dir():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with transaction() as conn:
        for ddl in ALL_TABLES:
            conn.execute(ddl)
    logger.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def upsert_unit(conn: sqlite3.Connection, unit: dict) -> bool:
    """
    Insert or update a unit record.
    Returns True if this was a brand-new insertion.
    """
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    existing = conn.execute(
        "SELECT id FROM units WHERE unique_id = ?", (unit["unique_id"],)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE units SET
                property_name    = ?,
                unit             = ?,
                bedrooms         = ?,
                bathrooms        = ?,
                sqft             = ?,
                rent             = ?,
                lease_start_date = ?,
                lease_end_date   = ?,
                details_url      = ?,
                detail_text      = COALESCE(?, detail_text),
                distance_to_hds  = COALESCE(?, distance_to_hds),
                last_seen_date   = ?,
                is_active        = 1,
                updated_at       = ?
            WHERE unique_id = ?
            """,
            (
                unit["property_name"],
                unit["unit"],
                unit.get("bedrooms"),
                unit.get("bathrooms"),
                unit.get("sqft"),
                unit.get("rent"),
                unit.get("lease_start_date"),
                unit.get("lease_end_date"),
                unit.get("details_url"),
                unit.get("detail_text"),
                unit.get("distance_to_hds"),
                today,
                now,
                unit["unique_id"],
            ),
        )
        return False
    else:
        conn.execute(
            """
            INSERT INTO units (
                id, unique_id, property_name, unit, bedrooms, bathrooms,
                sqft, rent, lease_start_date, lease_end_date, details_url,
                detail_text, distance_to_hds, first_seen_date, last_seen_date,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                unit["unique_id"],
                unit["property_name"],
                unit["unit"],
                unit.get("bedrooms"),
                unit.get("bathrooms"),
                unit.get("sqft"),
                unit.get("rent"),
                unit.get("lease_start_date"),
                unit.get("lease_end_date"),
                unit.get("details_url"),
                unit.get("detail_text"),
                unit.get("distance_to_hds"),
                today,
                today,
                now,
                now,
            ),
        )
        return True


def mark_inactive_units(conn: sqlite3.Connection, active_ids: list[str]):
    """Mark any unit NOT in active_ids as inactive."""
    if not active_ids:
        return
    placeholders = ",".join("?" * len(active_ids))
    now = datetime.utcnow().isoformat()
    conn.execute(
        f"""
        UPDATE units SET is_active = 0, updated_at = ?
        WHERE unique_id NOT IN ({placeholders}) AND is_active = 1
        """,
        [now] + active_ids,
    )


def get_unit(conn: sqlite3.Connection, unique_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM units WHERE unique_id = ?", (unique_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Daily Snapshots
# ---------------------------------------------------------------------------

def insert_snapshot(conn: sqlite3.Connection, snapshot_date: str, unit: dict):
    conn.execute(
        """
        INSERT OR REPLACE INTO daily_snapshot
            (snapshot_date, unique_id, rent, lease_start_date, lease_end_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            snapshot_date,
            unit["unique_id"],
            unit.get("rent"),
            unit.get("lease_start_date"),
            unit.get("lease_end_date"),
        ),
    )


def get_snapshot_ids(conn: sqlite3.Connection, snapshot_date: str) -> set[str]:
    rows = conn.execute(
        "SELECT unique_id FROM daily_snapshot WHERE snapshot_date = ?",
        (snapshot_date,),
    ).fetchall()
    return {row["unique_id"] for row in rows}


def get_previous_snapshot_date(conn: sqlite3.Connection, before_date: str) -> Optional[str]:
    row = conn.execute(
        """
        SELECT MAX(snapshot_date) AS prev
        FROM daily_snapshot
        WHERE snapshot_date < ?
        """,
        (before_date,),
    ).fetchone()
    return row["prev"] if row else None


# ---------------------------------------------------------------------------
# Scraper Runs
# ---------------------------------------------------------------------------

def create_run(conn: sqlite3.Connection, run_id: str, run_date: str):
    conn.execute(
        "INSERT INTO scraper_runs (run_id, run_date, status) VALUES (?, ?, 'running')",
        (run_id, run_date),
    )


def update_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    properties_seen: int = 0,
    new_properties: int = 0,
    errors: Optional[str] = None,
):
    conn.execute(
        """
        UPDATE scraper_runs SET
            status = ?,
            properties_seen = ?,
            new_properties = ?,
            errors = ?
        WHERE run_id = ?
        """,
        (status, properties_seen, new_properties, errors, run_id),
    )


# ---------------------------------------------------------------------------
# Email Log
# ---------------------------------------------------------------------------

def log_email(
    conn: sqlite3.Connection,
    run_id: str,
    recipient: str,
    subject: str,
    status: str,
    sent_at: Optional[str] = None,
):
    conn.execute(
        """
        INSERT INTO email_log (email_id, run_id, recipient, subject, sent_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), run_id, recipient, subject, sent_at, status),
    )
