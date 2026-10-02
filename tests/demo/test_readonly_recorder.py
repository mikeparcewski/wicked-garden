"""The demo recorder is read-only against the app it films (wicked-crew#565, wicked-studio#373).

The unit half runs anywhere Node does. The end-to-end half records a one-segment storyline that
presses a form's submit button on a local server which counts the writes it receives; it needs the
demo deps (Playwright in the garden cache) and ffmpeg, and is skipped without them.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "scripts" / "demo"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _node(script: str) -> str:
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=DEMO, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


@needs_node
def test_the_guard_blocks_every_write_except_to_the_fixture_origin():
    got = json.loads(_node(
        "import { blocks } from './readonly.mjs';"
        "const u = 'http://127.0.0.1:7701/api/v1/runs', fx = 'http://127.0.0.1:7701';"
        "console.log(JSON.stringify({"
        " get: blocks('GET', u, null), head: blocks('head', u, null), options: blocks('OPTIONS', u, null),"
        " post: blocks('POST', u, null), put: blocks('PUT', u, null), patch: blocks('PATCH', u, null),"
        " del: blocks('DELETE', u, null), otherOrigin: blocks('POST', 'https://api.example.com/x', fx),"
        " fixture: blocks('POST', u, fx), fixtureDelete: blocks('DELETE', u, fx),"
        " otherPort: blocks('POST', 'http://127.0.0.1:7702/api/v1/runs', fx),"
        " otherHostName: blocks('POST', 'http://localhost:7701/api/v1/runs', fx),"
        " data: blocks('POST', 'data:text/plain,x', null) }));"
    ))
    assert got == {
        "get": False, "head": False, "options": False,
        "post": True, "put": True, "patch": True, "del": True, "otherOrigin": True,
        "fixture": False, "fixtureDelete": False, "otherPort": True, "otherHostName": True,
        "data": False,
    }


@needs_node
def test_a_page_websocket_frame_is_blocked_unless_it_goes_to_the_fixture_origin():
    got = json.loads(_node(
        "import { blocksFrame } from './readonly.mjs';"
        "const fx = 'http://127.0.0.1:7701';"
        "console.log(JSON.stringify({"
        " none: blocksFrame('ws://127.0.0.1:7701/ws', null), fixture: blocksFrame('ws://127.0.0.1:7701/ws', fx),"
        " secure: blocksFrame('wss://127.0.0.1:7701/ws', fx), foreign: blocksFrame('ws://127.0.0.1:9/ws', fx),"
        " tls: blocksFrame('wss://h.localhost/ws', 'https://h.localhost') }));"
    ))
    assert got == {"none": True, "fixture": False, "secure": True, "foreign": True, "tls": False}


@needs_node
def test_the_fixture_origin_is_a_loopback_http_origin_or_it_is_refused():
    got = json.loads(_node(
        "import { fixtureOrigin } from './readonly.mjs';"
        "const t = (u) => { try { return fixtureOrigin(u); } catch (e) { return 'refused: ' + e.message; } };"
        "console.log(JSON.stringify({"
        " path: t('http://127.0.0.1:4310/app/'), localhost: t('http://localhost:4310'), v6: t('http://[::1]:4310'),"
        " remote: t('https://example.com'), lan: t('http://192.168.1.5:3000'), file: t('file:///tmp/x'),"
        " junk: t('not a url'), none: t(undefined) }));"
    ))
    assert got["path"] == "http://127.0.0.1:4310"
    assert got["localhost"] == "http://localhost:4310"
    assert got["v6"] == "http://[::1]:4310"
    assert got["none"] is None
    for k in ("remote", "lan", "file", "junk"):
        assert got[k].startswith("refused: "), (k, got[k])
        assert "loopback" in got[k], (k, got[k])


@needs_node
def test_there_is_no_env_switch_that_lifts_the_guard():
    got = json.loads(_node(
        "import * as m from './readonly.mjs';"
        "console.log(JSON.stringify(Object.keys(m).sort()));"
    ))
    assert "writesAllowed" not in got and "ALLOW_WRITES_ENV" not in got and "armReadOnly" not in got
    assert "armGuard" in got
    name = "DEMO_ALLOW" + "_WRITES"
    for sub in ("scripts", "skills", "tests", "docs"):
        assert (ROOT / sub).is_dir(), sub  # a negative grep over an absent path proves nothing
        hits = subprocess.run(["git", "grep", "-l", name, "--", sub], cwd=ROOT, capture_output=True, text=True)
        assert hits.stdout == "", f"{name} still named in {hits.stdout}"


@needs_node
def test_the_failure_is_typed_and_names_the_request():
    got = json.loads(_node(
        "import { sideEffectError } from './readonly.mjs';"
        "const e = sideEffectError('02-launch', ['POST http://127.0.0.1:7701/api/v1/runs']);"
        "console.log(JSON.stringify({ code: e.code, message: e.message }));"
    ))
    assert got["code"] == "side_effect_blocked"
    assert got["message"].startswith("side_effect_blocked: segment 02-launch")
    assert "POST http://127.0.0.1:7701/api/v1/runs" in got["message"]
    assert "--fixture-origin" in got["message"]


def _deps_installed() -> bool:
    """Where the recorder itself looks (scripts/demo/_playwright.mjs DEPS_DIR), so a cache placed by
    WICKED_GARDEN_CACHE_DIR or XDG_CACHE_HOME is found too."""
    if shutil.which("node") is None:
        return False
    out = subprocess.run(
        ["node", "--input-type=module", "-e", "import { DEPS_DIR } from './_playwright.mjs'; console.log(DEPS_DIR);"],
        cwd=DEMO, capture_output=True, text=True, timeout=60,
    )
    return out.returncode == 0 and (Path(out.stdout.strip()) / "node_modules" / "playwright").is_dir()


class _App(http.server.BaseHTTPRequestHandler):
    writes: list[str] = []

    def log_message(self, *_args):  # quiet
        pass

    def do_GET(self):
        body = (b"<!doctype html><html><body><h1>Runs</h1>"
                b"<form method='post' action='/api/runs'><button type='submit'>Launch</button></form>"
                b"</body></html>")
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        _App.writes.append(self.path)
        self.send_response(204)
        self.end_headers()


@needs_node
@pytest.mark.skipif(shutil.which("ffmpeg") is None or not _deps_installed(),
                    reason="needs ffmpeg and the demo deps (wicked-garden run scripts/demo/setup.mjs)")
def test_a_recording_that_presses_submit_sends_no_write_and_fails_typed(tmp_path):
    _App.writes = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    story = tmp_path / "storyline.mjs"
    story.write_text(
        "export default { title: 'demo', baseUrl: %s, segments: [\n"
        "  { key: '01-launch', title: 'Launch a run', async run(ctx) {\n"
        "      await ctx.click(ctx.app.getByRole('button', { name: 'Launch' }));\n"
        "      await ctx.hold(800);\n"
        "  } },\n"
        "] };\n" % json.dumps(base)
    )
    try:
        out = subprocess.run(
            ["node", str(DEMO / "record.mjs"), str(story), "--out", str(tmp_path / "demo-video")],
            capture_output=True, text=True, timeout=240,
        )
    finally:
        server.shutdown()
    assert out.returncode != 0, out.stdout
    assert "side_effect_blocked: segment 01-launch" in out.stderr, out.stderr[-2000:]
    assert f"POST {base}/api/runs" in out.stderr
    assert _App.writes == [], "the app received a write from the recorder"
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    assert not (seg / "segment.mp4").exists(), "a blocked segment is never kept as video"
    guard = json.loads((seg / "guard.json").read_text())
    assert guard["readOnly"] is True and guard["blocked"] == [f"POST {base}/api/runs"]


class _WsApp(http.server.BaseHTTPRequestHandler):
    """A page whose Launch button sends a WebSocket frame, and a bare RFC 6455 server that counts the
    frames it receives and pushes one frame of its own (a live view the recording must still see)."""
    frames: list[bytes] = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.headers.get("Upgrade", "").lower() == "websocket":
            key = self.headers["Sec-WebSocket-Key"]
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            self.wfile.write(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                             b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
            self.wfile.write(b"\x81\x04live")
            self.wfile.flush()
            while True:
                head = self.rfile.read(2)
                if len(head) < 2 or head[0] & 0x0F == 0x8:
                    return
                n = head[1] & 0x7F
                if n == 126:
                    n = int.from_bytes(self.rfile.read(2), "big")
                mask = self.rfile.read(4)
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(self.rfile.read(n)))
                _WsApp.frames.append(data)
        body = (b"<!doctype html><html><body><h1 id='h'>Runs</h1><button id='go'>Launch</button><script>"
                b"const ws = new WebSocket(location.origin.replace('http', 'ws') + '/ws');"
                b"ws.onmessage = (e) => { document.getElementById('h').textContent = 'Runs ' + e.data; };"
                b"document.getElementById('go').onclick = () => ws.send(JSON.stringify({action: 'launch'}));"
                b"</script></body></html>")
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _record(tmp_path, base: str, body: str, *args: str):
    story = tmp_path / "storyline.mjs"
    story.write_text(
        "export default { title: 'demo', baseUrl: %s, segments: [\n"
        "  { key: '01-launch', title: 'Launch a run', async run(ctx) {\n%s\n  } },\n"
        "] };\n" % (json.dumps(base), body)
    )
    return subprocess.run(
        ["node", str(DEMO / "record.mjs"), str(story), *args, "--out", str(tmp_path / "demo-video")],
        capture_output=True, text=True, timeout=240,
    )


needs_recorder = pytest.mark.skipif(shutil.which("ffmpeg") is None or not _deps_installed(),
                                    reason="needs ffmpeg and the demo deps (wicked-garden run scripts/demo/setup.mjs)")


@needs_node
@needs_recorder
def test_a_blocked_write_that_times_out_the_storylines_wait_still_fails_typed_and_leaves_no_stale_take(tmp_path):
    _App.writes = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    seg = tmp_path / "demo-video" / "segments" / "01-launch"
    seg.mkdir(parents=True)
    (seg / "segment.mp4").write_bytes(b"an earlier take")
    try:
        out = _record(tmp_path, base,
                      "      const posted = ctx.waitForPost(/api\\/runs/, 8000);\n"
                      "      await ctx.click(ctx.app.getByRole('button', { name: 'Launch' }));\n"
                      "      await posted;", "01-launch")
    finally:
        server.shutdown()
    assert out.returncode != 0, out.stdout
    assert "side_effect_blocked: segment 01-launch" in out.stderr, out.stderr[-2000:]
    assert _App.writes == []
    assert not (seg / "segment.mp4").exists(), "the earlier take must not survive to be stitched"
    assert not (seg / "timeline.json").exists(), "a failed take leaves no timeline to re-encode"
    # ...but it keeps its own evidence, beside the segment and never where a stitch would pick it up.
    failed = seg / "failed-1"
    assert (failed / "segment.mp4").stat().st_size > 0, "a failed take keeps its video"
    failure = json.loads((failed / "failure.json").read_text())
    assert failure["segment"] == "01-launch" and failure["take"] == 1
    assert failure["code"] == "side_effect_blocked" and failure["blocked"] == [f"POST {base}/api/runs"]
    # --reencode and --stitch fail closed on the blocked take instead of rebuilding it, stitching it,
    # or stitching around it: with a video beside its guard and without one.
    for flag, video in (("--reencode", True), ("--stitch", True), ("--stitch", False)):
        (seg / "segment.mp4").unlink(missing_ok=True)
        if video:
            (seg / "segment.mp4").write_bytes(b"not this take")
        again = subprocess.run(
            ["node", str(DEMO / "record.mjs"), str(tmp_path / "storyline.mjs"), flag, "--out", str(tmp_path / "demo-video")],
            capture_output=True, text=True, timeout=120)
        assert again.returncode != 0 and "side_effect_blocked: segment 01-launch" in again.stderr, (flag, again.stderr[-1500:])
        assert not (tmp_path / "demo-video" / "demo.mp4").exists()


@needs_node
@needs_recorder
def test_a_websocket_frame_the_page_sends_is_blocked_and_the_servers_push_still_arrives(tmp_path):
    _WsApp.frames = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _WsApp)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        out = _record(tmp_path, base,
                      "      await ctx.waitVisible(ctx.app.getByText('Runs live'), 10000);\n"
                      "      await ctx.click(ctx.app.getByRole('button', { name: 'Launch' }));\n"
                      "      await ctx.hold(800);")
    finally:
        server.shutdown()
    assert out.returncode != 0, out.stdout
    assert "side_effect_blocked: segment 01-launch" in out.stderr, out.stderr[-2000:]
    assert f"WS send ws://127.0.0.1:{server.server_address[1]}/ws" in out.stderr
    assert _WsApp.frames == [], "the app received a frame from the recorder"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
