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
 *     [--mode gate|event|manual|crew_integration] [--dry-run]
 *
 * Exit codes: 0 PASS · 1 FAIL · 2 CONDITIONAL · 3 SYSTEM_ERROR / invalid.
 *
 * wicked-ledger is resolved from the TARGET repo (cwd), not from the plugin
 * dir — the plugin ships no node_modules. Resolution: bare import (global /
 * hoisted install) → the repo's node_modules (ESM entry via package.json).
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

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
export async function runGate({ projectId, runId, verdict, verdictSummary, rationaleRef, councilRunId, mode, dryRun = false }) {
  // 1. Validate verdict enum before touching anything
  if (!VALID_GATE_VERDICTS.includes(verdict)) {
    process.stderr.write(
      JSON.stringify({ error: "INVALID_VERDICT", verdict, valid: VALID_GATE_VERDICTS }) + "\n"
    );
    process.exit(3);
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
  const ledgerRoot = typeof ledger.resolveLedgerRoot === "function"
    ? ledger.resolveLedgerRoot(process.cwd())
    : join(process.cwd(), ".wicked-qe");
  const evidencePath = join(ledgerRoot, "evidence", runId);
  if (!existsSync(evidencePath)) {
    process.stderr.write(
      JSON.stringify({ error: "EVIDENCE_NOT_FOUND", evidence_path: evidencePath }) + "\n"
    );
    process.exit(3);
  }

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

    try {
      const storeVerdict = VERDICT_TO_STORE_MAP[verdict] ?? "INCONCLUSIVE";
      const meta = {};
      if (rationaleRef) meta.rationale_ref = rationaleRef;
      if (councilRunId) meta.council_run_id = councilRunId;
      store.create("verdicts", {
        run_id: runId,
        verdict: storeVerdict,
        evidence_path: evidencePath,
        reviewer: "wicked-garden-qe-gate",
        reason: verdictSummary,
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

  // 8. Output canonical result JSON to stdout
  const output = {
    run_id: runId,
    project_id: projectId,
    gate_verdict: verdict,
    verdict_summary: verdictSummary,
    scenario_count,
    passed_count,
    failed_count,
    evidence_path: evidencePath,
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
  }).catch((err) => {
    process.stderr.write(`qe gate: fatal: ${err.message}\n`);
    process.exit(3);
  });
}
