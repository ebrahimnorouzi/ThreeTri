"""Garmin Connect wellness fetcher — sleep, HRV, resting HR, Body Battery.

VERIFIED 2026 approach (python-garminconnect >= 0.3.x, garth removed):
  * Tokens are minted ONCE locally (scripts/mint_garmin_token.py) and stored as a
    base64 blob in a per-athlete GitHub Secret.
  * Here in CI we ONLY resume:  Garmin().login(<base64 blob>)  — no email,
    no password, no MFA. A fresh credential login from a datacenter IP gets
    Cloudflare-blocked, so we never attempt one.

This whole module is NON-FATAL: any failure (expired token, Garmin hiccup,
Cloudflare) is caught and logged, and the pipeline carries on with Strava data
only. Garmin just enriches the dashboard with readiness; it must never break it.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from models import DailyWellness

try:
    from garminconnect import Garmin
    _HAVE_GARMIN = True
except Exception:  # library not installed (e.g. local dev without it)
    _HAVE_GARMIN = False


def _g(d, *path, default=None):
    """Safely walk nested dict/list responses: _g(obj, 'a', 0, 'b')."""
    cur = d
    for key in path:
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return default
    return cur if cur is not None else default


def _login(token_b64: str):
    g = Garmin()
    g.login(token_b64)  # >512-char string is auto-detected as a base64 token blob
    return g


def _body_battery_morning(rows) -> float | None:
    """Body Battery 'on waking' ≈ the earliest reading of the day."""
    if not rows:
        return None
    arr = _g(rows, 0, "bodyBatteryValuesArray", default=[]) or []
    levels = [pt[1] for pt in arr if isinstance(pt, list) and len(pt) >= 2 and pt[1] is not None]
    return float(levels[0]) if levels else None


def _one_day(g, aid: str, d: str) -> DailyWellness:
    w = DailyWellness(athlete_id=aid, date=d)
    try:
        sleep = g.get_sleep_data(d) or {}
        secs = _g(sleep, "dailySleepDTO", "sleepTimeSeconds")
        if secs:
            w.sleep_hours = round(secs / 3600.0, 2)
        w.sleep_score = _g(sleep, "dailySleepDTO", "sleepScores", "overall", "value")
    except Exception:
        pass
    try:
        hrv = g.get_hrv_data(d) or {}
        w.hrv = _g(hrv, "hrvSummary", "lastNightAvg")
    except Exception:
        pass
    try:
        rhr = g.get_rhr_day(d) or {}
        w.rhr = (_g(rhr, "restingHeartRate")
                 or _g(rhr, "allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"))
    except Exception:
        pass
    try:
        w.body_battery = _body_battery_morning(g.get_body_battery(d, d))
    except Exception:
        pass
    try:
        tr = g.get_training_readiness(d) or []
        w.readiness = _g(tr, 0, "score")
    except Exception:
        pass
    try:
        stats = g.get_stats(d) or {}
        w.stress_avg = _g(stats, "averageStressLevel")
    except Exception:
        pass
    return w


def fetch_athlete(athlete: dict, days: int = 14) -> list[DailyWellness]:
    """Fetch the last `days` of wellness for one athlete. Returns [] on any
    failure (non-fatal) so Strava-only runs always succeed."""
    if not _HAVE_GARMIN:
        print(f"  [garmin] {athlete['id']}: garminconnect not installed — skipping")
        return []
    token = os.environ.get(athlete["garmin_secret"], "").strip()
    if not token:
        print(f"  [garmin] {athlete['id']}: no {athlete['garmin_secret']} secret — skipping")
        return []

    try:
        g = _login(token)
    except Exception as exc:  # expired token, Cloudflare, etc.
        print(f"  [garmin] {athlete['id']}: login/resume failed ({type(exc).__name__}: {exc}); "
              f"re-mint with scripts/mint_garmin_token.py if this persists")
        return []

    out: list[DailyWellness] = []
    today = date.today()
    for n in range(days):
        d = (today - timedelta(days=n)).isoformat()
        try:
            out.append(_one_day(g, athlete["id"], d))
        except Exception as exc:
            print(f"  [garmin] {athlete['id']} {d}: {type(exc).__name__}")
    got = sum(1 for w in out if w.hrv or w.sleep_hours or w.rhr)
    print(f"  [garmin] {athlete['id']}: {got}/{len(out)} days with data")
    return out
