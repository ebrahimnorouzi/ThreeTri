"""Normalised data models.

The whole point of the pipeline is to turn two very different data sources
(Strava activities, Garmin daily wellness) into two flat, boring shapes that the
rest of the code can treat identically. Everything downstream (the SQLite store,
the stats engine, the sample-data generator) speaks only in `Activity` and
`DailyWellness`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, date

from config import sport_for_strava, sport_for_garmin


@dataclass
class Activity:
    athlete_id: str
    source: str               # "strava" | "manual"
    activity_id: str          # unique within source
    sport: str                # "swim" | "bike" | "run"
    name: str
    start_local: str          # ISO datetime, athlete's local tz
    distance_m: float
    moving_s: int
    elapsed_s: int
    elevation_m: float
    avg_hr: float | None
    max_hr: float | None
    avg_speed: float | None   # m/s
    suffer_score: float | None
    kudos: int
    # Start location, ROUNDED to ~1 km for privacy (the DB is committed to a
    # public repo). Enough to map "where we train", not enough to pin a home.
    start_lat: float | None = None
    start_lng: float | None = None

    @property
    def day(self) -> date:
        return datetime.fromisoformat(self.start_local).date()

    @property
    def hour(self) -> int:
        return datetime.fromisoformat(self.start_local).hour

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0

    @property
    def moving_min(self) -> float:
        return self.moving_s / 60.0

    @property
    def moving_h(self) -> float:
        return self.moving_s / 3600.0

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "Activity":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})

    @classmethod
    def from_strava(cls, athlete_id: str, a: dict) -> "Activity | None":
        """Build from a Strava SummaryActivity dict. Returns None for activity
        types we do not track (weights, yoga, ...)."""
        sport = sport_for_strava(a.get("type", ""), a.get("sport_type"))
        if sport is None:
            return None
        return cls(
            athlete_id=athlete_id,
            source="strava",
            activity_id=str(a["id"]),
            sport=sport,
            name=a.get("name", "") or sport.title(),
            start_local=a.get("start_date_local", a.get("start_date")),
            distance_m=float(a.get("distance", 0.0) or 0.0),
            moving_s=int(a.get("moving_time", 0) or 0),
            elapsed_s=int(a.get("elapsed_time", 0) or 0),
            elevation_m=float(a.get("total_elevation_gain", 0.0) or 0.0),
            avg_hr=_f(a.get("average_heartrate")),
            max_hr=_f(a.get("max_heartrate")),
            avg_speed=_f(a.get("average_speed")),
            suffer_score=_f(a.get("suffer_score")),
            kudos=int(a.get("kudos_count", 0) or 0),
            start_lat=_coord((a.get("start_latlng") or [None, None])[0]),
            start_lng=_coord((a.get("start_latlng") or [None, None])[1]),
        )

    @classmethod
    def from_garmin(cls, athlete_id: str, a: dict) -> "Activity | None":
        """Build from a Garmin Connect activity summary dict. Returns None for
        types we do not track (walks, hikes, strength, ...)."""
        type_key = (a.get("activityType") or {}).get("typeKey", "")
        sport = sport_for_garmin(type_key)
        if sport is None:
            return None
        start = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
        start = start.replace(" ", "T") if start else ""
        if not start:
            return None  # no timestamp → can't place it on a day
        moving = a.get("movingDuration") or a.get("duration") or 0
        return cls(
            athlete_id=athlete_id,
            source="garmin",
            activity_id=str(a.get("activityId")),
            sport=sport,
            name=a.get("activityName") or sport.title(),
            start_local=start,
            distance_m=float(a.get("distance") or 0.0),
            moving_s=int(moving or 0),
            elapsed_s=int(a.get("duration") or moving or 0),
            elevation_m=float(a.get("elevationGain") or 0.0),
            avg_hr=_f(a.get("averageHR")),
            max_hr=_f(a.get("maxHR")),
            avg_speed=_f(a.get("averageSpeed")),
            suffer_score=_f(a.get("activityTrainingLoad")),
            kudos=0,
            start_lat=_coord(a.get("startLatitude")),
            start_lng=_coord(a.get("startLongitude")),
        )


@dataclass
class DailyWellness:
    """One row per athlete per day, from Garmin. All fields optional because
    Garmin coverage is patchy (you might not wear the watch every night)."""

    athlete_id: str
    date: str                 # ISO date
    hrv: float | None = None          # overnight HRV (ms, rmssd)
    rhr: float | None = None          # resting heart rate (bpm)
    sleep_hours: float | None = None
    sleep_score: float | None = None
    body_battery: float | None = None  # 0-100 on waking
    stress_avg: float | None = None
    readiness: float | None = None     # Garmin training readiness 0-100

    def to_row(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "DailyWellness":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})


def _f(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _coord(v) -> float | None:
    """Round a GPS coordinate to ~1 km (2 dp). The store is committed publicly,
    so we never persist precise locations."""
    f = _f(v)
    return round(f, 2) if f is not None else None
