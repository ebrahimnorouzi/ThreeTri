"""SQLite store — the durable history that lives in the repo.

The nightly job merges newly fetched activities/wellness into this DB (committed
back to the repo for a full season of history), then `compute.py` reads it all
back to rebuild the dashboard. The same DB is what the MCP server queries for
"Ask Your Own Data" coaching.

Idempotent: activities upsert on (source, activity_id); wellness upserts on
(athlete_id, date). Re-running the pipeline never duplicates rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from models import Activity, DailyWellness

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "threetri.db"

_ACTIVITY_COLS = list(Activity.__dataclass_fields__.keys())
_WELLNESS_COLS = list(DailyWellness.__dataclass_fields__.keys())

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    athlete_id    TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    activity_id   TEXT    NOT NULL,
    sport         TEXT    NOT NULL,           -- 'swim' | 'bike' | 'run'
    name          TEXT,
    start_local   TEXT    NOT NULL,           -- ISO datetime, athlete local tz
    day           TEXT    NOT NULL,           -- ISO date (derived, for easy filtering)
    distance_m    REAL    NOT NULL DEFAULT 0,
    moving_s      INTEGER NOT NULL DEFAULT 0,
    elapsed_s     INTEGER NOT NULL DEFAULT 0,
    elevation_m   REAL    NOT NULL DEFAULT 0,
    avg_hr        REAL,
    max_hr        REAL,
    avg_speed     REAL,
    suffer_score  REAL,
    kudos         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, activity_id)
);
CREATE INDEX IF NOT EXISTS idx_act_athlete_day ON activities(athlete_id, day);
CREATE INDEX IF NOT EXISTS idx_act_sport ON activities(sport);

CREATE TABLE IF NOT EXISTS wellness (
    athlete_id    TEXT    NOT NULL,
    date          TEXT    NOT NULL,           -- ISO date
    hrv           REAL,
    rhr           REAL,
    sleep_hours   REAL,
    sleep_score   REAL,
    body_battery  REAL,
    stress_avg    REAL,
    readiness     REAL,
    PRIMARY KEY (athlete_id, date)
);
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_activities(conn: sqlite3.Connection, activities: list[Activity]) -> int:
    cols = _ACTIVITY_COLS + ["day"]
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT OR REPLACE INTO activities ({', '.join(cols)}) VALUES ({placeholders})"
    rows = []
    for a in activities:
        row = a.to_row()
        rows.append([row[c] for c in _ACTIVITY_COLS] + [a.day.isoformat()])
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def save_wellness(conn: sqlite3.Connection, wellness: list[DailyWellness]) -> int:
    placeholders = ", ".join("?" for _ in _WELLNESS_COLS)
    sql = f"INSERT OR REPLACE INTO wellness ({', '.join(_WELLNESS_COLS)}) VALUES ({placeholders})"
    rows = [[w.to_row()[c] for c in _WELLNESS_COLS] for w in wellness]
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def load_activities(conn: sqlite3.Connection) -> list[Activity]:
    cur = conn.execute(f"SELECT {', '.join(_ACTIVITY_COLS)} FROM activities")
    return [Activity.from_row(dict(r)) for r in cur.fetchall()]


def load_wellness(conn: sqlite3.Connection) -> list[DailyWellness]:
    cur = conn.execute(f"SELECT {', '.join(_WELLNESS_COLS)} FROM wellness")
    return [DailyWellness.from_row(dict(r)) for r in cur.fetchall()]
