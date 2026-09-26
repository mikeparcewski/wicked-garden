#!/usr/bin/env node
// Records a captioned product demo as independent segments and stitches them into one MP4 with chapters
// (part of the demo-video-recording skill; see references/storyline-api.md).
//
//   node record.mjs <storyline.mjs> [segment-key ...] [--all | --stitch | --reencode | --list] [--out <dir>] [--keep-closing]
//
// Each non-intro segment opens on its own chapter slide (the storyline's beforeSegment hook runs behind it) and ends
// on the plain stage background, so segments join with a clean cut. Frames and timelines are kept per segment, so a
// segment can be re-recorded alone and the whole video re-encoded without recording again.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { Stage } from "./stage.mjs";
import { buildVideo } from "./postprocess.mjs";

const FFMPEG = process.env.FFMPEG || "ffmpeg";
const FFPROBE = FFMPEG.replace(/ffmpeg(\.exe)?$/i, "ffprobe$1");

function usage(msg) {
  if (msg) console.error(`error: ${msg}\n`);
  console.error("usage: node record.mjs <storyline.mjs> [segment-key ...] [--all | --stitch | --reencode | --list] [--out <dir>]");
  process.exit(2);
}

// ---------------------------------------------------------------------------------------------------------------- args
const argv = process.argv.slice(2);
const flags = new Set(argv.filter((a) => a.startsWith("--") && a !== "--out"));
const outIdx = argv.indexOf("--out");
const positional = argv.filter((a, i) => !a.startsWith("--") && !(outIdx >= 0 && i === outIdx + 1));
const storyPath = positional[0] ? path.resolve(positional[0]) : usage("missing storyline path");
if (!fs.existsSync(storyPath)) usage(`storyline not found: ${storyPath}`);
const named = positional.slice(1);

const story = (await import(pathToFileURL(storyPath).href)).default;
if (!story?.segments?.length) usage("the storyline's default export needs a non-empty `segments` array");
const storyDir = path.dirname(storyPath);
const OUT = path.resolve(outIdx >= 0 ? argv[outIdx + 1] : path.join(storyDir, "demo-video"));
const SEG_DIR = path.join(OUT, "segments");
const slug = (story.title || "demo").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "demo";
const FINAL = path.join(OUT, `${slug}.mp4`);
const BASE = process.env.DEMO_BASE_URL || story.baseUrl;
if (!BASE) usage("the storyline needs a baseUrl (or set DEMO_BASE_URL)");
const brand = {
  name: story.brand?.name ?? story.title ?? "Demo",
  accent: story.brand?.accent ?? "#ee0000",
  logoSvg: story.brand?.logo ? fs.readFileSync(path.resolve(storyDir, story.brand.logo), "utf8") : "",
};
const SEGMENTS = story.segments;
for (const s of SEGMENTS) if (!/^[a-z0-9][a-z0-9-]*$/.test(s.key ?? "")) usage(`segment key must be lowercase letters, digits and hyphens: ${s.key}`);
const CHAPTERS = SEGMENTS.filter((s) => !s.intro).map((s) => s.title);
const LAST = SEGMENTS[SEGMENTS.length - 1].key;

const segDir = (key) => path.join(SEG_DIR, key);
const segVideo = (key) => path.join(segDir(key), "segment.mp4");
const readTimings = (key) => { try { return JSON.parse(fs.readFileSync(path.join(segDir(key), "timings.json"), "utf8")); } catch { return {}; } };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// ---------------------------------------------------------------------------------------------------------------- ctx
function makeCtx(stage, timings) {
  const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return {
    stage,
    timings,
    get app() { return stage.app; },
    get page() { return stage.page; },
    go: (p) => stage.go(p),
    caption: (kicker, title, body, readMs) => stage.caption(kicker, title, body ?? "", readMs),
    point: (locator, label, opts) => stage.point(locator, label, opts),
    unpoint: () => stage.unpoint(),
    click: (locator, opts) => stage.click(locator, opts),
    type: (locator, text, opts) => stage.type(locator, text, opts),
    fast: (label, factor, fn) => stage.fast(label, factor, fn),
    card: (html, ms) => stage.card(html, ms),
    uncard: () => stage.uncard(),
    hold: (ms) => stage.hold(ms),
    hideCursor: () => stage.hideCursor(),
    /** A response from the app whose URL matches (any method unless given). Register it before the click that causes it. */
    waitForResponse: (re, { method, timeout = 300_000 } = {}) =>
      stage.page.waitForResponse((r) => re.test(r.url()) && (!method || r.request().method() === method.toUpperCase()), { timeout }),
    waitForPost: (re, timeout = 300_000) => stage.page.waitForResponse((r) => re.test(r.url()) && r.request().method() === "POST", { timeout }),
    /** Wait for the app's URL (client-side routing changes it without a page load; network idle is not enough). */
    waitForPath: (re, timeout = 30_000) => stage.appFrame.waitForURL((u) => re.test(new URL(u).pathname + new URL(u).search), { timeout }),
    /** Wait until the element is on screen (e.g. results replacing loading placeholders). */
    waitVisible: (locator, timeout = 60_000) => locator.first().waitFor({ state: "visible", timeout }),
    async time(label, fn) {
      const t0 = Date.now();
      try { return await fn(); } finally { timings[label] = Math.round((Date.now() - t0) / 100) / 10; }
    },
    // The innermost <section> containing a heading named `title` (a trailing count badge is fine), else the innermost
    // <section> containing that exact text. Matches outside any <section> (sidebar links, breadcrumbs) never count.
    section(title) {
      const app = stage.app;
      const innermost = (inner) => app.locator("section").filter({ has: inner }).filter({ hasNot: app.locator("section").filter({ has: inner }) });
      const heading = app.getByRole("heading", { name: new RegExp(`^${reEsc(title)}(\\s*\\d+)?$`) });
      return innermost(heading).or(innermost(app.getByText(title, { exact: true }))).first();
    },
    button: (re) => stage.app.locator("button").filter({ hasText: re }),
  };
}

// ---------------------------------------------------------------------------------------------------------------- record
async function recordSegment(seg) {
  const n = CHAPTERS.indexOf(seg.title);
  console.log(`● ${seg.key}`);
  const stage = new Stage({ baseUrl: BASE, outDir: segDir(seg.key), chapters: CHAPTERS, brand, stickyOffset: story.stickyOffset,
    headful: process.env.DEMO_HEADFUL === "1", locale: story.locale, timezoneId: story.timezoneId });
  const timings = {};
  const ctx = makeCtx(stage, timings);
  await stage.open(story.startPath || "/");
  try {
    if (seg.intro) {
      await seg.run(ctx);
    } else {
      // Opening slide first; set-up (resets, log-in, persona) happens behind it.
      await stage.card(`<div class="seg"><div class="num">${String(n + 1).padStart(2, "0")}</div><div>
<div class="of">Chapter ${n + 1} of ${CHAPTERS.length}</div><h1>${esc(seg.title)}</h1>${seg.blurb ? `<p>${esc(seg.blurb)}</p>` : ""}
<div class="meta">${(seg.tags ?? []).map((x) => `<b>${esc(x)}</b>`).join("")}</div></div></div>`, 600);
      const t0 = Date.now();
      if (story.beforeSegment) await story.beforeSegment(ctx, seg);
      await stage.go(story.startPath || "/");
      await stage.hold(Math.max(1200, 4200 - (Date.now() - t0))); // the slide stays readable for ~4 s
      await stage.chapter(n);
      await stage.uncard();
      await seg.run(ctx);
      await stage.hideCursor();
      await stage.hold(600);
    }
    if (seg.key === LAST && story.closing) {
      const all = Object.fromEntries(SEGMENTS.map((s) => [s.key, s.key === seg.key ? timings : readTimings(s.key)]));
      await stage.hideCursor();
      await stage.card(story.closing(all), story.closingMs ?? 10_000);
    } else if (!seg.intro) {
      await stage.card("", 1100); // end on the plain background: the next chapter slide cuts in cleanly
    }
  } finally {
    await stage.close();
  }
  const tl = JSON.parse(fs.readFileSync(path.join(segDir(seg.key), "timeline.json"), "utf8"));
  fs.writeFileSync(path.join(segDir(seg.key), "timeline.json"), JSON.stringify({ ...tl, title: story.title }, null, 1));
  fs.writeFileSync(path.join(segDir(seg.key), "timings.json"), JSON.stringify(timings, null, 2));
  // Trim the set-up behind the opening slide: the segment starts on the slide, fully faded in.
  const r = buildVideo(segDir(seg.key), segVideo(seg.key), { trimStart: 0.9, ffmpeg: FFMPEG });
  console.log(`  ${seg.key}: ${r.seconds.toFixed(1)} s${Object.keys(timings).length ? " " + JSON.stringify(timings) : ""}`);
}

// ---------------------------------------------------------------------------------------------------------------- stitch
function probeSeconds(file) {
  const r = spawnSync(FFPROBE, ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`ffprobe failed on ${file}: ${r.stderr}`);
  return Number(r.stdout.trim());
}

function stitch() {
  const segs = SEGMENTS.filter((s) => fs.existsSync(segVideo(s.key)));
  const missing = SEGMENTS.filter((s) => !fs.existsSync(segVideo(s.key))).map((s) => s.key);
  if (!segs.length) throw new Error("no segments recorded yet");
  const list = path.join(SEG_DIR, "concat.txt");
  fs.writeFileSync(list, segs.map((s) => `file '${segVideo(s.key).replace(/\\/g, "/").replace(/'/g, "'\\''")}'`).join("\n") + "\n");
  let at = 0;
  const meta = [";FFMETADATA1", `title=${(story.title || "Demo").replace(/[=;#\\\n]/g, " ")}`];
  const rows = ["| Time | Chapter |", "|---|---|"];
  for (const s of segs) {
    const d = probeSeconds(segVideo(s.key));
    const title = s.intro ? "Introduction" : s.title;
    meta.push("[CHAPTER]", "TIMEBASE=1/1000", `START=${Math.round(at * 1000)}`, `END=${Math.round((at + d) * 1000)}`, `title=${title.replace(/[=;#\\\n]/g, " ")}`);
    rows.push(`| ${Math.floor(at / 60)}:${String(Math.floor(at % 60)).padStart(2, "0")} | ${title} |`);
    at += d;
  }
  fs.writeFileSync(path.join(SEG_DIR, "chapters.ffmeta"), meta.join("\n") + "\n");
  // Segments share codec, size and frame rate, so they join without re-encoding.
  const r = spawnSync(FFMPEG, ["-y", "-f", "concat", "-safe", "0", "-i", list, "-i", path.join(SEG_DIR, "chapters.ffmeta"), "-map", "0", "-map_metadata", "1",
    "-map_chapters", "1", "-map", "-0:d", "-c", "copy", "-movflags", "+faststart", FINAL], { stdio: ["ignore", "ignore", "pipe"] });
  if (r.status !== 0) throw new Error(`stitch failed: ${r.stderr?.toString().slice(-1500)}`);
  fs.writeFileSync(path.join(OUT, "chapters.md"), rows.join("\n") + "\n");
  fs.writeFileSync(path.join(OUT, "timings.json"), JSON.stringify(Object.fromEntries(SEGMENTS.map((s) => [s.key, readTimings(s.key)])), null, 2));
  console.log(`stitched ${segs.length} segments -> ${FINAL} (${Math.round(at)} s)${missing.length ? `; missing: ${missing.join(", ")}` : ""}`);
}

// ---------------------------------------------------------------------------------------------------------------- main
fs.mkdirSync(SEG_DIR, { recursive: true });
const ffCheck = spawnSync(FFMPEG, ["-version"], { stdio: "ignore" });
if (ffCheck.error || ffCheck.status !== 0) usage(`ffmpeg not found (${FFMPEG}); install it or set FFMPEG=/path/to/ffmpeg`);

if (flags.has("--list")) {
  for (const s of SEGMENTS) console.log(`${fs.existsSync(segVideo(s.key)) ? "recorded" : "missing "}  ${s.key}  ${s.intro ? "(intro)" : s.title}`);
  process.exit(0);
}
if (flags.has("--reencode")) {
  for (const s of SEGMENTS.filter((x) => fs.existsSync(path.join(segDir(x.key), "timeline.json")))) {
    const r = buildVideo(segDir(s.key), segVideo(s.key), { trimStart: 0.9, ffmpeg: FFMPEG });
    console.log(`  ${s.key}: ${r.seconds.toFixed(1)} s`);
  }
} else if (!flags.has("--stitch")) {
  const unknown = named.filter((k) => !SEGMENTS.some((s) => s.key === k));
  if (unknown.length) usage(`unknown segment(s): ${unknown.join(", ")} (see --list)`);
  const todo = SEGMENTS.filter((s) => (named.length ? named.includes(s.key) : flags.has("--all") || !fs.existsSync(segVideo(s.key))));
  // The closing card is baked into the last segment and summarises every segment's timings: whenever another segment
  // is re-recorded, re-record the last one too (it is normally a short wrap-up), so the card never shows stale numbers.
  if (story.closing && todo.length && !todo.some((s) => s.key === LAST) && !flags.has("--keep-closing")) {
    console.log(`note: also re-recording ${LAST} so the closing card reflects the new timings (--keep-closing to skip)`);
    todo.push(SEGMENTS.find((s) => s.key === LAST));
  }
  // The last segment carries the closing card: record it last.
  todo.sort((a, b) => (a.key === LAST) - (b.key === LAST));
  for (const seg of todo) await recordSegment(seg);
}
stitch();
