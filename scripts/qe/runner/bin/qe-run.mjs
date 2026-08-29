#!/usr/bin/env node
/**
 * bin/qe-run.mjs — CLI for the model-free qe campaign executor.
 *
 *   node bin/qe-run.mjs <spec.json> [--repo-root <dir>] [--video] [--trace]
 *   node bin/qe-run.mjs <spec.json> --lint-only
 *
 * Exit codes:
 *   0 executed, executor claim PASS
 *   1 executed, executor claim FAIL
 *   2 executed, claim INCONCLUSIVE (run error or secret-scan preflight hit)
 *   3 runner/system error (nothing trustworthy was recorded)
 *   4 spec rejected by lint (never executed)
 *
 * The claim is an EXECUTOR CLAIM, not a graded verdict — grading is the qe
 * accept trio's job (TH-10).
 */

import { parseArgs } from "node:util";
import { loadSpec, SpecError } from "../src/spec.mjs";
import { runSpec } from "../src/runner.mjs";

const { values, positionals } = parseArgs({
  options: {
    "repo-root": { type: "string" },
    video: { type: "boolean", default: false },
    trace: { type: "boolean", default: false },
    "lint-only": { type: "boolean", default: false },
  },
  allowPositionals: true,
});

const specPath = positionals[0];
if (!specPath) {
  console.error("usage: qe-run <spec.json> [--repo-root <dir>] [--video] [--trace] [--lint-only]");
  process.exit(3);
}

let spec;
try {
  spec = loadSpec(specPath);
} catch (e) {
  if (e instanceof SpecError) {
    console.error(`SPEC REJECTED (${specPath}):`);
    for (const err of e.errors) console.error(`  - ${err}`);
    process.exit(4);
  }
  console.error(`runner error: ${e.message}`);
  process.exit(3);
}

if (values["lint-only"]) {
  console.log(JSON.stringify({ lint: "ok", spec: specPath, scenario: spec.scenario.id }));
  process.exit(0);
}

try {
  const result = await runSpec(spec, {
    repoRoot: values["repo-root"] ?? process.cwd(),
    video: values.video,
    trace: values.trace,
    specPath,
  });
  console.log(
    JSON.stringify(
      {
        scenario: spec.scenario.id,
        run_id: result.runId,
        claim: result.claim,
        claim_reason: result.claimReason,
        evidence_dir: result.evidenceDir,
        manifest: result.manifestPath,
        preflight_hits: result.preflight.length,
      },
      null,
      2,
    ),
  );
  process.exit(result.exitCode);
} catch (e) {
  console.error(`runner error: ${e?.stack ?? e}`);
  process.exit(3);
}
