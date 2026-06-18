"""Generate realistic SAMPLE data so the site looks alive before any Strava /
Garmin setup is done.

It synthesises a season of activities + wellness for the three athletes, seeds
the SQLite store, and writes site/data/dashboard.json via the SAME compute path
the real pipeline uses. Run it any time to refresh the demo:

    python pipeline/sample_data.py

The nightly job overwrites this with real data once secrets are configured.
Deterministic (fixed seed) so the committed sample never churns.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, date, timedelta
from pathlib import Path

from config import ATHLETES, SEASON_START
from models import Activity, DailyWellness
from compute import assemble_dashboard
import store

SEED = 2026
# "Today" for the sample. Matches the project's current date so the countdown
# and "this week" look right in the committed demo.
SAMPLE_TODAY = date(2026, 6, 18)

SITE_DATA = Path(__file__).resolve().parent.parent / "site" / "data"
# Sample seeds a SEPARATE, gitignored DB so it never pollutes the real history
# store (data/threetri.db) that the live pipeline builds and commits.
SAMPLE_DB = Path(__file__).resolve().parent.parent / "data" / "sample.db"

# Per-athlete training personalities → different leaderboards make it a contest.
PROFILES = {
    "ebi": {   # the engine: big bike volume, strong all-rounder
        "weekly_sessions": (5, 7),
        "sport_weights": {"swim": 2, "bike": 4, "run": 3},
        "bike_km": (32, 72), "run_km": (7, 15), "swim_km": (1.8, 3.6),
        "run_pace": (290, 320), "hilliness": 1.1, "hrv": 70, "rhr": 47,
        "streak_bias": 0.86,
    },
    "sia": {   # the metronome: super consistent, run-leaning
        "weekly_sessions": (6, 7),
        "sport_weights": {"swim": 3, "bike": 3, "run": 4},
        "bike_km": (24, 52), "run_km": (8, 16), "swim_km": (2.0, 3.8),
        "run_pace": (270, 300), "hilliness": 0.8, "hrv": 64, "rhr": 50,
        "streak_bias": 0.93,
    },
    "alborz": {  # the climber: fewer but bigger sessions, lots of elevation
        "weekly_sessions": (4, 6),
        "sport_weights": {"swim": 2, "bike": 5, "run": 3},
        "bike_km": (40, 84), "run_km": (6, 13), "swim_km": (1.5, 3.0),
        "run_pace": (300, 340), "hilliness": 1.8, "hrv": 58, "rhr": 53,
        "streak_bias": 0.78,
    },
}

START_HOURS = [6, 7, 7, 8, 12, 17, 18, 19]  # bias toward mornings/evenings


def _mk_activity(rng: random.Random, aid: str, d: date, sport: str, idx: int, ramp: float) -> Activity:
    p = PROFILES[aid]
    hour = rng.choice(START_HOURS)
    if rng.random() < 0.12:  # the odd dawn session → Early Bird badge
        hour = 5
    start = datetime(d.year, d.month, d.day, hour, rng.randint(0, 59))

    if sport == "bike":
        km = rng.uniform(*p["bike_km"]) * ramp
        speed = rng.uniform(24, 33)  # km/h
        moving_s = int(km / speed * 3600)
        elev = km * rng.uniform(6, 14) * p["hilliness"]
        hr = rng.uniform(125, 158)
        names = ["Endurance ride", "Hill repeats", "Café spin", "Threshold bike", "Long ride", "Brick bike"]
    elif sport == "run":
        km = rng.uniform(*p["run_km"]) * ramp
        pace = rng.uniform(*p["run_pace"])  # s/km
        moving_s = int(km * pace)
        elev = km * rng.uniform(4, 11) * p["hilliness"]
        hr = rng.uniform(140, 168)
        speed = km / (moving_s / 3600)
        names = ["Easy run", "Tempo run", "Long run", "Intervals", "Recovery jog", "Brick run"]
    else:  # swim
        km = rng.uniform(*p["swim_km"]) * (0.85 + 0.15 * ramp)
        sec_per_100 = rng.uniform(95, 125)
        moving_s = int(km * 10 * sec_per_100)
        elev = 0.0
        hr = rng.uniform(120, 150)
        speed = km / (moving_s / 3600)
        names = ["Pool session", "Threshold swim", "Technique swim", "Open water", "Endurance swim"]

    # occasional hero sessions to light up the badges
    if sport == "bike" and rng.random() < 0.05:
        km = max(km, rng.uniform(101, 140))
        moving_s = int(km / rng.uniform(26, 30) * 3600)
    if sport == "run" and rng.random() < 0.04:
        km = max(km, rng.uniform(21.5, 32))
        moving_s = int(km * rng.uniform(300, 330))

    return Activity(
        athlete_id=aid,
        source="garmin",
        activity_id=f"sample-{aid}-{d.isoformat()}-{idx}",
        sport=sport,
        name=rng.choice(names),
        start_local=start.isoformat(),
        distance_m=round(km * 1000, 1),
        moving_s=moving_s,
        elapsed_s=int(moving_s * rng.uniform(1.02, 1.12)),
        elevation_m=round(elev, 1),
        avg_hr=round(hr, 1),
        max_hr=round(hr + rng.uniform(8, 22), 1),
        avg_speed=round(speed * 1000 / 3600, 3),
        suffer_score=round(hr - 100 + km, 0),
        kudos=rng.randint(0, 32),
    )


def _weighted_sport(rng: random.Random, weights: dict) -> str:
    pool = []
    for sport, w in weights.items():
        pool += [sport] * w
    return rng.choice(pool)


def generate() -> tuple[list[Activity], list[DailyWellness]]:
    rng = random.Random(SEED)
    season_start = date.fromisoformat(SEASON_START)
    activities: list[Activity] = []
    wellness: list[DailyWellness] = []

    total_weeks = ((SAMPLE_TODAY - season_start).days // 7) + 1

    for meta in ATHLETES:
        aid = meta["id"]
        p = PROFILES[aid]
        week_start = season_start - timedelta(days=season_start.isoweekday() - 1)
        wk = 0
        while week_start <= SAMPLE_TODAY:
            # Training ramps over the season (base → build) with a little noise.
            ramp = 0.7 + 0.5 * (wk / max(1, total_weeks)) + rng.uniform(-0.06, 0.06)
            sessions = rng.randint(*p["weekly_sessions"])
            # choose distinct-ish days of the week
            day_offsets = rng.sample(range(7), k=min(7, sessions))
            for idx, off in enumerate(sorted(day_offsets)):
                d = week_start + timedelta(days=off)
                if d < season_start or d > SAMPLE_TODAY:
                    continue
                sport = _weighted_sport(rng, p["sport_weights"])
                activities.append(_mk_activity(rng, aid, d, sport, idx, ramp))
                # sometimes a second session same day (brick) → Triple Threat chance
                if rng.random() < 0.1:
                    sport2 = _weighted_sport(rng, p["sport_weights"])
                    activities.append(_mk_activity(rng, aid, d, sport2, idx + 50, ramp))
            week_start += timedelta(days=7)
            wk += 1

        # Wellness for the last ~35 days (Garmin coverage)
        for n in range(35):
            d = SAMPLE_TODAY - timedelta(days=n)
            if d < season_start:
                break
            if rng.random() < 0.1:  # didn't wear the watch
                continue
            wellness.append(
                DailyWellness(
                    athlete_id=aid,
                    date=d.isoformat(),
                    hrv=round(p["hrv"] + rng.uniform(-9, 9), 1),
                    rhr=round(p["rhr"] + rng.uniform(-4, 5), 1),
                    sleep_hours=round(rng.uniform(5.8, 8.6), 1),
                    sleep_score=round(rng.uniform(55, 92)),
                    body_battery=round(rng.uniform(38, 95)),
                    stress_avg=round(rng.uniform(22, 48)),
                    readiness=round(rng.uniform(45, 92)),
                )
            )

    return activities, wellness


def main() -> None:
    activities, wellness = generate()

    # Seed a SAMPLE SQLite DB so you can try the MCP server before real data
    # exists. Point the MCP server's TRAINING_DB at data/sample.db for the demo.
    conn = store.connect(SAMPLE_DB)
    store.save_activities(conn, activities)
    store.save_wellness(conn, wellness)
    conn.close()

    now = datetime(SAMPLE_TODAY.year, SAMPLE_TODAY.month, SAMPLE_TODAY.day, 3, 14)
    dashboard = assemble_dashboard(activities, wellness, now)

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    out = SITE_DATA / "dashboard.json"
    out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Sample data: {len(activities)} activities, {len(wellness)} wellness rows")
    print(f"Wrote {out}")
    print(f"Seeded {SAMPLE_DB} (sample MCP DB; gitignored)")


if __name__ == "__main__":
    main()
