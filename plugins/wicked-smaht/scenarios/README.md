# Wicked Smaht Test Scenarios

This directory contains real-world test scenarios that demonstrate and validate wicked-smaht v2 functionality.

## Scenario Overview

| Scenario | Type | Difficulty | Time | What It Tests |
|----------|------|------------|------|---------------|
| [session-context-injection](session-context-injection.md) | integration | basic | 3 min | SessionStart hook automatically gathers project context |
| [intent-based-retrieval](intent-based-retrieval.md) | feature | basic | 5 min | Intent detection adjusts source weights for debugging vs planning |
| [multi-lane-tracking](multi-lane-tracking.md) | feature | intermediate | 6 min | Concurrent intent tracking with up to 3 active lanes |
| [fact-extraction](fact-extraction.md) | feature | intermediate | 5 min | Automatic extraction of decisions, discoveries, and artifacts |
| [memory-promotion](memory-promotion.md) | integration | intermediate | 7 min | Cross-session facts promoted to wicked-mem on session end |
| [graceful-degradation](graceful-degradation.md) | architecture | basic | 4 min | Works standalone without any wicked-garden dependencies |

## Coverage Map

### Core Features
- **Intent Detection**: intent-based-retrieval, multi-lane-tracking
- **Session Management**: session-context-injection, memory-promotion
- **Fact Ledger**: fact-extraction, memory-promotion
- **Lane Management**: multi-lane-tracking

### Processing Modes
- **Fast Mode (<500ms)**: intent-based-retrieval (high confidence queries)
- **Deep Mode (<1s)**: intent-based-retrieval (medium confidence queries)
- **Deep+Broad**: multi-lane-tracking (low confidence, multiple lanes)

### Integration & Architecture
- **wicked-mem Integration**: memory-promotion, session-context-injection
- **wicked-jam Integration**: session-context-injection
- **wicked-kanban Integration**: session-context-injection
- **wicked-search Integration**: intent-based-retrieval
- **Standalone Mode**: graceful-degradation

## Running Scenarios

Each scenario is self-contained with:
- **Setup** - Initial conditions and commands
- **Steps** - Specific actions to perform
- **Expected Outcome** - What should happen
- **Success Criteria** - Verifiable checkboxes
- **Value Demonstrated** - Why this matters

### Session Storage Location

All session data is stored at:
```
~/.something-wicked/wicked-smaht/sessions/{session-id}/
├── session_meta.json  # Session metadata (written at session end)
├── lanes.jsonl    # Intent lanes
├── facts.jsonl    # Extracted facts
└── turns.jsonl    # Turn records
```

### Verification

After running each scenario:
1. Check hook output in Claude Code terminal
2. Verify session data at `~/.something-wicked/wicked-smaht/sessions/`
3. Confirm all success criteria checkboxes can be marked

## Scenario Design Principles

All scenarios follow these guidelines:

1. **Real-world use cases** - Scenarios reflect actual development workflows
2. **Functional testing** - Each scenario proves a feature actually works
3. **Concrete setup** - Clear steps to create test conditions
4. **Verifiable criteria** - Objective checkboxes that can be tested
5. **Value articulation** - Clear explanation of WHY someone would use this

## Adding New Scenarios

When adding scenarios, include:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: workflow|integration|feature|architecture
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

## Setup
[Concrete setup steps]

## Steps
[Numbered steps with expected observations]

## Expected Outcome
[What should happen]

## Success Criteria
- [ ] Verifiable criteria 1
- [ ] Verifiable criteria 2

## Value Demonstrated
[Why this matters in real-world usage]
```

## Test Execution

These scenarios can be:
- **Manual testing** - Follow steps during development
- **Onboarding** - Help new users understand capabilities
- **Documentation** - Show real examples of features
- **Regression testing** - Verify nothing broke after changes
- **Value demonstration** - Show prospective users what the plugin does
