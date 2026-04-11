"""
SQL schema definitions for Harvard Housing Monitor.
"""

CREATE_UNITS_TABLE = """
CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    unique_id TEXT NOT NULL UNIQUE,
    property_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    bedrooms INTEGER,
    bathrooms REAL,
    sqft INTEGER,
    rent REAL,
    lease_start_date TEXT,
    lease_end_date TEXT,
    details_url TEXT,
    detail_text TEXT,
    distance_to_hds REAL,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_DAILY_SNAPSHOT_TABLE = """
CREATE TABLE IF NOT EXISTS daily_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    unique_id TEXT NOT NULL,
    rent REAL,
    lease_start_date TEXT,
    lease_end_date TEXT,
    UNIQUE(snapshot_date, unique_id)
);
"""

CREATE_SCRAPER_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS scraper_runs (
    run_id TEXT PRIMARY KEY,
    run_date TEXT NOT NULL,
    status TEXT NOT NULL,
    properties_seen INTEGER DEFAULT 0,
    new_properties INTEGER DEFAULT 0,
    errors TEXT
);
"""

CREATE_EMAIL_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS email_log (
    email_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    sent_at TEXT,
    status TEXT NOT NULL
);
"""

ALL_TABLES = [
    CREATE_UNITS_TABLE,
    CREATE_DAILY_SNAPSHOT_TABLE,
    CREATE_SCRAPER_RUNS_TABLE,
    CREATE_EMAIL_LOG_TABLE,
]
