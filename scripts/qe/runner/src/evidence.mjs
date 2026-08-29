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
 * grading stays with the qe accept trio (TH-10).
 *
 * TH-6 gate wiring (the seam this module feeds):
 *   - scenario_ids are STABLE: the `scenarios` row is looked up by
 *     (project, spec.scenario.id) and reused across re-runs, so every re-run
 *     appends a `runs` row under the SAME scenario_id — flake history and
 *     impact selection accrue per scenario (qe-flaky-test-hunter's 14d
 *     windows come free).
 *   - the graded verdict is recorded by `scripts/qe/lib/gate.mjs` (invoked
 *     by the accept trio / campaign action AFTER grading, with the same
 *     `WICKED_QE_LEDGER_DIR`/cwd this writer used): a `verdicts` row keyed by
 *     this module's run_id + the `wicked.qe.gate.*` bus events. crew's
 *     `GET /runs/:id/acceptance` then re-derives "done" from those rows.
 *   - when the installed wicked-ledger supports manifest 2.1 (TH-5), the
 *     bundle carries the campaign `scenario_evidence` block with first-class
 *     `claim_level`; on a pre-2.1 ledger floor the block is withheld (never
 *     silently mangled) and the result notes it.
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
 * Describe one executed step for the scenario_evidence `ui_steps` narrative
 * (manifest 2.1). Selector/path/name only — NEVER step values (a `fill`
 * value could be a credential; the narrative must stay redaction-safe).
 */
function describeStep(specStep, logEntry) {
  const s = specStep ?? {};
  const what =
    s.selector ?? s.path ?? s.name ?? s.capture ?? s.key ?? s.id ?? "";
  const outcome = logEntry.ok === false ? ` [FAILED: ${logEntry.error ?? "?"}]` : "";
  return `${logEntry.index}. ${logEntry.action}${what ? ` ${what}` : ""}${outcome}`;
}

/**
 * Build the manifest-2.1 `scenario_evidence` block (TH-5 shape, TH-6 wiring)
 * from the run's already-collected material. Pure — exported for tests.
 *
 * claim_level comes from the SPEC (the agent-authored plan): optional
 * `scenario.claim_level` (default "machinery-verified" — the conservative
 * floor; the runner cannot know a spec covers the real user journey) and
 * optional `scenario.legs` for disclosed per-leg ceilings. The lint enforces
 * the enum + the honest-cap invariant (scenario claim never stronger than
 * the weakest leg) before execution; wicked-ledger's buildManifest validates
 * it again at write time (fail loud).
 */
export function buildScenarioEvidence({ spec, claim, claimReason, stepLog, assertionResults, captures }) {
  const steps = spec.steps ?? [];
  const ui_steps = stepLog.map((e) => describeStep(steps[e.index], e));
  const screenshots = stepLog
    .filter((e) => e.detail?.screenshot)
    .map((e) => e.detail.screenshot);

  const wireCounts = Object.fromEntries(
    Object.entries(captures.wire ?? {}).map(([id, c]) => [id, c.responses.length]),
  );
  const wire_evidence = {
    artifact: "wire.json",
    capture_counts: wireCounts,
    websocket_connections: (captures.websockets ?? []).length,
    readbacks: Object.keys(captures.readbacks ?? {}),
  };

  const dbResults = assertionResults.filter((r) => r.type === "dbAssert");
  const stateProofs = assertionResults
    .filter((r) => r.type === "readBack" || r.type === "dbAssert" || r.type === "cliCrossCheck")
    .map((r) => `${r.type} ${r.id}: ${r.ok ? "ok" : `FAILED (${(r.failures ?? []).join("; ").slice(0, 200)})`}`);

  return {
    scenario: spec.scenario.id,
    status: claim,
    claim_level: spec.scenario.claim_level ?? "machinery-verified",
    ui_steps,
    ...(screenshots.length > 0 ? { screenshots } : {}),
    wire_evidence,
    ...(dbResults.length > 0
      ? { db_evidence: { assertions: dbResults.map((r) => ({ id: r.id, ok: r.ok })) } }
      : {}),
    ...(stateProofs.length > 0 ? { terminal_state_proof: stateProofs.join(" · ") } : {}),
    notes: claimReason,
    ...(Array.isArray(spec.scenario.legs) && spec.scenario.legs.length > 0
      ? { legs: spec.scenario.legs }
      : {}),
  };
}

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

  // ---- 3b. scenario_evidence block (manifest 2.1, TH-5/TH-6) ---------------
  // Built AFTER the claim is final, redacted like every other artifact, and
  // withheld in favor of a minimal quarantine block when the preflight hit —
  // ui_steps / terminal_state_proof derive from captured material and must
  // never carry what the artifacts themselves were quarantined for.
  const manifestMod = require("wicked-ledger/manifest");
  const { createDomainStore } = require("wicked-ledger");
  const { buildManifest } = manifestMod;
  // Pre-2.1 ledgers have no CLAIM_LEVELS export and silently drop unknown
  // buildManifest options — detect, and withhold the block rather than
  // pretending it was emitted (truth rule).
  const ledgerSupports21 = Array.isArray(manifestMod.CLAIM_LEVELS);
  let scenarioEvidence = null;
  if (ledgerSupports21) {
    if (preflight.length > 0) {
      scenarioEvidence = {
        scenario: spec.scenario.id,
        status: claim,
        claim_level: "skipped",
        notes:
          "evidence quarantined by secret-scan preflight (TH-19) — scenario_evidence content withheld, deny-dominates",
      };
    } else {
      scenarioEvidence = redactDeep(
        buildScenarioEvidence({ spec, claim, claimReason, stepLog, assertionResults, captures }),
        redactOpts,
      );
      const seHits = scanForSecrets(JSON.stringify(scenarioEvidence), extraPatterns);
      if (seHits.length > 0) {
        scenarioEvidence = {
          scenario: spec.scenario.id,
          status: claim,
          claim_level: "skipped",
          notes:
            "scenario_evidence quarantined by secret-scan preflight (TH-19) — content withheld, deny-dominates",
        };
      }
    }
  }

  // ---- 4. Ledger rows + manifest -------------------------------------------
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
      reason: `${claimReason} [executor claim — grading via qe accept trio (TH-10); verdict of record via scripts/qe/lib/gate.mjs (TH-6)]`,
      created_at: run.finished_at,
    },
    evidenceDir,
    qeVersion: RUNNER_VERSION,
    cli: "qe-runner",
    ...(scenarioEvidence !== null ? { scenarioEvidence } : {}),
  });

  return {
    runId: run.id,
    evidenceDir,
    manifestPath,
    claim,
    claimReason,
    preflight,
    projectId: project.id,
    scenarioId: scenario.id,
    // truth marker: false on a pre-2.1 ledger floor (block withheld, never
    // silently dropped by an older buildManifest)
    scenarioEvidenceEmitted: scenarioEvidence !== null,
  };
}
