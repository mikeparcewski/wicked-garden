/**
 * test/th21-flake-policy.test.mjs — TH-21: the flaky-verdict policy engine
 * (scripts/qe/lib/flake-policy.mjs), unit level. Pure data-in/data-out —
 * the CLI-surface behavior (scoreboard exclusions + gate --exclusions-from)
 * is pinned in tests/qe/test_campaign_flake_policy.py.
 *
 *  - quarantine records consume fail-closed: active needs quarantined:true +
 *    scenario binding + taxonomy cause + owner + unexpired deadline; invalid
 *    and expired are reported, never honored; newest active record wins.
 *  - mixed graded outcomes inside a campaign = flake signal (never best-of-N).
 *  - > 1 + MAX_DIAGNOSTIC_RERUNS runs of one scenario = rerun_bound_exceeded.
 *  - a filtered selection showing PASS while omitting a same-window deny
 *    sibling = pass_laundering_risk.
 *  - buildExclusionsClause refuses exclusions missing id/reason/owner/deadline
 *    — exclusions ALWAYS carry reasons.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  MAX_DIAGNOSTIC_RERUNS,
  FLAKE_TAXONOMY,
  parseQuarantineCandidates,
  evaluateQuarantineRecord,
  loadQuarantineState,
  detectFlakeSignals,
  checkRerunBounds,
  findLaunderingRisks,
  buildExclusionsClause,
  buildGateSummary,
} from "../../lib/flake-policy.mjs";

const NOW = new Date("2026-08-29T12:00:00Z");
const FUTURE = "2026-09-12T00:00:00.000Z";
const PAST = "2026-08-01T00:00:00.000Z";

function quarantineTask(bodyOverrides = {}, taskOverrides = {}) {
  return {
    id: taskOverrides.id ?? "task-1",
    status: "blocked",
    assignee_skill: "flaky-test-hunter:env",
    created_at: "2026-08-28T00:00:00.000Z",
    body: JSON.stringify({
      quarantined: true,
      scenario_id: "sc-uuid-7",
      cause: "env",
      owner: "alice",
      quarantine_expires: FUTURE,
      flake_rate: 0.12,
      proposed_fix: "pin TZ in frontmatter",
      ...bodyOverrides,
    }),
    ...taskOverrides,
  };
}

const NAMES = new Map([["sc-uuid-7", "S7"]]);

// ---- quarantine candidates -----------------------------------------------------

test("candidates: only live hunter tasks with truthy quarantined qualify", () => {
  const tasks = [
    quarantineTask(), // yes
    quarantineTask({}, { id: "t-closed", status: "closed" }), // closed → no
    { id: "t-other", status: "open", assignee_skill: "flaky-test-hunter:env", body: JSON.stringify({ quarantined: false, cause: "env" }) }, // root-cause task → no
    { id: "t-need", status: "open", assignee_skill: "flaky-test-hunter:need-more-data", body: "prose, not json" }, // unparseable → no
    { id: "t-mirror", status: "open", assignee_skill: null, body: JSON.stringify({ quarantined: true }) }, // not the hunter → no
  ];
  const c = parseQuarantineCandidates(tasks);
  assert.equal(c.length, 1);
  assert.equal(c[0].task.id, "task-1");
});

// ---- record evaluation (fail-closed) --------------------------------------------

test("evaluate: a complete record with a future deadline is active", () => {
  const [cand] = parseQuarantineCandidates([quarantineTask()]);
  const r = evaluateQuarantineRecord(cand, { scenarioNameById: NAMES, now: NOW });
  assert.equal(r.state, "active");
  assert.equal(r.scenario, "S7");
  assert.equal(r.owner, "alice");
  assert.equal(r.cause, "env");
  assert.equal(r.deadline, FUTURE);
  assert.ok(r.reason.length > 0); // reasons are always derivable
});

test("evaluate: missing owner → invalid, never honored", () => {
  const [cand] = parseQuarantineCandidates([quarantineTask({ owner: "  " })]);
  const r = evaluateQuarantineRecord(cand, { scenarioNameById: NAMES, now: NOW });
  assert.equal(r.state, "invalid");
  assert.ok(r.problems.some((p) => p.includes("owner")));
});

test("evaluate: cause outside the hunter taxonomy → invalid", () => {
  const [cand] = parseQuarantineCandidates([quarantineTask({ cause: "just-flaky" })]);
  const r = evaluateQuarantineRecord(cand, { scenarioNameById: NAMES, now: NOW });
  assert.equal(r.state, "invalid");
  assert.ok(r.problems.some((p) => FLAKE_TAXONOMY.every((c) => p.includes(c))));
});

test("evaluate: no deadline → invalid; past deadline → expired", () => {
  const [noDeadline] = parseQuarantineCandidates([quarantineTask({ quarantine_expires: null })]);
  assert.equal(evaluateQuarantineRecord(noDeadline, { scenarioNameById: NAMES, now: NOW }).state, "invalid");
  const [past] = parseQuarantineCandidates([quarantineTask({ quarantine_expires: PAST })]);
  const r = evaluateQuarantineRecord(past, { scenarioNameById: NAMES, now: NOW });
  assert.equal(r.state, "expired");
  assert.ok(r.problems[0].includes("expired"));
});

test("evaluate: unresolvable scenario binding → invalid; scenario_name fallback works", () => {
  const [unbound] = parseQuarantineCandidates([quarantineTask({ scenario_id: "nope" })]);
  assert.equal(evaluateQuarantineRecord(unbound, { scenarioNameById: NAMES, now: NOW }).state, "invalid");
  const [byName] = parseQuarantineCandidates([quarantineTask({ scenario_id: undefined, scenario_name: "S9" })]);
  const r = evaluateQuarantineRecord(byName, { scenarioNameById: NAMES, now: NOW });
  assert.equal(r.state, "active");
  assert.equal(r.scenario, "S9");
});

test("load: newest active record per scenario wins; invalid+expired all reported", () => {
  const state = loadQuarantineState(
    [
      quarantineTask({ owner: "old-owner" }, { id: "t-old", created_at: "2026-08-20T00:00:00.000Z" }),
      quarantineTask({ owner: "new-owner" }, { id: "t-new", created_at: "2026-08-28T00:00:00.000Z" }),
      quarantineTask({ owner: "" }, { id: "t-bad" }),
      quarantineTask({ quarantine_expires: PAST }, { id: "t-exp" }),
    ],
    { scenarioNameById: NAMES, now: NOW }
  );
  assert.equal(state.active.length, 1);
  assert.equal(state.active[0].owner, "new-owner");
  assert.equal(state.invalid.length, 1);
  assert.equal(state.expired.length, 1);
});

// ---- flake signals / rerun bounds / laundering ----------------------------------

test("signals: PASS next to a deny grade for one scenario = flake signal", () => {
  const signals = detectFlakeSignals(
    new Map([
      ["S1", [{ grade: "FAIL", run_id: "r1" }, { grade: "PASS", run_id: "r2" }]],
      ["S2", [{ grade: "PASS", run_id: "r3" }, { grade: "PASS", run_id: "r4" }]],
      ["S3", [{ grade: "PASS", run_id: "r5" }, { grade: "INCONCLUSIVE", run_id: "r6" }]], // schema state, not a flip
      ["S4", [{ grade: "FAIL", run_id: "r7" }]],
    ])
  );
  assert.deepEqual(signals.map((s) => s.id), ["S1"]);
  assert.match(signals[0].action, /flaky-test-hunter/);
  assert.match(signals[0].action, /never best-of-N/);
});

test("bounds: more than 1 original + MAX_DIAGNOSTIC_RERUNS runs is a violation", () => {
  const atCap = new Map([["S1", Array.from({ length: 1 + MAX_DIAGNOSTIC_RERUNS }, (_, i) => ({ grade: "PASS", run_id: `r${i}` }))]]);
  assert.deepEqual(checkRerunBounds(atCap), []);
  const overCap = new Map([["S1", Array.from({ length: 2 + MAX_DIAGNOSTIC_RERUNS }, (_, i) => ({ grade: "PASS", run_id: `r${i}` }))]]);
  const v = checkRerunBounds(overCap);
  assert.equal(v.length, 1);
  assert.equal(v[0].kind, "rerun_bound_exceeded");
  assert.match(v[0].detail, /pass-laundering/);
});

test("laundering: visible PASS + omitted same-window deny sibling is flagged; older history is not", () => {
  const scenarioNameById = new Map([["sc-1", "S1"]]);
  const allRuns = [
    { id: "r-old-fail", scenario_id: "sc-1", started_at: "2026-08-01T00:00:00Z" }, // previous campaign
    { id: "r-fail", scenario_id: "sc-1", started_at: "2026-08-29T10:00:00Z" }, // omitted!
    { id: "r-pass", scenario_id: "sc-1", started_at: "2026-08-29T11:00:00Z" }, // selected
  ];
  const grades = { "r-old-fail": "FAIL", "r-fail": "FAIL", "r-pass": "PASS" };
  const v = findLaunderingRisks({
    allRuns,
    selectedRunIds: new Set(["r-pass"]),
    gradeForRun: (id) => grades[id] ?? null,
    scenarioNameById,
    visibleGradesById: new Map([["S1", ["PASS"]]]),
  });
  assert.equal(v.length, 1);
  assert.equal(v[0].kind, "pass_laundering_risk");
  assert.equal(v[0].run_id, "r-fail"); // the same-window omission — not the old history
});

test("laundering: a visible deny already blocks — omission is not flagged", () => {
  const v = findLaunderingRisks({
    allRuns: [
      { id: "r-fail", scenario_id: "sc-1", started_at: "2026-08-29T10:00:00Z" },
      { id: "r-fail2", scenario_id: "sc-1", started_at: "2026-08-29T11:00:00Z" },
    ],
    selectedRunIds: new Set(["r-fail2"]),
    gradeForRun: () => "FAIL",
    scenarioNameById: new Map([["sc-1", "S1"]]),
    visibleGradesById: new Map([["S1", ["FAIL"]]]),
  });
  assert.deepEqual(v, []);
});

// ---- gate representation ---------------------------------------------------------

test("exclusions clause: refuses any exclusion missing reason/owner/deadline", () => {
  const bad = buildExclusionsClause([{ id: "S7", cause: "env", owner: "alice", deadline: FUTURE }]); // no reason
  assert.equal(bad.ok, false);
  assert.ok(bad.problems.some((p) => p.includes("reason")));
  const alsoBad = buildExclusionsClause([{ id: "S7", reason: "flaky", cause: "env", deadline: FUTURE }]); // no owner
  assert.equal(alsoBad.ok, false);
});

test("exclusions clause: empty list is a no-op; complete entries render with reasons", () => {
  assert.deepEqual(buildExclusionsClause([]), { ok: true, clause: "" });
  const r = buildExclusionsClause([
    { id: "S7", cause: "env", owner: "alice", deadline: FUTURE, reason: "TZ-dependent assertion" },
  ]);
  assert.equal(r.ok, true);
  assert.match(r.clause, /excluded-with-reason \(1\)/);
  assert.match(r.clause, /S7 \(cause=env; owner=alice; deadline=2026-09-12T00:00:00\.000Z\) — TZ-dependent assertion/);
});

test("gate summary: certified with exclusions itemizes them beside the disposition", () => {
  const line = buildGateSummary({
    disposition: "certified",
    gatedTotal: 5,
    gatedPass: 5,
    blockers: [],
    excluded: [{ id: "S7", cause: "env", owner: "alice", deadline: FUTURE, reason: "TZ-dependent assertion" }],
  });
  assert.match(line, /^certified — 5\/5 gated rows PASS; quarantined excluded-with-reason \(1\)/);
  assert.match(line, /owner=alice/);
});
