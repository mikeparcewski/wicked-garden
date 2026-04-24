# Hook Audit: STAY vs MIGRATE

Issue #592 (v8 PR-8). Grain-riding rule (#585):

- **STAY (Claude-grain)**: hooks that fire on signals Claude can SEE — just-submitted
  prompt content, just-completed tool output, current session events.
- **MIGRATE (bus-grain)**: hooks that fire on signals Claude CANNOT see — cross-session
  bus events, gate decisions that happened hours ago in another session.

## Audit Results

| Hook File | Event | Grain | Decision | Rationale |
|-----------|-------|-------|----------|-----------|
| `prompt_submit.py` | `UserPromptSubmit` | Claude-grain | **STAY** | Reads THIS session's prompt content; cannot be bus-grain |
| `pre_tool.py` | `PreToolUse` | Claude-grain | **STAY** | Validates THIS tool call's metadata; fires synchronously in Claude's context |
| `post_tool.py` | `PostToolUse` / `PostToolUseFailure` | Claude-grain | **STAY** | Reacts to JUST-RUN tool output; inherently session-local |
| `subagent_lifecycle.py` | `SubagentStart` / `SubagentStop` | Claude-grain | **STAY** | Tracks THIS session's subagent launches; procedure injection is session-scoped |
| `task_completed.py` | `TaskCompleted` | Claude-grain | **STAY** | Memory compliance nudge on THIS session's task completions; no cross-session signal |
| `stop.py` | `Stop` | Claude-grain | **STAY** | Session teardown is session-local; fact emission is fire-and-forget TO bus, not FROM bus |
| `bootstrap.py` | `SessionStart` | Claude-grain | **STAY** | Session initialization is per-session by definition |
| `notification.py` | `Notification` | Claude-grain | **STAY** | Reacts to Claude's own notification events |
| `permission_request.py` | `PermissionRequest` | Claude-grain | **STAY** | Reacts to THIS session's permission requests |
| `pre_compact.py` | `PreCompact` | Claude-grain | **STAY** | Session memory compaction is session-local |

## MIGRATE candidates

| Hook Pattern | Proposed Bus-Grain Handler | Subscription Config |
|---|---|---|
| React to `wicked.gate.decided` from ANY session | `hooks/scripts/subscribers/on_gate_decided.py` | `hooks/subscriptions/on_gate_decided.json` |

## Session-end fact emission (stop.py)

`stop.py`'s `_run_memory_promotion()` **emits TO** the bus (fire-and-forget
`wicked.fact.extracted` events). This is the PRODUCER direction — it is not
reacting to a bus event from another session. Per grain-riding rule, it STAYS
in the Stop hook because it fires on THIS session's end signal (Claude-grain).

The CONSUMER side of `wicked.fact.extracted` (wicked-brain's auto-memorize
subscriber) is already implemented as a bus-grain subscriber in wicked-brain.
No migration needed here.

## Summary

- **10 hooks STAY** (all hooks react to Claude-grain signals)
- **1 MIGRATE** (on_gate_decided: reacts to cross-session `wicked.gate.decided`)
- Net: the typed subscriber pattern is additive — no existing hooks are removed
  or modified. The migration adds new bus-grain handlers alongside the existing
  Claude-grain hooks.
