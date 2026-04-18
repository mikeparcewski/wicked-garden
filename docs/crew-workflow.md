# Crew Workflow

Crew is the orchestration engine. It analyzes what you're building, detects signals, selects phases, and routes to the right specialists — automatically.

## How It Works

```
Your description
     |
     v
+--------------------------+
|   Smart Decisioning      |
|                          |
|  1. Detect signals       |     security, architecture, data, ux,
|  2. Score complexity     |     performance, compliance, ambiguity...
|  3. Select specialists   |
|  4. Choose phases        |
+--------------------------+
     |
     v
Phase Plan: clarify -> design -> test-strategy -> build -> test -> review
```

One command starts the entire process:

```bash
/wicked-garden:crew:start "Migrate auth from sessions to JWT across 3 services"
```

## Signal Detection

Every project description is analyzed for **signals** — patterns that indicate what kind of expertise is needed:

| Signal | Triggers On | Specialists Engaged |
|--------|------------|-------------------|
| security | auth, encrypt, credentials, JWT, OAuth | platform, qe |
| architecture | system design, component, API contract | engineering, agentic |
| performance | latency, throughput, bottleneck, optimize | engineering, platform |
| data | analytics, pipeline, ETL, database, SQL | data |
| ux | user experience, usability, user flow | product |
| compliance | audit, regulatory, GDPR, HIPAA, SOC2 | platform |
| ambiguity | vague descriptions, multiple interpretations | jam |
| complexity | large scope, cross-cutting, coordination | delivery, engineering |
| content | messaging, copy, creative, branding | jam, product |
| quality | testing, coverage, reliability | qe |

Signals are detected through keyword patterns with confidence scoring. Multiple signals can fire simultaneously — a description mentioning "OAuth migration with compliance requirements" triggers both security and compliance.

## Complexity Scoring

Complexity is scored 0-7 across multiple dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| Impact | How much production behavior changes |
| Reversibility | How hard to undo |
| Novelty | How new/unfamiliar the pattern is |
| Test complexity | How complex the test strategy needs to be |
| Coordination cost | Cross-domain/cross-team coordination |
| Operational | Deployment/migration/rollback complexity |
| Documentation | How much documentation needs updating |

The score drives phase selection and rigor:

```
Score 0-2: Quick pass
  -> auto-finish mode, build + review only
  -> no user prompts needed

Score 3-4: Standard
  -> clarify + test-strategy + build + test + review
  -> design phase if architecture signals detected

Score 5-7: Full pipeline
  -> all phases, all matched specialists
  -> ideate phase for ambiguous problems
  -> delivery specialist for coordination
```

## Phases

Seven phases available, selected dynamically based on signals and complexity:

| Phase | Purpose | Always Included? |
|-------|---------|-----------------|
| **ideate** | Brainstorm and explore solution space | No (ambiguity/UX signals) |
| **clarify** | Define outcome, acceptance criteria | Yes |
| **design** | Architecture and implementation strategy | No (complexity >= 3) |
| **test-strategy** | Test planning before implementation | No (complexity >= 2) |
| **build** | Implementation with task tracking | Yes |
| **test** | Execute tests, collect evidence | No (complexity >= 2) |
| **review** | Final review with evidence evaluation | Yes |

### Phase Dependencies

```
ideate (optional)
  |
clarify (required)
  |
  +-> design (optional, depends on clarify)
  |     |
  +-> test-strategy (optional, depends on clarify)
  |     |
  +-----+-> build (required, depends on clarify)
              |
              +-> test (optional, depends on build + test-strategy)
              |
              +-> review (required, depends on build)
```

### Within Phases

As phases execute, the crew engine tracks work at a granular level:

- **Traceability Links**: `traceability.py` automatically creates cross-phase links between artifacts, decisions, and deliverables. A requirement defined in clarify is linked to the design that addresses it, the code that implements it, and the test that validates it. BFS traversal finds transitive dependencies, and coverage reports identify orphaned artifacts with no upstream or downstream connections.
- **Artifact Lifecycle**: Every artifact (spec, design doc, code deliverable, test plan) is tracked through a 6-state lifecycle managed by `artifact_state.py`: DRAFT, IN_REVIEW, APPROVED, IMPLEMENTED, VERIFIED, CLOSED. State transitions are enforced — you cannot build from a DRAFT design or close without verification.
- **Verification Protocol**: At each gate, `verification_protocol.py` runs 6-point checks: completeness (all required deliverables present), consistency (no contradictions across artifacts), traceability (links exist to upstream requirements), quality metrics (meets minimum gate score), dependency satisfaction (all depends_on phases completed), and evidence validation (evidence meets minimum byte threshold).

### Checkpoints

At three checkpoints (clarify, design, build), the system re-analyzes signals and can inject new phases mid-flight:

- Design phase reveals security concerns not in the original description? Signal re-analysis detects the new security pattern and pulls in the platform specialist.
- Build phase discovers data migration needs? Data specialist and test phase get injected into the remaining plan.
- Complexity changes based on what's found? Phase plan adjusts — phases can be added but never silently removed.
- Checkpoint re-analysis uses the same `smart_decisioning.py` pipeline as initial analysis, so specialist matching and complexity scoring are consistent.

## Specialists

Eight specialist roles that crew routes to based on signals:

| Specialist | Role | Engaged By |
|-----------|------|-----------|
| engineering | Implementation, architecture, code quality, code transformations | performance, architecture, complexity |
| platform | Security, infrastructure, compliance, plugin diagnostics | security, compliance, infrastructure |
| product | Requirements, UX, customer voice, design review, mockups | product, ux, strategy |
| qe | Testing, quality gates, risk, E2E scenarios | quality, non-trivial work (complexity >= 2) |
| data | Data pipelines, analytics, ML | data signals |
| delivery | Project coordination, cost, rollout | complexity >= 5 |
| agentic | Agent architecture, safety, patterns | architecture signals |
| jam | Brainstorming, diverse perspectives | ambiguity, architecture, complexity >= 4 |

When a recommended specialist isn't available, fallback agents cover the gap:

| Specialist | Fallback Agent |
|-----------|---------------|
| jam | facilitator |
| qe | reviewer |
| product | facilitator |
| engineering | implementer |
| platform | implementer |
| data | researcher |
| agentic | reviewer |

## Auto-Finish Mode

For low-complexity work (score 0-2), crew automatically applies a quick phase plan (build + review) and chains into just-finish mode — no user interaction required.

```bash
# This auto-finishes for simple tasks:
/wicked-garden:crew:start "Fix the typo in the login button"

# To override:
/wicked-garden:crew:start --no-auto-finish "Fix the typo in the login button"
```

## Quick Mode

Skip clarify, design, and test phases — go straight to build + review:

```bash
/wicked-garden:crew:start --quick "Add error handling to the API endpoint"
```

## Just-Finish Mode

Maximum autonomy — execute all remaining phases without stopping for approval:

```bash
/wicked-garden:crew:just-finish
```

## Native Task Integration

Phase work uses Claude Code's native `TaskCreate` / `TaskUpdate` with enriched `metadata` (`chain_id`, `event_type`, `source_agent`, `phase`). The PreToolUse validator in `hooks/scripts/pre_tool.py` enforces the envelope per `scripts/_event_schema.py`, and SubagentStart reads `metadata.event_type` from `${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json` to inject the matching procedure bundle (R1-R6 for coding-tasks, Gate Finding Protocol for gate-findings).

## Cross-Phase Intelligence

v3.4 introduces cross-phase intelligence — the ability for crew to understand relationships between artifacts, decisions, and deliverables across the entire workflow lifecycle.

- **Traceability Graph**: Every artifact is linked to its upstream requirements and downstream implementations. `traceability.py` provides BFS traversal to answer "what depends on this?" and coverage reports to find gaps.
- **Impact Analysis**: When an artifact changes mid-workflow, `impact_analyzer.py` identifies all downstream phases and artifacts that may be affected, preventing silent breakage.
- **Lifecycle Scoring**: Search results within crew context are ranked using `lifecycle_scoring.py` — phase-weighted, recency-aware, and traceability-boosted so the most relevant artifacts surface first.

For details on the traceability model and artifact states, see the scripts in `scripts/crew/`.

## Project Management

Each crew project is isolated via `project_registry.py`:

- **Project Registration**: Every `crew:start` registers a project with a unique ID, description, and metadata.
- **Isolation**: `get_project_filter()` returns a filter function that scopes all queries (memories, artifacts, evidence) to the active project. This prevents cross-project data leakage when multiple crew projects exist.
- **Multi-Project Support**: You can have multiple active projects. `crew:status` shows the current one; `crew:archive` manages lifecycle.

## Memory Integration

Crew stores significant decisions and patterns in memory automatically. When you start a new project, relevant memories from past projects surface during the clarify phase. v3.4's phase-aware recall (`mem/phase_scoring.py`) weights memories by affinity to the current crew phase — architecture decisions rank higher during design, test patterns rank higher during test-strategy.
