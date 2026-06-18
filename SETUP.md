# ThreeTri — Setup Guide  (Garmin-only)

Take this from "sample data" to a **live, nightly-updating dashboard** at
`https://ebrahimnorouzi.github.io/ThreeTri/`.

The site already works right now with realistic **sample data** so you can see
the design. Real data switches on once the GitHub Secrets below are in place.

> **Why Garmin-only:** all three of you record on Garmin, and Garmin Connect is
> **free** for your own data (activities + sleep/HRV/recovery). No Strava
> subscription, no API fees. The trade-off is reliability — see [§7](#7-reliability--the-honest-caveat).

---

## 0. How it fits together

```
        ┌────────── GitHub Actions (nightly cron, 05:17 UTC) ──────────┐
 Garmin │  run.py:  fetch activities + wellness ─► SQLite store         │
 Connect│           compute.py ─► site/data/dashboard.json             │
 (free) └──────────────────────────────────────────────┬──────────────┘
                                                         │ commit + deploy
                                                         ▼
                                     GitHub Pages ─► the Race HUD site
                                                         ▲
                                            race-day QR code points here
```

One login per athlete pulls **both** their training activities (swim/bike/run)
**and** their recovery metrics. Secrets stay private; only the computed stats
become public on the site.

---

## 1. 🔑 The Secrets checklist — *what to collect from each of you*

Add these in **GitHub → repo Settings → Secrets and variables → Actions → New repository secret**.
Names must match **exactly** (referenced in [.github/workflows/update.yml](.github/workflows/update.yml)).

| Secret name | Who provides it | How |
|---|---|---|
| `GARMIN_TOKEN_EBI` | **Ebi** | run [mint_garmin_token.py](scripts/mint_garmin_token.py) — step 2 |
| `GARMIN_TOKEN_SIA` | **Sia** | run [mint_garmin_token.py](scripts/mint_garmin_token.py) — step 2 |
| `GARMIN_TOKEN_ALBORZ` | **Alborz** | run [mint_garmin_token.py](scripts/mint_garmin_token.py) — step 2 |

That's it — **three secrets**. Each is a base64 "token blob" that lets the
nightly job read that athlete's Garmin data with no password and no MFA.

> 🔒 The blob grants access to your Garmin account — treat it like a password.
> It lives only in GitHub Secrets, never in the code or on the site. Send it to
> the repo admin (Ebi) **privately**. Never share your actual Garmin password.

---

## 2. Mint each athlete's Garmin token  *(all three, once)*

Garmin needs your password + MFA, so each person does this **on their own
machine** (your password never leaves it — only the resulting token is shared):

```bash
# Python 3.12+ required (curl_cffi)
pip install garminconnect curl_cffi
python scripts/mint_garmin_token.py
```

Enter your Garmin email, password, and MFA code if prompted. It prints a long
base64 **token blob** (valid ~1 year). Send it to Ebi to store as
`GARMIN_TOKEN_<NAME>`.

### 📨 Message to send Sia & Alborz

> Hey! I'm building a live site tracking the three of us training for Mallorca 🏊🚴🏃.
> To pull your Garmin stats, run this once on your computer (it needs Python 3.12+):
>
> ```
> pip install garminconnect curl_cffi
> python scripts/mint_garmin_token.py
> ```
> (Grab the repo first: `git clone https://github.com/ebrahimnorouzi/ThreeTri`.)
>
> It'll ask for your Garmin email + password (+ MFA code). Your password stays on
> your machine — it just prints a long code at the end. **Copy that whole code and
> send it to me privately.** That's all I need. 🙌

> No Python? We can do it together on a quick call (screen-share) so you type your
> own password — I just need the token it prints.

---

## 3. Make the repo public + enable Pages

GitHub Free serves Pages only from **public** repos, and the race-day QR needs a
public URL anyway.

1. **Make public:** repo **Settings → General → Danger Zone → Change repository
   visibility → Make public**. (Your committed training stats become viewable at
   the URL — that's the intent for the QR. The token *secrets* stay private.)
2. **Enable Pages:** repo **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.

---

## 4. First run

- **Actions** tab → **"Update data & deploy"** → **Run workflow**.
- It fetches everyone's Garmin data since 1 Jan 2026, builds `dashboard.json`,
  commits the history, and deploys.
- Live in ~1–2 min at **https://ebrahimnorouzi.github.io/ThreeTri/**, then
  automatically **every night at 05:17 UTC**.

---

## 5. The race-day QR code

`site/assets/img/qr.svg` already points at your site, and [qr.html](site/qr.html)
is a full-screen "scan to follow us live" card with the countdown and your names.
On race day, open **`…/ThreeTri/qr.html`** on a phone and let people scan it.

Regenerate the code if you change the site URL: `python scripts/make_qr.py`.

---

## 6. "Ask Your Own Data" — the MCP coach (optional)

Point Claude at your training history and ask real questions ("compare my run
volume to Sia's over 6 weeks"). See [mcp/threetri_mcp.py](mcp/threetri_mcp.py).

```bash
pip install -r mcp/requirements.txt
python pipeline/sample_data.py     # creates data/sample.db to try it on
```
**Claude Code:**
```bash
claude mcp add --scope user \
  --env THREETRI_DB=/ABS/PATH/ThreeTri/data/threetri.db \
  --transport stdio threetri \
  -- python /ABS/PATH/ThreeTri/mcp/threetri_mcp.py
```
(Use `data/sample.db` for the demo data; on Windows use the full path to `python.exe`.)
**Claude Desktop:** add a `threetri` entry to `claude_desktop_config.json`
(`%AppData%\Claude\…` on Windows) with `command`/`args`/`env` (`THREETRI_DB`), then restart.

---

## 7. Reliability — the honest caveat

Garmin has **no official public API**; [pipeline/garmin.py](pipeline/garmin.py)
logs in the way the phone app does (via `python-garminconnect`). It's free and it
works, but from GitHub's **datacenter IPs** Garmin occasionally rate-limits or
blocks requests. So:

- The nightly job is **non-fatal** — a blocked night just keeps the last data;
  it won't crash. It usually recovers the next night.
- If it gets blocked **often**, run the job from a **residential IP** instead:
  set up a [self-hosted GitHub Actions runner](https://docs.github.com/actions/hosting-your-own-runners)
  on an always-on home machine (or a Raspberry Pi) and change `runs-on: ubuntu-latest`
  to `runs-on: self-hosted` in the workflow. Same code, reliable Garmin access.
- Tokens last ~1 year. If a run logs `login/resume failed`, re-run
  `mint_garmin_token.py` and update that athlete's secret.

If you ever want rock-solid reliability and don't mind the cost, you can switch
to (or add) Strava — see [§9](#9-re-enabling-strava-later).

---

## 8. Customise it

Tune everything in **[pipeline/config.py](pipeline/config.py)**: athlete names /
emoji / neon colours / taglines, the race date + start time (drives the
countdown), per-sport `points_per_km`, the badge list, and `TEAM_GOAL_KM`.

Preview locally after edits:
```bash
pip install -r pipeline/requirements.txt
python pipeline/sample_data.py
python -m http.server 8000 --directory site   # http://localhost:8000
```

---

## 9. Re-enabling Strava later (optional)

The Strava code is kept but dormant ([pipeline/strava.py](pipeline/strava.py),
[scripts/mint_strava_token.py](scripts/mint_strava_token.py),
[scripts/exchange_strava_code.py](scripts/exchange_strava_code.py)). To add it:
1. The app owner needs a Strava subscription (post-June-2026 requirement) and
   should self-upgrade the app to 10 athletes (free) at strava.com/settings/api,
   with **Authorization Callback Domain = `localhost`**.
2. Mint per-athlete refresh tokens, add `STRAVA_CLIENT_ID/SECRET` +
   `STRAVA_REFRESH_TOKEN_<NAME>` secrets, and call `strava.fetch_athlete` in
   `run.py` (and re-add the `STRAVA_*` env block to the workflow).

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Action runs but site shows sample data | Check the `GARMIN_TOKEN_*` secrets exist and names match exactly. The job logs which athletes it skipped. |
| `login/resume failed` for an athlete | Token expired (~yearly) or Garmin blocked it. Re-run `mint_garmin_token.py`, update the secret. |
| Garmin blocked most nights | Move to a self-hosted runner on a home IP — see [§7](#7-reliability--the-honest-caveat). |
| Pages 404 | Settings → Pages → Source = **GitHub Actions**, and the repo must be **public**. |
| Countdown looks wrong | Set the real gun time in `RACE["start"]` in `config.py`. |

---

Built for the [Triathlon Port de Palma de Mallorca](https://worldsmarathons.com/de/marathon/triathlon-port-de-palma-de-mallorca),
20 Sep 2026 · Follow [@ebi.n.94](https://www.instagram.com/ebi.n.94/).
