/**
 * test/th6-gate-wiring.test.mjs — TH-6: campaign evidence wired through
 * wicked-ledger + gate.mjs.
 *
 *  - resolveGateLedgerRoot mirrors the TH-2 semantics shared by crew's
 *    qeLedgerRoot and the runner's resolveLedgerRoot (env pin: absolute IS
 *    the root, relative joins the base) — the verdict row must land in the
 *    SAME store the runner wrote its runs row to.
 *  - validateManifestForGate enforces the TH-5 rule at the recording seam:
 *    a nonconforming bundle downgrades to SYSTEM_ERROR (→ INCONCLUSIVE,
 *    deny-dominates); legacy bundles and pre-2.1 ledgers skip with a note.
 *  - buildScenarioEvidence produces the manifest-2.1 block from run
 *    material without leaking step values.
 *  - the lint admits/reject the new claim_level/legs vocabulary and enforces
 *    the honest-cap invariant.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { join, sep } from "node:path";
import { tmpdir } from "node:os";

import { resolveGateLedgerRoot, validateManifestForGate } from "../../lib/gate.mjs";
import { buildScenarioEvidence, resolveLedgerRoot } from "../src/evidence.mjs";
import { lintSpec } from "../src/lint.mjs";

// ---- resolveGateLedgerRoot ---------------------------------------------------

test("gate root: absolute WICKED_QE_LEDGER_DIR pins exactly", () => {
  const abs = `${sep}srv${sep}qe-ledger`;
  const got = resolveGateLedgerRoot("/repo", { WICKED_QE_LEDGER_DIR: abs }, {});
  assert.equal(got, abs);
});

test("gate root: relative WICKED_QE_LEDGER_DIR joins the base dir", () => {
  const got = resolveGateLedgerRoot("/repo", { WICKED_QE_LEDGER_DIR: "qe-ledger" }, {});
  assert.equal(got, join("/repo", "qe-ledger"));
});

test("gate root: no env → ledger's own dual-read resolution", () => {
  const got = resolveGateLedgerRoot(
    "/repo",
    {},
    { resolveLedgerRoot: (base) => join(base, ".wicked-testing") },
  );
  assert.equal(got, join("/repo", ".wicked-testing"));
});

test("gate root: no env, no ledger helper → .wicked-qe default", () => {
  assert.equal(resolveGateLedgerRoot("/repo", {}, {}), join("/repo", ".wicked-qe"));
});

test("gate root: identical semantics to the runner's writer resolution", () => {
  // The seam invariant itself: writer and gate MUST resolve the same root.
  const env = { WICKED_QE_LEDGER_DIR: `${sep}pinned${sep}root` };
  assert.equal(
    resolveGateLedgerRoot("/repo", env, {}),
    resolveLedgerRoot("/repo", env),
  );
  const rel = { WICKED_QE_LEDGER_DIR: "rel-ledger" };
  assert.equal(
    resolveGateLedgerRoot("/repo", rel, {}),
    resolveLedgerRoot("/repo", rel),
  );
});

// ---- validateManifestForGate ---------------------------------------------------

function tempEvidenceDir() {
  const dir = mkdtempSync(join(tmpdir(), "th6-gate-"));
  mkdirSync(dir, { recursive: true });
  return dir;
}

test("manifest validation: missing manifest.json skips (legacy bundle), verdict unchanged", () => {
  const dir = tempEvidenceDir();
  const r = validateManifestForGate({
    evidencePath: dir,
    ledger: { validateManifest: () => ({ ok: false, violations: [] }) },
    verdict: "PASS",
    verdictSummary: "all green",
  });
  assert.equal(r.ran, false);
  assert.equal(r.verdict, "PASS");
  assert.match(r.note, /no manifest\.json/);
});

test("manifest validation: pre-2.1 ledger (no validateManifest) skips with a note", () => {
  const dir = tempEvidenceDir();
  writeFileSync(join(dir, "manifest.json"), JSON.stringify({ manifest_version: "2.0.0", run_id: "r1" }));
  const r = validateManifestForGate({
    evidencePath: dir,
    ledger: {},
    verdict: "PASS",
    verdictSummary: "all green",
  });
  assert.equal(r.ran, false);
  assert.equal(r.verdict, "PASS");
  assert.match(r.note, /pre-2\.1/);
});

test("manifest validation: contract violation downgrades PASS → SYSTEM_ERROR (deny-dominates)", () => {
  const dir = tempEvidenceDir();
  writeFileSync(join(dir, "manifest.json"), JSON.stringify({ manifest_version: "2.1.0", run_id: "r1" }));
  const r = validateManifestForGate({
    evidencePath: dir,
    ledger: {
      validateManifest: () => ({
        ok: false,
        violations: [{ field: "scenario_evidence.claim_level", message: "invalid claim_level 'gold'" }],
      }),
    },
    verdict: "PASS",
    verdictSummary: "executor claimed pass",
  });
  assert.equal(r.ran, true);
  assert.equal(r.ok, false);
  assert.equal(r.verdict, "SYSTEM_ERROR");
  assert.match(r.verdictSummary, /scenario_evidence\.claim_level/);
  assert.match(r.verdictSummary, /original verdict PASS/);
});

test("manifest validation: unparseable manifest downgrades (never graded)", () => {
  const dir = tempEvidenceDir();
  writeFileSync(join(dir, "manifest.json"), "{not json");
  const r = validateManifestForGate({
    evidencePath: dir,
    ledger: { validateManifest: () => ({ ok: true, violations: [] }) },
    verdict: "FAIL",
    verdictSummary: "executor claimed fail",
  });
  assert.equal(r.ran, true);
  assert.equal(r.ok, false);
  assert.equal(r.verdict, "SYSTEM_ERROR");
});

test("manifest validation: conforming bundle records the graded verdict unchanged", () => {
  const dir = tempEvidenceDir();
  writeFileSync(join(dir, "manifest.json"), JSON.stringify({ manifest_version: "2.1.0", run_id: "r1" }));
  const r = validateManifestForGate({
    evidencePath: dir,
    ledger: { validateManifest: () => ({ ok: true, violations: [] }) },
    verdict: "PASS",
    verdictSummary: "graded pass",
  });
  assert.deepEqual([r.ran, r.ok, r.verdict, r.verdictSummary], [true, true, "PASS", "graded pass"]);
});

// ---- buildScenarioEvidence -----------------------------------------------------

const SPEC = {
  scenario: {
    id: "crew-acceptance-gate.th6-dod",
    name: "dod",
    project: "wicked-crew-studio",
    claim_level: "machinery-verified",
    legs: [
      { leg: "studio-home-ui", claim_level: "certified" },
      { leg: "daemon-state-cross-check", claim_level: "machinery-verified", reason: "REST/db cross-check" },
    ],
  },
  target: { kind: "browser", base_url: "http://127.0.0.1:7906" },
  steps: [
    { action: "goto", path: "/" },
    { action: "fill", selector: "#token", value: "super-secret-value" },
    { action: "screenshot", name: "th6-home-connected" },
    { action: "readBack", id: "health-readback", path: "/api/v1/health" },
  ],
};

const STEP_LOG = [
  { index: 0, action: "goto", ok: true, detail: {} },
  { index: 1, action: "fill", ok: true, detail: {} },
  { index: 2, action: "screenshot", ok: true, detail: { screenshot: "th6-home-connected.png" } },
  { index: 3, action: "readBack", ok: true, detail: { status: 200 } },
];

const ASSERTIONS = [
  { id: "ws-connected", type: "ws", ok: true, detail: { count: 1 }, failures: [] },
  { id: "health-content", type: "readBack", ok: true, detail: { status: 200 }, failures: [] },
  { id: "daemon-db-isolated", type: "dbAssert", ok: true, detail: {}, failures: [] },
];

const CAPTURES = {
  wire: { health: { responses: [{ status: 200 }] } },
  websockets: [{ url: "ws://x" }],
  readbacks: { "health-readback": { status: 200 } },
  console: [],
};

test("scenario_evidence: 8-key campaign shape with claim_level + legs from the spec", () => {
  const se = buildScenarioEvidence({
    spec: SPEC,
    claim: "PASS",
    claimReason: "3/3 assertions passed",
    stepLog: STEP_LOG,
    assertionResults: ASSERTIONS,
    captures: CAPTURES,
  });
  assert.equal(se.scenario, "crew-acceptance-gate.th6-dod");
  assert.equal(se.status, "PASS");
  assert.equal(se.claim_level, "machinery-verified");
  assert.deepEqual(se.screenshots, ["th6-home-connected.png"]);
  assert.equal(se.legs.length, 2);
  assert.equal(se.wire_evidence.capture_counts.health, 1);
  assert.equal(se.wire_evidence.websocket_connections, 1);
  assert.match(se.terminal_state_proof, /readBack health-content: ok/);
  assert.match(se.terminal_state_proof, /dbAssert daemon-db-isolated: ok/);
  assert.equal(se.notes, "3/3 assertions passed");
});

test("scenario_evidence: ui_steps carry selectors/paths, never step VALUES", () => {
  const se = buildScenarioEvidence({
    spec: SPEC,
    claim: "PASS",
    claimReason: "ok",
    stepLog: STEP_LOG,
    assertionResults: ASSERTIONS,
    captures: CAPTURES,
  });
  const text = JSON.stringify(se.ui_steps);
  assert.match(text, /#token/);
  assert.doesNotMatch(text, /super-secret-value/);
});

test("scenario_evidence: claim_level defaults to machinery-verified (conservative floor)", () => {
  const spec = { ...SPEC, scenario: { id: "x", name: "x", project: "p" } };
  const se = buildScenarioEvidence({
    spec,
    claim: "FAIL",
    claimReason: "1 failed",
    stepLog: [],
    assertionResults: [],
    captures: { wire: {}, websockets: [], readbacks: {}, console: [] },
  });
  assert.equal(se.claim_level, "machinery-verified");
  assert.equal(se.legs, undefined);
});

// ---- lint: claim_level / legs vocabulary ---------------------------------------

function minimalSpec(scenarioExtra = {}) {
  return {
    spec_version: "1.0",
    scenario: { id: "s", name: "n", project: "p", ...scenarioExtra },
    target: { kind: "browser", base_url: "http://x" },
    steps: [{ action: "goto", path: "/" }],
    assertions: [
      { id: "a", type: "readBack", capture: "r", status: 200, json_path: "body.ok", equals: "yes" },
    ],
  };
}

test("lint: valid claim_level + legs pass", () => {
  const r = lintSpec(minimalSpec({
    claim_level: "machinery-verified",
    legs: [
      { leg: "ui", claim_level: "certified" },
      { leg: "api", claim_level: "machinery-verified" },
    ],
  }));
  assert.deepEqual(r.errors, []);
});

test("lint: 'skipped' is outcome-only — rejected as a planned claim_level", () => {
  const r = lintSpec(minimalSpec({ claim_level: "skipped" }));
  assert.ok(r.errors.some((e) => e.includes("outcome-only")));
});

test("lint: unknown claim_level rejected", () => {
  const r = lintSpec(minimalSpec({ claim_level: "gold-plated" }));
  assert.ok(r.errors.some((e) => e.includes("scenario.claim_level")));
});

test("lint: honest-cap invariant — scenario claim stronger than weakest leg rejected", () => {
  const r = lintSpec(minimalSpec({
    claim_level: "certified",
    legs: [
      { leg: "ui", claim_level: "certified" },
      { leg: "acceptance", claim_level: "machinery-verified" },
    ],
  }));
  assert.ok(r.errors.some((e) => e.includes("weakest leg")));
});

test("lint: legs floor with no explicit claim_level is fine (default is the floor)", () => {
  const r = lintSpec(minimalSpec({
    legs: [{ leg: "ui", claim_level: "certified" }],
  }));
  assert.deepEqual(r.errors, []);
});
