/**
 * TH-22 — fixture namespacing, the parallel-isolation default.
 *
 * Specs embed `${env:QE_FIXTURE_NS}` in every fixture name they create; the
 * runner guarantees the variable is always available to interpolation —
 * caller-set (the campaign mapper pins one per node) wins, otherwise a
 * per-run unique default is generated. The value feeds fixture NAMES only,
 * never runner behavior.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fixtureNamespace, loadSpec } from "../src/spec.mjs";

const NS_SPEC = {
  spec_version: "1.0",
  scenario: { id: "ns-check", name: "namespaced fixtures", project: "demo" },
  target: { base_url: "http://127.0.0.1:1" },
  steps: [
    { action: "goto", path: "/" },
    { action: "readBack", id: "proj", path: "/api/v1/projects/proj-${env:QE_FIXTURE_NS}" },
  ],
  assertions: [
    {
      id: "a1",
      type: "readBack",
      capture: "proj",
      json_path: "body.name",
      equals: "proj-${env:QE_FIXTURE_NS}",
    },
  ],
};

function writeSpec(spec) {
  const dir = mkdtempSync(join(tmpdir(), "qe-ns-"));
  const p = join(dir, "spec.json");
  writeFileSync(p, JSON.stringify(spec));
  return p;
}

test("caller-set QE_FIXTURE_NS always wins", () => {
  assert.equal(fixtureNamespace("seed", { QE_FIXTURE_NS: "node-7" }), "node-7");
});

test("generated namespaces are slugged, prefixed, and unique per call", () => {
  const a = fixtureNamespace("Studio S1 Smoke!", {});
  const b = fixtureNamespace("Studio S1 Smoke!", {});
  assert.match(a, /^qe-studio-s1-smoke-[a-z0-9]+-[0-9a-f]{6}$/);
  assert.notEqual(a, b); // two parallel nodes never collide
});

test("empty-string env value is treated as unset (interpolation semantics)", () => {
  const ns = fixtureNamespace("x", { QE_FIXTURE_NS: "" });
  assert.match(ns, /^qe-x-/);
});

test("loadSpec fills the QE_FIXTURE_NS default — no fail-closed unset error", () => {
  const p = writeSpec(NS_SPEC);
  const spec = loadSpec(p, {}); // launcher did not pin a namespace
  const path = spec.steps[1].path;
  assert.match(path, /^\/api\/v1\/projects\/proj-qe-ns-check-/);
  // every reference interpolates to the SAME per-run value
  assert.equal(spec.assertions[0].equals, path.replace("/api/v1/projects/", ""));
});

test("loadSpec uses the caller-set namespace verbatim", () => {
  const p = writeSpec(NS_SPEC);
  const spec = loadSpec(p, { QE_FIXTURE_NS: "node-42" });
  assert.equal(spec.steps[1].path, "/api/v1/projects/proj-node-42");
  assert.equal(spec.assertions[0].equals, "proj-node-42");
});

test("other unset env vars still fail closed — the default is NS-only", () => {
  const spec = structuredClone(NS_SPEC);
  spec.target.base_url = "${env:QE_SMOKE_BASE_URL}";
  const p = writeSpec(spec);
  assert.throws(
    () => loadSpec(p, {}),
    /required env var QE_SMOKE_BASE_URL is unset/,
  );
});
