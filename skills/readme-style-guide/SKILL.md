---
name: readme-style-guide
description: Canonical README template and validation rules for Wicked Garden marketplace plugins. Use when writing, reviewing, or validating plugin READMEs.
tags: [documentation, style-guide, readme, marketplace, quality]
---

# README Style Guide

Standard structure, tone, and content rules for Wicked Garden plugin READMEs.

## Canonical Section Order

Every plugin README follows this structure. Sections marked CONDITIONAL include their trigger rule.

```
1.  # wicked-garden                           ← h1 + tagline (REQUIRED)
2.  ## {Lifecycle/Value Section}              ← CONDITIONAL: value invisible in single command
3.  ## Quick Start                            ← REQUIRED: 3 commands max
4.  ## {Core Workflows}                       ← REQUIRED: 2-3 real scenarios with output
5.  ## Commands                               ← REQUIRED: reference table
6.  ## When to Use What                       ← CONDITIONAL: 3+ commands with overlapping scope
7.  ## How It Works                           ← CONDITIONAL: mechanism is part of value prop
8.  ## Agents / Skills                        ← REQUIRED if plugin has agents or skills
9.  ## Data API                               ← CONDITIONAL: plugin exposes CP data sources
10. ## Integration                            ← REQUIRED: 3-column table
11. ## License                                ← REQUIRED
```

## Tagline Rules

The first line after the h1 heading is the tagline. It must:
- Be one sentence making a specific, differentiating claim
- Name the behavior or outcome, NOT the category
- Be falsifiable — a reader can verify whether it's true

```
GOOD: "Structural code intelligence across 73 languages — trace a JSP field to its database column."
BAD:  "A code search plugin for Claude Code."

GOOD: "Cross-session memory with signal-based recall and automatic decay."
BAD:  "A memory management plugin."
```

## Quick Start Rules

Exactly 3 commands, labeled:
1. Install command
2. First win (simplest useful command)
3. Most common use case

No prose explanations in Quick Start. That goes in Workflows or How It Works.

## Workflow Section

Appears BEFORE the Commands reference table. Workflows persuade; Commands reference.

Each workflow: heading + code block (3-5 commands) + optional expected output block. Show real output when possible — what does the user actually see?

## Integration Table Format

**Three columns are mandatory.** The "Without It" column converts a dependency list into a value story.

```markdown
| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-mem | Decisions persist across sessions | Brainstorming works, but insights aren't stored |
```

Use active voice in "What It Unlocks" to imply directionality (who calls whom).

## Conditional Section Triggers

| Section | Include When |
|---------|-------------|
| Lifecycle | Core value requires multiple invocations to see |
| When to Use What | 3+ commands with overlapping scope |
| How It Works | Internal mechanism is part of the value proposition |
| Data API | Plugin exposes data via the Control Plane |
| Agents & Skills | Merge tables if combined rows ≤5; split if either has 5+ |

## Tone

- Confident, specific, technically precise
- Lead with "why" before "what"
- Every marketing claim backed by a concrete example or code block
- No hedging language ("might", "could potentially")

## References

- Full annotated template: `refs/template.md`
- Validation rules and checklist: `refs/rules.md`
