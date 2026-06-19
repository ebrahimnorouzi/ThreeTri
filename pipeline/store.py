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
    start_lat     REAL,                          -- rounded to ~1km for privacy
    start_lng     REAL,
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

-- AI coaching notes, kept separate so activity upserts never clobber them.
CREATE TABLE IF NOT EXISTS coach_notes (
    source        TEXT    NOT NULL,
    activity_id   TEXT    NOT NULL,
    note          TEXT    NOT NULL,
    model         TEXT,
    created_at    TEXT,
    PRIMARY KEY (source, activity_id)
);

-- Weekly per-athlete AI summaries (one per ISO week).
CREATE TABLE IF NOT EXISTS summaries (
    athlete_id    TEXT    NOT NULL,
    week_key      TEXT    NOT NULL,        -- e.g. 2026-W25
    text          TEXT    NOT NULL,
    model         TEXT,
    created_at    TEXT,
    PRIMARY KEY (athlete_id, week_key)
);
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add any columns missing from an older committed DB (CREATE TABLE
    IF NOT EXISTS won't alter an existing table)."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(activities)")}
    for col, decl in (("start_lat", "REAL"), ("start_lng", "REAL")):
        if col not in have:
            conn.execute(f"ALTER TABLE activities ADD COLUMN {col} {decl}")
    conn.commit()


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


def load_notes(conn: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """Map (source, activity_id) → coaching note."""
    cur = conn.execute("SELECT source, activity_id, note FROM coach_notes")
    return {(r["source"], r["activity_id"]): r["note"] for r in cur.fetchall()}


def save_notes(conn: sqlite3.Connection, notes: dict[tuple[str, str], str], model: str, when: str) -> int:
    rows = [(src, aid, note, model, when) for (src, aid), note in notes.items()]
    conn.executemany(
        "INSERT OR REPLACE INTO coach_notes (source, activity_id, note, model, created_at) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def load_summaries(conn: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """Map (athlete_id, week_key) → weekly summary text."""
    cur = conn.execute("SELECT athlete_id, week_key, text FROM summaries")
    return {(r["athlete_id"], r["week_key"]): r["text"] for r in cur.fetchall()}


def save_summary(conn: sqlite3.Connection, athlete_id: str, week_key: str, text: str, model: str, when: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO summaries (athlete_id, week_key, text, model, created_at) VALUES (?, ?, ?, ?, ?)",
        (athlete_id, week_key, text, model, when),
    )
    conn.commit()


def latest_summaries(conn: sqlite3.Connection) -> dict[str, str]:
    """Most recent summary text per athlete (by week_key)."""
    cur = conn.execute(
        "SELECT athlete_id, text FROM summaries WHERE (athlete_id, week_key) IN "
        "(SELECT athlete_id, MAX(week_key) FROM summaries GROUP BY athlete_id)"
    )
    return {r["athlete_id"]: r["text"] for r in cur.fetchall()}
