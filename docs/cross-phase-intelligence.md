# Cross-Phase Intelligence

v3.4.0 added 9 modules across 5 domains that make crew phases aware of each other. Requirements trace forward to tests. Artifacts enforce lifecycle transitions. Verification checks run automatically at gates. Impact analysis reveals what breaks when something changes.

## Overview

Before v3.4.0, crew phases were isolated -- clarify produced requirements, design produced architecture docs, build produced code, and each phase started fresh with whatever the previous phase left behind. Cross-phase intelligence connects them:

- A requirement created in clarify is **traced** to a design decision, which is traced to code, which is traced to a test
- Artifacts move through enforced **lifecycle states** (DRAFT, IN_REVIEW, APPROVED, IMPLEMENTED, VERIFIED, CLOSED)
- Review gates run **6 automated checks** against real evidence before allowing phase advancement
- Changing a requirement triggers **impact analysis** showing every downstream artifact affected
- Memory **recall prioritizes context** relevant to the current phase
- Council **decisions preserve dissent** so future phases know what was contested

## Traceability Links

`scripts/crew/traceability.py` -- Cross-phase traceability links with forward/reverse graph traversal.

### Link Types

| Link Type | Meaning | Example |
|-----------|---------|---------|
| `TRACES_TO` | Requirement traces to design | req-001 -> design-auth |
| `IMPLEMENTED_BY` | Design implemented by code | design-auth -> src/auth.py |
| `TESTED_BY` | Requirement or code tested by scenario | req-001 -> test-oauth-flow |
| `VERIFIES` | Test result verifies a requirement | result-001 -> req-001 |
| `SATISFIES` | Evidence satisfies a requirement | evidence-001 -> req-001 |

### Forward and Reverse Trace

Forward trace walks from a source artifact downstream (requirement -> design -> code -> test -> evidence). Reverse trace walks upstream from any artifact back to its originating requirements. Both use BFS traversal.

```bash
# Create a traceability link
traceability.py create \
  --source-id req-001 --source-type requirement \
  --target-id design-auth --target-type design \
  --link-type TRACES_TO --project my-project --created-by clarify

# Walk forward from a requirement to see everything it traces to
traceability.py forward --source-id req-001 --project my-project

# Walk backward from a test to find which requirements it covers
traceability.py reverse --target-id test-oauth-flow --project my-project

# List all links for a project, optionally filtered
traceability.py list --project my-project --link-type TRACES_TO
```

### Coverage Reports

Coverage reports find all requirements and check whether each has a complete forward chain reaching at least one coverage endpoint (`test_scenario` or `evidence`).

```bash
traceability.py coverage --project my-project
```

Output includes `total_requirements`, `covered` (with endpoint IDs), `gaps` (with reached types), and `coverage_pct`.

### Cleanup

```bash
# Delete all links for a source artifact
traceability.py delete --project my-project --source-id req-001
```

## Artifact State Machine

`scripts/crew/artifact_state.py` -- Enforced lifecycle transitions for crew deliverables.

### States and Transitions

```
DRAFT -> IN_REVIEW -> APPROVED -> IMPLEMENTED -> VERIFIED -> CLOSED
                  \                    |
                   <--- (reject) ------+
```

6 states: `DRAFT`, `IN_REVIEW`, `APPROVED`, `IMPLEMENTED`, `VERIFIED`, `CLOSED`.

Invalid transitions raise `ValueError`. For example, you cannot go directly from `DRAFT` to `APPROVED` -- it must pass through `IN_REVIEW` first. `IN_REVIEW` can transition back to `DRAFT` (rejection) or forward to `APPROVED`. `IMPLEMENTED` can go back to `IN_REVIEW` for re-review.

### Artifact Types

`requirements`, `design`, `test-strategy`, `evidence`, `implementation`, `report`, `other`

### CLI Usage

```bash
# Register a new artifact (starts in DRAFT)
artifact_state.py register --name architecture.md --type design --project my-project --phase design

# Transition to a new state
artifact_state.py transition --id <artifact-id> --to IN_REVIEW --by design-phase
artifact_state.py transition --id <artifact-id> --to APPROVED --by gate-check

# Check if an artifact is in the required state
artifact_state.py check --id <artifact-id> --required-state APPROVED

# Bulk check: all artifacts for a phase must be APPROVED
artifact_state.py bulk-check --project my-project --phase design --required-state APPROVED

# List artifacts with filters
artifact_state.py list --project my-project --phase design --state APPROVED
```

All commands support `--json` for machine-readable output.

### Gate Integration

Three helper functions connect the state machine to crew gate decisions:

- `on_gate_approve(id, by=)` -- Transitions from IN_REVIEW to APPROVED
- `on_gate_reject(id, by=)` -- Transitions from IN_REVIEW back to DRAFT
- `on_gate_conditional(id, by=)` -- Keeps IN_REVIEW, logs a conditional event to state history

## Verification Protocol

`scripts/crew/verification_protocol.py` -- 6 automated evidence-based checks for review gates.

### The 6 Checks

| Check | What It Does |
|-------|-------------|
| `acceptance_criteria` | Cross-references AC IDs from clarify/test-strategy against deliverables |
| `test_suite` | Runs the project test command (npm test, pytest, make test) and checks exit code |
| `debug_artifacts` | Scans changed files for console.log, debugger, pdb.set_trace, TODO, FIXME |
| `code_quality` | Runs the project linter (ruff, flake8, eslint, npm lint) |
| `documentation` | Checks that public functions have docstrings/JSDoc |
| `traceability` | Walks requirement -> design -> code -> test chains for completeness |

Each check produces a result with status (`PASS`, `FAIL`, or `SKIP`), human-readable evidence, and a details dict. `SKIP` means the check could not run (e.g., no test runner detected) -- not a failure.

### Verdict Logic

The overall verdict is `FAIL` if any check returns `FAIL`. Otherwise it is `PASS`. Skipped checks do not affect the verdict.

### CLI Usage

```bash
# Run all 6 checks
verification_protocol.py run --project my-project --phases-dir ./phases

# Run a single check
verification_protocol.py run --project my-project --phases-dir ./phases --check debug_artifacts

# Provide explicit file list instead of git diff
verification_protocol.py run --project my-project --phases-dir ./phases --files src/a.py src/b.ts
```

JSON report goes to stdout. Human-readable summary goes to stderr. Exit code is 0 for PASS, 1 for FAIL.

## Project Isolation

`scripts/crew/project_registry.py` -- Formalized multi-project isolation for parallel crew projects.

### The Problem

Without isolation, running two crew projects in the same workspace causes state collisions. Project registry provides workspace-scoped project records and a `get_project_filter()` abstraction that other domains use to scope queries.

### Core Pattern

```python
from project_registry import get_project_filter

# Returns {"project_id": "<uuid>"} for the active project, or {} if none
pf = get_project_filter()

# Spread into any domain query to scope it
memories = mem_store.list("memories", **pf)
links = traceability.get_links(**pf)
```

### CLI Usage

```bash
# Create a project
project_registry.py create --name "auth-rewrite"

# List projects (current workspace)
project_registry.py list --active

# Switch active project
project_registry.py switch --id <project-id>

# Get the active project
project_registry.py get-active

# Archive a completed project
project_registry.py archive --id <project-id>

# Output project filter JSON (for piping to other tools)
project_registry.py filter
```

### Workspace Resolution

Workspace defaults to the `CLAUDE_PROJECT_NAME` environment variable, falling back to the current directory name. Each workspace tracks its own active project independently.

## Impact Analysis

`scripts/crew/impact_analyzer.py` -- Analyzes downstream impact of changing an artifact across crew phases.

### Three Layers

1. **Artifact traceability** -- Walks forward and reverse trace links via `traceability.py`. Direct impacts (1-hop) are separated from transitive impacts (2+ hops). The `depth` parameter limits how far to follow.
2. **Knowledge graph** -- Queries `knowledge_graph.py` for related entities not captured by explicit traceability links. Entities connected directly to the source are added to direct impacts; others become transitive.
3. **Phase impact** -- Extracts affected phases from all impacted artifacts (e.g., changing a requirement might affect clarify, design, build, and test phases).

### Risk Classification

| Total Affected | Risk Level |
|---------------|------------|
| 0 | none |
| 1-2 | low |
| 3-5 | medium |
| 6+ | high |

### CLI Usage

```bash
# Analyze impact of changing a requirement
impact_analyzer.py analyze --source-id req-123 --project my-project

# Limit knowledge graph traversal depth
impact_analyzer.py analyze --source-id req-123 --project my-project --depth 2

# Specify artifact type explicitly
impact_analyzer.py analyze --source-id design-456 --type design --project my-project
```

Output is a JSON report with `source`, `impact.direct`, `impact.transitive`, and `risk_summary` (counts, affected phases, risk level).

## Knowledge Graph

`scripts/smaht/knowledge_graph.py` -- Typed entity and relationship layer over SQLite.

### Entity Types (8)

`requirement`, `acceptance_criteria`, `design_artifact`, `task`, `test_scenario`, `evidence`, `decision`, `incident`

### Relationship Types (7)

`TRACES_TO`, `IMPLEMENTED_BY`, `TESTED_BY`, `VERIFIES`, `DECIDED_BY`, `BLOCKS`, `SUPERSEDES`

### Subgraph Traversal

`get_subgraph(entity_id, depth=2)` performs BFS from a starting entity, collecting all reachable entities and relationships within the specified hop count. Returns `{"entities": [...], "relationships": [...]}`.

### CLI Usage

```bash
# Create an entity
knowledge_graph.py create-entity --type requirement --name "Auth must use OAuth2" --phase clarify --project P1

# Create a relationship
knowledge_graph.py create-rel --source <entity-id-1> --target <entity-id-2> --type TRACES_TO --by clarify

# Get related entities (forward, reverse, or both)
knowledge_graph.py related --id <entity-id> --direction forward

# Extract a subgraph
knowledge_graph.py subgraph --id <entity-id> --depth 3

# List entities with filters
knowledge_graph.py list-entities --type requirement --project P1

# View statistics
knowledge_graph.py stats
```

## Lifecycle Scoring

`scripts/search/lifecycle_scoring.py` -- 5 composable scorers for search and memory results.

### Scorers

| Scorer | What It Does | Default |
|--------|-------------|---------|
| `phase_weighted` | Boosts items matching the active crew phase (e.g., requirements get 1.4x during clarify, designs get 1.5x during build) | Yes |
| `recency_decay` | Exponential decay by age in days: `e^(-rate * days)`, default rate 0.01 | Yes |
| `traceability_boost` | Boosts items with traceability links: 1.3x for 1-2 links, 1.5x for 3+ | Yes |
| `gate_status` | Multiplier by artifact state: VERIFIED 1.4x, APPROVED 1.3x, DRAFT 0.7x | Yes |
| `reciprocal_rank_fusion` | Fuses multiple independent rankings via RRF formula: `1/(k + rank)` | No (opt-in) |

### Pipeline Composition

```bash
# Default pipeline (4 scorers)
lifecycle_scoring.py score --phase build < items.json

# Custom scorer selection
lifecycle_scoring.py score --phase test --scorers phase_weighted,gate_status < items.json

# Include RRF for multi-ranker fusion
lifecycle_scoring.py score --phase build --scorers phase_weighted,recency_decay,rrf < items.json

# Custom parameters
lifecycle_scoring.py score --phase build --decay-rate 0.05 --rrf-k 100 < items.json
```

Each output item includes `_score` (final composite) and `_score_breakdown` (per-scorer multipliers).

### Python API

```python
from lifecycle_scoring import score_pipeline

results = score_pipeline(
    items=[{"id": "req-001", "type": "requirement", "created_at": "2026-03-01T00:00:00Z"}],
    context={"phase": "build"},
    scorers=["phase_weighted", "recency_decay"],
)
```

## Phase-Aware Memory

`scripts/mem/phase_scoring.py` -- Phase affinity matrix for memory recall.

### How It Works

When memories are recalled during a crew phase, each memory's creation phase is compared against the active phase using an affinity matrix. Memories from related phases score higher.

### Affinity Levels

| Level | Boost | Example |
|-------|-------|---------|
| High | 1.5x | During `build`, memories from `design` and `clarify` |
| Medium | 1.0x | During `build`, memories from `test-strategy` |
| Low | 0.7x | During `build`, memories from `ideate` |

When either phase is `None`, the boost is 1.0 (backward compatible -- no penalty for legacy memories without phase tags).

### CLI Usage

```bash
# Score memories by phase affinity (reads JSON array from stdin)
phase_scoring.py score --phase build < memories.json

# Filter to memories from a specific phase
phase_scoring.py filter --phase design < memories.json

# Detect the active crew phase
phase_scoring.py detect-phase

# Get the boost for a specific phase pair
phase_scoring.py boost --memory-phase design --active-phase build
```

### Auto-Detection

`detect_active_phase()` checks the `WICKED_CREW_PHASE` environment variable first, then falls back to reading the active project's current phase via `crew.py`.

## Council Consensus

`scripts/jam/consensus.py` -- Structured consensus scoring, dissent tracking, and synthesis for jam council sessions.

### 3-Stage Protocol

**Stage 1: Independent Proposals** -- Each participant submits:
- `proposal`: Their recommendation
- `rationale`: Why they recommend it
- `confidence`: 0.0 to 1.0
- `concerns`: List of potential issues

**Stage 2: Cross-Review** -- Each participant reviews others' proposals:
- `agreements`: Points they agree with
- `disagreements`: Points they disagree with, plus counter-rationale
- `questions`: Unresolved questions

**Stage 3: Synthesis** -- The protocol automatically:
- Clusters similar points across proposals using word-overlap similarity (Jaccard > 0.35)
- Identifies consensus points (agreement >= 60% of participants) and divergent points (< 40%)
- Extracts dissenting views classified by strength (strong/moderate/mild)
- Produces a decision summary from the top consensus points

### Dissent Classification

- **Strong**: Raised by 2+ personas, or has detailed counter-rationale (>50 characters)
- **Moderate**: Raised by 1 persona with rationale
- **Mild**: Unresolved question without strong objection

### CLI Usage

```bash
# Full 3-stage synthesis
consensus.py synthesize --proposals proposals.json --reviews reviews.json --question "Should we use microservices?"

# Score consensus from proposals only (stage 1)
consensus.py score --proposals proposals.json

# Format results as markdown (with dissent shown)
consensus.py format --result result.json --show-dissent
```

### Memory Integration

`format_for_memory()` converts a `ConsensusResult` into a dict ready for `mem:store`:

```python
from consensus import format_for_memory
memory_record = format_for_memory(result)
# Returns: {"content": "...", "type": "decision", "metadata": {"confidence": 0.85, "dissent_count": 2, ...}}
```

Strong dissents are preserved in metadata so future phases know what was contested.

## How They Work Together

```
                    Project Registry
                    (project isolation)
                          |
                    get_project_filter()
                          |
    +--------+--------+---+---+--------+--------+
    |        |        |       |        |        |
 Clarify  Design   Build   Test    Review   Deliver
    |        |        |       |        |        |
    +--------+--------+---+---+--------+--------+
                          |
                  Traceability Links
              (forward/reverse BFS trace)
                          |
              +-----+-----+-----+
              |           |           |
        Artifact     Knowledge    Lifecycle
      State Machine    Graph       Scoring
     (enforce gates) (entity+rel) (rank results)
              |           |           |
              +-----+-----+-----+
                          |
                  Impact Analyzer
              (3-layer risk assessment)
                          |
              +-----+-----+
              |           |
        Verification   Phase-Aware    Council
         Protocol       Memory       Consensus
       (6 checks)    (affinity)    (3-stage + dissent)
```

**Data flow example**: A requirement created in clarify gets a traceability link to a design artifact. The design artifact is registered in the state machine as DRAFT, then transitions to IN_REVIEW and APPROVED via gate checks. During build, lifecycle scoring boosts the requirement and design when they appear in search results (phase affinity). When the requirement changes, impact analysis walks the trace links and knowledge graph to identify every affected artifact. At the review gate, the verification protocol runs 6 checks including traceability coverage. Phase-aware memory ensures that context from clarify and design ranks highest during build. If a council session decided the architecture approach, the consensus result preserves dissenting views so the build phase knows what trade-offs were made.
