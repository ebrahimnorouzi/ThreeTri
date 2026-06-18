import { chromium } from "playwright";
import os from "os";
import path from "path";

const OUT = process.env.SHOT_DIR || os.tmpdir();
const BASE = "http://localhost:8765";

const shots = [
  { name: "home-desktop", url: "/index.html", vp: { width: 1280, height: 900 }, full: true },
  { name: "home-mobile", url: "/index.html", vp: { width: 390, height: 844 }, full: true },
  { name: "athlete-desktop", url: "/athlete.html?id=sia", vp: { width: 1280, height: 900 }, full: true },
  { name: "qr-mobile", url: "/qr.html", vp: { width: 390, height: 844 }, full: false },
];

const browser = await chromium.launch();
const errors = [];
for (const s of shots) {
  const page = await browser.newPage({ viewport: s.vp, deviceScaleFactor: 2 });
  page.on("console", (m) => { if (m.type() === "error") errors.push(`[${s.name}] console.error: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`[${s.name}] pageerror: ${e.message}`));
  await page.goto(BASE + s.url, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1800); // let count-ups, bar fills, fonts settle
  const file = path.join(OUT, `threetri-${s.name}.png`);
  await page.screenshot({ path: file, fullPage: s.full });
  console.log("shot:", file);
  await page.close();
}
await browser.close();
console.log("\nRUNTIME ERRORS:", errors.length ? "\n" + errors.join("\n") : "none");
