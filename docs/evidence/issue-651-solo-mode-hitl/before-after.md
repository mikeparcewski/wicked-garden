# Issue #651 — Solo-Mode HITL: Before / After

## Design Rationale

The brainstorm decision locked in `--hitl=inline` as the canonical flag for
replacing council-mode gate dispatch with synchronous inline human review.
This allows a solo developer to serve as the "council of one" for standard and
minimal rigor projects, while preserving all gate artifacts so CI and audit
tools see unchanged evidence shapes.

Full-rigor projects are explicitly excluded — the council pattern is mandatory
there.

## 7 Concrete Changes

### 1. Dispatch mode: `human-inline` branch in `_dispatch_gate_reviewer`

**File**: `scripts/crew/phase_manager.py`

Added `_dispatch_human_inline()` function and a branch for `mode == "human-inline"`
in `_dispatch_gate_reviewer()`. The insertion point is the mode-dispatch chain
(lines after council). Composable with all existing modes — no existing path
is touched.

The headless-fallback path within `_dispatch_human_inline` falls back to
`_dispatch_council()` when the session is non-interactive, so CI environments
never stall.

### 2. Schema updates

**File**: `scripts/crew/gate_result_schema.py`

- Added `_VALID_DISPATCH_MODES` frozenset including `"human-inline"`.
- Added `mode` field validation: absent mode is accepted for backward-compat;
  present mode must be in the valid-modes set.
- Extended `known_top_level` with `mode`, `dispatch_mode`, `context_ref`,
  `mode_fallback_reason`, `original_mode`, `external_review`.

**File**: `scripts/crew/content_sanitizer.py`

- Added `"mode"` and `"dispatch_mode"` to `_STRICT_FIELDS` so both fields
  are sanitized through the strict (Basic Latin) allowlist.
- `"human-inline"` is all Basic Latin printable — passes strict allowlist.

### 3. `ProjectState.solo_mode` flag

**File**: `scripts/crew/phase_manager.py` (CLI section)

- Added `--hitl MODE` and `--solo-mode` (alias) parser arguments.
- `create` action: after project creation, resolves effective solo mode
  via `resolve_solo_mode(state, flag)` and persists `solo_mode: true` to
  `state.extras` when active.
- Calls `reject_full_rigor_solo(state)` before persisting — raises
  `SoloModeUnavailableError` at full rigor with a clear message.

### 4. `inline-review-context.md`

**File**: `scripts/crew/solo_mode.py` (`_write_inline_review_context`)

Written alongside `gate-result.json` for each human-inline gate. Contains:
- 3-5 bullet evidence summary
- User's raw response
- Timestamp
- Reference to gate-result.json via `context_ref` field

### 5. Session-start banner

**File**: `hooks/scripts/bootstrap.py`

When the active crew project has `solo_mode: true` in its persisted data, the
bootstrap emits:

> [SOLO MODE ACTIVE] Council gates replaced with inline human review for this
> project. Gate artifacts are preserved. Merge-gate council pattern is unchanged.

### 6. Headless/CI fallback

**File**: `scripts/crew/solo_mode.py` (`_is_interactive`, `_headless_fallback_stub`)

- `WG_HEADLESS=true` or `sys.stdin.isatty()` returning False → non-interactive.
- Returns stub with `mode_fallback_reason: "no-interactive-session"`.
- `_dispatch_human_inline` in `phase_manager.py` detects `mode_fallback_reason`
  and delegates to `_dispatch_council()` with the original reviewer list.
- Warning logged to stderr; fallback reason annotated on the council result.

### 7. Global config support

**File**: `scripts/crew/solo_mode.py` (`load_global_config`, `resolve_solo_mode`)

- Reads `~/.wicked-brain/config/crew-defaults.json` (fail-open on any error).
- `resolve_solo_mode` precedence: flag > project extras > global config > default.
- `--solo-mode` alias maps to `--hitl=inline` at the parser level.

## New File

`scripts/crew/solo_mode.py` — 370 lines, stdlib-only, no circular imports.

Public API: `dispatch_human_inline`, `is_solo_mode`, `load_global_config`,
`reject_full_rigor_solo`, `resolve_solo_mode`, `SoloModeUnavailableError`,
`REVIEWER_NAME`, `DISPATCH_MODE`.
