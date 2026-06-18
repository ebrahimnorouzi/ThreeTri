# ThreeTri — Setup Guide

Everything you need to take this from "sample data" to a **live, nightly-updating
dashboard** at `https://ebrahimnorouzi.github.io/ThreeTri/`.

The site already works right now with realistic **sample data** so you can see the
design. Real data switches on the moment the GitHub Secrets below are in place.

---

## 0. How it fits together (30-second mental model)

```
            ┌─────────── GitHub Actions (nightly cron, 05:17 UTC) ───────────┐
 Strava API │  run.py:  fetch new activities  ──►  SQLite store (history)     │
 Garmin     │           fetch wellness        ──►  compute.py ──► dashboard.json │
 (optional) └───────────────────────────────────────────────────┬────────────┘
                                                                  │ commits + deploys
                                                                  ▼
                                          GitHub Pages  ──►  the Race HUD site
                                                                  ▲
                                                       race-day QR code points here
```

- **Secrets** hold the API credentials (safe in GitHub — never exposed to the site).
- **The Action** runs the Python pipeline nightly, commits the refreshed data, and
  redeploys the static site.
- **The site** is plain HTML/CSS/JS reading `dashboard.json` — fast, and works offline once loaded.

---

## 1. 🔑 The Secrets checklist — *what to collect from each of you*

Add these in **GitHub → repo Settings → Secrets and variables → Actions → New repository secret**.
Names must match **exactly** (they're referenced in [.github/workflows/update.yml](.github/workflows/update.yml)).

| Secret name | Who provides it | Required? | How to get it |
|---|---|---|---|
| `STRAVA_CLIENT_ID` | **Ebi** (one shared app) | ✅ yes | Strava API app — step 2 |
| `STRAVA_CLIENT_SECRET` | **Ebi** (one shared app) | ✅ yes | Strava API app — step 2 |
| `STRAVA_REFRESH_TOKEN_EBI` | **Ebi** | ✅ yes | `mint_strava_token.py` — step 3 |
| `STRAVA_REFRESH_TOKEN_SIA` | **Sia** | ✅ yes | `mint_strava_token.py` — step 3 |
| `STRAVA_REFRESH_TOKEN_ALBORZ` | **Alborz** | ✅ yes | `mint_strava_token.py` — step 3 |
| `GARMIN_TOKEN_EBI` | **Ebi** | ⬜ optional | `mint_garmin_token.py` — step 4 |
| `GARMIN_TOKEN_SIA` | **Sia** | ⬜ optional | `mint_garmin_token.py` — step 4 |
| `GARMIN_TOKEN_ALBORZ` | **Alborz** | ⬜ optional | `mint_garmin_token.py` — step 4 |

### 📨 In plain words — what to ask Sia and Alborz for

> "Run one small script on your laptop while logged into **your own** Strava
> account, and send me the **refresh token** it prints. If you also want your
> sleep/HRV/recovery on the site, run a second script for **Garmin** and send me
> the token it prints. Both are secret — send them to me privately (not a public
> chat). Don't ever send me your actual password."

So from **each of the three of you** the admin (Ebi) collects:
1. **A Strava refresh token** (required).
2. **A Garmin token blob** (optional — only if you want readiness/sleep/HRV).

And **Ebi alone** additionally provides the shared `STRAVA_CLIENT_ID` + `STRAVA_CLIENT_SECRET`.

> 🔒 These tokens grant **read** access to your training data. Treat them like
> passwords. They live only in GitHub Secrets, never in the code or the site.

---

## 2. Create the Strava API app  *(Ebi, once)*

1. Go to <https://www.strava.com/settings/api> and create an application.
2. Set **Authorization Callback Domain** to exactly: `localhost`
3. Copy the **Client ID** and **Client Secret**.
4. Add them as the `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` repo secrets.
5. Share the Client ID + Secret with Sia and Alborz so they can mint their own
   tokens in step 3 (any Strava user can authorize your app — the default
   single-player app supports up to ~10 athletes, plenty for three).

---

## 3. Get each athlete's Strava refresh token

There are two ways. **Your friends do NOT need to install Python** — use Option A.

### Option A — friends just click a link *(recommended; only Ebi needs Python)*

Ebi, for each athlete:

```bash
pip install requests
export STRAVA_CLIENT_ID=12345          # Windows PowerShell: $env:STRAVA_CLIENT_ID="12345"
export STRAVA_CLIENT_SECRET=abc123...
python scripts/exchange_strava_code.py --link      # prints an authorize link
```

1. Send the printed link to the athlete.
2. They open it **logged into their own Strava**, click **Authorize**. The page
   redirects to `http://localhost/?code=…` (it won't load — that's fine); they
   copy the **address-bar URL** (or just the `code=` value) and send it back.
3. Ebi exchanges it **promptly** (the code expires in ~10 min):
   ```bash
   python scripts/exchange_strava_code.py            # paste the URL/code
   ```
   It prints the athlete's **refresh token** → store as `STRAVA_REFRESH_TOKEN_<NAME>`.

### Option B — the athlete runs it themselves

If they're comfortable with a terminal, they can do the whole thing locally:

```bash
pip install requests
export STRAVA_CLIENT_ID=12345
export STRAVA_CLIENT_SECRET=abc123...
python scripts/mint_strava_token.py    # browser opens → Authorize → prints the token
```

Either way, the result is one **refresh token per athlete** for Ebi to store as a secret.

---

## 4. (Optional) Mint each athlete's Garmin token  *(all three, only for sleep/HRV)*

```bash
pip install garminconnect curl_cffi     # needs Python 3.12+
python scripts/mint_garmin_token.py
```

Enter your Garmin email, password, and MFA code if prompted. It prints a long
base64 **token blob** (valid ~1 year). Send it to Ebi to store as
`GARMIN_TOKEN_<NAME>`. Your password never leaves your machine.

> Garmin is genuinely optional. With no Garmin secrets the site simply omits the
> readiness panel and runs on Strava data alone. The nightly job treats any
> Garmin error as non-fatal.

---

## 5. Make the repo public + enable Pages

GitHub Free serves Pages only from **public** repos, and the race-day QR needs a
public URL anyway.

1. **Make public:** repo **Settings → General → Danger Zone → Change repository
   visibility → Make public**. (Your committed training stats become viewable at
   the URL — that's the intent for the QR. The *secrets* stay private regardless.)
2. **Enable Pages:** repo **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.

That's it — no branch to pick; the workflow publishes the artifact.

---

## 6. First run

- Go to the **Actions** tab → **"Update data & deploy"** → **Run workflow**.
- It installs deps, fetches everyone's data since 1 Jan 2026, builds
  `dashboard.json`, commits the history, and deploys.
- After ~1–2 minutes your live site is at **https://ebrahimnorouzi.github.io/ThreeTri/**.
- After that it runs **automatically every night at 05:17 UTC**.

---

## 7. The race-day QR code

`site/assets/img/qr.svg` already points at your site, and [qr.html](site/qr.html)
is a full-screen "scan to follow us live" card with the countdown and your names.

On race day, open **`…/ThreeTri/qr.html`** on a phone and let people scan it. If
you ever change the site URL, regenerate the code:

```bash
pip install segno
python scripts/make_qr.py
```

---

## 8. "Ask Your Own Data" — the MCP coach (optional, the guide's Level 3/5)

Point Claude at your training history and ask real questions
("compare my run volume to Sia's over 6 weeks", "is my easy pace improving at the
same HR?"). See [mcp/threetri_mcp.py](mcp/threetri_mcp.py).

```bash
pip install -r mcp/requirements.txt
# try it on the sample data first:
python pipeline/sample_data.py     # creates data/sample.db
```

**Claude Code** (run from the project folder):
```bash
claude mcp add --scope user \
  --env THREETRI_DB=/ABS/PATH/ThreeTri/data/threetri.db \
  --transport stdio threetri \
  -- python /ABS/PATH/ThreeTri/mcp/threetri_mcp.py
```
(Use `data/sample.db` for the demo data. On Windows use the full path to your
`python.exe` and backslash paths.)

**Claude Desktop** — add to `claude_desktop_config.json`
(Windows: `%AppData%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "threetri": {
      "command": "C:\\Users\\eno\\Documents\\Git_repo\\ebrahimnorouzi_github\\ThreeTri\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\eno\\Documents\\Git_repo\\ebrahimnorouzi_github\\ThreeTri\\mcp\\threetri_mcp.py"],
      "env": { "THREETRI_DB": "C:\\Users\\eno\\Documents\\Git_repo\\ebrahimnorouzi_github\\ThreeTri\\data\\threetri.db" }
    }
  }
}
```
Restart Claude Desktop after editing.

---

## 9. Customise it

Almost everything is tuned in **[pipeline/config.py](pipeline/config.py)**:

- **Athletes** — names, emoji, neon colours, taglines, which secret holds each token.
- **Race** — name, date, start time (drives the live countdown), location, link.
- **Scoring** — `points_per_km` per sport, level size, the badge list.
- **Team goal** — `TEAM_GOAL_KM` (the "Road to Mallorca" progress bar).

After editing, refresh the local sample so you can preview:
```bash
python pipeline/sample_data.py
python -m http.server 8000 --directory site   # open http://localhost:8000
```

---

## 10. Local development

```bash
pip install -r pipeline/requirements.txt   # or just `requests segno` for a quick look
python pipeline/sample_data.py             # regenerate the sample dashboard
python -m http.server 8000 --directory site
# open http://localhost:8000  (and /athlete.html?id=sia , /qr.html)
```

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| Action runs but site shows sample data | Check the `STRAVA_*` secrets exist and names match exactly. The job logs which athletes it skipped. |
| `Strava refresh token rotated` warning in the logs | Re-run `mint_strava_token.py` for that athlete and update their secret. (Rare — Strava tokens are usually stable.) |
| Garmin step says "login/resume failed" | The blob expired (~yearly) or Garmin blocked it. Re-run `mint_garmin_token.py` and update the secret. The site keeps working without it. |
| Pages 404 | Settings → Pages → Source must be **GitHub Actions**, and the repo must be **public** (on the free plan). |
| Countdown looks wrong | Set the real gun time in `RACE["start"]` in `config.py`. |

---

Built for the [Triathlon Port de Palma de Mallorca](https://worldsmarathons.com/de/marathon/triathlon-port-de-palma-de-mallorca),
20 Sep 2026 · Follow [@ebi.n.94](https://www.instagram.com/ebi.n.94/).
