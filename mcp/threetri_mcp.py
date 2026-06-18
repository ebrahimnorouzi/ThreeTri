"""ThreeTri MCP server — "Ask Your Own Data".

Exposes the training history (the SQLite store the pipeline builds) to an AI
client like Claude Desktop / Claude Code, so you can ask things like:

    "Compare my run volume to Sia's over the last 6 weeks."
    "Is Alborz's easy pace improving at the same heart rate, month over month?"
    "Who has the most consistent week-on-week build toward the race?"

This is the guide's Level 3 / "Ask Your Own Data" idea done right: MCP reads your
own unified store (it is NOT how the unattended pipeline fetches data).

Run it via Claude — see SETUP.md for registration. The DB path comes from the
THREETRI_DB env var (default: ../data/threetri.db; point it at data/sample.db to
explore the demo data before you have real data).

    pip install "mcp[cli]"      # official MCP Python SDK (Python >= 3.10)

GOTCHA: this is a stdio server — it must NEVER print to stdout (that carries the
JSON-RPC protocol). All logs go to stderr.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s %(levelname)s threetri-mcp: %(message)s")
log = logging.getLogger("threetri-mcp")

mcp = FastMCP("threetri")

ATHLETE_NAMES = {"ebi": "Ebi", "sia": "Sia", "alborz": "Alborz"}


def _db_path() -> Path:
    env = os.environ.get("THREETRI_DB")
    if env:
        return Path(env).expanduser().resolve()
    return (Path(__file__).resolve().parent.parent / "data" / "threetri.db")


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Training DB not found at {path}. Run the pipeline, or set THREETRI_DB "
            f"to data/sample.db to use the demo data."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)  # read-only
    conn.row_factory = sqlite3.Row
    return conn


def _enrich(r: dict) -> dict:
    """Add convenience fields (km, minutes, pace) to a raw activity row."""
    dist_km = (r.get("distance_m") or 0) / 1000.0
    mv_s = r.get("moving_s") or 0
    out = {
        "athlete": ATHLETE_NAMES.get(r.get("athlete_id"), r.get("athlete_id")),
        "date": r.get("day"),
        "sport": r.get("sport"),
        "name": r.get("name"),
        "distance_km": round(dist_km, 2),
        "moving_min": round(mv_s / 60.0, 1),
        "elevation_m": round(r.get("elevation_m") or 0),
        "avg_hr": r.get("avg_hr"),
    }
    if dist_km > 0 and mv_s > 0:
        if r.get("sport") == "bike":
            out["pace"] = f"{dist_km / (mv_s / 3600):.1f} km/h"
        elif r.get("sport") == "swim":
            s100 = mv_s / (dist_km * 10)
            out["pace"] = f"{int(s100 // 60)}:{int(s100 % 60):02d} /100m"
        else:
            spk = mv_s / dist_km
            out["pace"] = f"{int(spk // 60)}:{int(spk % 60):02d} /km"
    return out


@mcp.tool()
def list_athletes() -> list[dict[str, Any]]:
    """List athletes with their activity counts and date span."""
    with closing(_connect()) as c:
        rows = c.execute(
            "SELECT athlete_id, COUNT(*) n, MIN(day) first, MAX(day) last "
            "FROM activities GROUP BY athlete_id ORDER BY n DESC"
        ).fetchall()
    return [{"id": r["athlete_id"], "name": ATHLETE_NAMES.get(r["athlete_id"], r["athlete_id"]),
             "activities": r["n"], "from": r["first"], "to": r["last"]} for r in rows]


@mcp.tool()
def query_activities(athlete_id: str, sport: str | None = None,
                     since: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Return an athlete's activities, newest first.

    Args:
        athlete_id: one of 'ebi', 'sia', 'alborz'.
        sport: optional filter — 'swim', 'bike' or 'run'.
        since: optional ISO date 'YYYY-MM-DD'; only activities on/after it.
        limit: max rows (default 200).
    """
    sql = "SELECT * FROM activities WHERE athlete_id = ?"
    params: list[Any] = [athlete_id]
    if sport:
        sql += " AND sport = ?"; params.append(sport)
    if since:
        sql += " AND day >= ?"; params.append(since)
    sql += " ORDER BY day DESC, start_local DESC LIMIT ?"; params.append(int(limit))
    with closing(_connect()) as c:
        return [_enrich(dict(r)) for r in c.execute(sql, params)]


@mcp.tool()
def weekly_totals(athlete_id: str, sport: str | None = None) -> list[dict[str, Any]]:
    """Aggregate an athlete's training by ISO week: distance, hours, sessions."""
    sql = ("SELECT day, sport, distance_m, moving_s FROM activities WHERE athlete_id = ?")
    params: list[Any] = [athlete_id]
    if sport:
        sql += " AND sport = ?"; params.append(sport)
    buckets: dict[str, dict[str, float]] = {}
    with closing(_connect()) as c:
        for r in c.execute(sql, params):
            y, w, _ = datetime.fromisoformat(r["day"]).isocalendar()
            key = f"{y}-W{w:02d}"
            b = buckets.setdefault(key, {"sessions": 0, "distance_km": 0.0, "hours": 0.0})
            b["sessions"] += 1
            b["distance_km"] += (r["distance_m"] or 0) / 1000.0
            b["hours"] += (r["moving_s"] or 0) / 3600.0
    return [{"week": k, "sessions": v["sessions"],
             "distance_km": round(v["distance_km"], 1), "hours": round(v["hours"], 1)}
            for k, v in sorted(buckets.items())]


@mcp.tool()
def season_summary(since: str | None = None) -> dict[str, Any]:
    """Head-to-head season totals per athlete and per sport (distance km, hours,
    sessions, elevation). Optionally restrict to activities since an ISO date."""
    sql = ("SELECT athlete_id, sport, COUNT(*) n, SUM(distance_m) dm, "
           "SUM(moving_s) ms, SUM(elevation_m) em FROM activities")
    params: list[Any] = []
    if since:
        sql += " WHERE day >= ?"; params.append(since)
    sql += " GROUP BY athlete_id, sport"
    out: dict[str, Any] = {}
    with closing(_connect()) as c:
        for r in c.execute(sql, params):
            a = out.setdefault(ATHLETE_NAMES.get(r["athlete_id"], r["athlete_id"]),
                               {"swim": {}, "bike": {}, "run": {}, "total_km": 0.0})
            km = (r["dm"] or 0) / 1000.0
            a[r["sport"]] = {"km": round(km, 1), "hours": round((r["ms"] or 0) / 3600.0, 1),
                             "sessions": r["n"], "elevation_m": round(r["em"] or 0)}
            a["total_km"] = round(a["total_km"] + km, 1)
    return out


@mcp.tool()
def wellness_recent(athlete_id: str, days: int = 14) -> list[dict[str, Any]]:
    """Recent Garmin wellness (sleep, HRV, resting HR, body battery, readiness)
    for an athlete, newest first. Empty if Garmin was not configured."""
    with closing(_connect()) as c:
        rows = c.execute(
            "SELECT * FROM wellness WHERE athlete_id = ? ORDER BY date DESC LIMIT ?",
            [athlete_id, int(days)],
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.resource("schema://threetri")
def schema() -> str:
    """The DB schema plus a quick summary, so the model knows what it can query."""
    lines = [f"# ThreeTri training store\nDB: {_db_path()}\n", "## Tables"]
    try:
        with closing(_connect()) as c:
            for r in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"):
                lines.append(r["sql"])
            n = c.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
            span = c.execute("SELECT MIN(day), MAX(day) FROM activities").fetchone()
            lines.append(f"\n## Summary\nactivities: {n}\ndate range: {span[0]} .. {span[1]}")
            lines.append("athlete_id values: ebi, sia, alborz | sport values: swim, bike, run")
    except FileNotFoundError as exc:
        lines.append(f"(DB unavailable: {exc})")
    return "\n".join(lines)


def main() -> None:
    log.info("Starting ThreeTri MCP server (db=%s)", _db_path())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
