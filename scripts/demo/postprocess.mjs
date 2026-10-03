// Part of the wicked-garden-demo skill. Cuts a take's master (capture.mp4 + timeline.json) into a 1080p H.264 MP4
// with chapter markers.
//
// The master is the take at a constant FPS, encoded live while it recorded (stage.mjs): frame k is the picture at
// t0 + k/FPS, so wall clock and master time are the same line. The cut drops the opening trim, keeps one frame in
// `factor` across every span marked by Stage.fast() and re-times what is left back to back, so long model waits play
// as a visible time-lapse while the on-screen badge states the real elapsed time; the chapter marks land where
// videoClock().outAt() says. No frame file is read or written.
// Usage: wicked-garden run scripts/demo/postprocess.mjs <outDir> [output.mp4]
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

/** The master's constant frame rate. */
export const FPS = 30;
/** The master's file name inside a take's directory. */
export const CAPTURE = "capture.mp4";
/** ffprobe beside a given ffmpeg binary (`FFMPEG=/path/to/ffmpeg` is honoured for both). */
export const ffprobeOf = (ffmpeg) => ffmpeg.replace(/ffmpeg(\.exe)?$/i, "ffprobe$1");

/**
 * The video clock of a timeline, in master frames so it agrees with the cut to the frame: `inFrame`, the first
 * master frame kept; `spans`, the time-lapse spans as [a, b) frame ranges with their factor; `keptBefore(k)`, how many
 * cut frames precede master frame k; and `outAt(t)`, the position in the cut video (seconds) of a wall-clock instant.
 * Throws when a closed take says nothing was recorded past the trim; a timeline a killed take left (no frame count)
 * is clocked from its t0 and the master is counted by buildVideo.
 */
export function videoClock(tl, trimStart = 0) {
  const fps = tl.capture?.fps ?? FPS;
  const inFrame = Math.max(0, Math.ceil(trimStart * fps - 1e-9));
  if (typeof tl.capture?.frames === "number" && tl.capture.frames <= inFrame) throw new Error("no frames recorded");
  const toFrame = (t) => Math.round((t - tl.t0) * fps);
  // Inside a span only frame a and every frame where floor((k - a) / factor) advances are kept: one in `factor`.
  const spans = [...tl.marks.speed].sort((x, y) => x.start - y.start)
    .map((s) => ({ a: Math.max(inFrame, toFrame(s.start)), b: toFrame(s.end), f: s.factor }))
    .filter((s) => s.b > s.a && s.f > 1);
  const keptIn = (a, b, f) => (b > a ? Math.floor((b - a - 1) / f) + 1 : 0);
  const keptBefore = (k) => {
    let kept = Math.max(0, k - inFrame);
    for (const s of spans) {
      const b = Math.min(s.b, k);
      if (b > s.a) kept -= (b - s.a) - keptIn(s.a, b, s.f);
    }
    return kept;
  };
  const outAt = (t) => keptBefore(toFrame(t)) / fps;
  return { inFrame, fps, spans, keptIn, keptBefore, outAt, speed: tl.marks.speed };
}

/** Frames in the master, by demuxing it (exact for a master whose writer died: the complete packets count). */
function countFrames(ffprobe, file) {
  const r = spawnSync(ffprobe, ["-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", file],
    { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`ffprobe failed on ${file}: ${(r.error?.message ?? r.stderr ?? "").slice(-500)}`);
  const n = Number(r.stdout.trim());
  if (!Number.isInteger(n)) throw new Error(`ffprobe gave no frame count for ${file}: ${r.stdout.slice(0, 200)}`);
  return n;
}

export function buildVideo(outDir, outFile, { ffmpeg = process.env.FFMPEG || "ffmpeg", tail = 0.2, trimStart = 0 } = {}) {
  const tl = JSON.parse(fs.readFileSync(path.join(outDir, "timeline.json"), "utf8"));
  const capture = path.join(outDir, tl.capture?.file ?? CAPTURE);
  if (!fs.existsSync(capture)) {
    throw new Error(tl.capture?.error ?? `${path.basename(capture)} not found in ${outDir}` +
      (Array.isArray(tl.frames) && !tl.capture ? " (recorded from frames by an earlier version; re-record the segment)" : ""));
  }
  const { inFrame, fps, spans, keptBefore, outAt, speed } = videoClock(tl, trimStart);
  // What the master holds is what counts: an encoder that died late still left playable fragments to cut, and its
  // failure is the explanation only when nothing can be.
  let nFrames;
  try { nFrames = countFrames(ffprobeOf(ffmpeg), capture); } catch (e) { throw new Error(tl.capture?.error ?? e.message); }
  if (nFrames <= inFrame) throw new Error(tl.capture?.error ?? "no frames recorded");

  // Master frame k is the picture at t0 + k/fps. Inside a marked span one frame in `factor` is kept; the kept frames
  // are re-timed back to back at fps. In the select expression n counts frames after the trim (n = k - inFrame).
  const keep = spans.filter((s) => s.a < nFrames).reduce((rest, s) => {
    const a = s.a - inFrame, b = Math.min(s.b, nFrames) - inFrame - 1;
    return `if(between(n\\,${a}\\,${b})\\,gt(floor((n-${a})/${s.f})\\,floor((n-${a}-1)/${s.f}))\\,${rest})`;
  }, "1");
  const kept = keptBefore(nFrames);
  const total = kept / fps + tail;

  const chapters = tl.marks.chapters.map((c) => ({ ...c, out: Math.max(0, outAt(c.t)) }));
  const meta = [";FFMETADATA1", `title=${(tl.title || "Demo").replace(/[=;#\\\n]/g, " ")}`];
  chapters.forEach((c, i) => {
    const start = Math.round(c.out * 1000), end = Math.round((i + 1 < chapters.length ? chapters[i + 1].out : total) * 1000);
    meta.push("[CHAPTER]", "TIMEBASE=1/1000", `START=${start}`, `END=${end}`, `title=${c.title.replace(/[=;#\\\n]/g, " ")}`);
  });
  fs.writeFileSync(path.join(outDir, "chapters.ffmeta"), meta.join("\n") + "\n");

  // tpad holds the last picture for `tail` (a static close has frames of its own in the master, but the cut
  // should not end on the very tick recording stopped).
  const vf = `trim=start_frame=${inFrame},select='${keep}',setpts=N/(${fps}*TB),tpad=stop_mode=clone:stop_duration=${tail.toFixed(3)},format=yuv420p`;
  const args = ["-y", "-i", capture, "-i", "chapters.ffmeta", "-map_metadata", "1", "-map_chapters", "1", "-vf", vf, "-r", String(fps), "-fps_mode", "cfr",
    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "stillimage", "-movflags", "+faststart", path.resolve(outFile)];
  const r = spawnSync(ffmpeg, args, { cwd: outDir, stdio: ["ignore", "ignore", "pipe"] });
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${(r.error?.message ?? r.stderr?.toString() ?? "").slice(-2000)}`);

  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const md = ["| Time | Chapter |", "|---|---|", ...chapters.map((c) => `| ${fmt(c.out)} | ${c.title} |`)];
  fs.writeFileSync(path.join(outDir, "chapters.md"), md.join("\n") + "\n");
  return { seconds: total, chapters: chapters.map((c) => ({ at: fmt(c.out), title: c.title })), speedups: speed.length, frames: nFrames - inFrame };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [outDir, outFile] = process.argv.slice(2);
  if (outDir) console.log(JSON.stringify(buildVideo(outDir, outFile || path.join(outDir, "segment.mp4")), null, 2));
}
