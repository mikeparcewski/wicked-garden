"""The demo recorder is read-only against the app it films (wicked-crew#565, wicked-studio#373).

The unit half runs anywhere Node does. The end-to-end half records a one-segment storyline that
presses a form's submit button on a local server which counts the writes it receives; it needs the
demo deps (Playwright in the garden cache) and ffmpeg, and is skipped without them.
"""

from __future__ import annotations

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
def test_the_guard_blocks_every_write_method_unless_writes_are_allowed():
    got = json.loads(_node(
        "import { blocks, writesAllowed } from './readonly.mjs';"
        "const u = 'http://127.0.0.1:7701/api/v1/runs';"
        "console.log(JSON.stringify({"
        " get: blocks('GET', u, false), head: blocks('head', u, false), options: blocks('OPTIONS', u, false),"
        " post: blocks('POST', u, false), put: blocks('PUT', u, false), patch: blocks('PATCH', u, false),"
        " del: blocks('DELETE', u, false), otherOrigin: blocks('POST', 'https://api.example.com/x', false),"
        " allowed: blocks('POST', u, true), data: blocks('POST', 'data:text/plain,x', false),"
        " envUnset: writesAllowed({}), envOne: writesAllowed({ DEMO_ALLOW_WRITES: '1' }),"
        " envTrue: writesAllowed({ DEMO_ALLOW_WRITES: 'true' }) }));"
    ))
    assert got == {
        "get": False, "head": False, "options": False,
        "post": True, "put": True, "patch": True, "del": True, "otherOrigin": True,
        "allowed": False, "data": False,
        "envUnset": False, "envOne": True, "envTrue": False,
    }


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
    assert "DEMO_ALLOW_WRITES=1" in got["message"]


def _deps_installed() -> bool:
    cache = os.environ.get("WICKED_DEMO_DEPS") or str(Path.home() / ".cache" / "wicked-garden" / "demo-deps")
    return (Path(cache) / "node_modules" / "playwright").is_dir()


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
    env = {k: v for k, v in os.environ.items() if k != "DEMO_ALLOW_WRITES"}
    try:
        out = subprocess.run(
            ["node", str(DEMO / "record.mjs"), str(story), "--out", str(tmp_path / "demo-video")],
            capture_output=True, text=True, timeout=240, env=env,
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
