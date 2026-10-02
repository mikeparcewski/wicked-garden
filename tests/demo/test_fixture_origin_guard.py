"""The recorder's one write door is the fixture origin, and a failed take keeps its evidence (WT-G1).

`--fixture-origin <loopback origin>` names the disposable app a walkthrough started: writes and page
WebSocket frames to exactly that origin pass; any other write is still aborted and listed. With no
fixture origin a demo is fully read-only, as before. A take that fails keeps its video and a
`failure.json` under `segments/<key>/failed-<take>/`, and is never stitched.

Needs node, ffmpeg and the demo deps (wicked-garden run scripts/demo/setup.mjs); skipped without them.
"""

from __future__ import annotations

import http.server
import json
import subprocess
import threading

import pytest

from tests.demo.test_readonly_recorder import DEMO, _App, _WsApp, _record, needs_node, needs_recorder


class _Foreign(http.server.BaseHTTPRequestHandler):
    """A second app on another port: the recording must never write to it."""
    writes: list[str] = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        _Foreign.writes.append(self.path)
        self.send_response(204)
        self.end_headers()


class _CrossApp(_App):
    """The fixture's page, whose form posts to the foreign app."""
    action = ""

    def do_GET(self):
        body = (b"<!doctype html><html><body><h1>Runs</h1><form method='post' action='"
                + _CrossApp.action.encode() + b"'><button type='submit'>Launch</button></form></body></html>")
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


PRESS = ("      await ctx.click(ctx.app.getByRole('button', { name: 'Launch' }));\n"
         "      await ctx.hold(800);")


@needs_node
@needs_recorder
def test_a_write_to_the_fixture_origin_passes_and_the_recording_says_so(tmp_path):
    _App.writes = []
    server, base = _serve(_App)
    try:
        out = _record(tmp_path, base, PRESS, "--fixture-origin", base + "/")
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    assert _App.writes == ["/api/runs"], "the fixture did not receive the write"
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    assert (seg / "segment.mp4").stat().st_size > 0
    guard = json.loads((seg / "guard.json").read_text())
    assert guard["readOnly"] is False and guard["writableOrigin"] == base and guard["blocked"] == []
    assert guard["failed"] is False and guard["take"] == 1
    rec = json.loads((tmp_path / "demo-video" / "recording.json").read_text())
    assert rec["readOnly"] is False and rec["segments"] == {"01-launch": "fixture-writable"}


@needs_node
@needs_recorder
def test_a_write_to_any_other_origin_is_blocked_and_listed_even_with_a_fixture(tmp_path):
    _Foreign.writes = []
    foreign, foreign_base = _serve(_Foreign)
    _CrossApp.action = foreign_base + "/api/runs"
    fixture, base = _serve(_CrossApp)
    try:
        out = _record(tmp_path, base, PRESS, "--fixture-origin", base)
    finally:
        fixture.shutdown()
        foreign.shutdown()
    assert out.returncode != 0, out.stdout
    assert "side_effect_blocked: segment 01-launch" in out.stderr, out.stderr[-2000:]
    assert f"POST {foreign_base}/api/runs" in out.stderr
    assert _Foreign.writes == [], "the foreign app received a write from the recorder"
    guard = json.loads((tmp_path / "demo-video" / "segments" / "01-launch" / "guard.json").read_text())
    assert guard["blocked"] == [f"POST {foreign_base}/api/runs"]


WS_PRESS = ("      await ctx.waitVisible(ctx.app.getByText('Runs live'), 10000);\n"
            "      await ctx.click(ctx.app.getByRole('button', { name: 'Launch' }));\n"
            "      await ctx.hold(800);")


@needs_node
@needs_recorder
def test_a_websocket_frame_to_the_fixture_origin_passes(tmp_path):
    _WsApp.frames = []
    server, base = _serve(_WsApp)
    try:
        out = _record(tmp_path, base, WS_PRESS, "--fixture-origin", base)
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    assert _WsApp.frames == [b'{"action":"launch"}']


@needs_node
@needs_recorder
def test_a_websocket_frame_to_another_origin_is_blocked_and_listed(tmp_path):
    _WsApp.frames = []
    server, base = _serve(_WsApp)
    other, other_base = _serve(_Foreign)
    try:
        out = _record(tmp_path, base, WS_PRESS, "--fixture-origin", other_base)
    finally:
        server.shutdown()
        other.shutdown()
    assert out.returncode != 0, out.stdout
    assert f"WS send ws://127.0.0.1:{server.server_address[1]}/ws" in out.stderr, out.stderr[-2000:]
    assert _WsApp.frames == []


@needs_node
def test_a_remote_fixture_origin_is_refused_before_recording(tmp_path):
    out = _record(tmp_path, "http://127.0.0.1:9", PRESS, "--fixture-origin", "https://example.com")
    assert out.returncode == 2, out.stderr
    assert "loopback" in out.stderr
    assert not (tmp_path / "demo-video" / "segments" / "01-launch").exists()


@needs_node
@needs_recorder
def test_a_failed_take_keeps_its_video_and_failure_and_is_never_stitched(tmp_path):
    server, base = _serve(_App)
    fail = "      await ctx.waitVisible(ctx.app.getByText('No such heading'), 1500);"
    try:
        first = _record(tmp_path, base, fail, "01-launch")
        second = _record(tmp_path, base, fail, "01-launch")
    finally:
        server.shutdown()
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    for take, out in ((1, first), (2, second)):
        assert out.returncode != 0, out.stdout
        failed = seg / f"failed-{take}"
        assert (failed / "segment.mp4").stat().st_size > 0, f"take {take} kept no video"
        failure = json.loads((failed / "failure.json").read_text())
        assert failure["segment"] == "01-launch" and failure["take"] == take
        assert "No such heading" in failure["message"] and failure["blocked"] == []
        assert failure["failed_at_sec"] >= 0
        assert not (failed / "frames").exists(), "the failed take's raw frames are not kept beside its video"
    assert not (seg / "segment.mp4").exists()
    assert not (seg / "timeline.json").exists()
    assert json.loads((seg / "guard.json").read_text())["failed"] is True
    # The stitch refuses it (and so does a re-encode), even with a video planted where a good take would be.
    (seg / "segment.mp4").write_bytes(b"not this take")
    for flag in ("--stitch", "--reencode"):
        again = subprocess.run(
            ["node", str(DEMO / "record.mjs"), str(tmp_path / "storyline.mjs"), flag, "--out", str(tmp_path / "demo-video")],
            capture_output=True, text=True, timeout=120)
        assert again.returncode != 0, (flag, again.stdout)
        assert "failed_take: segment 01-launch" in again.stderr and "failed-2" in again.stderr, (flag, again.stderr[-1500:])
    assert not (tmp_path / "demo-video" / "demo.mp4").exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
