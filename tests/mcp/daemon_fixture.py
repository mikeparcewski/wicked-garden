"""A local http.server playing the wicked-crew daemon's MCP registry routes, for the
``openapi`` and ``install`` action tests. Records every request; answers from a script."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeDaemon:
    def __init__(self):
        self.requests: list[dict] = []
        # (method, path) -> (status, body) or a callable(request) -> (status, body)
        self.routes: dict = {}
        daemon = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                req = {"method": self.command, "path": self.path, "raw": raw.decode("utf-8"),
                       "body": json.loads(raw) if raw else None}
                daemon.requests.append(req)
                answer = daemon.routes.get((self.command, self.path), (404, {"error": "no route"}))
                status, body = answer(req) if callable(answer) else answer
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_DELETE = _serve

            def log_message(self, *args):  # quiet
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def closed_origin() -> str:
    """An origin nothing listens on."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"
