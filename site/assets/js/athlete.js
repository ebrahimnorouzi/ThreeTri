// Athlete profile renderer.
import { byId, el, clear, comma, km, oneDp, relDate, loadDashboard, toast, athleteMap } from "./util.js";

const SPORT_TABS = [
  { key: "all", label: "All" }, { key: "swim", label: "Swim" },
  { key: "bike", label: "Bike" }, { key: "run", label: "Run" },
];
let DATA, ATH, SPORTS, trendMetric = "all";

init();

async function init() {
  try { DATA = await loadDashboard(); }
  catch (err) { toast("Couldn't load data."); console.error(err); return; }

  SPORTS = DATA.sports;
  const map = athleteMap(DATA);
  const id = new URLSearchParams(location.search).get("id") || DATA.athletes[0].id;
  ATH = map[id];
  if (!ATH) { toast("Unknown athlete."); return; }

  document.title = `ThreeTri · ${ATH.name}`;
  renderNav(map);
  renderHero();
  renderSportCards();
  renderWeekCompare();
  renderTrendTabs();
  renderReadiness();
  renderBadges();
  renderFeed();
  byId("footer-updated").textContent = DATA.meta.generated_at_human;
}

const sportIcon = (s) => (SPORTS[s] ? SPORTS[s].icon : "🏅");

function renderNav(map) {
  const nav = byId("athlete-nav");
  clear(nav);
  for (const a of DATA.athletes) {
    nav.appendChild(el("a", { href: `athlete.html?id=${a.id}`, "--accent": a.color,
      style: a.id === ATH.id ? "color:var(--text);border-color:var(--accent)" : "" },
      el("span", { class: "dot" }), a.name));
  }
}

function renderHero() {
  const hero = byId("ath-hero");
  hero.style.setProperty("--accent", ATH.color);
  clear(hero);
  const chips = el("div", { class: "ath-chips" },
    el("span", { class: "ath-chip", html: `LV <b>${ATH.level}</b> · ${ATH.xp.xp_pct}% to next` }),
    el("span", { class: "ath-chip", html: `🔥 <b>${ATH.streak.current_days}</b> day streak` }),
    el("span", { class: "ath-chip", html: `longest <b>${ATH.streak.longest_days}</b>d` }),
    el("span", { class: "ath-chip", html: `<b>${ATH.badge_count}</b>/12 badges` }),
  );
  if (ATH.readiness) chips.appendChild(el("span", { class: `rd ${ATH.readiness.status}` }, ATH.readiness.status));

  hero.append(
    el("div", { class: "ath-avatar" }, ATH.emoji),
    el("div", { class: "ath-id" },
      el("div", { class: "ath-name" }, ATH.name),
      el("div", { class: "ath-tag" }, ATH.tagline),
      chips),
    el("div", { class: "ath-points" }, el("span", { class: "n" }, comma(ATH.points)), el("span", { class: "l" }, "points")),
  );
  byId("season-sub").textContent = `Since ${DATA.meta.season_start} · ${ATH.totals.all.activities} sessions · ${comma(ATH.totals.all.distance_km)} km · ${oneDp(ATH.totals.all.moving_h)} h`;
}

function renderSportCards() {
  const wrap = byId("sport-cards");
  clear(wrap);
  for (const s of ["swim", "bike", "run"]) {
    const t = ATH.totals[s];
    const w = ATH.this_week[s];
    wrap.appendChild(el("div", { class: "sport-card", "--sc": SPORTS[s].color, style: `--sc:${SPORTS[s].color}` },
      el("div", { class: "sc-head" }, el("span", { class: "ico" }, sportIcon(s)), SPORTS[s].label),
      el("div", { class: "sc-big", html: `${comma(t.distance_km)}<span class="u"> km</span>` }),
      el("div", { class: "sc-sub", html:
        `<span><b>${t.activities}</b> sessions</span><span><b>${oneDp(t.moving_h)}</b> h</span>` +
        (s !== "swim" ? `<span><b>${comma(t.elevation_m)}</b> m climb</span>` : "") +
        `<span><b>${oneDp(w.distance_km)}</b> km this wk</span>` }),
    ));
  }
}

function renderWeekCompare() {
  const wrap = byId("wcompare");
  clear(wrap);
  const rows = [
    { label: "All", now: ATH.this_week.all.distance_km, prev: ATH.last_week.all.distance_km, unit: "km" },
    { label: "Swim", now: ATH.this_week.swim.distance_km, prev: ATH.last_week.swim.distance_km, unit: "km" },
    { label: "Bike", now: ATH.this_week.bike.distance_km, prev: ATH.last_week.bike.distance_km, unit: "km" },
    { label: "Run", now: ATH.this_week.run.distance_km, prev: ATH.last_week.run.distance_km, unit: "km" },
    { label: "Hours", now: ATH.this_week.all.moving_h, prev: ATH.last_week.all.moving_h, unit: "h" },
  ];
  wrap.style.setProperty("--accent", ATH.color);
  for (const r of rows) {
    const max = Math.max(0.001, r.now, r.prev);
    const now = el("span", {}); const prev = el("span", {});
    wrap.appendChild(el("div", { class: "wc-row" },
      el("div", { class: "wc-label" }, r.label),
      el("div", { class: "wc-seg" },
        el("div", { class: "wc-bar wc-now" }, now),
        el("div", { class: "wc-cap" }, `this week · ${oneDp(r.now)} ${r.unit}`)),
      el("div", { class: "wc-seg" },
        el("div", { class: "wc-bar wc-prev" }, prev),
        el("div", { class: "wc-cap" }, `last week · ${oneDp(r.prev)} ${r.unit}`)),
    ));
    requestAnimationFrame(() => { now.style.width = `${(r.now / max) * 100}%`; prev.style.width = `${(r.prev / max) * 100}%`; });
  }
}

function renderTrendTabs() {
  const tabs = byId("ath-trend-tabs");
  clear(tabs);
  SPORT_TABS.forEach((t) => tabs.appendChild(el("button", {
    class: `tab${t.key === trendMetric ? " active" : ""}`, "--accent": ATH.color,
    onclick: () => { trendMetric = t.key; renderTrendTabs(); drawTrend(); },
  }, t.label)));
  drawTrend();
}

function drawTrend() {
  const wrap = byId("ath-trend-chart");
  const t = DATA.trends;
  const key = trendMetric === "all" ? "all_km" : `${trendMetric}_km`;
  const vals = t.athletes[ATH.id][key];
  const n = vals.length;
  if (n < 2) { wrap.innerHTML = '<p style="color:var(--muted)">Not enough weeks yet.</p>'; return; }

  const W = 820, H = 280, padL = 40, padR = 14, padT = 14, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  let max = Math.max(1, Math.ceil(Math.max(...vals) / 10) * 10);
  const x = (i) => padL + (i * plotW) / (n - 1);
  const y = (v) => padT + plotH * (1 - v / max);

  let grid = "";
  for (let g = 0; g <= 4; g++) {
    const yy = padT + (plotH * g) / 4;
    grid += `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>` +
      `<text class="trend-axis" x="${padL - 6}" y="${yy + 3}" text-anchor="end">${Math.round((max * (4 - g)) / 4)}</text>`;
  }
  const step = Math.max(1, Math.round(n / 6));
  let xl = "";
  for (let i = 0; i < n; i += step) xl += `<text class="trend-axis" x="${x(i)}" y="${H - 8}" text-anchor="middle">${t.short[i]}</text>`;

  const pts = vals.map((v, i) => `${x(i)},${y(v)}`);
  const line = `M ${pts.join(" L ")}`;
  const area = `M ${x(0)},${y(0)} L ${pts.join(" L ")} L ${x(n - 1)},${y(0)} Z`;
  const last = n - 1;
  wrap.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Weekly ${trendMetric} volume for ${ATH.name}">` +
    `<g class="trend-grid">${grid}</g>${xl}` +
    `<path class="trend-area" d="${area}" fill="${ATH.color}"/>` +
    `<g class="trend-line" style="color:${ATH.color}"><path d="${line}" stroke="${ATH.color}"/></g>` +
    `<circle class="trend-dot" cx="${x(last)}" cy="${y(vals[last])}" r="4" fill="${ATH.color}"/></svg>`;
}

function renderReadiness() {
  if (!ATH.readiness) return;
  byId("readiness-block").hidden = false;
  const r = ATH.readiness;
  const grid = byId("readiness-grid");
  clear(grid);
  const cards = [
    { k: "HRV", v: r.hrv, sub: r.hrv_7d ? `7d avg ${r.hrv_7d}` : "", u: "ms" },
    { k: "Resting HR", v: r.rhr, sub: "", u: "bpm" },
    { k: "Sleep", v: r.sleep_hours, sub: r.sleep_score ? `score ${r.sleep_score}` : "", u: "h" },
    { k: "Body Battery", v: r.body_battery, sub: r.garmin_readiness ? `readiness ${r.garmin_readiness}` : "", u: "" },
  ];
  for (const c of cards) {
    if (c.v == null) continue;
    grid.appendChild(el("div", { class: "rd-card" },
      el("div", { class: "k" }, c.k),
      el("div", { class: "v", html: `${oneDp(c.v)} <small>${c.u}</small>` }),
      c.sub ? el("div", { class: "wc-cap" }, c.sub) : null,
    ));
  }
}

function renderBadges() {
  const grid = byId("badge-grid");
  clear(grid);
  byId("badge-sub").textContent = `${ATH.badge_count} of ${ATH.badges.length} earned`;
  for (const b of ATH.badges) {
    grid.appendChild(el("div", { class: `badge ${b.earned ? "earned" : "locked"}` },
      el("div", { class: "b-ico" }, b.icon),
      el("div", { class: "b-name" }, b.label),
      el("div", { class: "b-desc" }, b.desc),
    ));
  }
}

function renderFeed() {
  const feed = byId("ath-feed");
  clear(feed);
  for (const act of ATH.recent_activities) {
    feed.appendChild(el("div", { class: "feed-item", "--accent": ATH.color },
      el("div", { class: "feed-ico" }, sportIcon(act.sport)),
      el("div", { class: "feed-main" },
        el("div", { class: "feed-name" }, act.name),
        el("div", { class: "feed-meta", html: `${relDate(act.date)}${act.avg_hr ? " · " + act.avg_hr + " bpm" : ""}${act.elevation_m ? " · " + comma(act.elevation_m) + " m" : ""}` })),
      el("div", { class: "feed-fig" },
        el("div", { class: "d" }, `${oneDp(act.distance_km)} km`),
        el("div", { class: "p" }, act.pace || `${act.moving_min} min`)),
    ));
  }
}
