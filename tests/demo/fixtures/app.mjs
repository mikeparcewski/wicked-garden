#!/usr/bin/env node
// Minimal fixture HTTP server for walkthrough integration tests.
// ENV: PORT (required), DATA_DIR (where artifacts are written).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const PORT = Number(process.env.PORT || 3000);
const DATA_DIR = process.env.DATA_DIR || "./data";
fs.mkdirSync(DATA_DIR, { recursive: true });

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (req.method === "GET" && url.pathname === "/ready") {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("ok");
    return;
  }

  if (req.method === "GET" && url.pathname === "/") {
    const body = `<!doctype html><html><body>
<h1>Fixture App</h1>
<p id="status">Ready</p>
<button id="go">Run</button>
<script>
  document.getElementById('go').onclick = () => {
    fetch('/api/run', { method: 'POST', body: JSON.stringify({ action: 'run' }), headers: { 'content-type': 'application/json' } })
      .then(() => { document.getElementById('status').textContent = 'Done'; });
  };
</script>
</body></html>`;
    res.writeHead(200, { "content-type": "text/html", "content-length": Buffer.byteLength(body) });
    res.end(body);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/run") {
    const record = { ran_at: new Date().toISOString() };
    fs.writeFileSync(path.join(DATA_DIR, "run.json"), JSON.stringify(record));
    res.writeHead(204);
    res.end();
    return;
  }

  res.writeHead(404);
  res.end("not found");
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(`listening on http://127.0.0.1:${PORT}\n`);
});
