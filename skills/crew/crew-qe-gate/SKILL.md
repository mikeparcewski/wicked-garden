---
name: crew-qe-gate
description: |
  Crew-integrated quality gates for phase transitions: value gate, strategy gate, execution gate.
  Runs gate analysis at crew checkpoints (post-clarify, post-design, post-build) to validate
  readiness before advancing. Quality checkpoint within the wicked-crew workflow.

  Use when: "quality gate", "value gate", "strategy gate", "execution gate",
  "gate analysis", "quality checkpoint", "phase gate", "crew quality gate",
  "ready to advance", "should we build this", "does it work", "crew QE checkpoint"
---

# Crew QE Gate Skill

Quality gates for crew phase transitions — validate readiness before advancing.

## Core Concept

Quality is how we deliver fast. Don't wait for QE phase—analyze early.

## Three Gates

| Gate | When | Question |
|------|------|----------|
| **Value** | post-clarify | Should we build this? |
| **Strategy** | post-design | Can we build it well? |
| **Execution** | post-build | Does it work? |

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-testing:review` | Run QE gate analysis |
| `/wicked-testing:review --gate value` | Value Gate |
| `/wicked-testing:review --gate strategy` | Strategy Gate (default) |
| `/wicked-testing:review --gate execution` | Execution Gate |

## Usage

```bash
# Default Strategy Gate
/wicked-testing:review src/auth

# Value Gate on requirements
/wicked-testing:review outcome.md --gate value

# Execution Gate after build
/wicked-testing:review src/auth --gate execution

# Quick triage
/wicked-testing:review --rigor quick
```

## Output

Analysis produces:
- **Decision**: APPROVE / CONDITIONAL / REJECT
- **Evidence**: Qualitative + quantitative findings
- **Tasks**: Evidence attached to the active task via TaskUpdate description append

## Integration

Works with:
- **wicked-crew**: Auto-suggested after phases
- **Native tasks**: Stores evidence via TaskUpdate description appends on the active gate task (`metadata.event_type="gate-finding"`)
- **product**: Deep review delegation
- **wicked-brain:memory**: Cross-session learning
