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

Cases, per editor (the plugin's half of §12.1 and DES-EDITOR-PLUGIN-CONTRACT-001 §8.3; the host-control
cases against a hostile bundle belong to studio's CI):

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

Protocol 2 (an editor whose ``protocol`` lists 2; DES-EDITOR-PLUGIN-CONTRACT-001 §8.3):

  13 surfaces      the host negotiated 2, and the surfaces it renders from (``plugin.ready``'s) are the
                   manifest's, as canonical JSON; the labels pass the word and length rules
  14 card          it mounts as the card; with ``aspect:"auto"`` a ``ui.height`` arrives within 2 s and is
                   accepted; every ``verb:"plugin"`` action answers ``host.action`` within 2 s
  15 options       each plugin tab mounts as ``surface:'options', tab`` and survives ``host.selection``;
                   every controls tab's ``options.values`` is accepted, and a valid change gets a well-formed
                   answer within 2 s (applied or refused)
  16 full          ``host.surface`` card→full keeps the instance (no reload, no second ``plugin.ready``);
                   with modes, every ``host.mode`` is answered within 2 s with the same mode

Protocol 1 only:

  17 v1-compat     the host negotiated 1, and cases 1-12 passed under this protocol-2 host

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
import re
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
from _surfaces import SurfacesError, canonical_surfaces, parse_surfaces  # noqa: E402

# The third-party bundle policy, as wicked-crew serves it (crew `editors/csp.ts`, no `https:` media).
BUNDLE_CSP = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
              "img-src data: blob:; media-src blob:; font-src data:; frame-src blob: data: about:; "
              "child-src blob: data: about:; connect-src 'none'; form-action 'none'; base-uri 'none'; "
              "worker-src 'none'; manifest-src 'none'")
W, H = 1440, 700
SAFE_CTYPE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+(?:; ?charset=[A-Za-z0-9_-]+)?")
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
            # Only a plain media type goes into the header (an upstream value is never echoed raw).
            ctype = ctype if SAFE_CTYPE.fullmatch(ctype) else "application/octet-stream"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            if ctype.startswith("text/html") and not (extra or {}).get("Content-Security-Policy"):
                origin = f"http://127.0.0.1:{self.server.server_address[1]}"  # this server's own origin, never the Host header
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
        # What the host negotiated (a host before protocol 2 has no `negotiated`: it speaks 1).
        # null = a host before protocol 2 (it has no `negotiated`): case 17 then cannot be shown.
        report["negotiated"] = page.evaluate("() => window.__wickedEditor.host()?.negotiated ?? null")

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


def speaks(editor: dict, version: int) -> bool:
    protocol = editor.get("protocol")
    return isinstance(protocol, list) and version in protocol


def expected_cases(editor: dict) -> int:
    """0-6 and 8-12, plus 13-16 for a protocol-2 editor or 17 for a protocol-1 one."""
    return 12 + (4 if speaks(editor, 2) else 1)


HOST_ANSWER_S = 2.0
# On the HOST side, before any page script runs: every message a host MessagePort receives (the structured clone the
# editor actually transmitted, read from the event, never re-serialized) and every request the host posts, both on
# the page's clock. The host's API normalizes a reply (a `{}` reply to host.action reads as handled:false), so the
# editor's own answer is read here, correlated to the request by its id.
HOST_WIRE = """(() => {
  if (window.top !== window || window.__wgWire) return;
  const wire = window.__wgWire = { out: [], in: [] };
  const post = MessagePort.prototype.postMessage;
  MessagePort.prototype.postMessage = function (m, t) {
    if (m && typeof m === 'object' && typeof m.id === 'string' && typeof m.type === 'string') wire.out.push({ at: performance.now(), id: m.id, type: m.type });
    return post.call(this, m, t);
  };
  const d = Object.getOwnPropertyDescriptor(MessagePort.prototype, 'onmessage');
  Object.defineProperty(MessagePort.prototype, 'onmessage', { configurable: true, get() { return d.get.call(this); },
    set(fn) { d.set.call(this, typeof fn === 'function' ? function (ev) { wire.in.push({ at: performance.now(), m: ev.data }); return fn.call(this, ev); } : fn); } });
})();"""
# The reply to the newest host request of `type` sent after `t0`: a valid envelope with `re` = that request's id, ok,
# and a payload of the shape `{shape}` (a JS expression over `p`), and its delay from the request.
WIRE_REPLY = """([t0, type]) => {{ const w = window.__wgWire; if (!w) return {{ error: 'no wire hook' }};
  const req = w.out.filter(e => e.at >= t0 && e.type === type).at(-1); if (!req) return {{ error: 'no ' + type + ' request was sent' }};
  const ok = (p) => {shape};
  const r = w.in.find(e => e.m && e.m.re === req.id);
  if (!r) return {{ error: 'no reply to ' + req.id }};
  // A reply's envelope is exactly {{p, v, re, ok, payload}}: a `type` or `id` on it makes the host refuse it as ambiguous.
  const m = r.m, keys = Object.keys(m).sort().join(',');
  const valid = keys === 'ok,p,payload,re,v' && m.p === 'wicked.editor' && m.v === 1 && m.ok === true
    && m.payload !== null && typeof m.payload === 'object' && ok(m.payload);
  return {{ ms: r.at - req.at, valid, payload: m.payload ?? null, envelope: {{ p: m.p ?? null, v: m.v ?? null, ok: m.ok ?? null }} }}; }}"""
ACTION_SHAPE = "typeof p.handled === 'boolean' && (p.status === undefined || (typeof p.status === 'string' && p.status.length <= 120))"
CHANGE_SHAPE = "typeof p.applied === 'boolean' && Number.isInteger(p.rev) && p.values !== null && typeof p.values === 'object' && !Array.isArray(p.values)"
OPTIONS_WAIT_MS = 5000


def run_editor_v2(browser, origin: str, editor: dict, sha: str, report: dict) -> None:
    """Cases 13-16: the three surfaces of a protocol-2 editor, each in its own host instance."""
    eid, version, title = editor["id"], editor["version"], editor.get("title") or editor["id"]
    grants = [p.get("id") for p in editor.get("permissions", []) if isinstance(p, dict) and p.get("id") != "network.media"]
    cases: dict = report["cases"]
    try:
        declared = parse_surfaces(editor.get("surfaces"))
    except SurfacesError as exc:
        cases["13-surfaces"] = {"ok": False, "error": f"the manifest's surfaces are refused: {exc}"}
        return

    def check(name: str, ok: bool, **detail) -> None:
        cases[name] = {"ok": bool(ok), **detail}
        if not ok:
            raise CaseFailed(name)

    def open_page(**extra):
        q = {"editor": eid, "version": version, "sha": sha, "title": title, "grants": ",".join(grants), **extra}
        page = browser.new_page(viewport={"width": W, "height": H}, reduced_motion="reduce")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(HOST_WIRE)
        page.goto(f"{origin}/editors/conformance?{urllib.parse.urlencode(q)}", wait_until="networkidle")
        page.get_by_test_id("editor-host-page").wait_for(state="visible", timeout=15000)
        page.wait_for_function("() => (window.__wickedEditor?.log ?? []).some(e => e.kind === 'handshake')", timeout=6000)
        page.wait_for_timeout(300)
        return page, errors

    def count(page, kind: str, type_: str | None = None) -> int:
        return sum(1 for e in page.evaluate(LOG) if e["kind"] == kind and (type_ is None or e["type"] == type_))

    def size_of(page) -> str | None:
        return page.get_by_test_id("editor-artifact-frame").get_attribute("data-size")

    def timed(page, js: str):
        t0 = time.time()
        out = page.evaluate(js)
        return out, round(time.time() - t0, 2)

    def answered(page, js: str, type_: str, shape: str) -> dict:
        """Run a host request and read the editor's own reply as the host received it: correlated by id, a valid
        envelope, the payload's shape, and within 2 s of the request."""
        t0 = page.evaluate("() => performance.now()")
        out = page.evaluate(js)
        reply = page.evaluate(WIRE_REPLY.format(shape=shape), [t0, type_])
        ok = "error" not in reply and reply["valid"] and reply["ms"] <= HOST_ANSWER_S * 1000
        # host.action: the host itself must also have taken the reply (null = it refused or timed out).
        if type_ == "host.action":
            ok = ok and out is not None
        return {"answer": out, "reply": reply, "ok": ok}

    pages = []
    try:
        # 13: the declaration the host renders from is the manifest's.
        page, errors = open_page(surface="card")
        pages.append(page)
        negotiated = page.evaluate("() => window.__wickedEditor.host()?.negotiated ?? null")
        shown = page.evaluate("() => window.__wickedEditor.host()?.surfaces ?? null")
        same = shown is not None and canonical_surfaces(shown) == canonical_surfaces(declared)
        check("13-surfaces", negotiated == 2 and same, negotiated=negotiated,
              **({} if same else {"host": shown, "manifest": declared}))

        # 14: the card. The page mounts it as the card (its frame at the card's size), it reports its height when
        # it sizes itself, and every plugin action is answered in time.
        card = declared["card"]
        if card["aspect"] == "auto":
            try:
                page.wait_for_function("() => (window.__wickedEditor?.log ?? []).some(e => e.kind === 'in' && e.type === 'ui.height')",
                                       timeout=int(HOST_ANSWER_S * 1000))
            except Exception:  # noqa: BLE001 — reported as the case's detail below
                pass
        heights, dropped_h = count(page, "in", "ui.height"), count(page, "dropped", "ui.height")
        # §8.3: the first height within 2 s of the card starting (the handshake), by the host's own clock.
        height_ms = page.evaluate("""() => { const log = window.__wickedEditor?.log ?? [];
            const hs = log.find(e => e.kind === 'handshake'); const h = log.find(e => e.kind === 'in' && e.type === 'ui.height');
            return hs && h ? h.at - hs.at : null; }""")
        answers = []
        for a in card["actions"]:
            if a["verb"] != "plugin":
                continue
            r = answered(page, f"() => window.__wickedEditor.host().action({json.dumps(a['id'])})", "host.action", ACTION_SHAPE)
            answers.append({"id": a["id"], **r})
        late = [x for x in answers if not x["ok"]]
        on_time = card["aspect"] != "auto" or (heights >= 1 and height_ms is not None and height_ms <= HOST_ANSWER_S * 1000)
        check("14-card", size_of(page) == "inline" and dropped_h == 0 and on_time
              and not late and count(page, "teardown") == 0 and not errors,
              frame_size=size_of(page), heights=heights, first_height_ms=height_ms, heights_dropped=dropped_h, actions=answers,
              uncaught=errors[:3])

        # 16: the same instance morphs to full screen and back; with modes, each is echoed in time. A declaration
        # without `full` (optional, §5.2) has no full-screen surface to probe.
        if declared["full"] is None:
            check("16-full", True, note="no full surface declared")
        else:
            loads_before = count(page, "load")
            page.evaluate("() => window.__wickedEditor.host().setSurface('full')")
            page.wait_for_timeout(300)
            echoes = []
            if declared["full"] is not None and declared["full"]["modes"] is not None:
                for m in ("advanced", "simple"):
                    got, secs = timed(page, f"() => window.__wickedEditor.host().setMode('{m}')")
                    echoes.append({"mode": m, "echo": got, "seconds": secs})
            page.evaluate("() => window.__wickedEditor.host().setSurface('card')")
            page.wait_for_timeout(200)
            bad = [e for e in echoes if e["echo"] != e["mode"] or e["seconds"] > HOST_ANSWER_S]
            check("16-full", count(page, "load") == loads_before == 1
                  and count(page, "handshake") == 1 and count(page, "ignored-window-message") == 0 and not bad
                  and count(page, "teardown") == 0 and not errors,
                  loads=count(page, "load"), readies=count(page, "handshake"), modes=echoes, uncaught=errors[:3])
    except CaseFailed:
        pass
    finally:
        for pg in pages:
            pg.close()

    # 15: every plugin tab in its own options instance; the controls tabs' values from the first one.
    tabs = declared["options"]["tabs"] if declared["options"] is not None else []
    plugin_tabs = [t for t in tabs if t["render"] == "plugin"]
    controls_tabs = [t for t in tabs if t["render"] == "controls"]
    if not tabs:
        cases["15-options"] = {"ok": True, "tabs": 0, "note": "no options surface declared"}
        return
    detail: list = []
    ok = True
    for i, t in enumerate(plugin_tabs or [None]):
        page, errors = open_page(surface="options", **({"tab": t["id"]} if t else {}))
        try:
            page.evaluate("() => window.__wickedEditor.host().relaySelection([{kind:'element', id:'conformance-probe'}])")
            page.wait_for_timeout(300)
            row = {"tab": t["id"] if t else None, "frame_size": size_of(page),
                   "alive": page.evaluate("() => window.__wickedEditor.host()?.alive === true") and count(page, "teardown") == 0}
            row_ok = True
            if i == 0 and controls_tabs:
                # Every controls tab needs its own accepted snapshot (the host keeps the newest per tab), and one
                # valid change per tab gets a well-formed answer, applied or refused. A host page that does not report
                # the snapshots fails closed.
                want = json.dumps([t2["id"] for t2 in controls_tabs])
                try:  # every controls tab's first snapshot, however late the editor starts (a finite wait)
                    page.wait_for_function(f"() => {{ const v = window.__wickedEditor.optionsValues?.(); "
                                           f"return v != null && {want}.every(t => t in v); }}", timeout=OPTIONS_WAIT_MS)
                except Exception:  # noqa: BLE001 — reported below as the tabs that never arrived
                    pass
                seen = page.evaluate("() => window.__wickedEditor.optionsValues?.() ?? null")
                row["values_dropped"] = count(page, "dropped", "options.values")
                row["values_tabs"] = sorted(seen) if isinstance(seen, dict) else None
                changes = []
                for t2 in controls_tabs:
                    first = t2["controls"][0]
                    value = _probe_value(first)
                    r = answered(page, f"() => window.__wickedEditor.host().changeOption("
                                       f"{json.dumps(t2['id'])}, {json.dumps(first['id'])}, {json.dumps(value)})", "options.changed", CHANGE_SHAPE)
                    # Applied or refused are both answers (§6): a well-formed reply within 2 s is what counts.
                    changes.append({"tab": t2["id"], "id": first["id"], "value": value, "applied": r["answer"],
                                    "reply": r["reply"], "answered": r["ok"]})
                row["changes"] = changes
                row_ok = (isinstance(seen, dict) and all(t2["id"] in seen for t2 in controls_tabs)
                          and row["values_dropped"] == 0 and all(c["answered"] for c in changes))
                if not isinstance(seen, dict):
                    row["error"] = "the conformance host page reports no options values per tab (window.__wickedEditor.optionsValues)"
            row["uncaught"] = errors[:3]
            ok = ok and row_ok and row["alive"] and row["frame_size"] == "pane" and not errors
            detail.append(row)
        finally:
            page.close()
    cases["15-options"] = {"ok": ok, "tabs": detail}


def _probe_value(control: dict):
    """A value the control can hold that differs from the template's first one, for the change probe."""
    kind = control["type"]
    if kind == "toggle":
        return True
    if kind in ("segmented", "select"):
        return control["options"][-1]["id"]
    if kind == "range":
        return control["min"] + control["step"]  # on the step grid, and ≤ max since step ≤ max - min
    if kind == "color":
        return "#aa0000"
    return "conformance"[: control.get("maxChars", 200)]


def _torn(page, wait: bool = False):
    try:
        loc = page.get_by_test_id("editor-torn")
        if wait:
            loc.wait_for(state="visible", timeout=8000)
        return loc.inner_text() if loc.count() else None
    except Exception:  # noqa: BLE001
        return None


def python_with_playwright() -> str | None:
    """The first python3 / python on PATH that can import playwright. Each is probed, never compared by
    path: a venv's python links to the same base binary yet sees other site-packages (codex)."""
    import shutil, subprocess  # noqa: E401, PLC0415
    for name in ("python3", "python"):
        exe = shutil.which(name)
        if exe is None:
            continue
        try:
            if subprocess.run([exe, "-c", "import playwright.sync_api"], capture_output=True, timeout=30).returncode == 0:
                return exe
        except (OSError, subprocess.TimeoutExpired):
            continue
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
        # The launcher's snapshot venv carries no browser driver (E2E finding F-EDIT-2): run once more
        # under a python on PATH that has one, with the same arguments.
        other = python_with_playwright() if not os.environ.get("WG_EDITOR_CONFORMANCE_REEXEC") else None
        if other is not None:
            import subprocess  # noqa: PLC0415
            env = {**os.environ, "WG_EDITOR_CONFORMANCE_REEXEC": "1"}
            return subprocess.call([other, os.path.abspath(__file__), *(argv if argv is not None else sys.argv[1:])], env=env)
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
                          "the host-control cases against a hostile bundle: studio CI runs them",
                          "16b (host.action grants no activation for a tools/call) is the host's rule: studio CI runs "
                          "it with a test plugin"]}
                if m0["ok"]:
                    run_editor(browser, origin, e, er["sha256"], er)
                    base_ok = len(er["cases"]) == 12 and all(c.get("ok") for c in er["cases"].values())
                    if speaks(e, 2) and base_ok and er.get("negotiated") is None:
                        # A host before protocol 2 runs this editor the protocol-1 way: its surfaces cannot be
                        # checked here (not a failure of the editor). crew requires 13-16 of a protocol-2 install,
                        # so such a report never installs it as protocol 2 there.
                        er["gaps"].append("cases 13-16 not run: this conformance host speaks protocol 1 only")
                        er["expected"] = 12
                    elif speaks(e, 2) and base_ok:
                        run_editor_v2(browser, origin, e, er["sha256"], er)
                    elif not speaks(e, 2):
                        er["cases"]["17-v1-compat"] = {
                            "ok": base_ok and er.get("negotiated") == 1, "negotiated": er.get("negotiated"),
                            **({"error": "the conformance host does not speak protocol 2"} if er.get("negotiated") is None else {})}
                er["ok"] = len(er["cases"]) == er.pop("expected", expected_cases(e)) and all(c.get("ok") for c in er["cases"].values())
                report["editors"].append(er)
            browser.close()
    finally:
        server.shutdown()
    report["ok"] = bool(report["editors"]) and all(e["ok"] for e in report["editors"])
    return out(report, 0 if report["ok"] else 1)


if __name__ == "__main__":
    sys.exit(main())
