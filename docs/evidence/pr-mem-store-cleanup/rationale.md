# Dead Code Cleanup Rationale — mem:store hook references (#601)

## Context

`wicked-garden:mem:store` was removed in #603/#604. The canonical memory API is now
`wicked-brain:memory`. Hook code that detected `mem:store` skill calls became unreachable.

## Per-file decisions

### hooks/scripts/post_tool.py

**Dead guard removed. Reset condition updated to wicked-brain:memory.**

The `_handle_skill` function contained two distinct blocks:
1. Pull-model tracking for `wicked-brain:query/search` — kept, live path.
2. Compliance counter reset guarded by `":mem:store" not in skill and skill != "mem:store"` — dead gate removed.

The reset itself (`memory_compliance_escalations = 0`) has legitimate value: it zeros the
escalation counter when the model acts on the memory directive. Updated the detection condition
from `mem:store` to `wicked-brain:memory` so the counter resets correctly going forward.

Dispatch comment at line ~1462 updated from "mem:store escalation counter reset" to
"memory compliance counter reset + pull-model tracking" (both live purposes documented).

**LOC delta: ~0 net** (removed old comment lines, added new ones; guard condition replaced).

### hooks/scripts/task_completed.py

**Comments updated. No logic changed.**

- Line 48 comment: `mem:store call` → `wicked-brain:memory call`
- `_infer_mem_type` docstring: `mem:store type` → `wicked-brain:memory type`

The function itself is still called at line 271 to pick the `type=` argument for the
`wicked-brain:memory` directive emitted in system messages. It stays.

**LOC delta: 2 lines changed (comments only).**

### hooks/scripts/pre_tool.py

**TODO comment updated.**

The TODO (Issue #329) describes a future redirect of MEMORY.md Write/Edit to the memory
skill API. Updated reference from `mem:store` to `wicked-brain:memory`. Feature not yet
implemented; comment accuracy only.

**LOC delta: 1 line changed.**

### hooks/hooks.json

**_TODO_329 comment updated.**

Same TODO as pre_tool.py — updated the target redirect from `mem:store` to `wicked-brain:memory`.

**LOC delta: 1 line changed.**

### scripts/_session.py

**Field comment updated.**

`memory_compliance_escalations` field comment: `mem:store Write/Edit` → `wicked-brain:memory Skill call`.
Field and default value unchanged.

**LOC delta: 1 line changed.**

## Counter disposition

**Kept and updated for wicked-brain:memory.**

The `memory_compliance_escalations` counter remains in `_session.py` with default 0.
- Incremented by: `task_completed.py` on every deliverable-producing task
- Reset by: `post_tool.py` when `wicked-brain:memory` skill call succeeds
- Consumed by: `task_completed.py` to decide whether to prefix `[ESCALATION]` on memory directives

The counter mechanism is live and valuable. Only the detection string was stale (`mem:store`
→ `wicked-brain:memory`). No counter fields removed; `grep -rn "memory_compliance_escalations"`
returns only the live increment/reset/read paths plus the session field definition.

## Runtime behavior

No runtime behavior changed for any path that was reachable before this PR.
The dead `":mem:store" not in skill` branch was unreachable post-#603; its removal
changes no observable behavior. The counter reset now fires correctly on `wicked-brain:memory`
calls instead of silently never firing.
