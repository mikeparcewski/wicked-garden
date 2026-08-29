import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { dbAssert, cliCrossCheck, jsonPath } from "../src/asserts.mjs";

test("jsonPath resolves dotted paths with array indices", () => {
  const v = { body: { rows: [{ name: "x" }] } };
  assert.equal(jsonPath(v, "body.rows.0.name"), "x");
  assert.equal(jsonPath(v, "body.missing.deep"), undefined);
  assert.equal(jsonPath(v, undefined), v);
});

test("dbAssert: rows/min_rows/value against a real sqlite db (node:sqlite)", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const dbPath = join(mkdtempSync(join(tmpdir(), "qe-dbassert-")), "t.db");
  const db = new DatabaseSync(dbPath);
  db.exec("CREATE TABLE runs (id TEXT, status TEXT)");
  db.exec("INSERT INTO runs VALUES ('r1','passed'), ('r2','failed')");
  db.close();

  const ok = await dbAssert({ db: dbPath, sql: "SELECT COUNT(*) FROM runs", expect: { value: 2 } });
  assert.ok(ok.ok, JSON.stringify(ok.failures));

  const rows = await dbAssert({ db: dbPath, sql: "SELECT * FROM runs WHERE status='passed'", expect: { rows: 1 } });
  assert.ok(rows.ok);

  const bad = await dbAssert({ db: dbPath, sql: "SELECT * FROM runs", expect: { rows: 5 } });
  assert.ok(!bad.ok);
  assert.match(bad.failures[0], /expected 5 rows, got 2/);

  const content = await dbAssert({ db: dbPath, sql: "SELECT status FROM runs ORDER BY id", json_path: "0.status", equals: "passed", expect: {} });
  assert.ok(content.ok, JSON.stringify(content.failures));
});

test("dbAssert: missing db is a failure, not a crash", async () => {
  const r = await dbAssert({ db: "/nonexistent/nope.db", sql: "SELECT 1", expect: { rows: 1 } });
  assert.ok(!r.ok);
  assert.match(r.failures[0], /dbAssert error/);
});

test("cliCrossCheck: expectation against CLI JSON output", () => {
  const r = cliCrossCheck(
    { cmd: ["node", "-e", "console.log(JSON.stringify({version:'1.2.3'}))"], json_path: "version", expect_matches: "^1\\.2\\." },
    { wire: {}, readbacks: {} },
  );
  assert.ok(r.ok, JSON.stringify(r.failures));
  assert.equal(r.detail.actual, "1.2.3");
});

test("cliCrossCheck: diff against a captured readBack value", () => {
  const captures = { wire: {}, readbacks: { health: { status: 200, body: { version: "0.7.0" } } } };
  const match = cliCrossCheck(
    {
      cmd: ["node", "-e", "console.log(JSON.stringify({v:'0.7.0'}))"],
      json_path: "v",
      compare_to: { kind: "readBack", capture: "health", json_path: "body.version" },
    },
    captures,
  );
  assert.ok(match.ok, JSON.stringify(match.failures));

  const diff = cliCrossCheck(
    {
      cmd: ["node", "-e", "console.log(JSON.stringify({v:'0.6.0'}))"],
      json_path: "v",
      compare_to: { kind: "readBack", capture: "health", json_path: "body.version" },
    },
    captures,
  );
  assert.ok(!diff.ok);
  assert.match(diff.failures[0], /!=/);
});

test("cliCrossCheck: non-zero exit is a failure with stderr context", () => {
  const r = cliCrossCheck({ cmd: ["node", "-e", "console.error('kaput'); process.exit(7)"] }, { wire: {}, readbacks: {} });
  assert.ok(!r.ok);
  assert.match(r.failures[0], /exit 7/);
  assert.match(r.failures[0], /kaput/);
});
