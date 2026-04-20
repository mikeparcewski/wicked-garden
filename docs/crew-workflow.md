# Crew Workflow

Crew is the orchestration engine. It analyzes what you're building, scores 9 factors, detects the project archetype, picks specialists by reading their `subagent_type` frontmatter, and runs enforced quality gates — automatically.

v6 replaced the v5 rule engine with a **facilitator skill** (`skills/propose-process/`) that makes these calls inline, per project, using the current agent roster on disk.

## How It Works

```
Your description
     |
     v
+----------------------------------------+
|  Facilitator (propose-process skill)   |
|                                        |
|  1. Score 9 factors (0-7 each)         |
|  2. Detect archetype (1 of 7)          |
|  3. Pick specialists from agents/**/   |
|  4. Select phases from phases.json     |
|  5. Set rigor tier (min/std/full)      |
|  6. Emit process-plan.md + task chain  |
+----------------------------------------+
     |
     v
Phase plan — typically: clarify -> design -> (challenge) -> test-strategy -> build -> test -> review
```

One command starts the entire process:

```bash
/wicked-garden:crew:start "Migrate auth from sessions to JWT across 3 services"
```

## The 9 Factors

The facilitator reads every crew request against nine factors. Each scores 0–7. The combination drives specialist panel, phase selection, and rigor.

| Factor | What It Measures |
|--------|-----------------|
| reversibility | How hard it is to undo |
| blast_radius | How many systems / users / services are affected |
| compliance_scope | Regulatory surface touched (SOC2, HIPAA, GDPR, PCI) |
| user_facing_impact | Direct user-visible behavior change |
| novelty | How unfamiliar the pattern is to this codebase |
| scope_effort | Raw size of the change |
| state_complexity | Data model, migrations, persistent state |
| operational_risk | Deployment, rollback, on-call burden |
| coordination_cost | Cross-team / cross-service coordination required |

No keyword table. No signal patterns. The facilitator reads the description and the codebase, assigns scores with reasoning, and commits them to `process-plan.md` so every subsequent decision is auditable.

## Archetype Detection

`scripts/crew/archetype_detect.py` classifies every project into **one of seven archetypes** before phase selection. Detection is stdlib-only heuristics over the changed-file set plus the project description. A `DOMINANCE_RATIO` of 4 means one archetype must be 4× stronger than the next — otherwise the detector falls back to `code-repo`.

Priority order (first match wins):

1. **schema-migration** — database migrations, DDL, alembic/flyway
2. **multi-repo** — spans multiple repos or submodules
3. **testing-only** — changes live entirely under test dirs
4. **config-infra** — Terraform, Kubernetes, workflow YAML, config files
5. **skill-agent-authoring** — touches `agents/` / `skills/` / `commands/`
6. **docs-only** — only markdown / docs/ changes
7. **code-repo** — default fallback

Archetype is injected into `TaskCreate` metadata at clarify time. The **phase-boundary gate adjudicator** (`agents/crew/gate-adjudicator.md`) reads it at the `testability` and `evidence-quality` gates to pick per-archetype `test_types` and `evidence_required` expectations. A docs-only project isn't asked for unit test coverage; a schema-migration is asked for dry-run + rollback evidence.

## Rigor Tiers

Instead of a complexity number, v6 commits to an explicit tier. The facilitator picks it based on the 9-factor readings.

| Tier | When | Gate Behavior |
|------|------|---------------|
| **minimal** | Low reversibility/blast + no compliance + routine patterns | Advisory gates, self-check review |
| **standard** | Default for most work | Enforced gates, single-reviewer minimum |
| **full** | High blast_radius, compliance_scope > 0, or novelty + operational_risk | Enforced gates, multi-reviewer panels, BLEND aggregation |

Security or compliance signals override the rubric: if `compliance_scope > 0`, the project is full-rigor regardless of other factors.

## Phases

Phases are defined in `.claude-plugin/phases.json` with gate config (min scores, evidence requirements, dependencies). The facilitator picks which ones apply per project.

| Phase | Purpose | When Included |
|-------|---------|---------------|
| **ideate** | Explore solution space | Ambiguity or greenfield |
| **clarify** | Define outcome + acceptance criteria + archetype | Always |
| **design** | Architecture + implementation strategy | Non-trivial state or novelty |
| **challenge** | Contrarian steelman | **Auto-inserted at complexity >= 4** |
| **test-strategy** | Plan tests before code | Non-trivial test complexity (min threshold 3) |
| **build** | Implementation | Always |
| **test** | Execute tests, collect evidence | When test-strategy ran |
| **review** | Gate review with evidence evaluation | Always |
| **operate** | Post-deploy feedback, incidents, retro | On opt-in or compliance projects |

### Phase Dependencies

```
ideate (optional)
  |
clarify (required)
  |
  +-> design (optional, depends on clarify)
  |     |
  |     +-> challenge (auto at complexity >= 4)
  |
  +-> test-strategy (optional, non-skippable at complexity >= 3)
  |
  +-> build (required, depends_on: [clarify, design])
         |
         +-> test (optional, depends on build + test-strategy)
         |
         +-> review (required, depends on build)
                |
                +-> operate (opt-in)
```

Build explicitly `depends_on: [clarify, design]` — you cannot skip design on anything non-trivial. Test-strategy has `skip_complexity_threshold: 3` — it cannot be skipped above that line.

## Challenge Gate + Contrarian Agent

At complexity ≥ 4 the facilitator auto-inserts a **challenge phase** (commit `4c011d0`). The `agents/crew/contrarian.md` agent runs a structured steelman of the alternative path — the option you didn't pick. Output goes into `phases/challenge/` as deliverables and into the review-gate evidence bundle.

The challenge gate is enforceable: if the contrarian surfaces a blocking concern the reviewer signs off on, the plan adjusts before build starts.

## Gate Enforcement

Quality gates are hard enforcement, not advisory. `.claude-plugin/gate-policy.json` codifies which reviewers run at which gate, in which dispatch mode.

| Verdict | Effect |
|---------|--------|
| **APPROVE** | Phase advances |
| **CONDITIONAL** | `conditions-manifest.json` written; conditions must be verified before next phase |
| **REJECT** | Phase blocked; triggers mandatory rework |

**Banned reviewers**: `just-finish-auto`, `fast-pass`, anything starting with `auto-approve-` — rejected by the PreToolUse validator.

**Content validation**: zero-byte deliverables are blocked. Evidence needs at least 100 bytes.

**Auto-resolution (AC-4.4)**: spec-gap conditions are fixed inline by the executor. Intent-changing conditions escalate to the user or, for full-rigor, to a council session.

### Dispatch Modes

Per-gate reviewer assignment lives in `gate-policy.json`. Each gate × rigor tier entry declares:

| Mode | Behavior |
|------|----------|
| **self-check** | Gate-evaluator agent runs deterministic checks (byte count, required deliverables) |
| **sequential** | One specialist reviewer at a time; early REJECT short-circuits |
| **parallel** | Multiple reviewers in one batch; findings merged |
| **council** | Full multi-reviewer panel with BLEND aggregation |
| **advisory** | Findings-only — never blocks |

### BLEND Multi-Reviewer Aggregation

When 2+ reviewers evaluate the same gate, scores combine as **`0.4 × min + 0.6 × avg`**. Strong dissent (low minimum) pulls the combined score down proportionally — one skeptic can hold up weak work even when the panel average would have passed.

### Blind Reviewer Context Stripping

Reviewers run with session context stripped of prior approval signals — they see deliverables and evidence, not the previous gate's verdict. Prevents "rubber stamp" bias.

### Partial-Panel Invariant

If a reviewer fails to respond in a panel, the gate stays `pending` (not silently approved). The full panel must speak before a verdict is rendered.

## Convergence Lifecycle (Build / Test Phases)

A task marked `completed` is not the same as an artifact being wired into the production path. v6 tracks every build/test artifact through a six-state machine:

```
Designed -> Built -> Wired -> Tested -> Integrated -> Verified
```

Implementers and test-designers call `scripts/crew/convergence.py record` after landing each artifact. The **`convergence-verify`** review gate refuses to flip to APPROVE until every tracked artifact has reached at least `Integrated`. Stalls at the same state for three sessions surface as findings.

Scenario: `scenarios/crew/convergence-lifecycle.md`.

## Semantic Reviewer

`agents/qe/semantic-reviewer.md` runs at the review gate for complexity ≥ 3. It extracts numbered acceptance criteria (`AC-*`, `FR-*`, `REQ-*`) from clarify-phase artifacts and emits a **Gap Report** per item with status `aligned` / `divergent` / `missing`.

Tests passing is not the same as spec intent being satisfied. The semantic reviewer closes that gap.

## Specialists

Specialists are **discovered at runtime by reading `agents/**/*.md` frontmatter**. There is no static `enhances` map. The facilitator matches factor readings to agent descriptions and `subagent_type` values.

Roles, grouped by discipline (75 agents as of v6.3.4):

| Discipline | Agents |
|-----------|--------|
| engineering (10) | senior-engineer, solution-architect, system-designer, backend-engineer, frontend-engineer, debugger, technical-writer, api-documentarian, devex-engineer, migration-engineer |
| product (11) | product-manager, requirements-analyst, ux-designer, ux-analyst, user-researcher, user-voice, market-strategist, value-strategist, a11y-expert, ui-reviewer, mockup-generator |
| platform (11) | security-engineer, sre, compliance-officer, incident-responder, infrastructure-engineer, devops-engineer, release-engineer, auditor, privacy-expert, chaos-engineer, observability-engineer |
| qe (11) | test-strategist, test-designer, test-automation-engineer, testability-reviewer, semantic-reviewer, risk-assessor, requirements-quality-analyst, code-analyzer, continuous-quality-monitor, production-quality-engineer, contract-testing-engineer |
| data (4) | data-analyst, data-engineer, data-architect, ml-engineer |
| delivery (7) | delivery-manager, stakeholder-reporter, rollout-manager, experiment-designer, risk-monitor, progress-tracker, cloud-cost-intelligence |
| agentic (5) | architect, safety-reviewer, pattern-advisor, performance-analyst, framework-researcher |
| jam (2) | brainstorm-facilitator, council |
| persona (1) | persona-agent |
| mem (3) | memory-archivist, memory-learner, memory-recaller |
| crew (10) | facilitator, phase-executor, gate-evaluator, independent-reviewer, contrarian, gate-adjudicator, qe-orchestrator, implementer, researcher, reviewer |

### Fallback Agents

When a matched specialist isn't available on disk, four fallback agents cover the gap:

| Need | Fallback |
|------|----------|
| Facilitation, brainstorming, product | `facilitator` |
| Engineering, platform, data, agentic | `implementer` |
| QE, review | `reviewer` |
| Research, discovery | `researcher` |

## Checkpoints + Re-evaluation

At clarify / design / build, the facilitator re-runs in `re-evaluate` mode. Findings are appended — never silently overwriting — to:

- `phases/{phase}/reeval-log.jsonl` (schema `1.1.0`, archetype-aware)
- `phases/{phase}/amendments.jsonl` (append-only per-gate)
- `phases/{phase}/reeval-start.json` (phase-entry snapshot)
- `phases/{phase}/process-plan.addendum.jsonl` (plan mutations)

Phases can be **added** mid-flight (e.g., test phase injected when build discovers migration work) but are **never silently removed**. Re-tier UP is automatic; re-tier DOWN requires a CONDITIONAL and manifest.

## Interaction Modes

### Normal

Default. User is prompted at phase boundaries. Approval is explicit.

### Yolo (`crew:yolo` / `crew:auto-approve`)

Grants APPROVE-verdict auto-advance for the project. Guardrails (commit `c883271`):

- **Standard rigor**: simple grant with justification
- **Full rigor**: rejected unless the justification meets length + sentinel requirements — `--override-gate` must also be supplied on CONDITIONAL
- **Cooldown**: re-grant after revoke blocked for a cooldown window
- Pre-flip monitoring: T>7 silent, 1≤T≤7 emits a `PreFlipNotice WARN`, T=0 flips to StrictMode

`crew:yolo status` is read-only.

### Just-Finish

Maximum-autonomy execution of all remaining phases with the same guardrails as yolo at full rigor.

```bash
/wicked-garden:crew:just-finish
```

## Native Task Integration

Phase work uses Claude Code's native `TaskCreate` / `TaskUpdate` with a structured metadata envelope (`scripts/_event_schema.py`):

- **`chain_id`** — dotted causality: `{project}.root` → `{project}.{phase}` → `{project}.{phase}.{gate}`
- **`event_type`** — `task` | `coding-task` | `gate-finding` | `phase-transition` | `procedure-trigger` | `subtask`
- **`source_agent`** — authoring agent (banned values rejected)
- **`phase`** — must match a key in `phases.json`
- **`archetype`** — optional, set at clarify time

The `PreToolUse` validator in `hooks/scripts/pre_tool.py` enforces the envelope. `WG_TASK_METADATA=strict` denies on violation; `warn` (default) emits a deprecation `systemMessage`.

The `SubagentStart` hook reads the most-recently-modified in-progress task and injects the procedure bundle keyed on `metadata.event_type`:

- `coding-task` → R1–R6 bulletproof coding standards
- `gate-finding` → Gate Finding Protocol
- Other event types → matching per-role procedures

## Dispatch Log + HMAC Audit

Every specialist dispatch appends an HMAC-signed entry to `phases/{phase}/dispatch-log.jsonl`. On gate evaluation:

- **Matched entry** → pass
- **Orphan gate-result** (result without a matching dispatch) → CONDITIONAL
- Log rotates at the configured size threshold

Ops bundle scenario: `scenarios/crew/dispatch-log-hmac-orphan-detection-rotation.md`.

## Swarm Detection

`scripts/crew/swarm_trigger.py::detect_swarm_trigger()` watches for 3+ BLOCK/REJECT findings across gates and recommends a **Quality Coalition** — a coordinated multi-specialist response to a quality crisis. Surfaced by `/wicked-garden:crew:swarm`.

## Cross-Phase Intelligence

Every artifact links to upstream and downstream counterparts. Covered in [Cross-Phase Intelligence](cross-phase-intelligence.md):

- **Traceability links** — `traceability.py`, BFS forward/reverse trace
- **Artifact state machine** — 6-state lifecycle enforced at gates
- **Verification protocol** — 6 automated checks at review
- **Impact analysis** — change propagation across phases
- **Knowledge graph** — typed entity + relationship layer
- **Convergence lifecycle** — Designed → Built → Wired → Tested → Integrated → Verified
- **Archetype-aware scoring** — phase-boundary QE evaluator uses archetype for test_types / evidence_required

## Project Management

Each crew project is isolated via `project_registry.py`:

- `crew:start` registers the project
- `get_project_filter()` scopes all cross-domain queries (memories, artifacts, evidence) to the active project
- Multiple concurrent projects are supported
- `crew:status`, `crew:archive`, `crew:explain` (plain-language translation) manage lifecycle

## Memory Integration

Crew stores significant decisions, patterns, and gate failures in `wicked-garden:mem` automatically. Phase-aware recall (`mem/phase_scoring.py`) weights memories by affinity to the current phase — architecture decisions surface during design, test patterns during test-strategy, deployment notes during build. v6 adds **persistent process memory** + **kaizen backlog** (commit `7658fb9`): retro phase auto-populates a facilitator-context digest so future projects inherit learned trade-offs.
