# 🔺 ThreeTri

**Three athletes. Three sports. One finish line.**
A live, self-updating training HUD for **Ebi · Sia · Alborz** on the road to the
[Triathlon Port de Palma de Mallorca](https://worldsmarathons.com/de/marathon/triathlon-port-de-palma-de-mallorca)
(20 Sep 2026) — built to keep us honest, a little competitive, and moving.

👉 **Live site:** https://ebrahimnorouzi.github.io/ThreeTri/
📲 **Race-day QR card:** https://ebrahimnorouzi.github.io/ThreeTri/qr.html
📸 **Follow:** [@ebi.n.94](https://www.instagram.com/ebi.n.94/)

> Inspired by the *Running on AI* iceberg guide — this is **Level 4 "Own the
> Pipe"**, done fully free on GitHub: Secrets hold the API keys, Actions run the
> nightly job, Pages hosts the dashboard. Plus a **Level 3 MCP server** so you
> can ask Claude questions about your own data.

## What it does

- **Live countdown** to race day (days · hrs · min · sec), ticking on the homepage.
- **Competition-first Race HUD** — points-based standings, levels & XP, streak
  flames, badges, and this-week head-to-head bars for swim / bike / run.
- **Season leaderboards**, weekly volume trends, a consistency heatmap, and
  auto-written "highlights" that surface the story in the numbers.
- **Per-athlete pages** with Garmin readiness (HRV, sleep, resting HR, Body Battery).
- A **team challenge** bar — combined distance toward a shared goal.
- Updates **automatically every night** via Strava (+ optional Garmin).

## How it's built

| Layer | Tech |
|---|---|
| Data pipeline | Python — Strava REST API + `python-garminconnect` ([pipeline/](pipeline/)) |
| History store | SQLite, committed for full-season history |
| Stats engine | [pipeline/compute.py](pipeline/compute.py) — the single source of truth for `dashboard.json` |
| Frontend | Vanilla HTML/CSS/JS, hand-rolled SVG charts, **zero runtime dependencies** ([site/](site/)) |
| Automation | One GitHub Actions workflow: fetch → commit → deploy ([.github/workflows/update.yml](.github/workflows/update.yml)) |
| Hosting | GitHub Pages (free) |
| Secrets | GitHub Secrets (Strava + Garmin credentials) |
| AI coach | MCP server over your own data ([mcp/threetri_mcp.py](mcp/threetri_mcp.py)) |

The site ships with **realistic sample data** so it looks alive before any setup.

## Get started

➡️ **[SETUP.md](SETUP.md)** — the secrets checklist, Strava/Garmin token minting,
making the repo public, enabling Pages, and the MCP coach.

Quick local preview:
```bash
pip install -r pipeline/requirements.txt
python pipeline/sample_data.py
python -m http.server 8000 --directory site   # → http://localhost:8000
```

## Repo layout

```
pipeline/   config + stats engine + Strava/Garmin fetchers + run.py
site/       the static dashboard (index, athlete, qr) + data/dashboard.json
scripts/    one-time token minters + QR generator
mcp/        "Ask Your Own Data" MCP server
.github/    the nightly workflow
SETUP.md    full setup guide
```
