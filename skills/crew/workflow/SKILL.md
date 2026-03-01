---
name: workflow
description: |
  Core wicked-crew v3 workflow with capability-based orchestration.
  Smart decisioning analyzes input to determine specialists needed.
  Built-in fallbacks when specialists unavailable.

  Use when the user mentions "start a project", "clarify outcome", "design phase",
  "QE gate", "shift-left testing", "just finish", "approve phase", or needs structured
  software delivery workflow guidance.
---

# Workflow Skill (v3)

Capability-based orchestration with smart specialist engagement.

## v3 Architecture

```
User Input → Smart Decisioning → Specialist Discovery → Engagement
                  │                     │
                  ├── Signal Detection  ├── Available specialists
                  ├── Complexity Score  ├── Personas
                  └── Ambiguity Check   └── Fallback agents
```

## Phase Progression

```
clarify → design → qe → build → review
```

Each phase has: Clear deliverables, specialist engagement based on signals, approval gate.

## Smart Decisioning

### Signal Categories

| Signal | Keywords | Specialists |
|--------|----------|-------------|
| Security | auth, encrypt, token, jwt | devsecops, compliance |
| Performance | scale, optimize, cache | appeng, qe |
| Product | user, feature, story | product, strategy |
| Compliance | SOC2, HIPAA, audit | compliance |
| Ambiguity | maybe, should we, options | jam |
| Complexity | integration, migrate, refactor | pmo, arch |

### Complexity Scoring (0-7)

- 0-2: Simple → Built-in agents only
- 3-4: Moderate → Core specialists
- 5-7: Complex → All relevant + PMO

## Specialist Engagement

### Discovery

Crew discovers specialists via `specialist.json` in each plugin.

### Fallback Agents

| Specialist | Fallback |
|------------|----------|
| jam | facilitator |
| qe, strategy | reviewer |
| arch | researcher |
| appeng, devsecops | implementer |

## Phase Details

### Clarify
**Goal**: Define success criteria
**Deliverables**: Outcome statement, success criteria, scope boundaries
**Specialists**: jam (if ambiguous), product

### Design
**Goal**: Architect the solution
**Deliverables**: Architecture docs, pattern identification, technical approach
**Specialists**: strategy, arch, appeng

### QE (Quality Engineering)
**Goal**: Define test strategy before building
**Deliverables**: Test scenarios, risk assessment, edge cases
**Specialists**: qe, devsecops (if security signals)

### Build
**Goal**: Implement the solution
**Deliverables**: Working implementation, progress tracking, tests passing
**Specialists**: appeng, devsecops (if infra)

### Review
**Goal**: Multi-perspective validation
**Deliverables**: Review findings, recommendations, sign-off
**Specialists**: strategy, qe, compliance (if regulated)

## Project Lifecycle

Projects can be archived when complete or paused:

```bash
python3 scripts/cp.py crew projects archive <name>      # Sets archived=true
python3 scripts/cp.py crew projects unarchive <name>    # Reactivates
python3 scripts/cp.py crew projects list                 # Excludes archived by default
python3 scripts/cp.py crew projects list --include_archived true
```

Phase operations are blocked on archived projects.

## Commands Reference

| Command | Purpose |
|---------|---------|
| `/wicked-garden:crew:start` | Begin project with smart decisioning |
| `/wicked-garden:crew:status` | View current state and engaged specialists |
| `/wicked-garden:crew:execute` | Run current phase with specialists |
| `/wicked-garden:crew:approve` | Approve and advance phase |
| `/wicked-garden:crew:just-finish` | Autonomous completion |
| `/wicked-garden:crew:gate` | Run QE gate (value/strategy/execution) |
| `/wicked-garden:crew:evidence` | Query evidence for a task |

## Event Flow

### Project Start
```
crew:project:started:success
crew:specialist:engaged:success
crew:specialist:unavailable:warning (with fallback)
```

### Phase Transitions
```
crew:phase:started:success
crew:phase:completed:success
crew:phase:approved:success
```

## Utility Integration

| Plugin | Enhancement | Fallback |
|--------|-------------|----------|
| wicked-kanban | Persistent task board | TodoWrite |
| wicked-mem | Cross-session learning | Project files |

See [Integration Details](refs/integration.md) for usage patterns.

## Evidence Tracking

Gate decisions and artifacts are tracked as evidence. See [EVIDENCE.md](../../docs/EVIDENCE.md) for:
- Evidence tiers (L1-L4)
- Artifact naming conventions
- Automatic vs manual evidence collection

## Configuration

Customize in `~/.something-wicked/wicked-garden/local/wicked-crew/config.yaml`:

```yaml
defaults:
  always_engage: [qe]      # Always use QE specialist
  complexity_threshold: 4  # Lower = more specialists
```
