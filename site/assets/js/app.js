// ThreeTri homepage renderer — the Race Day HUD.
import {
  byId, el, clear, comma, km, oneDp, relDate,
  countUp, startCountdown, loadDashboard, toast, athleteMap,
  loadContent, pickDaily, dayIndex, enableTips,
  applyTimeTheme, THEME_GLYPH, THEME_LABEL,
} from "./util.js";

const SPORT_TABS = [
  { key: "swim", label: "Swim" },
  { key: "bike", label: "Bike" },
  { key: "run", label: "Run" },
  { key: "all", label: "All" },
];
const LB_TABS = [
  { key: "all", label: "All", metric: "all" },
  { key: "swim", label: "Swim", metric: "swim" },
  { key: "bike", label: "Bike", metric: "bike" },
  { key: "run", label: "Run", metric: "run" },
  { key: "hours", label: "Hours", metric: "hours" },
  { key: "elevation", label: "Climb", metric: "elevation" },
];

let DATA, A, CONTENT; // dashboard payload + athlete map + content library
let SPORTS = {};

init();

async function init() {
  let content;
  try {
    [DATA, content] = await Promise.all([loadDashboard(), loadContent()]);
  } catch (err) {
    toast("Couldn't load data — run the pipeline or the sample generator.");
    console.error(err);
    return;
  }
  A = athleteMap(DATA);
  SPORTS = DATA.sports;
  CONTENT = content;

  const ind = byId("theme-ind");
  const setTheme = () => { const t = applyTimeTheme(); if (ind) { ind.textContent = THEME_GLYPH[t]; ind.title = `${THEME_LABEL[t]} theme · follows your local time`; } };
  setTheme();
  setInterval(setTheme, 15 * 60 * 1000);

  renderNav();
  renderHero();
  renderMilestoneBanner();
  renderBriefing();
  renderMedia();
  renderDigest();
  renderPodium();
  renderHeadToHead();
  renderChallenge();
  renderContributions();
  renderLeaderboard();
  renderTrends();
  renderSportSplit();
  renderCumulative();
  renderPatterns();
  renderMap();
  renderHighlights();
  renderConsistency();
  renderCalendar();
  renderScoring();
  renderFeed();
  renderFooter();
}

const sportIcon = (s) => (SPORTS[s] ? SPORTS[s].icon : "🏅");
const sportColor = (s) => (SPORTS[s] ? SPORTS[s].color : "var(--c-ebi)");

// --------------------------------------------------------------------------- //
function renderNav() {
  const nav = byId("athlete-nav");
  clear(nav);
  for (const a of DATA.athletes) {
    nav.appendChild(
      el("a", { href: `athlete.html?id=${a.id}`, "--accent": a.color },
        el("span", { class: "dot" }), a.name)
    );
  }
}

function renderHero() {
  const r = DATA.race;
  byId("race-short").textContent = r.short_name;
  byId("race-meta").textContent = `Triathlon · ${r.location}`;
  byId("phase-chip").textContent = `${r.phase} · ${r.days_to_go} days to go`;
  const link = byId("race-link");
  link.href = r.url;
  byId("race-date-line").textContent = `${r.date_human} · Palma, Spain`;
  byId("footer-race-link").href = r.url;

  startCountdown(r.start_iso, {
    days: byId("cd-days"), hours: byId("cd-hours"), mins: byId("cd-mins"), secs: byId("cd-secs"),
  }, () => byId("countdown").classList.add("race-day"));
}

function renderPodium() {
  const wrap = byId("podium");
  clear(wrap);
  const ranked = [...DATA.athletes].sort((a, b) => b.points - a.points);
  ranked.forEach((a, i) => {
    const rank = i + 1;
    const card = el("div", { class: `pod-card r${rank}`, "--accent": a.color });

    const nameRow = el("div", { class: "pod-name-row" },
      el("span", { class: "pod-name" }, a.name),
      a.race ? el("span", { class: "race-badge", "--accent": a.color,
        title: `Targeting ${a.race.label}: ${a.race.legs.swim} / ${a.race.legs.bike} / ${a.race.legs.run} km` }, a.race.label) : null,
      el("span", { class: "pod-lvl" }, `LV ${a.level}`),
    );

    const streak = a.streak.current_days;
    const stats = el("div", { class: "pod-stats" },
      el("span", { class: "pod-stat", html: `<b>${km(a.this_week.all.distance_km)}</b> km this week` }),
      el("span", { class: "pod-stat", html: `<span class="flame">🔥</span> <b>${streak}</b> day streak` }),
      el("span", { class: "pod-stat", html: `<b>${a.badge_count}</b>/12 badges` }),
    );
    if (a.readiness) {
      stats.appendChild(el("span", { class: `rd ${a.readiness.status}` }, a.readiness.status));
    }

    const xpFill = el("div", { class: "xp-fill" });
    const body = el("div", { class: "pod-body" },
      nameRow,
      el("div", { class: "pod-tag" }, a.tagline),
      stats,
      el("div", { class: "xp-track" }, xpFill),
    );

    const ptsNum = el("span", { class: "pts" }, "0");
    const end = el("div", { class: "pod-end" },
      el("div", { class: "pod-points" }, ptsNum, el("span", { class: "pts-label" }, "points")),
    );

    card.append(
      el("div", { class: "pod-rank" }, String(rank)),
      el("a", { class: "avatar", href: `athlete.html?id=${a.id}`, title: a.name }, a.emoji),
      body, end,
    );
    wrap.appendChild(card);

    requestAnimationFrame(() => { xpFill.style.width = `${a.xp.xp_pct}%`; });
    countUp(ptsNum, a.points, { dur: 1300 });
  });
}

function renderHeadToHead() {
  const grid = byId("h2h-grid");
  clear(grid);
  const h2h = DATA.head_to_head.this_week;
  for (const key of ["swim", "bike", "run", "all"]) {
    const block = h2h[key];
    const card = el("div", { class: "h2h-card card" });
    const leaderName = block.leader ? A[block.leader].name : "—";
    const isAll = key === "all";
    card.appendChild(el("div", { class: "h2h-title" },
      el("span", { class: "sport-ico" }, isAll ? "🏆" : sportIcon(key)),
      isAll ? "All sports" : SPORTS[key].label,
      el("span", { class: "lead" }, block.leader ? `${leaderName} leads` : "no data yet"),
    ));

    const max = Math.max(0.001, ...Object.values(block.values));
    for (const a of DATA.athletes) {
      const v = block.values[a.id] || 0;
      const isLeader = a.id === block.leader;
      const fill = el("div", { class: `bar-fill${isLeader ? " leader" : ""}`, "--accent": a.color });
      const row = el("div", { class: "h2h-row", "--accent": a.color },
        el("span", { class: "h2h-who" }, el("span", { class: "chip" }), a.name),
        el("div", { class: "bar-track" }, fill),
        el("span", { class: "h2h-val", html: `${oneDp(v)}<span class="u"> km</span>` }),
      );
      card.appendChild(row);
      requestAnimationFrame(() => { fill.style.width = `${(v / max) * 100}%`; });
    }
    grid.appendChild(card);
  }
}

function renderChallenge() {
  const c = DATA.team.challenge;
  byId("challenge-label").textContent = c.label;
  const pctEl = byId("challenge-pct");
  countUp(pctEl, c.pct, { dur: 1400, decimals: 1, suffix: "%" });
  byId("challenge-sub").innerHTML =
    `<b>${comma(c.done_km)} km</b> down · <b>${comma(c.remaining_km)} km</b> to go · combined swim + bike + run across the team.`;
  requestAnimationFrame(() => { byId("challenge-bar").style.width = `${c.pct}%`; });
}

// ---- season leaderboard (tabbed bar chart) -------------------------------- //
let lbActive = "all";
function renderLeaderboard() {
  const tabs = byId("lb-tabs");
  clear(tabs);
  LB_TABS.forEach((t) => {
    const btn = el("button", {
      class: `tab${t.key === lbActive ? " active" : ""}`, role: "tab",
      "--accent": "var(--c-ebi)",
      onclick: () => { lbActive = t.key; renderLeaderboard(); },
    }, t.label);
    tabs.appendChild(btn);
  });
  drawLbChart();
}

function drawLbChart() {
  const chart = byId("lb-chart");
  clear(chart);
  const board = DATA.leaderboards.season[lbActive] || [];
  const max = Math.max(0.001, ...board.map((b) => b.value));
  const unit = board[0] ? board[0].unit : "";
  board.forEach((b) => {
    const a = A[b.athlete_id];
    const fill = el("div", { class: `bar-fill${b.rank === 1 ? " leader" : ""}`, "--accent": a.color });
    chart.appendChild(el("div", { class: "lb-row", "--accent": a.color },
      el("div", { class: "lb-who" }, el("span", { class: "av" }, a.emoji), a.name),
      el("div", { class: "bar-track big" }, fill),
      el("div", { class: "lb-val", html: `${comma(b.value)}<span class="u"> ${unit}</span>` }),
    ));
    requestAnimationFrame(() => { fill.style.width = `${(b.value / max) * 100}%`; });
  });
}

// ---- weekly trend chart (hand-rolled SVG) --------------------------------- //
let trendMetric = "all";
function renderTrends() {
  const tabs = byId("trend-tabs");
  clear(tabs);
  SPORT_TABS.forEach((t) => {
    tabs.appendChild(el("button", {
      class: `tab${t.key === trendMetric ? " active" : ""}`, role: "tab",
      onclick: () => { trendMetric = t.key; renderTrends(); },
    }, t.label));
  });
  drawTrendChart();
  drawTrendLegend();
}

function drawTrendChart() {
  const wrap = byId("trend-chart");
  const t = DATA.trends;
  const seriesKey = trendMetric === "all" ? "all_km" : `${trendMetric}_km`;
  const n = t.labels.length;
  if (n < 2) { wrap.innerHTML = '<p style="color:var(--muted)">Not enough weeks yet.</p>'; return; }

  const W = 820, H = 300, padL = 40, padR = 14, padT = 14, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  let max = 0;
  for (const a of DATA.athletes) max = Math.max(max, ...t.athletes[a.id][seriesKey]);
  max = Math.max(1, Math.ceil(max / 10) * 10);

  const x = (i) => padL + (i * plotW) / (n - 1);
  const y = (v) => padT + plotH * (1 - v / max);

  // grid + y labels
  let grid = "";
  for (let g = 0; g <= 4; g++) {
    const yy = padT + (plotH * g) / 4;
    const val = Math.round((max * (4 - g)) / 4);
    grid += `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>`;
    grid += `<text class="trend-axis" x="${padL - 6}" y="${yy + 3}" text-anchor="end">${val}</text>`;
  }
  // x labels (~6 evenly spaced)
  const step = Math.max(1, Math.round(n / 6));
  let xlabels = "";
  for (let i = 0; i < n; i += step) {
    xlabels += `<text class="trend-axis" x="${x(i)}" y="${H - 8}" text-anchor="middle">${t.short[i]}</text>`;
  }

  let lines = "";
  for (const a of DATA.athletes) {
    const vals = t.athletes[a.id][seriesKey];
    const pts = vals.map((v, i) => `${x(i)},${y(v)}`);
    const linePath = `M ${pts.join(" L ")}`;
    const areaPath = `M ${x(0)},${y(0)} L ${pts.join(" L ")} L ${x(n - 1)},${y(0)} Z`;
    const last = vals.length - 1;
    lines += `<path class="trend-area" d="${areaPath}" fill="${a.color}"/>`;
    lines += `<g class="trend-line" style="color:${a.color}"><path d="${linePath}" stroke="${a.color}"/></g>`;
    lines += `<circle class="trend-dot" cx="${x(last)}" cy="${y(vals[last])}" r="3.5" fill="${a.color}"/>`;
  }

  // transparent hover bands per week → tooltip with everyone's value
  let bands = "";
  const bw = plotW / (n - 1);
  for (let i = 0; i < n; i++) {
    const rows = DATA.athletes.map((a) => `${a.name}: ${t.athletes[a.id][seriesKey][i]} km`).join("\n");
    const tip = tipAttr(`Week of ${t.short[i]}\n${rows}`);
    bands += `<rect x="${x(i) - bw / 2}" y="${padT}" width="${bw}" height="${plotH}" fill="transparent" data-tip="${tip}"/>`;
  }

  wrap.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Weekly ${trendMetric} volume">` +
    `<g class="trend-grid">${grid}</g>${xlabels}${lines}${bands}</svg>`;
  enableTips(wrap);
}

// escape a tooltip string for an HTML attribute
function tipAttr(s) {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function drawTrendLegend() {
  const lg = byId("trend-legend");
  clear(lg);
  for (const a of DATA.athletes) {
    lg.appendChild(el("span", { class: "legend-item" },
      el("span", { class: "swatch", "--accent": a.color }), a.name));
  }
}

// ---- highlights ----------------------------------------------------------- //
function renderHighlights() {
  const grid = byId("highlight-grid");
  clear(grid);
  for (const h of DATA.highlights) {
    const color = h.athlete_id && A[h.athlete_id] ? A[h.athlete_id].color : "var(--c-ebi)";
    grid.appendChild(el("div", { class: "hl-card", "--accent": color },
      el("span", { class: "hl-ico" }, h.icon),
      el("div", { class: "hl-body" }, el("h4", {}, h.title), el("p", {}, h.text)),
    ));
  }
}

// ---- consistency calendar heatmap ----------------------------------------- //
function renderCalendar() {
  const wrap = byId("calendar");
  clear(wrap);
  const cal = DATA.team.calendar;
  if (!cal.length) return;

  const grid = el("div", { class: "cal-grid" });
  // pad leading cells so rows align to weekday (Mon=0..Sun=6)
  const first = new Date(cal[0].date + "T12:00:00");
  const lead = (first.getDay() + 6) % 7; // Mon=0
  for (let i = 0; i < lead; i++) grid.appendChild(el("div", { class: "cal-cell", style: "visibility:hidden" }));

  for (const d of cal) {
    const lvl = d.total === 0 ? 0 : d.total === 1 ? 1 : d.total === 2 ? 2 : d.total === 3 ? 3 : 4;
    const who = DATA.athletes.filter((a) => d[a.id] > 0).map((a) => a.name).join(", ");
    grid.appendChild(el("div", {
      class: "cal-cell", "data-lvl": String(lvl),
      title: `${d.date} · ${d.total} session${d.total === 1 ? "" : "s"}${who ? " · " + who : ""}`,
    }));
  }
  wrap.appendChild(grid);

  const foot = el("div", { class: "cal-foot" }, "less");
  [0, 1, 2, 3, 4].forEach((l) => foot.appendChild(el("div", { class: "cal-cell", "data-lvl": String(l) })));
  foot.appendChild(document.createTextNode("more"));
  wrap.appendChild(foot);
}

// ---- recent activity feed ------------------------------------------------- //
function renderFeed() {
  const feed = byId("feed");
  clear(feed);
  const all = [];
  for (const a of DATA.athletes) {
    for (const act of a.recent_activities) all.push({ ...act, athlete: a });
  }
  all.sort((x, y) => (x.datetime < y.datetime ? 1 : -1));
  all.slice(0, 12).forEach((act) => {
    const a = act.athlete;
    const item = el("div", { class: "feed-item", "--accent": a.color },
      el("div", { class: "feed-ico" }, sportIcon(act.sport)),
      el("div", { class: "feed-main" },
        el("div", { class: "feed-name" }, act.name),
        el("div", { class: "feed-meta", html: `<span class="who">${a.name}</span> · ${relDate(act.date)}${act.avg_hr ? " · " + act.avg_hr + " bpm" : ""}` }),
      ),
      el("div", { class: "feed-fig" },
        el("div", { class: "d" }, `${oneDp(act.distance_km)} km`),
        el("div", { class: "p" }, act.pace || `${act.moving_min} min`),
      ),
    );
    if (act.coach_note) item.appendChild(el("div", { class: "feed-note" }, `🧠 ${act.coach_note}`));
    feed.appendChild(item);
  });
}

function renderFooter() {
  const sources = DATA.meta.data_sources.map((s) => s[0].toUpperCase() + s.slice(1)).join(" + ");
  byId("footer-sources").textContent = `Sources: ${sources}`;
  byId("footer-updated").textContent = DATA.meta.generated_at_human;
  byId("updated").textContent = `◷ ${DATA.meta.generated_at_human}`;
}

// ---- milestone / race-day banner ------------------------------------------ //
function renderMilestoneBanner() {
  const b = byId("milestone-banner");
  if (!CONTENT || !CONTENT.messages) return;
  const m = CONTENT.messages, r = DATA.race, pct = DATA.team.challenge.pct;
  let html = null, cls = "banner";
  const card = (icon, title, msg) => `<div class="banner-emoji">${icon}</div><div class="banner-body"><h3>${title}</h3><p>${msg}</p></div>`;

  if (r.days_to_go <= 0 && m.race_day) {
    cls += " race-day"; html = card("🏁", m.race_day.title, m.race_day.message);
  } else if (r.days_to_go <= 7 && (m.race_week || []).length) {
    cls += " race-week";
    html = card("⚡", `Race week — ${r.days_to_go} day${r.days_to_go === 1 ? "" : "s"} to go`, pickDaily(m.race_week));
  } else {
    const dm = (m.day_milestones || []).find((x) => x.days === r.days_to_go);
    if (dm) { cls += " milestone"; html = card("📍", dm.title, dm.message); }
    else {
      const reached = (m.goal_milestones || []).filter((x) => pct >= x.pct).sort((a, c) => c.pct - a.pct)[0];
      if (reached && reached.pct >= 10) { cls += " goal"; html = card("🏝️", reached.title, reached.message); }
    }
  }
  if (!html) { b.hidden = true; return; }
  b.className = cls; b.innerHTML = html; b.hidden = false;
}

// ---- daily briefing -------------------------------------------------------- //
function renderBriefing() {
  const block = byId("briefing-block");
  if (!CONTENT) { block.hidden = true; return; }
  const now = new Date();
  byId("briefing-date").textContent =
    now.toLocaleDateString("en-US", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) +
    ` · ${DATA.race.days_to_go} days to ${DATA.race.short_name}`;

  const q = pickDaily(CONTENT.quotes) || { text: "Show up today.", author: "ThreeTri" };
  byId("brief-quote").innerHTML =
    `<div class="bq-mark">“</div><blockquote>${q.text}</blockquote><cite>— ${q.author}</cite>`;

  const sports = ["swim", "bike", "run"];
  const sp = sports[dayIndex() % 3];
  const tips = (CONTENT.tips && CONTENT.tips[sp]) || [];
  const tip = tips.length ? tips[Math.floor(dayIndex() / 3) % tips.length] : "";
  byId("brief-tip").innerHTML =
    `<h4>${sportIcon(sp)} ${SPORTS[sp].label} tip of the day</h4><p>${tip}</p>`;

  const lg = pickDaily(CONTENT.legends);
  const lgEl = byId("brief-legend");
  if (lg) {
    lgEl.innerHTML =
      `<h4>🏅 Legend of the day</h4><p class="lg-name">${lg.name} <span class="lg-sport">· ${lg.sport}</span></p>` +
      `<p>${lg.blurb}</p><a href="${lg.wikipedia_url}" target="_blank" rel="noopener">Wikipedia ↗</a>`;
  } else { lgEl.hidden = true; }

  const ng = byId("nudge-grid"); clear(ng);
  const nudges = (CONTENT.messages && CONTENT.messages.athlete_nudges) || [];
  DATA.athletes.forEach((a, i) => {
    const n = nudges.length ? nudges[(dayIndex() + i * 7) % nudges.length] : "";
    ng.appendChild(el("div", { class: "nudge", "--accent": a.color },
      el("span", { class: "nudge-who" }, `${a.emoji} ${a.name}`),
      el("span", { class: "nudge-text" }, n)));
  });
}

// ---- daily Watch & Listen -------------------------------------------------- //
function renderMedia() {
  const row = byId("media-row");
  if (!row) return;
  clear(row);
  const media = CONTENT && CONTENT.media;
  if (!media) { row.remove(); return; }

  const vids = media.videos || [];
  const lists = media.playlists || [];
  if (vids.length) {
    const v = vids[dayIndex() % vids.length];
    const thumb = `https://i.ytimg.com/vi/${v.youtube_id}/hqdefault.jpg`;
    row.appendChild(el("a", { class: "media-card video", href: v.url, target: "_blank", rel: "noopener" },
      el("div", { class: "media-thumb", style: `background-image:url('${thumb}')` }, el("span", { class: "play" }, "▶")),
      el("div", { class: "media-meta" },
        el("div", { class: "media-kind" }, `▶ Watch today · ${v.topic}`),
        el("div", { class: "media-title" }, v.title),
        el("div", { class: "media-by" }, v.channel)),
    ));
  }
  if (lists.length) {
    const p = lists[(dayIndex() + 1) % lists.length];
    row.appendChild(el("a", { class: "media-card audio", href: p.url, target: "_blank", rel: "noopener" },
      el("div", { class: "media-spotify" }, "🎧"),
      el("div", { class: "media-meta" },
        el("div", { class: "media-kind" }, `Listen today · ${p.kind || "mix"}`),
        el("div", { class: "media-title" }, p.title),
        el("div", { class: "media-by" }, `${p.by} · Spotify ↗`)),
    ));
  }
  if (!row.children.length) row.remove();
}

// ---- daily digest timeline (who did what) --------------------------------- //
function renderDigest() {
  const wrap = byId("timeline");
  if (!wrap) return;
  clear(wrap);
  const digest = (DATA.team && DATA.team.digest) || [];
  if (!digest.length) { byId("digest-block").hidden = true; return; }

  for (const day of digest) {
    const dots = day.athletes_active.map((id) =>
      el("span", { class: "tl-dot", "--accent": A[id] ? A[id].color : "var(--c-ebi)", title: A[id] ? A[id].name : id }));
    const head = el("div", { class: "tl-day" },
      el("span", { class: "tl-label" }, day.label),
      el("span", { class: "tl-dots" }, ...dots),
      el("span", { class: "tl-count" }, `${day.activities.length} session${day.activities.length === 1 ? "" : "s"}`));
    const items = el("div", { class: "tl-items" });
    for (const act of day.activities) {
      const a = A[act.athlete_id] || { name: act.athlete_id, color: "var(--c-ebi)" };
      const row = el("div", { class: "tl-item", "--accent": a.color });
      const main = el("div", { class: "tl-main" },
        el("span", { class: "tl-ico" }, sportIcon(act.sport)),
        el("span", { class: "tl-who" }, a.name),
        el("span", { class: "tl-name" }, act.name),
        el("span", { class: "tl-fig" }, `${oneDp(act.distance_km)} km${act.pace ? " · " + act.pace : ""}`));
      row.appendChild(main);
      if (act.coach_note) {
        const note = el("div", { class: "tl-note", hidden: true }, el("span", { class: "tl-note-ico" }, "🧠"), act.coach_note);
        main.appendChild(el("button", { class: "tl-toggle", title: "Coach's read",
          onclick: () => { note.hidden = !note.hidden; } }, "🧠"));
        row.appendChild(note);
      }
      items.appendChild(row);
    }
    wrap.appendChild(el("div", { class: "tl-group" }, head, items));
  }
}

// ---- team contribution breakdown ------------------------------------------ //
function renderContributions() {
  const stack = byId("contrib-stack"), legend = byId("contrib-legend");
  if (!stack) return;
  clear(stack); clear(legend);
  for (const c of DATA.team.challenge.contributions || []) {
    const a = A[c.athlete_id];
    const seg = el("div", { class: "contrib-seg", "--accent": a.color,
      "data-tip": tipAttr(`${a.name}: ${comma(c.km)} km · ${c.pct_of_done}% of distance done · ${c.pct_of_goal}% of goal`) });
    stack.appendChild(seg);
    requestAnimationFrame(() => { seg.style.width = `${c.pct_of_done}%`; });
    legend.appendChild(el("span", { class: "contrib-item", "--accent": a.color },
      el("span", { class: "sw" }), `${a.name} · ${comma(c.km)} km (${c.pct_of_done}%)`));
  }
  enableTips(stack);
}

// ---- discipline split ------------------------------------------------------ //
function renderSportSplit() {
  const grid = byId("split-grid"); clear(grid);
  for (const a of DATA.athletes) {
    const t = a.totals, tot = t.all.distance_km || 1;
    const card = el("div", { class: "card split-card", "--accent": a.color });
    card.appendChild(el("div", { class: "split-head" }, el("span", { class: "av" }, a.emoji), a.name));
    const bar = el("div", { class: "split-bar" });
    for (const s of ["swim", "bike", "run"]) {
      const v = t[s].distance_km, w = (v / tot) * 100;
      const seg = el("div", { class: "split-seg", style: `background:${SPORTS[s].color}`,
        "data-tip": tipAttr(`${a.name} · ${SPORTS[s].label}: ${comma(v)} km (${Math.round(w)}%)`) });
      bar.appendChild(seg);
      requestAnimationFrame(() => { seg.style.width = `${w}%`; });
    }
    card.appendChild(bar);
    const legend = el("div", { class: "split-legend" });
    for (const s of ["swim", "bike", "run"]) {
      legend.appendChild(el("span", { class: "split-li" },
        el("span", { class: "sw", style: `background:${SPORTS[s].color}` }),
        `${SPORTS[s].label} ${comma(t[s].distance_km)}`));
    }
    card.appendChild(legend);
    grid.appendChild(card);
    enableTips(bar);
  }
}

// ---- cumulative-to-goal line ---------------------------------------------- //
function renderCumulative() {
  const wrap = byId("cumulative-chart"), cu = DATA.team.cumulative;
  const n = cu.cumulative_km.length;
  if (n < 2) { wrap.innerHTML = '<p style="color:var(--muted)">Not enough weeks yet.</p>'; return; }
  const W = 820, H = 300, padL = 52, padR = 16, padT = 16, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const max = Math.max(cu.target_km, cu.cumulative_km[n - 1]) * 1.02;
  const x = (i) => padL + (i * plotW) / (n - 1);
  const y = (v) => padT + plotH * (1 - v / max);

  let grid = "";
  for (let g = 0; g <= 4; g++) {
    const yy = padT + (plotH * g) / 4, val = Math.round((max * (4 - g)) / 4);
    grid += `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>` +
      `<text class="trend-axis" x="${padL - 6}" y="${yy + 3}" text-anchor="end">${comma(val)}</text>`;
  }
  const step = Math.max(1, Math.round(n / 6));
  let xl = "";
  for (let i = 0; i < n; i += step) xl += `<text class="trend-axis" x="${x(i)}" y="${H - 8}" text-anchor="middle">${cu.short[i]}</text>`;

  const gy = y(cu.target_km);
  const goal = `<line x1="${padL}" y1="${gy}" x2="${W - padR}" y2="${gy}" stroke="var(--gold)" stroke-dasharray="6 5" stroke-width="1.5"/>` +
    `<text class="trend-axis" x="${W - padR}" y="${gy - 5}" text-anchor="end" fill="var(--gold)">goal ${comma(cu.target_km)}</text>`;
  const pts = cu.cumulative_km.map((v, i) => `${x(i)},${y(v)}`);
  const area = `M ${x(0)},${y(0)} L ${pts.join(" L ")} L ${x(n - 1)},${y(0)} Z`;
  const line = `M ${pts.join(" L ")}`;
  let bands = ""; const bw = plotW / (n - 1);
  for (let i = 0; i < n; i++) {
    bands += `<rect x="${x(i) - bw / 2}" y="${padT}" width="${bw}" height="${plotH}" fill="transparent" ` +
      `data-tip="${tipAttr(`Week of ${cu.short[i]}\n+${cu.weekly_km[i]} km that week\nTotal: ${comma(cu.cumulative_km[i])} km`)}"/>`;
  }
  wrap.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Cumulative team distance toward goal">` +
    `<g class="trend-grid">${grid}</g>${xl}` +
    `<path class="trend-area" d="${area}" fill="var(--c-run)"/>` +
    `<g class="trend-line" style="color:var(--c-run)"><path d="${line}" stroke="var(--c-run)"/></g>` +
    `${goal}${bands}</svg>`;
  enableTips(wrap);
}

// ---- training patterns (day of week / hour of day) ------------------------ //
function renderPatterns() {
  const p = DATA.team.patterns;
  const drawBars = (host, values, labelFor, tipFor) => {
    clear(host);
    const max = Math.max(1, ...values);
    const row = el("div", { class: "bars-row" });
    values.forEach((v, i) => {
      const col = el("div", { class: "bar-col", "data-tip": tipAttr(tipFor(i, v)) });
      const fill = el("div", { class: "bar-v" });
      col.appendChild(fill);
      const lbl = labelFor(i);
      if (lbl) col.appendChild(el("span", { class: "bar-x" }, lbl));
      row.appendChild(col);
      requestAnimationFrame(() => { fill.style.height = `${(v / max) * 100}%`; });
    });
    host.appendChild(row);
    enableTips(host);
  };
  drawBars(byId("dow-chart"), p.day_of_week,
    (i) => p.dow_labels[i], (i, v) => `${p.dow_labels[i]}: ${v} session${v === 1 ? "" : "s"}`);
  drawBars(byId("hod-chart"), p.hour_of_day,
    (h) => (h % 6 === 0 ? `${h}h` : ""), (h, v) => `${String(h).padStart(2, "0")}:00 — ${v} session${v === 1 ? "" : "s"}`);
}

// ---- training map (Leaflet, graceful) ------------------------------------- //
function renderMap() {
  const locs = DATA.team.locations || [];
  if (!locs.length) { byId("map-block").hidden = true; return; }
  let tries = 0;
  (function build() {
    if (!window.L) {
      if (++tries > 20) { byId("map-block").hidden = true; return; }
      return void setTimeout(build, 250);
    }
    const L = window.L;
    const map = L.map("train-map", { scrollWheelZoom: false });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19, attribution: '&copy; OpenStreetMap &copy; CARTO',
    }).addTo(map);
    const maxc = Math.max(...locs.map((l) => l.count));
    const bounds = [];
    for (const l of locs) {
      const r = 5 + 13 * (l.count / maxc);
      const who = l.athletes.map((id) => (A[id] ? A[id].name : id)).join(", ");
      L.circleMarker([l.lat, l.lng], { radius: r, color: "#22d3ee", weight: 1.5, fillColor: "#22d3ee", fillOpacity: 0.45 })
        .bindTooltip(`${l.count} session${l.count === 1 ? "" : "s"} · ${who}`)
        .addTo(map);
      bounds.push([l.lat, l.lng]);
    }
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
  })();
}

// ---- consistency (per-person + note) -------------------------------------- //
function renderConsistency() {
  const wrap = byId("consist-people"); clear(wrap);
  for (const b of DATA.leaderboards.consistency || []) {
    const a = A[b.athlete_id];
    const fill = el("div", { class: "bar-fill", "--accent": a.color });
    wrap.appendChild(el("div", { class: "consist-row", "--accent": a.color },
      el("div", { class: "consist-who" }, el("span", { class: "chip" }), a.name),
      el("div", { class: "bar-track" }, fill),
      el("div", { class: "consist-val" }, `${Math.round(b.value)}%`)));
    requestAnimationFrame(() => { fill.style.width = `${b.value}%`; });
  }
  byId("consist-note").textContent =
    "Consistency = the share of the last 56 days (8 weeks) with at least one session. " +
    "The calendar shows the team's combined activity — brighter green means more sessions that day.";
}

// ---- scoring explainer + badge gallery ------------------------------------ //
function renderScoring() {
  const s = DATA.scoring;
  if (!s) { byId("scoring-block").hidden = true; return; }
  const ppk = s.points_per_km;
  byId("score-formula").innerHTML =
    `<h4>How points are earned</h4><ul class="formula">` +
    `<li>🏊 Swim <b>${ppk.swim}</b> pts/km</li>` +
    `<li>🚴 Bike <b>${ppk.bike}</b> pt/km</li>` +
    `<li>🏃 Run <b>${ppk.run}</b> pts/km</li>` +
    `<li>⛰️ Climbing <b>${s.elevation_per_m}</b> pts/m</li>` +
    `<li>✅ Every session <b>${s.per_activity}</b> pts</li>` +
    `<li>🔥 Every streak day <b>${s.streak_day}</b> pts</li></ul>` +
    `<p class="formula-note">Swimming pays the most per km because it's the slowest distance to cover — so honest volume in every discipline is rewarded, not just running mileage.</p>`;
  byId("score-levels").innerHTML =
    `<h4>Levels &amp; XP</h4><p>Every <b>${s.level_size}</b> points levels you up. The XP bar on the podium shows progress to your next level.</p>` +
    `<p class="formula-note">Levels reward the long game — consistency compounds faster than any single hero day.</p>`;

  const earnedBy = {};
  for (const b of s.badges) earnedBy[b.id] = [];
  for (const a of DATA.athletes) for (const b of a.badges) if (b.earned) (earnedBy[b.id] ||= []).push(a);

  byId("badges-count").textContent = `· ${s.badges.length} to collect`;
  const gal = byId("badge-gallery"); clear(gal);
  for (const b of s.badges) {
    const who = earnedBy[b.id] || [];
    const card = el("div", { class: `badge ${who.length ? "earned" : "locked"}` },
      el("div", { class: "b-ico" }, b.icon),
      el("div", { class: "b-name" }, b.label),
      el("div", { class: "b-desc" }, b.desc));
    const by = el("div", { class: "b-by" });
    if (who.length) who.forEach((a) => by.appendChild(el("span", { class: "b-dot", "--accent": a.color, title: a.name }, a.initials)));
    else by.appendChild(el("span", { class: "b-none" }, "not yet earned"));
    card.appendChild(by);
    gal.appendChild(card);
  }
}
