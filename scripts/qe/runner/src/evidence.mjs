/**
 * src/evidence.mjs — evidence persistence in the wicked-ledger shape
 * (TH-4 item 5), with redaction + secret-scan preflight in the write path
 * (TH-19).
 *
 * Flow (ORDER IS THE CONTRACT — TH-17 inherits it):
 *   raw captures ──redactDeep──▶ artifact objects ──serialize──▶
 *   scanForSecrets preflight ──▶ (hit? claim := INCONCLUSIVE) ──▶
 *   write artifacts ──▶ ledger rows (projects/scenarios/runs) ──▶
 *   buildManifest (wicked-ledger manifest 2.0.0) under
 *   `<repo>/.wicked-qe/evidence/<run-id>/`
 *
 * The runner writes EVIDENCE, not verdicts of record: no `verdicts` row is
 * created here. The manifest's verdict block carries the EXECUTOR CLAIM
 * (reviewer: "qe-runner/executor-claim") so the bundle is shape-conformant;
 * grading stays with the qe accept trio (TH-10), and run/verdict wiring into
 * gate.mjs + crew acceptance is TH-6.
 * TODO(TH-6): emit stable scenario_ids + verdict rows through the accept
 * trio / gate.mjs so `GET /runs/:id/acceptance` re-derives from these rows.
 */

import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { join, isAbsolute } from "node:path";
import { randomUUID } from "node:crypto";
import { createRequire } from "node:module";
import {
  redactDeep,
  scanForSecrets,
  compileExtraFields,
  compileExtraPatterns,
} from "./redact.mjs";

const require = createRequire(import.meta.url);
const RUNNER_VERSION = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
).version;

/**
 * Resolve the ledger root. Mirrors crew's TH-2 semantics: an explicit
 * WICKED_QE_LEDGER_DIR pins the dirname exactly (absolute values stay
 * absolute; relative values join the repo root); otherwise `.wicked-qe/`
 * under the repo root.
 */
export function resolveLedgerRoot(repoRoot, env = process.env) {
  const override = env.WICKED_QE_LEDGER_DIR?.trim();
  if (override) return isAbsolute(override) ? override : join(repoRoot, override);
  return join(repoRoot, ".wicked-qe");
}

/**
 * Write the full evidence bundle for a completed run.
 *
 * @param {object} opts
 * @param {object} opts.spec           the linted spec
 * @param {object} opts.captures       raw captures from the run
 * @param {Array}  opts.assertionResults evaluateAssertions() output
 * @param {Array}  opts.stepLog        step timeline
 * @param {string} opts.repoRoot       target repo root (evidence lands under
 *                                     its .wicked-qe/)
 * @param {string} opts.claim          executor claim: PASS|FAIL|INCONCLUSIVE
 * @param {string} opts.claimReason    one-line reason
 * @param {Array}  opts.screenshots    [{ name, path }] already-written PNGs
 *                                     (written straight into the evidence
 *                                     dir by the runner)
 * @param {string} [opts.runError]     fatal error text when the run crashed
 * @returns {{ runId, evidenceDir, manifestPath, claim, preflight }}
 */
export function writeEvidence(opts) {
  const { spec, captures, assertionResults, stepLog, repoRoot } = opts;
  const extraFields = compileExtraFields(spec.target?.redact?.fields ?? []);
  const extraPatterns = compileExtraPatterns(spec.target?.redact?.patterns ?? []);
  const redactOpts = { extraFields, extraPatterns };

  // ---- 1. REDACT (before anything is serialized for persistence) ----------
  const wireArtifact = redactDeep(
    {
      wire: captures.wire,
      websockets: captures.websockets,
      ws_first_frame: captures.wsFirstFrame ?? null,
      readbacks: captures.readbacks,
    },
    redactOpts,
  );
  const consoleArtifact = redactDeep({ messages: captures.console }, redactOpts);
  const stepsArtifact = redactDeep({ steps: stepLog }, redactOpts);
  const resultArtifact = redactDeep(
    {
      scenario: spec.scenario,
      target: { base_url: spec.target.base_url, kind: spec.target.kind ?? "browser" },
      executor: { name: "qe-runner", version: RUNNER_VERSION, model_free: true },
      assertions: assertionResults,
      run_error: opts.runError ?? null,
    },
    redactOpts,
  );

  // ---- 2. PREFLIGHT (secret scan on the final serialized text) ------------
  // A hit does two things, deny-dominates style:
  //   a. the executor claim flips to INCONCLUSIVE, and
  //   b. the offending artifact's CONTENT is withheld — a quarantine stub is
  //      written in its place, so no unscrubbed credential ever reaches disk.
  // The hits themselves carry pattern ids + offsets only, never matched text.
  const quarantineStub = (name, hits, extra = {}) =>
    JSON.stringify(
      {
        quarantined: true,
        artifact: name,
        reason: "secret-scan preflight hit — content withheld before persistence (TH-19)",
        hits,
        ...extra,
      },
      null,
      2,
    );

  const serialized = {
    "wire.json": JSON.stringify(wireArtifact, null, 2),
    "console.json": JSON.stringify(consoleArtifact, null, 2),
    "steps.json": JSON.stringify(stepsArtifact, null, 2),
  };
  const preflight = [];
  for (const [name, text] of Object.entries(serialized)) {
    const hits = scanForSecrets(text, extraPatterns).map((h) => ({ artifact: name, ...h }));
    if (hits.length > 0) {
      preflight.push(...hits);
      serialized[name] = quarantineStub(name, hits);
    }
  }

  let claim = opts.claim;
  let claimReason = opts.claimReason;
  if (preflight.length > 0) {
    claim = "INCONCLUSIVE";
    claimReason = `secret-scan preflight hit ${preflight.length} pattern(s) in ${[...new Set(preflight.map((p) => p.artifact))].join(", ")} — evidence quarantined, deny-dominates (TH-19)`;
  }
  resultArtifact.executor_claim = { value: claim, reason: claimReason };
  resultArtifact.redaction = {
    applied: true,
    preflight_hits: preflight, // pattern ids + offsets only — never matched text
  };
  let resultText = JSON.stringify(resultArtifact, null, 2);
  const resultHits = scanForSecrets(resultText, extraPatterns).map((h) => ({ artifact: "result.json", ...h }));
  if (resultHits.length > 0) {
    preflight.push(...resultHits);
    if (claim !== "INCONCLUSIVE") {
      claim = "INCONCLUSIVE";
      claimReason = `secret-scan preflight hit ${resultHits.length} pattern(s) in result.json — evidence quarantined, deny-dominates (TH-19)`;
    }
    // Withhold assertion detail; keep the claim + hit metadata interpretable.
    resultText = quarantineStub("result.json", resultHits, {
      executor_claim: { value: claim, reason: claimReason },
      scenario: spec.scenario,
    });
  }

  // ---- 3. WRITE artifacts ---------------------------------------------------
  const ledgerRoot = resolveLedgerRoot(repoRoot);
  const runId = opts.runId ?? randomUUID();
  const evidenceDir = join(ledgerRoot, "evidence", runId);
  mkdirSync(evidenceDir, { recursive: true });
  writeFileSync(join(evidenceDir, "wire.json"), serialized["wire.json"] + "\n");
  writeFileSync(join(evidenceDir, "console.json"), serialized["console.json"] + "\n");
  writeFileSync(join(evidenceDir, "steps.json"), serialized["steps.json"] + "\n");
  writeFileSync(join(evidenceDir, "result.json"), resultText + "\n");
  // Screenshots were streamed into evidenceDir by the runner already (they
  // are pixel data — see redact.mjs limitation note).

  // ---- 4. Ledger rows + manifest -------------------------------------------
  const { createDomainStore } = require("wicked-ledger");
  const { buildManifest } = require("wicked-ledger/manifest");
  const store = createDomainStore({ root: ledgerRoot });

  const projectName = spec.scenario.project;
  const project =
    store.list("projects", { name: projectName })[0] ??
    store.create("projects", { name: projectName });
  const scenario =
    store.list("scenarios", { project_id: project.id, name: spec.scenario.id })[0] ??
    store.create("scenarios", {
      project_id: project.id,
      name: spec.scenario.id,
      format_version: "1.0",
      body: spec.scenario.name,
      source_path: opts.specPath ?? null,
    });

  const status =
    opts.runError !== undefined ? "errored"
    : claim === "PASS" ? "passed"
    : claim === "FAIL" ? "failed"
    : "inconclusive";

  const run = store.create("runs", {
    id: runId,
    project_id: project.id,
    scenario_id: scenario.id,
    started_at: opts.startedAt,
    finished_at: opts.finishedAt ?? new Date().toISOString(),
    status,
    evidence_path: evidenceDir,
  });

  // Executor CLAIM only — not a graded verdict; no verdicts row (TH-10).
  const { path: manifestPath } = buildManifest({
    runRecord: run,
    scenarioRecord: scenario,
    verdictRecord: {
      verdict: claim,
      reviewer: "qe-runner/executor-claim",
      reason: `${claimReason} [executor claim — grading via qe accept trio (TH-10); gate wiring TH-6]`,
      created_at: run.finished_at,
    },
    evidenceDir,
    qeVersion: RUNNER_VERSION,
    cli: "qe-runner",
  });

  return { runId: run.id, evidenceDir, manifestPath, claim, claimReason, preflight, projectId: project.id, scenarioId: scenario.id };
}
