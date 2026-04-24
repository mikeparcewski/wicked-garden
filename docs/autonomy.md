# Autonomy Flag

`--autonomy={ask|balanced|full}` is the single axis for controlling how
autonomously crew gates run.  It replaces five old surfaces that expressed
the same intent in different ways.

## Three modes

| Mode | Clarify halt | Council verdict | Challenge phase | Destructive ops |
|------|-------------|-----------------|-----------------|-----------------|
| `ask` (default) | Always pause | Show and pause | Require approval | Confirm |
| `balanced` | HITL judge decides | Pause on split | HITL judge decides | Confirm |
| `full` | Auto unless judge pauses | Auto if unanimous | Auto | Confirm |

**HITL judge** (Issue #575, `scripts/crew/hitl_judge.py`) is the existing
rule-based decision engine.  `balanced` and `full` both delegate to it; the
difference is that `full` also tries structured AC lookup before consulting the
judge.

**Destructive ops** (`confirm`) are never auto-approved regardless of mode.
This row exists only for audit clarity.

### ask (default)

Every gate pauses for human acknowledgment.  This is the conservative default
that preserves pre-v8 behaviour for new users and CI pipelines that have not
opted in to autonomy.

### balanced

HITL judge decides whether to pause at each gate.  The rule table:

- `clarify`: yolo=True + confidence ≥ 0.7 + complexity < 5 + 0 open questions → auto-proceed; anything else → pause.
- `council`: unanimous + all votes ≥ 0.6 confidence → auto-proceed; split or low confidence → pause.
- `challenge`: below complexity threshold → skip; otherwise runs with charter selected by judge.

### full

Auto-proceeds when signals are clean.

- `clarify`: queries structured ACs (PR-5 `acceptance_criteria.load_acs()`) first.  If all ACs satisfied and HITL judge agrees → auto-proceed.  If ACs unsatisfied or judge pauses → falls back to `balanced` behaviour.
- `council`: auto-proceeds when verdict is unanimous and all votes are high-confidence.
- `challenge`: always auto-proceeds (challenge runs as part of the workflow, not as a halt).

## How to use

Pass `--autonomy=<mode>` on `crew:execute` or `crew:just-finish`:

```
/wicked-garden:crew:execute --autonomy=balanced
/wicked-garden:crew:just-finish --autonomy=full
```

Or set the env var for the whole session:

```bash
export WG_AUTONOMY=balanced
```

## Precedence rules

Resolution order (high to low):

1. CLI flag: `--autonomy=<mode>`
2. Env var: `WG_AUTONOMY=<mode>`
3. Project config: `autonomy_mode` field in `project.json` `extras`
4. Default: `ask`

Unknown values at any layer are skipped and the next layer is tried.

## Migration from old flags

The table below maps each old surface to its `--autonomy` equivalent.  Old
surfaces are preserved as compatibility shims — they continue to work but emit
a one-time deprecation warning per session.  They will be removed in v9.

| Old surface | Equivalent | Notes |
|-------------|-----------|-------|
| `crew:auto-approve --approve` | `--autonomy=full` | Routes through autonomy layer with mode=full |
| `--yolo` (on `just-finish`) | `--autonomy=full` | Same semantics; execution behaviour preserved |
| `--just-finish` (engagement level) | `--autonomy=full` | The command itself is not deprecated; only the `--yolo` flag on it |
| `engagementLevel: just-finish` | `--autonomy=full` | Internal metadata field; now stored as `autonomy_mode: full` |
| (unset) | `--autonomy=ask` | Default conserves prior behaviour |

## Structured AC integration (full mode)

When `autonomy=full` is active and a `project_dir` is provided to
`apply_policy()`, the clarify gate queries:

1. `phases/clarify/ac-evidence.json` — structured evidence store written by
   the AC evidence tracker (PR-5 full implementation).
2. `phases/clarify/acceptance-criteria.md` — Markdown AC list as fallback.

If all ACs are satisfied, the gate auto-proceeds (subject to HITL judge
confirmation).  If any AC is unsatisfied, the gate falls back to `balanced`
behaviour — the HITL judge makes the final call.

When no `project_dir` is provided or the AC module is unavailable, `full` mode
behaves like `balanced` for the clarify gate.

## Implementation

The policy table lives in `.claude-plugin/autonomy-policy.json` (schema at
`autonomy-policy.schema.json`).  The Python layer is
`scripts/crew/autonomy.py`.  Tests are in
`tests/crew/test_autonomy.py` and `tests/crew/test_autonomy_deprecation.py`.

Policy is **data**, not code.  Adding a fourth mode is a JSON edit to
`autonomy-policy.json` plus a matching policy-handler in `autonomy.py`.
