# ThreeTri Telegram bot — serverless webhook (instant replies)

This replaces the ~5-min polling Action ([.github/workflows/bot.yml](../.github/workflows/bot.yml))
with a **Cloudflare Worker** that Telegram calls on every message, so replies are
**instant**. It reads the public `dashboard.json` / `content.json` from your
Pages site, so it always has the latest nightly data.

> Telegram allows **either** a webhook **or** `getUpdates` polling — not both.
> So once you set this up, **disable the polling workflow** (it's already
> de-scheduled in `bot.yml`; you can also disable it under Actions → Telegram bot → ⋯ → Disable).

## Deploy (Cloudflare Workers — free tier, ~100k requests/day)

1. Install + log in (one time):
   ```bash
   npm install -g wrangler
   wrangler login
   ```
2. Deploy the worker:
   ```bash
   cd webhook
   wrangler deploy
   ```
   Note the URL it prints, e.g. `https://threetri-bot.<your-subdomain>.workers.dev`.
3. Set secrets (you'll be prompted to paste each value):
   ```bash
   wrangler secret put BOT_TOKEN          # your Telegram bot token
   wrangler secret put WEBHOOK_SECRET     # any random string, e.g. `openssl rand -hex 16`
   wrangler secret put ANTHROPIC_API_KEY  # optional — for /ask and /coach (Claude)
   # or:  wrangler secret put HF_TOKEN     # optional — free-ish Hugging Face instead
   ```
4. **Wire it up** — visit this once in a browser (it sets the Telegram webhook to
   itself *and* registers the `/` command menu):
   ```
   https://threetri-bot.<your-subdomain>.workers.dev/setup?key=<WEBHOOK_SECRET>
   ```
   You should see a JSON response with `"setWebhook": {"ok": true}`.

That's it — type `/standings` in your ThreeTri group and the reply is instant.

### No CLI / `wrangler` won't run (e.g. old Node) — use the dashboard

`wrangler` needs Node 22+. If you don't have it, deploy from the browser instead —
no Node, no install:

1. Go to **[dash.cloudflare.com](https://dash.cloudflare.com)** → **Workers & Pages**
   → **Create** → **Workers** → **Create Worker**. Name it `threetri-bot` → **Deploy**
   (this creates a placeholder).
2. Click **Edit code**, delete the placeholder, **paste the entire contents of
   [`worker.js`](worker.js)**, then **Deploy**.
3. **Settings → Variables and Secrets**:
   - Add **Secret** `BOT_TOKEN` = your Telegram bot token
   - Add **Secret** `WEBHOOK_SECRET` = any random string
   - (optional) Add **Secret** `ANTHROPIC_API_KEY` (or `HF_TOKEN`) for `/ask` & `/coach`
   - (optional) Add **Variable** `SITE_BASE` only if your site isn't the default
     `https://ebrahimnorouzi.github.io/ThreeTri`
   - **Deploy** again so the secrets take effect.
4. Your URL is shown at the top, e.g. `https://threetri-bot.<subdomain>.workers.dev`.
   Visit **`https://threetri-bot.<subdomain>.workers.dev/setup?key=<WEBHOOK_SECRET>`**
   once → expect `"setWebhook":{"ok":true}`. Done — try `/standings` in the group.

### Or, if you want the CLI: update Node first
`wrangler` needs Node ≥ 22. In WSL:
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
exec $SHELL          # reload shell so nvm is available
nvm install 22 && nvm use 22
node -v               # should print v22.x
npm install -g wrangler && wrangler login
```
then follow the `wrangler deploy` steps above.

## Deno Deploy alternative
`worker.js` is standard `export default { fetch }`, which Deno Deploy also runs.
Create a project at [dash.deno.com](https://dash.deno.com), point it at this file
(or paste it), add the same env vars in the project settings, then visit
`https://<project>.deno.dev/setup?key=<WEBHOOK_SECRET>`.

## Switching back to polling
Delete the webhook and re-enable `bot.yml`:
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook"
```
