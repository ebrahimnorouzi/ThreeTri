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

### Prefer the dashboard (no CLI)?
Cloudflare dashboard → **Workers & Pages → Create → Worker** → paste
[`worker.js`](worker.js) → Deploy → **Settings → Variables**: add `SITE_BASE` (var)
and `BOT_TOKEN` / `WEBHOOK_SECRET` / `ANTHROPIC_API_KEY` (secrets) → then hit the
`/setup?key=…` URL.

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
