"""Build short, varied social posts from the dashboard + content library.

Pure text — no network, no secrets. social.py turns these into Bluesky posts /
Discord messages / emails. Each post is kept well under Bluesky's 300-grapheme
limit. A rotation maps an hour-of-day to a post kind so a workflow scheduled at
several times posts a different thing each time (a reason to keep checking).
"""

from __future__ import annotations

HASHTAGS = "#triathlon #swimbikerun"

# Which kind to post at each scheduled hour (UTC). Add/remove hours here (and in
# .github/workflows/social.yml's cron) to change how many posts/day. The daily
# content kinds (quote/tip/legend/song/video) are indexed by hour too, so even a
# repeated kind shows different content each slot. ~13 posts/day below.
HOUR_ROTATION = {
    4: "countdown",
    6: "recap",
    7: "quote",
    8: "tip",
    10: "leaderboard",
    11: "legend",
    12: "song",
    14: "quote",
    15: "challenge",
    16: "video",
    18: "tip",
    19: "streak",
    21: "legend",
}


def _name(d, aid):
    for a in d["athletes"]:
        if a["id"] == aid:
            return a["name"]
    return aid


def _trunc(s: str, n: int = 295) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _site(d) -> str:
    return (d.get("meta", {}).get("site_url") or "").rstrip("/")


def _day_recap(d) -> str:
    """Yesterday's 'who did what' (falls back to the most recent active day)."""
    digest = d.get("team", {}).get("digest", [])
    entry = next((x for x in digest if x["label"] == "Yesterday"), None) or (digest[0] if digest else None)
    if not entry or not entry["activities"]:
        return ""
    per = {}
    for act in entry["activities"]:
        per.setdefault(act["athlete_id"], []).append(act)
    bits = []
    for aid, acts in per.items():
        km = sum(a["distance_km"] for a in acts)
        bits.append(f"{_name(d, aid)} {len(acts)}× ({km:.0f} km)")
    return f"📊 {entry['label']} on ThreeTri: " + " · ".join(bits) + f". {_site(d)}"


def build_all(d, content, day_index: int = 0) -> dict[str, str]:
    """Return {kind: text}. Skips kinds with no data. `day_index` rotates the
    daily content (quote/tip/legend/song/video) so each day differs."""
    race = d["race"]
    posts: dict[str, str] = {}
    site = _site(d)

    # recap of who did what
    recap = _day_recap(d)
    if recap:
        posts["recap"] = _trunc(recap)

    # countdown
    posts["countdown"] = _trunc(
        f"⏱️ {race['days_to_go']} days to {race['short_name']} ({race['phase']} phase). "
        f"Three of us. Three sports. One finish line. {site} {HASHTAGS}")

    # leaderboard (points)
    board = d.get("leaderboards", {}).get("points", [])
    if board:
        rows = " · ".join(f"{i+1}. {_name(d, b['athlete_id'])} {int(b['value'])}pts" for i, b in enumerate(board))
        posts["leaderboard"] = _trunc(f"🏆 ThreeTri standings — {rows}. {site}")

    # team challenge
    ch = d.get("team", {}).get("challenge")
    if ch:
        posts["challenge"] = _trunc(
            f"🏝️ Road to Mallorca: {ch['done_km']:,.0f} / {ch['target_km']:,} km together "
            f"({ch['pct']:g}%). {ch['remaining_km']:,.0f} km to go. {site}")

    # streak
    streaks = sorted(d["athletes"], key=lambda a: a["streak"]["current_days"], reverse=True)
    if streaks and streaks[0]["streak"]["current_days"] >= 3:
        s = streaks[0]
        posts["streak"] = _trunc(f"🔥 {s['name']} is on a {s['streak']['current_days']}-day streak. Don't break the chain. {site}")

    # content-library kinds (rotate by day)
    if content:
        quotes = content.get("quotes") or []
        if quotes:
            q = quotes[day_index % len(quotes)]
            posts["quote"] = _trunc(f"💬 “{q['text']}” — {q['author']} {site}")
        tips = content.get("tips") or {}
        sport = ["swim", "bike", "run"][day_index % 3]
        tlist = tips.get(sport) or []
        if tlist:
            icon = {"swim": "🏊", "bike": "🚴", "run": "🏃"}[sport]
            posts["tip"] = _trunc(f"{icon} {sport.title()} tip: {tlist[(day_index // 3) % len(tlist)]} {site}")
        legends = content.get("legends") or []
        if legends:
            lg = legends[day_index % len(legends)]
            posts["legend"] = _trunc(f"🏅 Legend of the day — {lg['name']} ({lg['sport']}): {lg['blurb']} {lg['wikipedia_url']}")
        media = content.get("media") or {}
        vids = media.get("videos") or []
        if vids:
            v = vids[day_index % len(vids)]
            posts["video"] = _trunc(f"▶ Watch today: {v['title']} — {v['channel']} {v['url']} {HASHTAGS}")
        lists = media.get("playlists") or []
        if lists:
            p = lists[(day_index + 1) % len(lists)]
            posts["song"] = _trunc(f"🎧 Today's training playlist: {p['title']} — {p['url']} {HASHTAGS}")
    return posts
