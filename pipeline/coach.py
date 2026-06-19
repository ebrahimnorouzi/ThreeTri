"""Optional per-activity AI coaching — the guide's Level 1 "session read",
automated.

If ANTHROPIC_API_KEY is set, generate a short coach's note for each NEW activity
with Claude (default: the cheapest model, Haiku 4.5). Notes are cached in the DB
so each activity is analysed exactly once — a whole season costs ~$1–2.

Entirely optional and non-fatal:
  * No API key            → no notes, dashboard unchanged.
  * anthropic not installed → skipped.
  * A call fails           → stop early, keep what we have, never crash the run.

Config via env:
  ANTHROPIC_API_KEY   the key (a GitHub Secret)
  COACH_MODEL         override the model (default claude-haiku-4-5; set to
                      claude-opus-4-8 or claude-sonnet-4-6 for deeper analysis)
  COACH_MAX_PER_RUN   cap notes generated per run (default 40) to bound cost
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from config import RACE, SPORTS
from models import Activity

MODEL = os.environ.get("COACH_MODEL", "claude-haiku-4-5")
MAX_PER_RUN = int(os.environ.get("COACH_MAX_PER_RUN", "40"))

SYSTEM = (
    "You are an elite endurance triathlon coach giving a quick, sharp read on a single "
    "training session. Use the actual numbers. Output 2 short sentences, under 45 words "
    "total: first an intensity/execution read, then one concrete takeaway. "
    "No preamble, no markdown, no bullet points, no greeting."
)

try:
    import anthropic
    _HAVE = True
except Exception:
    _HAVE = False


def _prompt(a: Activity) -> str:
    sport = SPORTS.get(a.sport, {}).get("label", a.sport)
    hr = f"{round(a.avg_hr)} bpm avg" if a.avg_hr else "no HR"
    pace = ""
    if a.distance_km > 0 and a.moving_s > 0:
        if a.sport == "run":
            spk = a.moving_s / a.distance_km
            pace = f", pace {int(spk // 60)}:{int(spk % 60):02d}/km"
        elif a.sport == "bike":
            pace = f", {a.distance_km / a.moving_h:.1f} km/h"
        elif a.sport == "swim":
            s100 = a.moving_s / (a.distance_km * 10)
            pace = f", {int(s100 // 60)}:{int(s100 % 60):02d}/100m"
    return (
        f"Session: {sport} — \"{a.name}\". {a.distance_km:.1f} km in {a.moving_min:.0f} min{pace}; "
        f"{hr}; {round(a.elevation_m)} m climb; {a.day.isoformat()}. "
        f"Athlete is training for {RACE['short_name']} ({RACE['name']}) on {RACE['date']}. "
        f"Give your read."
    )


def analyze(activities: list[Activity], existing: dict[tuple[str, str], str]) -> tuple[dict[tuple[str, str], str], str, str]:
    """Generate notes for activities that don't already have one.
    Returns (new_notes, model, iso_now). new_notes is empty if disabled/failed."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not _HAVE:
        print("  [coach] anthropic not installed — skipping (set up ANTHROPIC_API_KEY to enable)")
        return {}, MODEL, now
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  [coach] no ANTHROPIC_API_KEY — skipping AI notes")
        return {}, MODEL, now

    todo = [a for a in activities if (a.source, a.activity_id) not in existing and a.distance_km > 0]
    # newest first so the freshest sessions get notes if we hit the per-run cap
    todo.sort(key=lambda a: a.start_local, reverse=True)
    todo = todo[:MAX_PER_RUN]
    if not todo:
        print("  [coach] all activities already analysed")
        return {}, MODEL, now

    client = anthropic.Anthropic()
    out: dict[tuple[str, str], str] = {}
    for a in todo:
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=200,
                system=SYSTEM,
                messages=[{"role": "user", "content": _prompt(a)}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                out[(a.source, a.activity_id)] = text
        except Exception as exc:  # auth / rate / network — stop to avoid burning calls
            print(f"  [coach] stopped after {len(out)} notes ({type(exc).__name__}: {exc})")
            return out, MODEL, now
    print(f"  [coach] generated {len(out)} notes with {MODEL}")
    return out, MODEL, now
