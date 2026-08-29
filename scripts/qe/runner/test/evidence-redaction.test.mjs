/**
 * The TH-19 acceptance test: a captured wire body carrying a bearer token
 * NEVER reaches any written artifact — not wire.json, not result.json, not
 * the manifest. And when a secret shape survives the scrub (no matching
 * pattern at redaction time but caught by a per-target preflight pattern),
 * the claim flips to INCONCLUSIVE.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

// Isolate the ledger's fire-and-forget bus emissions from the user's real
// wicked-bus store — MUST be set before any DomainStore write.
process.env.WICKED_BUS_DATA_DIR = mkdtempSync(join(tmpdir(), "qe-runner-bus-"));

const { writeEvidence } = await import("../src/evidence.mjs");

const SECRET = "Bearer sekrit-token-AAAABBBBCCCCDDDD1234";
const COOKIE = "sid=deadbeefcafe0123; Path=/; HttpOnly";

function fakeRun(extraTargetRedact = undefined, smuggle = undefined) {
  const spec = {
    spec_version: "1.0",
    scenario: { id: "unit-redaction", name: "unit", project: "qe-runner-unit" },
    target: { base_url: "http://127.0.0.1:1", ...(extraTargetRedact ? { redact: extraTargetRedact } : {}) },
    steps: [{ action: "goto", path: "/" }],
    assertions: [{ id: "a", type: "wire", capture: "w", json_path: "body.ok", equals: true }],
  };
  const captures = {
    wire: {
      w: {
        responses: [
          {
            url: "http://127.0.0.1:1/api/x",
            status: 200,
            headers: { authorization: SECRET, "set-cookie": COOKIE, "content-type": "application/json" },
            body: { ok: true, note: `caller sent ${SECRET}`, ...(smuggle ? { smuggled: smuggle } : {}) },
            at: "2026-08-29T00:00:00Z",
          },
        ],
      },
    },
    websockets: [],
    wsFirstFrame: undefined,
    readbacks: {
      h: { id: "h", url: "http://127.0.0.1:1/api/x", method: "GET", request_headers: { Authorization: SECRET }, status: 200, body: { ok: true }, at: "t" },
    },
    console: [{ type: "error", text: `boom with ${SECRET}`, at: "t" }],
  };
  return { spec, captures };
}

function writeToTmp(overrides = {}) {
  const repoRoot = mkdtempSync(join(tmpdir(), "qe-runner-evidence-"));
  const { spec, captures } = fakeRun(overrides.redact, overrides.smuggle);
  const out = writeEvidence({
    spec,
    captures,
    assertionResults: [{ id: "a", type: "wire", ok: true, detail: {}, failures: [] }],
    stepLog: [{ index: 0, action: "goto", ok: true, started_at: "t", finished_at: "t" }],
    repoRoot,
    claim: "PASS",
    claimReason: "1/1 assertions passed",
    startedAt: "2026-08-29T00:00:00.000Z",
    finishedAt: "2026-08-29T00:00:05.000Z",
  });
  return { repoRoot, out };
}

test("a captured bearer token never reaches any written artifact", () => {
  const { out } = writeToTmp();
  const files = readdirSync(out.evidenceDir);
  assert.ok(files.includes("manifest.json"));
  for (const f of files) {
    const text = readFileSync(join(out.evidenceDir, f), "utf8");
    assert.ok(!text.includes("sekrit-token"), `${f} leaked the bearer token`);
    assert.ok(!text.includes("deadbeefcafe0123"), `${f} leaked the cookie`);
  }
  // Fully scrubbed => no preflight hit => claim stays PASS.
  assert.equal(out.claim, "PASS");
  assert.equal(out.preflight.length, 0);
  // The scrub is a scrub, not a deletion: redacted markers are present.
  const wire = readFileSync(join(out.evidenceDir, "wire.json"), "utf8");
  assert.ok(wire.includes("[REDACTED:"));
});

test("evidence dir + ledger layout: .wicked-qe/evidence/<run-id>/ with the installed ledger's manifest version", () => {
  const { repoRoot, out } = writeToTmp();
  assert.ok(out.evidenceDir.startsWith(join(repoRoot, ".wicked-qe", "evidence")));
  const manifest = JSON.parse(readFileSync(out.manifestPath, "utf8"));
  // Floor-agnostic (TH-6): 2.0.0 on the published ledger, 2.1.0 once XC-4
  // bumps the floor — pin the MAJOR, mirror the installed contract exactly.
  const { MANIFEST_VERSION } = require("wicked-ledger/manifest");
  assert.match(manifest.manifest_version, /^2\.\d+\.\d+$/);
  assert.equal(manifest.manifest_version, MANIFEST_VERSION);
  assert.equal(manifest.run_id, out.runId);
  assert.equal(manifest.status, "passed");
  assert.equal(manifest.verdict.reviewer, "qe-runner/executor-claim");
  assert.ok(manifest.verdict.reason.includes("executor claim"));
  assert.ok(manifest.artifacts.some((a) => a.name === "wire.json"));
  assert.ok(manifest.artifacts.every((a) => /^[a-f0-9]{64}$/.test(a.sha256)));
  // ledger rows exist (JSON canonical store or sqlite — either mode)
  const projects = readdirSync(join(repoRoot, ".wicked-qe"));
  assert.ok(projects.length > 0);
});

test("per-target patterns scrub custom secret shapes at layer 2", () => {
  const { out } = writeToTmp({
    redact: { patterns: ["zz9-[a-z0-9-]{10,}"] },
    smuggle: "zz9-supersecret-cred-0011223344",
  });
  const wire = readFileSync(join(out.evidenceDir, "wire.json"), "utf8");
  assert.ok(!wire.includes("zz9-supersecret-cred"), "per-target pattern must scrub the value");
  assert.equal(out.claim, "PASS", "fully scrubbed evidence keeps the claim");
  assert.equal(out.preflight.length, 0);
});

test("preflight INCONCLUSIVE + quarantine: a leak only visible in serialized form", () => {
  // A per-target pattern written against the SERIALIZED artifact shape
  // ('"smuggled": "...'). The layer-2 scrub runs on bare string VALUES, so
  // it cannot match — the preflight (which scans final serialized text) is
  // the only line of defense, exactly the safety net TH-19 requires.
  const { out } = writeToTmp({
    redact: { patterns: ['"smuggled": "zz9-[a-z0-9-]{10,}"'] },
    smuggle: "zz9-supersecret-cred-0011223344",
  });
  assert.equal(out.claim, "INCONCLUSIVE", "preflight hit must flip the claim (deny-dominates)");
  assert.ok(out.claimReason.includes("secret-scan preflight"));
  assert.ok(out.preflight.length >= 1);
  // The offending artifact is QUARANTINED — the secret reaches no written file.
  const files = readdirSync(out.evidenceDir);
  for (const f of files) {
    const text = readFileSync(join(out.evidenceDir, f), "utf8");
    assert.ok(!text.includes("zz9-supersecret-cred"), `${f} leaked the smuggled secret`);
  }
  const wire = JSON.parse(readFileSync(join(out.evidenceDir, "wire.json"), "utf8"));
  assert.equal(wire.quarantined, true);
  assert.equal(typeof wire.hits[0].pattern, "string");
  const manifest = JSON.parse(readFileSync(out.manifestPath, "utf8"));
  assert.equal(manifest.verdict.value, "INCONCLUSIVE");
  assert.equal(manifest.status, "inconclusive");
});

test("smoke the CLI lint path end-to-end (exit 4 on a status-only spec)", () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "qe-runner-cli-"));
  const bad = join(repoRoot, "bad.spec.json");
  const spec = {
    spec_version: "1.0",
    scenario: { id: "bad", name: "bad", project: "p" },
    target: { base_url: "http://127.0.0.1:1" },
    steps: [{ action: "goto", path: "/" }],
    assertions: [{ id: "only200", type: "wire", capture: "w", status: 200 }],
  };
  execFileSync("node", ["-e", `require('fs').writeFileSync(${JSON.stringify(bad)}, ${JSON.stringify(JSON.stringify(spec))})`]);
  let code = 0;
  try {
    execFileSync("node", [new URL("../bin/qe-run.mjs", import.meta.url).pathname, bad, "--lint-only"], { encoding: "utf8" });
  } catch (e) {
    code = e.status;
  }
  assert.equal(code, 4);
});
