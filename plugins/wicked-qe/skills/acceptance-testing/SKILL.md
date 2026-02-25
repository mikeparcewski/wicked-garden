---
name: acceptance-testing
description: >
  Evidence-gated acceptance testing with three-agent separation of concerns.
  Writer designs test plans, Executor collects artifacts, Reviewer evaluates independently.
  Eliminates false positives from self-grading. Reusable for any project's acceptance criteria.
---

# Acceptance Testing

Three-agent pipeline that separates test writing, execution, and review for higher-fidelity acceptance testing.

## The Problem with Self-Grading

When the same agent executes and grades tests, it pattern-matches "something happened" as success:

- Command produced output → "PASS" (but output was wrong)
- File was created → "PASS" (but contents are incorrect)
- No errors → "PASS" (but the feature didn't activate)

**Result**: 80%+ false positive rate on qualitative criteria.

## Three-Agent Architecture

```
Writer ──→ Test Plan ──→ Executor ──→ Evidence ──→ Reviewer ──→ Verdict
```

| Agent | Role | What it catches |
|-------|------|-----------------|
| **Writer** | Reads scenario + implementation code → structured test plan with evidence gates | **Specification bugs** — scenario expects X, code does Y |
| **Executor** | Follows plan step-by-step → collects artifacts, no judgment | **Runtime bugs** — crashes, missing files, timeouts |
| **Reviewer** | Evaluates cold evidence against assertions | **Semantic bugs** — everything ran but output is wrong |

## Quick Start

```bash
# Full pipeline on a scenario
/wicked-qe:acceptance path/to/scenario.md

# Generate test plan only (inspect before running)
/wicked-qe:acceptance scenario.md --phase write

# Run all scenarios for a plugin
/wicked-qe:acceptance wicked-mem --all
```

## Scenario Formats Supported

- **Plugin acceptance scenarios** — wicked-garden `scenarios/*.md` format
- **User stories with acceptance criteria** — Given/When/Then format
- **E2E scenarios** — wicked-scenarios CLI-based format
- **Custom acceptance criteria** — any structured test description

## Key Concepts

### Evidence-Gated Steps

Every step in the test plan requires the executor to produce specific artifacts. No evidence = no verdict (INCONCLUSIVE, not auto-PASS).

### Assertion Types

| Type | Example | Auto-evaluable |
|------|---------|----------------|
| `CONTAINS` | stdout contains "success" | Yes |
| `MATCHES` | output matches `score: \d+` | Yes |
| `EXISTS` | file at path exists | Yes |
| `JSON_PATH` | `$.status` equals "ok" | Yes |
| `HUMAN_REVIEW` | "Is output actionable?" | No — flagged for human |

### Failure Causes

| Cause | Who fixes |
|-------|-----------|
| `IMPLEMENTATION_BUG` | Developer |
| `SPECIFICATION_BUG` | Scenario author |
| `ENVIRONMENT_ISSUE` | DevOps/setup |
| `TEST_DESIGN_ISSUE` | Test writer |

## Agents

| Agent | Purpose |
|-------|---------|
| acceptance-test-writer | Transforms scenarios into evidence-gated test plans |
| acceptance-test-executor | Executes plans, collects artifacts, no judgment |
| acceptance-test-reviewer | Evaluates evidence against assertions independently |

## Detailed References

- **[Test Plan Format](refs/test-plan-format.md)** — Structure, fields, and examples for test plans
- **[Evidence Protocol](refs/evidence-protocol.md)** — How to capture, reference, and evaluate evidence

## Integration

- **wicked-crew**: Evidence-gated quality gates during delivery phases
- **wicked-scenarios**: Executor delegates E2E CLI steps to `/wicked-scenarios:run --json` for machine-readable execution artifacts. Writer understands E2E scenario format natively. Falls back to inline bash execution when scenarios plugin is not installed.
- **/wg-test**: Delegates to `/wicked-qe:acceptance` as the single acceptance pipeline. QE owns Writer/Executor/Reviewer end-to-end.
- **Any project**: Works with custom acceptance criteria, not just wicked-garden plugins
