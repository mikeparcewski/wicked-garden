---
name: qe-strategy
description: |
  Shift-left QE analysis with quality gates.
  Generate test scenarios, assess risks, analyze code quality.
  Works standalone or integrated with wicked-crew.

  Use when: "test strategy", "what should I test", "quality gate",
  "test scenarios", "QE analysis", "should we build this", "does it work"
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
| `/wicked-qe:analyze` | Run QE gate analysis |
| `/wicked-qe:analyze --gate value` | Value Gate |
| `/wicked-qe:analyze --gate strategy` | Strategy Gate (default) |
| `/wicked-qe:analyze --gate execution` | Execution Gate |

## Usage

```bash
# Default Strategy Gate
/wicked-qe:analyze src/auth

# Value Gate on requirements
/wicked-qe:analyze outcome.md --gate value

# Execution Gate after build
/wicked-qe:analyze src/auth --gate execution

# Quick triage
/wicked-qe:analyze --rigor quick
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
