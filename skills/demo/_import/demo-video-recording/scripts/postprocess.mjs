// Part of the demo-video-recording skill. Turns a recorded timeline (frames + marks) into a 1080p H.264 MP4 with chapter markers.
//
// Each screencast frame lasts until the next one; spans marked by Stage.fast() are compressed by their factor,
// so long model waits play as a visible time-lapse while the on-screen badge states the real elapsed time.
// Usage: node postprocess.mjs <outDir> [output.mp4]
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const FPS = 30;

export function buildVideo(outDir, outFile, { ffmpeg = process.env.FFMPEG || "ffmpeg", tail = 0.2, trimStart = 0 } = {}) {
  const tl = JSON.parse(fs.readFileSync(path.join(outDir, "timeline.json"), "utf8"));
  const frames = tl.frames.filter((f) => f.t >= tl.t0 + trimStart);
  if (!frames.length) throw new Error("no frames recorded");
  const speed = [...tl.marks.speed].sort((a, b) => a.start - b.start);

  // Output time for a wall-clock instant: integrate 1/factor over the marked spans.
  const origin = frames[0].t;
  const outAt = (t) => {
    let out = t - origin;
    for (const s of speed) {
      const a = Math.max(s.start, origin), b = Math.min(s.end, t);
      if (b > a) out -= (b - a) * (1 - 1 / s.factor);
    }
    return out;
  };

  // Resample to constant frame rate: output tick k shows the newest frame captured at or before k/FPS, and each
  // run of identical picks becomes one concat entry lasting (run length / FPS). Bursts collapse, gaps hold.
  const outTimes = frames.map((f) => outAt(f.t));
  // The screencast only emits a frame when the picture changes, so a static hold at the end (a closing card, a final
  // pause) has no frame of its own: end at the moment recording stopped, not at the last captured frame.
  const total = Math.max(outTimes[outTimes.length - 1] + 1 / FPS, outAt(tl.tEnd ?? frames[frames.length - 1].t)) + tail;
  const ticks = Math.ceil(total * FPS);
  const runs = [];
  for (let k = 0, i = 0; k < ticks; k++) {
    while (i + 1 < frames.length && outTimes[i + 1] <= k / FPS) i++;
    if (runs.length && runs[runs.length - 1].i === i) runs[runs.length - 1].n++;
    else runs.push({ i, n: 1 });
  }
  const lines = ["ffconcat version 1.0"];
  for (const r of runs) lines.push(`file 'frames/${frames[r.i].file}'`, `duration ${(r.n / FPS).toFixed(6)}`);
  lines.push(`file 'frames/${frames[runs[runs.length - 1].i].file}'`); // concat demuxer needs the last file repeated
  fs.writeFileSync(path.join(outDir, "frames.ffconcat"), lines.join("\n"));

  const chapters = tl.marks.chapters.map((c) => ({ ...c, out: Math.max(0, outAt(c.t)) }));
  const meta = [";FFMETADATA1", `title=${(tl.title || "Demo").replace(/[=;#\\\n]/g, " ")}`];
  chapters.forEach((c, i) => {
    const start = Math.round(c.out * 1000), end = Math.round((i + 1 < chapters.length ? chapters[i + 1].out : total) * 1000);
    meta.push("[CHAPTER]", "TIMEBASE=1/1000", `START=${start}`, `END=${end}`, `title=${c.title.replace(/[=;#\\\n]/g, " ")}`);
  });
  fs.writeFileSync(path.join(outDir, "chapters.ffmeta"), meta.join("\n") + "\n");

  const args = ["-y", "-f", "concat", "-safe", "0", "-i", "frames.ffconcat", "-i", "chapters.ffmeta", "-map_metadata", "1", "-map_chapters", "1",
    "-t", total.toFixed(3), "-vf", `fps=${FPS},format=yuv420p`, "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "stillimage", "-movflags", "+faststart", path.resolve(outFile)];
  const r = spawnSync(ffmpeg, args, { cwd: outDir, stdio: ["ignore", "ignore", "pipe"] });
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${r.stderr?.toString().slice(-2000)}`);

  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const md = ["| Time | Chapter |", "|---|---|", ...chapters.map((c) => `| ${fmt(c.out)} | ${c.title} |`)];
  fs.writeFileSync(path.join(outDir, "chapters.md"), md.join("\n") + "\n");
  return { seconds: total, chapters: chapters.map((c) => ({ at: fmt(c.out), title: c.title })), speedups: speed.length, frames: frames.length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [outDir, outFile] = process.argv.slice(2);
  if (outDir) console.log(JSON.stringify(buildVideo(outDir, outFile || path.join(outDir, "segment.mp4")), null, 2));
}
