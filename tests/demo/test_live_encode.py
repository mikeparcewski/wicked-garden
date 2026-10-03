"""The demo recorder encodes while it records: no raw frame touches disk (live encode, 12.42.0).

Before, every changed screencast frame was written as a JPEG (q95, 1920x1080: ~8 MB/s, ~5 GB per
10-minute take) and encoded afterwards. Now a 30 fps ticker feeds the newest picture to ffmpeg's stdin,
which writes a fragmented H.264 master (`capture.mp4`); postprocess cuts that master into `segment.mp4`
(opening trim, time-lapsed waits, chapter markers). These tests pin what must not change: the outputs,
the clock, a failed or killed take's evidence, and the picture, measured against the 12.41.0 recipe run
on the same take (tests/demo/fixtures/postprocess_12_41_0.mjs, DEMO_KEEP_FRAMES=1 dumps the frames).

Needs node, ffmpeg/ffprobe and the demo deps (wicked-garden run scripts/demo/setup.mjs); skipped without.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.demo.test_readonly_recorder import DEMO, _App, _record, needs_node, needs_recorder

FIXTURES = Path(__file__).parent / "fixtures"
LEGACY = FIXTURES / "postprocess_12_41_0.mjs"
FPS = 30
TRIM = 0.9  # record.mjs SEGMENT_TRIM_START
TAIL = 0.2  # postprocess buildVideo default


def _serve(handler=_App):
    import http.server
    import threading
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _probe(video: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-print_format", "json",
         "-show_entries", "stream=nb_read_packets,width,height,codec_name:format=duration", "-show_chapters", str(video)],
        capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    s = data["streams"][0]
    return {
        "frames": int(s["nb_read_packets"]), "width": s["width"], "height": s["height"], "codec": s["codec_name"],
        "duration": float(data["format"]["duration"]),
        "chapters": [{"start": float(c["start_time"]), "end": float(c["end_time"]), "title": c.get("tags", {}).get("title")}
                     for c in data.get("chapters", [])],
    }


def _decodes(video: Path) -> bool:
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                          capture_output=True, text=True, timeout=120).returncode == 0


def _node(script: str, cwd: Path = DEMO) -> str:
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=cwd, capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _clock(seg: Path, trim: float = TRIM) -> dict:
    """outAt() of the take's marks and end, through the recorder's own clock."""
    return json.loads(_node(
        "import fs from 'node:fs'; import { videoClock } from './postprocess.mjs';"
        f"const tl = JSON.parse(fs.readFileSync({json.dumps(str(seg / 'timeline.json'))}, 'utf8'));"
        f"const c = videoClock(tl, {trim});"
        "console.log(JSON.stringify({ end: c.outAt(tl.tEnd), chapters: tl.marks.chapters.map((m) => c.outAt(m.t)),"
        " speed: tl.marks.speed, wall: tl.tEnd - tl.t0, frames: tl.capture.frames }));"))


def _ssim(a: Path, b: Path) -> dict:
    """ffmpeg's ssim filter over the frames both videos have: the mean, and the median over frames
    (a frame-of-latency difference at a transition dents the mean, not the median)."""
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(a), "-i", str(b), "-lavfi", "[0:v][1:v]ssim=stats_file=-",
                          "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-1500:]
    per_frame = [float(m.group(1)) for m in re.finditer(r"\bAll:(\d\.\d+)", out.stdout)]
    mean = re.search(r"SSIM .*All:(\d\.\d+)", out.stderr)
    assert per_frame and mean, (out.stdout[-500:], out.stderr[-500:])
    return {"mean": float(mean.group(1)), "median": statistics.median(per_frame), "min": min(per_frame), "frames": len(per_frame)}


def _dir_bytes(d: Path) -> int:
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


@needs_node
@needs_recorder
def test_a_take_writes_no_frames_and_leaves_about_two_videos_worth_of_bytes(tmp_path):
    server, base = _serve()
    try:
        out = _record(tmp_path, base, "      await ctx.hold(2500);")
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    assert not (seg / "frames").exists(), "a take must not write frames to disk"
    assert not (seg / "frames.ffconcat").exists()
    capture, video = seg / "capture.mp4", seg / "segment.mp4"
    assert capture.stat().st_size > 0 and video.stat().st_size > 0
    tl = json.loads((seg / "timeline.json").read_text())
    assert "frames" not in tl, "the timeline no longer lists frame files"
    assert tl["capture"]["file"] == "capture.mp4" and tl["capture"]["fps"] == FPS
    assert "error" not in tl["capture"]
    master = _probe(capture)
    # The master is the take at a constant 30 fps: frame k is the picture at t0 + k/30, so the clock is linear.
    assert (master["width"], master["height"], master["codec"]) == (1920, 1080, "h264")
    assert master["frames"] == tl["capture"]["frames"]
    assert abs(master["frames"] - (int((tl["tEnd"] - tl["t0"]) * FPS) + 1)) <= 1, (master["frames"], tl["tEnd"] - tl["t0"])
    cut = _probe(video)
    assert (cut["width"], cut["height"], cut["codec"]) == (1920, 1080, "h264")
    # Disk: what the take left behind is the master plus the cut video (plus a few KB of JSON), nothing per frame.
    total = _dir_bytes(seg)
    ratio = total / video.stat().st_size
    print(f"\ndisk: capture={capture.stat().st_size} segment={video.stat().st_size} dir={total} dir/segment={ratio:.2f} "
          f"master_frames={master['frames']} wall={tl['tEnd'] - tl['t0']:.2f}s")
    assert ratio <= 4.0, f"the segment dir holds {ratio:.1f}x the final video"
    # ...and the master is the only large file beside the video.
    assert total - capture.stat().st_size - video.stat().st_size < 64 * 1024


@needs_node
@needs_recorder
def test_keep_frames_dumps_the_frames_and_the_pipe_matches_the_frames_recipe_on_the_same_take(tmp_path):
    """DEMO_KEEP_FRAMES=1 writes the screencast frames beside the master (debugging). The same take then
    yields both videos: the 12.41.0 recipe built from the frames, and the pipe's cut of the master. The
    picture must match; a lossless build of the frames is the yardstick both are measured against."""
    server, base = _serve()
    body = ("      await ctx.caption('Runs', 'Every run on one page', 'The list the team reads first', 1500);\n"
            "      await ctx.point(ctx.app.getByRole('heading', { name: 'Runs' }), 'Runs', { hold: 1200 });\n"
            "      await ctx.unpoint();\n"
            "      await ctx.hold(900);")
    story = tmp_path / "storyline.mjs"
    story.write_text("export default { title: 'demo', baseUrl: %s, segments: [\n"
                     "  { key: '01-launch', title: 'Launch a run', async run(ctx) {\n%s\n  } },\n] };\n" % (json.dumps(base), body))
    try:
        out = subprocess.run(["node", str(DEMO / "record.mjs"), str(story), "--out", str(tmp_path / "demo-video")],
                             capture_output=True, text=True, timeout=240, env={**os.environ, "DEMO_KEEP_FRAMES": "1"})
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    jpgs = sorted((seg / "frames").glob("f*.jpg"))
    assert len(jpgs) >= 10, "the opt-out dumps every screencast frame"
    tl = json.loads((seg / "timeline.json").read_text())
    assert [f["file"] for f in tl["frames"]] == [p.name for p in jpgs]
    assert all(f["t"] >= tl["t0"] - 1 for f in tl["frames"])
    assert (seg / "capture.mp4").stat().st_size > 0, "the pipe still runs with the frames dumped"

    # The 12.41.0 recipe on this take's frames, in its own directory (it writes frames.ffconcat + chapters there).
    ref = tmp_path / "ref"
    ref.mkdir()
    shutil.copy(seg / "timeline.json", ref / "timeline.json")
    os.symlink(seg / "frames", ref / "frames")
    _node(f"import {{ buildVideo }} from {json.dumps(LEGACY.resolve().as_posix())};"
          f"console.log(JSON.stringify(buildVideo({json.dumps(str(ref))}, {json.dumps(str(ref / 'legacy.mp4'))}, {{ trimStart: {TRIM} }})));")
    # The yardstick: the same frames, same resampling, no encoder loss (x264 lossless).
    lossless = ref / "lossless.mp4"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "frames.ffconcat", "-vf", f"fps={FPS},format=yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", str(lossless)], cwd=ref, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-1000:]

    new, legacy = seg / "segment.mp4", ref / "legacy.mp4"
    pn, pl = _probe(new), _probe(legacy)
    assert abs(pn["duration"] - pl["duration"]) <= 0.15, (pn["duration"], pl["duration"])
    parity = _ssim(new, legacy)
    new_vs_truth, legacy_vs_truth = _ssim(new, lossless), _ssim(legacy, lossless)
    jpeg_bytes = sum(p.stat().st_size for p in jpgs)
    print(f"\nquality: ssim(pipe,frames-recipe) mean={parity['mean']:.4f} median={parity['median']:.4f} min={parity['min']:.4f} over {parity['frames']} frames;"
          f" ssim(pipe,lossless) mean={new_vs_truth['mean']:.4f} median={new_vs_truth['median']:.4f};"
          f" ssim(frames-recipe,lossless) mean={legacy_vs_truth['mean']:.4f} median={legacy_vs_truth['median']:.4f};"
          f" bytes: jpeg_frames={jpeg_bytes} ({len(jpgs)} frames) capture={(seg / 'capture.mp4').stat().st_size} segment={new.stat().st_size} legacy={legacy.stat().st_size};"
          f" duration pipe={pn['duration']:.2f} legacy={pl['duration']:.2f}")
    # Same picture: the two cuts of one take agree frame for frame, except where a frame of screencast latency
    # lands a transition one tick apart (hence the median).
    assert parity["median"] >= 0.98, parity
    assert parity["mean"] >= 0.95, parity
    # The live master is not the lossy step: against the lossless build of the frames, the pipe's video is as close
    # as the single-encode recipe was (within a hundredth of SSIM on the median frame).
    assert new_vs_truth["median"] >= legacy_vs_truth["median"] - 0.01, (new_vs_truth, legacy_vs_truth)
    # The disk saving the whole change is for.
    assert (seg / "capture.mp4").stat().st_size < jpeg_bytes


@needs_node
@needs_recorder
@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL")
def test_a_recorder_killed_mid_take_leaves_a_playable_master_the_cut_can_rebuild(tmp_path):
    """SIGKILL the recorder in the middle of a take: nothing of it runs again, but the encoder sees EOF, flushes,
    and the fragmented master plays; the timeline written so far is enough for postprocess to cut it."""
    server, base = _serve()
    story = tmp_path / "storyline.mjs"
    story.write_text("export default { title: 'demo', baseUrl: %s, segments: [\n"
                     "  { key: '01-launch', title: 'Launch a run', async run(ctx) { await ctx.hold(60000); } },\n] };\n" % json.dumps(base))
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    capture = seg / "capture.mp4"
    proc = subprocess.Popen(["node", str(DEMO / "record.mjs"), str(story), "--out", str(tmp_path / "demo-video")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 45
        while time.time() < deadline and not (capture.exists() and (seg / "timeline.json").exists() and capture.stat().st_size > 0):
            assert proc.poll() is None, proc.stderr.read()[-2000:]
            time.sleep(0.25)
        assert capture.exists() and (seg / "timeline.json").exists(), "the master and a first timeline appear while the take runs"
        time.sleep(4)  # a few complete fragments
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
        server.shutdown()
    # The encoder finishes on its own (EOF on stdin) and lets go of the file.
    deadline = time.time() + 30
    last = -1
    while time.time() < deadline:
        size = capture.stat().st_size
        held = subprocess.run(["pgrep", "-f", str(capture)], capture_output=True, text=True).stdout.strip()
        if size == last and not held:
            break
        last = size
        time.sleep(1)
    assert not held, "ffmpeg still runs after the recorder died"
    master = _probe(capture)
    assert master["frames"] >= 2 * FPS, master
    assert _decodes(capture), "the partial master must play"
    tl = json.loads((seg / "timeline.json").read_text())
    assert tl["tEnd"] is None and tl["capture"]["file"] == "capture.mp4" and tl["t0"] > 0, tl
    # And it is evidence a cut can be built from: the same postprocess, no frames anywhere.
    r = json.loads(_node(
        "import { buildVideo } from './postprocess.mjs';"
        f"console.log(JSON.stringify(buildVideo({json.dumps(str(seg))}, {json.dumps(str(seg / 'segment.mp4'))}, {{ trimStart: {TRIM} }})));"))
    cut = _probe(seg / "segment.mp4")
    assert r["seconds"] > 1 and abs(cut["duration"] - r["seconds"]) <= 0.05, (r, cut["duration"])
    assert cut["frames"] == master["frames"] - int(TRIM * FPS + 0.999999) + round(TAIL * FPS)
    assert not (seg / "frames").exists()


@needs_node
@needs_recorder
@pytest.mark.skipif(sys.platform == "win32", reason="the fake encoder is a POSIX shell script")
def test_an_encoder_that_dies_during_the_take_fails_it_at_the_next_step_and_keeps_what_it_left(tmp_path):
    """The live encoder exits at once: the take fails `encoder_failed` instead of filming into nothing, its failure
    names ffmpeg's exit, and whatever the encoder left stays as evidence (no video could be cut from it)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "ffmpeg"
    fake.write_text("#!/bin/sh\n[ \"$1\" = -version ] && exit 0\nprintf 'partial' > \"$(eval echo \\${$#})\"\necho boom >&2\nexit 1\n")
    fake.chmod(0o755)
    os.symlink(shutil.which("ffprobe"), bindir / "ffprobe")
    server, base = _serve()
    story = tmp_path / "storyline.mjs"
    story.write_text("export default { title: 'demo', baseUrl: %s, segments: [\n"
                     "  { key: '01-launch', title: 'Launch a run', async run(ctx) { await ctx.hold(20000); } },\n] };\n" % json.dumps(base))
    t0 = time.time()
    try:
        out = subprocess.run(["node", str(DEMO / "record.mjs"), str(story), "--out", str(tmp_path / "demo-video")],
                             capture_output=True, text=True, timeout=120, env={**os.environ, "FFMPEG": str(fake)})
    finally:
        server.shutdown()
    assert out.returncode != 0, out.stdout
    assert time.time() - t0 < 20, "the take did not stop when its encoder died"
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    failure = json.loads((seg / "failed-1" / "failure.json").read_text())
    assert failure["code"] == "encoder_failed" and "ffmpeg failed (1): boom" in failure["message"], failure
    assert failure["video"] is None and "ffmpeg failed (1): boom" in failure["video_error"], failure
    assert (seg / "failed-1" / "capture.mp4").exists() and not (seg / "failed-1" / "segment.mp4").exists()
    tl = json.loads((seg / "failed-1" / "timeline.json").read_text())
    assert "ffmpeg failed (1): boom" in tl["capture"]["error"]


@needs_node
@needs_recorder
def test_chapters_and_the_time_lapse_are_cut_from_the_master_and_the_contact_sheet_reads_it(tmp_path):
    server, base = _serve()
    try:
        out = _record(tmp_path, base, "      await ctx.fast('Waiting', 4, () => ctx.hold(4000));\n      await ctx.hold(600);")
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    clock = _clock(seg)
    cut = _probe(seg / "segment.mp4")
    # The clock: a wall-clock instant maps to the same video position the cut put it at.
    assert len(clock["speed"]) == 1 and 3.8 <= clock["speed"][0]["end"] - clock["speed"][0]["start"] <= 4.6, clock["speed"]
    assert abs(cut["duration"] - (clock["end"] + TAIL)) <= 2.5 / FPS, (cut["duration"], clock["end"])
    # The 4 s wait plays in about 1 s: the video is about 3 s shorter than the trimmed wall clock.
    saved = (clock["wall"] - TRIM) - clock["end"]
    assert 2.6 <= saved <= 3.4, saved
    # Chapter markers, embedded and listed, at the clock's position.
    assert [c["title"] for c in cut["chapters"]] == ["Launch a run"], cut["chapters"]
    assert abs(cut["chapters"][0]["start"] - clock["chapters"][0]) <= 0.05, (cut["chapters"], clock["chapters"])
    assert abs(cut["chapters"][0]["end"] - cut["duration"]) <= 0.05
    assert "| Launch a run |" in (seg / "chapters.md").read_text()
    # The stitched video carries them too.
    final = tmp_path / "demo-video" / "demo.mp4"
    assert [c["title"] for c in _probe(final)["chapters"]] == ["Launch a run"]
    # Review still works from the video alone (there are no frame files to read).
    sheet = tmp_path / "sheet.png"
    r = subprocess.run([sys.executable, str(DEMO / "contact_sheet.py"), str(seg / "segment.mp4"), "--every", "1", "--out", str(sheet)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1000:]
    assert sheet.stat().st_size > 0
    # --reencode rebuilds from the master, and the result is the same cut.
    again = subprocess.run(["node", str(DEMO / "record.mjs"), str(tmp_path / "storyline.mjs"), "--reencode", "--out", str(tmp_path / "demo-video")],
                           capture_output=True, text=True, timeout=240)
    assert again.returncode == 0, again.stderr[-1500:]
    assert _probe(seg / "segment.mp4")["frames"] == cut["frames"]
    assert not (seg / "frames").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
