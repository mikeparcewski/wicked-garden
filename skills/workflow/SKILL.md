---
name: workflow
description: |
  wicked-crew v6 workflow engine. The facilitator rubric in
  wicked-garden:propose-process drives project orchestration — scoring 9 risk
  factors, picking phases from the catalog, assigning rigor tier, and emitting
  a process-plan + full task chain. Phases have hard quality gates (APPROVE /
  CONDITIONAL / REJECT); CONDITIONAL auto-resolves spec gaps or escalates.

  Use when: "crew phases", "phase plan", "workflow execution", "start a project",
  "clarify outcome", "design phase", "build phase", "approve phase", "crew workflow",
  "phase progression", "QE gate", "shift-left testing", or structured delivery.
context: fork

**Plain:** wicked-crew v6 — propose-process rubric picks phases and rigor tier;
gates are hard enforcement; two interaction modes (normal / yolo).
---

# Workflow Skill (v6)

Facilitator-rubric orchestration with hard quality gates.

## Decision Engine — `wicked-garden:propose-process`

```
User project description
        │
        ▼
propose-process facilitator
  ├── Score 9 risk factors (0-3 each)
  ├── Read agents/**/*.md frontmatter → pick specialists
  ├── Pick phases from phases.json catalog
  ├── Set rigor_tier (minimal / standard / full)
  └── Emit process-plan.md + full task chain
```

All phase selection is judgment-driven by the facilitator, not rule-based.

## Interaction Modes

| Mode | How | Effect |
|------|-----|--------|
| **normal** | Default | Each phase gate requires explicit user approval before advancing |
| **yolo** | `/wicked-garden:crew:auto-approve` | Auto-advance through gates; gates still run, findings still logged |

## Rigor Tiers

| Tier | Complexity | Gates | Reviewers |
|------|-----------|-------|-----------|
| **minimal** | 0-2 | Advisory — gate findings logged but do not block | Single reviewer |
| **standard** | 3-5 | Enforced — REJECT blocks advancement | Single reviewer |
| **full** | 6-7 | Enforced — REJECT blocks; multi-reviewer | 2+ reviewers |

Security or compliance signals override to **full** regardless of complexity.

## Phase Plan

```
clarify → design → [challenge?] → [test-strategy?] → build → test → review
```

Brackets = optional phases. The facilitator picks which phases apply based on
factor readings. `phases.json` defines gate config per phase (min_gate_score,
valid_skip_reasons, depends_on).

### Phase Summary

| Phase | Goal | Key deliverable |
|-------|------|-----------------|
| **clarify** | Define success criteria | Outcome statement + success criteria |
| **design** | Architect solution | Architecture docs + approach |
| **challenge** | Adversarial stress-test | Challenge findings + revised design |
| **test-strategy** | Define test approach pre-build | Test scenarios + risk assessment |
| **build** | Implement | Working implementation |
| **test** | Verify | Test results + convergence evidence |
| **review** | Multi-perspective validation | Review findings + sign-off |

## Gate Enforcement (v2.5.0+)

Gates are hard enforcement — not advisory — at standard and full rigor.

| Verdict | Effect |
|---------|--------|
| **APPROVE** | Phase advances |
| **CONDITIONAL** | `conditions-manifest.json` written; verify before next phase |
| **REJECT** | Blocks advancement; mandatory rework |

CONDITIONAL auto-resolution (AC-4.4): spec gap conditions → fixed inline.
Intent-changing conditions → escalate to user or council.

Gate reviewer assignment happens at approve time, not at phase start. Banned
reviewer values: `just-finish-auto`, `fast-pass`, `auto-approve-*`.

Build depends on design (`depends_on: ["clarify", "design"]`). To migrate
legacy beta.3 projects: the `adopt-legacy` migration guide was removed in v9 — v6 is the baseline.

## Specialist Discovery

Crew discovers specialists by reading `agents/**/*.md` frontmatter directly at
runtime. No static `enhances` map. Fallback agents (facilitator, researcher,
implementer, reviewer) handle phases when no specialist matches.

## Convergence Tracking (build/test phases)

Artifact states: `Designed → Built → Wired → Tested → Integrated → Verified`.
The `convergence-verify` gate flips REJECT → APPROVE only when every tracked
artifact reaches `Integrated`. Stalls at threshold 3 sessions surface as findings.

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/wicked-garden:crew:start` | Begin project — invokes propose-process |
| `/wicked-garden:crew:status` | View current phase and engaged specialists |
| `/wicked-garden:crew:execute` | Run current phase |
| `/wicked-garden:crew:approve` | Advance phase after gate |
| `/wicked-garden:crew:just-finish` | Autonomous completion (yolo-equivalent) |
| `/wicked-garden:crew:gate` | Run a specific quality gate |
| `/wicked-garden:crew:evidence` | Query evidence for a task |
| `/wicked-garden:crew:auto-approve` | Switch to auto-advance mode |

## Storage

| Store | What |
|-------|------|
| Native tasks | TaskCreate/TaskUpdate with validated `metadata` (see `scripts/_event_schema.py`) |
| `wicked-garden:mem` | Cross-session learning at project completion and gate failures |
| Local JSON | DomainStore fallback; always available |

## Refs (load on demand)

- [Evidence Tracking](refs/evidence.md) — evidence tiers L1-L4, artifact naming
- [Integration Details](refs/integration.md) — mem, search, wicked-bus usage
- [Scoring Rubric](refs/scoring-rubric.md) — **HISTORICAL v5 only**; see propose-process for v6
- [Risk Dimension Signals](refs/risk-dimension-signals.md) — signal keywords per factor
