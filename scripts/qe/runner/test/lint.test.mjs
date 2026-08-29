import test from "node:test";
import assert from "node:assert/strict";
import { lintSpec } from "../src/lint.mjs";
import { interpolate } from "../src/spec.mjs";

const GOOD = {
  spec_version: "1.0",
  scenario: { id: "s-good", name: "good spec", project: "demo" },
  target: { base_url: "http://127.0.0.1:1" },
  steps: [
    { action: "goto", path: "/" },
    { action: "waitFor", selector: "[data-testid=x]" },
  ],
  assertions: [
    { id: "a1", type: "wire", capture: "health", status: 200, json_path: "body.status", equals: "ok" },
  ],
};

test("a good spec passes", () => {
  const r = lintSpec(GOOD);
  assert.deepEqual(r.errors, []);
  assert.ok(r.ok);
});

test("status-only assertion is rejected", () => {
  const spec = structuredClone(GOOD);
  spec.assertions = [{ id: "just200", type: "wire", capture: "health", status: 200 }];
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes("status-only assertion")), r.errors.join("; "));
});

test("status-only readBack is rejected too", () => {
  const spec = structuredClone(GOOD);
  spec.assertions = [
    { id: "content", type: "wire", capture: "health", json_path: "body.status", equals: "ok" },
    { id: "just200", type: "readBack", capture: "h", status: 200 },
  ];
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes("status-only assertion")));
});

test("a spec with zero content-bearing assertions is rejected", () => {
  const spec = structuredClone(GOOD);
  spec.assertions = [{ id: "ws", type: "ws", min_count: 1 }];
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes("content-bearing")));
});

test("fixed sleeps are rejected in every disguise", () => {
  for (const step of [
    { action: "sleep", ms: 1500 },
    { action: "waitForTimeout", timeout: 1500 },
    { action: "pause" },
    { action: "goto", path: "/", sleep_ms: 500 },
    { action: "waitFor", selector: "x", delay_ms: 100 },
  ]) {
    const spec = structuredClone(GOOD);
    spec.steps = [step];
    const r = lintSpec(spec);
    assert.ok(!r.ok, `should reject ${JSON.stringify(step)}`);
    assert.ok(
      r.errors.some((e) => e.includes("forbidden") || e.includes("unknown action")),
      r.errors.join("; "),
    );
  }
});

test("viewport / headless / console overrides are rejected (non-configurable)", () => {
  for (const [k, patch] of [
    ["viewport", (s) => (s.target.viewport = { width: 800, height: 600 })],
    ["headless", (s) => (s.target.headless = false)],
    ["console", (s) => (s.console = { capture: false })],
  ]) {
    const spec = structuredClone(GOOD);
    patch(spec);
    const r = lintSpec(spec);
    assert.ok(!r.ok, `${k} override should be rejected`);
    assert.ok(r.errors.some((e) => e.includes("non-configurable")));
  }
});

test("unknown actions and assertion types are rejected (deterministic vocabulary)", () => {
  const spec = structuredClone(GOOD);
  spec.steps = [{ action: "evaluate", js: "alert(1)" }];
  spec.assertions = [{ id: "x", type: "llmJudge" }];
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes('unknown action "evaluate"')));
  assert.ok(r.errors.some((e) => e.includes('unknown type "llmJudge"')));
});

test("dbAssert must be a read-only SELECT", () => {
  const spec = structuredClone(GOOD);
  spec.assertions.push({ id: "bad", type: "dbAssert", db: "x.db", sql: "DELETE FROM runs", expect: { rows: 0 } });
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes("read-only")));
});

test("empty assertions are rejected", () => {
  const spec = structuredClone(GOOD);
  spec.assertions = [];
  const r = lintSpec(spec);
  assert.ok(!r.ok);
  assert.ok(r.errors.some((e) => e.includes("asserts nothing")));
});

test("env interpolation: value, fallback, missing", () => {
  const missing = [];
  const out = interpolate(
    { a: "${env:QE_T_SET}", b: "${env:QE_T_UNSET:-fb}", c: "${env:QE_T_GONE}" },
    { QE_T_SET: "v1" },
    missing,
  );
  assert.equal(out.a, "v1");
  assert.equal(out.b, "fb");
  assert.deepEqual(missing, ["QE_T_GONE"]);
});
