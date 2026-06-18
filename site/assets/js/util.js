// Shared helpers for the ThreeTri HUD (used by app.js and athlete.js).

export const byId = (id) => document.getElementById(id);

/** Tiny DOM builder: el('div', {class:'x', '--accent':'#f00'}, child, 'text') */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("--")) node.style.setProperty(k, v);
    else if (k === "style") node.setAttribute("style", v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  return node;
}

export const clear = (node) => { while (node && node.firstChild) node.removeChild(node.firstChild); };

// ---- formatting -----------------------------------------------------------
export const comma = (n) => Math.round(n).toLocaleString("en-US");
export const km = (n) => `${(+n).toLocaleString("en-US", { maximumFractionDigits: n < 100 ? 1 : 0 })}`;
export const oneDp = (n) => (+n).toLocaleString("en-US", { maximumFractionDigits: 1 });

export function relDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + (iso.length <= 10 ? "T12:00:00" : ""));
  const days = Math.round((Date.now() - d.getTime()) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  if (days < 35) return `${Math.floor(days / 7)}w ago`;
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short" });
}

// ---- animated count-up ----------------------------------------------------
export function countUp(node, to, { dur = 1100, decimals = 0, suffix = "" } = {}) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    node.textContent = to.toLocaleString("en-US", { maximumFractionDigits: decimals }) + suffix;
    return;
  }
  const start = performance.now();
  const from = 0;
  function step(t) {
    const p = Math.min(1, (t - start) / dur);
    const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
    const val = from + (to - from) * eased;
    node.textContent = val.toLocaleString("en-US", { maximumFractionDigits: decimals }) + suffix;
    if (p < 1) requestAnimationFrame(step);
    else node.textContent = to.toLocaleString("en-US", { maximumFractionDigits: decimals }) + suffix;
  }
  requestAnimationFrame(step);
}

// ---- live countdown -------------------------------------------------------
const pad = (n) => String(n).padStart(2, "0");

export function startCountdown(targetIso, els, onDone) {
  const target = new Date(targetIso).getTime();
  function tick() {
    const diff = target - Date.now();
    if (diff <= 0) {
      els.days.textContent = "00"; els.hours.textContent = "00";
      els.mins.textContent = "00"; els.secs.textContent = "00";
      if (onDone) onDone();
      return false;
    }
    const s = Math.floor(diff / 1000);
    els.days.textContent = pad(Math.floor(s / 86400));
    els.hours.textContent = pad(Math.floor((s % 86400) / 3600));
    els.mins.textContent = pad(Math.floor((s % 3600) / 60));
    els.secs.textContent = pad(s % 60);
    return true;
  }
  if (tick()) {
    const id = setInterval(() => { if (!tick()) clearInterval(id); }, 1000);
  }
}

// ---- data loading ---------------------------------------------------------
export async function loadDashboard() {
  const res = await fetch("data/dashboard.json", { cache: "no-cache" });
  if (!res.ok) throw new Error(`data/dashboard.json → HTTP ${res.status}`);
  return res.json();
}

export function toast(msg) {
  const t = byId("toast");
  if (!t) return;
  t.textContent = msg;
  t.hidden = false;
}

// athlete lookup by id from the dashboard payload
export function athleteMap(data) {
  const m = {};
  for (const a of data.athletes) m[a.id] = a;
  return m;
}
