"""AI coaching — per-activity "session reads" and weekly summaries.

Pluggable backend (pick with the COACH_BACKEND env var, or auto-detect):
  * "anthropic" — Claude (default model: the cheapest, Haiku 4.5). Needs
    ANTHROPIC_API_KEY. ~$0.002/activity, best quality.
  * "hf"        — Hugging Face Inference Providers (OpenAI-compatible router).
    Needs HF_TOKEN (fine-grained, "Make calls to Inference Providers" scope).
    Cheap open models (default Qwen2.5-7B). NOTE: HF's free tier is only ~$0.10/
    month of credit — fine for light daily use, not unlimited.
  * "off"       — no AI (default when neither key is set). Dashboard works fine.

Auto-detect order: ANTHROPIC_API_KEY → "anthropic"; else HF_TOKEN → "hf"; else off.

Everything here is NON-FATAL: any failure logs and returns empty, never crashing
the pipeline. Notes/summaries are cached in the DB so each is generated once.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from config import RACE, SPORTS
from models import Activity

MODEL_ANTHROPIC = os.environ.get("COACH_MODEL", "claude-haiku-4-5")
MODEL_HF = os.environ.get("COACH_MODEL_HF", "Qwen/Qwen2.5-7B-Instruct:cheapest")
MAX_PER_RUN = int(os.environ.get("COACH_MAX_PER_RUN", "40"))
HF_ROUTER = "https://router.huggingface.co/v1/chat/completions"

NOTE_SYSTEM = (
    "You are an elite endurance triathlon coach giving a quick, sharp read on a single "
    "training session. Use the actual numbers. Output 2 short sentences, under 45 words "
    "total: first an intensity/execution read, then one concrete takeaway. "
    "No preamble, no markdown, no bullet points, no greeting."
)
SUMMARY_SYSTEM = (
    "You are a supportive but honest triathlon coach. Given an athlete's week of training, "
    "write 3 short sentences: (1) what stood out this week, (2) one thing to watch or improve, "
    "(3) one specific focus for next week tied to their goal race. Use their numbers. "
    "No markdown, no lists, no preamble."
)


def backend() -> str:
    b = os.environ.get("COACH_BACKEND", "auto").lower()
    if b in ("anthropic", "hf", "off"):
        return b
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("HF_TOKEN"):
        return "hf"
    return "off"


def model_label() -> str:
    return {"anthropic": MODEL_ANTHROPIC, "hf": MODEL_HF}.get(backend(), "none")


def available() -> bool:
    return backend() != "off"


def chat(system: str, user: str, max_tokens: int = 400) -> str:
    """Public one-shot completion (used by the interactive bot's /ask)."""
    return _complete(system, user, max_tokens)


def _complete(system: str, user: str, max_tokens: int = 200) -> str:
    b = backend()
    if b == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        r = client.messages.create(model=MODEL_ANTHROPIC, max_tokens=max_tokens, system=system,
                                   messages=[{"role": "user", "content": user}])
        return "".join(x.text for x in r.content if x.type == "text").strip()
    if b == "hf":
        import requests
        r = requests.post(
            HF_ROUTER,
            headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}", "Content-Type": "application/json"},
            json={"model": MODEL_HF, "max_tokens": max_tokens, "temperature": 0.4,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    return ""


def _activity_line(a: Activity) -> str:
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
    return f"{sport} \"{a.name}\" {a.distance_km:.1f} km / {a.moving_min:.0f} min{pace}; {hr}; {round(a.elevation_m)} m climb"


# --------------------------------------------------------------------------- #
# Per-activity notes
# --------------------------------------------------------------------------- #
def analyze(activities: list[Activity], existing: dict[tuple[str, str], str]) -> tuple[dict[tuple[str, str], str], str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    b = backend()
    if b == "off":
        print("  [coach] no backend (set ANTHROPIC_API_KEY or HF_TOKEN to enable AI notes)")
        return {}, "none", now

    todo = [a for a in activities if (a.source, a.activity_id) not in existing and a.distance_km > 0]
    todo.sort(key=lambda a: a.start_local, reverse=True)
    todo = todo[:MAX_PER_RUN]
    if not todo:
        print("  [coach] all activities already analysed")
        return {}, model_label(), now

    out: dict[tuple[str, str], str] = {}
    for a in todo:
        user = (f"Session: {_activity_line(a)} on {a.day.isoformat()}. "
                f"Training for {RACE['short_name']} ({RACE['name']}) on {RACE['date']}. Give your read.")
        try:
            text = _complete(NOTE_SYSTEM, user, max_tokens=200)
            if text:
                out[(a.source, a.activity_id)] = text
        except Exception as exc:
            print(f"  [coach] notes stopped after {len(out)} ({type(exc).__name__}: {exc})")
            return out, model_label(), now
    print(f"  [coach] generated {len(out)} notes via {b} ({model_label()})")
    return out, model_label(), now


# --------------------------------------------------------------------------- #
# Weekly per-athlete summary + suggestion
# --------------------------------------------------------------------------- #
def summarize_week(athlete_name: str, race_label: str, week_acts: list[Activity]) -> str:
    if backend() == "off" or not week_acts:
        return ""
    lines = "\n".join(f"- {_activity_line(a)}" for a in sorted(week_acts, key=lambda a: a.start_local))
    user = (f"Athlete: {athlete_name}, targeting the {race_label} distance at {RACE['short_name']} "
            f"({RACE['date']}). This week's sessions:\n{lines}\n\nWrite the weekly read.")
    try:
        return _complete(SUMMARY_SYSTEM, user, max_tokens=220)
    except Exception as exc:
        print(f"  [coach] weekly summary for {athlete_name} failed ({type(exc).__name__})")
        return ""
