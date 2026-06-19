/**
 * ThreeTri Telegram bot — Cloudflare Worker (instant webhook replies).
 *
 * Telegram POSTs each update here; we reply immediately (no polling, no server
 * to run). Reads the public dashboard.json / content.json from GitHub Pages, so
 * it always reflects the latest nightly data. /ask and /coach use the AI coach
 * (Anthropic or Hugging Face) if a key is configured.
 *
 * Deploy: see webhook/README.md. Set secrets: BOT_TOKEN (required),
 * WEBHOOK_SECRET (recommended), ANTHROPIC_API_KEY or HF_TOKEN (for /ask).
 * Then visit  https://<your-worker-url>/setup?key=<WEBHOOK_SECRET>  once to wire
 * the webhook + register the / command menu.
 */

const COMMANDS = [
  ["help", "What I can do"],
  ["standings", "Points leaderboard"],
  ["today", "Who trained today"],
  ["week", "This week's totals"],
  ["coach", "AI weekly read (/coach ebi)"],
  ["readiness", "Recovery: HRV / sleep"],
  ["countdown", "Days to race day"],
  ["challenge", "Team goal progress"],
  ["streak", "Current streaks"],
  ["quote", "A shot of motivation"],
  ["tip", "Training tip (/tip swim)"],
  ["song", "Today's playlist"],
  ["video", "Today's video"],
  ["ask", "Ask the AI coach (/ask ...)"],
];

const SITE = (env) => (env.SITE_BASE || "https://ebrahimnorouzi.github.io/ThreeTri").replace(/\/$/, "");

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/setup") {
      if (env.WEBHOOK_SECRET && url.searchParams.get("key") !== env.WEBHOOK_SECRET)
        return new Response("forbidden", { status: 403 });
      const hook = `${url.origin}/`;
      const set = await tg(env, "setWebhook", {
        url: hook,
        secret_token: env.WEBHOOK_SECRET || undefined,
        allowed_updates: ["message", "edited_message"],
      });
      const cmds = await tg(env, "setMyCommands", {
        commands: COMMANDS.map(([command, description]) => ({ command, description })),
      });
      return Response.json({ webhook: hook, setWebhook: set, setMyCommands: cmds });
    }

    if (request.method !== "POST") {
      return new Response("ThreeTri bot webhook is alive. POST updates here; visit /setup to wire it.", {
        headers: { "content-type": "text/plain" },
      });
    }

    // Verify the request really came from Telegram.
    if (env.WEBHOOK_SECRET &&
        request.headers.get("x-telegram-bot-api-secret-token") !== env.WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }

    let update;
    try { update = await request.json(); } catch { return new Response("ok"); }
    const msg = update.message || update.edited_message;
    const text = (msg && msg.text) || "";
    if (!msg || !text.startsWith("/")) return new Response("ok");

    try {
      const [dashboard, content] = await Promise.all([
        fetchJson(`${SITE(env)}/data/dashboard.json`),
        fetchJson(`${SITE(env)}/data/content.json`),
      ]);
      const reply = await replyFor(text, dashboard, content, env);
      if (reply) await tg(env, "sendMessage", { chat_id: msg.chat.id, text: reply.slice(0, 4000), disable_web_page_preview: false });
    } catch (e) {
      await tg(env, "sendMessage", { chat_id: msg.chat.id, text: "⚠️ Hmm, I couldn't fetch the data just now. Try again in a moment." });
    }
    return new Response("ok");
  },
};

// ---------------------------------------------------------------------------
async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function fetchJson(u) {
  const r = await fetch(u, { cf: { cacheTtl: 300 } });
  if (!r.ok) throw new Error(`fetch ${u} -> ${r.status}`);
  return r.json();
}

const athlete = (d, key) => d.athletes.find((a) => a.id === key.toLowerCase() || a.name.toLowerCase() === key.toLowerCase());
const dayIdx = () => Math.floor(Date.now() / 3600000); // hourly rotation

async function replyFor(text, d, content, env) {
  const parts = text.trim().split(/\s+/);
  const cmd = parts[0].replace(/^\//, "").split("@")[0].toLowerCase();
  const arg = text.trim().slice(parts[0].length).trim();

  switch (cmd) {
    case "help":
    case "start":
      return "🔺 ThreeTri bot — ask me anything:\n\n" + COMMANDS.map(([c, desc]) => `/${c} — ${desc}`).join("\n");

    case "standings":
    case "leaderboard":
      return "🏆 Standings (ThreeTri points)\n" + d.leaderboards.points.map((b, i) => {
        const a = athlete(d, b.athlete_id);
        return `${i + 1}. ${a.emoji} ${a.name} — ${Math.round(b.value)} pts · LV${a.level} · 🔥${a.streak.current_days}d`;
      }).join("\n");

    case "today": {
      const dig = (d.team.digest || []);
      const e = dig.find((x) => x.label === "Today") || dig[0];
      if (!e || !e.activities.length) return "Nothing logged yet today. Be the first. 🏊🚴🏃";
      const per = {};
      e.activities.forEach((act) => (per[act.athlete_id] = per[act.athlete_id] || []).push(act));
      return `📅 ${e.label}\n` + Object.entries(per).map(([aid, acts]) => {
        const a = athlete(d, aid);
        return `${a.emoji} ${a.name}: ` + acts.map((x) => `${x.sport} ${x.distance_km}km`).join(", ");
      }).join("\n");
    }

    case "week":
      return "📈 This week\n" + d.athletes.map((a) => {
        const w = a.this_week;
        return `${a.emoji} ${a.name}: ${w.all.distance_km} km · ${w.all.moving_h} h (🏊${w.swim.distance_km} 🚴${w.bike.distance_km} 🏃${w.run.distance_km})`;
      }).join("\n");

    case "coach": {
      const list = arg ? [athlete(d, arg)].filter(Boolean) : d.athletes;
      if (!list.length) return "Unknown athlete. Try /coach ebi, /coach sia or /coach alborz.";
      return list.map((a) => `🧠 ${a.name} — ${a.race ? a.race.label : ""}\n${a.weekly_summary || "No weekly read yet."}`).join("\n\n");
    }

    case "readiness": {
      let any = false;
      const lines = d.athletes.map((a) => {
        const r = a.readiness;
        if (!r) return `${a.emoji} ${a.name}: —`;
        any = true;
        const bits = [];
        if (r.hrv) bits.push(`HRV ${r.hrv}`);
        if (r.rhr) bits.push(`RHR ${r.rhr}`);
        if (r.sleep_hours) bits.push(`sleep ${r.sleep_hours}h`);
        if (r.body_battery) bits.push(`BB ${r.body_battery}`);
        return `${a.emoji} ${a.name}: ${r.status.toUpperCase()} (${bits.join(", ")})`;
      });
      return any ? "🫀 Readiness (latest Garmin)\n" + lines.join("\n") : "No Garmin recovery data yet.";
    }

    case "countdown":
      return `⏱️ ${d.race.days_to_go} days to ${d.race.short_name} (${d.race.phase} phase). Three of us. Three sports. One finish line. ${SITE(env)}`;

    case "challenge": {
      const c = d.team.challenge;
      return `🏝️ Road to Mallorca: ${Math.round(c.done_km).toLocaleString()} / ${c.target_km.toLocaleString()} km together (${c.pct}%). ${Math.round(c.remaining_km).toLocaleString()} km to go.`;
    }

    case "streak": {
      const top = [...d.athletes].sort((a, b) => b.streak.current_days - a.streak.current_days)[0];
      return top && top.streak.current_days >= 1
        ? `🔥 ${top.name} leads with a ${top.streak.current_days}-day streak. Don't break the chain.`
        : "No active streaks — get out there today. 🔥";
    }

    case "quote": {
      const qs = (content && content.quotes) || [];
      if (!qs.length) return "Show up today.";
      const q = qs[dayIdx() % qs.length];
      return `💬 “${q.text}” — ${q.author}`;
    }

    case "tip": {
      const tips = (content && content.tips) || {};
      const sport = ["swim", "bike", "run"].includes(arg.toLowerCase()) ? arg.toLowerCase() : ["swim", "bike", "run"][dayIdx() % 3];
      const list = tips[sport] || [];
      if (!list.length) return "No tips loaded.";
      const icon = { swim: "🏊", bike: "🚴", run: "🏃" }[sport];
      return `${icon} ${sport[0].toUpperCase() + sport.slice(1)} tip: ${list[dayIdx() % list.length]}`;
    }

    case "song": {
      const ls = (content && content.media && content.media.playlists) || [];
      if (!ls.length) return "No playlists loaded.";
      const p = ls[dayIdx() % ls.length];
      return `🎧 Training playlist: ${p.title} — ${p.url}`;
    }

    case "video": {
      const vs = (content && content.media && content.media.videos) || [];
      if (!vs.length) return "No videos loaded.";
      const v = vs[dayIdx() % vs.length];
      return `▶ Watch: ${v.title} — ${v.channel}\n${v.url}`;
    }

    case "ask": {
      if (!arg) return "Ask me something, e.g. /ask who has the best run consistency this month?";
      if (!env.ANTHROPIC_API_KEY && !env.HF_TOKEN) return "AI coach isn't configured (add ANTHROPIC_API_KEY or HF_TOKEN as a Worker secret).";
      const ctx = [`Race: ${d.race.short_name} in ${d.race.days_to_go} days (${d.race.phase} phase).`];
      for (const a of d.athletes) {
        const t = a.totals, w = a.this_week, r = a.readiness;
        ctx.push(`${a.name} (${a.race ? a.race.label : ""}): season ${t.all.distance_km}km (sw${t.swim.distance_km}/bk${t.bike.distance_km}/rn${t.run.distance_km}), this week ${w.all.distance_km}km, streak ${a.streak.current_days}d, consistency ${a.consistency_pct ?? "?"}%${r ? `, readiness ${r.status}` : ""}`);
      }
      const system = "You are a sharp, supportive triathlon coach with this team's training data below. Answer the user's question concisely (under 120 words) using the numbers. If the data can't answer it, say so briefly. No markdown.";
      const user = "TEAM DATA:\n" + ctx.join("\n") + `\n\nQUESTION: ${arg.slice(0, 300)}`;
      const ans = await llm(env, system, user);
      return ans ? `🧠 ${ans}` : "Couldn't generate an answer right now.";
    }

    default:
      return null; // ignore unknown commands
  }
}

async function llm(env, system, user) {
  try {
    if (env.ANTHROPIC_API_KEY) {
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
        body: JSON.stringify({ model: env.COACH_MODEL || "claude-haiku-4-5", max_tokens: 300, system, messages: [{ role: "user", content: user }] }),
      });
      const j = await r.json();
      return (j.content || []).filter((b) => b.type === "text").map((b) => b.text).join("").trim();
    }
    if (env.HF_TOKEN) {
      const r = await fetch("https://router.huggingface.co/v1/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${env.HF_TOKEN}`, "content-type": "application/json" },
        body: JSON.stringify({ model: env.HF_MODEL || "Qwen/Qwen2.5-7B-Instruct:cheapest", max_tokens: 300, temperature: 0.4, messages: [{ role: "system", content: system }, { role: "user", content: user }] }),
      });
      const j = await r.json();
      return (j.choices && j.choices[0] && j.choices[0].message.content || "").trim();
    }
  } catch (e) { /* fall through */ }
  return "";
}
