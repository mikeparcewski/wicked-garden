---
name: crew-qe-gate
description: |
  Crew-integrated quality gates for phase transitions.
  Runs QE checks at crew checkpoints (clarify, design, build) to validate
  readiness before advancing. Works within wicked-crew workflow context.

  Use when: "crew quality gate", "phase gate check", "ready to advance",
  "should we build this", "does it work", "crew QE checkpoint"
---

# QE Strategy Skill

Shift-left quality engineering: embed quality thinking throughout delivery.

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
| `/wicked-garden:qe:analyze` | Run QE gate analysis |
| `/wicked-garden:qe:analyze --gate value` | Value Gate |
| `/wicked-garden:qe:analyze --gate strategy` | Strategy Gate (default) |
| `/wicked-garden:qe:analyze --gate execution` | Execution Gate |

## Usage

```bash
# Default Strategy Gate
/wicked-garden:qe:analyze src/auth

# Value Gate on requirements
/wicked-garden:qe:analyze outcome.md --gate value

# Execution Gate after build
/wicked-garden:qe:analyze src/auth --gate execution

# Quick triage
/wicked-garden:qe:analyze --rigor quick
```

## Output

Analysis produces:
- **Decision**: APPROVE / CONDITIONAL / REJECT
- **Evidence**: Qualitative + quantitative findings
- **Kanban**: Evidence attached to task

## Integration

Works with:
- **wicked-crew**: Auto-suggested after phases
- **wicked-kanban**: Stores evidence
- **wicked-product**: Deep review delegation
- **wicked-mem**: Cross-session learning
