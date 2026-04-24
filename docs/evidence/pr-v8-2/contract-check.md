# Contract Check — v8-PR-2 vs v9 Drop-in Plugin Contract + PR-1 Locked Decisions

## v9 Drop-In Plugin Contract (`docs/v9/drop-in-plugin-contract.md`)

| Rule | Status | Notes |
|------|--------|-------|
| Skills use v9 discovery-shape descriptions | PASS | PR-2 adds no new skills or commands |
| `plugin.json` includes scope statement | PASS | Not modified |
| Plugin skills do NOT duplicate wicked-garden core | PASS | No new skills added |
| Bus events use canonical `{domain}:{action}:{outcome}` naming | PASS | New bus event types follow `wicked.task.{created|updated|completed}` pattern |
| Persistent state routes through wicked-brain:memory | PASS | Daemon tasks table is operational state, not cross-session knowledge |
| No internal patching | PASS | All changes are additive to daemon/ + helper scripts |
| Graceful degradation | PASS | WG_DAEMON_ENABLED=false (default) is bit-identical to pre-PR-2 |

**Contract verdict: PASS**

---

## PR-1 Locked Decisions (10 decisions from #589 Architecture Contract)

| Decision | Rule | Status |
|----------|------|--------|
| #1 | Stdlib only in daemon/ | PASS — `daemon/db.py`, `daemon/projector.py`, `daemon/server.py` use stdlib only |
| #2 | Off by default | PASS — `WG_DAEMON_ENABLED=false` default maintained |
| #3 | Port 4244 (WG_DAEMON_PORT override) | PASS — unchanged in server.py |
| #4 | DB path `~/.something-wicked/wicked-garden-daemon/projections.db` | PASS — unchanged in db.py |
| #5 | Bus subscription via `_bus.py` cursor pattern | PASS — consumer.py unchanged |
| #6 | All hooks/skills fail-open | PASS — all 8 migrated readers have try/except; daemon failure never blocks crew |
| #7 | Touch-null semantic on project upserts | PASS — tasks table uses INSERT OR IGNORE + UPDATE pattern; no regression |
| #8 | Unknown events ignored (never raise) | PASS — `_HANDLERS` miss → 'ignored'; verified by test_unknown_task_event_ignored |
| #9 | Timestamp normalisation via `_to_epoch` | PASS — task handlers use `_to_epoch(event.get("created_at"))` |
| #10 | Bind to 127.0.0.1 only | PASS — server.py DEFAULT_HOST unchanged |

**All 10 PR-1 locked decisions: PASS**

---

## Additional Checks

### Daemon stays READ-ONLY for task data
- No POST/PUT/DELETE endpoints added to server.py for tasks
- Tasks table populated ONLY by projector.py via wicked.task.* bus events
- Claude's native TaskList remains the primary writer — confirmed by non-goal #596

### No new surfaces (commands, skills)
- No new commands/*.md files
- No new skills/*.md files
- No new agents/*.md files
- Only new file is `scripts/crew/_task_reader.py` (internal routing helper, not a plugin surface)

### No description sharpens (v9-only work)
- No changes to skill SKILL.md files
- No changes to plugin.json skill descriptions
- All changes confined to daemon/, hooks/scripts/, scripts/crew/, scripts/mem/, scripts/delivery/

---

**Overall: PASS — PR-2 is consistent with the v9 plugin contract and all 10 PR-1 locked decisions.**
