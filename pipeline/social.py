"""Broadcast ThreeTri updates to Bluesky / Discord / Telegram, and send a daily
coach-digest email. Run by .github/workflows/social.yml on a schedule.

Every channel is NON-FATAL and OPT-IN — it only fires if its secrets are set, so
you can enable just the ones you want. Nothing here can break the data pipeline.

Usage:
  python pipeline/social.py --kind auto     # pick a post type by the current UTC hour
  python pipeline/social.py --kind quote    # post a specific type (quote/recap/tip/…)
  python pipeline/social.py --email         # send the daily coach-digest email

Secrets (all optional):
  Bluesky : BLUESKY_HANDLE, BLUESKY_APP_PASSWORD      (App Password, not main pw)
  Discord : DISCORD_WEBHOOK_URL
  Telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  Email   : EMAIL_USER, EMAIL_PASSWORD (app pw), EMAIL_TO (comma-sep), [EMAIL_HOST, EMAIL_PORT, EMAIL_FROM]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

import posts

try:  # avoid cp1252 console crashes on emoji (Windows local runs); CI is already UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SITE_DATA = Path(__file__).resolve().parent.parent / "site" / "data"
PDS = "https://bsky.social"
_URL_RE = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"


def _load(name: str):
    p = SITE_DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _day_index() -> int:
    return datetime.now(timezone.utc).date().toordinal()


# --------------------------------------------------------------------------- #
# Bluesky (raw AT Protocol — clickable link facets, no SDK dependency)
# --------------------------------------------------------------------------- #
def _bsky_facets(text: str) -> list[dict]:
    out = []
    for m in re.finditer(_URL_RE, text.encode("utf-8")):
        out.append({"index": {"byteStart": m.start(1), "byteEnd": m.end(1)},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(1).decode("utf-8")}]})
    return out


def post_bluesky(text: str) -> bool:
    handle, pw = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not pw:
        return False
    try:
        s = requests.post(f"{PDS}/xrpc/com.atproto.server.createSession",
                          json={"identifier": handle, "password": pw}, timeout=30)
        s.raise_for_status()
        sess = s.json()
        record = {"$type": "app.bsky.feed.post", "text": text,
                  "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "langs": ["en"]}
        facets = _bsky_facets(text)
        if facets:
            record["facets"] = facets
        r = requests.post(f"{PDS}/xrpc/com.atproto.repo.createRecord",
                          headers={"Authorization": "Bearer " + sess["accessJwt"]},
                          json={"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record}, timeout=30)
        r.raise_for_status()
        print("  [bluesky] posted")
        return True
    except Exception as exc:
        print(f"  [bluesky] failed: {type(exc).__name__}: {exc}")
        return False


def post_discord(text: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    try:
        r = requests.post(url, json={"content": text[:1990]}, timeout=30)
        r.raise_for_status()
        print("  [discord] posted")
        return True
    except Exception as exc:
        print(f"  [discord] failed: {type(exc).__name__}")
        return False


def post_telegram(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "disable_web_page_preview": False}, timeout=30)
        r.raise_for_status()
        print("  [telegram] posted")
        return True
    except Exception as exc:
        print(f"  [telegram] failed: {type(exc).__name__}")
        return False


def send_email(subject: str, html: str) -> bool:
    user, pw = os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_PASSWORD")
    to = [x.strip() for x in (os.environ.get("EMAIL_TO", "") or "").split(",") if x.strip()]
    if not user or not pw or not to:
        return False
    host = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.environ.get("EMAIL_PORT", "465"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_FROM", user)
    msg["To"] = ", ".join(to)
    msg.set_content("Your client doesn't support HTML. Open the ThreeTri site for the full digest.")
    msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP_SSL(host, port) as smtp:
            smtp.login(user, pw)
            smtp.send_message(msg)
        print(f"  [email] sent to {len(to)} recipient(s)")
        return True
    except Exception as exc:
        print(f"  [email] failed: {type(exc).__name__}: {exc}")
        return False


# --------------------------------------------------------------------------- #
# Daily coach-digest email
# --------------------------------------------------------------------------- #
def _digest_html(d) -> str:
    site = (d.get("meta", {}).get("site_url") or "").rstrip("/")
    race = d["race"]
    rows = []
    for a in d["athletes"]:
        rd = a.get("readiness")
        ready = f" · readiness <b>{rd['status'].upper()}</b>" if rd else ""
        summary = a.get("weekly_summary") or "—"
        recent = a.get("recent_activities", [])[:3]
        recent_html = "".join(
            f"<li>{r['date']} · {r['sport']} {r['distance_km']} km{' · 🧠 ' + r['coach_note'] if r.get('coach_note') else ''}</li>"
            for r in recent)
        rows.append(
            f"<div style='margin:0 0 18px'><h3 style='margin:0;color:{a['color']}'>{a['name']} "
            f"<span style='font-weight:400;color:#888'>· {a.get('race',{}).get('label','')}{ready}</span></h3>"
            f"<p style='margin:6px 0'><b>Coach:</b> {summary}</p>"
            f"<ul style='margin:6px 0;padding-left:18px;color:#444'>{recent_html}</ul></div>")
    return (
        f"<div style='font-family:sans-serif;max-width:620px;margin:auto;color:#222'>"
        f"<h2>🔺 ThreeTri — daily digest</h2>"
        f"<p style='color:#666'>{race['days_to_go']} days to {race['short_name']} ({race['phase']} phase).</p>"
        + "".join(rows) +
        f"<p><a href='{site}'>Open the live dashboard →</a></p></div>")


def main() -> int:
    ap = argparse.ArgumentParser(description="ThreeTri social / notifications")
    ap.add_argument("--kind", default="auto", help="post kind, or 'auto' to pick by UTC hour")
    ap.add_argument("--email", action="store_true", help="send the daily coach-digest email instead of a post")
    args = ap.parse_args()

    dashboard = _load("dashboard.json")
    content = _load("content.json")
    if not dashboard:
        print("No dashboard.json — nothing to post.")
        return 0

    if args.email:
        sent = send_email(f"ThreeTri · {dashboard['race']['days_to_go']} days to {dashboard['race']['short_name']}",
                          _digest_html(dashboard))
        if not sent:
            print("  [email] skipped (set EMAIL_USER / EMAIL_PASSWORD / EMAIL_TO to enable)")
        return 0

    all_posts = posts.build_all(dashboard, content, _day_index())
    kind = args.kind
    if kind == "auto":
        kind = posts.HOUR_ROTATION.get(datetime.now(timezone.utc).hour, "quote")
    text = all_posts.get(kind) or all_posts.get("recap") or all_posts.get("countdown")
    if not text:
        print("No post text available.")
        return 0

    print(f"Posting kind='{kind}': {text[:80]}…")
    sent = any([post_bluesky(text), post_discord(text), post_telegram(text)])
    if not sent:
        print("  No channel configured — set Bluesky/Discord/Telegram secrets to enable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
