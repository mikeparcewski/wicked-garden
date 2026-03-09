# Edit Coordination — Session Locks and Render Guards

Lightweight advisory coordination for concurrent or sequential edit operations within a single
session. Prevents conflicting writes to the Deck Spec and avoids re-rendering stale content.

---

## Overview

Two session keys protect the edit workflow:

| Key | Purpose | Scope |
|---|---|---|
| `presentation:session.css_lock` | Signals that CSS/template edits are in progress | Advisory — checked before CSS changes |
| `presentation:session.render_guard` | Signals that a render is in progress | Advisory — checked before starting a new render |

Both keys are **transient**: they exist only within the current session and are not persisted
across session restart. On session start, both keys are absent (treated as unlocked).

Advisory means: checks are informational — they surface a warning rather than hard-blocking
the operation. The user can override at any time by saying "proceed anyway" or "force render."

---

## css_lock

### What it protects

Signals that a CSS or template modification is actively in progress. Other operations that
would write to the same template or zone should check this key before proceeding.

### Key structure

```json
{
  "locked_by": "css-contract-update",
  "template": "stat-callout",
  "started_at": "2025-03-15T10:14:00Z",
  "reason": "Updating zone-stat font-size across stat-callout slides"
}
```

| Field | Description |
|---|---|
| `locked_by` | Brief identifier for the operation that set the lock |
| `template` | Template name being modified (or `"all"` for deck-wide changes) |
| `started_at` | ISO timestamp when the lock was set |
| `reason` | Human-readable description of the in-progress change |

### Setting and clearing

Set `css_lock` when beginning a CSS or template edit that spans multiple slides or passes.
Clear it immediately after the edit completes or fails.

**Merge-update pattern (required — never overwrite the whole session object):**

1. Read the current session object: `GET presentation:session`
2. Set or update only the `css_lock` sub-key within the object
3. Write the updated session object back: `PUT presentation:session`
4. After the operation completes (success or failure): repeat steps 1–3, setting `css_lock` to `null`

Example — setting the lock:
```
session = GET("presentation:session")
session["css_lock"] = {
  "locked_by": "css-contract-update",
  "template": "stat-callout",
  "started_at": now_iso(),
  "reason": "Updating zone-stat font-size across stat-callout slides"
}
PUT("presentation:session", session)
```

Example — clearing the lock:
```
session = GET("presentation:session")
session["css_lock"] = null
PUT("presentation:session", session)
```

Never do: `PUT("presentation:session", {"css_lock": {...}})` — this would erase all other
session keys (last-used profile, mode, format, fidelity, etc.).

### Check before proceeding

Before any CSS or template write:
```
session = GET("presentation:session")
lock = session.get("css_lock")
if lock and lock is not null:
  WARN "A CSS edit is in progress (started [started_at], reason: [reason]). Proceed anyway?"
  → Wait for user confirmation before continuing
```

---

## render_guard

### What it protects

Signals that a render pass is actively running. Starting a second render while one is in
progress would produce a race condition on the output file.

### Key structure

```json
{
  "deck_name": "q1-results",
  "version": "v3",
  "pass": 2,
  "total_passes": 3,
  "started_at": "2025-03-15T10:18:00Z",
  "format": "html"
}
```

| Field | Description |
|---|---|
| `deck_name` | Name of the deck being rendered |
| `version` | Version string being rendered |
| `pass` | Current pass number (1-based) |
| `total_passes` | Expected total passes for this fidelity level |
| `started_at` | ISO timestamp when the render started |
| `format` | `pptx`, `html`, or `both` |

### Setting and clearing

**Merge-update pattern (required — same as css_lock):**

1. Read the current session object: `GET presentation:session`
2. Set or update only the `render_guard` sub-key
3. Write the updated session object back: `PUT presentation:session`
4. After render completes or fails: repeat steps 1–3, setting `render_guard` to `null`

Example — setting the guard before pass 1:
```
session = GET("presentation:session")
session["render_guard"] = {
  "deck_name": "q1-results",
  "version": "v3",
  "pass": 1,
  "total_passes": 3,
  "started_at": now_iso(),
  "format": "html"
}
PUT("presentation:session", session)
```

Example — updating for pass 2 (read-update-write, not overwrite):
```
session = GET("presentation:session")
session["render_guard"]["pass"] = 2
PUT("presentation:session", session)
```

Example — clearing after completion:
```
session = GET("presentation:session")
session["render_guard"] = null
PUT("presentation:session", session)
```

### Check before proceeding

Before starting any render:
```
session = GET("presentation:session")
guard = session.get("render_guard")
if guard and guard is not null:
  WARN "A render is already in progress for [deck_name] [version], pass [pass]/[total_passes]
        (format: [format], started: [started_at]). Proceed anyway?"
  → Wait for user confirmation before continuing
```

---

## Handling Stale Keys

Because these keys are transient and advisory, a stale key (set but never cleared due to an
interrupted session or error) should not block the user permanently.

**Stale detection heuristic**: If `started_at` is > 10 minutes ago, treat the key as stale.

```
if lock and (now - parse_iso(lock["started_at"])) > 600 seconds:
  WARN "[key] appears stale (started [started_at]). Clearing and proceeding."
  session[key] = null
  PUT("presentation:session", session)
  # continue without advisory check
```

---

## Coordinating Audit + Edit Flows

When the audit identifies issues and the user requests an inline fix:

```
1. Check css_lock → clear to proceed
2. Set css_lock (merge-update)
3. Apply CSS / template correction to Deck Spec
4. Clear css_lock (merge-update)
5. Check render_guard → clear to proceed
6. Set render_guard for re-render pass (merge-update)
7. Run re-render pass
8. Run visual QA checks
9. Clear render_guard (merge-update)
10. Report corrected slide status
```

If the user requests "fix all issues" (bulk remediation):
- Process FAIL findings first, then WARN findings, then INFO
- Set css_lock once for the batch — do not toggle per slide
- Clear css_lock after all corrections are applied
- Then run a single re-render pass with render_guard

---

## Integration with Other Refs

| Need | Read |
|---|---|
| What triggers a CSS edit | [css-contract.md](css-contract.md) |
| Render pass lifecycle | [fidelity.md](fidelity.md) — best fidelity render loop |
| Audit-driven remediation | [audit.md](audit.md) — Re-audit After Fix section |
| Storage API | SKILL.md — Plugin Storage section |
