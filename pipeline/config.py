"""ThreeTri – central configuration.

Everything that is "about us and the race" lives here so the rest of the
pipeline stays generic. Editing this file is how you re-skin the whole project:
change the athletes, the race, the colours, or the scoring and every page and
stat updates the next time the nightly job runs.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The race we are all training for
# ---------------------------------------------------------------------------
RACE = {
    "name": "Triathlon Port de Palma de Mallorca",
    "short_name": "Mallorca '26",
    "date": "2026-09-20",  # event day (ISO, local Mallorca date)
    # Precise start used for the live homepage countdown. Mallorca is CEST
    # (UTC+2) in September; triathlons typically gun early morning. Adjust once
    # the official start time is published.
    "start": "2026-09-20T08:00:00+02:00",
    "location": "Port de Palma de Mallorca, Palma, Spain",
    "url": "https://worldsmarathons.com/de/marathon/triathlon-port-de-palma-de-mallorca",
}

# Stats are aggregated from this date forward (the "season").
SEASON_START = "2026-01-01"

# Triathlon race formats each athlete is targeting (leg distances in km).
RACE_DISTANCES = {
    "sprint": {"label": "Sprint", "swim": 0.75, "bike": 20.0, "run": 5.0},
    "olympic": {"label": "Olympic", "swim": 1.5, "bike": 40.0, "run": 10.0},
    "70.3": {"label": "Half (70.3)", "swim": 1.9, "bike": 90.0, "run": 21.1},
    "ironman": {"label": "Ironman", "swim": 3.8, "bike": 180.0, "run": 42.2},
}

# A shared team challenge: combined distance across all three of us, all sports,
# this season. A stretch goal for three triathletes over a year — tune it so the
# progress bar stays motivating (somewhere short of 100% until close to race day).
TEAM_GOAL_KM = 15000
TEAM_GOAL_LABEL = "Road to Mallorca — 15,000 km as a team"

# Public URL the QR code points at (GitHub Pages, project site).
SITE_URL = "https://ebrahimnorouzi.github.io/ThreeTri/"

# ---------------------------------------------------------------------------
# The three of us
# ---------------------------------------------------------------------------
# `color` is the athlete's neon accent used everywhere on the HUD.
# `strava_secret` / `garmin_secret` name the GitHub Secret holding that
# athlete's credentials (see SETUP.md). They are NOT the secrets themselves.
ATHLETES = [
    {
        "id": "ebi",
        "name": "Ebi",
        "initials": "EB",
        "emoji": "🐬",
        "color": "#22d3ee",  # electric cyan
        "tagline": "The engine",
        "race_type": "olympic",  # 1.5 km swim · 40 km bike · 10 km run
        "strava_secret": "STRAVA_REFRESH_TOKEN_EBI",
        "garmin_secret": "GARMIN_TOKEN_EBI",
    },
    {
        "id": "sia",
        "name": "Sia",
        "initials": "SI",
        "emoji": "⚡",
        "color": "#f0398b",  # hot magenta
        "tagline": "The metronome",
        "race_type": "sprint",  # 0.75 km swim · 20 km bike · 5 km run
        "strava_secret": "STRAVA_REFRESH_TOKEN_SIA",
        "garmin_secret": "GARMIN_TOKEN_SIA",
    },
    {
        "id": "alborz",
        "name": "Alborz",
        "initials": "AL",
        "emoji": "🦅",
        "color": "#a3e635",  # lime
        "tagline": "The climber",
        "race_type": "sprint",  # 0.75 km swim · 20 km bike · 5 km run
        "strava_secret": "STRAVA_REFRESH_TOKEN_ALBORZ",
        "garmin_secret": "GARMIN_TOKEN_ALBORZ",
    },
]

# ---------------------------------------------------------------------------
# Sports – the three triathlon disciplines.
# `strava_types` maps Strava's `sport_type`/`type` enum values onto our buckets.
# `points_per_km` weights each discipline in the gamified score (swimming is
# the slowest per km, so a swum km is worth the most).
# ---------------------------------------------------------------------------
# NOTE: `strava_types` use Strava's `sport_type` enum (the `type` field is
# deprecated). Verified against developers.strava.com (2026): there is no
# OpenWaterSwim / VirtualSwim / Treadmill enum — pool/open-water is not
# distinguished, and treadmill runs come through as `Run` with trainer=true.
SPORTS = {
    "swim": {
        "label": "Swim",
        "icon": "🏊",
        "color": "#38bdf8",
        "unit": "km",
        "strava_types": ["Swim"],
        "points_per_km": 6.0,
    },
    "bike": {
        "label": "Bike",
        "icon": "🚴",
        "color": "#fb923c",
        "unit": "km",
        "strava_types": [
            "Ride",
            "VirtualRide",
            "MountainBikeRide",
            "GravelRide",
            "EBikeRide",
            "EMountainBikeRide",
            "Velomobile",
            "Handcycle",
        ],
        "points_per_km": 1.0,
    },
    "run": {
        "label": "Run",
        "icon": "🏃",
        "color": "#34d399",
        "unit": "km",
        "strava_types": ["Run", "TrailRun", "VirtualRun"],
        "points_per_km": 3.0,
    },
}

# Order disciplines are shown in (swim → bike → run, like a triathlon).
SPORT_ORDER = ["swim", "bike", "run"]

# ---------------------------------------------------------------------------
# Gamified scoring – tuned so a committed season lands around level 10-15.
# ---------------------------------------------------------------------------
POINTS = {
    "elevation_per_m": 0.01,   # every metre climbed
    "per_activity": 8.0,       # just showing up
    "streak_day": 4.0,         # each day of the current streak
    "level_size": 800.0,       # points needed per level
}

# Badges are awarded by predicate in compute.py. Keep the copy punchy – this is
# what shows up on the cards and is meant to be a little bit of bragging rights.
BADGES = [
    {"id": "streak-7", "icon": "🔥", "label": "Week Warrior", "desc": "7-day activity streak"},
    {"id": "streak-14", "icon": "🔥🔥", "label": "Fortnight Beast", "desc": "14-day activity streak"},
    {"id": "streak-30", "icon": "🌋", "label": "Unbreakable", "desc": "30-day activity streak"},
    {"id": "century-ride", "icon": "💯", "label": "Centurion", "desc": "A single ride of 100 km+"},
    {"id": "half-run", "icon": "🥈", "label": "Half Hero", "desc": "A single run of 21.1 km+"},
    {"id": "marathon-run", "icon": "🏅", "label": "Marathoner", "desc": "A single run of 42.2 km+"},
    {"id": "swim-3k", "icon": "🦈", "label": "Open Water", "desc": "A single swim of 3 km+"},
    {"id": "triple-day", "icon": "🎯", "label": "Triple Threat", "desc": "Swam, biked and ran on the same day"},
    {"id": "everester", "icon": "⛰️", "label": "Sky High", "desc": "5,000 m+ climbed this season"},
    {"id": "early-bird", "icon": "🌅", "label": "Early Bird", "desc": "Started a session before 6am"},
    {"id": "big-week", "icon": "📈", "label": "Big Week", "desc": "12+ hours of training in one week"},
    {"id": "iron-volume", "icon": "🛡️", "label": "Iron Volume", "desc": "1,000 km+ across all sports this season"},
]


def athlete_by_id(athlete_id: str) -> dict:
    for a in ATHLETES:
        if a["id"] == athlete_id:
            return a
    raise KeyError(athlete_id)


def sport_for_strava(activity_type: str, sport_type: str | None = None) -> str | None:
    """Map a Strava activity onto one of our buckets, or None if it is not a
    swim/bike/run (e.g. a WeightTraining or Yoga session). Strava is dormant in
    the Garmin-only setup but kept for if you ever enable it."""
    candidate = sport_type or activity_type
    for bucket, meta in SPORTS.items():
        if candidate in meta["strava_types"] or activity_type in meta["strava_types"]:
            return bucket
    return None


def sport_for_garmin(type_key: str | None) -> str | None:
    """Map a Garmin activityType.typeKey onto a swim/bike/run bucket, or None.

    Garmin has many granular keys (running, trail_running, treadmill_running,
    road_biking, indoor_cycling, virtual_ride, lap_swimming, open_water_swimming,
    …). Substring matching covers them all and excludes walks/hikes/strength."""
    t = (type_key or "").lower()
    if "swim" in t:
        return "swim"
    if any(k in t for k in ("cycl", "bik", "ride")):
        return "bike"
    if "run" in t:
        return "run"
    return None
