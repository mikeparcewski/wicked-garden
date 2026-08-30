#!/usr/bin/env node
/**
 * scripts/qe/lib/flake-policy.mjs — the flaky-verdict policy at the campaign
 * acceptance gate (TH-21, ADR 0006 "qe campaign"; RECON-TEST-HARNESS test-R23).
 *
 * Deny-dominates plus a 20+ scenario corpus means one flaky scenario denies
 * every nightly campaign — and a silent retry-to-green launders real bugs.
 * This module is the deterministic half of the written policy
 * (skills/qe/refs/campaign-flake-policy.md); campaign-scoreboard.mjs applies
 * it on every assembly and gate.mjs consumes its exclusions clause. Three
 * rules, all mechanical:
 *
 *  1. **Bounded diagnostic re-runs — BOTH verdicts recorded, never
 *     pass-laundering.** A re-run is a diagnostic, not a mulligan: every run
 *     lands as its own runs+verdicts rows under the SAME stable scenario id
 *     (TH-6 — that is the flake history the hunter consumes). Mixed graded
 *     outcomes for one scenario inside a campaign are a `flake_signal`
 *     (blocks certification, names the hunter as the remedy); more than
 *     1 + MAX_DIAGNOSTIC_RERUNS runs of one scenario is a
 *     `rerun_bound_exceeded` violation; a `--runs` selection that shows a
 *     scenario as PASS while omitting a deny-graded sibling run from the same
 *     window is a `pass_laundering_risk` violation.
 *
 *  2. **Quarantine lane — owner + deadline via the hunter's taxonomy.** Only
 *     `wicked-garden-qe-flaky-test-hunter` quarantines (its SKILL.md § 6
 *     strict policy); the gate only CONSUMES its machine-readable record: a
 *     ledger `tasks` row with `assignee_skill: flaky-test-hunter:<cause>`
 *     whose JSON body carries `quarantined: true`, a scenario binding,
 *     `cause` from the fixed taxonomy, `owner`, and `quarantine_expires`.
 *     Consumption is fail-closed: a record missing any of those is INVALID
 *     and not honored (the scenario stays in the gate, loudly); an expired
 *     record is not honored either.
 *
 *  3. **Excluded-with-reason, never silently dropped.** An honored
 *     quarantine removes the scenario's rows from the certification calculus
 *     but never from the scoreboard: the exclusion (id, cause, owner,
 *     deadline, reason, observed grades) rides `certification.excluded`, the
 *     `gate_summary` line, and — via gate.mjs `--exclusions-from` — the
 *     acceptance payload's `verdict_summary`. Exclusions without reasons are
 *     structurally impossible: `buildExclusionsClause` refuses them.
 *
 * Pure data-in/data-out — no filesystem, no process.exit — so every rule is
 * unit-testable. See scripts/qe/runner/test/th21-flake-policy.test.mjs and
 * tests/qe/test_campaign_flake_policy.py.
 */

// --- policy constants ----------------------------------------------------------

/** The hunter's fixed root-cause taxonomy (qe-flaky-test-hunter SKILL.md § 3). */
export const FLAKE_TAXONOMY = Object.freeze([
  "timing",
  "order-dep",
  "env",
  "resource",
  "external-dep",
]);

/** At most this many DIAGNOSTIC re-runs per rung per campaign (matches the
 *  fix-lane bound in refs/campaign-grading.md — bounded, then park). */
export const MAX_DIAGNOSTIC_RERUNS = 2;

/** Grades that deny at the gate (crew acceptance deny-dominates). */
export const DENY_GRADES = Object.freeze(new Set(["FAIL", "PARTIAL", "CONDITIONAL"]));

const QUARANTINE_SKILL_PREFIX = "flaky-test-hunter:";
const CLOSED_TASK_STATUSES = new Set(["closed", "done", "resolved", "cancelled"]);

// --- quarantine records ----------------------------------------------------------

function parseBody(task) {
  if (typeof task?.body !== "string") return null;
  try {
    const body = JSON.parse(task.body);
    return body && typeof body === "object" ? body : null;
  } catch {
    return null;
  }
}

/**
 * Filter ledger `tasks` rows down to quarantine CANDIDATES: written under the
 * hunter's `assignee_skill` namespace, not closed, JSON body with a truthy
 * `quarantined`. Non-quarantine hunter tasks (root-cause work,
 * `need-more-data`) and unrelated tasks are ignored entirely — they are not
 * "invalid quarantines", they are just not quarantines.
 */
export function parseQuarantineCandidates(tasks) {
  const candidates = [];
  for (const task of tasks ?? []) {
    const skill = String(task?.assignee_skill ?? "");
    if (!skill.startsWith(QUARANTINE_SKILL_PREFIX)) continue;
    if (CLOSED_TASK_STATUSES.has(String(task?.status ?? "").toLowerCase())) continue;
    const body = parseBody(task);
    if (!body || !body.quarantined) continue;
    candidates.push({ task, body });
  }
  return candidates;
}

/**
 * Evaluate ONE quarantine candidate against the fail-closed contract.
 * Returns a normalized record with `state`: 'active' | 'invalid' | 'expired'.
 * Invalid dominates expired (a record that is both is reported as invalid).
 */
export function evaluateQuarantineRecord({ task, body }, { scenarioNameById, now = new Date() } = {}) {
  const problems = [];

  // scenario binding: ledger scenario UUID (preferred) or the stable name
  let scenario = null;
  if (body.scenario_id && scenarioNameById?.has(body.scenario_id)) {
    scenario = scenarioNameById.get(body.scenario_id);
  } else if (typeof body.scenario_name === "string" && body.scenario_name.trim()) {
    scenario = body.scenario_name.trim();
  }
  if (!scenario) {
    problems.push("scenario binding unresolvable (scenario_id not in the ledger; no scenario_name)");
  }

  if (body.quarantined !== true) {
    problems.push(`quarantined must be exactly true (got ${JSON.stringify(body.quarantined)})`);
  }

  const cause = typeof body.cause === "string" ? body.cause : null;
  if (!cause || !FLAKE_TAXONOMY.includes(cause)) {
    problems.push(
      `cause '${cause ?? "(missing)"}' outside the hunter taxonomy (${FLAKE_TAXONOMY.join(" | ")})`
    );
  }

  const owner = typeof body.owner === "string" && body.owner.trim() ? body.owner.trim() : null;
  if (!owner) {
    problems.push("owner missing — a quarantine without an owner is not honored (hunter SKILL.md § 6)");
  }

  const deadlineRaw = body.quarantine_expires;
  const deadline = typeof deadlineRaw === "string" ? new Date(deadlineRaw) : null;
  if (!deadline || Number.isNaN(deadline.getTime())) {
    problems.push("quarantine_expires missing or unparseable — a quarantine without a deadline is not honored");
  }

  const flakeRate =
    typeof body.flake_rate === "number" ? ` flake_rate=${(body.flake_rate * 100).toFixed(1)}%` : "";
  const reason =
    typeof body.reason === "string" && body.reason.trim()
      ? body.reason.trim()
      : `flaky (cause=${cause ?? "?"}${flakeRate}) — quarantined pending: ${
          typeof body.proposed_fix === "string" && body.proposed_fix.trim()
            ? body.proposed_fix.trim()
            : "root-cause fix"
        }`;

  const record = {
    scenario,
    task_id: task?.id ?? null,
    task_status: task?.status ?? null,
    cause,
    owner,
    deadline: deadline && !Number.isNaN(deadline.getTime()) ? deadline.toISOString() : deadlineRaw ?? null,
    reason,
    created_at: task?.created_at ?? null,
  };

  if (problems.length > 0) return { ...record, state: "invalid", problems };
  if (deadline.getTime() <= now.getTime()) {
    return {
      ...record,
      state: "expired",
      problems: [
        `quarantine expired ${record.deadline} — not honored; the hunter auto-reopens expired quarantines`,
      ],
    };
  }
  return { ...record, state: "active", problems: [] };
}

/**
 * Load the quarantine state from ledger `tasks` rows. Active records are
 * deduped per scenario (newest `created_at` wins); invalid and expired
 * records are all reported — the gate stays honest about what it refused.
 */
export function loadQuarantineState(tasks, { scenarioNameById, now = new Date() } = {}) {
  const active = new Map(); // scenario -> record
  const invalid = [];
  const expired = [];
  for (const candidate of parseQuarantineCandidates(tasks)) {
    const record = evaluateQuarantineRecord(candidate, { scenarioNameById, now });
    if (record.state === "invalid") {
      invalid.push(record);
    } else if (record.state === "expired") {
      expired.push(record);
    } else {
      const prev = active.get(record.scenario);
      if (!prev || String(record.created_at ?? "") > String(prev.created_at ?? "")) {
        active.set(record.scenario, record);
      }
    }
  }
  return { active: [...active.values()], invalid, expired };
}

// --- diagnostic re-runs: signals, bounds, laundering ---------------------------

/**
 * Mixed graded outcomes for one scenario inside the campaign = a flake
 * signal. Input: Map<scenarioId, Array<{grade, run_id}>> over the GATED
 * (non-quarantined) rows. A PASS next to a deny grade means the diagnostic
 * re-run policy fired (or nondeterminism did) — both verdicts stand; the
 * signal blocks certification and names the hunter. INCONCLUSIVE/UNGRADED
 * are schema/pipeline states, not verdict flips, and do not signal.
 */
export function detectFlakeSignals(rowsByScenario) {
  const signals = [];
  for (const [id, rows] of rowsByScenario ?? []) {
    if (!rows || rows.length < 2) continue;
    const grades = rows.map((r) => r.grade);
    const hasPass = grades.includes("PASS");
    const denies = grades.filter((g) => DENY_GRADES.has(g));
    if (hasPass && denies.length > 0) {
      signals.push({
        id,
        grades,
        run_ids: rows.map((r) => r.run_id),
        action:
          "mixed verdicts within one campaign — BOTH recorded (never best-of-N); " +
          "route to wicked-garden-qe-flaky-test-hunter: fix by root cause, or quarantine " +
          "with owner+deadline (TH-21)",
      });
    }
  }
  return signals;
}

/**
 * More runs of one scenario than 1 original + MAX_DIAGNOSTIC_RERUNS
 * diagnostics is a policy violation — re-running until green is
 * pass-laundering even when every verdict is recorded.
 */
export function checkRerunBounds(rowsByScenario, maxDiagnosticReruns = MAX_DIAGNOSTIC_RERUNS) {
  const violations = [];
  const cap = 1 + maxDiagnosticReruns;
  for (const [id, rows] of rowsByScenario ?? []) {
    if (rows.length > cap) {
      violations.push({
        kind: "rerun_bound_exceeded",
        id,
        run_id: null,
        detail:
          `${rows.length} runs of '${id}' in one campaign exceeds the diagnostic re-run bound ` +
          `(1 original + ${maxDiagnosticReruns} diagnostics) — re-running until green is ` +
          "pass-laundering; park the rung and route to wicked-garden-qe-flaky-test-hunter (TH-21)",
      });
    }
  }
  return violations;
}

/**
 * Pass-laundering guard for filtered assemblies: when a `--runs` selection
 * shows a scenario as all-PASS while a sibling run of the SAME scenario from
 * the same window sits outside the selection with a deny grade, the omission
 * is flagged. "Same window" = the same UTC calendar day as a selected run of
 * that scenario (the hunter's own mixed-outcome heuristic — the classic
 * laundering shape is FAIL at 10:00, re-run PASS at 11:00, select only the
 * PASS), or any later run. Older history (previous campaigns, earlier days)
 * is legitimately out of scope.
 *
 * @param allRuns          every ledger runs row (unfiltered)
 * @param selectedRunIds   Set of run ids in the assembly
 * @param gradeForRun      (runId) => graded verdict string or null — the
 *                         caller's isolated-reviewer grade resolution
 * @param scenarioNameById Map<scenarioUuid, stable name>
 * @param visibleGradesById Map<stable name, Array<grade>> over gated rows
 */
export function findLaunderingRisks({
  allRuns,
  selectedRunIds,
  gradeForRun,
  scenarioNameById,
  visibleGradesById,
}) {
  const violations = [];
  // per scenario: earliest selected started_at + the selected calendar days
  const windowStart = new Map();
  const selectedDays = new Map();
  for (const run of allRuns ?? []) {
    if (!selectedRunIds.has(run.id)) continue;
    const name = scenarioNameById.get(run.scenario_id) ?? run.scenario_id;
    const at = String(run.started_at ?? "");
    const cur = windowStart.get(name);
    if (cur === undefined || at < cur) windowStart.set(name, at);
    if (!selectedDays.has(name)) selectedDays.set(name, new Set());
    selectedDays.get(name).add(at.slice(0, 10));
  }
  for (const run of allRuns ?? []) {
    if (selectedRunIds.has(run.id)) continue;
    const name = scenarioNameById.get(run.scenario_id) ?? run.scenario_id;
    const visible = visibleGradesById.get(name);
    if (!visible || visible.length === 0) continue; // scenario not in the assembly at all
    if (!visible.every((g) => g === "PASS")) continue; // a visible deny already blocks
    const at = String(run.started_at ?? "");
    const sameDay = selectedDays.get(name)?.has(at.slice(0, 10)) ?? false;
    const atOrAfter = windowStart.has(name) && at >= windowStart.get(name);
    if (!sameDay && !atOrAfter) continue; // older history
    const grade = gradeForRun(run.id);
    if (grade && DENY_GRADES.has(grade)) {
      violations.push({
        kind: "pass_laundering_risk",
        id: name,
        run_id: run.id,
        detail:
          `'${name}' shows PASS in this assembly while sibling run ${run.id} from the same ` +
          `window graded ${grade} and was omitted from the selection — a diagnostic re-run ` +
          "never replaces the failing verdict; include every run of the scenario (TH-21)",
      });
    }
  }
  return violations;
}

// --- gate representation ---------------------------------------------------------

/**
 * The canonical excluded-with-reason clause for the acceptance payload
 * (gate.mjs --exclusions-from appends it to --verdict-summary; the 8-field
 * wicked.qe.gate.* wire contract is untouched — the clause rides
 * verdict_summary). Fail-closed: an exclusion missing id, reason, owner, or
 * deadline is refused — exclusions ALWAYS carry reasons.
 */
export function buildExclusionsClause(excluded) {
  const problems = [];
  for (const e of excluded ?? []) {
    for (const key of ["id", "reason", "owner", "deadline"]) {
      const v = e?.[key];
      if (typeof v !== "string" || !v.trim()) {
        problems.push(`exclusion '${e?.id ?? "(unknown)"}': missing ${key} — an exclusion without a ${key} is refused`);
      }
    }
  }
  if (problems.length > 0) return { ok: false, problems };
  if (!excluded || excluded.length === 0) return { ok: true, clause: "" };
  const parts = excluded.map(
    (e) =>
      `${e.id} (cause=${e.cause ?? "unspecified"}; owner=${e.owner}; deadline=${e.deadline}) — ${e.reason}`
  );
  return {
    ok: true,
    clause: `quarantined excluded-with-reason (${excluded.length}): ${parts.join(" · ")}`,
  };
}

/**
 * One line for gate.mjs --verdict-summary: disposition + gated tallies +
 * every exclusion with its reason. Deterministic assembly, no judgment.
 */
export function buildGateSummary({ disposition, gatedTotal, gatedPass, blockers = [], excluded = [] }) {
  let line =
    disposition === "certified"
      ? `certified — ${gatedPass}/${gatedTotal} gated rows PASS`
      : `not-certified — ${blockers.length} blocker(s): ${blockers.join(" · ")}`;
  if (excluded.length > 0) {
    const built = buildExclusionsClause(excluded);
    line += `; ${built.ok ? built.clause : `${excluded.length} exclusion(s) UNREPORTABLE: ${built.problems.join("; ")}`}`;
  }
  return line;
}
