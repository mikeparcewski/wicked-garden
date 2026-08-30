/**
 * test/th17-vault-evidence.test.mjs — TH-17: vault-backed evidence integrity.
 *
 * The two acceptance proofs (RECON-TEST-HARNESS test-R16):
 *   1. A campaign PASS is RE-DERIVABLE months later: the bundle is frozen
 *      into wicked-vault content-addressed (payload = manifest.json, which
 *      binds every artifact's sha256); `rederive` recomputes every hash —
 *      nothing time-dependent, no cached status is ever trusted — and any
 *      changed byte (artifact OR vault payload) diverges.
 *   2. ORDERING IS ENFORCED IN THE PIPELINE: a synthetic credential is
 *      scrubbed by the executor's TH-19 redaction BEFORE the vault write,
 *      and a bundle that provably did NOT go through redaction (missing
 *      marker, or forged marker with a residual secret) is REFUSED — the
 *      vault stays empty. Vault immutability makes leaks permanent, so the
 *      refusal happens in code, not in docs.
 *
 * Release dependency (documented in vault-evidence.mjs): these tests need
 * the wicked-vault manifest-2.1 twin, which is on wicked-vault main but
 * UNRELEASED (npm 0.6.0 predates it). Until the next wicked-vault release,
 * set WICKED_QE_VAULT_PKG to a local checkout of wicked-vault main; without
 * one the vault-dependent tests SKIP with that exact message (the pure
 * mapping/capability tests still run).
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync, mkdirSync, readFileSync, writeFileSync, readdirSync,
  existsSync, chmodSync, appendFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

// Isolate the ledger's fire-and-forget bus emissions from the user's real
// wicked-bus store — MUST be set before any DomainStore write.
process.env.WICKED_BUS_DATA_DIR = mkdtempSync(join(tmpdir(), "th17-bus-"));

const { writeEvidence } = await import("../src/evidence.mjs");
const {
  resolveVaultModule,
  checkVaultCapability,
  assertRedactionBeforeVault,
  recordEvidenceBundle,
  attestGrade,
  rederiveBundle,
  applyVaultIntegrity,
  verdictToOpinion,
  VaultEvidenceError,
  VAULT_RELEASE_REQUIREMENT,
} = await import("../../lib/vault-evidence.mjs");

const HERE = dirname(fileURLToPath(import.meta.url));

// ---- local wicked-vault (manifest-2.1 twin) resolution -------------------------
// 1. explicit WICKED_QE_VAULT_PKG; 2. the sibling checkout in the standard
// wicked projects layout (…/wicked/wicked-vault). Either must carry the 2.1
// twin (checkVaultCapability) or it is refused — a pre-2.1 vault never
// silently degrades these proofs.
async function loadLocalVault() {
  const candidates = [
    process.env.WICKED_QE_VAULT_PKG,
    join(HERE, "..", "..", "..", "..", "..", "wicked-vault"),
  ].filter(Boolean);
  for (const c of candidates) {
    if (!existsSync(c)) continue;
    const r = await resolveVaultModule({ cwd: tmpdir(), env: { WICKED_QE_VAULT_PKG: c } });
    if (r.ok) return { vault: r.vault, pkg: c };
  }
  return null;
}

const local = await loadLocalVault();
const vault = local?.vault ?? null;
const SKIP = vault
  ? false
  : `wicked-vault manifest-2.1 twin unavailable — ${VAULT_RELEASE_REQUIREMENT}`;

// ---- fixtures (same shape the TH-19 acceptance test proved) --------------------

const SECRET = "Bearer sekrit-token-AAAABBBBCCCCDDDD1234";
const GH_TOKEN = "ghp_synthEticCredential0123456789abcdefXYZ";

function writeBundle({ claim = "PASS" } = {}) {
  const repoRoot = mkdtempSync(join(tmpdir(), "th17-repo-"));
  const spec = {
    spec_version: "1.0",
    scenario: { id: "th17-vault", name: "th17 vault integrity", project: "th17-unit" },
    target: { base_url: "http://127.0.0.1:1" },
    steps: [{ action: "goto", path: "/" }],
    assertions: [{ id: "a", type: "wire", capture: "w", json_path: "body.ok", equals: true }],
  };
  const captures = {
    wire: {
      w: {
        responses: [{
          url: "http://127.0.0.1:1/api/x",
          status: 200,
          headers: { authorization: SECRET, "content-type": "application/json" },
          body: { ok: true, note: `caller sent ${SECRET} and ${GH_TOKEN}` },
          at: "2026-08-30T00:00:00Z",
        }],
      },
    },
    websockets: [],
    wsFirstFrame: undefined,
    readbacks: {},
    console: [],
  };
  const out = writeEvidence({
    spec,
    captures,
    assertionResults: [{ id: "a", type: "wire", ok: true, detail: {}, failures: [] }],
    stepLog: [{ index: 0, action: "goto", ok: true, started_at: "t", finished_at: "t" }],
    repoRoot,
    claim,
    claimReason: "1/1 assertions passed",
    startedAt: "2026-08-30T00:00:00.000Z",
    finishedAt: "2026-08-30T00:00:05.000Z",
  });
  return { repoRoot, out };
}

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

function vaultEntryCount(repoRoot) {
  const entries = join(repoRoot, ".wicked-vault", "entries");
  return existsSync(entries) ? readdirSync(entries).filter((f) => f.endsWith(".json")).length : 0;
}

// ---- pure tests (no vault needed) ----------------------------------------------

test("verdictToOpinion: deny-shaped verdicts never inflate to pass", () => {
  assert.equal(verdictToOpinion("PASS"), "pass");
  assert.equal(verdictToOpinion("FAIL"), "reject");
  for (const v of ["CONDITIONAL", "SYSTEM_ERROR", "INCONCLUSIVE", "PARTIAL", "banana"]) {
    assert.equal(verdictToOpinion(v), "unclear");
  }
});

test("checkVaultCapability: a pre-2.1 vault is refused WITH the release requirement", () => {
  const fn = () => {};
  const pre21 = { record: fn, verify: fn, attest: fn, findRoot: fn, listEntries: fn, listAttestations: fn };
  const r = checkVaultCapability(pre21);
  assert.equal(r.ok, false);
  assert.equal(r.pre21, true);
  assert.match(r.reason, /UNRELEASED/);
  assert.match(r.reason, /WICKED_QE_VAULT_PKG/);
  // and a non-vault module is a different refusal (not "release the vault")
  const notVault = checkVaultCapability({ record: fn });
  assert.equal(notVault.ok, false);
  assert.ok(!notVault.pre21);
});

test("ordering: a bundle with no result.json (never touched the executor) is refused", () => {
  const dir = mkdtempSync(join(tmpdir(), "th17-raw-"));
  writeFileSync(join(dir, "wire.json"), JSON.stringify({ note: `raw ${SECRET}` }));
  assert.throws(
    () => assertRedactionBeforeVault({ evidenceDir: dir }),
    (e) => e instanceof VaultEvidenceError && e.code === "REDACTION_ORDERING",
  );
});

test("ordering: result.json without the redaction marker is refused", () => {
  const dir = mkdtempSync(join(tmpdir(), "th17-nomarker-"));
  writeFileSync(join(dir, "result.json"), JSON.stringify({ executor_claim: { value: "PASS" } }));
  writeFileSync(join(dir, "wire.json"), JSON.stringify({ ok: true }));
  assert.throws(
    () => assertRedactionBeforeVault({ evidenceDir: dir }),
    (e) => e instanceof VaultEvidenceError && e.code === "REDACTION_ORDERING" && /redaction marker/.test(e.message),
  );
});

test("ordering: a FORGED marker with a residual secret is caught by the scan re-run (no matched text in the report)", () => {
  const dir = mkdtempSync(join(tmpdir(), "th17-forged-"));
  writeFileSync(join(dir, "result.json"), JSON.stringify({ redaction: { applied: true, preflight_hits: [] } }));
  writeFileSync(join(dir, "wire.json"), JSON.stringify({ note: `smuggled ${SECRET}` }));
  let err;
  try {
    assertRedactionBeforeVault({ evidenceDir: dir });
  } catch (e) { err = e; }
  assert.ok(err instanceof VaultEvidenceError);
  assert.equal(err.code, "SECRET_SCAN_HIT");
  assert.ok(err.detail.hits.length > 0);
  assert.equal(err.detail.hits[0].artifact, "wire.json");
  // hits are pattern ids + offsets only — the refusal itself must be safe to persist
  assert.ok(!JSON.stringify(err.detail).includes("sekrit-token"));
});

test("ordering: the executor's real redacted bundle passes the gate with marker proof", () => {
  const { out } = writeBundle();
  const proof = assertRedactionBeforeVault({ evidenceDir: out.evidenceDir });
  assert.equal(proof.ok, true);
  assert.equal(proof.marker, "redaction.applied");
  assert.ok(proof.scanned.includes("manifest.json"));
  assert.ok(proof.scanned.includes("wire.json"));
});

// ---- vault-backed proofs (skip loudly without a 2.1 vault) ----------------------

test("AC-1 record: a redacted campaign bundle freezes content-addressed (payload = manifest bytes)", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot });
  assert.match(r.entryId, /\S+/);
  assert.equal(r.payloadSha256, sha256(readFileSync(join(out.evidenceDir, "manifest.json"))));
  assert.equal(r.redactionProof.marker, "redaction.applied");
  // the vault's own re-derivation agrees (G2/G3 — never a cached status)
  const v = vault.verify(r.vaultRoot, r.entryId);
  assert.equal(v.hash_ok, true);
  assert.equal(v.rederived, true);
});

test("AC-1 rederive: the PASS re-derives 'months later' — and ANY changed byte diverges", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot });

  // months later: nothing in the re-derivation consults a clock or a cache —
  // it is a pure function of (vault store, evidence dir). Intact → ok.
  const ok = rederiveBundle({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, evidenceDir: out.evidenceDir });
  assert.equal(ok.ok, true);
  assert.equal(ok.verify.hash_ok, true);
  const manifest = JSON.parse(readFileSync(join(out.evidenceDir, "manifest.json"), "utf8"));
  assert.equal(ok.artifactsChecked, manifest.artifacts.length);

  // tamper an ARTIFACT on disk → divergence named precisely, deny not refresh
  appendFileSync(join(out.evidenceDir, "wire.json"), " ");
  const tampered = rederiveBundle({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, evidenceDir: out.evidenceDir });
  assert.equal(tampered.ok, false);
  assert.ok(tampered.mismatches.some((m) => m.artifact === "wire.json" && m.problem === "sha256 mismatch"));

  // tamper the VAULT PAYLOAD blob → the content address itself fails
  const blobPath = join(r.vaultRoot, ".wicked-vault", "payloads", r.payloadSha256);
  writeFileSync(blobPath, JSON.stringify({ forged: true }));
  const forged = rederiveBundle({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, evidenceDir: out.evidenceDir });
  assert.equal(forged.ok, false);
  assert.equal(forged.verify.hash_ok, false);
});

test("AC-2 ordering: the synthetic credential is scrubbed BEFORE the vault write", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  // The executor's redaction ran (TH-19) — claim stayed PASS, no quarantine.
  assert.equal(out.claim, "PASS");
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot });

  // The immutable payload the vault now holds forever: no credential in it.
  const payload = readFileSync(join(r.vaultRoot, ".wicked-vault", "payloads", r.payloadSha256), "utf8");
  assert.ok(!payload.includes("sekrit-token"), "vault payload leaked the bearer token");
  assert.ok(!payload.includes(GH_TOKEN), "vault payload leaked the github token");
  // …and neither does any artifact the payload binds (the whole frozen bundle).
  for (const f of readdirSync(out.evidenceDir)) {
    const text = readFileSync(join(out.evidenceDir, f), "utf8");
    assert.ok(!text.includes("sekrit-token"), `${f} leaked the bearer token`);
    assert.ok(!text.includes(GH_TOKEN), `${f} leaked the github token`);
  }
  // the scrub is a scrub, not a deletion
  assert.ok(readFileSync(join(out.evidenceDir, "wire.json"), "utf8").includes("[REDACTED:"));
});

test("AC-2 ordering: an UNREDACTED bundle never reaches the vault — refusal leaves the vault empty", { skip: SKIP }, () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "th17-refuse-"));
  const dir = join(repoRoot, ".wicked-qe", "evidence", "raw-run");
  mkdirSync(dir, { recursive: true });
  // a bundle that provably bypassed the executor: raw secret, no marker
  writeFileSync(join(dir, "result.json"), JSON.stringify({ executor_claim: { value: "PASS" } }));
  writeFileSync(join(dir, "wire.json"), JSON.stringify({ note: `raw ${SECRET}` }));
  writeFileSync(join(dir, "manifest.json"), JSON.stringify({ manifest_version: "2.1.0" }));

  assert.throws(
    () => recordEvidenceBundle({ vault, evidenceDir: dir, repoRoot }),
    (e) => e instanceof VaultEvidenceError && e.code === "REDACTION_ORDERING",
  );
  assert.equal(vaultEntryCount(repoRoot), 0, "ordering refusal must leave NO vault entry");

  // forged marker + residual secret: refused by the scan re-run, still no write
  writeFileSync(join(dir, "result.json"), JSON.stringify({ redaction: { applied: true } }));
  assert.throws(
    () => recordEvidenceBundle({ vault, evidenceDir: dir, repoRoot }),
    (e) => e instanceof VaultEvidenceError && e.code === "SECRET_SCAN_HIT",
  );
  assert.equal(vaultEntryCount(repoRoot), 0, "secret-scan refusal must leave NO vault entry");
});

test("a nonconforming manifest is never frozen (schema-fail bundles stay out of the vault)", { skip: SKIP }, () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "th17-badmanifest-"));
  const dir = join(repoRoot, ".wicked-qe", "evidence", "bad-run");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "result.json"), JSON.stringify({ redaction: { applied: true, preflight_hits: [] } }));
  writeFileSync(join(dir, "manifest.json"), JSON.stringify({ manifest_version: "2.1.0", run_id: "bad-run" }));
  assert.throws(
    () => recordEvidenceBundle({ vault, evidenceDir: dir, repoRoot }),
    (e) => e instanceof VaultEvidenceError && e.code === "MANIFEST_INVALID",
  );
  assert.equal(vaultEntryCount(repoRoot), 0);
});

test("reviewer grade lands as an APPEND-ONLY opinion attestation, hash-bound to the graded payload", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot });

  const att = attestGrade({
    vault, vaultRoot: r.vaultRoot, entryId: r.entryId,
    verdict: "PASS", evaluator: "wicked-garden-qe-gate",
    rationale: "21/21 assertions re-derived from wire + read-back evidence",
  });
  assert.equal(att.opinion, "pass");

  const list = vault.listAttestations(r.vaultRoot, r.entryId);
  assert.equal(list.length, 1);
  assert.equal(list[0].opinion, "pass");
  assert.equal(list[0].evaluator, "wicked-garden-qe-gate");
  assert.equal(list[0].evidence_sha256, r.payloadSha256, "attestation must bind the EXACT payload graded");

  // a FAIL grade is a reject opinion, appended (never replacing)
  attestGrade({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, verdict: "FAIL", evaluator: "second-reviewer", rationale: "regraded" });
  assert.equal(vault.listAttestations(r.vaultRoot, r.entryId).length, 2);
});

test("self-grade is refused mechanically (evaluator == recording actor)", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot }); // actor: qe-runner
  assert.throws(
    () => attestGrade({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, verdict: "PASS", evaluator: "qe-runner", rationale: "looks great to me" }),
    /G10\/D4/,
  );
});

test("an attestation rationale carrying a secret is refused (every vault write is scanned)", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = recordEvidenceBundle({ vault, evidenceDir: out.evidenceDir, repoRoot });
  assert.throws(
    () => attestGrade({ vault, vaultRoot: r.vaultRoot, entryId: r.entryId, verdict: "PASS", evaluator: "wicked-garden-qe-gate", rationale: `saw header ${SECRET}` }),
    (e) => e instanceof VaultEvidenceError && e.code === "SECRET_SCAN_HIT",
  );
  assert.equal(vault.listAttestations(r.vaultRoot, r.entryId).length, 0);
});

test("gate glue: applyVaultIntegrity = record + attest, returning the verdicts-row payload sha", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  const r = applyVaultIntegrity({
    vault, evidenceDir: out.evidenceDir, repoRoot,
    verdict: "PASS", verdictSummary: "campaign green",
    evaluator: "wicked-garden-qe-gate",
  });
  assert.equal(r.payloadSha256, sha256(readFileSync(join(out.evidenceDir, "manifest.json"))));
  assert.equal(r.opinion, "pass");
  const list = vault.listAttestations(r.vaultRoot, r.entryId);
  assert.equal(list.length, 1);

  // link path: --vault-entry re-derives before trusting; tamper → refused
  const linked = applyVaultIntegrity({
    vault, evidenceDir: out.evidenceDir, repoRoot,
    vaultEntry: r.entryId, verdict: "PASS", verdictSummary: "re-gated",
    evaluator: "second-reviewer",
  });
  assert.equal(linked.payloadSha256, r.payloadSha256);

  writeFileSync(join(r.vaultRoot, ".wicked-vault", "payloads", r.payloadSha256), "{}");
  assert.throws(
    () => applyVaultIntegrity({
      vault, evidenceDir: out.evidenceDir, repoRoot,
      vaultEntry: r.entryId, verdict: "PASS", verdictSummary: "tampered",
      evaluator: "third-reviewer",
    }),
    (e) => e instanceof VaultEvidenceError && e.code === "ENTRY_TAMPERED",
  );
});

// ---- end-to-end: gate.mjs --vault-record → verdicts row carries vault_payload_sha

test("gate.mjs --vault-record: the verdicts row of record carries vault_payload_sha (+ attestation)", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();

  // stub wicked-bus on PATH so the gate's fire-and-forget emit never leaves
  // the sandbox (and never invokes npx/network)
  const binDir = mkdtempSync(join(tmpdir(), "th17-bin-"));
  const stub = join(binDir, "wicked-bus");
  writeFileSync(stub, "#!/bin/sh\nexit 0\n");
  chmodSync(stub, 0o755);

  // the gate resolves wicked-ledger from the TARGET repo — hand it the
  // runner's own install
  mkdirSync(join(repoRoot, "node_modules"), { recursive: true });
  execFileSync("ln", ["-s", join(HERE, "..", "node_modules", "wicked-ledger"), join(repoRoot, "node_modules", "wicked-ledger")]);

  const gate = join(HERE, "..", "..", "lib", "gate.mjs");
  const stdout = execFileSync(process.execPath, [
    gate,
    "--project-id", out.projectId,
    "--run-id", out.runId,
    "--verdict", "PASS",
    "--verdict-summary", "campaign green — re-derived from evidence",
    "--vault-record",
  ], {
    cwd: repoRoot,
    env: {
      ...process.env,
      WICKED_QE_VAULT_PKG: local.pkg,
      PATH: `${binDir}:${process.env.PATH}`,
    },
    encoding: "utf8",
  });
  const result = JSON.parse(stdout);
  assert.equal(result.gate_verdict, "PASS");
  assert.ok(result.vault.entry_id, "gate output must carry the vault entry id");
  assert.equal(result.vault.opinion, "pass");
  assert.equal(
    result.vault.payload_sha256,
    sha256(readFileSync(join(out.evidenceDir, "manifest.json"))),
  );

  // the row of record: vault_payload_sha present (ledger migration 003)
  const { createDomainStore } = require("wicked-ledger");
  const store = createDomainStore({ root: join(repoRoot, ".wicked-qe") });
  try {
    const rows = store.list("verdicts", { run_id: out.runId });
    assert.equal(rows.length, 1);
    assert.equal(rows[0].verdict, "PASS");
    assert.equal(rows[0].reviewer, "wicked-garden-qe-gate");
    assert.equal(rows[0].vault_payload_sha, result.vault.payload_sha256);
    const meta = JSON.parse(rows[0].equivalence_json);
    assert.equal(meta.vault_entry_id, result.vault.entry_id);
    assert.equal(meta.vault_attestation_id, result.vault.attestation_id);
  } finally {
    try { store.close(); } catch { /* ignore */ }
  }

  // and the attestation chain is really there, bound to the payload
  const vaultRoot = vault.findRoot(repoRoot);
  const atts = vault.listAttestations(vaultRoot, result.vault.entry_id);
  assert.equal(atts.length, 1);
  assert.equal(atts[0].evidence_sha256, result.vault.payload_sha256);
});

test("gate.mjs --vault-record: a bundle that fails validation records its DOWNGRADE but is never vaulted", { skip: SKIP }, () => {
  const { repoRoot, out } = writeBundle();
  // corrupt the manifest AFTER the executor wrote it: drops a required field
  const mPath = join(out.evidenceDir, "manifest.json");
  const m = JSON.parse(readFileSync(mPath, "utf8"));
  delete m.verdict;
  writeFileSync(mPath, JSON.stringify(m, null, 2));

  mkdirSync(join(repoRoot, "node_modules"), { recursive: true });
  execFileSync("ln", ["-s", join(HERE, "..", "node_modules", "wicked-ledger"), join(repoRoot, "node_modules", "wicked-ledger")]);

  // stub wicked-bus so the fire-and-forget emit never reaches npx/network
  const binDir = mkdtempSync(join(tmpdir(), "th17-bin-"));
  writeFileSync(join(binDir, "wicked-bus"), "#!/bin/sh\nexit 0\n");
  chmodSync(join(binDir, "wicked-bus"), 0o755);

  const gate = join(HERE, "..", "..", "lib", "gate.mjs");
  let stdout = "", code = 0;
  try {
    stdout = execFileSync(process.execPath, [
      gate,
      "--project-id", out.projectId,
      "--run-id", out.runId,
      "--verdict", "PASS",
      "--verdict-summary", "executor said pass",
      "--vault-record",
    ], { cwd: repoRoot, env: { ...process.env, WICKED_QE_VAULT_PKG: local.pkg, PATH: `${binDir}:${process.env.PATH}` }, encoding: "utf8" });
  } catch (e) {
    code = e.status;
    stdout = String(e.stdout ?? "");
  }
  const result = JSON.parse(stdout);
  assert.equal(code, 3, "SYSTEM_ERROR downgrade exits 3");
  assert.equal(result.gate_verdict, "SYSTEM_ERROR");
  assert.equal(result.vault.skipped, true);
  assert.match(result.vault.reason, /never vaulted/);
  assert.equal(vaultEntryCount(repoRoot), 0, "a nonconforming bundle must never be frozen");

  const { createDomainStore } = require("wicked-ledger");
  const store = createDomainStore({ root: join(repoRoot, ".wicked-qe") });
  try {
    const rows = store.list("verdicts", { run_id: out.runId });
    assert.equal(rows.length, 1);
    assert.equal(rows[0].verdict, "INCONCLUSIVE"); // deny-dominates
    assert.ok(!rows[0].vault_payload_sha, "downgraded row must carry NO vault link");
  } finally {
    try { store.close(); } catch { /* ignore */ }
  }
});

test("gate.mjs --vault-record REFUSES an unredacted bundle: exit 3, no verdict row, vault empty", { skip: SKIP }, () => {
  const repoRoot = mkdtempSync(join(tmpdir(), "th17-gate-refuse-"));
  const runId = "raw-run";
  const dir = join(repoRoot, ".wicked-qe", "evidence", runId);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "result.json"), JSON.stringify({ executor_claim: { value: "PASS" } })); // no marker
  writeFileSync(join(dir, "wire.json"), JSON.stringify({ note: `raw ${SECRET}` }));

  mkdirSync(join(repoRoot, "node_modules"), { recursive: true });
  execFileSync("ln", ["-s", join(HERE, "..", "node_modules", "wicked-ledger"), join(repoRoot, "node_modules", "wicked-ledger")]);

  // seed a runs row so the refusal we observe is the ORDERING one, not RUN_NOT_FOUND
  const { createDomainStore } = require("wicked-ledger");
  const store = createDomainStore({ root: join(repoRoot, ".wicked-qe") });
  const project = store.create("projects", { name: "th17-refuse" });
  const scenario = store.create("scenarios", { project_id: project.id, name: "raw", format_version: "1.0", body: "raw" });
  store.create("runs", { id: runId, project_id: project.id, scenario_id: scenario.id, started_at: "t", finished_at: "t", status: "passed", evidence_path: dir });
  try { store.close(); } catch { /* ignore */ }

  const gate = join(HERE, "..", "..", "lib", "gate.mjs");
  let code = 0, stderr = "";
  try {
    execFileSync(process.execPath, [
      gate,
      "--project-id", project.id,
      "--run-id", runId,
      "--verdict", "PASS",
      "--verdict-summary", "should never be recorded",
      "--vault-record",
    ], { cwd: repoRoot, env: { ...process.env, WICKED_QE_VAULT_PKG: local.pkg }, encoding: "utf8" });
  } catch (e) {
    code = e.status;
    stderr = String(e.stderr ?? "");
  }
  assert.equal(code, 3, "ordering refusal must exit 3");
  assert.match(stderr, /REDACTION_ORDERING/);
  assert.equal(vaultEntryCount(repoRoot), 0, "no vault entry after refusal");

  const store2 = createDomainStore({ root: join(repoRoot, ".wicked-qe") });
  try {
    assert.equal(store2.list("verdicts", { run_id: runId }).length, 0, "no verdict row after refusal");
  } finally {
    try { store2.close(); } catch { /* ignore */ }
  }
});
