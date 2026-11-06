#!/usr/bin/env node
// Records a captioned product demo as independent segments and stitches them into one MP4 with chapters
// (part of the wicked-garden-demo skill; see skills/demo/refs/storyline-api.md).
//
//   wicked-garden run scripts/demo/record.mjs <storyline.mjs> [segment-key ...] [--all | --stitch | --reencode | --list] [--out <dir>]
//       [--fixture-origin <loopback origin>] [--keep-closing]
//
// The browser sends no writes while it records (readonly.mjs), except to the --fixture-origin: a disposable app
// started on a loopback port for this recording. A take that fails keeps its video and failure.json under
// segments/<key>/failed-<take>/ and is never stitched.
//
// Each non-intro segment opens on its own chapter slide (the storyline's beforeSegment hook runs behind it) and ends
// on the plain stage background, so segments join with a clean cut. Each segment keeps its master (capture.mp4,
// encoded live while it recorded) and timeline.json, so a segment can be re-recorded alone and the whole video
// re-cut (--reencode) without recording again. No frame files are written (DEMO_KEEP_FRAMES=1 dumps them for debugging).
import { fetchVideoPalette } from "./palette.mjs";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { Stage } from "./stage.mjs";
import { buildVideo, videoClock, CAPTURE, ffprobeOf, ffmetaValue } from "./postprocess.mjs";
import { fixtureOrigin, sideEffectError } from "./readonly.mjs";

// ---- module-level constants (used by exports) --------------------------------------------------
export const SEGMENT_TRIM_START = 0.9; // the set-up behind the opening slide is trimmed from every take's video
// How long a chapter card stays up while its app loads behind it (ms). A chapter whose app takes longer to get
// ready (DES-DEMO-RECORD-001 §13 A1.1) keeps this much of the card and the rest of the wait is cut: the frames cut
// all show the same card, never the app.
export const CARD_HOLD_MS = 4200;
const CARD_CUT_AFTER_MS = CARD_HOLD_MS - 1200;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// ---- ctx ---------------------------------------------------------------------------------------
export function makeCtx(stage, timings) {
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
    /** The engine-run recorder's checkpoint: still in the app, its document loaded, the capture live (stage.mjs). */
    checkpoint: (kind) => stage.checkpoint(kind),
    /** An optional step that was skipped: marked on the timeline and listed in the take's record. */
    skipped: (entry) => stage.skipped(entry),
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

/** Where `failedAt` (wall clock, seconds) falls in the failed take's video; null when it has no frames or no instant. */
export function failedAtInVideo(dir, failedAt, trimStart = SEGMENT_TRIM_START) {
  if (failedAt === null) return null;
  try {
    const tl = JSON.parse(fs.readFileSync(path.join(dir, "timeline.json"), "utf8"));
    return Math.max(0, Math.round(videoClock(tl, trimStart).outAt(failedAt) * 10) / 10);
  } catch {
    return null;
  }
}

// ---- exported stitch ---------------------------------------------------------------------------
/**
 * Join segment videos (same codec, size and frame rate — every take is cut by buildVideo) into one MP4 with
 * chapter metadata, without re-encoding. `parts` = [{ title, file }] in take order; `workDir` holds the two
 * ffmpeg list files. Returns the `| m:ss | Title |` marker rows (chapters.md) and the total seconds.
 */
export function stitchParts(parts, outFile, { ffmpeg = "ffmpeg", title = "Demo", workDir }) {
  const ffprobe = ffprobeOf(ffmpeg);
  const probeSeconds = (file) => {
    const r = spawnSync(ffprobe, ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" });
    if (r.status !== 0) throw new Error(`ffprobe failed on ${file}: ${r.stderr}`);
    return Number(r.stdout.trim());
  };
  if (!parts.length) throw new Error("no segments recorded yet");
  fs.mkdirSync(workDir, { recursive: true });
  const list = path.join(workDir, "concat.txt");
  fs.writeFileSync(list, parts.map((p) => `file '${p.file.replace(/\\/g, "/").replace(/'/g, "'\\''")}'`).join("\n") + "\n");
  let at = 0;
  const meta = [";FFMETADATA1", `title=${ffmetaValue(title)}`];
  const rows = ["| Time | Chapter |", "|---|---|"];
  for (const p of parts) {
    const d = probeSeconds(p.file);
    meta.push("[CHAPTER]", "TIMEBASE=1/1000", `START=${Math.round(at * 1000)}`, `END=${Math.round((at + d) * 1000)}`, `title=${ffmetaValue(p.title)}`);
    rows.push(`| ${Math.floor(at / 60)}:${String(Math.floor(at % 60)).padStart(2, "0")} | ${p.title} |`);
    at += d;
  }
  const metaFile = path.join(workDir, "chapters.ffmeta");
  fs.writeFileSync(metaFile, meta.join("\n") + "\n");
  const r = spawnSync(ffmpeg, ["-y", "-f", "concat", "-safe", "0", "-i", list, "-i", metaFile, "-map", "0", "-map_metadata", "1",
    "-map_chapters", "1", "-map", "-0:d", "-c", "copy", "-movflags", "+faststart", outFile], { stdio: ["ignore", "ignore", "pipe"] });
  if (r.status !== 0) throw new Error(`stitch failed: ${r.stderr?.toString().slice(-1500)}`);
  return { seconds: at, rows };
}

/** One frame of a video as a JPEG (`atSec` into it); false when ffmpeg could not decode one there. */
export function extractFrame(video, atSec, outFile, { ffmpeg = "ffmpeg" } = {}) {
  const r = spawnSync(ffmpeg, ["-y", "-ss", String(Math.max(0, atSec)), "-i", video, "-frames:v", "1", "-q:v", "3", outFile],
    { stdio: ["ignore", "ignore", "pipe"] });
  const ok = r.status === 0 && fs.existsSync(outFile) && fs.statSync(outFile).size > 0;
  if (!ok) fs.rmSync(outFile, { force: true });
  return ok;
}

// ---- exported recorder factory -----------------------------------------------------------------
/**
 * Build a reusable per-segment recorder bound to a story context.
 * The returned async function records one segment (including failed-take housekeeping).
 *
 * @param {object} opts
 * @param {object} opts.story          the storyline default export
 * @param {string} opts.baseUrl        app base URL
 * @param {string|null} [opts.fixture] fixture origin (fixtureOrigin() result); null = read-only
 * @param {string} [opts.ffmpeg]       ffmpeg binary (default "ffmpeg")
 * @param {object} opts.brand          brand config {name, accent, logoSvg}
 * @param {string} opts.segmentsDir    absolute path to the segments output dir
 * @param {number} [opts.trimStart]    opening-slide trim (default SEGMENT_TRIM_START)
 * @param {Function|null} [opts.consoleHandler] page.on("console", handler) installed before navigation
 * @param {Function|null} [opts.extendCtx] (baseCtx, seg, stage) => extra ctx keys to spread in
 * @param {object|null} [opts.policy]  the engine-run recorder's request policy (readonly.mjs demoPolicy); null = the
 *                                     hand recorder's write guard
 */
export function makeSegmentRecorder({
  palette = null,
  story,
  baseUrl,
  fixture: writableOrigin = null,
  ffmpeg: FFMPEG_BIN = "ffmpeg",
  brand,
  segmentsDir,
  trimStart = SEGMENT_TRIM_START,
  consoleHandler = null,
  extendCtx = null,
  policy = null,
  dropPicturesAfterFirst = false,
  redactFailures = false,
}) {
  const CHAPTERS_LIST = story.segments.filter((s) => !s.intro).map((s) => s.title);
  const LAST_KEY = story.segments[story.segments.length - 1].key;
  const localSegDir = (key) => path.join(segmentsDir, key);
  const localSegVideo = (key) => path.join(localSegDir(key), "segment.mp4");
  const readLocalGuard = (key) => {
    try { return JSON.parse(fs.readFileSync(path.join(localSegDir(key), "guard.json"), "utf8")); } catch { return null; }
  };
  const readLocalTimings = (key) => {
    try { return JSON.parse(fs.readFileSync(path.join(localSegDir(key), "timings.json"), "utf8")); } catch { return {}; }
  };

  function localKeepFailedTake(key, take, err, stage, failedAt) {
    const dir = path.join(localSegDir(key), `failed-${take}`);
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });
    const tlPath = path.join(localSegDir(key), "timeline.json");
    let video = null;
    let videoError = null;
    if (fs.existsSync(tlPath)) {
      fs.renameSync(tlPath, path.join(dir, "timeline.json"));
      // The master (and the frames dump, if any) go with the timeline; they are dropped once a video is built from them.
      for (const f of [CAPTURE, "frames"]) {
        if (fs.existsSync(path.join(localSegDir(key), f))) fs.renameSync(path.join(localSegDir(key), f), path.join(dir, f));
      }
      try {
        buildVideo(dir, path.join(dir, "segment.mp4"), { trimStart, ffmpeg: FFMPEG_BIN });
        video = "segment.mp4";
        fs.rmSync(path.join(dir, CAPTURE), { force: true });
        fs.rmSync(path.join(dir, "frames"), { recursive: true, force: true });
      } catch (e) {
        videoError = e.message;
        fs.rmSync(path.join(dir, "segment.mp4"), { force: true });
      }
    } else {
      videoError = "the take failed before recording began";
    }
    // With `redactFailures` (the app's rows may not reach a model), no message, cause or URL is kept: a browser
    // error can quote the page.
    const failure = {
      segment: key,
      take,
      code: err.code ?? null,
      // The failed step's name is the storyline's own words: it stays when the message is redacted.
      message: redactFailures ? `${err.code ?? "failed"}${typeof err.step === "string" ? ` at ${err.step}` : ""}` : err.message,
      cause: redactFailures ? null : err.cause?.message ?? null,
      blocked: redactFailures ? stage.blocked.map(() => "(redacted)") : stage.blocked,
      failed_at_sec: failedAtInVideo(dir, failedAt, trimStart),
      video,
      ...(videoError ? { video_error: videoError } : {}),
    };
    fs.writeFileSync(path.join(dir, "failure.json"), JSON.stringify(failure, null, 2));
    console.error(`  ${key}: take ${take} failed; evidence kept in ${dir}`);
  }

  return async function recordSegment(seg) {
    // By position among the chapters, never by title: two chapters may share one.
    const n = story.segments.filter((s) => !s.intro).indexOf(seg);
    const take = (readLocalGuard(seg.key)?.take ?? 0) + 1;
    console.log(`● ${seg.key} (take ${take})`);
    const stage = new Stage({
      baseUrl, outDir: localSegDir(seg.key), chapters: CHAPTERS_LIST, brand, palette,
      stickyOffset: story.stickyOffset, headful: process.env.DEMO_HEADFUL === "1", keepFrames: process.env.DEMO_KEEP_FRAMES === "1",
      locale: story.locale, timezoneId: story.timezoneId, writableOrigin, consoleHandler, ffmpeg: FFMPEG_BIN, policy, dropPicturesAfterFirst,
      hide: story.hide ?? [],
      // A crew app is recorded in its own frame only: studio's page around it is never in the picture (§13 A1.2).
      focusContent: policy?.target?.kind === "crew_app",
      redactSkips: redactFailures,
    });
    const timings = Object.create(null); // a label like `__proto__` is still a timing
    let ctx = makeCtx(stage, timings);
    fs.mkdirSync(localSegDir(seg.key), { recursive: true });
    fs.rmSync(localSegVideo(seg.key), { force: true });
    fs.rmSync(path.join(localSegDir(seg.key), "timeline.json"), { force: true });
    fs.rmSync(path.join(localSegDir(seg.key), CAPTURE), { force: true });
    let failure = null;
    let failedAt = null;
    let view;
    try {
      await stage.open(story.startPath || "/");
      // extendCtx must run after open() so that stage.app/page are set when the
      // spread evaluates their getters on the baseCtx object.
      if (extendCtx) ctx = { ...ctx, ...extendCtx(ctx, seg, stage) };
      if (seg.intro) {
        await seg.run(ctx);
        if (policy) await stage.checkpoint("chapter");
      } else {
        await stage.card(`<div class="seg"><div class="num">${String(n + 1).padStart(2, "0")}</div><div>
<div class="of">Chapter ${n + 1} of ${CHAPTERS_LIST.length}</div><h1>${esc(seg.title)}</h1>${seg.blurb ? `<p>${esc(seg.blurb)}</p>` : ""}
<div class="meta">${(seg.tags ?? []).map((x) => `<b>${esc(x)}</b>`).join("")}</div></div></div>`, 600);
        const t0 = Date.now();
        if (story.beforeSegment) await story.beforeSegment(ctx, seg);
        await stage.go(story.startPath || "/");
        // The app gets ready behind the card. A wait longer than the card's own hold is cut from the take.
        if (seg.prepare) await seg.prepare(ctx);
        // (A crew app) its own frame fills the window from here on, proven at every checkpoint, or the take fails.
        if (stage.focusContent) { await stage.requireView(); view = "app_frame"; }
        const waited = Date.now() - t0;
        if (waited > CARD_CUT_AFTER_MS) {
          stage.cutSince((t0 + CARD_CUT_AFTER_MS) / 1000, "the app got ready behind the chapter card");
          await stage.hold(1200);
        } else {
          await stage.hold(Math.max(1200, CARD_HOLD_MS - waited));
        }
        await stage.chapter(n);
        await stage.uncard();
        // The engine-run recorder proves the app is on screen, live, once the chapter card is gone.
        if (policy) await stage.checkpoint("chapter");
        await seg.run(ctx);
        // ...and once its steps are done, before any closing card: the state the chapter ends on.
        if (policy) await stage.checkpoint("done");
        await stage.hideCursor();
        await stage.hold(600);
      }
      if (seg.key === LAST_KEY && story.closing) {
        const all = Object.fromEntries(story.segments.map((s) => [s.key, s.key === seg.key ? timings : readLocalTimings(s.key)]));
        await stage.hideCursor();
        await stage.card(story.closing(all), story.closingMs ?? 10_000);
      } else if (!seg.intro) {
        await stage.card("", 1100);
      }
      // The engine-run recorder: the capture is proven live at the very end too, so a capture that died after
      // the last checkpoint never stitches its frozen picture into a passing take.
      if (policy) await stage.checkpoint("end");
    } catch (e) {
      failure = e;
      failedAt = Date.now() / 1000;
    } finally {
      await stage.close().catch(() => {});
    }
    // An encoder that failed while close() drained it is a failed take too: its master may be short of the end.
    let err = failure ?? stage.encoderError ?? null;
    // The engine-run recorder: a take that left the app or whose app frame failed to load fails even when no
    // checkpoint came after it.
    if (err === null && policy) {
      try { stage.policyCheck(); } catch (e) { err = e; }
    }
    // A failure the policy saw after the last step still names its moment in the video.
    if (stage.blocked.length) {
      err = sideEffectError(seg.key, stage.blocked);
      if (failure !== null) err.cause = failure;
      // The step the first refusal happened in (the storyline's words), not a later one that happened to throw.
      if (stage.blockedDuring) err.step = stage.blockedDuring;
    }
    // A failure the policy saw (a refused request, leaving the app, a document that failed) names ITS moment in the
    // video, not the moment a later step happened to throw.
    if (err !== null && policy && stage.firstFailureAt !== null) failedAt = stage.firstFailureAt;
    const writeGuard = (failed) => fs.writeFileSync(path.join(localSegDir(seg.key), "guard.json"), JSON.stringify({
      take, failed, readOnly: stage.readOnly, writableOrigin: stage.writableOrigin,
      ...(view !== undefined ? { view } : {}), ...(stage.hideInvalid.length ? { hide_invalid: stage.hideInvalid } : {}),
      blocked: redactFailures ? stage.blocked.map(() => "(redacted)") : stage.blocked,
      ...(policy ? { policy: { appOrigin: policy.appOrigin, launchPath: policy.launchPath, target: policy.target.kind }, diagnostics: stage.diagnostics } : {}),
    }, null, 2));
    writeGuard(true);
    if (err !== null) {
      localKeepFailedTake(seg.key, take, err, stage, failedAt);
      throw err;
    }
    let r;
    try {
      const tl = JSON.parse(fs.readFileSync(path.join(localSegDir(seg.key), "timeline.json"), "utf8"));
      fs.writeFileSync(path.join(localSegDir(seg.key), "timeline.json"), JSON.stringify({ ...tl, title: story.title }, null, 1));
      fs.writeFileSync(path.join(localSegDir(seg.key), "timings.json"), JSON.stringify(timings, null, 2));
      try {
        r = buildVideo(localSegDir(seg.key), localSegVideo(seg.key), { trimStart, ffmpeg: FFMPEG_BIN });
      } catch (e) {
        e.code ??= "encoder_failed"; // the cut failing is the host's, never the storyline's
        throw e;
      }
    } catch (e) {
      fs.rmSync(localSegVideo(seg.key), { force: true });
      localKeepFailedTake(seg.key, take, e, stage, null);
      throw e;
    }
    writeGuard(false);
    console.log(`  ${seg.key}: ${r.seconds.toFixed(1)} s${Object.keys(timings).length ? " " + JSON.stringify(timings) : ""}`);
  };
}

// ---- CLI entry point (only runs when invoked directly) -----------------------------------------
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const FFMPEG = process.env.FFMPEG || "ffmpeg";

  function usage(msg) {
    if (msg) console.error(`error: ${msg}\n`);
    console.error("usage: wicked-garden run scripts/demo/record.mjs <storyline.mjs> [segment-key ...] [--all | --stitch | --reencode | --list] [--out <dir>] [--fixture-origin <loopback origin>]");
    process.exit(2);
  }

  // ---- args ----
  const argv = process.argv.slice(2);
  const VALUED = ["--out", "--fixture-origin"];
  const valueAt = new Set(VALUED.map((f) => argv.indexOf(f)).filter((i) => i >= 0).map((i) => i + 1));
  const flags = new Set(argv.filter((a) => a.startsWith("--") && !VALUED.includes(a)));
  const outIdx = argv.indexOf("--out");
  const fixtureIdx = argv.indexOf("--fixture-origin");
  const positional = argv.filter((a, i) => !a.startsWith("--") && !valueAt.has(i));
  let FIXTURE = null;
  try {
    FIXTURE = fixtureIdx >= 0 ? fixtureOrigin(argv[fixtureIdx + 1] ?? "") : null;
    if (fixtureIdx >= 0 && !FIXTURE) throw new Error("--fixture-origin needs a value");
  } catch (e) {
    usage(e.message);
  }
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
  function readLogo(rel) {
    if (!rel) return "";
    const p = path.resolve(storyDir, rel);
    if (!fs.existsSync(p)) {
      console.warn(`warning: brand.logo not found, recording without a logo: ${p}`);
      return "";
    }
    return fs.readFileSync(p, "utf8");
  }
  const brand = {
    name: story.brand?.name ?? story.title ?? "Demo",
    accent: story.brand?.accent ?? null, // null = the studio skin's accent (palette.mjs)
    logoSvg: readLogo(story.brand?.logo),
  };
  const SEGMENTS = story.segments;
  for (const s of SEGMENTS) if (!/^[a-z0-9][a-z0-9-]*$/.test(s.key ?? "")) usage(`segment key must be lowercase letters, digits and hyphens: ${s.key}`);
  const CHAPTERS = SEGMENTS.filter((s) => !s.intro).map((s) => s.title);
  const LAST = SEGMENTS[SEGMENTS.length - 1].key;

  const segDir = (key) => path.join(SEG_DIR, key);
  const segVideo = (key) => path.join(segDir(key), "segment.mp4");
  const TRIM_START = SEGMENT_TRIM_START;
  const readTimings = (key) => { try { return JSON.parse(fs.readFileSync(path.join(segDir(key), "timings.json"), "utf8")); } catch { return {}; } };

  // ---- stitch ----
  /** A segment's guard.json (how its last take was recorded), or null when it has none. */
  function readGuard(key) {
    try { return JSON.parse(fs.readFileSync(path.join(segDir(key), "guard.json"), "utf8")); } catch { return null; }
  }

  /** A segment whose last take was blocked or failed stops a re-encode or a stitch until it is re-recorded (or its
   *  directory is removed): it is never re-encoded, stitched around, or left out quietly. */
  function refuseFailedTakes() {
    for (const s of SEGMENTS) {
      const guard = readGuard(s.key);
      const blocked = guard?.blocked ?? [];
      if (blocked.length) throw sideEffectError(s.key, blocked);
      if (guard?.failed === true) {
        const err = new Error(`failed_take: segment ${s.key}'s last take (${guard.take}) failed; its evidence is in ` +
          `${path.join(segDir(s.key), `failed-${guard.take}`)}. Re-record the segment (or remove its directory) first.`);
        err.code = "failed_take";
        throw err;
      }
    }
  }

  function stitch() {
    refuseFailedTakes();
    const segs = SEGMENTS.filter((s) => fs.existsSync(segVideo(s.key)));
    const missing = SEGMENTS.filter((s) => !fs.existsSync(segVideo(s.key))).map((s) => s.key);
    const { seconds: at, rows } = stitchParts(
      segs.map((s) => ({ title: s.intro ? "Introduction" : s.title, file: segVideo(s.key) })),
      FINAL, { ffmpeg: FFMPEG, title: story.title || "Demo", workDir: SEG_DIR },
    );
    fs.writeFileSync(path.join(OUT, "chapters.md"), rows.join("\n") + "\n");
    fs.writeFileSync(path.join(OUT, "timings.json"), JSON.stringify(Object.fromEntries(SEGMENTS.map((s) => [s.key, readTimings(s.key)])), null, 2));
    // How the stitched segments were recorded: read-only only when every one of them was (a segment recorded
    // before the guard existed has no guard.json and counts as unknown, not read-only). A segment recorded with
    // --fixture-origin is "fixture-writable"; its guard.json names the origin.
    const guards = segs.map((s) => readGuard(s.key));
    const mode = (g) => (g === null ? "unknown" : g.readOnly === true ? "read-only" : g.writableOrigin ? "fixture-writable" : "unknown");
    fs.writeFileSync(path.join(OUT, "recording.json"), JSON.stringify({
      readOnly: guards.every((g) => g?.readOnly === true && Array.isArray(g.blocked) && g.blocked.length === 0),
      segments: Object.fromEntries(segs.map((s, i) => [s.key, mode(guards[i])])),
    }, null, 2));
    console.log(`stitched ${segs.length} segments -> ${FINAL} (${Math.round(at)} s)${missing.length ? `; missing: ${missing.join(", ")}` : ""}`);
  }

  // ---- main ----
  fs.mkdirSync(SEG_DIR, { recursive: true });
  const ffCheck = spawnSync(FFMPEG, ["-version"], { stdio: "ignore" });
  if (ffCheck.error || ffCheck.status !== 0) usage(`ffmpeg not found (${FFMPEG}); install it or set FFMPEG=/path/to/ffmpeg`);

  // The studio skin's colours by default (crew's video palette), the neutral palette without a daemon.
  const skin = await fetchVideoPalette();
  console.log(`palette: ${skin.source}`);
  const recordSegment = makeSegmentRecorder({ story, baseUrl: BASE, fixture: FIXTURE, ffmpeg: FFMPEG, brand, palette: skin.palette, segmentsDir: SEG_DIR });

  if (flags.has("--list")) {
    for (const s of SEGMENTS) console.log(`${fs.existsSync(segVideo(s.key)) ? "recorded" : "missing "}  ${s.key}  ${s.intro ? "(intro)" : s.title}`);
    process.exit(0);
  }
  if (flags.has("--reencode")) {
    refuseFailedTakes();
    for (const s of SEGMENTS.filter((x) => fs.existsSync(path.join(segDir(x.key), "timeline.json")))) {
      const r = buildVideo(segDir(s.key), segVideo(s.key), { trimStart: TRIM_START, ffmpeg: FFMPEG });
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
}
