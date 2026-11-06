"""A tiny app for the engine-run demo recorder's tests (DES-DEMO-RECORD-001).

Serves /app (a page with a heading, a table of "live" rows, and buttons), /app/missing (404), /app/jump (a redirect
out of the launch path to /outside), and records every request it receives so a test can prove what never arrived.
"""

from __future__ import annotations

import http.server
import threading
import time

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Demo board</title>
<style>body{font-family:sans-serif;margin:40px}table{border-collapse:collapse}td{border:1px solid #ccc;padding:6px}</style></head>
<body><div id="devbar" style="background:#ff0000;height:90px;color:#fff">DEV BUILD</div><h1>Demo board</h1>
<section><h2>Tickets</h2><table><tr><td>SECRET-ROW-ACME</td><td><button>Open SECRET-ROW-ACME</button></td></tr></table></section>
<button id="details" onclick="history.pushState({}, '', '/app/details'); document.getElementById('out').textContent='Details shown'">Open details</button>
<button id="leave" onclick="history.pushState({}, '', '/elsewhere')">Leave</button>
<button id="save" onclick="fetch('/app/save', {method:'POST', body:'x'})">Save</button>
<p id="out"></p>
<span hidden>ACME-HIDDEN-NOTE</span>
<script>fetch('/app/data').then(r => r.text()).then(t => { document.getElementById('out').dataset.loaded = t; });</script>
</body></html>"""

# A crew-shaped app at /apps/esc, laid out like studio's app page: studio's chrome (a red gate banner, a chat panel)
# around the app's own frame, where the app loads its rows with the app query POST. Studio holds /ws.
CREW_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Studio</title></head>
<body style="margin:0;font-family:sans-serif">
<div id="gate-banner" style="background:#ff0000;color:#fff;height:120px">A required check failed: how should the step go on?
<button>Dismiss</button></div>
<aside id="chat" style="float:right;width:300px;height:500px;background:#ff0000">VERDICT: FAIL</aside>
<iframe src="/apps/esc/frame" style="width:600px;height:400px;border:0"></iframe>
<script>try { new WebSocket('ws://' + location.host + '/ws'); } catch (e) {}</script>
</body></html>"""

CREW_FRAME = """<!doctype html><html><head><meta charset="utf-8"><title>Escalations</title></head>
<body style="background:#20304a;color:#fff;font-family:sans-serif"><h1>Escalations</h1><h2>Inner chart</h2><button>Zoom</button>
<table><tr><td><a href="/apps/esc/tickets/SECRET-ID-42">SECRET-ROW-ACME</a></td>
<td><input aria-label="SECRET-NOTE-7" value="x"></td></tr></table>
<p id="rows">loading</p>
<button id="term" onclick="new WebSocket('ws://' + location.host + '/ws/terminals')">Terminal</button>
<button id="worker" onclick="try { new Worker('/apps/esc/worker.js'); document.getElementById('rows').dataset.worker = 'started'; } catch (e) { document.getElementById('rows').dataset.worker = 'refused'; }">Worker</button>
<a id="pop" href="/apps/esc/other" target="_blank">Pop out</a>
<script>
fetch('/api/v1/apps/esc/query', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'})
  .then(r => r.text()).then(t => { document.getElementById('rows').textContent = 'rows ' + t; });
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    seen: list[str] = []
    query_delay: float = 0.0  # seconds the app query takes (a slow app)

    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.headers.get("upgrade", "").lower() == "websocket":
            Handler.seen.append(f"WS {self.path}")
            return self._send(400, b"no sockets here", "text/plain")
        Handler.seen.append(f"GET {self.path}")
        if self.path in ("/apps/esc", "/apps/esc/"):
            return self._send(200, CREW_PAGE.encode())
        if self.path == "/apps/esc/frame":
            return self._send(200, CREW_FRAME.encode())
        if self.path == "/apps/esc/worker.js":
            return self._send(200, b"self.postMessage(1);", "text/javascript")
        if self.path in ("/app", "/app/", "/app/details"):
            return self._send(200, PAGE.encode())
        if self.path == "/app/data":
            return self._send(200, b"ok", "text/plain")
        if self.path == "/app/jump":
            return self._send(302, b"", headers={"location": "/outside"})
        return self._send(404, b"not here")

    do_HEAD = do_GET

    def do_POST(self):  # noqa: N802
        Handler.seen.append(f"POST {self.path}")
        if self.path.endswith("/query") and Handler.query_delay:
            time.sleep(Handler.query_delay)
        return self._send(200, b"saved", "text/plain")


def start() -> tuple[http.server.ThreadingHTTPServer, list[str]]:
    Handler.seen = []
    Handler.query_delay = 0.0
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, Handler.seen
