#!/usr/bin/env node
// The engine-run demo recorder (DES-DEMO-RECORD-001, wicked-core#1249): the fixed command of the `demo_probe` and
// `demo_record` catalog Tools.
//
//   wicked-garden run scripts/demo/demo-record.mjs probe
//   wicked-garden run scripts/demo/demo-record.mjs record
//
// The engine runs it on the host, in its OS jail (writes only to the demo root's tool directories and a private temp
// dir; network to ONE loopback port, the app's), with a cleared environment:
//
//   WICKED_DEMO_JAIL            the launcher kind; without it nothing records (INCONCLUSIVE / unjailed_host)
//   WICKED_DEMO_ROOT            the demo root; probe writes probe/, record writes demo-video/ and review/
//   WICKED_DEMO_APP_ORIGIN      the app's loopback origin, from the URL the person typed at launch
//   WICKED_DEMO_LAUNCH_PATH     that URL's path (and query): every navigation the storyline makes stays under it
//   WICKED_DEMO_TARGET          {"kind":"crew_app","id":"<app>"} or {"kind":"loopback_app"}, decided by crew
//   WICKED_DEMO_LIVE_DATA_TO_MODELS  "0" when this app's rows may not reach a model: the probe reads structure only,
//                               and no failure message carries page text
//   WICKED_DEMO_STORYLINE       (record) the approved snapshot dir: storyline.json + chapters.json
//   FFMPEG, PYTHON, WICKED_DEMO_DEPS, PLAYWRIGHT_BROWSERS_PATH   the host's tools, resolved by the engine
//
// It never installs anything. It always exits 0 once it has written its verdict file (probe/result.json,
// demo-video/record.json): `overall` PASS, FAIL or INCONCLUSIVE, with a `cause`. A cause in REFUSAL_CAUSES says the
// host could not record (the engine offers a retry); any other non-PASS cause is a verdict on the take (the engine
// sends it back to the plan step). Exit 2 is a usage error.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { DEPS_DIR, loadChromium } from "./_playwright.mjs";
import { demoPolicy } from "./readonly.mjs";
import { parseStoryline, compileStoryline } from "./storyline-data.mjs";
import { makeSegmentRecorder, stitchParts, SEGMENT_TRIM_START } from "./record.mjs";
import { ffprobeOf, videoClock } from "./postprocess.mjs";
import { fetchVideoPalette } from "./palette.mjs";
import { probePages } from "./probe.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const FINAL = "demo.mp4";

/** Causes that are refusals (the host could not record: the engine offers a retry). Every other non-PASS cause is a
 *  verdict on the storyline's take (send-back to the plan). The engine keeps its own copy of this list. */
export const REFUSAL_CAUSES = Object.freeze([
  "unjailed_host", "recorder_deps_missing", "engine_refused", "app_unreachable", "encoder_failed", "capture_stalled",
]);

const INSTALL = {
  ffmpeg: "install ffmpeg on the daemon host (brew install ffmpeg / apt install ffmpeg), or set WICKED_FFMPEG to its path",
  ffprobe: "install ffprobe beside ffmpeg (it ships with ffmpeg)",
  python3: "install Python 3.8 or newer on the daemon host",
  playwright: "run once on the daemon host: wicked-garden run scripts/demo/setup.mjs",
  chromium: "run once on the daemon host: wicked-garden run scripts/demo/setup.mjs (it installs Playwright's Chromium)",
};

/** The first line of an error, trimmed; with `redact`, only its code (a page's text never reaches a model). */
function said(e, redact = false) {
  const code = e?.code ?? null;
  // A step's name is the storyline's own words (never the page's): it stays when the failure is redacted.
  if (redact) return `${code ?? "the step failed"}${typeof e?.step === "string" ? ` at ${e.step}` : ""}`;
  return String(e?.message ?? e).split("\n")[0].slice(0, 300);
}

/** Which of the host tools the recorder needs are missing: `[{tool, detail, install}]`. */
export async function missingDeps({ env = process.env, needVideo = true } = {}) {
  const out = [];
  const ok = (cmd, args) => {
    const r = spawnSync(cmd, args, { stdio: "ignore", timeout: 20_000 });
    return !r.error && r.status === 0;
  };
  if (needVideo) {
    const ffmpeg = env.FFMPEG || "ffmpeg";
    if (!ok(ffmpeg, ["-version"])) out.push({ tool: "ffmpeg", detail: ffmpeg, install: INSTALL.ffmpeg });
    else if (!ok(ffprobeOf(ffmpeg), ["-version"])) out.push({ tool: "ffprobe", detail: ffprobeOf(ffmpeg), install: INSTALL.ffprobe });
    const py = env.PYTHON || "python3";
    if (!ok(py, ["-c", "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"])) out.push({ tool: "python3", detail: py, install: INSTALL.python3 });
  }
  try {
    createRequire(path.join(DEPS_DIR, "package.json")).resolve("playwright");
  } catch {
    out.push({ tool: "playwright", detail: DEPS_DIR, install: INSTALL.playwright });
    return out;
  }
  // The package without its browser (or a Playwright too old for the socket policy) is missing too.
  try {
    const chromium = await loadChromium();
    const b = await chromium.launch({ headless: true });
    const ctx = await b.newContext();
    const hasWs = typeof ctx.routeWebSocket === "function";
    await b.close();
    if (!hasWs) out.push({ tool: "playwright", detail: "needs 1.48 or newer (routeWebSocket)", install: INSTALL.playwright });
  } catch (e) {
    out.push({ tool: "chromium", detail: said(e), install: INSTALL.chromium });
  }
  return out;
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2) + "\n");
  fs.renameSync(tmp, file);
}

/** The engine's values, checked: `{root, policy, liveDataToModels, jail}`; throws with a reason. */
export function readEnv(env = process.env) {
  const root = env.WICKED_DEMO_ROOT;
  if (!root || !path.isAbsolute(root)) throw new Error("WICKED_DEMO_ROOT must be an absolute directory");
  let target;
  try { target = JSON.parse(env.WICKED_DEMO_TARGET || '{"kind":"loopback_app"}'); } catch { throw new Error("WICKED_DEMO_TARGET is not JSON"); }
  const policy = demoPolicy({ appOrigin: env.WICKED_DEMO_APP_ORIGIN, launchPath: env.WICKED_DEMO_LAUNCH_PATH, target });
  return { root, policy, liveDataToModels: env.WICKED_DEMO_LIVE_DATA_TO_MODELS !== "0", jail: env.WICKED_DEMO_JAIL || null };
}

/** One GET of the exact launch URL, following no redirect: `null` when it answered 2xx, else why not. */
export async function appUnreachable(policy, { timeoutMs = 15_000 } = {}) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(policy.appOrigin + policy.launchUrl, { redirect: "manual", signal: ctl.signal });
    await r.body?.cancel().catch(() => {});
    if (r.status >= 200 && r.status < 300) return null;
    return `GET ${policy.launchUrl} answered ${r.status}${r.status >= 300 && r.status < 400 ? " (a redirect: launch the URL it redirects to)" : ""}`;
  } catch (e) {
    return `GET ${policy.appOrigin}${policy.launchUrl} failed: ${String(e?.cause?.code ?? e?.message ?? e)}`;
  } finally {
    clearTimeout(timer);
  }
}

function ffprobeJson(ffprobe, file) {
  const r = spawnSync(ffprobe, ["-v", "error", "-show_format", "-show_streams", "-show_chapters", "-of", "json", file], { encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  if (r.status !== 0) throw Object.assign(new Error(`ffprobe failed on ${path.basename(file)}: ${(r.stderr ?? "").slice(-300)}`), { code: "encoder_failed" });
  const j = JSON.parse(r.stdout);
  const v = (j.streams ?? []).find((s) => s.codec_type === "video") ?? null;
  return {
    codec: v?.codec_name ?? null, width: v?.width ?? null, height: v?.height ?? null,
    duration: Number(j.format?.duration ?? 0),
    chapters: (j.chapters ?? []).map((c) => ({ title: c.tags?.title ?? "", start: Number(c.start_time), end: Number(c.end_time) })),
  };
}

function segmentSeconds(ffprobe, file) {
  const r = spawnSync(ffprobe, ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" });
  return r.status === 0 ? Number(r.stdout.trim()) : 0;
}

const round1 = (x) => Math.round(x * 10) / 10;

/**
 * Each part's checkpoints on the final video's clock: `[{key, start, ready_at, checkpoints: [{kind, at, picture_at}]}]`.
 * `at` is where the checkpoint fell; `picture_at` where its proving picture did (the moment worth looking at).
 */
export function partClock(parts, ffprobe) {
  const out = [];
  let offset = 0;
  for (const p of parts) {
    let tl = null;
    try { tl = JSON.parse(fs.readFileSync(path.join(p.dir, "timeline.json"), "utf8")); } catch { /* no timeline */ }
    const entry = { key: p.key, start: round1(offset), ready_at: null, checkpoints: [], ...takeNotes(tl, offset) };
    if (tl) {
      const clock = videoClock(tl, SEGMENT_TRIM_START);
      for (const c of tl.marks?.checkpoints ?? []) {
        const at = round1(offset + clock.outAt(c.t));
        const pictureAt = round1(offset + clock.outAt(Math.max(c.t, c.pictureAt ?? c.t)));
        entry.checkpoints.push({ kind: c.kind, at, picture_at: pictureAt });
        if (c.kind === "ready" && entry.ready_at === null) entry.ready_at = pictureAt;
      }
    }
    out.push(entry);
    offset += segmentSeconds(ffprobe, p.file);
  }
  return out;
}

/**
 * What a take left out, said in its record (§13 A1): the optional steps it skipped (`at` on the video's clock, from
 * `offset`) and the card time it cut while the app got ready. A timeline that cannot be read says nothing.
 */
export function takeNotes(tl, offset = 0) {
  if (!tl) return { skipped_steps: [], load_cut_s: 0 };
  let clock = null;
  try { clock = videoClock(tl, SEGMENT_TRIM_START); } catch { /* nothing recorded past the trim */ }
  return {
    skipped_steps: (tl.marks?.skipped ?? []).map((x) => ({
      step: x.step ?? null, verb: x.verb ?? null, what: x.what ?? null, reason: x.reason ?? null,
      at: clock ? round1(offset + clock.outAt(x.t)) : null,
    })),
    load_cut_s: round1((tl.marks?.speed ?? []).filter((x) => x.cut).reduce((n, x) => n + Math.max(0, x.end - x.start), 0)),
  };
}

const readJson = (file) => { try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return null; } };

/** The chapters sheet's moments: per chapter, the app once its card is gone, at `ready`, and after its last action. */
export function sheetMoments(clock) {
  // Every chapter gets its `ready` moment (the app, proven on screen) and its last action's: at most two
  // per chapter, so twelve chapters still fit one sheet. The moment is the proving picture itself.
  const m = [];
  for (const c of clock) {
    const cps = c.checkpoints.filter((x) => x.kind !== "end");
    const ready = cps.find((x) => x.kind === "ready") ?? cps.find((x) => x.kind === "chapter");
    // The state the chapter ends on (its `done` checkpoint), else its last action.
    const last = cps.find((x) => x.kind === "done") ?? (cps.length ? cps[cps.length - 1] : null);
    for (const x of [ready, last !== ready ? last : null]) if (x) m.push(round1(x.picture_at + 0.05));
  }
  return [...new Set(m)].sort((a, b) => a - b);
}

function contactSheet(python, ffmpeg, video, args, out) {
  const r = spawnSync(python, [path.join(HERE, "contact_sheet.py"), video, ...args, "--out", out],
    { encoding: "utf8", env: { ...process.env, FFMPEG: ffmpeg }, timeout: 300_000 });
  if (r.status !== 0 || !fs.existsSync(out)) {
    throw Object.assign(new Error(`contact_sheet.py ${args.join(" ")} failed: ${(r.stderr || r.stdout || "").trim().slice(-300)}`), { code: "encoder_failed" });
  }
}

// ---- probe ---------------------------------------------------------------------------------------------------

export async function runProbe(env = process.env) {
  let cfg;
  const fallbackRoot = env.WICKED_DEMO_ROOT && path.isAbsolute(env.WICKED_DEMO_ROOT) ? env.WICKED_DEMO_ROOT : null;
  // This probe's directory holds this probe only, from the very first return: an earlier probe's screenshot or
  // summary never survives a refusal below (the plan seat would read it as current).
  if (fallbackRoot !== null) {
    const probeDir = path.join(fallbackRoot, "probe");
    if (fs.existsSync(probeDir)) for (const e of fs.readdirSync(probeDir)) fs.rmSync(path.join(probeDir, e), { recursive: true, force: true });
  }
  const result = (root, v) => { if (root) writeJson(path.join(root, "probe", "result.json"), v); return v; };
  try { cfg = readEnv(env); } catch (e) {
    return result(fallbackRoot, { overall: "INCONCLUSIVE", cause: "engine_refused", reason: said(e) });
  }
  const redact = !cfg.liveDataToModels;
  if (!cfg.jail) return result(cfg.root, { overall: "INCONCLUSIVE", cause: "unjailed_host", reason: "the probe runs only inside the engine's jail (WICKED_DEMO_JAIL is unset)" });
  const missing = await missingDeps({ env, needVideo: false });
  if (missing.length) return result(cfg.root, { overall: "INCONCLUSIVE", cause: "recorder_deps_missing", reason: missing.map((m) => `${m.tool}: ${m.install}`).join("; "), missing });
  const down = await appUnreachable(cfg.policy);
  if (down) return result(cfg.root, { overall: "INCONCLUSIVE", cause: "app_unreachable", reason: down });
  let r;
  try {
    [r] = await probePages({
      base: cfg.policy.appOrigin, paths: [cfg.policy.launchUrl], out: path.join(cfg.root, "probe"),
      policy: cfg.policy, structureOnly: redact,
    });
  } catch (e) {
    return result(cfg.root, { overall: "INCONCLUSIVE", cause: "app_unreachable", reason: said(e, redact) });
  }
  // A page that answered an error, left the launch path, or tried a request the policy refuses is not a probe the
  // plan should write from (and the recorder would meet the same).
  let finalPath = null;
  try { finalPath = new URL(r.finalUrl).pathname; } catch { /* about: or worse */ }
  const problems = [];
  if (r.status === null || r.status < 200 || r.status >= 300) problems.push(`the page answered ${r.status ?? "nothing"}`);
  if (r.frameErrors.length) problems.push(`a frame inside the page did not load (${redact ? "redacted" : r.frameErrors.slice(0, 3).join("; ")})`);
  if (r.otherPages) problems.push("the page opened another page");
  if (finalPath === null || !(finalPath === cfg.policy.launchPath || finalPath.startsWith(cfg.policy.launchPath === "/" ? "/" : cfg.policy.launchPath + "/"))) {
    problems.push("the page left the launch path");
  }
  if (r.blocked.length) problems.push(`${r.blocked.length} request(s) the recorder refuses (${redact ? "redacted" : r.blocked.slice(0, 3).join("; ")})`);
  if (problems.length) return result(cfg.root, { overall: "INCONCLUSIVE", cause: "app_unreachable", reason: problems.join("; ") });
  return result(cfg.root, {
    overall: "PASS", launch_path: cfg.policy.launchUrl, structure_only: redact, page: `${r.slug}.json`,
    // What the recorder will film (§13 A1.2): a crew app's own frame only, so the storyline targets it alone.
    ...(cfg.policy.target.kind === "crew_app" ? {
      recorded_view: "app_frame",
      note: 'The video shows only the app\'s own frame (the page summary\'s first frame); studio\'s page around it is hidden. Every target, `ready` included, is `"in": "content"`.',
    } : { recorded_view: "page" }),
  });
}

// ---- record --------------------------------------------------------------------------------------------------

export async function runRecord(env = process.env) {
  const fallbackRoot = env.WICKED_DEMO_ROOT && path.isAbsolute(env.WICKED_DEMO_ROOT) ? env.WICKED_DEMO_ROOT : null;
  const recordFile = (root) => path.join(root, "demo-video", "record.json");
  let cfg;
  try { cfg = readEnv(env); } catch (e) {
    const v = { overall: "INCONCLUSIVE", cause: "engine_refused", reason: said(e), chapters: [] };
    if (fallbackRoot) writeJson(recordFile(fallbackRoot), v);
    return v;
  }
  const redact = !cfg.liveDataToModels;
  const base = { app_origin: cfg.policy.appOrigin, launch_path: cfg.policy.launchUrl, target: cfg.policy.target.kind, jail: cfg.jail };
  const done = (v) => {
    const out = { ...base, ...v };
    if (out.overall !== "PASS" && !REFUSAL_CAUSES.includes(out.cause) && out.overall === "INCONCLUSIVE") out.overall = "FAIL";
    writeJson(recordFile(cfg.root), out);
    return out;
  };
  if (!cfg.jail) return done({ overall: "INCONCLUSIVE", cause: "unjailed_host", reason: "the recorder runs only inside the engine's jail (WICKED_DEMO_JAIL is unset)", chapters: [] });
  const missing = await missingDeps({ env });
  if (missing.length) {
    return done({ overall: "INCONCLUSIVE", cause: "recorder_deps_missing", reason: missing.map((m) => `${m.tool}: ${m.install}`).join("; "), missing, chapters: [] });
  }
  const ffmpeg = env.FFMPEG || "ffmpeg";
  const ffprobe = ffprobeOf(ffmpeg);
  const python = env.PYTHON || "python3";

  // The approved snapshot (never the live plan files). The engine owns the directory; the files are the plan's.
  const snap = env.WICKED_DEMO_STORYLINE;
  if (!snap || !path.isAbsolute(snap) || !fs.statSync(snap, { throwIfNoEntry: false })?.isDirectory()) {
    return done({ overall: "INCONCLUSIVE", cause: "engine_refused", reason: "WICKED_DEMO_STORYLINE must name the approved snapshot directory", chapters: [] });
  }
  let checked;
  let storylineSha = null;
  try {
    const read = (name) => {
      try { return fs.readFileSync(path.join(snap, name), "utf8"); } catch {
        throw Object.assign(new Error(`${name}: the approved plan has none`), { code: "storyline_refused" });
      }
    };
    const storyText = read("storyline.json");
    const chaptersText = read("chapters.json");
    storylineSha = crypto.createHash("sha256").update(storyText).digest("hex");
    // A crew app is recorded in its own frame only, so each of its targets is `in: "content"` (§13 A1.2).
    checked = parseStoryline(storyText, chaptersText, {
      appOrigin: cfg.policy.appOrigin, launchPath: cfg.policy.launchUrl, contentOnly: cfg.policy.target.kind === "crew_app",
    });
  } catch (e) {
    return done({ overall: "FAIL", cause: "storyline_refused", reason: said(e), storyline_sha: storylineSha, chapters: [] });
  }
  const down = await appUnreachable(cfg.policy);
  if (down) return done({ overall: "INCONCLUSIVE", cause: "app_unreachable", reason: down, storyline_sha: storylineSha, chapters: [] });

  const story = compileStoryline(checked, { launchPath: cfg.policy.launchUrl });
  const outDir = path.join(cfg.root, "demo-video");
  const segDir = path.join(outDir, "segments");
  const reviewDir = path.join(cfg.root, "review");
  fs.mkdirSync(segDir, { recursive: true });
  fs.mkdirSync(reviewDir, { recursive: true });
  const skin = await fetchVideoPalette({ env });
  const recordSegment = makeSegmentRecorder({
    story, baseUrl: cfg.policy.appOrigin, ffmpeg, palette: skin.palette, segmentsDir: segDir, policy: cfg.policy,
    brand: { name: story.brand?.name ?? story.title ?? "Demo", accent: story.brand?.accent ?? null, logoSvg: "" },
    // A test seam, honoured only under the tests' own jail marker (the engine sets the launcher kind).
    dropPicturesAfterFirst: cfg.jail === "test" && env.WICKED_DEMO_TEST_DROP_PICTURES === "1",
    redactFailures: redact,
  });
  const chapters = [];
  for (const seg of story.segments) {
    try {
      await recordSegment(seg);
      chapters.push({ key: seg.key, title: seg.intro ? "Introduction" : seg.title, status: "ok" });
    } catch (e) {
      const code = e.code ?? "step_failed";
      let failedAt = null;
      const g = readJson(path.join(segDir, seg.key, "guard.json"));
      if (g) failedAt = readJson(path.join(segDir, seg.key, `failed-${g.take}`, "failure.json"))?.failed_at_sec ?? null;
      chapters.push({ key: seg.key, title: seg.intro ? "Introduction" : seg.title, status: "failed", code, failed_at_sec: failedAt, message: said(e, redact) });
      // A failed take discloses its cuts and skips too, each chapter on its own take's clock (nothing was stitched).
      const notes = chapters.map((c) => {
        const take = c.status === "failed" && g ? path.join(segDir, c.key, `failed-${g.take}`) : path.join(segDir, c.key);
        return { ...c, ...takeNotes(readJson(path.join(take, "timeline.json"))) };
      });
      return done({
        overall: REFUSAL_CAUSES.includes(code) ? "INCONCLUSIVE" : "FAIL", cause: code, reason: `chapter ${seg.key}: ${said(e, redact)}`,
        storyline_sha: storylineSha, chapters: notes, clock: "take",
      });
    }
  }

  // Stitch, sheets, probe.
  const segVideo = (k) => path.join(segDir, k, "segment.mp4");
  const parts = story.segments.map((s) => ({ title: s.intro ? "Introduction" : s.title, file: segVideo(s.key), key: s.key, intro: !!s.intro, dir: path.join(segDir, s.key) }));
  let ff;
  let clock;
  try {
    const { rows } = stitchParts(parts, path.join(outDir, FINAL), { ffmpeg, title: story.title || "Demo", workDir: segDir });
    fs.writeFileSync(path.join(outDir, "chapters.md"), rows.join("\n") + "\n");
    const timings = Object.fromEntries(story.segments.map((s) => {
      try { return [s.key, JSON.parse(fs.readFileSync(path.join(segDir, s.key, "timings.json"), "utf8"))]; } catch { return [s.key, {}]; }
    }));
    fs.writeFileSync(path.join(outDir, "timings.json"), JSON.stringify(timings, null, 2));
    const video = path.join(outDir, FINAL);
    clock = partClock(parts, ffprobe);
    const moments = sheetMoments(clock);
    contactSheet(python, ffmpeg, video, moments.length ? ["--at", moments.join(",")] : ["--chapters"], path.join(reviewDir, "chapters.png"));
    // One chapter has no join: its sheet is the opening second instead, so the file the review reads exists.
    contactSheet(python, ffmpeg, video, parts.length > 1 ? ["--joins"] : ["--at", "1"], path.join(reviewDir, "joins.png"));
    contactSheet(python, ffmpeg, video, ["--end"], path.join(reviewDir, "end.png"));
    ff = ffprobeJson(ffprobe, video);
    writeJson(path.join(reviewDir, "ffprobe.json"), ff);
  } catch (e) {
    return done({ overall: "INCONCLUSIVE", cause: "encoder_failed", reason: said(e), storyline_sha: storylineSha, chapters });
  }

  // The verdict, from what the files say. (A blocked request already failed its chapter above, in record.mjs; the
  // guards are read again here so the manifest says what each segment met.)
  const guards = parts.map((p) => { try { return JSON.parse(fs.readFileSync(path.join(p.dir, "guard.json"), "utf8")); } catch { return null; } });
  const blocked = guards.flatMap((g) => g?.blocked ?? []);
  const want = parts.map((p) => p.title);
  const got = ff.chapters.map((c) => c.title);
  const problems = [];
  if (!ff.codec || !ff.width) problems.push("no video stream");
  if (want.length !== got.length || want.some((t, i) => t !== got[i])) problems.push(`the video's chapters [${got.join(" | ")}] are not the approved [${want.join(" | ")}]`);
  if (ff.chapters.some((c) => c.end - c.start < 1)) problems.push("a chapter is shorter than 1 s");
  if (parts.some((p, i) => !p.intro && clock[i].ready_at === null)) problems.push("a chapter never reached its ready checkpoint");
  if (blocked.length) problems.push(`${blocked.length} request(s) blocked`);
  const diagnostics = {
    ws_refused: [...new Set(guards.flatMap((g) => g?.diagnostics?.ws_refused ?? []))],
    ws_frames_dropped: guards.reduce((n, g) => n + (g?.diagnostics?.ws_frames_dropped ?? 0), 0),
  };
  return done({
    overall: problems.length ? "FAIL" : "PASS",
    ...(problems.length ? { cause: "chapter_mismatch", reason: problems.join("; ") } : {}),
    storyline_sha: storylineSha, read_only: blocked.length === 0, blocked: redact ? blocked.map(() => "(redacted)") : blocked,
    // By position, never by title (two chapters may share one).
    chapters: chapters.map((c, i) => ({
      ...c, start: ff.chapters[i]?.start ?? null, end: ff.chapters[i]?.end ?? null, ready_at: clock[i]?.ready_at ?? null, checkpoints: clock[i]?.checkpoints ?? [],
      // A skip's reason is the browser's words, which can quote the page: redacted when live data stays private.
      skipped_steps: (clock[i]?.skipped_steps ?? []).map((x) => (redact ? { ...x, reason: "(redacted)" } : x)),
      load_cut_s: clock[i]?.load_cut_s ?? 0,
    })),
    // A crew app's take fails unless its own frame filled the window at every checkpoint (Stage.requireView).
    view: cfg.policy.target.kind === "crew_app" ? "app_frame" : "page",
    hide_invalid: [...new Set(guards.flatMap((g) => g?.hide_invalid ?? []))],
    ffprobe: ff, diagnostics,
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const action = process.argv[2];
  if (action !== "probe" && action !== "record") {
    process.stderr.write("usage: demo-record.mjs <probe|record>   (run by the engine; see the header)\n");
    process.exit(2);
  }
  const v = action === "probe" ? await runProbe() : await runRecord();
  process.stdout.write(`${action}: ${v.overall}${v.cause ? ` (${v.cause}${v.reason ? `: ${v.reason}` : ""})` : ""}\n`);
  process.exit(0);
}
