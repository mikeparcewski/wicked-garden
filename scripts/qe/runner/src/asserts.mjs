/**
 * src/asserts.mjs — the generalized assertion helpers (TH-4 item 2).
 *
 *  - readBack(baseUrl, step)     assert-by-read-back: fetch the state the UI
 *                                claims to have changed and record it
 *  - dbAssert(assertion)         run a read-only SQL SELECT against a SQLite
 *                                db (node:sqlite) and compare
 *  - cliCrossCheck(assertion,…)  run a CLI (argv array, no shell) and diff
 *                                its output against an expected value or a
 *                                captured readBack/wire value
 *  - evaluateAssertions(...)     drive the whole assertion list over the
 *                                captures produced by the run
 *
 * Everything here is deterministic and model-free. Failures return
 * structured results — they never throw past evaluateAssertions.
 */

import { spawnSync } from "node:child_process";

// --- shared -----------------------------------------------------------------

/** Resolve a dotted path ("body.status", "rows.0.name") into a value. */
export function jsonPath(value, path) {
  if (path === undefined || path === null || path === "") return value;
  let cur = value;
  for (const seg of String(path).split(".")) {
    if (cur === null || cur === undefined) return undefined;
    cur = cur[seg];
  }
  return cur;
}

function checkContent(actual, a) {
  const checks = [];
  if (a.equals !== undefined) checks.push([actual === a.equals || String(actual) === String(a.equals), `equals ${JSON.stringify(a.equals)}`]);
  if (a.matches !== undefined) checks.push([new RegExp(a.matches).test(String(actual)), `matches /${a.matches}/`]);
  if (a.contains !== undefined) checks.push([String(actual).includes(String(a.contains)), `contains ${JSON.stringify(a.contains)}`]);
  if (a.not_contains !== undefined) checks.push([!String(actual).includes(String(a.not_contains)), `not_contains ${JSON.stringify(a.not_contains)}`]);
  const failed = checks.filter(([ok]) => !ok).map(([, label]) => label);
  return { ok: failed.length === 0, failed };
}

// --- readBack ----------------------------------------------------------------

/**
 * Execute a readBack step: a server-side fetch of `base_url + path`, recorded
 * as a capture. The RAW response is used for live assertion evaluation; the
 * PERSISTED copy is redacted by the evidence writer, never here — assertions
 * must see real content, artifacts must not.
 */
export async function readBack(baseUrl, step) {
  const url = new URL(step.path, baseUrl).toString();
  const started = new Date().toISOString();
  const res = await fetch(url, {
    method: step.method ?? "GET",
    headers: step.headers ?? {},
    body: step.body !== undefined ? JSON.stringify(step.body) : undefined,
  });
  const text = await res.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text; }
  return {
    id: step.id,
    url,
    method: step.method ?? "GET",
    request_headers: step.headers ?? {},
    status: res.status,
    body,
    at: started,
  };
}

// --- dbAssert ----------------------------------------------------------------

/**
 * Read-only SQLite assertion via node:sqlite (ships with Node >= 22.5 — no
 * native build, works on macOS/Linux/Windows alike). The lint guarantees the
 * SQL is a SELECT; the connection is opened read-only anyway.
 *
 * expect: { rows?: n, min_rows?: n, value?: x (first column of first row),
 *           json_path? + equals/matches/contains applied to the rows array }
 */
export async function dbAssert(a) {
  const { DatabaseSync } = await import("node:sqlite");
  let db;
  try {
    db = new DatabaseSync(a.db, { readOnly: true });
    const rows = db.prepare(a.sql).all();
    const detail = { rows: rows.length };
    const failures = [];
    const expect = a.expect ?? {};
    if (expect.rows !== undefined && rows.length !== expect.rows) {
      failures.push(`expected ${expect.rows} rows, got ${rows.length}`);
    }
    if (expect.min_rows !== undefined && rows.length < expect.min_rows) {
      failures.push(`expected >= ${expect.min_rows} rows, got ${rows.length}`);
    }
    if (expect.value !== undefined) {
      const first = rows[0] ? Object.values(rows[0])[0] : undefined;
      detail.value = first;
      // node:sqlite returns integers as BigInt in some configurations —
      // compare loosely via String to stay honest about content.
      if (first !== expect.value && String(first) !== String(expect.value)) {
        failures.push(`expected first value ${JSON.stringify(expect.value)}, got ${JSON.stringify(String(first))}`);
      }
    }
    if (a.json_path !== undefined || a.equals !== undefined || a.matches !== undefined || a.contains !== undefined) {
      const actual = jsonPath(rows, a.json_path);
      const c = checkContent(actual, a);
      if (!c.ok) failures.push(...c.failed.map((f) => `rows${a.json_path ? "." + a.json_path : ""} failed ${f}`));
    }
    return { ok: failures.length === 0, detail, failures };
  } catch (e) {
    return { ok: false, detail: {}, failures: [`dbAssert error: ${e.message}`] };
  } finally {
    try { db?.close(); } catch { /* already closed */ }
  }
}

// --- cliCrossCheck -------------------------------------------------------------

/**
 * Run a CLI (argv array — never a shell string) and diff its output against
 * an expectation or a captured value. Cross-checking the same fact through a
 * second, independent channel is what turns "the UI said so" into evidence.
 *
 * a.cmd: ["node", "-e", "..."]     a.parse: "json" | "text" (default json-try)
 * a.json_path: path into parsed stdout
 * a.expect_equals / a.expect_matches: direct expectation
 * a.compare_to: { kind: "readBack"|"wire", capture: "<id>", json_path: "..." }
 *               → the CLI value must equal the captured value
 */
export function cliCrossCheck(a, captures) {
  const res = spawnSync(a.cmd[0], a.cmd.slice(1), {
    encoding: "utf8",
    timeout: a.timeout_ms ?? 60_000,
    shell: false,
  });
  if (res.error) return { ok: false, detail: {}, failures: [`cliCrossCheck spawn error: ${res.error.message}`] };
  if (res.status !== 0) {
    return { ok: false, detail: { exit: res.status }, failures: [`cliCrossCheck exit ${res.status}: ${String(res.stderr).slice(0, 300)}`] };
  }
  const stdout = String(res.stdout).trim();
  let parsed = stdout;
  if (a.parse !== "text") {
    try { parsed = JSON.parse(stdout); } catch { parsed = stdout; }
  }
  const actual = jsonPath(parsed, a.json_path);
  const failures = [];
  const detail = { exit: 0, actual };
  if (a.expect_equals !== undefined && actual !== a.expect_equals && String(actual) !== String(a.expect_equals)) {
    failures.push(`expected ${JSON.stringify(a.expect_equals)}, got ${JSON.stringify(actual)}`);
  }
  if (a.expect_matches !== undefined && !new RegExp(a.expect_matches).test(String(actual))) {
    failures.push(`expected match /${a.expect_matches}/, got ${JSON.stringify(String(actual))}`);
  }
  if (a.compare_to !== undefined) {
    const pool = a.compare_to.kind === "wire" ? captures.wire[a.compare_to.capture]?.responses : [captures.readbacks[a.compare_to.capture]];
    const source = Array.isArray(pool) ? pool[0] : pool;
    const other = jsonPath(source, a.compare_to.json_path);
    detail.compared_against = other;
    if (other === undefined) failures.push(`compare_to capture "${a.compare_to.capture}" has no value at ${a.compare_to.json_path}`);
    else if (actual !== other && String(actual) !== String(other)) {
      failures.push(`CLI value ${JSON.stringify(actual)} != captured value ${JSON.stringify(other)}`);
    }
  }
  return { ok: failures.length === 0, detail, failures };
}

// --- the evaluator -------------------------------------------------------------

/**
 * Evaluate every assertion against the captures. `page` is the live
 * Playwright page (still open) for pageText assertions.
 *
 * Returns [{ id, type, ok, detail, failures }] — one row per assertion,
 * never throws.
 */
export async function evaluateAssertions(spec, captures, page) {
  const results = [];
  for (const a of spec.assertions) {
    let r;
    try {
      switch (a.type) {
        case "wire": {
          const cap = captures.wire[a.capture];
          const responses = cap?.responses ?? [];
          const failures = [];
          const min = a.min_count ?? 1;
          if (responses.length < min) failures.push(`expected >= ${min} captured responses, got ${responses.length}`);
          const target = a.last ? responses[responses.length - 1] : responses[0];
          if (target) {
            if (a.status !== undefined && target.status !== a.status) failures.push(`expected status ${a.status}, got ${target.status}`);
            if (a.json_path !== undefined || a.equals !== undefined || a.matches !== undefined || a.contains !== undefined || a.not_contains !== undefined) {
              const actual = jsonPath(target, a.json_path);
              const c = checkContent(actual, a);
              if (!c.ok) failures.push(...c.failed.map((f) => `${a.json_path} failed ${f} (actual ${JSON.stringify(actual)?.slice(0, 200)})`));
            }
            if (a.body_contains !== undefined && !JSON.stringify(target.body ?? "").includes(a.body_contains)) {
              failures.push(`body does not contain ${JSON.stringify(a.body_contains)}`);
            }
          } else if (a.status !== undefined || a.json_path !== undefined) {
            failures.push("no captured response to assert against");
          }
          r = { ok: failures.length === 0, detail: { count: responses.length }, failures };
          break;
        }
        case "ws": {
          const failures = [];
          const min = a.min_count ?? 1;
          if (captures.websockets.length < min) failures.push(`expected >= ${min} websocket connections, got ${captures.websockets.length}`);
          if (a.first_frame_matches !== undefined) {
            const frame = captures.wsFirstFrame;
            if (frame === undefined) failures.push("no websocket frame captured");
            else if (!new RegExp(a.first_frame_matches).test(frame)) failures.push(`first frame does not match /${a.first_frame_matches}/`);
          }
          r = { ok: failures.length === 0, detail: { count: captures.websockets.length }, failures };
          break;
        }
        case "readBack": {
          const cap = captures.readbacks[a.capture];
          const failures = [];
          if (!cap) failures.push(`no readBack capture "${a.capture}" — did the step run?`);
          else {
            if (a.status !== undefined && cap.status !== a.status) failures.push(`expected status ${a.status}, got ${cap.status}`);
            if (a.json_path !== undefined || a.equals !== undefined || a.matches !== undefined || a.contains !== undefined || a.not_contains !== undefined) {
              const actual = jsonPath(cap, a.json_path);
              const c = checkContent(actual, a);
              if (!c.ok) failures.push(...c.failed.map((f) => `${a.json_path} failed ${f} (actual ${JSON.stringify(actual)?.slice(0, 200)})`));
            }
            if (a.body_contains !== undefined && !JSON.stringify(cap.body ?? "").includes(a.body_contains)) {
              failures.push(`body does not contain ${JSON.stringify(a.body_contains)}`);
            }
          }
          r = { ok: failures.length === 0, detail: cap ? { status: cap.status } : {}, failures };
          break;
        }
        case "pageText": {
          const text = await page.locator(a.selector).innerText({ timeout: a.timeout_ms ?? 10_000 });
          const c = checkContent(text, a);
          r = { ok: c.ok, detail: { length: text.length }, failures: c.failed.map((f) => `page text at ${a.selector} failed ${f}`) };
          break;
        }
        case "console": {
          const errors = captures.console.filter((m) => m.type === "error");
          const ok = errors.length <= a.max_errors;
          r = { ok, detail: { errors: errors.length }, failures: ok ? [] : [`${errors.length} console errors > max ${a.max_errors}`] };
          break;
        }
        case "dbAssert":
          r = await dbAssert(a);
          break;
        case "cliCrossCheck":
          r = cliCrossCheck(a, captures);
          break;
        default:
          r = { ok: false, detail: {}, failures: [`unknown assertion type ${a.type}`] };
      }
    } catch (e) {
      r = { ok: false, detail: {}, failures: [`assertion error: ${e.message}`] };
    }
    results.push({ id: a.id, type: a.type, ...r });
  }
  return results;
}
