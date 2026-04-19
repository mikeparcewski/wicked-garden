# Process memory — first-class context at session start

Issue #447 adds a persistent per-project process memory. The facilitator reads this at every session start so retro observations, kaizen hypotheses, and unresolved action items don't evaporate between sessions.

## Surface

Every crew project has a `process-memory.json` + rendered `process-memory.md` in its project directory:

```
<project-dir>/process-memory.json    # canonical, machine-readable
<project-dir>/process-memory.md      # rendered companion, read at session start
```

The facilitator MUST read `process-memory.md` (or call the context helper) BEFORE scoring factors (Step 3) or selecting phases (Step 5). Observations from prior sessions change the plan — a 3-session-old unresolved action item about flaky tests is a signal that the testability factor needs a higher weight.

## One-shot context read

At session start, fetch the compact dict via:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/delivery/process_memory.py show \
  --project <project-name>
```

This returns:

- `narrative` — free-text block written at the most recent retro
- `aging_action_items` — list of AIs unresolved for >= 2 sessions
- `aging_count` — integer for quick threshold checks
- `proposed_kaizen` / `trialing_kaizen` — kaizen items that need attention
- `kaizen_backlog_size` — total count
- `pass_rate_timeline_length` — how many samples are available for drift classification
- `markdown_path` — absolute path to `process-memory.md`

When `aging_count > 0`, surface those items to the user BEFORE creating new tasks. Unresolved process risk from prior sessions takes precedence over novel planning.

## Kaizen backlog

Every process-improvement hypothesis gets a stable `KZN-NNN` ID, a Lean waste classification, impact/effort ratings, and a lifecycle (`proposed` → `trialing` → `adopted` / `rejected`). Waste types match the canonical 8-waste list: defects, overproduction, waiting, non-utilized-talent, transportation, inventory, motion, overprocessing.

When the facilitator notices a process friction point during planning, emit a kaizen item instead of silently absorbing the cost.

## Action items (retro outputs)

Retro action items get `AI-NNN` IDs and are tracked across sessions. The `age_sessions` counter increments whenever the AI is surfaced in a distinct session. At >= 2 sessions unresolved, the item appears in the facilitator's aging list automatically — no manual recall required.

## Uncertainty gate — before adding new process

When a specialist (or the facilitator itself) proposes adding a new gate or review, the proposal MUST pass the uncertainty gate:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/delivery/process_memory.py uncertainty-gate \
  --project <project-name> \
  --proposed-gate-name "<slug>" \
  --uncertainty "epistemic|aleatoric" \
  --session-id "<session-id>"
```

Pass condition: **actionable drift** (special-cause signal from `scripts/delivery/drift.classify`) OR **epistemic uncertainty** (the team is explicitly saying "we don't know enough, a gate would help us learn").

Fail condition: common-cause variation + aleatoric uncertainty = more process would just add overhead without addressing root cause.

The decision is recorded as a kaizen item so the audit trail is durable. A blocked proposal is auto-filed as `rejected` in the kaizen backlog.

**Fail-open behavior**: If `scripts/delivery/drift` is not importable yet (PR #452 pending at time of writing), the gate runs with drift classification treated as inconclusive and decides based on the uncertainty flag alone. This is intentional — we don't block work because a sibling PR hasn't landed.
