"""The nightly job — fetch → store → compute → publish.

Run by the GitHub Action (and locally for testing):

    python pipeline/run.py                 # incremental: fetch since last sync
    python pipeline/run.py --full          # re-fetch the whole season
    python pipeline/run.py --no-garmin     # Strava only
    python pipeline/run.py --garmin-days 21

It is incremental and idempotent: only activities since the last stored day
(minus a 2-day overlap to catch edits) are fetched, then upserted into the
SQLite store. The dashboard is rebuilt from the *entire* store every time, so
trends and totals always reflect full history.

Needs these env vars / GitHub Secrets:
    STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET           (shared app)
    STRAVA_REFRESH_TOKEN_<EBI|SIA|ALBORZ>            (per athlete)
    GARMIN_TOKEN_<EBI|SIA|ALBORZ>                    (per athlete, optional)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from config import ATHLETES
import store
import strava
import garmin
from compute import assemble_dashboard
from sample_data import SITE_DATA  # reuse the canonical output path


def _latest_day_by_athlete(activities) -> dict[str, object]:
    latest: dict[str, object] = {}
    for a in activities:
        d = a.day
        if a.athlete_id not in latest or d > latest[a.athlete_id]:
            latest[a.athlete_id] = d
    return latest


def main() -> int:
    ap = argparse.ArgumentParser(description="ThreeTri nightly pipeline")
    ap.add_argument("--full", action="store_true", help="re-fetch the whole season, ignoring last sync")
    ap.add_argument("--no-garmin", action="store_true", help="skip Garmin wellness")
    ap.add_argument("--garmin-days", type=int, default=14, help="how many days of wellness to fetch")
    args = ap.parse_args()

    season_start = strava.season_start_date()
    conn = store.connect()
    existing = store.load_activities(conn)
    latest = _latest_day_by_athlete(existing)
    print(f"Store: {len(existing)} activities on disk")

    new_activities = []
    new_wellness = []
    rotated_tokens: dict[str, str] = {}

    for ath in ATHLETES:
        if args.full or ath["id"] not in latest:
            after = season_start
        else:
            after = max(season_start, latest[ath["id"]] - timedelta(days=2))  # 2-day overlap

        acts, rotated = strava.fetch_athlete(ath, after)
        new_activities.extend(acts)
        if rotated:
            rotated_tokens[ath["strava_secret"]] = rotated

        if not args.no_garmin:
            new_wellness.extend(garmin.fetch_athlete(ath, days=args.garmin_days))

    if new_activities:
        store.save_activities(conn, new_activities)
    if new_wellness:
        store.save_wellness(conn, new_wellness)

    activities = store.load_activities(conn)
    wellness = store.load_wellness(conn)
    conn.close()

    # Surface rotated Strava refresh tokens loudly (GitHub Actions annotation).
    for secret_name, _val in rotated_tokens.items():
        print(f"::warning::Strava refresh token rotated — update GitHub Secret '{secret_name}' "
              f"(re-run scripts/mint_strava_token.py if logins start failing).")

    if not activities:
        print("No activities in store and none fetched — keeping existing dashboard.json "
              "(is this a misconfigured run? check the STRAVA_* secrets).")
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    dashboard = assemble_dashboard(activities, wellness, now)

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
