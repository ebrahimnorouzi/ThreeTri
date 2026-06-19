"""The nightly job — fetch → store → compute → publish (Garmin-only).

Run by the GitHub Action (and locally for testing):

    python pipeline/run.py                 # incremental: fetch since last sync
    python pipeline/run.py --full          # re-fetch the whole season
    python pipeline/run.py --garmin-days 21  # widen the wellness window

It pulls BOTH activities (swim/bike/run) and wellness (sleep/HRV/…) from Garmin
Connect, one login per athlete. Incremental and idempotent: only activities
since the last stored day (minus a 2-day overlap) are fetched, then upserted
into the SQLite store. The dashboard is rebuilt from the entire store each run.

Needs these GitHub Secrets:
    GARMIN_TOKEN_EBI, GARMIN_TOKEN_SIA, GARMIN_TOKEN_ALBORZ   (per athlete)

(Strava is dormant in this setup — pipeline/strava.py is kept for if you ever
get a Strava subscription and want to switch back / add it.)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone, date

from config import ATHLETES, SEASON_START
import store
import garmin
import coach
from compute import assemble_dashboard
from sample_data import SITE_DATA  # reuse the canonical output path


def _latest_day_by_athlete(activities) -> dict[str, date]:
    latest: dict[str, date] = {}
    for a in activities:
        d = a.day
        if a.athlete_id not in latest or d > latest[a.athlete_id]:
            latest[a.athlete_id] = d
    return latest


def main() -> int:
    ap = argparse.ArgumentParser(description="ThreeTri nightly pipeline (Garmin-only)")
    ap.add_argument("--full", action="store_true", help="re-fetch the whole season, ignoring last sync")
    ap.add_argument("--garmin-days", type=int, default=14, help="how many days of wellness to fetch")
    args = ap.parse_args()

    season_start = date.fromisoformat(SEASON_START)
    today = datetime.now(timezone.utc).date()

    conn = store.connect()
    existing = store.load_activities(conn)
    latest = _latest_day_by_athlete(existing)
    print(f"Store: {len(existing)} activities on disk")

    new_activities = []
    new_wellness = []

    for ath in ATHLETES:
        if args.full or ath["id"] not in latest:
            after = season_start
        else:
            after = max(season_start, latest[ath["id"]] - timedelta(days=2))  # 2-day overlap

        acts, wellness = garmin.fetch_athlete(ath, after, today, wellness_days=args.garmin_days)
        new_activities.extend(acts)
        new_wellness.extend(wellness)

    if new_activities:
        store.save_activities(conn, new_activities)
    if new_wellness:
        store.save_wellness(conn, new_wellness)

    activities = store.load_activities(conn)
    wellness = store.load_wellness(conn)

    # Optional per-activity AI coaching (no-op without ANTHROPIC_API_KEY).
    existing_notes = store.load_notes(conn)
    new_notes, model, when = coach.analyze(activities, existing_notes)
    if new_notes:
        store.save_notes(conn, new_notes, model, when)
    notes = store.load_notes(conn)

    conn.close()

    if not activities:
        # Nothing real yet (e.g. secrets not configured). Don't leave/commit an
        # empty schema-only DB — remove it so the nightly job makes no noisy commit.
        try:
            store.DEFAULT_DB.unlink(missing_ok=True)
        except OSError:
            pass
        print("No activities in store and none fetched — keeping existing dashboard.json "
              "(misconfigured run? check the GARMIN_TOKEN_* secrets and that tokens haven't expired).")
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    dashboard = assemble_dashboard(activities, wellness, now, notes=notes)

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    out = SITE_DATA / "dashboard.json"
    out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote {out}")
    print(f"  {len(activities)} activities · {len(wellness)} wellness rows · "
          f"+{len(new_activities)} new this run")
    print(f"  {dashboard['race']['days_to_go']} days to {dashboard['race']['short_name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
