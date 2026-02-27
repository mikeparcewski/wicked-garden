---
name: memory
description: |
  Memory storage, recall, and lifecycle management for maintaining context across sessions.

  This skill should be used when the user asks to "remember this", "store a decision",
  "recall what we did", "find past context", "save for later", "what did we learn",
  "what did we decide", or mentions persisting knowledge, decisions, or learnings.

  Use when:
  - "remember this for next time"
  - "store this decision"
  - "what did we do before"
  - "recall past context"
  - "save this pattern"
---

# Memory Management Skill

This skill provides guidance on effectively using Claude's memory system to persist knowledge, decisions, and learnings across sessions.

## When to Use This Skill

- After completing significant work that yielded learnings
- When making architectural or design decisions
- When encountering and solving bugs that might recur
- When establishing patterns or preferences
- When needing to recall past context

## Core Concepts

**Memory Types** - Choose the right type for durability:
- `episodic`: What happened (90-day TTL)
- `procedural`: How to do things (permanent)
- `decision`: Choices and rationale (permanent)
- `preference`: User/project preferences (permanent)

**Scope** - Where memories live:
- `core`: Global, cross-project
- `project`: Specific to current project

**Importance** - Affects decay rate:
- `high`: 2x TTL multiplier
- `medium`: Standard TTL
- `low`: 0.5x TTL multiplier

## Quick Reference

| Task | Command |
|------|---------|
| Store a decision | `/wicked-garden:mem-store "..." --type decision` |
| Find past context | `/wicked-garden:mem-recall "query"` |
| Check memory health | `/wicked-garden:mem-stats` |
| Archive old memory | `/wicked-garden:mem-forget mem_id` |

## On-Demand Recall

Memories are pulled on-demand, not preloaded. When context is needed:

1. **Auto-triggered**: Prompts like "why did we decide..." auto-search memories
2. **Manual fallback**: If no context is injected and you need history, use:
   ```
   /wicked-garden:mem-recall "query terms"
   ```

**When to proactively recall:**
- User asks about past decisions but no memory was injected
- Task relates to previous work in the project
- Making decisions that should reference past rationale
- Debugging an issue that might have been solved before

## Workflow Guides

| Task | Guide |
|------|-------|
| What to store and how to structure it | [Storing Decisions](refs/storing-decisions.md) |
| Effective search and filtering | [Effective Recall](refs/effective-recall.md) |
| Managing memory lifecycle | [Memory Lifecycle](refs/memory-lifecycle.md) |
