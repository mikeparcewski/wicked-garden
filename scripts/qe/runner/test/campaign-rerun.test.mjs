/**
 * test/campaign-rerun.test.mjs — TH-23: `qe campaign rerun` verdict diffs.
 *
 *  - diffVerdicts classifies every delta honestly: regression / fixed /
 *    still-failing / unchanged-pass / new / not-rerun / ungraded-current —
 *    and an INCONCLUSIVE current never counts as "still passing".
 *  - the grade rule mirrors the scoreboard (TH-10): only NON-executor
 *    verdicts rows source a grade; an ungraded rerun BLOCKS instead of
 *    silently diffing an executor claim.
 *  - the --since window picks the newest GRADED run per side; an ungraded
 *    straggler never silently becomes the baseline.
 *  - buildRerunDiff is fail-closed on scope: zero ledger matches is an
 *    ERROR naming what was tried, never a silent empty diff; blockers
 *    (regression / ungraded-current / not-rerun under requireRerun) make
 *    the envelope "blocked".
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import {
  diffVerdicts,
  isExecutorIdentity,
  strategyScope,
  buildRerunDiff,
  DELTAS,
} from "../../lib/campaign-rerun.mjs";

// ---- helpers -----------------------------------------------------------------

function mkDiff({ runs, grades, since = null }) {
  const scenarios = [{ id: "sc1", name: "camp-s1" }];
  const runsByScenario = new Map([
    ["sc1", runs.map((r, i) => ({ id: `r${i}`, scenario_id: "sc1", started_at: r }))],
  ]);
  const gradeForRun = (id) => grades[Number(id.slice(1))] ?? null;
  return diffVerdicts({ scenarios, runsByScenario, gradeForRun, since })[0];
}

// ---- grade-source rule (TH-10) -------------------------------------------------

test("executor identities never source a grade", () => {
  assert.equal(isExecutorIdentity("qe-runner/executor-claim"), true);
  assert.equal(isExecutorIdentity("wicked-garden-qe-acceptance-test-executor"), true);
  assert.equal(isExecutorIdentity("qe-test-designer"), true);
  assert.equal(isExecutorIdentity("self"), true);
  assert.equal(isExecutorIdentity(""), true);
  assert.equal(isExecutorIdentity(undefined), true);
  assert.equal(isExecutorIdentity("qe-acceptance-test-reviewer"), false);
});

// ---- delta taxonomy ------------------------------------------------------------

test("PASS → FAIL is a regression", () => {
  const row = mkDiff({ runs: ["2026-08-28T10:00:00Z", "2026-08-30T10:00:00Z"], grades: ["PASS", "FAIL"] });
  assert.equal(row.delta, "regression");
  assert.equal(row.baseline.grade, "PASS");
  assert.equal(row.current.grade, "FAIL");
});

test("PASS → INCONCLUSIVE is a regression too — schema-fail is never 'still passing'", () => {
  const row = mkDiff({ runs: ["a", "b"], grades: ["PASS", "INCONCLUSIVE"] });
  assert.equal(row.delta, "regression");
});

test("deny → PASS is fixed; deny → deny is still-failing; PASS → PASS unchanged", () => {
  assert.equal(mkDiff({ runs: ["a", "b"], grades: ["FAIL", "PASS"] }).delta, "fixed");
  assert.equal(mkDiff({ runs: ["a", "b"], grades: ["FAIL", "CONDITIONAL"] }).delta, "still-failing");
  assert.equal(mkDiff({ runs: ["a", "b"], grades: ["PASS", "PASS"] }).delta, "unchanged-pass");
});

test("first-ever graded run is new; ungraded rerun blocks as ungraded-current", () => {
  assert.equal(mkDiff({ runs: ["a"], grades: ["PASS"] }).delta, "new");
  const row = mkDiff({ runs: ["2026-08-28T10:00:00Z", "2026-08-30T10:00:00Z"], grades: ["PASS", null] });
  assert.equal(row.delta, "ungraded-current");
  assert.equal(row.current.grade, "UNGRADED");
});

test("baseline exists but nothing ran in the window → not-rerun", () => {
  const row = mkDiff({
    runs: ["2026-08-28T10:00:00Z"],
    grades: ["PASS"],
    since: "2026-08-30T00:00:00Z",
  });
  assert.equal(row.delta, "not-rerun");
  assert.equal(row.baseline.grade, "PASS");
  assert.equal(row.current, null);
});

test("window: newest GRADED run wins the window; an ungraded straggler never becomes baseline", () => {
  // three runs: graded PASS before the window; in-window graded FAIL then ungraded straggler
  const row = mkDiff({
    runs: ["2026-08-28T10:00:00Z", "2026-08-30T09:00:00Z", "2026-08-30T11:00:00Z"],
    grades: ["PASS", "FAIL", null],
    since: "2026-08-30T00:00:00Z",
  });
  assert.equal(row.current.grade, "FAIL"); // graded beats newer-but-ungraded
  assert.equal(row.baseline.grade, "PASS");
  assert.equal(row.delta, "regression");
});

test("no since: baseline skips back past ungraded runs to the newest graded one", () => {
  const row = mkDiff({
    runs: ["2026-08-27T10:00:00Z", "2026-08-29T10:00:00Z", "2026-08-30T10:00:00Z"],
    grades: ["PASS", null, "FAIL"],
  });
  assert.equal(row.baseline.grade, "PASS");
  assert.equal(row.delta, "regression");
});

// ---- strategy scope --------------------------------------------------------------

test("strategyScope derives exact stub names + capability and plan-slug prefixes", () => {
  const scope = strategyScope({
    name: "crew-e2e",
    scenarios: [{ id: "api-smoke", capability_ids: ["api-health"] }],
    capabilities: [{ id: "api-health" }],
  });
  assert.ok(scope.exact.has("crew-e2e-api-smoke"));
  assert.ok(scope.prefixes.includes("crew-e2e-"));
  assert.ok(scope.prefixes.includes("api-health."));
});

// ---- buildRerunDiff end to end -----------------------------------------------------

function writeLedgerFixture(root, { grades }) {
  for (const table of ["scenarios", "runs", "verdicts"]) {
    mkdirSync(join(root, table), { recursive: true });
  }
  const w = (table, id, row) =>
    writeFileSync(join(root, table, `${id}.json`), JSON.stringify(row));
  w("scenarios", "sc1", { id: "sc1", name: "camp-s1" });
  grades.forEach((g, i) => {
    w("runs", `r${i}`, { id: `r${i}`, scenario_id: "sc1", started_at: `2026-08-2${8 + i}T10:00:00Z` });
    if (g) {
      // an executor self-claim rides along on every run and must never grade
      w("verdicts", `x${i}`, {
        id: `x${i}`,
        run_id: `r${i}`,
        verdict: "PASS",
        reviewer: "qe-runner/executor-claim",
        created_at: `2026-08-2${8 + i}T10:01:00Z`,
      });
      w("verdicts", `v${i}`, {
        id: `v${i}`,
        run_id: `r${i}`,
        verdict: g,
        reviewer: "qe-acceptance-test-reviewer",
        created_at: `2026-08-2${8 + i}T10:05:00Z`,
      });
    }
  });
}

function writeStrategy(dir) {
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "campaign-recon.json"),
    JSON.stringify({
      spec: 2,
      name: "camp",
      target: { repo: "acme/x" },
      sources: { estate: "unindexed" },
      capabilities: [{ id: "c1", surface: "s", apis: "a", test_shape: "t", needs: "n" }],
      environment_manifest: { ref: "environment-manifest.json" },
      scenarios: [
        {
          id: "s1",
          category: "api",
          capability_ids: ["c1"],
          deps: [],
          pass_criteria: { terminal_state: "t", artifact: "a", consumer_state: "c" },
          claim_ceiling: "machinery-verified",
        },
      ],
    }),
  );
}

test("regression makes the envelope blocked; executor claims never mask it", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  writeLedgerFixture(ledger, { grades: ["PASS", "FAIL"] });
  writeStrategy(join(t, "camp"));
  const env = buildRerunDiff({ strategyPath: join(t, "camp"), ledgerRoot: ledger });
  assert.equal(env.verdict_diff, "blocked");
  assert.deepEqual(env.regressions, ["camp-s1"]);
  assert.equal(env.summary.regression, 1);
});

test("clean rerun (PASS → PASS) is exit-0 clean", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  writeLedgerFixture(ledger, { grades: ["PASS", "PASS"] });
  writeStrategy(join(t, "camp"));
  const env = buildRerunDiff({ strategyPath: join(t, "camp"), ledgerRoot: ledger });
  assert.equal(env.verdict_diff, "clean");
  assert.equal(env.blockers.length, 0);
  assert.equal(env.summary["unchanged-pass"], 1);
});

test("ungraded rerun blocks — grade it, never diff an executor claim", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  writeLedgerFixture(ledger, { grades: ["PASS", null] });
  writeStrategy(join(t, "camp"));
  const env = buildRerunDiff({ strategyPath: join(t, "camp"), ledgerRoot: ledger });
  assert.equal(env.verdict_diff, "blocked");
  assert.match(env.blockers.join(" "), /ungraded/);
});

test("requireRerun turns not-rerun into a blocker (coverage never shrinks silently)", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  writeLedgerFixture(ledger, { grades: ["PASS"] });
  writeStrategy(join(t, "camp"));
  const relaxed = buildRerunDiff({
    strategyPath: join(t, "camp"),
    ledgerRoot: ledger,
    since: "2026-08-30T00:00:00Z",
  });
  assert.equal(relaxed.summary["not-rerun"], 1);
  assert.equal(relaxed.verdict_diff, "clean"); // listed loudly, not a blocker
  const strict = buildRerunDiff({
    strategyPath: join(t, "camp"),
    ledgerRoot: ledger,
    since: "2026-08-30T00:00:00Z",
    requireRerun: true,
  });
  assert.equal(strict.verdict_diff, "blocked");
  assert.match(strict.blockers.join(" "), /not re-run/);
});

test("zero scope matches is an error naming what was tried — never an empty diff", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  mkdirSync(join(ledger, "scenarios"), { recursive: true });
  writeFileSync(
    join(ledger, "scenarios", "other.json"),
    JSON.stringify({ id: "other", name: "unrelated-scenario" }),
  );
  writeStrategy(join(t, "camp"));
  assert.throws(
    () => buildRerunDiff({ strategyPath: join(t, "camp"), ledgerRoot: ledger }),
    /no ledger scenarios .* matched/s,
  );
});

test("a non-plan strategy file is refused with the fix in the message", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  writeFileSync(join(t, "nope.json"), JSON.stringify({ hello: 1 }));
  assert.throws(
    () => buildRerunDiff({ strategyPath: join(t, "nope.json"), ledgerRoot: t }),
    /scenarios\[\] missing/,
  );
});

test("the delta vocabulary is closed and every summary key is present", () => {
  const t = mkdtempSync(join(tmpdir(), "rerun-"));
  const ledger = join(t, "ledger");
  writeLedgerFixture(ledger, { grades: ["PASS", "PASS"] });
  writeStrategy(join(t, "camp"));
  const env = buildRerunDiff({ strategyPath: join(t, "camp"), ledgerRoot: ledger });
  assert.deepEqual(Object.keys(env.summary).sort(), [...DELTAS].sort());
});
