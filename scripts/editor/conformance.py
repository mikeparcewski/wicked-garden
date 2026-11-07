#!/usr/bin/env python3
"""Run the editor-plugin conformance cases against every editor in a pack (DES-artifact-editor-plugins §12.1).

    wicked-garden run scripts/editor/conformance.py --pack <pack dir> [--host-url <crew URL> | --studio-dist <dir>]
        [--timeout <seconds>] [--json]
    wicked-garden run scripts/editor/conformance.py --engine --json      (the engine's host step; see ENGINE MODE)

The cases run in headless Chromium against studio's own **conformance host page**
(``/editors/conformance``: the real plugin host, its sandboxed frame, its MessagePort handshake, its
grants check, over a scripted in-memory page). This script serves that page on a local origin —
proxied from a wicked-crew daemon (``--host-url``, else ``$WICKED_CREW_URL``), or from a studio
``dist`` directory (``--studio-dist``) — and serves the candidate's entry itself on the editor
bundle route, hash-checked and with the third-party bundle policy (no network at all). Nothing is
installed, registered or written outside a temporary directory.

``--timeout`` (else ``$WG_EDITOR_CONFORMANCE_TIMEOUT``, default 120 s) bounds each load of the host page and
each request proxied to the daemon. A page counts as loaded when the DOM is ready and the host page has
rendered, never on "network idle": studio keeps a live socket and slow reads open, so a busy daemon would
otherwise fail a correct editor. The host page's own assets are fetched from the daemon once per run and
then served from memory. The editor's own deadlines (the 3 s handshake, the 2 s answers) do not stretch. The bound
is per load, not for the whole run: wicked-crew's install runs this script under its own overall cap, which this
setting does not extend (set ``$WG_EDITOR_CONFORMANCE_TIMEOUT`` in the daemon's environment to change it there).

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
  7  edit          it saves through its own UI: an editor that asks ``artifact.write`` marks the control that saves
                   with ``data-wicked-save``; with its empty text fields filled with valid values (or, none empty, its
                   first text field changed), a click on the first visible marked control lands exactly ONE version
                   (an editor that asks no ``artifact.write`` is a viewer and passes)
  8  strict-input  malformed host messages leave it alive
  9  liveness      it answers ``host.ping`` over a full ping period
  10 keyboard      every control in it can take focus (axe is not run: a reported gap)
  11 theme         a ``host.theme`` change leaves it alive, with no running animation
  12 hash-pinned   a wrong pinned hash never starts it
  18 shows         it shows the content it is handed: it asks ``artifact.read``, reads within 3 s of the handshake (the
                   host's clock), a text run of the version it read is in its rendered text or fields, and when
                   another version lands (``artifact.changed``) it reads again and shows what changed
                   (7 and 18 run for kinds ``page`` and ``deck``, the samples this host has; another kind is reported
                   not checked)

Protocol 2 (an editor whose ``protocol`` lists 2; DES-EDITOR-PLUGIN-CONTRACT-001 §8.3):

  13 surfaces      the host negotiated 2, and the surfaces it renders from (``plugin.ready``'s) are the
                   manifest's, as canonical JSON; the labels pass the word and length rules
  14 card          it mounts as the card (its ``host.hello`` says ``surface:'card'``); with ``aspect:"auto"`` a ``ui.height`` arrives within 2 s and is
                   accepted; every ``verb:"plugin"`` action answers ``host.action`` within 2 s
  15 options       each plugin tab mounts as its own options instance: the ``host.hello`` the frame received
                   says ``surface:'options'`` and that ``tab``; it survives ``host.selection`` and ``host.tab``
                   to every other plugin tab and back (no reload); every controls tab's ``options.values`` is
                   accepted, and a valid change gets a well-formed answer within 2 s (applied or refused)
  16 full          ``host.surface`` card→full keeps the instance (no reload, no second ``plugin.ready``);
                   with modes, every ``host.mode`` is answered within 2 s with the same mode

Protocol 1 only:

  17 v1-compat     the host negotiated 1, and cases 1-6 and 8-12 passed under this protocol-2 host (7 and 18 report on their own)

Cases 7 and 18 are behaviour (G9b): an editor that never reads the artifact it opens, or cannot save an edit
through its own UI, is not conformant. Both are recorded without stopping the run, so the other cases still report.

Prints one JSON report ``{ok, pack, host, editors: [{id, version, protocol, sha256, ok, cases, gaps}]}``.
Exit 0 every editor passed, 1 a case failed, 2 bad arguments or an unreadable pack, 3 no headless
browser (fail closed: an editor is never reported conformant without the run).

ENGINE MODE (``--engine``; DES-EDITOR-CONFORMANCE-HOST, F18). wicked-core runs this script as the editor-plugin
workflow's ``conformance`` step, on the host, in an OS jail whose only network is ONE loopback port: this script's
own origin. So the host page always comes from a studio dist, never from the daemon, and every input is the
engine's, from the environment:

  WICKED_EDITOR_CONFORMANCE_JAIL         the jail's launcher kind; refused without it (never run unjailed)
  WICKED_EDITOR_PACK_ROOT                the run's worktree: the ONE editor pack under it is the candidate
                                         (no link anywhere on the way to its manifest or entries)
  WG_EDITOR_CONFORMANCE_PORT             the loopback port to serve the origin on (the one the jail opens)
  WG_EDITOR_CONFORMANCE_STUDIO_DIST      the studio dist to serve the host page from
  WG_EDITOR_CONFORMANCE_OUT              where to write the report as well (a file in the engine's temp dir)
  WG_EDITOR_CONFORMANCE_PYTHON           the interpreter with Playwright (wicked-crew's private venv), in any mode

The report then also carries ``cause`` when it is not ok: ``case_failed`` or ``pack_invalid`` (a verdict on the
pack: its author fixes it), else what kept the cases from running (``no_jail``, ``bad_arguments``, ``no_studio``,
``port_unavailable``, ``no_browser``, ``host_page_failed``, ``harness_broken``): the host's problem, never a verdict
on the editor. In engine mode the ``cause`` decides, not the exit code: exit 2 also covers the host refusals
before the cases start (a port that is taken, inputs it cannot vouch for), and exit 1 a host page that did not
render or a pack checker that is missing or crashed. Engine mode refuses any link anywhere in the pack directory (and on the way to it from the tree), and
re-executes under ``$WG_EDITOR_CONFORMANCE_PYTHON`` before it imports a browser driver.
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

from _pack import (  # noqa: E402
    MANIFEST_CAP, PackError, editors_of, entry_path, find_editor_packs, read_manifest, refuse_links, refuse_links_under,
)
from _surfaces import SurfacesError, canonical_surfaces, parse_surfaces  # noqa: E402

# The third-party bundle policy, as wicked-crew serves it (crew `editors/csp.ts`, no `https:` media).
BUNDLE_CSP = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
              "img-src data: blob:; media-src blob:; font-src data:; frame-src blob: data: about:; "
              "child-src blob: data: about:; connect-src 'none'; form-action 'none'; base-uri 'none'; "
              "worker-src 'none'; manifest-src 'none'")
W, H = 1440, 700
SAFE_CTYPE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+(?:; ?charset=[A-Za-z0-9_-]+)?")
PING_PERIOD_MS = 11_500
DEFAULT_TIMEOUT_S = 120.0
TIMEOUT_ENV = "WG_EDITOR_CONFORMANCE_TIMEOUT"
PYTHON_ENV = "WG_EDITOR_CONFORMANCE_PYTHON"
JAIL_ENV = "WICKED_EDITOR_CONFORMANCE_JAIL"
PACK_ROOT_ENV = "WICKED_EDITOR_PACK_ROOT"
PORT_ENV = "WG_EDITOR_CONFORMANCE_PORT"
STUDIO_DIST_ENV = "WG_EDITOR_CONFORMANCE_STUDIO_DIST"
OUT_ENV = "WG_EDITOR_CONFORMANCE_OUT"
# The causes that are a verdict on the pack (its author fixes it); every other cause kept the cases from running.
VERDICT_CAUSES = ("case_failed", "pack_invalid")
# In the editor's frame, before its own script: the host.hello it took (the first trusted one from the parent carrying
# a port), as the frame received it. The surface and tab a host page says it mounted are only claims; this is what the
# editor was told. Every native it needs is captured before the editor runs, only own primitive fields are read, and
# the record is a JSON string behind a non-configurable getter: the editor can neither forge the event (isTrusted, the
# parent as source) nor rewrite the record afterwards.
FRAME_HELLO = """(() => {
  if (window.top === window) return;
  const parentWin = window.parent, stringify = JSON.stringify, hasOwn = Object.hasOwn, apply = Reflect.apply;
  const getter = (proto, key) => Object.getOwnPropertyDescriptor(proto, key).get;
  const dataOf = getter(MessageEvent.prototype, 'data'), sourceOf = getter(MessageEvent.prototype, 'source');
  const portsOf = getter(MessageEvent.prototype, 'ports');
  const field = (o, k) => { if (o === null || typeof o !== 'object' || !hasOwn(o, k)) return null;
    const v = o[k]; return typeof v === 'string' || typeof v === 'number' ? v : null; };
  let seen = null;
  Object.defineProperty(window, '__wgHello', { configurable: false, enumerable: false, get: () => seen });
  addEventListener('message', (e) => {
    if (seen !== null || e.isTrusted !== true || apply(sourceOf, e, []) !== parentWin) return;
    const d = apply(dataOf, e, []), ports = apply(portsOf, e, []);
    if (field(d, 'p') !== 'wicked.editor' || field(d, 'type') !== 'host.hello' || !ports || ports.length < 1) return;
    const p = d.payload;
    // Built from primitives only: JSON.stringify of a string, number or null never looks up a toJSON, and no object
    // the editor's prototypes could reach is ever serialized.
    seen = '{"protocol":' + stringify(field(p, 'protocol')) + ',"surface":' + stringify(field(p, 'surface'))
      + ',"tab":' + stringify(field(p, 'tab')) + ',"mode":' + stringify(field(p, 'mode')) + '}';
  }, true);
})();"""
LOG = ("() => (window.__wickedEditor?.log ?? []).map(e => ({kind: e.kind, type: e.type ?? null, "
       "code: e.code ?? null, why: e.why ?? e.reason ?? null}))")
COMPOSER = "() => window.__wickedEditor?.composer() ?? null"
# Cases 7 and 18 (the behaviour an editor owes the artifact it opens).
SHOW_WAIT_S = 3.0
EDIT_WAIT_S = 5.0
EDIT_SENTENCE = "Conformance case seven"
SAVE_MARK = "data-wicked-save"
# The empty text fields case 7 fills before it presses the marked control.
EDIT_FIELDS = ('input:not([type]), input[type="text"], input[type="search"], input[type="url"], input[type="email"], '
               'input[type="tel"], input[type="number"], textarea')
# The visible text runs of the version the host hands out (on the host page, never in the editor's frame): every leaf
# anchored element's text, whitespace collapsed, 4+ characters, outside anything hidden.
CONTENT_RUNS = ("() => { const d = new DOMParser().parseFromString(window.__wickedEditor.adapter.headHtml(), 'text/html');"
                " return [...d.querySelectorAll('[data-wid]')].filter(e => !e.querySelector('[data-wid]')"
                " && !e.closest('[hidden], [data-wi-no-anchor], script, style'))"
                ".map(e => (e.textContent || '').replace(/\\s+/g, ' ').trim()).filter(t => t.length >= 4); }")
JUNK = ["null", "'x'", "{p:'wicked.editor'}", "{p:'wicked.editor',v:1,type:'nonsense',payload:{}}",
        "{p:'wicked.editor',v:1,type:'host.size',payload:null}", "{p:'wicked.editor',v:1,type:'host.theme'}"]


class CaseFailed(Exception):
    pass


class PageFailed(Exception):
    """The conformance host page did not load or did not start the editor (the message says which)."""


# ── the local origin ───────────────────────────────────────────────────────────────────────

def make_server(candidates: dict[tuple[str, str], tuple[bytes, str]], host_url: str | None, dist: Path | None,
                timeout_s: float = DEFAULT_TIMEOUT_S, port: int = 0):
    """A local origin: the candidate entries on the bundle route, everything else from the host.

    The host page's own files (anything outside ``/api/``) are fetched from the daemon once and then served from
    memory, so the many page loads of one run cost the daemon one read each; API reads always go through."""
    static_cache: dict[str, tuple[int, bytes, str]] = {}
    cache_lock = threading.Lock()

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
            try:
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return  # the page closed before its read finished (the next case already began): nothing to report

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
            path = urllib.parse.urlparse(self.path).path
            accept = self.headers.get("Accept", "*/*")
            # The whole request target and the one header forwarded: a different query or Accept is another entry.
            key = (self.path, accept)
            cacheable = not path.startswith("/api/") and path != "/ws"
            if cacheable:
                with cache_lock:
                    hit = static_cache.get(key)
                if hit is not None:
                    return self._send(*hit)
            got = _fetch(host_url + self.path, accept, timeout_s)
            if cacheable and got[0] == 200:
                with cache_lock:
                    static_cache[key] = got
            return self._send(*got)

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

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _fetch(url: str, accept: str, timeout_s: float) -> tuple[int, bytes, str]:
    """One GET from the daemon, bounded as a whole (connect, headers and every byte of the body): a daemon that
    trickles its answer gets a 504 at the deadline, never an unbounded wait. The reading thread is left to finish
    on its own; it holds nothing this run needs."""
    box: dict = {}

    def get() -> None:
        try:
            req = urllib.request.Request(url, headers={"Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout_s) as r:  # noqa: S310 (the operator's own daemon)
                box["got"] = (r.status, r.read(), r.headers.get("Content-Type", "application/octet-stream"))
        except urllib.error.HTTPError as e:
            box["got"] = (e.code, e.read(), e.headers.get("Content-Type", "application/json"))
        except (urllib.error.URLError, OSError) as e:
            box["got"] = (502, json.dumps({"error": f"host unreachable: {e}"}).encode(), "application/json")

    worker = threading.Thread(target=get, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if "got" not in box:
        return (504, json.dumps({"error": f"the daemon did not answer within {timeout_s:g} s"}).encode(), "application/json")
    return box["got"]


def _remaining_ms(deadline: float) -> int:
    """What is left of one page load's single budget (at least 1 ms, so a late stage fails fast instead of hanging)."""
    return max(1, int((deadline - time.monotonic()) * 1000))


# ── the cases ──────────────────────────────────────────────────────────────────────────────

def run_editor(browser, origin: str, editor: dict, sha: str, report: dict, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
    load_ms = int(timeout_s * 1000)
    eid, version, title = editor["id"], editor["version"], editor.get("title") or editor["id"]
    perms = [p.get("id") for p in editor.get("permissions", []) if isinstance(p, dict)]
    grants = [p for p in perms if p != "network.media"]
    cases: dict = report["cases"]

    def check(name: str, ok: bool, **detail) -> None:
        cases[name] = {"ok": bool(ok), **detail}
        if not ok:
            raise CaseFailed(name)

    shown_kind = sample_kind(editor)

    def url(sha_value: str, grant_list: list[str]) -> str:
        q = {"editor": eid, "version": version, "sha": sha_value, "title": title, "grants": ",".join(grant_list),
             **({"kind": "deck"} if shown_kind == "deck" else {})}
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
        try:
            deadline = time.monotonic() + timeout_s  # ONE budget for the load: the navigation and the host page
            page.goto(url(sha, grants), wait_until="domcontentloaded", timeout=load_ms)
            page.get_by_test_id("editor-host-page").wait_for(state="visible", timeout=_remaining_ms(deadline))
        except Exception as exc:  # noqa: BLE001
            msg = (f"the conformance host page did not render within {timeout_s:g} s "
                   f"(--timeout / ${TIMEOUT_ENV}): {str(exc).splitlines()[0]}")
            # The host page renders before the editor's frame loads: this is the host's failure, not the editor's.
            report.setdefault("host_failure", msg)
            check("1-handshake", False, error=msg)
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

        # 18: it shows what it is handed, and reads again when another version lands (before case 2's read baseline).
        cases["18-shows"] = shows_case(page, frame, perms, shown_kind, alive)

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

        # 7: it saves through its own UI (grants still on).
        cases["7-edit"] = edit_case(page, frame, perms, shown_kind, log, alive)

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


        try:
            deadline = time.monotonic() + timeout_s
            page.goto(url("0" * 64, grants), wait_until="domcontentloaded", timeout=load_ms)
            page.get_by_test_id("editor-host-page").wait_for(state="visible", timeout=_remaining_ms(deadline))
        except Exception as exc:  # noqa: BLE001
            msg = (f"the conformance host page did not render within {timeout_s:g} s "
                   f"(--timeout / ${TIMEOUT_ENV}): {str(exc).splitlines()[0]}")
            report.setdefault("host_failure", msg)  # the host page, not the editor (it renders first)
            check("12-hash-pinned", False, error=msg)
        torn = _torn(page, wait=True)
        check("12-hash-pinned", torn is not None and count("handshake") == 0, torn=torn)
    except CaseFailed:
        pass
    finally:
        if errors:
            report["page_errors"] = errors[:5]
        page.close()


# Every editor's cases: wicked-crew's CONFORMANCE_CASES and wicked-core's editor_conformance CASES require the same ids.
CASES_V1 = ("0-manifest", "1-handshake", "2-sizes", "3-no-network", "4-permissions", "5-typing", "6-forwarding",
            "7-edit", "8-strict-input", "9-liveness", "10-keyboard", "11-theme", "12-hash-pinned", "18-shows")
CASES_V2 = ("13-surfaces", "14-card", "15-options", "16-full")
# What the editor does with the artifact (G9b): recorded without stopping the run, and never a prerequisite of 13-17.
BEHAVIOUR_CASES = ("7-edit", "18-shows")


def sample_kind(editor: dict) -> str | None:
    """The conformance host's sample an editor is shown on: the page, or the deck for a deck-only editor. None: the
    host has no sample of any kind it opens (cases 7 and 18 then report it not checked)."""
    kinds = editor.get("kinds") if isinstance(editor.get("kinds"), list) else []
    return "page" if "page" in kinds else "deck" if "deck" in kinds else None


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def shown_runs(frame_text: str, runs: list) -> list[str]:
    """The text runs of the handed version that the editor's visible text holds (whitespace-insensitive)."""
    seen = _squash(frame_text)
    return [r for r in runs if isinstance(r, str) and _squash(r) and _squash(r) in seen]


# What the editor shows: its body's rendered text plus what its text fields hold (an editor may show the artifact in a
# field). Read in the editor's frame; only strings come back.
# Open shadow roots count (an editor built from web components renders inside them).
FRAME_TEXT = ("(b) => { const out = [b.innerText || '']; const walk = (root) => { for (const e of root.querySelectorAll('*')) {"
              " if ((e.tagName === 'INPUT' || e.tagName === 'TEXTAREA') && e.type !== 'hidden' && e.type !== 'password')"
              " out.push(String(e.value || '')); if (e.shadowRoot) { out.push(e.shadowRoot.textContent || ''); walk(e.shadowRoot); } } };"
              " walk(document); return out.join('\\n'); }")
# The editor's artifact.read requests as the host took them (its own clock), the handshake's time, and the times of the
# refused ones (the host refuses at once, so a refusal follows its request). Protocol requests only: the host's own
# reads (a write's inventory) never count as the editor reading; a malformed request is logged `in` with ok false.
READS = ("() => { const log = window.__wickedEditor?.log ?? []; const hs = log.find(e => e.kind === 'handshake');"
         " return { hs: hs ? hs.at : null, at: log.filter(e => e.kind === 'in' && e.type === 'artifact.read' && e.ok !== false).map(e => e.at),"
         " refused: log.filter(e => e.kind === 'refused' && e.type === 'artifact.read').map(e => e.at) }; }")


def answered_reads_by(r: dict, t: float) -> int:
    """How many of the editor's reads up to host time ``t`` were not refused."""
    return sum(1 for a in r["at"] if a <= t) - sum(1 for a in r["refused"] if a <= t)
# A valid value for a field case 7 fills, by its type and constraints (a validating form keeps Save disabled otherwise).
FIELD_VALUE = ("(e, sentence) => { const t = (e.getAttribute('type') || 'text').toLowerCase();"
               " if (t === 'email') return 'conformance@example.com'; if (t === 'url') return 'https://example.com/conformance';"
               " if (t === 'tel') return '5550100'; if (t === 'number') { const min = parseFloat(e.min), max = parseFloat(e.max);"
               " const st = parseFloat(e.step), step = Number.isFinite(st) && st > 0 ? st : 1, base = Number.isFinite(min) ? min : 0;"
               " let v = base + Math.ceil((Math.max(7, base) - base) / step) * step;"
               " if (Number.isFinite(max) && v > max) v = base + Math.floor((max - base) / step) * step; return String(v); }"
               " let v = sentence; while (e.minLength > 0 && v.length < e.minLength) v += ' ' + sentence;"
               " return e.maxLength > 0 ? v.slice(0, e.maxLength) : v; }")
# A different value for a field that already holds one, within its length limit (Save waits for a change).
FIELD_CHANGED = ("e => { const v = String(e.value || ''), add = ' (conformance)';"
                 " if (!(e.maxLength > 0) || v.length + add.length <= e.maxLength) return v + add;"
                 " if (v.length < e.maxLength) return v + 'x'; const c = v.slice(-1) === 'x' ? 'y' : 'x'; return v.slice(0, -1) + c; }")
SAVE_READY_S = 2.0
WRITE_QUIET_S = 1.5
READ_QUIET_S = 2.0


def _frame_text(frame) -> str:
    try:
        return frame.locator("body").evaluate(FRAME_TEXT, timeout=1000) or ""
    except Exception:  # noqa: BLE001 — a frame that cannot be read shows nothing
        return ""


def _poll(page, done, wait_s: float) -> bool:
    deadline = time.monotonic() + wait_s
    while True:
        if done():
            return True
        if time.monotonic() >= deadline:
            return False
        page.wait_for_timeout(150)


def _editor_wait(name: str, fn) -> dict:
    """Run a behaviour case; a Playwright wait on the editor's own frame or controls that never came is THIS case's
    failure (recorded, the run goes on); the browser going away, or anything else, stays the harness's."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ == "TimeoutError" and type(exc).__module__.startswith("playwright"):
            return {"ok": False, "error": f"{name}: waiting on the editor timed out ({str(exc).splitlines()[0] if str(exc) else ''})"}
        raise


NOT_CHECKED = "the conformance host has no sample of the kinds it opens (page and deck only): not checked here"


def shows_case(page, frame, perms: list, kind: str | None, alive) -> dict:
    """Case 18: the editor shows the content it is handed, and follows a new version (DES-EDITOR-PLUGINS-001 §5:
    ``artifact.changed`` → re-read unless ``by`` is this editor). Never raises on the editor's account."""
    if "artifact.read" not in perms:
        return {"ok": False, "error": "it asks no artifact.read: an editor opens an artifact to show it (ask "
                                      "artifact.read and render what artifact.read returns)"}
    if kind is None:
        return {"ok": True, "not_checked": True, "note": NOT_CHECKED}

    def run() -> dict:
        reads = lambda: page.evaluate(READS)  # noqa: E731
        runs = page.evaluate(CONTENT_RUNS)
        got: dict = {"seen": []}

        def first() -> bool:
            r = reads()
            got["r"] = r
            got["seen"] = shown_runs(_frame_text(frame), runs)
            return len(r["at"]) > len(r["refused"]) and bool(got["seen"])
        _poll(page, first, SHOW_WAIT_S)
        r = got["r"]
        # A read the host answered (not refused) within 3 s of the handshake, on the host's clock.
        read_ok = r["hs"] is not None and answered_reads_by(r, r["hs"] + SHOW_WAIT_S * 1000) > 0
        first_ms = (r["at"][0] - r["hs"]) if r["at"] and r["hs"] is not None else None
        answered = lambda x: len(x["at"]) - len(x["refused"])  # noqa: E731
        before = answered(reads())
        page.evaluate("() => window.__wickedEditor.agentVersion()")
        # A read the host ANSWERED after the change (a refused one, e.g. a version that does not exist, is not one).
        reread = _poll(page, lambda: answered(reads()) > before, SHOW_WAIT_S)
        after_runs = page.evaluate(CONTENT_RUNS)
        new_runs = [x for x in after_runs if x not in runs]
        seen_after: list = []

        def follows() -> bool:
            nonlocal seen_after
            seen_after = shown_runs(_frame_text(frame), new_runs)
            return bool(seen_after)
        # What the new version changed must show. The deck sample's agent version changes no text: there only the
        # re-read is judged, and the report says so.
        shows_new = reread and (not new_runs or _poll(page, follows, SHOW_WAIT_S))
        # Its change handling settles (no read for a quiet second, at most 4 s) before case 2 takes its read baseline.
        last = {"n": len(reads()["at"]), "t": time.monotonic()}

        def quiet() -> bool:
            n = len(reads()["at"])
            if n != last["n"]:
                last.update(n=n, t=time.monotonic())
            return time.monotonic() - last["t"] >= READ_QUIET_S
        settled = _poll(page, quiet, 6.0)
        ok = read_ok and bool(got["seen"]) and reread and shows_new and alive()
        detail: dict = {"ok": ok, "first_read_ms": None if first_ms is None else round(first_ms), "shown": got["seen"][:3],
                        "reread": reread, "shown_after": seen_after[:3],
                        **({} if new_runs else {"note": "the sample's new version changes no text: only the re-read is checked"}),
                        **({} if settled else {"reads_unsettled": True})}
        if not ok:
            detail["error"] = ("it did not read the artifact within 3 s of the handshake" if not read_ok
                               else "none of the handed content is visible in it" if not got["seen"]
                               else "it did not read again when another version landed (artifact.changed)" if not reread
                               else "it does not show what the new version changed" if not shows_new
                               else "it stopped answering")
        return detail
    return _editor_wait("18-shows", run)


def edit_case(page, frame, perms: list, kind: str | None, log, alive) -> dict:
    """Case 7: an editor that may write saves an edit through its own UI: its empty text fields filled with valid
    values (or, when none is empty, its first text field changed), one click on the first visible control marked
    ``data-wicked-save`` lands exactly one version. Never raises on the editor's account."""
    if "artifact.write" not in perms:
        return {"ok": True, "viewer": True, "note": "it asks no artifact.write: a viewer (Open with says it only views)"}
    if kind is None:
        return {"ok": True, "not_checked": True, "note": NOT_CHECKED}

    def run() -> dict:
        save = frame.locator(f"[{SAVE_MARK}]")
        if save.count() == 0:
            return {"ok": False, "marked": 0,
                    "error": f"no control marked {SAVE_MARK}: an editor that asks artifact.write marks the control that "
                             f"saves an edit with {SAVE_MARK}"}
        written = lambda: sum(1 for e in log() if e["kind"] == "written")  # noqa: E731
        refused = lambda: sum(1 for e in log() if e["kind"] == "refused" and e["type"] == "version.write")  # noqa: E731
        prep0 = written()
        fields = frame.locator(EDIT_FIELDS)
        usable_fields = [fields.nth(i) for i in range(fields.count())]
        usable_fields = [f for f in usable_fields if f.is_visible() and f.is_editable()]
        filled = 0
        commit = "e => { e.dispatchEvent(new Event('change', { bubbles: true })); e.blur(); }"
        for f in usable_fields:
            if f.input_value() == "":
                f.fill(f.evaluate(FIELD_VALUE, EDIT_SENTENCE))
                f.evaluate(commit)  # what leaving the field does: a form validating on change or blur sees it
                filled += 1
        changed = None
        if filled == 0:
            # Fields loaded from the artifact, Save waiting for a change: change the first text one.
            text_like = [f for f in usable_fields if (f.get_attribute("type") or "text").lower() in ("text", "search")
                         or f.evaluate("e => e.tagName") == "TEXTAREA"]
            if text_like:
                changed = text_like[0].evaluate(FIELD_CHANGED)
                text_like[0].fill(changed)
                text_like[0].evaluate(commit)
        # A save control may stay disabled until there is something to save (and a form may validate on a debounce).
        found: dict = {}

        def ready() -> bool:
            found["usable"] = [save.nth(i) for i in range(save.count()) if save.nth(i).is_visible() and save.nth(i).is_enabled()]
            return bool(found["usable"])
        if not _poll(page, ready, SAVE_READY_S):
            return {"ok": False, "marked": save.count(), "filled": filled,
                    "error": f"its {SAVE_MARK} control stayed hidden or disabled with its text fields filled"}
        # An editor that saves as you type: its writes settle (a quiet second) before the click's baseline, so they are
        # noted and never credited to the click.
        last_w = {"n": written(), "t": time.monotonic()}

        def writes_quiet() -> bool:
            n = written()
            if n != last_w["n"]:
                last_w.update(n=n, t=time.monotonic())
            return time.monotonic() - last_w["t"] >= 1.0
        _poll(page, writes_quiet, 4.0)
        prep_writes = written() - prep0
        head = "() => window.__wickedEditor.adapter.artifact().head"
        head0, written0, refused0 = page.evaluate(head), written(), refused()
        found["usable"][0].click(timeout=5000)
        landed = _poll(page, lambda: written() > written0, EDIT_WAIT_S)
        page.wait_for_timeout(int(WRITE_QUIET_S * 1000))  # a second write from the same click would land here
        moved, wrote, refusals = page.evaluate(head) - head0, written() - written0, refused() - refused0
        html = page.evaluate("() => window.__wickedEditor.adapter.headHtml()") or ""
        detail: dict = {"filled": filled, "writes": wrote, "head_moved": moved, "refused": refusals,
                        "typed_in_version": EDIT_SENTENCE in html or (changed is not None and changed in html),
                        **({"saved_while_typing": prep_writes} if prep_writes else {})}
        detail["ok"] = ok = landed and wrote == 1 and moved == 1 and refusals == 0 and alive()
        if not ok:
            detail["error"] = (f"a click on its {SAVE_MARK} control landed no version within {EDIT_WAIT_S:g} s"
                               if not landed else f"one click landed {wrote} writes and moved the head by {moved}"
                               if wrote != 1 or moved != 1 else "the host refused a write" if refusals else "it stopped answering")
        return detail
    return _editor_wait("7-edit", run)


def record_stop(report: dict, exc: Exception, cases: tuple) -> None:
    """A case run that stopped on an exception no case caught, classified by the exception's TYPE, never its text
    (an editor can put any words in an error): a Playwright timeout is a wait on the editor's own frame or controls
    that never came (the host page had rendered: its own failures are caught where it loads), so it is the editor's
    failure, recorded as ``stopped`` with the last case that finished (never charged to a case that did not run);
    the browser or page going away (``TargetClosedError``) and anything else are the harness's, a refusal."""
    msg = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
    if type(exc).__name__ == "TimeoutError" and type(exc).__module__.startswith("playwright"):
        done = [c for c in cases if c in report["cases"]]
        report["cases"]["stopped"] = {"ok": False, "error": f"the run stopped waiting on the editor: {msg}",
                                      "after": list(report["cases"])[-1] if report["cases"] else None,
                                      "not_run": [c for c in cases if c not in done]}
        return
    what = "the browser went away mid-run" if type(exc).__name__ == "TargetClosedError" else "the harness stopped"
    report.setdefault("host_failure", f"{what} ({msg})")


def speaks(editor: dict, version: int) -> bool:
    protocol = editor.get("protocol")
    return isinstance(protocol, list) and version in protocol


def expected_cases(editor: dict) -> int:
    """0-12 and 18, plus 13-16 for a protocol-2 editor or 17 for a protocol-1 one."""
    return len(CASES_V1) + (4 if speaks(editor, 2) else 1)


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


def run_editor_v2(browser, origin: str, editor: dict, sha: str, report: dict, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
    """Cases 13-16: the three surfaces of a protocol-2 editor, each in its own host instance."""
    load_ms = int(timeout_s * 1000)
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
        page.add_init_script(FRAME_HELLO)
        try:
            deadline = time.monotonic() + timeout_s
            page.goto(f"{origin}/editors/conformance?{urllib.parse.urlencode(q)}", wait_until="domcontentloaded", timeout=load_ms)
            page.get_by_test_id("editor-host-page").wait_for(state="visible", timeout=_remaining_ms(deadline))
        except Exception as exc:  # noqa: BLE001 — the case that opened it fails, naming why
            page.close()
            msg = (f"the conformance host page did not render within {timeout_s:g} s (--timeout / "
                   f"${TIMEOUT_ENV}): {str(exc).splitlines()[0]}")
            report.setdefault("host_failure", msg)  # the host's failure, not the editor's (it renders first)
            raise PageFailed(msg) from exc
        try:
            page.wait_for_function("() => (window.__wickedEditor?.log ?? []).some(e => e.kind === 'handshake')", timeout=6000)
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ == "TargetClosedError":  # the browser went away: the host's, never the editor's
                report.setdefault("host_failure", f"the browser went away mid-run ({str(exc).splitlines()[0]})")
            with contextlib.suppress(Exception):
                page.close()
            raise PageFailed("no plugin.ready the host accepted within its 3 s") from exc
        page.wait_for_timeout(300)
        return page, errors

    def hello(page) -> dict | None:
        """The host.hello the editor's frame took, as the frame received it (None: no frame or no hello seen)."""
        for fr in page.frames:
            if fr is not page.main_frame and "/entry?" in fr.url:
                with contextlib.suppress(Exception):
                    raw = fr.evaluate("() => window.__wgHello")
                    return json.loads(raw) if isinstance(raw, str) else None
        return None

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

    pages: list = []
    try:
        # 13: the declaration the host renders from is the manifest's.
        try:
            page, errors = open_page(surface="card")
        except PageFailed as exc:
            check("13-surfaces", False, error=str(exc))
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
        told = hello(page)
        check("14-card", size_of(page) == "inline" and told is not None and told.get("surface") == "card"
              and dropped_h == 0 and on_time and not late and count(page, "teardown") == 0 and not errors,
              frame_size=size_of(page), hello=told, heights=heights, first_height_ms=height_ms, heights_dropped=dropped_h, actions=answers,
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
        want_tab = t["id"] if t else None
        row: dict = {"tab": want_tab}
        try:
            page, errors = open_page(surface="options", **({"tab": want_tab} if t else {}))
        except PageFailed as exc:
            row["error"] = str(exc)
            detail.append(row)
            ok = False
            continue
        try:
            # The options mount itself: the editor must have been told it is the options instance, on this tab (a
            # group of controls tabs only has no plugin tab, so no tab). A host page that mounts it as anything else
            # cannot show the options surface works, so the case fails closed.
            told = hello(page)
            row["hello"] = told
            mounted = told is not None and told.get("surface") == "options" and told.get("tab") == want_tab
            if not mounted:
                row.setdefault("errors", []).append(f"the editor was not mounted as the options instance of tab {want_tab!r}: the host.hello its "
                                f"frame took said {told!r}. The conformance host page must hand surface=options and "
                                "tab=<id> to the host (a studio whose /editors/conformance page takes them)")
            page.evaluate("() => window.__wickedEditor.host().relaySelection([{kind:'element', id:'conformance-probe'}])")
            page.wait_for_timeout(300)
            switched_ok = True
            if i == 0 and len(plugin_tabs) > 1:
                # host.tab: the one options instance shows every other plugin tab, then this one again, without a reload.
                loads_before = count(page, "load")
                order = [x["id"] for x in plugin_tabs[1:]] + [want_tab]
                for other in order:
                    page.evaluate(f"() => window.__wickedEditor.host().setTab({json.dumps(other)})")
                    page.wait_for_timeout(200)
                row["host_tab"] = order
                row["loads"] = count(page, "load")
                switched_ok = row["loads"] == loads_before == 1 and count(page, "handshake") == 1
                if not switched_ok:
                    row.setdefault("errors", []).append("host.tab to the other plugin tabs and back reloaded or "
                                                        "restarted the options instance")
            row["frame_size"] = size_of(page)
            row["alive"] = page.evaluate("() => window.__wickedEditor.host()?.alive === true") and count(page, "teardown") == 0
            row_ok = mounted and switched_ok
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
                row_ok = (row_ok and isinstance(seen, dict) and all(t2["id"] in seen for t2 in controls_tabs)
                          and row["values_dropped"] == 0 and all(c["answered"] for c in changes))
                if not isinstance(seen, dict):
                    row.setdefault("errors", []).append(
                        "the conformance host page reports no options values per tab (window.__wickedEditor.optionsValues)")
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


def python_with_playwright(engine: bool = False) -> str | None:
    """``$WG_EDITOR_CONFORMANCE_PYTHON`` (an absolute path: wicked-crew's private Playwright venv), else the first
    python3 / python on PATH, that can import playwright. Each is probed, never compared by path: a venv's python
    links to the same base binary yet sees other site-packages (codex)."""
    import shutil, subprocess  # noqa: E401, PLC0415
    named = os.environ.get(PYTHON_ENV, "")
    candidates = [named] if named and os.path.isabs(named) and os.path.isfile(named) else []
    if not engine:  # the engine hands the one interpreter it vouches for; PATH is never probed there
        candidates += [x for x in (shutil.which(n) for n in ("python3", "python")) if x is not None]
    for exe in candidates:
        try:
            # -I for the engine's interpreter (no PYTHON* variable, no user site); a hand run keeps a user-site playwright.
            probe = [exe, "-I", "-c", "import playwright.sync_api"] if engine else [exe, "-c", "import playwright.sync_api"]
            if subprocess.run(probe, capture_output=True, timeout=30).returncode == 0:
                return exe
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def manifest_case(pack: Path) -> dict:
    """Case 0: garden's own `pack check` (the same gate wicked-crew runs before an install)."""
    try:
        from pack.check import check_pack  # noqa: PLC0415 (scripts/ on the path above)
    except ImportError as exc:
        # The harness's own install is broken: never a verdict on the pack.
        return {"ok": False, "error": f"pack check unavailable: {exc}", "host_failure": f"pack check unavailable: {exc}"}
    try:
        findings = check_pack(pack, garden_root=HERE.parents[1])
    except Exception as exc:  # noqa: BLE001
        # The checker is garden's own, exercised on every pack it ships; what makes it throw is the pack's shape
        # (bad UTF-8, JSON nested past the limit, a field of the wrong type): case 0 fails, a verdict the pack's
        # author fixes. The same pack fails crew's install gate the same way. Only a checker that will not import,
        # or the host running out of what it needs (descriptors, memory, an I/O error), is the harness's.
        import errno  # noqa: PLC0415
        if isinstance(exc, MemoryError) or (isinstance(exc, OSError) and exc.errno in (
                errno.EMFILE, errno.ENFILE, errno.EIO, errno.ENOMEM, errno.ENOSPC)):
            return {"ok": False, "error": f"pack check unavailable: {exc}", "host_failure": f"pack check unavailable: {exc}"}
        return {"ok": False, "error": f"pack check could not read the pack: {type(exc).__name__}: {exc}"}
    errs = [f.render() for f in findings if f.level == "error"]
    return {"ok": not errs, "errors": errs[:10]}


def load_timeout(arg: float | None, env: str | None) -> float:
    """The page-load and proxy bound, in seconds: ``--timeout``, else the environment, else the default (5-1800)."""
    raw: object = arg if arg is not None else (env if env not in (None, "") else DEFAULT_TIMEOUT_S)
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"the timeout {raw!r} is not a number of seconds (--timeout / ${TIMEOUT_ENV})") from None
    if not 5 <= value <= 1800:
        raise ValueError(f"the timeout {value:g} s is outside 5-1800 s (--timeout / ${TIMEOUT_ENV})")
    return value


REPORT_STRING_MAX = 1000
# More editors than this in one pack is refused outright in engine mode (a real pack holds one or a few).
ENGINE_EDITORS_MAX = 20


def _cut(value, limit: int = REPORT_STRING_MAX) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)[:limit] if value is not None else ""
    return text if len(text) <= limit else text[:limit] + "… (cut)"


def engine_report(report: dict) -> dict:
    """The report the engine reads: a FIXED shape built from the harness's own result, never pack-controlled
    structure. Every verdict-bearing field is kept whole (each editor, its full set of protocols, every case's
    ok); diagnostics are cut to one bounded string each. Depth and size are bounded whatever the pack holds."""
    def case(c) -> dict:
        c = c if isinstance(c, dict) else {}
        row: dict = {"ok": c.get("ok") is True}
        if not row["ok"] and c.get("error") is not None:
            row["error"] = _cut(c.get("error"))
        return row
    editors = []
    for e in report.get("editors") or []:
        protocol = e.get("protocol")
        editors.append({
            "id": _cut(e.get("id"), 200), "version": _cut(e.get("version"), 200),
            "sha256": _cut(e.get("sha256"), 64),
            # The whole set: a pack-controlled list is never truncated into a different requirement.
            "protocol": sorted({p for p in protocol if isinstance(p, int) and not isinstance(p, bool)})
            if isinstance(protocol, list) else [],
            "negotiated": e.get("negotiated") if isinstance(e.get("negotiated"), int) else None,
            "ok": e.get("ok") is True,
            "cases": {_cut(k, 64): case(v) for k, v in (e.get("cases") or {}).items()},
        })
    out = {"ok": report.get("ok") is True, "pack": _cut(report.get("pack"), 500), "editors": editors}
    for k in ("cause", "error"):
        if report.get(k) is not None:
            out[k] = _cut(report.get(k)) if k == "error" else _cut(report.get(k), 64)
    return out


def engine_inputs(env) -> tuple[dict | None, dict]:
    """ENGINE MODE's inputs from the environment: ``({pack, root, port, dist, out}, {})`` or ``(None, refusal)``
    where the refusal is ``{cause, error}``. The pack is the ONE editor pack under the run's tree, with no link on
    the way to its manifest or entries."""
    def refuse(cause: str, error: str) -> tuple[None, dict]:
        return None, {"cause": cause, "error": error}
    if not env.get(JAIL_ENV, "").strip():
        return refuse("no_jail", f"engine mode runs only inside the engine's jail (${JAIL_ENV} unset): the cases run a "
                                 "seat-written editor in a browser on the host, never unjailed")
    raw_port = env.get(PORT_ENV, "")
    if not raw_port.isascii() or not raw_port.isdigit() or not 1024 <= int(raw_port) <= 65535:
        return refuse("bad_arguments", f"${PORT_ENV} must be the loopback port the jail opens (1024-65535), not {raw_port!r}")
    out = env.get(OUT_ENV, "")
    if not os.path.isabs(out):
        return refuse("bad_arguments", f"${OUT_ENV} must be an absolute file path, not {out!r}")
    dist = env.get(STUDIO_DIST_ENV, "")
    if not dist or not os.path.isabs(dist) or not (Path(dist) / "index.html").is_file():
        return refuse("no_studio", f"${STUDIO_DIST_ENV} must name a studio dist holding index.html (got {dist!r}); "
                                   "wicked-crew exports its own at boot")
    tree = env.get(PACK_ROOT_ENV, "")
    if not tree or not os.path.isabs(tree) or not Path(tree).is_dir():
        return refuse("bad_arguments", f"${PACK_ROOT_ENV} must name the run's worktree (got {tree!r})")
    try:
        found = find_editor_packs(Path(tree), strict=True)
    except (PackError, ValueError, RecursionError) as exc:
        return refuse("pack_invalid", str(exc))
    if len(found) != 1:
        names = ", ".join(str(p.relative_to(tree)) or "." for p in found[:5]) or "none"
        return refuse("pack_invalid", f"the run's tree must hold exactly one editor pack (wicked-pack.json spec 2 with "
                                      f"editors); found {len(found)} ({names})")
    return {"pack": found[0], "root": Path(tree), "port": int(raw_port), "dist": Path(dist).resolve(),
            "out": Path(out)}, {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, default=None)
    parser.add_argument("--engine", action="store_true",
                        help="the engine's host step: every input from the environment (see ENGINE MODE)")
    parser.add_argument("--host-url", default=None, help="a wicked-crew daemon serving studio (default $WICKED_CREW_URL)")
    parser.add_argument("--studio-dist", type=Path, default=None, help="serve studio's built dist instead of a daemon")
    parser.add_argument("--timeout", type=float, default=None, metavar="SECONDS",
                        help=f"each host page load and each read proxied to the daemon (default ${TIMEOUT_ENV}, else "
                             f"{DEFAULT_TIMEOUT_S:g}); the editor's own 3 s / 2 s deadlines never stretch")
    parser.add_argument("--json", action="store_true", help="print the report as JSON (the default output)")
    args = parser.parse_args(argv)
    engine = None
    if args.engine:
        engine, refusal = engine_inputs(os.environ)
        if engine is None:
            text = json.dumps(engine_report({"ok": False, "pack": None, **refusal}), indent=2)
            print(text)
            # The out file is only trusted once the inputs are: a refusal before them goes to stdout alone.
            out = os.environ.get(OUT_ENV, "")
            if os.path.isabs(out) and refusal["cause"] != "no_jail":
                with contextlib.suppress(OSError):
                    Path(out).write_text(text)
            return 2
        if args.pack is not None or args.host_url is not None or args.studio_dist is not None:
            parser.error("--engine takes every input from the environment: no --pack, --host-url or --studio-dist")
        args.pack, args.studio_dist = engine["pack"], engine["dist"]
    elif args.pack is None:
        parser.error("--pack is required (or --engine)")

    def out(report: dict, code: int) -> int:
        if engine is not None and not report.get("ok"):
            # A pack problem always names its cause where it is found; an un-named failure is never blamed on the pack.
            report.setdefault("cause", {1: "case_failed", 3: "no_browser"}.get(code, "bad_arguments"))
        if engine is not None:
            # The engine reads a fixed, bounded shape (an editor's error text, a pack's paths and identities can
            # never grow it into a report the engine refuses, or cut a requirement out of it).
            report = engine_report(report)
        try:
            text = json.dumps(report, indent=2, allow_nan=False)
        except ValueError:  # a pack-controlled non-finite number reached the report: say so in valid JSON
            report = {"ok": False, "pack": str(args.pack), "cause": "pack_invalid" if engine is not None else None,
                      "error": "the pack carries a number JSON cannot hold (NaN or Infinity)"}
            text = json.dumps(report, indent=2)
            code = 2
        print(text)
        if engine is not None:
            try:
                engine["out"].write_text(text)
            except OSError as exc:
                print(f"conformance: could not write {engine['out']}: {exc}", file=sys.stderr)
                return 2
        return code

    try:
        if engine is not None:
            # Before a byte of the pack is read past its manifest: no link anywhere in it (codex: case 0 also reads
            # the pack's skills), and none on the way to it from the run's tree.
            refuse_links_under(engine["root"], args.pack)
        manifest = read_manifest(args.pack, cap=MANIFEST_CAP if engine is not None else None,
                                 finite=engine is not None)
        editors = editors_of(manifest)
        if engine is not None:
            if len(editors) > ENGINE_EDITORS_MAX:
                raise PackError(f"the pack declares {len(editors)} editors; engine mode runs at most {ENGINE_EDITORS_MAX}")
            for e in editors:
                # What rides the host page's address (id, version, title) and the protocols the engine reads back:
                # a value no host page or report reader can carry is the pack's to fix, never a host refusal.
                for field, cap in (("id", 200), ("version", 200), ("title", 500)):
                    if len(str(e.get(field) or "")) > cap:
                        raise PackError(f"editor {str(e.get('id'))[:60]!r}: its {field} is over {cap} characters")
                perms = e.get("permissions")
                if perms is not None and (not isinstance(perms, list) or len(perms) > 32):
                    raise PackError(f"editor {str(e.get('id'))[:60]!r}: permissions must be a list of at most 32")
                protocol = e.get("protocol")
                if isinstance(protocol, list) and any(isinstance(v, int) and not 0 <= v <= 1000 for v in protocol):
                    raise PackError(f"editor {str(e.get('id'))[:60]!r}: a protocol number outside 0-1000")
            refuse_links(engine["root"], args.pack, editors)
        entries = {}
        for e in editors:
            # ONE read: the bytes served to the browser are the bytes hashed into the report (codex).
            body = entry_path(args.pack, e).read_bytes()
            entries[(str(e.get("id")), str(e.get("version")))] = (body, hashlib.sha256(body).hexdigest())
    except (PackError, ValueError, TypeError, RecursionError, OSError) as exc:  # NUL in a path, bad UTF-8, deep JSON, an
        # entry the seat made unreadable: the run's tree is the creator's, so a file in it that cannot be read is too
        return out({"ok": False, "pack": str(args.pack), "error": f"{type(exc).__name__}: {exc}",
                    "cause": "pack_invalid"}, 2)
    if engine is not None and not os.environ.get("WG_EDITOR_CONFORMANCE_REEXEC"):
        # The engine's interpreter (crew's pinned venv), never whichever playwright this interpreter happens to
        # import: re-execute under it before anything imports a browser driver (the pack is refused first, if it is).
        other = python_with_playwright(engine=True)
        if other is None:
            return out({"ok": False, "pack": str(args.pack), "error": "no headless browser: the interpreter the engine "
                        f"names (${PYTHON_ENV}) is missing or cannot import playwright; refusing to report conformance "
                        "without the run"}, 3)
        import subprocess  # noqa: PLC0415
        env = {**os.environ, "WG_EDITOR_CONFORMANCE_REEXEC": "1"}
        return subprocess.call([other, "-I", os.path.abspath(__file__), *(argv if argv is not None else sys.argv[1:])],
                               env=env)
    try:
        timeout_s = load_timeout(args.timeout, os.environ.get(TIMEOUT_ENV))
    except ValueError as exc:
        return out({"ok": False, "pack": str(args.pack), "error": str(exc), "cause": "bad_arguments"}, 2)
    host_url = None
    if args.studio_dist is None:
        host_url = (args.host_url or os.environ.get("WICKED_CREW_URL") or "").rstrip("/") or None
        if host_url is None:
            return out({"ok": False, "pack": str(args.pack), "error": "no host: pass --host-url <a wicked-crew daemon URL> "
                        "(crew sets $WICKED_CREW_URL in every governed unit) or --studio-dist <dir> — never a guessed port"}, 2)
    else:
        args.studio_dist = args.studio_dist.resolve()
    if args.studio_dist is not None and not (args.studio_dist / "index.html").is_file():
        return out({"ok": False, "pack": str(args.pack), "error": f"{args.studio_dist} holds no index.html",
                    "cause": "no_studio"}, 2)

    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        # The launcher's snapshot venv carries no browser driver (E2E finding F-EDIT-2): run once more
        # under a python on PATH that has one, with the same arguments.
        other = python_with_playwright(engine is not None) if not os.environ.get("WG_EDITOR_CONFORMANCE_REEXEC") else None
        if other is not None:
            import subprocess  # noqa: PLC0415
            env = {**os.environ, "WG_EDITOR_CONFORMANCE_REEXEC": "1"}
            # A hand run (engine mode re-executed above, before this import): keep the interpreter's user site.
            return subprocess.call([other, os.path.abspath(__file__), *(argv if argv is not None else sys.argv[1:])],
                                   env=env)
        return out({"ok": False, "pack": str(args.pack), "error": "no headless browser: the Python playwright package is "
                    "not installed (pip install playwright && playwright install chromium); refusing to report conformance "
                    "without the run"}, 3)

    report: dict = {"ok": False, "pack": str(args.pack), "host": host_url or str(args.studio_dist), "timeout_s": timeout_s,
                    "editors": []}
    try:
        server = make_server(entries, host_url, args.studio_dist, timeout_s, engine["port"] if engine else 0)
    except OSError as exc:
        report["error"] = f"the conformance origin could not listen on 127.0.0.1:{engine['port'] if engine else 0}: {exc}"
        report["cause"] = "port_unavailable"
        return out(report, 2)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    m0 = manifest_case(args.pack)
    try:
        with tempfile.TemporaryDirectory(prefix="wg-editor-conformance-") as tmp, contextlib.ExitStack() as stack:
            try:
                p = stack.enter_context(sync_playwright())  # the driver itself may not start
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                report["error"] = f"no headless browser: chromium did not start ({str(exc).splitlines()[0]})"
                return out(report, 3)
            with contextlib.suppress(Exception):
                os.chdir(tmp)  # nothing the browser writes lands in the pack
            for e in editors:
                er = {"id": e.get("id"), "version": e.get("version"),
                      "protocol": [p for p in e.get("protocol") or [] if isinstance(p, int) and not isinstance(p, bool)]
                      if isinstance(e.get("protocol"), list) else [],
                      "sha256": entries[(str(e.get("id")), str(e.get("version")))][1],
                      "cases": {"0-manifest": m0}, "gaps": [
                          f"case 7 fills the empty text fields (or changes the first one) and presses the first "
                          f"visible control marked {SAVE_MARK}: the editor's other edits are its own tests'",
                          "cases 7 and 18 run on the page and deck samples only (another kind is not checked here); "
                          "case 18 reads rendered text, field values and open shadow roots, not pixels (an editor could "
                          "hide the text); on the deck sample it checks the re-read only (the agent version changes no "
                          "deck text)",
                          "case 7 fills empty fields with values valid for their type, step and length, or changes the "
                          "first text field; an editor whose save needs another edit (a select, a number-only form) is "
                          "its own tests'",
                          "case 17 restates the host-contract cases 1-6 and 8-12; 7 and 18 report on their own",
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
                    try:
                        run_editor(browser, origin, e, er["sha256"], er, timeout_s)
                    except Exception as exc:  # noqa: BLE001 (codex: an editor-owned wait escaped the cases)
                        record_stop(er, exc, CASES_V1)
                    # The protocol-2 cases (and 17) need the host contract cases to have passed; a failed behaviour
                    # case (7, 18) fails the editor on its own and never keeps 13-17 from reporting.
                    base_ok = len(er["cases"]) == len(CASES_V1) and all(
                        c.get("ok") for k, c in er["cases"].items() if k not in BEHAVIOUR_CASES)
                    if speaks(e, 2) and base_ok and er.get("negotiated") is None:
                        # A host before protocol 2 runs this editor the protocol-1 way: its surfaces cannot be
                        # checked here (not a failure of the editor). crew requires 13-16 of a protocol-2 install,
                        # so such a report never installs it as protocol 2 there.
                        er["gaps"].append("cases 13-16 not run: this conformance host speaks protocol 1 only")
                        er["expected"] = len(CASES_V1)
                    elif speaks(e, 2) and base_ok:
                        try:
                            run_editor_v2(browser, origin, e, er["sha256"], er, timeout_s)
                        except Exception as exc:  # noqa: BLE001
                            record_stop(er, exc, CASES_V2)
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
    host_failure = next((e.get("host_failure") or e["cases"].get("0-manifest", {}).get("host_failure")
                         for e in report["editors"]
                         if e.get("host_failure") or e["cases"].get("0-manifest", {}).get("host_failure")), None)
    if host_failure is not None:
        # The host page or the harness failed, not the editor: a refusal the operator retries, never a send-back.
        report["ok"] = False
        report["error"] = host_failure
        if engine is not None:
            report["cause"] = ("host_page_failed" if host_failure.startswith("the conformance host page")
                               else "harness_broken")
    return out(report, 0 if report["ok"] else 1)


if __name__ == "__main__":
    sys.exit(main())
