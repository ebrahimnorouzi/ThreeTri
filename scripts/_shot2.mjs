import { chromium } from "playwright";
import os from "os";
import path from "path";

const OUT = process.env.SHOT_DIR || os.tmpdir();
const BASE = "http://localhost:8765";
const sels = (process.env.SELS || "#briefing-block,#scoring-block,#map-block,#cumulative-block,#split-block,#pattern-block").split(",");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(BASE + "/index.html", { waitUntil: "networkidle", timeout: 20000 });
await page.waitForTimeout(2200);
for (const sel of sels) {
  try {
    const locator = page.locator(sel.trim());
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    const file = path.join(OUT, `sec-${sel.trim().replace(/[#.]/g, "")}.png`);
    await locator.screenshot({ path: file });
    console.log("shot:", file);
  } catch (e) {
    console.log("skip", sel, e.message.split("\n")[0]);
  }
}
await browser.close();
console.log("ERRORS:", errors.length ? errors.join(" | ") : "none");
