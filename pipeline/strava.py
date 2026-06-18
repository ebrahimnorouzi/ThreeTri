"""Strava REST fetcher (the unattended half of the pipeline).

Per athlete we hold a long-lived *refresh token* in a GitHub Secret. Each run we
exchange it for a 6-hour access token, then page through their activities since
the last sync. Verified against developers.strava.com (2026):

  * refresh:  POST /oauth/token grant_type=refresh_token  → access_token (+ a
              possibly-rotated refresh_token, which we surface so it can be
              re-stored if Strava ever changes it).
  * list:     GET /api/v3/athlete/activities?after=<epoch>&per_page=200  (page++)
  * classify: use `sport_type` (the `type` field is deprecated).

Rate limits: 100 reads / 15 min, 1000 / day. We only hit the list endpoint a few
times per athlete per day, so we stay far under — but we still back off on 429.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, date, timezone

import requests

from config import SEASON_START
from models import Activity

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")


class StravaError(RuntimeError):
    pass


def refresh_access_token(refresh_token: str) -> dict:
    """Return the full token payload. Caller should persist payload['refresh_token']
    if it differs from what was sent in (Strava may rotate it)."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise StravaError("STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET not set in the environment.")
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        # Never echo the /oauth/token response body into (public) CI logs.
        raise StravaError(f"token refresh failed: HTTP {resp.status_code}")
    return resp.json()


def _iter_activities(access_token: str, after_epoch: int, per_page: int = 200, max_429_retries: int = 3):
    page = 1
    attempts = 0  # consecutive 429s on the current page
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        params = {"after": after_epoch, "page": page, "per_page": per_page}
        r = requests.get(ACTIVITIES_URL, headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            # Both the 15-min and the DAILY read limit surface as 429. Retry the
            # same page a few times (waiting to the next 15-min boundary), but
            # give up rather than blocking for up to a day if the limit won't clear.
            attempts += 1
            if attempts > max_429_retries:
                raise StravaError("rate limited (HTTP 429) and not clearing — giving up for this run")
            wait = 900 - (int(time.time()) % 900) + 2
            print(f"  [strava] 429 rate-limited (attempt {attempts}/{max_429_retries}); sleeping {wait}s")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise StravaError(f"activities failed: HTTP {r.status_code}")
        attempts = 0
        batch = r.json()
        if not batch:
            break
        yield from batch
        if len(batch) < per_page:
            break
        page += 1


def fetch_athlete(athlete: dict, after: date) -> tuple[list[Activity], str | None]:
    """Fetch one athlete's swim/bike/run activities since `after`.

    Returns (activities, rotated_refresh_token_or_None). A None refresh token
    means "unchanged / nothing to update". Missing credentials → ([], None) with
    a warning, so one athlete's missing secret never breaks the whole run.
    """
    secret_name = athlete["strava_secret"]
    refresh_token = os.environ.get(secret_name, "").strip()
    if not refresh_token:
        print(f"  [strava] {athlete['id']}: no {secret_name} secret — skipping")
        return [], None

    try:
        tok = refresh_access_token(refresh_token)
    except StravaError as exc:
        print(f"  [strava] {athlete['id']}: {exc}")
        return [], None

    rotated = tok.get("refresh_token")
    rotated = rotated if rotated and rotated != refresh_token else None

    after_epoch = int(datetime(after.year, after.month, after.day, tzinfo=timezone.utc).timestamp())
    activities: list[Activity] = []
    skipped = 0
    try:
        for raw in _iter_activities(tok["access_token"], after_epoch):
            act = Activity.from_strava(athlete["id"], raw)
            if act is None:
                skipped += 1
                continue
            activities.append(act)
    except StravaError as exc:
        # Keep whatever we got; the 2-day overlap on the next run will catch up.
        print(f"  [strava] {athlete['id']}: stopped early ({exc}); keeping {len(activities)} fetched")

    print(f"  [strava] {athlete['id']}: {len(activities)} activities (+{skipped} non-tri skipped)"
          + ("  ⚠ refresh token rotated — update the secret" if rotated else ""))
    return activities, rotated


def season_start_date() -> date:
    return date.fromisoformat(SEASON_START)
