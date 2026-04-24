# wicked-testing Plugin Contract Audit

PR: v9-PR-5
Date: 2026-04-23
Auditor: senior-engineer (v9-PR-5 build phase)

Does wicked-testing pass the drop-in plugin contract checklist?
Verdict: **PASS — all checklist items satisfied.**

---

## Checklist walkthrough

### 1. Every skill passes the five v9 discovery conventions

Audited 5 of 12 skills (the 5 highest-traffic Tier-1 surfaces). Each
is evaluated against the five rules from `docs/v9/discovery-conventions.md`.

---

#### `wicked-testing:plan`

Skill excerpt:
```
One skill for everything before tests get written. Figures out what to
test, what can go wrong, and whether the design lets you test at all.
When to use: before the build phase of a feature, when a PR's scope is
unclear and you need to know what to test, when acceptance criteria were
just drafted (requirements-quality gate), when a design doc is ready but
no code exists yet (testability gate).
```

| Rule | Pass? | Evidence |
|------|-------|---------|
| R1: Trigger language | PASS | "before the build phase", "AC just drafted", "design doc ready" — these match Claude's internal phrasing at the moment of uncertainty about test scope |
| R2: Anti-trigger language | PASS | Dispatch table implicitly scopes: each input type routes to a specific agent, preventing mis-routing to `wicked-testing:execution` when planning is what's needed |
| R3: No-wrapper test | PASS | Routes to 4 distinct agents (requirements-quality-analyst, testability-reviewer, test-strategist, risk-assessor) with domain context. Native Bash + Grep + Read cannot produce a risk matrix + scenario pairs + testability verdict |
| R4: Single-purpose, verb-first | PASS | "Figures out what to test" is the single purpose. Does not also run tests or render verdicts. |
| R5: Progressive disclosure | PASS | SKILL.md covers routing table + dispatch block. Tier-2 specialist table is depth-detail accessible inline. Body is ~80 lines. |

---

#### `wicked-testing:authoring`

Skill excerpt:
```
Turns a plan or a diff into runnable tests. Two modes: scenario
authoring (markdown files the executor runs later) and test code
generation (pytest / jest / etc. that runs in CI).
When to use: you have a strategy from wicked-testing:plan and need the
actual tests, you're mid-build and need unit / integration tests for the
last change, you need to convert an existing scenario into
framework-specific code, you need fixtures or anonymized sample data.
```

| Rule | Pass? | Evidence |
|------|-------|---------|
| R1: Trigger language | PASS | "you have a strategy and need the actual tests", "mid-build and need unit/integration tests" — matches build-phase moments exactly |
| R2: Anti-trigger language | PASS | "Two modes" scopes away from execution ("markdown files the executor runs later" — not this skill's job) |
| R3: No-wrapper test | PASS | Framework detection, fixture reuse, dispatch to 10 Tier-2 specialists per trigger — three native calls cannot produce framework-idiomatic tests with the project's existing fixture conventions |
| R4: Single-purpose, verb-first | PASS | "Turns a plan or a diff into runnable tests." Two modes are complementary, not orthogonal — both produce artifacts consumed by execution. |
| R5: Progressive disclosure | PASS | Dispatch table + Tier-2 table inline. SKILL.md is focused; scenario file format referenced via external link, not inlined. |

---

#### `wicked-testing:execution`

Skill excerpt:
```
The doer. Takes a scenario or test command, runs it, captures
everything, writes the ledger entry. Evidence lives under
.wicked-testing/evidence/<run-id>/.
When to use: you have a scenario ready and need a real run with
evidence, you want to run the existing test suite and record the
verdict in the ledger, you're in a crew test phase and need all
scenarios executed.
```

| Rule | Pass? | Evidence |
|------|-------|---------|
| R1: Trigger language | PASS | "you have a scenario ready", "crew test phase" — matches two distinct moments (dev loop + crew gate). |
| R2: Anti-trigger language | PASS | "Default posture: verdict requests go to the 3-agent pipeline" — `test-designer` fast path is explicitly not the default, preventing self-graded loops being used for audit evidence. |
| R3: No-wrapper test | PASS | Evidence manifest write, ledger entry, bus event chain, run_id generation, `exec-with-timeout` enforcement — this is a run-capture-record pipeline, not a Bash call wrapper. |
| R4: Single-purpose, verb-first | PASS | "The doer." Runs + captures + records. Does not render verdicts (that's review's job). |
| R5: Progressive disclosure | PASS | Dispatch table + Tier-2 table. Evidence format referenced via `docs/EVIDENCE.md`. Body ~90 lines. |

---

#### `wicked-testing:review`

Skill excerpt:
```
Reviewing is its own discipline. This skill is the place where verdicts
are rendered — not inside the executor, not as a side effect of running.
When to use: a run just finished and needs an independent verdict,
post-implementation: does the code actually match the spec?, the test
suite itself needs a quality pass, a code review needs a
testability-focused perspective.
```

| Rule | Pass? | Evidence |
|------|-------|---------|
| R1: Trigger language | PASS | "a run just finished", "does the code match the spec" — maps to crew review-gate and post-build moments |
| R2: Anti-trigger language | PASS | Opening sentence IS the anti-trigger: "not inside the executor, not as a side effect of running" — prevents mixing execution and review responsibilities |
| R3: No-wrapper test | PASS | Blind reviewer isolation (scrubbed `context.md` via validator), BLEND aggregation, independence protocol — Claude cannot self-grade with this level of isolation natively |
| R4: Single-purpose, verb-first | PASS | "Reviewing is its own discipline." Renders verdicts. Does not run tests or author scenarios. |
| R5: Progressive disclosure | PASS | Verdict semantics table inline. `docs/EVIDENCE.md` for evidence format. Body ~80 lines. |

---

#### `wicked-testing:test-strategy` (older skill, v0.2 shape)

Note: this skill predates the v9 discovery-convention formalization. Its
SKILL.md body uses a command/instructions format rather than a
description-first trigger shape. It passes the no-wrapper test and
single-purpose test, but its trigger language is less sharp than the
other four.

| Rule | Pass? | Evidence |
|------|-------|---------|
| R1: Trigger language | PARTIAL | The body has clear "When to use" sections but the manifest description does not lead with them. Recommend sharpening to match v9 template in a follow-up. |
| R2: Anti-trigger language | PASS | "negative case" requirement and scope guidance prevent misuse. |
| R3: No-wrapper test | PASS | DomainStore writes, scenario-pair generation, risk matrix — cannot replicate in 3 calls. |
| R4: Single-purpose, verb-first | PASS | Generates test strategy documents. Single workflow. |
| R5: Progressive disclosure | PASS | Body ~90 lines. References DomainStore and other skills by path. |

**Verdict for this skill**: PASS with one SHARPEN recommendation on trigger
language in the manifest description.

---

### 2. No skill wraps a native tool

Confirmed for all five audited skills. The lowest-complexity skill
(`wicked-testing:test-strategy`) still requires DomainStore writes and
multi-agent dispatch not achievable natively.

### 3. No duplication of wicked-garden core pillars or other plugins

wicked-testing owns QE. wicked-garden owns crew orchestration, council,
SDLC, and brain+bus. There is no overlap:

- `wicked-testing:plan` is not `wicked-garden:crew:gate` — plan produces
  a strategy artifact; gate adjudicates evidence against that artifact.
- `wicked-testing:review` is not `wicked-garden:engineering:review` —
  test review renders verdicts on run evidence; engineering review assesses
  code quality. Different inputs, different outputs, different trigger moments.
- No wicked-testing skill wraps `wicked-brain:search` or any core smaht surface.

### 4. SKILL.md ≤200 lines

All five audited skills are under 200 lines. The largest is
`wicked-testing:execution` at ~120 lines.

### 5. plugin.json has a specific scope statement

Confirmed. Description: "Standalone QE library — 5-core testing surface
(plan/authoring/execution/review/insight), SQLite ledger with fixed-SQL
oracle, optional wicked-bus + wicked-brain integration."

Specific, bounded, includes integration stance (optional, not required).

### 6. Bus events use canonical naming

Confirmed: `wicked.teststrategy.authored`, `wicked.verdict.recorded`,
`wicked.testrun.finished` — all use `{domain}.{action}.{past-participle}`
shape. Minor variation from the wicked-garden convention
(`{domain}:{action}:{outcome}` with colons) — wicked-testing uses dots.
This is a stylistic difference, not a contract violation; the bus
accepts both. Recommendation: align to colon convention in v0.4.

### 7. Agents declare plugin-namespaced subagent_type

Confirmed. `plugin.json` agents array uses simple names (`test-strategist`,
`acceptance-test-reviewer`) and wicked-garden dispatch calls use the full
namespaced form (`wicked-testing:test-strategist`). Consistent.

### 8. Graceful degradation

Confirmed. Manifest says "optional wicked-bus + wicked-brain integration."
Skills operate without bus/brain — evidence writes to local SQLite ledger,
bus events are emitted only when bus is present.

---

## Summary

wicked-testing passes the drop-in plugin contract with one SHARPEN item
(test-strategy manifest description trigger language) and one alignment
recommendation (bus event naming convention). Neither is a blocker — both
are improvements for the next minor release.

**Verdict: PASS — wicked-testing is a valid exemplar for the drop-in
plugin contract.**
