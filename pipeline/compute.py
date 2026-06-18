"""The stats engine — the single source of truth for the dashboard data contract.

`assemble_dashboard(activities, wellness, now)` turns the normalised activity /
wellness rows into the exact JSON the frontend renders. Because BOTH the real
pipeline (run.py) and the sample-data generator (sample_data.py) call this same
function, the sample site and the live site can never drift apart in shape.

The output is competition-first (leaderboards, head-to-head, streaks, points,
badges, highlights) with training depth underneath (weekly trends, readiness,
team totals, a virtual team challenge, and a contribution-style calendar).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, date, timedelta

from config import (
    RACE,
    SEASON_START,
    SITE_URL,
    TEAM_GOAL_KM,
    TEAM_GOAL_LABEL,
    ATHLETES,
    SPORTS,
    SPORT_ORDER,
    POINTS,
    BADGES,
)
from models import Activity, DailyWellness

# How many days of the calendar heatmap to expose (multiple of 7 keeps the grid tidy).
CALENDAR_DAYS = 182  # ~26 weeks
RECENT_LIMIT = 8


# --------------------------------------------------------------------------- #
# Small date / number helpers
# --------------------------------------------------------------------------- #
def _iso_week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _week_start(d: date) -> date:
    """Monday of the week containing d."""
    return d - timedelta(days=d.isoweekday() - 1)


def _empty_totals() -> dict:
    return {"distance_km": 0.0, "moving_h": 0.0, "activities": 0, "elevation_m": 0.0}


def _round_totals(t: dict) -> dict:
    return {
        "distance_km": round(t["distance_km"], 1),
        "moving_h": round(t["moving_h"], 1),
        "activities": int(t["activities"]),
        "elevation_m": round(t["elevation_m"]),
    }


def _totals(acts: list[Activity]) -> dict:
    """Totals grouped as {all, swim, bike, run}."""
    allt = _empty_totals()
    by_sport = {s: _empty_totals() for s in SPORTS}
    for a in acts:
        for bucket in (allt, by_sport[a.sport]):
            bucket["distance_km"] += a.distance_km
            bucket["moving_h"] += a.moving_h
            bucket["activities"] += 1
            bucket["elevation_m"] += a.elevation_m
    out = {"all": _round_totals(allt)}
    for s in SPORT_ORDER:
        out[s] = _round_totals(by_sport[s])
    return out


# --------------------------------------------------------------------------- #
# Streaks
# --------------------------------------------------------------------------- #
def _streak(acts: list[Activity], today: date) -> dict:
    days = sorted({a.day for a in acts})
    if not days:
        return {"current_days": 0, "longest_days": 0, "last_active": None, "active_days_this_week": 0}

    dayset = set(days)

    # Longest run of consecutive days anywhere in the season.
    longest = current_run = 1
    for i in range(1, len(days)):
        if (days[i] - days[i - 1]).days == 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 1

    # Current streak: count back from today; if nothing today yet, allow yesterday
    # so a streak isn't "broken" until a full day is actually missed.
    anchor = today if today in dayset else today - timedelta(days=1)
    current = 0
    d = anchor
    while d in dayset:
        current += 1
        d -= timedelta(days=1)

    week_start = _week_start(today)
    active_week = len({dd for dd in dayset if week_start <= dd <= today})

    return {
        "current_days": current,
        "longest_days": longest,
        "last_active": days[-1].isoformat(),
        "active_days_this_week": active_week,
    }


# --------------------------------------------------------------------------- #
# Points / level (gamification)
# --------------------------------------------------------------------------- #
def _points(acts: list[Activity], current_streak: int) -> int:
    pts = 0.0
    for a in acts:
        pts += a.distance_km * SPORTS[a.sport]["points_per_km"]
        pts += a.elevation_m * POINTS["elevation_per_m"]
        pts += POINTS["per_activity"]
    pts += current_streak * POINTS["streak_day"]
    return round(pts)


def _level_info(points: int) -> dict:
    size = POINTS["level_size"]
    level = int(points // size) + 1
    base = (level - 1) * size
    return {
        "level": level,
        "xp_into": round(points - base),
        "xp_per_level": int(size),
        "xp_pct": round((points - base) / size * 100, 1),
    }


# --------------------------------------------------------------------------- #
# Pace / activity views
# --------------------------------------------------------------------------- #
def _pace_str(a: Activity) -> str | None:
    """Human pace string appropriate to the sport."""
    if a.distance_km <= 0 or a.moving_s <= 0:
        return None
    if a.sport == "bike":
        kmh = a.distance_km / a.moving_h if a.moving_h else 0
        return f"{kmh:.1f} km/h"
    if a.sport == "swim":
        sec_per_100 = a.moving_s / (a.distance_m / 100.0)
        return f"{int(sec_per_100 // 60)}:{int(sec_per_100 % 60):02d} /100m"
    # run
    sec_per_km = a.moving_s / a.distance_km
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d} /km"


def _activity_view(a: Activity) -> dict:
    return {
        "date": a.day.isoformat(),
        "datetime": a.start_local,
        "sport": a.sport,
        "name": a.name,
        "distance_km": round(a.distance_km, 2),
        "moving_min": round(a.moving_min),
        "elevation_m": round(a.elevation_m),
        "avg_hr": round(a.avg_hr) if a.avg_hr else None,
        "pace": _pace_str(a),
        "kudos": a.kudos,
        "source": a.source,
    }


def _recent(acts: list[Activity], limit: int = RECENT_LIMIT) -> list[dict]:
    ordered = sorted(acts, key=lambda a: a.start_local, reverse=True)
    return [_activity_view(a) for a in ordered[:limit]]


# --------------------------------------------------------------------------- #
# Readiness (from Garmin wellness)
# --------------------------------------------------------------------------- #
def _readiness(rows: list[DailyWellness], today: date) -> dict | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda w: w.date)
    latest = rows[-1]
    recent = [w for w in rows if (today - date.fromisoformat(w.date)).days <= 7]
    hrvs = [w.hrv for w in recent if w.hrv is not None]
    hrv_7d = round(sum(hrvs) / len(hrvs), 1) if hrvs else None

    flags = 0
    if latest.sleep_hours is not None and latest.sleep_hours < 6.5:
        flags += 1
    if latest.body_battery is not None and latest.body_battery < 40:
        flags += 1
    if latest.hrv is not None and hrv_7d and latest.hrv < 0.92 * hrv_7d:
        flags += 1
    status = "green" if flags == 0 else "amber" if flags == 1 else "red"

    return {
        "status": status,
        "date": latest.date,
        "hrv": latest.hrv,
        "hrv_7d": hrv_7d,
        "rhr": latest.rhr,
        "sleep_hours": latest.sleep_hours,
        "sleep_score": latest.sleep_score,
        "body_battery": latest.body_battery,
        "garmin_readiness": latest.readiness,
    }


# --------------------------------------------------------------------------- #
# Badges
# --------------------------------------------------------------------------- #
def _evaluate_badges(acts: list[Activity], totals: dict, streak: dict) -> list[dict]:
    longest_streak = max(streak["current_days"], streak["longest_days"])
    max_bike = max((a.distance_km for a in acts if a.sport == "bike"), default=0)
    max_run = max((a.distance_km for a in acts if a.sport == "run"), default=0)
    max_swim = max((a.distance_km for a in acts if a.sport == "swim"), default=0)
    early = any(a.hour < 6 for a in acts)

    # days with all three sports
    sports_by_day: dict[date, set[str]] = defaultdict(set)
    hours_by_week: dict[date, float] = defaultdict(float)
    for a in acts:
        sports_by_day[a.day].add(a.sport)
        hours_by_week[_week_start(a.day)] += a.moving_h
    triple = any(len(s) == 3 for s in sports_by_day.values())
    big_week = max(hours_by_week.values(), default=0) >= 12

    earned = {
        "streak-7": longest_streak >= 7,
        "streak-14": longest_streak >= 14,
        "streak-30": longest_streak >= 30,
        "century-ride": max_bike >= 100,
        "half-run": max_run >= 21.0,
        "marathon-run": max_run >= 42.0,
        "swim-3k": max_swim >= 3.0,
        "triple-day": triple,
        "everester": totals["all"]["elevation_m"] >= 5000,
        "early-bird": early,
        "big-week": big_week,
        "iron-volume": totals["all"]["distance_km"] >= 1000,
    }
    return [{**b, "earned": bool(earned.get(b["id"], False))} for b in BADGES]


# --------------------------------------------------------------------------- #
# Leaderboards / head-to-head
# --------------------------------------------------------------------------- #
def _rank(values: dict[str, float], unit: str) -> list[dict]:
    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"athlete_id": aid, "value": round(v, 1), "unit": unit, "rank": i + 1}
        for i, (aid, v) in enumerate(ranked)
    ]


def _leaderboards(totals_by_ath: dict[str, dict]) -> dict:
    out = {}
    out["all"] = _rank({aid: t["all"]["distance_km"] for aid, t in totals_by_ath.items()}, "km")
    for s in SPORT_ORDER:
        out[s] = _rank({aid: t[s]["distance_km"] for aid, t in totals_by_ath.items()}, "km")
    out["hours"] = _rank({aid: t["all"]["moving_h"] for aid, t in totals_by_ath.items()}, "h")
    out["elevation"] = _rank({aid: t["all"]["elevation_m"] for aid, t in totals_by_ath.items()}, "m")
    return out


def _head_to_head(week_totals_by_ath: dict[str, dict]) -> dict:
    h2h = {}
    for key in ["all"] + SPORT_ORDER:
        values = {aid: t[key]["distance_km"] for aid, t in week_totals_by_ath.items()}
        leader = max(values, key=values.get) if values and max(values.values()) > 0 else None
        h2h[key] = {"leader": leader, "values": {k: round(v, 1) for k, v in values.items()}, "unit": "km"}
    return h2h


# --------------------------------------------------------------------------- #
# Weekly trends
# --------------------------------------------------------------------------- #
def _weekly_trends(acts_by_ath: dict[str, list[Activity]], season_start: date, today: date) -> dict:
    weeks: list[date] = []
    cur = _week_start(season_start)
    end = _week_start(today)
    while cur <= end:
        weeks.append(cur)
        cur += timedelta(days=7)
    idx = {w: i for i, w in enumerate(weeks)}

    out = {
        "labels": [_iso_week_key(w) for w in weeks],
        "week_starts": [w.isoformat() for w in weeks],
        "short": [f"{w.day:02d}/{w.month:02d}" for w in weeks],
        "athletes": {},
    }
    for aid, acts in acts_by_ath.items():
        series = {k: [0.0] * len(weeks) for k in ("all_km", "swim_km", "bike_km", "run_km", "hours")}
        for a in acts:
            w = _week_start(a.day)
            if w in idx:
                i = idx[w]
                series["all_km"][i] += a.distance_km
                series[f"{a.sport}_km"][i] += a.distance_km
                series["hours"][i] += a.moving_h
        out["athletes"][aid] = {k: [round(v, 1) for v in vals] for k, vals in series.items()}
    return out


# --------------------------------------------------------------------------- #
# Calendar heatmap
# --------------------------------------------------------------------------- #
def _calendar(season_acts: list[Activity], today: date) -> list[dict]:
    start = today - timedelta(days=CALENDAR_DAYS - 1)
    by_day: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for a in season_acts:
        if a.day >= start:
            by_day[a.day][a.athlete_id] += 1
    out = []
    for n in range(CALENDAR_DAYS):
        d = start + timedelta(days=n)
        counts = by_day.get(d, {})
        out.append(
            {
                "date": d.isoformat(),
                "total": int(sum(counts.values())),
                **{a["id"]: int(counts.get(a["id"], 0)) for a in ATHLETES},
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Highlights — auto-written "interesting stats" cards
# --------------------------------------------------------------------------- #
def _name(aid: str) -> str:
    for a in ATHLETES:
        if a["id"] == aid:
            return a["name"]
    return aid


def _highlights(athletes_out: list[dict], h2h: dict, team: dict, season_acts: list[Activity], today: date) -> list[dict]:
    cards: list[dict] = []

    # 1) Hottest current streak
    streaks = [(a["id"], a["streak"]["current_days"]) for a in athletes_out]
    aid, days = max(streaks, key=lambda kv: kv[1], default=(None, 0))
    if days >= 3:
        cards.append({"icon": "🔥", "title": "Hottest streak", "athlete_id": aid,
                      "text": f"{_name(aid)} is on a {days}-day streak — keep it alive."})

    # 2) Who leads the team this week (total km)
    leader = h2h["all"]["leader"]
    if leader:
        val = h2h["all"]["values"][leader]
        cards.append({"icon": "👑", "title": "This week's leader", "athlete_id": leader,
                      "text": f"{_name(leader)} tops the team with {val:g} km across all sports this week."})

    # 3) Biggest single session this week
    week_start = _week_start(today)
    this_week = [a for a in season_acts if a.day >= week_start]
    if this_week:
        big = max(this_week, key=lambda a: a.distance_km)
        if big.distance_km > 0:
            icon = SPORTS[big.sport]["icon"]
            cards.append({"icon": icon, "title": "Biggest session", "athlete_id": big.athlete_id,
                          "text": f"{_name(big.athlete_id)} logged a {big.distance_km:.1f} km {SPORTS[big.sport]['label'].lower()} — the week's longest."})

    # 4) Most improved week-on-week (all km)
    deltas = [(a["id"], a["this_week"]["all"]["distance_km"] - a["last_week"]["all"]["distance_km"]) for a in athletes_out]
    aid, delta = max(deltas, key=lambda kv: kv[1], default=(None, 0))
    if delta and delta > 1:
        cards.append({"icon": "📈", "title": "On the up", "athlete_id": aid,
                      "text": f"{_name(aid)} is up {delta:.0f} km on last week — momentum building."})

    # 5) Team challenge progress
    tc = team["challenge"]
    cards.append({"icon": "🏝️", "title": "Road to Mallorca", "athlete_id": None,
                  "text": f"Together you've covered {tc['done_km']:g} of {tc['target_km']:g} km ({tc['pct']:g}%) toward the team goal."})

    # 6) Climbing leader this week
    climb = {a["id"]: a["this_week"]["all"]["elevation_m"] for a in athletes_out}
    aid = max(climb, key=climb.get) if climb else None
    if aid and climb[aid] >= 200:
        cards.append({"icon": "⛰️", "title": "King of the mountains", "athlete_id": aid,
                      "text": f"{_name(aid)} climbed {climb[aid]:.0f} m this week — the most of anyone."})

    return cards[:6]


# --------------------------------------------------------------------------- #
# Race phase
# --------------------------------------------------------------------------- #
def _race_phase(days_to_go: int) -> str:
    if days_to_go < 0:
        return "Race done"
    if days_to_go <= 7:
        return "Race week"
    if days_to_go <= 21:
        return "Taper"
    if days_to_go <= 56:
        return "Peak"
    if days_to_go <= 112:
        return "Build"
    return "Base"


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def assemble_dashboard(activities: list[Activity], wellness: list[DailyWellness], now: datetime) -> dict:
    today = now.date()
    season_start = date.fromisoformat(SEASON_START)
    race_date = date.fromisoformat(RACE["date"])
    days_to_go = (race_date - today).days

    this_ws = _week_start(today)
    last_ws = this_ws - timedelta(days=7)

    def in_week(a: Activity, ws: date) -> bool:
        return ws <= a.day <= ws + timedelta(days=6)

    season_acts = [a for a in activities if a.day >= season_start]

    acts_by_ath: dict[str, list[Activity]] = {a["id"]: [] for a in ATHLETES}
    for a in season_acts:
        if a.athlete_id in acts_by_ath:
            acts_by_ath[a.athlete_id].append(a)

    wellness_by_ath: dict[str, list[DailyWellness]] = defaultdict(list)
    for w in wellness:
        wellness_by_ath[w.athlete_id].append(w)

    athletes_out: list[dict] = []
    season_totals_by_ath: dict[str, dict] = {}
    week_totals_by_ath: dict[str, dict] = {}
    points_board: dict[str, int] = {}
    streak_board: dict[str, int] = {}

    for meta in ATHLETES:
        aid = meta["id"]
        acts = acts_by_ath.get(aid, [])
        tw = [a for a in acts if in_week(a, this_ws)]
        lw = [a for a in acts if in_week(a, last_ws)]

        season_t = _totals(acts)
        week_t = _totals(tw)
        last_t = _totals(lw)
        streak = _streak(acts, today)
        points = _points(acts, streak["current_days"])
        level = _level_info(points)
        badges = _evaluate_badges(acts, season_t, streak)
        readiness = _readiness(wellness_by_ath.get(aid, []), today)

        season_totals_by_ath[aid] = season_t
        week_totals_by_ath[aid] = week_t
        points_board[aid] = points
        streak_board[aid] = streak["current_days"]

        athletes_out.append(
            {
                "id": aid,
                "name": meta["name"],
                "initials": meta["initials"],
                "emoji": meta["emoji"],
                "color": meta["color"],
                "tagline": meta["tagline"],
                "totals": season_t,
                "this_week": week_t,
                "last_week": last_t,
                "streak": streak,
                "points": points,
                "level": level["level"],
                "xp": level,
                "badges": badges,
                "badge_count": sum(1 for b in badges if b["earned"]),
                "readiness": readiness,
                "recent_activities": _recent(acts),
            }
        )

    # Team aggregates
    team_all = _empty_totals()
    team_week = _empty_totals()
    team_by_sport = {s: 0.0 for s in SPORTS}
    for aid, t in season_totals_by_ath.items():
        team_all["distance_km"] += t["all"]["distance_km"]
        team_all["moving_h"] += t["all"]["moving_h"]
        team_all["activities"] += t["all"]["activities"]
        team_all["elevation_m"] += t["all"]["elevation_m"]
        for s in SPORTS:
            team_by_sport[s] += t[s]["distance_km"]
    for aid, t in week_totals_by_ath.items():
        team_week["distance_km"] += t["all"]["distance_km"]
        team_week["moving_h"] += t["all"]["moving_h"]
        team_week["activities"] += t["all"]["activities"]
        team_week["elevation_m"] += t["all"]["elevation_m"]

    done_km = round(team_all["distance_km"], 1)
    team = {
        "totals": _round_totals(team_all),
        "this_week": _round_totals(team_week),
        "by_sport": {s: round(team_by_sport[s], 1) for s in SPORT_ORDER},
        "challenge": {
            "label": TEAM_GOAL_LABEL,
            "target_km": TEAM_GOAL_KM,
            "done_km": done_km,
            "pct": round(min(100.0, done_km / TEAM_GOAL_KM * 100), 1),
            "remaining_km": round(max(0.0, TEAM_GOAL_KM - done_km), 1),
        },
        "calendar": _calendar(season_acts, today),
    }

    leaderboards = {
        "season": _leaderboards(season_totals_by_ath),
        "this_week": _leaderboards(week_totals_by_ath),
        "points": _rank({k: float(v) for k, v in points_board.items()}, "pts"),
        "streak": _rank({k: float(v) for k, v in streak_board.items()}, "days"),
    }
    h2h = {"this_week": _head_to_head(week_totals_by_ath)}
    trends = _weekly_trends(acts_by_ath, season_start, today)
    highlights = _highlights(athletes_out, h2h["this_week"], team, season_acts, today)

    sources = sorted({a.source for a in season_acts}) or ["garmin"]
    if any(a["readiness"] for a in athletes_out) and "garmin" not in sources:
        sources.append("garmin")

    return {
        "meta": {
            "generated_at": now.replace(microsecond=0).isoformat() + "Z",
            "generated_at_human": now.strftime("%d %b %Y, %H:%M UTC"),
            "season_start": SEASON_START,
            "site_url": SITE_URL,
            "data_sources": sources,
            "schema_version": 1,
        },
        "race": {
            "name": RACE["name"],
            "short_name": RACE["short_name"],
            "date": RACE["date"],
            "start_iso": RACE.get("start", RACE["date"] + "T08:00:00+02:00"),
            "date_human": race_date.strftime("%d %b %Y"),
            "location": RACE["location"],
            "url": RACE["url"],
            "days_to_go": days_to_go,
            "weeks_to_go": round(days_to_go / 7, 1),
            "phase": _race_phase(days_to_go),
        },
        "sports": {s: {"label": SPORTS[s]["label"], "icon": SPORTS[s]["icon"], "color": SPORTS[s]["color"]} for s in SPORT_ORDER},
        "athletes": athletes_out,
        "leaderboards": leaderboards,
        "head_to_head": h2h,
        "trends": trends,
        "team": team,
        "highlights": highlights,
    }
