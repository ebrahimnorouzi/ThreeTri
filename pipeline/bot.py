"""Interactive @ThreeTriBot — replies to Telegram commands with on-demand stats
and AI analysis. No server needed: a GitHub Action polls every ~5 min
(.github/workflows/bot.yml), so replies arrive within a few minutes.

Commands:
  /help                what I can do (and registers the / menu)
  /standings           points leaderboard
  /today               who trained today
  /week                this week's totals per athlete
  /coach [name]        the AI weekly read (all, or one athlete)
  /readiness           recovery (HRV / sleep / body battery)
  /countdown /challenge /streak /quote /tip [sport] /song /video
  /ask <question>      free-form question answered by the AI coach over our data

Stateless: each run fetches pending updates, replies, then confirms them (so the
next run won't reprocess). Needs TELEGRAM_BOT_TOKEN. /ask and /coach AI need
ANTHROPIC_API_KEY or HF_TOKEN (same backend as the pipeline coach).

  python pipeline/bot.py            # poll & reply (what the Action runs)
  python pipeline/bot.py --setup    # register the / command menu (run once)
  python pipeline/bot.py --dry "/standings"   # print a reply locally, no Telegram
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

import posts
import coach

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SITE_DATA = Path(__file__).resolve().parent.parent / "site" / "data"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"

COMMANDS = [
    ("help", "What I can do"),
    ("standings", "Points leaderboard"),
    ("today", "Who trained today"),
    ("week", "This week's totals"),
    ("coach", "AI weekly read (/coach ebi)"),
    ("readiness", "Recovery: HRV / sleep"),
    ("countdown", "Days to race day"),
    ("challenge", "Team goal progress"),
    ("streak", "Current streaks"),
    ("quote", "A shot of motivation"),
    ("tip", "Training tip (/tip swim)"),
    ("song", "Today's playlist"),
    ("video", "Today's video"),
    ("ask", "Ask the AI coach (/ask ...)"),
]


def _load(name):
    p = SITE_DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _athlete(d, key):
    key = key.lower()
    for a in d["athletes"]:
        if a["id"] == key or a["name"].lower() == key:
            return a
    return None


def _idx():
    n = datetime.now(timezone.utc)
    return n.date().toordinal() * 24 + n.hour


# --------------------------------------------------------------------------- #
# Reply builders (Telegram allows up to 4096 chars, so fuller than the posts)
# --------------------------------------------------------------------------- #
def _r_help(d, content, arg):
    lines = "\n".join(f"/{c} — {desc}" for c, desc in COMMANDS)
    return f"🔺 ThreeTri bot — ask me anything:\n\n{lines}"


def _r_standings(d, content, arg):
    out = ["🏆 Standings (ThreeTri points)"]
    for i, b in enumerate(d["leaderboards"]["points"]):
        a = _athlete(d, b["athlete_id"])
        out.append(f"{i+1}. {a['emoji']} {a['name']} — {int(b['value'])} pts · LV{a['level']} · 🔥{a['streak']['current_days']}d")
    return "\n".join(out)


def _r_today(d, content, arg):
    digest = d.get("team", {}).get("digest", [])
    entry = next((x for x in digest if x["label"] == "Today"), None) or (digest[0] if digest else None)
    if not entry or not entry["activities"]:
        return "Nothing logged yet today. Be the first. 🏊🚴🏃"
    per = {}
    for act in entry["activities"]:
        per.setdefault(act["athlete_id"], []).append(act)
    out = [f"📅 {entry['label']}"]
    for aid, acts in per.items():
        a = _athlete(d, aid)
        bits = ", ".join(f"{x['sport']} {x['distance_km']}km" for x in acts)
        out.append(f"{a['emoji']} {a['name']}: {bits}")
    return "\n".join(out)


def _r_week(d, content, arg):
    out = ["📈 This week"]
    for a in d["athletes"]:
        w = a["this_week"]
        out.append(f"{a['emoji']} {a['name']}: {w['all']['distance_km']:g} km · {w['all']['moving_h']:g} h "
                   f"(🏊{w['swim']['distance_km']:g} 🚴{w['bike']['distance_km']:g} 🏃{w['run']['distance_km']:g})")
    return "\n".join(out)


def _r_coach(d, content, arg):
    athletes = [_athlete(d, arg)] if arg else d["athletes"]
    athletes = [a for a in athletes if a]
    if not athletes:
        return "Unknown athlete. Try /coach ebi, /coach sia or /coach alborz."
    out = []
    for a in athletes:
        s = a.get("weekly_summary") or "No weekly read yet."
        out.append(f"🧠 {a['name']} — {a.get('race', {}).get('label', '')}\n{s}")
    return "\n\n".join(out)


def _r_readiness(d, content, arg):
    out = ["🫀 Readiness (latest Garmin)"]
    any_data = False
    for a in d["athletes"]:
        rd = a.get("readiness")
        if not rd:
            out.append(f"{a['emoji']} {a['name']}: —")
            continue
        any_data = True
        bits = []
        if rd.get("hrv"): bits.append(f"HRV {rd['hrv']:g}")
        if rd.get("rhr"): bits.append(f"RHR {rd['rhr']:g}")
        if rd.get("sleep_hours"): bits.append(f"sleep {rd['sleep_hours']:g}h")
        if rd.get("body_battery"): bits.append(f"BB {rd['body_battery']:g}")
        out.append(f"{a['emoji']} {a['name']}: {rd['status'].upper()} ({', '.join(bits)})")
    if not any_data:
        return "No Garmin recovery data yet (needs the GARMIN_TOKEN secrets)."
    return "\n".join(out)


def _r_ask(d, content, arg):
    if not arg:
        return "Ask me something, e.g. /ask who has the best run consistency this month?"
    if not coach.available():
        return "AI coach isn't configured yet (add ANTHROPIC_API_KEY or HF_TOKEN as a repo secret)."
    ctx = [f"Race: {d['race']['short_name']} in {d['race']['days_to_go']} days ({d['race']['phase']} phase)."]
    for a in d["athletes"]:
        t, w = a["totals"], a["this_week"]
        rd = a.get("readiness")
        ctx.append(
            f"{a['name']} ({a.get('race',{}).get('label','')}): season {t['all']['distance_km']:g}km "
            f"(sw{t['swim']['distance_km']:g}/bk{t['bike']['distance_km']:g}/rn{t['run']['distance_km']:g}), "
            f"this week {w['all']['distance_km']:g}km, streak {a['streak']['current_days']}d, "
            f"consistency {a.get('consistency_pct','?')}%" + (f", readiness {rd['status']}" if rd else ""))
    system = ("You are a sharp, supportive triathlon coach with access to this team's training data below. "
              "Answer the user's question concisely (under 120 words) using the numbers. If the data can't "
              "answer it, say so briefly. No markdown.")
    user = "TEAM DATA:\n" + "\n".join(ctx) + f"\n\nQUESTION: {arg[:300]}"
    try:
        ans = coach.chat(system, user, max_tokens=300)
        return f"🧠 {ans}" if ans else "Couldn't generate an answer right now."
    except Exception as exc:
        return f"AI error ({type(exc).__name__}). Try again later."


# kinds that reuse the social post builders (concise is fine)
def _r_post(kind):
    def fn(d, content, arg):
        p = posts.build_all(d, content, _idx())
        if kind == "tip" and arg:
            tips = (content or {}).get("tips", {}).get(arg.lower())
            if tips:
                icon = {"swim": "🏊", "bike": "🚴", "run": "🏃"}.get(arg.lower(), "")
                return f"{icon} {arg.title()} tip: {tips[_idx() % len(tips)]}"
        return p.get(kind) or "Not available right now."
    return fn


HANDLERS = {
    "help": _r_help, "start": _r_help,
    "standings": _r_standings, "leaderboard": _r_standings,
    "today": _r_today, "week": _r_week,
    "coach": _r_coach, "readiness": _r_readiness, "ask": _r_ask,
    "countdown": _r_post("countdown"), "challenge": _r_post("challenge"),
    "streak": _r_post("streak"), "quote": _r_post("quote"),
    "tip": _r_post("tip"), "song": _r_post("song"), "video": _r_post("video"),
}


def reply_for(text, d, content):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lstrip("/").split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    fn = HANDLERS.get(cmd)
    if not fn:
        return None  # ignore non-commands / unknown
    return fn(d, content, arg)


# --------------------------------------------------------------------------- #
# Telegram I/O
# --------------------------------------------------------------------------- #
def _send(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage",
                      json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": False}, timeout=30)
    except Exception as exc:
        print(f"  send failed: {type(exc).__name__}")


def setup_menu():
    if not TOKEN:
        print("No TELEGRAM_BOT_TOKEN."); return
    r = requests.post(f"{API}/setMyCommands",
                      json={"commands": [{"command": c, "description": desc} for c, desc in COMMANDS]}, timeout=30)
    print("setMyCommands:", r.json().get("ok"))


def poll(d, content):
    if not TOKEN:
        print("No TELEGRAM_BOT_TOKEN — skipping bot poll.")
        return
    try:
        r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=30).json()
    except Exception as exc:
        print(f"getUpdates failed: {type(exc).__name__}"); return
    if not r.get("ok"):
        print("getUpdates not ok:", r.get("description"))  # e.g. 409 if a webhook is set
        return
    updates = r.get("result", [])
    last = None
    handled = 0
    for u in updates:
        last = u["update_id"]
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            continue
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            continue
        reply = reply_for(text, d, content)
        if reply:
            _send(msg["chat"]["id"], reply)
            handled += 1
    if last is not None:  # confirm/clear so we don't reprocess next run
        try:
            requests.get(f"{API}/getUpdates", params={"offset": last + 1, "timeout": 0}, timeout=30)
        except Exception:
            pass
    print(f"bot: {len(updates)} updates, {handled} commands handled")


def main():
    ap = argparse.ArgumentParser(description="ThreeTri interactive Telegram bot")
    ap.add_argument("--setup", action="store_true", help="register the / command menu (run once)")
    ap.add_argument("--dry", metavar="CMD", help="print the reply for a command locally (no Telegram)")
    args = ap.parse_args()

    d = _load("dashboard.json")
    content = _load("content.json")
    if not d:
        print("No dashboard.json."); return 0

    if args.setup:
        setup_menu()
    elif args.dry:
        print(reply_for(args.dry, d, content) or "(no reply / unknown command)")
    else:
        poll(d, content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
