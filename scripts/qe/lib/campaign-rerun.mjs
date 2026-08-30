#!/usr/bin/env node
/**
 * scripts/qe/lib/campaign-rerun.mjs — `qe campaign rerun` verdict diffs
 * (TH-23 / test-R19b, ADR 0006 "qe campaign").
 *
 * A campaign rerun reuses the PERSISTED strategy (campaign-recon.json) and
 * its committed deterministic specs; execution is the runner's job
 * (scripts/qe/runner) and grading is the accept trio + gate.mjs (TH-10/TH-6).
 * THIS module is the diff half: it consumes the ledger's run history —
 * the runs + verdicts rows that accrue under STABLE scenario ids (TH-6) —
 * and answers "what changed since the prior campaign run?", per scenario:
 *
 *   regression      baseline PASS → current deny/INCONCLUSIVE      (exit 1)
 *   fixed           baseline deny/INCONCLUSIVE → current PASS
 *   still-failing   deny → deny
 *   unchanged-pass  PASS → PASS
 *   new             no baseline run exists for the scenario
 *   not-rerun       baseline exists but no run inside the current
 *                   window (--since) — listed loudly; fails only with
 *                   --require-rerun (silently shrinking coverage is the
 *                   classic laundering move)
 *   ungraded-current the rerun happened but no isolated-reviewer verdict
 *                   exists yet — BLOCKS (exit 1): grade it (accept trio +
 *                   gate.mjs), never diff an executor claim
 *
 * Grade rule (mirrors campaign-scoreboard.mjs, TH-10): a grade is the newest
 * `verdicts` row by a NON-executor reviewer. Executor identities
 * ('qe-runner/executor-claim', /executor/i, /test-designer/i, 'self',
 * anonymous) never source a grade — deny-dominates.
 *
 * Scope rule (honest, fail-closed): the strategy names which ledger
 * scenarios belong to the campaign. A ledger scenario is in scope when its
 * name matches, for any rung/capability of the plan:
 *   - the rung's stub name  slug(`<plan-name>-<rung-id>`)     (exact)
 *   - a capability-id prefix `<capability-id>.`               (TH-6 naming)
 *   - the plan-name slug prefix `<plan-slug>-`                (stub family)
 * `--scenario-prefix` overrides derivation entirely. Zero matches is an
 * ERROR (exit 3) naming what was tried — never a silent empty diff.
 *
 * Usage (from the target repo's root):
 *   node campaign-rerun.mjs --strategy <campaign-recon.json | campaign-dir>
 *        [--repo-root <dir>] [--ledger-root <dir>] [--since <ISO-8601>]
 *        [--scenario-prefix <p>] [--require-rerun] [--json] [--out <file>]
 *
 * Exit codes: 0 no regressions/blockers · 1 regressions or blockers
 * (ungraded-current; not-rerun under --require-rerun) · 3 usage/system error.
 *
 * Ledger ROWS are read straight from the DomainStore's canonical JSON files
 * (`<root>/<table>/<id>.json`) like campaign-scoreboard.mjs — no package
 * resolution needed; the diff is pure history.
 */

import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, resolve, isAbsolute } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

// --- constants (mirror campaign-scoreboard.mjs / flake-policy.mjs) -------------

const EXECUTOR_CLAIM_REVIEWER = "qe-runner/executor-claim";
const SELF_GRADE_PATTERNS = [/executor/i, /test-designer/i];
/** Grades that deny at the gate (deny-dominates). INCONCLUSIVE also blocks a
 *  PASS baseline: schema-fail/system-error is never "still passing". */
const DENY_GRADES = new Set(["FAIL", "PARTIAL", "CONDITIONAL"]);

export const DELTAS = Object.freeze([
  "regression",
  "fixed",
  "still-failing",
  "unchanged-pass",
  "new",
  "not-rerun",
  "ungraded-current",
  "other",
]);

// --- small helpers --------------------------------------------------------------

function readJsonSafe(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function loadRows(ledgerRoot, table) {
  const dir = join(ledgerRoot, table);
  if (!existsSync(dir)) return [];
  const rows = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    const row = readJsonSafe(join(dir, f));
    if (row && row.deleted !== 1) rows.push(row);
  }
  return rows;
}

export function isExecutorIdentity(reviewer) {
  const rev = String(reviewer ?? "").trim();
  if (!rev) return true;
  if (rev === EXECUTOR_CLAIM_REVIEWER) return true;
  if (rev.toLowerCase() === "self") return true;
  return SELF_GRADE_PATTERNS.some((re) => re.test(rev));
}

/** Dual-read ledger-root resolution (same TH-2 semantics as the scoreboard). */
export function resolveLedgerRootLocal(repoRoot, env = process.env) {
  const pinned = env.WICKED_QE_LEDGER_DIR;
  if (pinned) return isAbsolute(pinned) ? pinned : join(repoRoot, pinned);
  const current = join(repoRoot, ".wicked-qe");
  if (existsSync(current)) return current;
  const legacy = join(repoRoot, ".wicked-testing");
  if (existsSync(legacy)) return legacy;
  return current;
}

function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// --- strategy loading ------------------------------------------------------------

/** Load the persisted strategy: a campaign-recon.json path or a campaign dir. */
export function loadStrategy(strategyPath) {
  let path = resolve(strategyPath);
  if (existsSync(path) && statSync(path).isDirectory()) {
    path = join(path, "campaign-recon.json");
  }
  const plan = readJsonSafe(path);
  if (!plan || !Array.isArray(plan.scenarios)) {
    throw new Error(
      `strategy ${path} is not a campaign-recon plan (scenarios[] missing) — ` +
        "pass the persisted campaign-recon.json (or its campaign dir)",
    );
  }
  return { plan, path };
}

/** Derive the scope matchers from a plan (see the module-header scope rule). */
export function strategyScope(plan) {
  const planSlug = slug(plan.name ?? "campaign");
  const exact = new Set();
  const prefixes = new Set([`${planSlug}-`]);
  for (const rung of plan.scenarios ?? []) {
    if (rung?.id) exact.add(slug(`${planSlug}-${rung.id}`));
    for (const cid of rung?.capability_ids ?? []) prefixes.add(`${cid}.`);
  }
  for (const cap of plan.capabilities ?? []) {
    if (cap?.id) prefixes.add(`${cap.id}.`);
  }
  return { exact, prefixes: [...prefixes] };
}

function inScope(name, scope, scenarioPrefix) {
  if (scenarioPrefix) return name.startsWith(scenarioPrefix);
  if (scope.exact.has(name)) return true;
  return scope.prefixes.some((p) => name.startsWith(p));
}

// --- the diff --------------------------------------------------------------------

/**
 * Diff current vs baseline verdicts per stable scenario id.
 *
 * Windows:
 *  - with `since`: current = runs with started_at >= since; baseline = the
 *    newest GRADED run strictly before since.
 *  - without `since`: current = the newest run; baseline = the newest GRADED
 *    run before it (an ungraded straggler never silently becomes baseline).
 *
 * Pure data-in/data-out — unit-testable without a filesystem.
 */
export function diffVerdicts({ scenarios, runsByScenario, gradeForRun, since = null }) {
  const rows = [];
  for (const s of scenarios) {
    const runs = [...(runsByScenario.get(s.id) ?? [])].sort((a, b) =>
      String(a.started_at ?? "").localeCompare(String(b.started_at ?? "")),
    );
    const graded = (run) => (run ? gradeForRun(run.id) : null);
    const describe = (run) =>
      run
        ? { run_id: run.id, grade: graded(run) ?? "UNGRADED", started_at: run.started_at ?? null }
        : null;

    let currentRun = null;
    let baselineRun = null;
    if (since) {
      const inWindow = runs.filter((r) => String(r.started_at ?? "") >= since);
      const before = runs.filter((r) => String(r.started_at ?? "") < since);
      // newest graded run in the window wins; else the newest window run
      // (surfacing UNGRADED honestly rather than reaching back in time).
      currentRun =
        [...inWindow].reverse().find((r) => graded(r)) ?? inWindow[inWindow.length - 1] ?? null;
      baselineRun = [...before].reverse().find((r) => graded(r)) ?? null;
    } else {
      currentRun = runs[runs.length - 1] ?? null;
      baselineRun =
        [...runs.slice(0, Math.max(0, runs.length - 1))].reverse().find((r) => graded(r)) ?? null;
    }

    const current = describe(currentRun);
    const baseline = describe(baselineRun);

    let delta;
    if (!currentRun && baselineRun) delta = "not-rerun";
    else if (!currentRun && !baselineRun) delta = "not-rerun"; // scenario known, never run
    else if (current.grade === "UNGRADED") delta = "ungraded-current";
    else if (!baselineRun) delta = "new";
    else {
      const b = baseline.grade;
      const c = current.grade;
      const bPass = b === "PASS";
      const cPass = c === "PASS";
      const bDeny = DENY_GRADES.has(b) || b === "INCONCLUSIVE";
      const cDeny = DENY_GRADES.has(c) || c === "INCONCLUSIVE";
      if (bPass && cPass) delta = "unchanged-pass";
      else if (bPass && cDeny) delta = "regression";
      else if (bDeny && cPass) delta = "fixed";
      else if (bDeny && cDeny) delta = "still-failing";
      else delta = "other";
    }

    rows.push({ id: s.name, scenario_id: s.id, baseline, current, delta });
  }
  return rows;
}

/**
 * Assemble the full rerun-diff envelope for a strategy against a ledger.
 * Throws on zero scope matches (never a silent empty diff).
 */
export function buildRerunDiff({
  strategyPath,
  repoRoot = process.cwd(),
  ledgerRoot = null,
  since = null,
  scenarioPrefix = null,
  requireRerun = false,
  env = process.env,
}) {
  const { plan, path } = loadStrategy(strategyPath);
  const scope = strategyScope(plan);
  const root = ledgerRoot ?? resolveLedgerRootLocal(repoRoot, env);

  const scenarioRows = loadRows(root, "scenarios").map((s) => ({
    id: s.id,
    name: s.name ?? s.id,
  }));
  const matched = scenarioRows.filter((s) => inScope(s.name, scope, scenarioPrefix));
  if (matched.length === 0) {
    const tried = scenarioPrefix
      ? `--scenario-prefix '${scenarioPrefix}'`
      : `exact stub names [${[...scope.exact].join(", ")}] and prefixes [${scope.prefixes.join(", ")}]`;
    throw new Error(
      `no ledger scenarios in ${root} matched the strategy scope (${tried}) — ` +
        "nothing to diff. Did the campaign's runs land in this ledger root? " +
        "(WICKED_QE_LEDGER_DIR / --ledger-root must match the runner's)",
    );
  }

  const runsByScenario = new Map();
  for (const run of loadRows(root, "runs")) {
    if (!runsByScenario.has(run.scenario_id)) runsByScenario.set(run.scenario_id, []);
    runsByScenario.get(run.scenario_id).push(run);
  }
  const verdictsByRun = new Map();
  for (const v of loadRows(root, "verdicts")) {
    if (!verdictsByRun.has(v.run_id)) verdictsByRun.set(v.run_id, []);
    verdictsByRun.get(v.run_id).push(v);
  }
  const gradeForRun = (runId) => {
    const vs = (verdictsByRun.get(runId) ?? []).sort((a, b) =>
      String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")),
    );
    return vs.find((v) => !isExecutorIdentity(v.reviewer))?.verdict ?? null;
  };

  const rows = diffVerdicts({ scenarios: matched, runsByScenario, gradeForRun, since }).sort(
    (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );

  const summary = Object.fromEntries(DELTAS.map((d) => [d, 0]));
  for (const r of rows) summary[r.delta] += 1;

  const regressions = rows.filter((r) => r.delta === "regression");
  const blockers = [];
  if (regressions.length > 0) {
    blockers.push(
      `${regressions.length} regression(s): ${regressions.map((r) => r.id).join(", ")}`,
    );
  }
  const ungraded = rows.filter((r) => r.delta === "ungraded-current");
  if (ungraded.length > 0) {
    blockers.push(
      `${ungraded.length} rerun(s) ungraded — grade them (accept trio + gate.mjs) before diffing: ` +
        ungraded.map((r) => r.id).join(", "),
    );
  }
  const notRerun = rows.filter((r) => r.delta === "not-rerun");
  if (requireRerun && notRerun.length > 0) {
    blockers.push(
      `--require-rerun: ${notRerun.length} scenario(s) not re-run in the current window: ` +
        notRerun.map((r) => r.id).join(", "),
    );
  }

  return {
    strategy: { name: plan.name ?? null, path, spec: plan.spec ?? null },
    ledger_root: root,
    since,
    scope: scenarioPrefix
      ? { scenario_prefix: scenarioPrefix }
      : { exact: [...scope.exact], prefixes: scope.prefixes },
    matched_scenarios: matched.length,
    rows,
    summary,
    regressions: regressions.map((r) => r.id),
    blockers,
    verdict_diff: blockers.length === 0 ? "clean" : "blocked",
    generated_at: new Date().toISOString(),
  };
}

// --- CLI -----------------------------------------------------------------------

const IS_MAIN = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (IS_MAIN) {
  let values;
  try {
    ({ values } = parseArgs({
      options: {
        strategy: { type: "string" },
        "repo-root": { type: "string" },
        "ledger-root": { type: "string" },
        since: { type: "string" },
        "scenario-prefix": { type: "string" },
        "require-rerun": { type: "boolean", default: false },
        json: { type: "boolean", default: false },
        out: { type: "string" },
      },
    }));
  } catch (err) {
    process.stderr.write(`campaign-rerun: ${err.message}\n`);
    process.exit(3);
  }

  if (!values.strategy) {
    process.stderr.write(
      "campaign-rerun: --strategy <campaign-recon.json | campaign-dir> is required\n",
    );
    process.exit(3);
  }
  if (values.since && Number.isNaN(Date.parse(values.since))) {
    process.stderr.write(`campaign-rerun: --since '${values.since}' is not an ISO-8601 timestamp\n`);
    process.exit(3);
  }

  try {
    const envelope = buildRerunDiff({
      strategyPath: values.strategy,
      repoRoot: values["repo-root"] ? resolve(values["repo-root"]) : process.cwd(),
      ledgerRoot: values["ledger-root"] ? resolve(values["ledger-root"]) : null,
      since: values.since ?? null,
      scenarioPrefix: values["scenario-prefix"] ?? null,
      requireRerun: values["require-rerun"],
    });
    const text = values.json
      ? JSON.stringify(envelope, null, 2)
      : [
          `qe campaign rerun diff — ${envelope.strategy.name ?? envelope.strategy.path}`,
          `  ledger: ${envelope.ledger_root}${envelope.since ? ` · window since ${envelope.since}` : " · latest vs prior graded"}`,
          ...envelope.rows.map(
            (r) =>
              `  ${r.id.padEnd(32)} ${String(r.baseline?.grade ?? "—").padEnd(12)} → ` +
              `${String(r.current?.grade ?? "—").padEnd(12)} ${r.delta}`,
          ),
          `  diff: ${envelope.verdict_diff}` +
            (envelope.blockers.length ? ` (${envelope.blockers.join(" · ")})` : ""),
        ].join("\n");
    if (values.out) writeFileSync(values.out, JSON.stringify(envelope, null, 2) + "\n", "utf8");
    process.stdout.write(text + "\n");
    process.exit(envelope.blockers.length === 0 ? 0 : 1);
  } catch (err) {
    process.stderr.write(`campaign-rerun error: ${err?.message ?? err}\n`);
    process.exit(3);
  }
}
