#!/usr/bin/env node
// Read-only selector probe for writing a storyline (part of the demo-video-recording skill).
//
//   node probe.mjs <baseUrl> <path> [path ...] [--out <dir>] [--width 1600] [--height 862]
//
// For each page: loads it (no clicks, no typing), waits for the network to settle, saves a full-page screenshot and
// prints what a storyline can target: headings (with level), <section> titles as ctx.section() will see them, buttons
// with their ARIA role and state (tabs and toggles are often role=radio), inputs with placeholders, and the first
// links. Writes the same as <out>/<slug>.json. Uses the Playwright installed next to this script, so it runs from
// anywhere: `node <skill>/scripts/probe.mjs http://localhost:3000 / /reports`.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : dflt; };
const positional = argv.filter((a, i) => !a.startsWith("--") && !(i > 0 && argv[i - 1].startsWith("--")));
const [base, ...paths] = positional;
if (!base || !paths.length) {
  console.error("usage: node probe.mjs <baseUrl> <path> [path ...] [--out <dir>] [--width 1600] [--height 862]");
  process.exit(2);
}
const out = path.resolve(opt("--out", "probe-out"));
fs.mkdirSync(out, { recursive: true });
// 1600x862 is the app viewport inside the recording stage's window (1600x900 minus the 38 px title bar).
const viewport = { width: Number(opt("--width", 1600)), height: Number(opt("--height", 862)) };

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport })).newPage();
for (const p of paths) {
  const url = base.replace(/\/$/, "") + p;
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(800);
  const slug = (p.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "root").slice(0, 60);
  await page.screenshot({ path: path.join(out, `${slug}.png`), fullPage: true });
  const info = await page.evaluate(() => {
    const text = (el) => (el.innerText || el.getAttribute("aria-label") || el.value || "").replace(/\s+/g, " ").trim().slice(0, 80);
    const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const all = (sel) => [...document.querySelectorAll(sel)].filter(visible);
    return {
      url: location.href,
      title: document.title,
      headings: all("h1,h2,h3,h4,[role=heading]").map((h) => `${h.tagName.toLowerCase()}: ${text(h)}`),
      sections: all("section").map((s) => {
        const h = s.querySelector("h1,h2,h3,h4,[role=heading]");
        return h ? text(h) : `(no heading) ${text(s).slice(0, 40)}`;
      }),
      buttons: all("button,[role=button],[role=tab],[role=radio],[role=menuitem]").map((b) =>
        `${text(b) || "(icon)"}  [${b.getAttribute("role") || b.tagName.toLowerCase()}${b.disabled || b.getAttribute("aria-disabled") === "true" ? ", disabled" : ""}${b.getAttribute("aria-checked") === "true" || b.getAttribute("aria-pressed") === "true" || b.getAttribute("aria-selected") === "true" ? ", on" : ""}]`),
      inputs: all("input,textarea,select,[contenteditable=true]").map((i) => `${i.tagName.toLowerCase()} placeholder="${i.getAttribute("placeholder") || ""}" name="${i.getAttribute("name") || ""}" aria-label="${i.getAttribute("aria-label") || ""}"`),
      links: all("a[href]").slice(0, 40).map((a) => `${text(a) || "(icon)"} -> ${a.getAttribute("href")}`),
    };
  });
  fs.writeFileSync(path.join(out, `${slug}.json`), JSON.stringify(info, null, 2));
  console.log(`\n=== ${p}  (${info.title})  screenshot: ${path.join(out, `${slug}.png`)}`);
  for (const [k, v] of Object.entries(info)) if (Array.isArray(v)) console.log(`${k} (${v.length}):\n  ${v.slice(0, 30).join("\n  ")}${v.length > 30 ? "\n  ..." : ""}`);
}
await browser.close();
