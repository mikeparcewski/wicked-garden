#!/usr/bin/env node
// HTTP probe for walkthrough integration tests (garden#1248): reads the fixture over HTTP at the
// origin the recorder hands every probe, and reports which port it reached.
const base = process.env.BASE_URL;
const port = process.env.PORT;
if (!base || !port || !base.endsWith(`:${port}`)) {
  process.stdout.write(JSON.stringify({ ok: false, base: base ?? null, port: port ?? null }) + "\n");
  process.exit(3);
}
const res = await fetch(`${base}/ready`);
process.stdout.write(JSON.stringify({ ok: res.ok, status: res.status, port: Number(port) }) + "\n");
process.exit(res.ok ? 0 : 4);
