// ThreeTri homepage renderer — the Race Day HUD.
import {
  byId, el, clear, comma, km, oneDp, relDate,
  countUp, startCountdown, loadDashboard, toast, athleteMap,
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

let DATA, A; // dashboard payload + athlete map
let SPORTS = {};

init();

async function init() {
  try {
    DATA = await loadDashboard();
  } catch (err) {
    toast("Couldn't load data — run the pipeline or the sample generator.");
    console.error(err);
    return;
  }
  A = athleteMap(DATA);
  SPORTS = DATA.sports;

  renderNav();
  renderHero();
  renderPodium();
  renderHeadToHead();
  renderChallenge();
  renderLeaderboard();
  renderTrends();
  renderHighlights();
  renderCalendar();
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

  wrap.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Weekly ${trendMetric} volume">` +
    `<g class="trend-grid">${grid}</g>${xlabels}${lines}</svg>`;
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
    feed.appendChild(el("div", { class: "feed-item", "--accent": a.color },
      el("div", { class: "feed-ico" }, sportIcon(act.sport)),
      el("div", { class: "feed-main" },
        el("div", { class: "feed-name" }, act.name),
        el("div", { class: "feed-meta", html: `<span class="who">${a.name}</span> · ${relDate(act.date)}${act.avg_hr ? " · " + act.avg_hr + " bpm" : ""}` }),
      ),
      el("div", { class: "feed-fig" },
        el("div", { class: "d" }, `${oneDp(act.distance_km)} km`),
        el("div", { class: "p" }, act.pace || `${act.moving_min} min`),
      ),
    ));
  });
}

function renderFooter() {
  const sources = DATA.meta.data_sources.map((s) => s[0].toUpperCase() + s.slice(1)).join(" + ");
  byId("footer-sources").textContent = `Sources: ${sources}`;
  byId("footer-updated").textContent = DATA.meta.generated_at_human;
  byId("updated").textContent = `◷ ${DATA.meta.generated_at_human}`;
}
