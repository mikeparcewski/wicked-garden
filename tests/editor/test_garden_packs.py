"""The editor plugin packs garden ships (``packs/``), and the conformance runner's slow-host and options-mount rules.

``packs/garden-mcp-inspector`` is the MCP inspector (DES-EDITOR-PLUGIN-CONTRACT-001 §9-§10 slice 5) built the way
the editor-plugin builder builds any plugin: ``scaffold.py`` made its manifest, README and entry, and the inspector
replaced the entry's YOUR EDITOR part. These tests re-run the scaffold with the pack's own declaration and hold the
manifest (all but the entry hash), the README and the entry's surfaces stamp to what it produces; the entry's protocol
behaviour is held by the conformance run. The browser cases need Chromium and a protocol-2 studio dist
(``WICKED_STUDIO_DIST``) whose conformance page takes ``surface``/``tab``.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "editor"))

import conformance  # noqa: E402
from pack.check import check_pack  # noqa: E402

SCRIPTS = REPO / "scripts" / "editor"
PACK = REPO / "packs" / "garden-mcp-inspector"
ENTRY = PACK / "editors" / "garden-mcp-inspector" / "index.html"
SURFACES_RE = re.compile(r"  const SURFACES = (\{.*?\n\});\n", re.S)


def run(script: str, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("WICKED_CREW_URL", conformance.TIMEOUT_ENV)}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, env=env, timeout=600)


def manifest() -> dict:
    return json.loads((PACK / "wicked-pack.json").read_text(encoding="utf-8"))


# ── the MCP inspector pack ───────────────────────────────────────────────────────────────────

def test_the_mcp_inspector_pack_is_what_the_scaffold_makes(tmp_path):
    m = manifest()
    e = m["editors"][0]
    decl = tmp_path / "surfaces.json"
    decl.write_text(json.dumps(e["surfaces"]), encoding="utf-8")
    out = tmp_path / "pack"
    done = run("scaffold.py", "--vendor", m["vendor"], "--id", e["id"], "--title", e["title"], "--kinds", ",".join(e["kinds"]),
               "--permissions", ",".join(p["id"] for p in e["permissions"]), "--surfaces", str(decl),
               "--version", e["version"], "--out", str(out))
    assert done.returncode == 0, done.stderr
    made = json.loads((out / "wicked-pack.json").read_text(encoding="utf-8"))
    # The manifest, but for the entry's hash (the inspector replaced the template's viewer), is the scaffold's own.
    assert made["editors"][0].pop("sha256") != e["sha256"]
    ours = json.loads(json.dumps(m))
    ours["editors"][0].pop("sha256")
    assert ours == made
    assert (out / "README.md").read_bytes() == (PACK / "README.md").read_bytes()
    # The entry's declaration is the scaffold's stamp, byte for byte (it must equal the manifest's, case 13).
    stamped = SURFACES_RE.search((out / ENTRY.relative_to(PACK)).read_text(encoding="utf-8"))
    shipped = SURFACES_RE.search(ENTRY.read_text(encoding="utf-8"))
    assert stamped and shipped and stamped.group(1) == shipped.group(1)


def test_the_mcp_inspector_pack_passes_pack_check_and_its_hash_is_pinned():
    assert [f.render() for f in check_pack(PACK, garden_root=REPO) if f.level == "error"] == []
    assert manifest()["editors"][0]["sha256"] == hashlib.sha256(ENTRY.read_bytes()).hexdigest()


def test_the_mcp_inspector_asks_for_exactly_what_it_uses():
    m = manifest()
    e = m["editors"][0]
    assert m["vendor"] == "garden" and not re.match(r"^wicked(?:$|-)", m["vendor"]) and m["name"].startswith("garden-")
    assert e["kinds"] == ["mcp-server"] and e["protocol"] == [1, 2] and e["sizes"] == ["inline", "pane", "full"]
    assert [p["id"] for p in e["permissions"]] == ["artifact.read", "mcp.session", "ui.fullscreen"]
    src = ENTRY.read_text(encoding="utf-8")
    # Each permission has the request that needs it (security-review rule of the skill), and nothing else is asked.
    assert "req('artifact.read'" in src and "req('mcp.request'" in src and "req('ui.fullscreen'" in src
    requested = set(re.findall(r"req\('([a-z.]+)'", src))
    assert requested == {"artifact.read", "mcp.request", "ui.fullscreen"}
    assert "innerHTML" not in src and "http://" not in src and "https://" not in src


def test_tools_call_leaves_only_from_the_call_buttons_click():
    src = ENTRY.read_text(encoding="utf-8")
    # The one tools/call is the Call button's (run(label, 'tools/call', …) builds a click handler); nothing on load,
    # on a timer or from host.action calls a tool.
    assert src.count("'tools/call'") == 1 and "run('Call ' + String(x.name), 'tools/call'" in src
    assert "setTimeout" not in src and "setInterval" not in src


# ── conformance: the page-load bound ─────────────────────────────────────────────────────────

def test_the_page_load_bound_comes_from_the_flag_then_the_environment_then_the_default():
    assert conformance.load_timeout(None, None) == conformance.DEFAULT_TIMEOUT_S == 120.0
    assert conformance.load_timeout(None, "300") == 300.0
    assert conformance.load_timeout(45, "300") == 45.0
    for bad in ("abc", "nan", "2", "4000"):
        with pytest.raises(ValueError):
            conformance.load_timeout(None, bad)


def test_a_bad_timeout_is_a_usage_error_before_any_browser_starts(tmp_path):
    assert run("scaffold.py", "--vendor", "acme", "--id", "acme-x", "--title", "X", "--kinds", "page",
               "--out", str(tmp_path / "p")).returncode == 0
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>")
    done = run("conformance.py", "--pack", str(tmp_path / "p"), "--studio-dist", str(tmp_path / "dist"),
               env_extra={conformance.TIMEOUT_ENV: "2"})
    assert done.returncode == 2 and "outside 5-1800" in json.loads(done.stdout)["error"]


def test_no_page_load_waits_for_network_idle():
    # A daemon keeps a socket and slow reads open: "network idle" never comes on a busy host (the 30 s timeouts).
    assert "networkidle" not in (SCRIPTS / "conformance.py").read_text(encoding="utf-8")


def _upstream():
    hits: list[str] = []

    class Up(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_a):
            return

        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            body = b"{}" if self.path.startswith("/api/") else b"console.log(1)"
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if self.path.startswith("/api/") else "text/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Up)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


def test_the_host_pages_own_files_are_read_from_the_daemon_once_and_api_reads_every_time():
    up, hits = _upstream()
    local = conformance.make_server({}, f"http://127.0.0.1:{up.server_address[1]}", None, 10)
    base = f"http://127.0.0.1:{local.server_address[1]}"
    try:
        for _ in range(3):
            assert urllib.request.urlopen(base + "/assets/app.js", timeout=10).read() == b"console.log(1)"
            urllib.request.urlopen(base + "/api/v1/health", timeout=10).read()
    finally:
        local.shutdown()
        up.shutdown()
    assert hits.count("/assets/app.js") == 1 and hits.count("/api/v1/health") == 3


def test_a_different_query_or_accept_is_its_own_cache_entry():
    up, hits = _upstream()
    local = conformance.make_server({}, f"http://127.0.0.1:{up.server_address[1]}", None, 10)
    base = f"http://127.0.0.1:{local.server_address[1]}"
    try:
        for target, accept in (("/a.js?v=1", "*/*"), ("/a.js?v=2", "*/*"), ("/a.js?v=1", "text/javascript"), ("/a.js?v=1", "*/*")):
            urllib.request.urlopen(urllib.request.Request(base + target, headers={"Accept": accept}), timeout=10).read()
    finally:
        local.shutdown()
        up.shutdown()
    assert hits == ["/a.js?v=1", "/a.js?v=2", "/a.js?v=1"]


def test_a_daemon_that_trickles_its_answer_is_cut_off_at_the_bound():
    class Slow(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_a):
            return

        def do_GET(self):  # noqa: N802 — headers at once, then one byte every 0.2 s for 4 s
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "20")
            self.end_headers()
            for _ in range(20):
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.2)

    up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    try:
        t0 = time.monotonic()
        code, body, _ = conformance._fetch(f"http://127.0.0.1:{up.server_address[1]}/slow", "*/*", 1.0)
        took = time.monotonic() - t0
    finally:
        up.shutdown()
    assert code == 504 and b"within 1 s" in body and took < 2.5


# ── conformance in the browser ───────────────────────────────────────────────────────────────

def _browser_ready() -> bool:
    try:
        import playwright.sync_api  # noqa: F401, PLC0415
    except ImportError:
        return False
    dist = os.environ.get("WICKED_STUDIO_DIST")
    return bool(dist) and (Path(dist) / "index.html").is_file()


needs_browser = pytest.mark.skipif(not _browser_ready(), reason="needs playwright + chromium and WICKED_STUDIO_DIST "
                                   "(a protocol-2 studio dist whose conformance page takes surface/tab)")


def conform(pack: Path, dist: str | None = None) -> tuple[int, dict]:
    done = run("conformance.py", "--pack", str(pack), "--studio-dist", dist or os.environ["WICKED_STUDIO_DIST"])
    return done.returncode, json.loads(done.stdout)


@needs_browser
def test_the_mcp_inspector_passes_every_case_and_mounts_each_options_tab():
    code, report = conform(PACK)
    cases = report["editors"][0]["cases"]
    assert code == 0, json.dumps(cases, indent=1)[-3000:]
    assert cases["14-card"]["hello"]["surface"] == "card"
    rows = cases["15-options"]["tabs"]
    assert [r["hello"]["tab"] for r in rows] == ["resources", "prompts", "log"]
    assert all(r["hello"]["surface"] == "options" for r in rows)
    assert rows[0]["host_tab"] == ["prompts", "log", "resources"] and rows[0]["loads"] == 1


@needs_browser
def test_a_host_page_that_drops_the_options_tab_fails_case_15(tmp_path):
    # The conformance page as an older studio serves it: the editor is mounted, but never told which tab it shows.
    dist = tmp_path / "dist"
    shutil.copytree(os.environ["WICKED_STUDIO_DIST"], dist)
    index = dist / "index.html"
    drop = ("<script>(() => { const u = new URL(location.href); if (u.searchParams.has('tab')) "
            "{ u.searchParams.delete('tab'); history.replaceState(null, '', u); } })();</script>")
    index.write_text(index.read_text(encoding="utf-8").replace("<head>", "<head>" + drop, 1), encoding="utf-8")
    code, report = conform(PACK, str(dist))
    rows = report["editors"][0]["cases"]["15-options"]["tabs"]
    assert code == 1 and report["editors"][0]["cases"]["15-options"]["ok"] is False
    assert all(r["hello"]["tab"] is None for r in rows)
    assert all(any("was not mounted as the options instance" in x for x in r["errors"]) for r in rows)


@needs_browser
def test_an_editor_cannot_forge_the_hello_the_frame_received(tmp_path):
    # Before its own handshake listener exists, the editor dispatches a synthetic hello claiming the options surface,
    # then replaces the natives a probe might call and poisons Object.prototype.toJSON. Cases 14 and 15 must still see
    # the hellos the host really sent.
    assert run("scaffold.py", "--vendor", "acme", "--id", "acme-forge", "--title", "Forge", "--kinds", "page",
               "--out", str(tmp_path / "p")).returncode == 0
    entry = tmp_path / "p" / "editors" / "acme-forge" / "index.html"
    forge = ("'use strict';\n  window.dispatchEvent(new MessageEvent('message', { data: { p: 'wicked.editor', type: 'host.hello', "
             "payload: { protocol: 2, surface: 'options', tab: 'parts' } }, ports: [new MessageChannel().port1] }));\n"
             "  JSON.stringify = () => '{\"surface\":\"options\"}'; Object.freeze = (o) => o; Object.hasOwn = () => true;\n"
             "  Object.defineProperty(Object.prototype, 'toJSON', { configurable: true, value: function () { "
             "return { protocol: 2, surface: 'options', tab: 'forged', mode: null }; } });\n")
    src = entry.read_text(encoding="utf-8")
    assert src.count("'use strict';\n") == 1
    entry.write_text(src.replace("'use strict';\n", forge, 1), encoding="utf-8")
    assert run("pin.py", str(tmp_path / "p")).returncode == 0
    code, report = conform(tmp_path / "p")
    cases = report["editors"][0]["cases"]
    assert cases["14-card"]["hello"]["surface"] == "card", json.dumps(cases["14-card"])
    assert cases["15-options"]["tabs"][0]["hello"] == {"protocol": 2, "surface": "options", "tab": "parts", "mode": None}
