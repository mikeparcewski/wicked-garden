# Evidence: cluster-A P1

Branch: cluster-a/p1-smaht-rename-events-ground
Date: 2026-04-25

## Renames

smaht:debug -> smaht:state (commands/smaht/debug.md -> commands/smaht/state.md)
smaht:events-query -> crew:activity (commands/smaht/events-query.md -> commands/crew/activity.md)

v5->v6 archaeology section deleted from state.md.

## Ground surfacing

Added "When context is thin" suggestion (invoke wicked-garden:ground) to:
- commands/smaht/state.md
- commands/smaht/briefing.md
- commands/crew/status.md

## Cross-refs

Pre: 22 live references across 10 files
Post: 0 live references (6 remaining are intentional CHANGELOG historical / v9/audit done-markers)

Files updated: commands/smaht/state.md, commands/crew/activity.md, commands/smaht/briefing.md,
commands/help.md, commands/smaht/events-import.md, docs/domains.md, docs/advanced.md,
docs/v9/audit.md, CHANGELOG.md

## Tests

11 failed, 1664 passed, 3 deselected, 15 subtests passed
11 failures are pre-existing (yolo alias + telemetry + bare-pass audit).
