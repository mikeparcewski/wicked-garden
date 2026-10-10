#!/usr/bin/env python3
"""Run the editor-plugin conformance cases against every editor in a pack (DES-artifact-editor-plugins §12.1).

    wicked-garden run scripts/editor/conformance.py --pack <pack dir> [--host-url <crew URL> | --studio-dist <dir>]
        [--timeout 120] [--json]

The cases run in headless Chromium against studio's own **conformance host page**
(``/editors/conformance``: the real plugin host, its sandboxed frame, its MessagePort handshake, its
grants check, over a scripted in-memory page). This script serves that page on a local origin —
proxied from a wicked-crew daemon (``--host-url``, else ``$WICKED_CREW_URL``), or from a studio
``dist`` directory (``--studio-dist``) — and serves the candidate's entry itself on the editor
bundle route, hash-checked and with the third-party bundle policy (no network at all). Nothing is
installed, registered or written outside a temporary directory.

Cases, per editor (the plugin's half of §12.1; the host-control cases 13-18 belong to studio's CI):

  0  manifest      wicked-garden's ``pack check`` passes (schema, entry inside the pack, hash, size,
                   nothing loaded from outside it, kinds, sizes, permissions)
  1  handshake     ``plugin.ready`` within the host's 3 s, once; nothing on ``window`` after the port
  2  sizes         inline → full → pane without a reload or a re-read
  3  no-network    0 requests from the frame beyond its own entry
  4  permissions   every grant withdrawn mid-session, then a change: it keeps answering, and any
                   request it makes is refused ``not_granted`` (never acted on)
  5  typing        typing a sentence into it yields exactly ONE ``ui.typed``, the rest lands in the
                   composer, and 0 writes, drafts or selections; Backspace/Delete do nothing
  6  forwarding    Escape and Mod+K pressed in it reach the host as ``ui.key``
  8  strict-input  malformed host messages leave it alive
  9  liveness      it answers ``host.ping`` over a full ping period
  10 keyboard      every control in it can take focus (axe is not run: a reported gap)
  11 theme         a ``host.theme`` change leaves it alive, with no running animation
  12 hash-pinned   a wrong pinned hash never starts it

Case 7 (a scripted edit) needs the editor's own UI and is not run here: an editor asking for
``artifact.write`` gets it reported as a gap for its author's tests.

Prints one JSON report ``{ok, pack, host, editors: [{id, version, sha256, ok, cases, gaps}]}``.
Exit 0 every editor passed, 1 a case failed, 2 bad arguments or an unreadable pack, 3 no headless
browser (fail closed: an editor is never reported conformant without the run).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.server
import json
import mimetypes
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from _pack import PackError, editors_of, entry_path, read_manifest  # noqa: E402

# The third-party bundle policy, as wicked-crew serves it (crew `editors/csp.ts`, no `https:` media).
BUNDLE_CSP = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
              "img-src data: blob:; media-src blob:; font-src data:; frame-src blob: data: about:; "
              "child-src blob: data: about:; connect-src 'none'; form-action 'none'; base-uri 'none'; "
              "worker-src 'none'; manifest-src 'none'")
W, H = 1440, 700
PING_PERIOD_MS = 11_500
LOG = ("() => (window.__wickedEditor?.log ?? []).map(e => ({kind: e.kind, type: e.type ?? null, "
       "code: e.code ?? null, why: e.why ?? e.reason ?? null}))")
COMPOSER = "() => window.__wickedEditor?.composer() ?? null"
JUNK = ["null", "'x'", "{p:'wicked.editor'}", "{p:'wicked.editor',v:1,type:'nonsense',payload:{}}",
        "{p:'wicked.editor',v:1,type:'host.size',payload:null}", "{p:'wicked.editor',v:1,type:'host.theme'}"]


class CaseFailed(Exception):
    pass


# ── the local origin ───────────────────────────────────────────────────────────────────────

def make_server(candidates: dict[tuple[str, str], tuple[bytes, str]], host_url: str | None, dist: Path | None):
    """A local origin: the candidate entries on the bundle route, everything else from the host."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):  # quiet
            return

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            if ctype.startswith("text/html") and not (extra or {}).get("Content-Security-Policy"):
                origin = f"http://{self.headers.get('Host', '127.0.0.1')}"
                # The shell's frame-src (crew `shellCsp`): a frame may point only at the bundle route.
                self.send_header("Content-Security-Policy", f"frame-src {origin}/api/v1/editors/ blob: data:")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            url = urllib.parse.urlparse(self.path)
            parts = url.path.split("/")
            if len(parts) == 7 and parts[1:4] == ["api", "v1", "editors"] and parts[6] == "entry":
                found = candidates.get((urllib.parse.unquote(parts[4]), urllib.parse.unquote(parts[5])))
                if found is None:
                    return self._send(404, b'{"error":"no such editor bundle"}', "application/json")
                body, sha = found
                if (urllib.parse.parse_qs(url.query).get("sha") or [""])[0] != sha:
                    return self._send(409, b'{"code":"bundle_hash_mismatch"}', "application/json")
                return self._send(200, body, "text/html; charset=utf-8", {
                    "Content-Security-Policy": BUNDLE_CSP, "Cross-Origin-Resource-Policy": "same-origin",
                    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
            if host_url is not None:
                return self._proxy()
            return self._static(url.path)

        def _proxy(self) -> None:
            try:
                req = urllib.request.Request(host_url + self.path, headers={"Accept": self.headers.get("Accept", "*/*")})
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (the operator's own daemon)
                    return self._send(r.status, r.read(), r.headers.get("Content-Type", "application/octet-stream"))
            except urllib.error.HTTPError as e:
                return self._send(e.code, e.read(), e.headers.get("Content-Type", "application/json"))
            except (urllib.error.URLError, OSError) as e:
                return self._send(502, json.dumps({"error": f"host unreachable: {e}"}).encode(), "application/json")

        def _static(self, path: str) -> None:
            if path.startswith("/api/") or path == "/ws":
                return self._send(404, b'{"error":"not served by the conformance origin"}', "application/json")
            assert dist is not None
            root = dist.resolve()
            target = (root / urllib.parse.unquote(path).lstrip("/")).resolve()
            if root not in target.parents or not target.is_file():
                target = (root / "index.html").resolve()  # the SPA's client routes
                if root not in target.parents or not target.is_file():
                    return self._send(404, b'{"error":"the studio dist has no index.html inside it"}', "application/json")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype == "text/html":
                ctype = "text/html; charset=utf-8"
            return self._send(200, target.read_bytes(), ctype)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ── the cases ──────────────────────────────────────────────────────────────────────────────

def run_editor(browser, origin: str, editor: dict, sha: str, report: dict) -> None:
    eid, version, title = editor["id"], editor["version"], editor.get("title") or editor["id"]
    perms = [p.get("id") for p in editor.get("permissions", []) if isinstance(p, dict)]
    grants = [p for p in perms if p != "network.media"]
    cases: dict = report["cases"]

    def check(name: str, ok: bool, **detail) -> None:
        cases[name] = {"ok": bool(ok), **detail}
        if not ok:
            raise CaseFailed(name)

    def url(sha_value: str, grant_list: list[str]) -> str:
        q = {"editor": eid, "version": version, "sha": sha_value, "title": title, "grants": ",".join(grant_list)}
        return f"{origin}/editors/conformance?{urllib.parse.urlencode(q)}"

    # Reduced motion on: the host passes it in host.hello's prefs, and case 11 then requires no animation.
    page = browser.new_page(viewport={"width": W, "height": H}, reduced_motion="reduce")
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    frame_requests: list[str] = []
    page.on("request", lambda r: frame_requests.append(r.url)
            if r.frame is not None and r.frame != page.main_frame and "/entry?" not in r.url else None)

    def log() -> list:
        return page.evaluate(LOG)

    def count(kind: str, type_: str | None = None) -> int:
        return sum(1 for e in log() if e["kind"] == kind and (type_ is None or e["type"] == type_))

    def alive() -> bool:
        return page.evaluate("() => window.__wickedEditor?.host()?.alive === true") and count("teardown") == 0

    try:
        t0 = time.time()
        page.goto(url(sha, grants), wait_until="networkidle")
        try:
            page.get_by_test_id("editor-host-page").wait_for(state="visible", timeout=15000)
        except Exception as exc:  # noqa: BLE001
            check("1-handshake", False, error=f"the conformance host page did not render: {exc}")
        try:
            page.wait_for_function("() => (window.__wickedEditor?.log ?? []).some(e => e.kind === 'handshake')", timeout=6000)
        except Exception:  # noqa: BLE001
            check("1-handshake", False, error="no plugin.ready the host accepted within its 3 s",
                  host_log=log()[-6:], torn=_torn(page))
        frame = page.frame_locator('[data-testid="editor-frame"]')
        frame.locator("body").wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(300)
        check("1-handshake", count("handshake") == 1 and count("ignored-window-message") == 0,
              seconds=round(time.time() - t0, 2), ignored_window_messages=count("ignored-window-message"))

        reads_before = page.evaluate("() => window.__wickedEditor.adapter.reads")
        for size in ("inline", "full", "pane"):
            page.evaluate(f"() => window.__wickedEditor.setSize('{size}')")
            page.wait_for_timeout(200)
        reads_after = page.evaluate("() => window.__wickedEditor.adapter.reads")
        check("2-sizes", count("load") == 1 and reads_after == reads_before and alive(),
              loads=count("load"), reads=[reads_before, reads_after])

        frame.locator("body").click(position={"x": 3, "y": 3})
        page.wait_for_timeout(150)
        # Baselines AFTER the focus click: a click that legitimately points at a part is not typing.
        typed_before = count("in", "ui.typed")
        head_before = page.evaluate("() => window.__wickedEditor.adapter.artifact().head")
        mutations = ("version.write", "version.fork", "version.undo")
        writes_before = sum(count("in", t) for t in mutations)
        drafts_before, sels_before = count("in", "composer.draft"), count("in", "selection.set")
        page.keyboard.type("approve this delete it", delay=50)
        page.wait_for_timeout(300)
        composer = page.evaluate(COMPOSER) or {}
        typed = count("in", "ui.typed") - typed_before
        writes = sum(count("in", t) for t in mutations) - writes_before
        drafts = count("in", "composer.draft") - drafts_before
        sels = count("in", "selection.set") - sels_before
        head = "() => window.__wickedEditor.adapter.artifact().head"
        head_moves = page.evaluate(head) - head_before
        frame.locator("body").click(position={"x": 3, "y": 3})
        page.wait_for_timeout(150)
        bs_before, bs_head = sum(count("in", t) for t in mutations), page.evaluate(head)
        page.keyboard.press("Backspace")
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        writes += sum(count("in", t) for t in mutations) - bs_before
        head_moves += page.evaluate(head) - bs_head
        check("5-typing", typed == 1 and composer.get("text") == "approve this delete it" and writes == 0 and drafts == 0
              and sels == 0 and head_moves == 0, typed=typed, composer=composer.get("text"), writes=writes,
              drafts=drafts, selections=sels, head_moves=head_moves)

        frame.locator("body").click(position={"x": 3, "y": 3})
        page.keyboard.press("Escape")
        page.keyboard.press("ControlOrMeta+k")
        page.keyboard.press("Alt+j")  # a navigation chord: forwardable
        page.wait_for_timeout(250)
        keys = (page.evaluate(COMPOSER) or {}).get("keys", [])
        # The decision chords (approve, reject, select for batch) must never be forwarded: the host drops
        # each one, and three drops tear the editor down.
        dropped_before = count("dropped", "ui.key")
        for chord in ("Alt+a", "Alt+r", "Alt+x"):
            frame.locator("body").click(position={"x": 3, "y": 3})
            page.keyboard.press(chord)
        page.wait_for_timeout(250)
        dropped = count("dropped", "ui.key") - dropped_before
        check("6-forwarding", keys[:3] == ["Escape", "Mod+K", "Alt+J"] and dropped == 0 and alive(), keys=keys,
              decision_chords_forwarded=dropped)

        errors_before = len(errors)
        for junk in JUNK:
            page.evaluate(f"() => window.__wickedEditor.inject({junk})")
        page.wait_for_timeout(300)
        check("8-strict-input", alive() and len(errors) == errors_before, uncaught=errors[errors_before:][:3])

        page.evaluate("() => window.__wickedEditor.setTheme({'--accent': '#aa0000'})")
        page.wait_for_timeout(300)
        anims = frame.locator("body").evaluate("() => document.getAnimations().length")
        check("11-theme", alive() and anims == 0, animations=anims)

        controls = frame.locator("body").evaluate("""() => [...document.querySelectorAll(
            'button, a[href], input, select, textarea, [tabindex]')]
            .filter(el => !el.matches(':disabled') && !el.closest('[inert]') && el.tabIndex >= 0 && el.getClientRects().length > 0
                          && getComputedStyle(el).visibility !== 'hidden')
            .map(el => { el.focus(); return {tag: el.tagName.toLowerCase(), tab: el.tabIndex, focused: document.activeElement === el}; })""")
        check("10-keyboard", all(c["tab"] >= 0 and c["focused"] for c in controls), controls=len(controls),
              unreachable=[c for c in controls if not (c["tab"] >= 0 and c["focused"])][:5])

        # 4: every grant withdrawn, then a change lands; only what happens AFTER the withdrawal counts,
        # and the liveness wait below (a full ping period) proves it still answers afterwards.
        mark = len(log())
        acted_before = count("written")
        errors_mark = len(errors)
        page.evaluate("() => window.__wickedEditor.host().setGrants([])")
        page.evaluate("() => window.__wickedEditor.agentVersion()")
        page.wait_for_timeout(600)
        after = log()[mark:]
        refused = [e for e in after if e["kind"] == "refused"]
        acted = count("written") - acted_before
        check("4-permissions", alive() and acted == 0 and all(e["code"] == "not_granted" for e in refused)
              and len(errors) == errors_mark, refused_not_granted=len(refused), writes=acted, uncaught=errors[errors_mark:][:3])

        # 9: a full ping period answered, no uncaught error since the withdrawal, and still nothing on
        # `window` after the port (a late window message is as much a breach as an early one).
        page.wait_for_timeout(PING_PERIOD_MS)
        check("9-liveness", alive() and len(errors) == errors_mark and count("ignored-window-message") == 0,
              uncaught=errors[errors_mark:][:3], ignored_window_messages=count("ignored-window-message"))

        check("3-no-network", frame_requests == [], requests=frame_requests[:10])


        page.goto(url("0" * 64, grants), wait_until="networkidle")
        torn = _torn(page, wait=True)
        check("12-hash-pinned", torn is not None and count("handshake") == 0, torn=torn)
    except CaseFailed:
        pass
    finally:
        if errors:
            report["page_errors"] = errors[:5]
        page.close()


def _torn(page, wait: bool = False):
    try:
        loc = page.get_by_test_id("editor-torn")
        if wait:
            loc.wait_for(state="visible", timeout=8000)
        return loc.inner_text() if loc.count() else None
    except Exception:  # noqa: BLE001
        return None


def manifest_case(pack: Path) -> dict:
    """Case 0: garden's own `pack check` (the same gate wicked-crew runs before an install)."""
    try:
        from pack.check import check_pack  # noqa: PLC0415 (scripts/ on the path above)
    except ImportError as exc:
        return {"ok": False, "error": f"pack check unavailable: {exc}"}
    findings = check_pack(pack, garden_root=HERE.parents[1])
    errs = [f.render() for f in findings if f.level == "error"]
    return {"ok": not errs, "errors": errs[:10]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--host-url", default=None, help="a wicked-crew daemon serving studio (default $WICKED_CREW_URL)")
    parser.add_argument("--studio-dist", type=Path, default=None, help="serve studio's built dist instead of a daemon")
    parser.add_argument("--json", action="store_true", help="print the report as JSON (the default output)")
    args = parser.parse_args(argv)

    def out(report: dict, code: int) -> int:
        print(json.dumps(report, indent=2))
        return code

    try:
        manifest = read_manifest(args.pack)
        editors = editors_of(manifest)
        entries = {}
        for e in editors:
            # ONE read: the bytes served to the browser are the bytes hashed into the report (codex).
            body = entry_path(args.pack, e).read_bytes()
            entries[(str(e.get("id")), str(e.get("version")))] = (body, hashlib.sha256(body).hexdigest())
    except PackError as exc:
        return out({"ok": False, "pack": str(args.pack), "error": str(exc)}, 2)
    host_url = None
    if args.studio_dist is None:
        host_url = (args.host_url or os.environ.get("WICKED_CREW_URL") or "").rstrip("/") or None
        if host_url is None:
            return out({"ok": False, "pack": str(args.pack), "error": "no host: pass --host-url <a wicked-crew daemon URL> "
                        "(crew sets $WICKED_CREW_URL in every governed unit) or --studio-dist <dir> — never a guessed port"}, 2)
    else:
        args.studio_dist = args.studio_dist.resolve()
    if args.studio_dist is not None and not (args.studio_dist / "index.html").is_file():
        return out({"ok": False, "pack": str(args.pack), "error": f"{args.studio_dist} holds no index.html"}, 2)

    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return out({"ok": False, "pack": str(args.pack), "error": "no headless browser: the Python playwright package is "
                    "not installed (pip install playwright && playwright install chromium); refusing to report conformance "
                    "without the run"}, 3)

    report: dict = {"ok": False, "pack": str(args.pack), "host": host_url or str(args.studio_dist), "editors": []}
    server = make_server(entries, host_url, args.studio_dist)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    m0 = manifest_case(args.pack)
    try:
        with tempfile.TemporaryDirectory(prefix="wg-editor-conformance-") as tmp, sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                report["error"] = f"no headless browser: chromium did not start ({str(exc).splitlines()[0]})"
                return out(report, 3)
            with contextlib.suppress(Exception):
                os.chdir(tmp)  # nothing the browser writes lands in the pack
            for e in editors:
                er = {"id": e.get("id"), "version": e.get("version"),
                      "sha256": entries[(str(e.get("id")), str(e.get("version")))][1],
                      "cases": {"0-manifest": m0}, "gaps": [
                          "case 7 (a scripted edit) is the editor's own UI: not run here",
                          "case 2 checks no reload or re-read across sizes, not each size's layout",
                          "case 6 does not walk Tab/Shift+Tab off the editor's edges",
                          "case 5 presses Backspace/Delete with no part known to be selected (a generic editor exposes "
                          "no common part selector); the editor's own tests must cover a selected part",
                          "case 11 checks the editor survives a theme change with no animation under reduced motion, "
                          "not that it applied the tokens",
                          "case 10 checks focus reach only; axe is not run",
                          "case 3 cannot see WebRTC/STUN or DNS prefetch (DES §12.1)",
                          "cases 13-18 test the host against a hostile bundle: studio CI runs them"]}
                if m0["ok"]:
                    run_editor(browser, origin, e, er["sha256"], er)
                expected = 12  # cases 0-6 and 8-12
                er["ok"] = len(er["cases"]) == expected and all(c.get("ok") for c in er["cases"].values())
                report["editors"].append(er)
            browser.close()
    finally:
        server.shutdown()
    report["ok"] = bool(report["editors"]) and all(e["ok"] for e in report["editors"])
    return out(report, 0 if report["ok"] else 1)


if __name__ == "__main__":
    sys.exit(main())
