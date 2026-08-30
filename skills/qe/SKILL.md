---
name: wicked-garden-qe
user-invocable: true
description: |
  Consolidated quality-engineering domain skill: evidence-gated testing from
  strategy to verdict. Nine actions — setup (per-project init), plan (test
  strategy, risk, testability, AC quality), author (scenarios, test code,
  fixtures), campaign (three-lens repo recon → dependency-ordered scenario
  ladder per campaign-recon format v2), intake (plan proposed as a crew HITL
  gate — approve/amend/reject), execute (run scenarios/suites, capture
  evidence), review (independent verdicts, spec alignment, suite quality),
  insight (ledger stats, flake detection, coverage archaeology), accept
  (the isolated 3-agent pipeline that eliminates self-grading).

  Use when: "what should I test", "test strategy", "write tests", "author
  scenarios", "qe campaign", "test the whole app", "capability inventory",
  "campaign plan", "run the test", "capture evidence", "prove it works",
  "acceptance test", "verify it works", "did it pass", "judge the evidence",
  "verdict", "is this test suite any good", "flake rate", "has this passed
  recently", "coverage gaps", "release readiness", "initialize testing".

  NOT for: senior-engineer code review (engineering review action),
  multi-model deliberation (jam council), in-run crew review
  (wicked-garden-crew-reviewer), or the portable evidence gate stamped into
  a repo (the prove skill's compile action).
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# QE — quality engineering

Evidence-gated testing as a domain: strategy → authoring → execution →
independent verdict, with a read-only ledger lens. Verdicts are re-derived
from captured evidence — never self-asserted by the agent that ran the work.
Data contract: `.wicked-qe/` (config, evidence, SQLite ledger); legacy <!-- historical -->
`.wicked-testing/` roots still resolve via wicked-ledger's dual-read.

## Routing

| Ask | Action |
|-----|--------|
| Initialize QE for this project / `ERR_NO_CONFIG` | § setup |
| What to test, risk matrix, testability, AC quality | § plan |
| Write scenarios, test code, fixtures, test data | § author |
| Campaign a whole repo: recon → capability inventory → scenario ladder | § campaign |
| Confirm/refine a campaign plan at a human gate; annotation intake | § intake |
| Flaky campaign verdict: diagnostic re-run, quarantine, gate exclusions | § campaign (flake policy) |
| Run a scenario/suite, capture evidence, record the run | § execute |
| Independent verdict, spec-vs-code alignment, suite quality | § review |
| Ledger stats, flake rate, coverage gaps, history | § insight |
| Acceptance-grade verdict via the isolated 3-agent pipeline | § accept |

**Review disambiguation**: this domain renders *verdicts on captured QE
evidence*. Source-code quality review is the `engineering` skill's review
action; multi-model deliberation is `jam` council; in-run crew review is
`wicked-garden-crew-reviewer`; spec-meaning judgment is dispatched to
`wicked-garden-qe-semantic-reviewer`.

## Preflight (all actions except setup)

```bash
# dual-read (Phase 6c): a legacy .wicked-testing root still counts
{ test -f ".wicked-qe/config.json" || test -f ".wicked-testing/config.json"; } || echo "ERR_NO_CONFIG"
```

On `ERR_NO_CONFIG`, run § setup first (it is safe to auto-run: it only
scaffolds `.wicked-qe/` and registers a project record).

## setup — per-project initialization

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/setup.md")` — full playbook.
2. Detect available test CLIs, create `.wicked-qe/` + `config.json`,
   register the project row in the ledger DomainStore.

## plan — strategy, risk, testability, AC quality

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/plan.md")` — full playbook.
2. Route the target to `wicked-garden-qe-{test-strategist | risk-assessor |
   testability-reviewer | requirements-quality-analyst}` (parallel when broad);
   merge findings into one strategy with concrete next actions.

## author — scenarios, test code, fixtures

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/author.md")` — full playbook.
2. Scenario authoring and/or framework test code via
   `wicked-garden-qe-{test-automation-engineer | acceptance-test-writer |
   test-data-manager | contract-testing-engineer}` per the playbook's table.

## campaign — repo recon + generated scenario ladder

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/campaign.md")` — full playbook.
2. Three-lens recon (estate code graph when the target is indexed, docs
   recall via `wicked-garden-mem`, live probe incl. committed endpoint
   manifests) → a plan CONFORMING to
   `${CLAUDE_PLUGIN_ROOT}/schemas/campaign-recon.schema.json` (v2; spec:1
   plans still validate — never a parallel format), assembled + validated
   fail-closed by `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_plan.py`,
   persisted as a ledger `strategies` row + scenario-format v1.1 files. Unindexed targets
   degrade honestly (`sources.estate: "unindexed"`); doc-derived claims
   enter `proposed`, pending human review.
3. Flaky verdicts at the campaign gate:
   `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/campaign-flake-policy.md")` —
   bounded diagnostic re-runs (BOTH verdicts recorded, never best-of-N), the
   hunter-owned quarantine lane (owner + deadline via the flake taxonomy),
   and quarantined scenarios excluded-with-reason in the scoreboard and
   acceptance payload (TH-21).

## intake — propose the campaign plan as a human gate (TH-12)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/intake.md")` — full playbook.
2. V1 = **propose-as-gate** over crew's campaign-proven UI+REST gate wire
   (`${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_intake.py`): approve runs the
   confirmed set, amend = the scenario-edit channel, reject cancels.
   Annotations → PROPOSED entries. Elicitation = v2 (wicked-crew#358).

## execute — run + capture evidence

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/execute.md")` — full playbook.
2. Dispatch `wicked-garden-qe-scenario-executor` (or the matching specialist);
   evidence lands in `.wicked-qe/evidence/<run-id>/`; run + verdict rows
   go to the ledger. Verdict requests default to § accept, never self-grading.

## review — independent verdicts

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/review.md")` — full playbook.
2. Evidence manifests → `wicked-garden-qe-acceptance-test-reviewer`;
   spec-vs-code → `wicked-garden-qe-semantic-reviewer`; suite quality →
   `wicked-garden-qe-code-analyzer` + the matching tier-2 specialist.

## insight — read-only ledger lens

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/insight.md")` — full playbook.
2. Natural-language questions route to `wicked-garden-qe-test-oracle`
   (fixed-SQL oracle — never synthesized SQL); flake/coverage/exploratory
   questions go to their dedicated specialists. Never mutates state.

## accept — the 3-agent acceptance pipeline

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/qe/refs/accept.md")` — full playbook.
   **Isolation is the point**: Writer plans, Executor captures, Reviewer
   judges from evidence paths only (`allowed-tools: Read`, `context: fork`,
   evidence-only dispatch). Never leak executor context to the reviewer.
2. Verdict + run rows are written via the wicked-ledger DomainStore and the
   public manifest lands at `.wicked-qe/evidence/<run-id>/manifest.json`.

## Fork workers (dispatch with the Skill tool)

**Dispatch guard (mandatory):** resolve every specialist through
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_dispatch.py" <name>`
before the Skill call — it asserts the resolved worker is a shipped
`wicked-garden-qe-*` skill and BLOCKS retired `wicked-testing-*` /
`wicked-brain-*` names at dispatch with a clear error naming the garden
replacement. Never work around a block; fix the caller.

Pipeline: `wicked-garden-qe-acceptance-test-{writer, executor, reviewer}` ·
`wicked-garden-qe-scenario-executor` · `wicked-garden-qe-test-designer`
(dev-loop fast path — keeps its self-grading warning).

Planning: `wicked-garden-qe-{test-strategist, risk-assessor,
testability-reviewer, requirements-quality-analyst}`.

Review/insight: `wicked-garden-qe-{semantic-reviewer, code-analyzer,
test-oracle, production-quality-engineer, release-readiness-engineer,
flaky-test-hunter, coverage-archaeologist, exploratory-tester,
test-code-quality-auditor, snapshot-hygiene-auditor, test-impact-analyzer,
mutation-test-engineer}`.

Domain specialists (all prefixed `wicked-garden-qe-`): `a11y-test-engineer` ·
`security-test-engineer` · `compliance-test-engineer` ·
`ai-feature-test-engineer` · `chaos-test-engineer` · `iac-test-engineer` ·
`integration-test-engineer` · `localization-test-engineer` ·
`observability-test-engineer` · `ui-component-test-engineer` ·
`load-performance-engineer` · `visual-regression-engineer` ·
`fuzz-property-engineer` · `data-quality-tester` · `e2e-orchestrator` ·
`contract-testing-engineer` · `test-automation-engineer` ·
`test-data-manager` · `incident-to-scenario-synthesizer`.

**Executor-vs-advisor twins** (reciprocal NOT-THIS-WHEN contracts): qe
specialists RUN tools and write evidence + ledger verdict rows; their garden
twins advise. a11y ↔ `product-a11y-expert`; security ↔
`platform-security-engineer`; compliance ↔ `platform-compliance-officer`;
AC quality ↔ `product-requirements-analyst`; AI-feature probes ↔
`agentic-safety-reviewer` (design-time).

## Data layer

- **Evidence + config contract (shared with crew/ledger — do not rename):**
  `.wicked-qe/config.json`, `.wicked-qe/evidence/<run-id>/`,
  `.wicked-qe/wicked-qe.db`.
- **wicked-ledger** (npm, pinned via `wicked_ledger_version` in plugin.json):
  DomainStore CRUD, fixed-SQL oracle queries, `buildManifest`. Import-style
  snippets need the package resolvable from the project
  (`npm i --no-save wicked-ledger`).
- **`{WT_LIB}` helpers**: specialist playbooks reference helper modules that
  ship in-catalog at `${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/` (ported from the
  retired wicked-testing package in Phase 6c) — resolve <!-- historical -->
  `WT_LIB="${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib"`.

## Integration with wicked-crew

Engaged during **build** (author + execute), **test/review** phases
(execute + accept + review), and **ship** gates (release-readiness via
insight/review). Crew routes the `qe` specialist per `specialist.json`;
gates read verdict rows from the ledger — the pipeline never self-declares
a crew gate passed.
