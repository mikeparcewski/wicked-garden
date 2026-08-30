#!/usr/bin/env node
/**
 * scripts/qe/lib/gate.mjs — the qe gate-announcement CLI.
 *
 * Records a gate verdict for a test run in the qe evidence ledger
 * (wicked-ledger DomainStore) and emits the STABLE gate events wicked-crew's
 * acceptance route subscribes to. Ported from the retired wicked-testing
 * package's `wicked-qe gate` (lib/gate.mjs + bin/wicked-qe.mjs) in Phase 6c —
 * garden ships qe in-catalog, so the emit seam lives here now. The event
 * types and the 8-field payload are a WIRE CONTRACT (crew folds them into
 * its acceptance view) — do not rename fields or types:
 *
 *   wicked.qe.gate.passed | wicked.qe.gate.failed | wicked.qe.gate.conditional
 *     payload: run_id, context, gate_verdict, exit_code, verdict_summary,
 *              mode, completed_at, scenario_count
 *     idempotency key: qe:gate.result:{context}:{sha256(run_id)[0:16]}:0
 *   wicked.qe.deploy.completed  (alongside a PASS)
 *     payload: run_id, project_id
 *
 * Usage (from a target repo's root):
 *   node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/gate.mjs" \
 *     --project-id <id> --run-id <id> --verdict <PASS|FAIL|CONDITIONAL|SYSTEM_ERROR> \
 *     --verdict-summary "<text>" [--rationale-ref <path>] [--council-run-id <id>]
 *     [--mode gate|event|manual|crew_integration] [--exclusions-from <scoreboard.json>]
 *     [--dry-run]
 *
 * Exit codes: 0 PASS · 1 FAIL · 2 CONDITIONAL · 3 SYSTEM_ERROR / invalid.
 *
 * wicked-ledger is resolved from the TARGET repo (cwd), not from the plugin
 * dir — the plugin ships no node_modules. Resolution: bare import (global /
 * hoisted install) → the repo's node_modules (ESM entry via package.json).
 *
 * TH-6 gate wiring:
 *   - The ledger root honors `WICKED_QE_LEDGER_DIR` with the same TH-2
 *     semantics as crew's acceptance reader and the qe-runner's writer
 *     (absolute pins exactly; relative joins cwd) — the verdict row MUST
 *     land in the same store the runner wrote its runs row to, or crew's
 *     `GET /runs/:id/acceptance` re-derives from a store that never saw it.
 *   - When the evidence bundle carries a `manifest.json` and the resolved
 *     wicked-ledger exports `validateManifest` (manifest 2.1, TH-5), the
 *     bundle is validated BEFORE the verdict is recorded: a nonconforming
 *     bundle downgrades the recorded verdict to SYSTEM_ERROR (stored as
 *     INCONCLUSIVE — deny-dominates; schema-fail is never a PASS). Bundles
 *     without a manifest (legacy evidence dirs) skip validation unchanged.
 *
 * TH-21 flake policy (excluded-with-reason in the acceptance payload):
 *   - `--exclusions-from <scoreboard.json>` reads the campaign scoreboard
 *     envelope (campaign-scoreboard.mjs --out) and appends the canonical
 *     `quarantined excluded-with-reason (…)` clause — id, cause, owner,
 *     deadline, reason per exclusion — to the verdict summary, so the
 *     exclusions reach the verdicts row AND the wicked.qe.gate.* event's
 *     `verdict_summary` (the 8-field wire contract is untouched — the clause
 *     rides the existing field). Fail-closed: an unreadable envelope or an
 *     exclusion missing id/reason/owner/deadline exits 3 — an exclusion
 *     without a reason never reaches the acceptance payload.
 *
 * TH-17 vault-backed evidence integrity (./vault-evidence.mjs):
 *   - `--vault-record` freezes the (already-redacted) evidence bundle into
 *     wicked-vault — a content-addressed manifest payload binding every
 *     artifact hash — and appends the FINAL verdict as the reviewer's
 *     opinion attestation; the verdicts row then carries `vault_payload_sha`
 *     (ledger migration 003; DomainStore emits wicked.test.evidence.captured
 *     alongside the verdict event when the field is present).
 *   - `--vault-entry <id>` links a bundle vaulted earlier in the pipeline
 *     instead of recording: the entry is RE-DERIVED first (fail-closed on
 *     tamper), then attested the same way.
 *   - ORDERING LAW: the vault write path structurally refuses a bundle
 *     without the executor's TH-19 redaction marker or with any residual
 *     secret-scan hit — redaction runs before any vault write, asserted in
 *     code (vault-evidence.mjs), because vault immutability makes leaks
 *     permanent. Any vault refusal aborts the gate (exit 3): no verdict
 *     row, no events.
 *   - A bundle that failed manifest validation (downgraded above) is NOT
 *     vaulted — the downgraded INCONCLUSIVE verdict records with
 *     `vault: {skipped}` instead (never freeze a nonconforming bundle).
 *   - Release dependency: needs the wicked-vault manifest-2.1 twin —
 *     UNRELEASED (npm 0.6.0 predates it). Until the next wicked-vault
 *     release, `WICKED_QE_VAULT_PKG` must point at a local checkout of
 *     wicked-vault main; a pre-2.1 vault is refused fail-closed.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, dirname, isAbsolute } from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

import { buildExclusionsClause } from "./flake-policy.mjs";
import { resolveVaultModule, applyVaultIntegrity, VaultEvidenceError } from "./vault-evidence.mjs";

// --- wicked-ledger resolution (cwd-anchored; mirrors wicked-vault's bus.mjs) ---

function esmEntryForPackage(resolvedFile) {
  let dir = dirname(resolvedFile);
  for (let i = 0; i < 10; i++) {
    const pj = join(dir, "package.json");
    if (existsSync(pj)) {
      let pkg;
      try { pkg = JSON.parse(readFileSync(pj, "utf8")); } catch { return null; }
      const dot = pkg.exports && pkg.exports["."] !== undefined ? pkg.exports["."] : pkg.exports;
      const rel =
        (dot && typeof dot === "object" && (dot.import || dot.default)) ||
        (typeof dot === "string" ? dot : null) ||
        pkg.module || pkg.main || "index.js";
      return join(dir, rel);
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

async function resolveLedgerModule(cwd) {
  try {
    return await import("wicked-ledger");
  } catch { /* fall through */ }
  try {
    const require = createRequire(join(cwd, "__qe_gate_anchor__.js"));
    const located = require.resolve("wicked-ledger");
    const esm = esmEntryForPackage(located) || located;
    return await import(pathToFileURL(esm).href);
  } catch {
    return null;
  }
}

/**
 * Resolve the ledger root the gate writes to (TH-6). MUST mirror the TH-2
 * semantics shared by crew's `qeLedgerRoot` (packages/crew/src/qe/ledger.ts)
 * and the qe-runner's `resolveLedgerRoot` (scripts/qe/runner/src/evidence.mjs):
 * an explicit `WICKED_QE_LEDGER_DIR` pins the root exactly — absolute values
 * ARE the root, relative values join the base dir; otherwise the ledger
 * package's own dual-read resolution (`.wicked-qe`, legacy `.wicked-testing`).
 * Exported for tests.
 */
export function resolveGateLedgerRoot(baseDir, env, ledger) {
  const override = env.WICKED_QE_LEDGER_DIR?.trim();
  if (override !== undefined && override !== "") {
    return isAbsolute(override) ? override : join(baseDir, override);
  }
  return typeof ledger?.resolveLedgerRoot === "function"
    ? ledger.resolveLedgerRoot(baseDir)
    : join(baseDir, ".wicked-qe");
}

/**
 * Validate the bundle's evidence manifest against the ledger contract before
 * grading (TH-5 rule, wired here per TH-6). Pure decision helper — no exits,
 * no writes. Exported for tests.
 *
 * @returns {{ ran: boolean, ok?: boolean, violations?: Array,
 *             verdict: string, verdictSummary: string, note?: string }}
 *   `verdict`/`verdictSummary` are the (possibly downgraded) values to record:
 *   a nonconforming or unparseable manifest downgrades PASS/FAIL/CONDITIONAL
 *   to SYSTEM_ERROR (stored as INCONCLUSIVE — deny-dominates). A missing
 *   manifest (legacy evidence dir) or a ledger without `validateManifest`
 *   (pre-2.1 floor) skips validation with a note, never a downgrade.
 */
export function validateManifestForGate({ evidencePath, ledger, verdict, verdictSummary }) {
  const manifestPath = join(evidencePath, "manifest.json");
  if (!existsSync(manifestPath)) {
    return { ran: false, verdict, verdictSummary, note: "no manifest.json in evidence dir — validation skipped (legacy bundle)" };
  }
  if (typeof ledger?.validateManifest !== "function") {
    return { ran: false, verdict, verdictSummary, note: "resolved wicked-ledger exports no validateManifest (pre-2.1 floor) — validation skipped" };
  }
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch (e) {
    return {
      ran: true,
      ok: false,
      violations: [{ field: "(manifest.json)", message: `unparseable: ${e.message}` }],
      verdict: "SYSTEM_ERROR",
      verdictSummary: `manifest.json is unparseable (${e.message}) — verdict downgraded to INCONCLUSIVE per TH-5 (schema-fail is never graded); original verdict ${verdict}: ${verdictSummary}`,
    };
  }
  const res = ledger.validateManifest(parsed);
  if (res.ok) return { ran: true, ok: true, violations: [], verdict, verdictSummary };
  const detail = res.violations.map((v) => `${v.field}: ${v.message}`).join("; ");
  return {
    ran: true,
    ok: false,
    violations: res.violations,
    verdict: "SYSTEM_ERROR",
    verdictSummary: `evidence manifest violates the ledger contract (${detail}) — verdict downgraded to INCONCLUSIVE per TH-5 (schema-fail is never graded); original verdict ${verdict}: ${verdictSummary}`,
  };
}

// Gate verdicts → domain store verdict enum.
// SYSTEM_ERROR has no direct domain-store mapping; INCONCLUSIVE is the closest
// semantic fit (the store rejects anything outside VERDICT_VALUES).
const VERDICT_TO_STORE_MAP = {
  PASS: "PASS",
  FAIL: "FAIL",
  CONDITIONAL: "CONDITIONAL",
  SYSTEM_ERROR: "INCONCLUSIVE",
};

const VALID_GATE_VERDICTS = ["PASS", "FAIL", "CONDITIONAL", "SYSTEM_ERROR"];

/**
 * Fire-and-forget wicked-bus emit.
 * Tries the wicked-bus binary directly first (fast path when installed
 * globally), then falls back to `npx wicked-bus`. Never throws.
 */
function spawnBusEmit(type, domain, subdomain, payload, idempotencyKey) {
  const payloadStr = JSON.stringify(payload);
  const args = [
    "emit",
    "--type", type,
    "--domain", domain,
    "--subdomain", subdomain,
    "--payload", payloadStr,
  ];
  if (idempotencyKey) {
    args.push("--idempotency-key", idempotencyKey);
  }

  try {
    const r = spawnSync("wicked-bus", args, { stdio: "pipe", timeout: 5000 });
    if (!r.error || r.error.code !== "ENOENT") return; // success or non-ENOENT failure
  } catch { /* fall through to npx */ }

  // npx fallback (slower, but works without global install). On win32 invoke
  // `npx.cmd` directly with shell:false — shell:true would route the quoted
  // JSON `--payload` arg through cmd.exe, which re-parses the quotes/braces
  // and corrupts the payload.
  const npxCmd = process.platform === "win32" ? "npx.cmd" : "npx";
  try {
    spawnSync(npxCmd, ["wicked-bus", ...args], { stdio: "pipe", timeout: 10000 });
  } catch { /* fire-and-forget — ignore */ }
}

/**
 * Read scenario counts from the evidence directory (best-effort, never throws).
 */
function countScenarios(evidencePath) {
  const result = { scenario_count: 0, passed_count: 0, failed_count: 0 };
  if (!existsSync(evidencePath)) return result;

  const manifestPath = join(evidencePath, "manifest.json");
  if (existsSync(manifestPath)) {
    try {
      const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
      if (typeof manifest.scenario_count === "number") {
        result.scenario_count = manifest.scenario_count;
        result.passed_count = manifest.passed_count ?? 0;
        result.failed_count = manifest.failed_count ?? 0;
        return result;
      }
      if (manifest.run_id) {
        result.scenario_count = 1;
        const v = manifest.verdict?.value;
        if (v === "PASS") result.passed_count = 1;
        else if (v === "FAIL") result.failed_count = 1;
        return result;
      }
    } catch { /* ignore parse errors — fall through */ }
  }

  try {
    const files = readdirSync(evidencePath).filter(
      (f) => f.endsWith(".json") && f !== "manifest.json" && !f.startsWith("gate-")
    );
    result.scenario_count = files.length;
  } catch { /* ignore readdir errors */ }

  return result;
}

/** Run the gate command. See the module header for the contract. */
export async function runGate({ projectId, runId, verdict, verdictSummary, rationaleRef, councilRunId, mode, dryRun = false, exclusionsFrom = null, vaultRecord = false, vaultEntry = null, vaultActor = null, vaultEvaluator = null }) {
  // 1. Validate verdict enum before touching anything
  if (!VALID_GATE_VERDICTS.includes(verdict)) {
    process.stderr.write(
      JSON.stringify({ error: "INVALID_VERDICT", verdict, valid: VALID_GATE_VERDICTS }) + "\n"
    );
    process.exit(3);
  }

  // 1a'. --vault-record and --vault-entry are mutually exclusive: record
  //      freezes a NEW entry; entry links an existing one. Both at once is
  //      ambiguous — refuse rather than guess.
  if (vaultRecord && vaultEntry) {
    process.stderr.write(
      JSON.stringify({ error: "VAULT_OPTIONS_CONFLICT", detail: "--vault-record and --vault-entry are mutually exclusive" }) + "\n"
    );
    process.exit(3);
  }

  // 1a. TH-21: fold quarantine exclusions into the verdict summary —
  //     excluded-with-reason in the acceptance payload, fail-closed. This
  //     runs BEFORE manifest validation so a downgrade's "original verdict"
  //     echo still carries the exclusions.
  if (exclusionsFrom) {
    let envelope;
    try {
      envelope = JSON.parse(readFileSync(exclusionsFrom, "utf8"));
    } catch (e) {
      process.stderr.write(
        JSON.stringify({ error: "EXCLUSIONS_SOURCE_UNREADABLE", path: exclusionsFrom, detail: e.message }) + "\n"
      );
      process.exit(3);
    }
    const cert = envelope?.certification;
    if (!cert || typeof cert !== "object" || !Array.isArray(cert.excluded)) {
      process.stderr.write(
        JSON.stringify({
          error: "EXCLUSIONS_SOURCE_INVALID",
          path: exclusionsFrom,
          detail: "not a campaign scoreboard envelope (certification.excluded missing) — build it with campaign-scoreboard.mjs --out",
        }) + "\n"
      );
      process.exit(3);
    }
    const built = buildExclusionsClause(cert.excluded);
    if (!built.ok) {
      process.stderr.write(
        JSON.stringify({
          error: "EXCLUSION_MISSING_REASON",
          detail: "exclusions ALWAYS carry reasons — refusing to record a gate verdict over incomplete exclusions",
          problems: built.problems,
        }) + "\n"
      );
      process.exit(3);
    }
    if (built.clause) verdictSummary = `${verdictSummary} | ${built.clause}`;
  }

  // 1b. Reject a runId that could escape the evidence directory.
  if (
    runId.includes("/") ||
    runId.includes("\\") ||
    runId.includes("..") ||
    runId.includes("\0")
  ) {
    process.stderr.write(
      JSON.stringify({
        error: "INVALID_RUN_ID",
        run_id: runId,
        reason: "path separators, '..', and NUL are not allowed in --run-id",
      }) + "\n"
    );
    process.exit(3);
  }

  // 2. Resolve the ledger module from the target repo, then the ledger root
  //    (dual-read: `.wicked-qe`, or a legacy `.wicked-testing` — Phase 6c).
  const ledger = await resolveLedgerModule(process.cwd());
  if (!ledger || typeof ledger.createDomainStore !== "function") {
    process.stderr.write(
      JSON.stringify({
        error: "LEDGER_UNRESOLVABLE",
        detail: "wicked-ledger is not resolvable from this repo — npm i --no-save wicked-ledger",
      }) + "\n"
    );
    process.exit(3);
  }
  const ledgerRoot = resolveGateLedgerRoot(process.cwd(), process.env, ledger);
  const evidencePath = join(ledgerRoot, "evidence", runId);
  if (!existsSync(evidencePath)) {
    process.stderr.write(
      JSON.stringify({ error: "EVIDENCE_NOT_FOUND", evidence_path: evidencePath }) + "\n"
    );
    process.exit(3);
  }

  // 2c. TH-17: resolve wicked-vault up front when vault integrity was asked
  //     for — fail fast (exit 3) on an unresolvable or pre-2.1 vault, BEFORE
  //     anything is written anywhere. The refusal message carries the release
  //     dependency (the manifest-2.1 twin is unreleased; npm 0.6.0 predates it).
  const wantsVault = Boolean(vaultRecord || vaultEntry);
  let vaultModule = null;
  if (wantsVault) {
    const resolved = await resolveVaultModule({ cwd: process.cwd() });
    if (!resolved.ok) {
      process.stderr.write(
        JSON.stringify({ error: "VAULT_UNAVAILABLE", detail: resolved.reason, pre21: resolved.pre21 ?? false }) + "\n"
      );
      process.exit(3);
    }
    vaultModule = resolved.vault;
  }

  // 2b. Validate the bundle's manifest against the ledger contract BEFORE
  //     grading (TH-5 rule, wired per TH-6): a nonconforming bundle downgrades
  //     the recorded verdict to SYSTEM_ERROR → INCONCLUSIVE (deny-dominates).
  //     Legacy bundles (no manifest.json) and pre-2.1 ledgers skip with a note.
  const validation = validateManifestForGate({ evidencePath, ledger, verdict, verdictSummary });
  const manifestValidation = {
    ran: validation.ran,
    ...(validation.ran ? { ok: validation.ok, violations: validation.violations } : {}),
    ...(validation.note ? { note: validation.note } : {}),
    ...(validation.verdict !== verdict ? { downgraded_from: verdict } : {}),
  };
  verdict = validation.verdict;
  verdictSummary = validation.verdictSummary;

  // 3. Count scenarios from evidence (best-effort)
  const { scenario_count, passed_count, failed_count } = countScenarios(evidencePath);

  // Idempotency key per DEC-00010: qe:gate.result:{context}:{sha256(run_id)[0:16]}:0
  const runIdHash = createHash("sha256").update(runId).digest("hex").slice(0, 16);
  const idempotencyKey = `qe:gate.result:${projectId}:${runIdHash}:0`;

  // 4. Validate the run exists, then write the gate verdict. A verdict.run_id
  //    is an FK into `runs`; the store swallows an FK index failure instead of
  //    throwing, so recording a verdict for a nonexistent run would leave a
  //    JSON-only phantom verdict AND still fire gate/deploy events. Guard:
  //    confirm the run exists BEFORE recording or emitting anything.
  let store = null;
  let vaultInfo = wantsVault && dryRun ? { skipped: true, reason: "dry-run" } : null;
  if (!dryRun) {
    try {
      store = ledger.createDomainStore({ root: ledgerRoot });
    } catch (err) {
      process.stderr.write(
        JSON.stringify({ error: "STORE_UNAVAILABLE", detail: err.message }) + "\n"
      );
      process.exit(3);
    }

    const run = store.get("runs", runId);
    if (!run) {
      process.stderr.write(
        JSON.stringify({ error: "RUN_NOT_FOUND", run_id: runId }) + "\n"
      );
      try { store.close(); } catch { /* ignore close errors */ }
      process.exit(3);
    }

    // TH-17: vault-backed integrity BEFORE the verdict row. Ordering is the
    // contract: (a) a bundle that failed manifest validation is never vaulted
    // — the downgraded verdict records without a vault link; (b) any vault
    // refusal (missing TH-19 redaction marker, residual secret-scan hit,
    // tamper on --vault-entry, self-grade) aborts the gate — exit 3, no
    // verdict row, no events.
    if (wantsVault) {
      if (validation.ran && validation.ok === false) {
        vaultInfo = { skipped: true, reason: "bundle failed manifest validation — a nonconforming bundle is never vaulted" };
      } else {
        try {
          const r = applyVaultIntegrity({
            vault: vaultModule,
            evidenceDir: evidencePath,
            repoRoot: process.cwd(),
            vaultEntry,
            verdict,
            verdictSummary,
            actor: vaultActor ?? undefined,
            evaluator: vaultEvaluator ?? "wicked-garden-qe-gate",
          });
          vaultInfo = {
            entry_id: r.entryId,
            payload_sha256: r.payloadSha256,
            attestation_id: r.attestationId,
            opinion: r.opinion,
          };
        } catch (err) {
          const code = err instanceof VaultEvidenceError ? err.code : "VAULT_SYSTEM_ERROR";
          process.stderr.write(
            JSON.stringify({
              error: code,
              detail: err.message,
              ...(err.detail?.hits ? { hits: err.detail.hits } : {}),
              ...(err.detail?.mismatches ? { mismatches: err.detail.mismatches } : {}),
            }) + "\n"
          );
          try { store.close(); } catch { /* ignore close errors */ }
          process.exit(3);
        }
      }
    }

    try {
      const storeVerdict = VERDICT_TO_STORE_MAP[verdict] ?? "INCONCLUSIVE";
      const meta = {};
      if (rationaleRef) meta.rationale_ref = rationaleRef;
      if (councilRunId) meta.council_run_id = councilRunId;
      if (vaultInfo?.entry_id) meta.vault_entry_id = vaultInfo.entry_id;
      if (vaultInfo?.attestation_id) meta.vault_attestation_id = vaultInfo.attestation_id;
      store.create("verdicts", {
        run_id: runId,
        verdict: storeVerdict,
        evidence_path: evidencePath,
        reviewer: "wicked-garden-qe-gate",
        reason: verdictSummary,
        // TH-17: content address of the vaulted bundle (ledger migration 003).
        // Presence makes DomainStore emit wicked.test.evidence.captured too.
        ...(vaultInfo?.payload_sha256 ? { vault_payload_sha: vaultInfo.payload_sha256 } : {}),
        ...(Object.keys(meta).length ? { equivalence_json: JSON.stringify(meta) } : {}),
      });
    } catch (err) {
      process.stderr.write(`[wicked-garden-qe] domain store write failed (non-fatal): ${err.message}\n`);
      // continue — a store *write* failure must not abort the gate
    } finally {
      if (store) {
        try { store.close(); } catch { /* ignore close errors */ }
      }
    }
  }

  // 5. Build the 8-field canonical bus payload — the wire contract. Do not
  //    add, remove, or rename fields here.
  const exitCodeMap = { PASS: 0, FAIL: 1, CONDITIONAL: 2 };
  const exitCode = exitCodeMap[verdict] ?? 3;

  const busPayload = {
    run_id: runId,
    context: projectId,
    gate_verdict: verdict,
    exit_code: exitCode,
    verdict_summary: verdictSummary,
    mode: mode || "gate",
    completed_at: new Date().toISOString(),
    scenario_count,
  };

  // 6. Emit the gate bus event (fire-and-forget).
  //    SYSTEM_ERROR maps to wicked.qe.gate.conditional (per spec).
  const gateEventType =
    verdict === "PASS" ? "wicked.qe.gate.passed" :
    verdict === "FAIL" ? "wicked.qe.gate.failed" :
    "wicked.qe.gate.conditional"; // CONDITIONAL and SYSTEM_ERROR

  if (!dryRun) {
    spawnBusEmit(gateEventType, "qe", "gate", busPayload, idempotencyKey);

    // 7. On PASS, emit the cross-product deploy signal
    if (verdict === "PASS") {
      spawnBusEmit("wicked.qe.deploy.completed", "qe", "deploy", {
        run_id: runId,
        project_id: projectId,
      });
    }
  }

  // 8. Output canonical result JSON to stdout. `manifest_validation` is
  //    additive stdout detail (TH-6) — the 8-field BUS payload above is the
  //    wire contract and stays untouched.
  const output = {
    run_id: runId,
    project_id: projectId,
    gate_verdict: verdict,
    verdict_summary: verdictSummary,
    scenario_count,
    passed_count,
    failed_count,
    evidence_path: evidencePath,
    manifest_validation: manifestValidation,
    ...(vaultInfo ? { vault: vaultInfo } : {}),
  };
  process.stdout.write(JSON.stringify(output) + "\n");

  // 9. Exit with verdict-mapped code (exitCode computed in step 5)
  process.exit(exitCode);
}

// --- CLI entry (merged from the retired bin/wicked-qe.mjs) ---

const GATE_HELP = `\
qe gate — record a gate verdict for a test run

Usage:
  node gate.mjs --project-id <id> --run-id <id> --verdict <verdict> \\
                --verdict-summary "<text>" [options]

Required:
  --project-id <id>         Project identifier
  --run-id <id>             Test run identifier
  --verdict <verdict>       Gate verdict: PASS | FAIL | CONDITIONAL | SYSTEM_ERROR
  --verdict-summary <text>  Human-readable summary of the verdict

Optional:
  --rationale-ref <path>    Path to rationale document
  --council-run-id <id>     Council session ID (for CONDITIONAL verdicts)
  --mode <mode>             Trigger mode: gate | event | manual | crew_integration (default: gate)
  --exclusions-from <path>  Campaign scoreboard envelope (campaign-scoreboard.mjs --out);
                            appends the quarantined excluded-with-reason clause to the
                            verdict summary (TH-21). Refuses exclusions missing
                            id/reason/owner/deadline (exit 3)
  --vault-record            TH-17: freeze the evidence bundle into wicked-vault
                            (content-addressed) and attest the verdict as the reviewer's
                            opinion; the verdicts row carries vault_payload_sha. REFUSES
                            unredacted bundles (TH-19 ordering) — exit 3, nothing recorded.
                            Needs the wicked-vault manifest-2.1 twin (unreleased; set
                            WICKED_QE_VAULT_PKG to a wicked-vault main checkout until then)
  --vault-entry <id>        TH-17: link an already-vaulted bundle instead of recording;
                            re-derived fail-closed before the verdict is recorded
  --vault-actor <id>        Recording (worker) identity for --vault-record (default: qe-runner)
  --vault-evaluator <id>    Attesting (reviewer) identity (default: wicked-garden-qe-gate);
                            must differ from the recording actor (self-grade is refused)
  --dry-run                 Validate and print result without writing to store or emitting events
  -h, --help                Show this help

Exit codes:
  0  PASS
  1  FAIL
  2  CONDITIONAL
  3  SYSTEM_ERROR or invalid invocation
`;

function isMain() {
  try {
    return import.meta.url === pathToFileURL(process.argv[1]).href;
  } catch {
    return false;
  }
}

if (isMain()) {
  let values;
  try {
    ({ values } = parseArgs({
      args: process.argv.slice(2),
      options: {
        "project-id":       { type: "string" },
        "run-id":           { type: "string" },
        "verdict":          { type: "string" },
        "verdict-summary":  { type: "string" },
        "rationale-ref":    { type: "string" },
        "council-run-id":   { type: "string" },
        "mode":             { type: "string" },
        "exclusions-from":  { type: "string" },
        "vault-record":     { type: "boolean" },
        "vault-entry":      { type: "string" },
        "vault-actor":      { type: "string" },
        "vault-evaluator":  { type: "string" },
        "dry-run":          { type: "boolean" },
        "help":             { type: "boolean", short: "h" },
      },
      allowPositionals: true,
      strict: false,
    }));
  } catch (err) {
    process.stderr.write(`qe gate: ${err.message}\n`);
    process.exit(3);
  }

  if (values["help"]) {
    process.stdout.write(GATE_HELP);
    process.exit(0);
  }

  const projectId      = values["project-id"];
  const runId          = values["run-id"];
  const verdict        = values["verdict"];
  const verdictSummary = values["verdict-summary"];

  const missing = [];
  if (!projectId)      missing.push("--project-id");
  if (!runId)          missing.push("--run-id");
  if (!verdict)        missing.push("--verdict");
  if (!verdictSummary) missing.push("--verdict-summary");

  if (missing.length > 0) {
    process.stderr.write(
      `qe gate: missing required option(s): ${missing.join(", ")}\n` +
      `Run with --help for usage.\n`
    );
    process.exit(3);
  }

  runGate({
    projectId,
    runId,
    verdict,
    verdictSummary,
    rationaleRef:  values["rationale-ref"],
    councilRunId:  values["council-run-id"],
    mode:          values["mode"],
    dryRun:        values["dry-run"] ?? false,
    exclusionsFrom: values["exclusions-from"] ?? null,
    vaultRecord:   values["vault-record"] ?? false,
    vaultEntry:    values["vault-entry"] ?? null,
    vaultActor:    values["vault-actor"] ?? null,
    vaultEvaluator: values["vault-evaluator"] ?? null,
  }).catch((err) => {
    process.stderr.write(`qe gate: fatal: ${err.message}\n`);
    process.exit(3);
  });
}
