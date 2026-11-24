#!/usr/bin/env node
// Read-only selector probe for writing a storyline (part of the wicked-garden-demo skill).
//
//   wicked-garden run scripts/demo/probe.mjs <baseUrl> <path> [path ...] [--out <dir>] [--width 1600] [--height 862]
//
// For each page: loads it (no clicks, no typing), waits for the network to settle, saves a full-page screenshot and
// prints what a storyline can target: headings (with level), <section> titles as ctx.section() will see them, buttons
// with their ARIA role and state (tabs and toggles are often role=radio), inputs with placeholders, and the first
// links. Writes the same as <out>/<slug>.json. Uses the Playwright installed by setup.mjs (see _playwright.mjs), so it runs from
// anywhere: `wicked-garden run scripts/demo/probe.mjs http://localhost:3000 / /reports`.
//
// The browser sends no writes (readonly.mjs). The engine-run `demo_probe` Tool (demo-record.mjs probe) calls
// probePages with the request policy, and with `structureOnly` when the app's live rows may not reach a model: then
// no screenshot is written and no text from a table, a list or a grid is read, only the page's controls and labels.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadChromium } from "./_playwright.mjs";
import { armGuard, armPolicy } from "./readonly.mjs";

/** One file-name-safe slug per path. */
export const slugOf = (p) => (String(p).replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "root").slice(0, 60);

/** What a page or frame shows that a storyline can target (run in the page; `structure` withholds data). */
const SUMMARISE = (structure) => {
        // Live data sits in tables, lists and grids: with `structure` nothing inside one is read (text, labels,
        // values, link targets), and an element's text never descends into one.
        const DATA = "table,ul,ol,dl,[role=grid],[role=table],[role=list],[role=listbox],[role=row],[role=cell],[role=gridcell],[role=listitem]";
        const dataRegion = (el) => structure && !!el.closest(DATA);
        const ownText = (el) => {
          if (!structure) return el.innerText || "";
          let t = "";
          // Only what is rendered: no data region, no hidden element, no script or style text.
          const shown = (e) => { const cs = getComputedStyle(e); return cs.display !== "none" && cs.visibility !== "hidden" && !e.hidden; };
          const walk = (n) => {
            for (const c of n.childNodes) {
              if (c.nodeType === 3) t += c.textContent;
              else if (c.nodeType === 1 && !c.matches(DATA) && !c.matches("script,style,template,noscript") && shown(c)) walk(c);
            }
          };
          walk(el);
          return t;
        };
        const text = (el) => (dataRegion(el) ? "(data)" : (ownText(el) || el.getAttribute("aria-label") || (structure ? "" : el.value) || "")).replace(/\s+/g, " ").trim().slice(0, 80);
        const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        const all = (sel) => [...document.querySelectorAll(sel)].filter(visible);
        return {
          url: location.pathname,
          title: structure ? "" : document.title,
          headings: all("h1,h2,h3,h4,[role=heading]").map((h) => `${h.tagName.toLowerCase()}: ${text(h)}`),
          sections: all("section").map((s) => {
            const h = s.querySelector("h1,h2,h3,h4,[role=heading]");
            return h ? text(h) : `(no heading) ${structure ? "" : text(s).slice(0, 40)}`;
          }),
          buttons: all("button,[role=button],[role=tab],[role=radio],[role=menuitem]").map((b) =>
            `${text(b) || "(icon)"}  [${b.getAttribute("role") || b.tagName.toLowerCase()}${b.disabled || b.getAttribute("aria-disabled") === "true" ? ", disabled" : ""}${b.getAttribute("aria-checked") === "true" || b.getAttribute("aria-pressed") === "true" || b.getAttribute("aria-selected") === "true" ? ", on" : ""}]`),
          inputs: all("input,textarea,select,[contenteditable=true]").map((i) => (structure
            ? (dataRegion(i) ? `${i.tagName.toLowerCase()} (data)` : `${i.tagName.toLowerCase()} placeholder="${i.getAttribute("placeholder") || ""}" aria-label="${i.getAttribute("aria-label") || ""}"`)
            : `${i.tagName.toLowerCase()} placeholder="${i.getAttribute("placeholder") || ""}" name="${i.getAttribute("name") || ""}" aria-label="${i.getAttribute("aria-label") || ""}"`)),
          // With `structure`, a link's target is never written (it can carry a row's id), only its text.
          links: all("a[href]").slice(0, 40).map((a) => (structure ? `${text(a) || "(icon)"}` : `${text(a) || "(icon)"} -> ${a.getAttribute("href")}`)),
          ...(structure ? { structureOnly: "no screenshot; text inside tables, lists and grids is withheld (this app's data stays out of model context)" } : {}),
        };
      };

/**
 * Probe each path; returns `[{path, slug, info, blocked}]` and writes `<out>/<slug>.json` (+ `.png` unless
 * structureOnly). `policy` (readonly.mjs demoPolicy) replaces the hand probe's write guard.
 */
export async function probePages({ base, paths, out, viewport = { width: 1600, height: 862 }, policy = null, structureOnly = false }) {
  fs.mkdirSync(out, { recursive: true });
  if (policy) {
    // The engine's probe directory holds THIS probe only: an earlier full probe's screenshot or summary must never
    // survive into a structure-only one.
    for (const e of fs.readdirSync(out)) fs.rmSync(path.join(out, e), { recursive: true, force: true });
  }
  const browser = await (await loadChromium()).launch();
  const results = [];
  try {
    const context = await browser.newContext({ viewport, serviceWorkers: "block" });
    let blocked;
    if (policy) {
      // The probe's page IS the app frame here: its own navigations stay under the launch path.
      ({ blocked } = await armPolicy(context, policy, { navOf: (f) => (f && f.parentFrame() === null ? "app" : null) }));
    } else {
      blocked = await armGuard(context, {});
    }
    const page = await context.newPage();
    // What the recorder would refuse, the probe refuses too: a frame inside the page that fails to load, a popup.
    const frameErrors = [];
    let otherPages = false;
    context.on("page", (p2) => { if (p2 !== page) { otherPages = true; p2.close().catch(() => {}); } });
    page.on("response", (r) => {
      const req = r.request();
      try { if (req.isNavigationRequest() && req.frame() !== page.mainFrame() && r.status() >= 400) frameErrors.push(`${r.status()} ${r.url()}`); } catch { /* no frame */ }
    });
    page.on("requestfailed", (req) => {
      try {
        if (req.isNavigationRequest() && req.frame() !== page.mainFrame() && !/blockedbyclient/i.test(req.failure()?.errorText ?? "")) frameErrors.push(`${req.failure()?.errorText ?? "failed"} ${req.url()}`);
      } catch { /* no frame */ }
    });
    for (const p of paths) {
      const url = base.replace(/\/$/, "") + p;
      const response = await page.goto(url, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
      await page.waitForTimeout(800);
      const slug = slugOf(p);
      if (!structureOnly) await page.screenshot({ path: path.join(out, `${slug}.png`), fullPage: true });
      const info = await page.evaluate(SUMMARISE, structureOnly);
      // An app often renders inside a frame of its own page (a crew app does, in its editor frame): each nested
      // frame is summarised too, so a storyline can target what it shows (`"in": "content"`).
      const frames = [];
      for (const f of page.frames()) {
        if (f === page.mainFrame()) continue;
        try {
          frames.push({ path: new URL(f.url()).pathname, ...(await f.evaluate(SUMMARISE, structureOnly)) });
        } catch { /* a frame that went away or refuses evaluation */ }
      }
      if (frames.length) info.frames = frames.slice(0, 5);
      // A crew app is filmed in its own frame only (DES-DEMO-RECORD-001 §13 A1.2): say so where the storyline is written from.
      if (policy?.target?.kind === "crew_app") info.filmed = 'only frames[0] (the app\'s own frame) is filmed; the page around it is hidden, so every target is "in": "content"';
      fs.writeFileSync(path.join(out, `${slug}.json`), JSON.stringify(info, null, 2));
      results.push({ path: p, slug, info, blocked: [...blocked], status: response?.status() ?? null, finalUrl: page.url(), frameErrors: [...frameErrors], otherPages });
    }
  } finally {
    await browser.close().catch(() => {});
  }
  return results;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const argv = process.argv.slice(2);
  const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : dflt; };
  const positional = argv.filter((a, i) => !a.startsWith("--") && !(i > 0 && argv[i - 1].startsWith("--")));
  const [base, ...paths] = positional;
  if (!base || !paths.length) {
    console.error("usage: wicked-garden run scripts/demo/probe.mjs <baseUrl> <path> [path ...] [--out <dir>] [--width 1600] [--height 862]");
    process.exit(2);
  }
  const out = path.resolve(opt("--out", "probe-out"));
  // 1600x862 is the app viewport inside the recording stage's window (1600x900 minus the 38 px title bar).
  const viewport = { width: Number(opt("--width", 1600)), height: Number(opt("--height", 862)) };
  for (const r of await probePages({ base, paths, out, viewport })) {
    console.log(`\n=== ${r.path}  (${r.info.title})  screenshot: ${path.join(out, `${r.slug}.png`)}`);
    for (const [k, v] of Object.entries(r.info)) if (Array.isArray(v)) console.log(`${k} (${v.length}):\n  ${v.slice(0, 30).join("\n  ")}${v.length > 30 ? "\n  ..." : ""}`);
    if (r.blocked.length) console.log(`blocked (${r.blocked.length}): ${r.blocked.slice(0, 5).join("; ")}`);
  }
}
