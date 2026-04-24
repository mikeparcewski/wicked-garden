# v8 Daemon — Architecture Contract (PR-1)

## Scope
- Read-only projection daemon. NO mutation endpoints in PR-1.
- Stdlib only: `http.server`, `sqlite3`, `urllib.request`, `subprocess`, `threading`, `json`, `os`, `pathlib`, `time`, `logging`. NO new deps; `requirements.txt` unchanged.
- Off by default: `WG_DAEMON_ENABLED=false` keeps every existing code path unchanged.
- Port: `4244` (override `WG_DAEMON_PORT`). Brain is 4243; bus has no HTTP.
- DB path: `~/.something-wicked/wicked-garden-daemon/projections.db` (override `WG_DAEMON_DB`).
- Bus subscription reuses `_bus.py` pattern proved by #572 (npx wicked-bus subscribe + cursor persistence).
- All hooks/skills fail-open when daemon is missing. Daemon failure NEVER blocks crew flow.

## File layout
```
daemon/
├── __init__.py        # Package marker. Exports: VERSION = "0.1.0", DEFAULT_PORT = 4244.
├── db.py              # SQLite schema + connection + per-table CRUD signatures.
├── server.py          # http.server with 5 read endpoints.
├── consumer.py        # Bus event reader (cursor-poll, restart-safe).
└── projector.py       # event_type → table column mapping rules.

tests/daemon/
├── __init__.py
├── conftest.py        # ephemeral DB fixture, fake bus event source, free-port allocator.
├── test_db.py         # schema init, upserts, FK behavior, idempotency.
├── test_server.py     # spawn server on free port, urllib.request assertions on JSON shapes.
├── test_consumer.py   # cursor advance + resume + restart-safe + unknown event survives.
├── test_projector.py  # per event_type → expected row state, including idempotent re-projection.
└── test_parity.py     # daemon projection vs direct-read for 5+ fixture scenarios.
```

## Module: daemon/db.py

### Tables (SQLite, all timestamps `INTEGER` epoch-seconds UTC)

**projects** — one row per crew project (mirrors `scripts/crew/project_registry.py` shape).
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | Project name slug (matches `state.name` in phase_manager). |
| `name` | TEXT NOT NULL | Human-readable name. |
| `workspace` | TEXT | From `CLAUDE_PROJECT_NAME` or cwd. NULL allowed. |
| `directory` | TEXT | Absolute path. |
| `archetype` | TEXT | One of 7 archetypes; NULL until classified. |
| `complexity_score` | REAL | 0.0–10.0; NULL until scored. |
| `rigor_tier` | TEXT | `minimal` \| `standard` \| `full`; NULL until set. |
| `current_phase` | TEXT | Most recent phase name; `''` at create, `'completed'` when done. |
| `status` | TEXT NOT NULL DEFAULT 'active' | `active` \| `completed` \| `archived`. |
| `chain_id` | TEXT | `{project}.root`. |
| `yolo_revoked_count` | INTEGER NOT NULL DEFAULT 0 | From `wicked.crew.yolo_revoked` (#581). |
| `last_revoke_reason` | TEXT | Most recent revoke reason. |
| `created_at` | INTEGER NOT NULL | Epoch seconds. |
| `updated_at` | INTEGER NOT NULL | Touched on every projection write. |

Index: `CREATE INDEX idx_projects_status ON projects(status)`; `CREATE INDEX idx_projects_updated ON projects(updated_at DESC)`.

**phases** — one row per (project, phase).
| Column | Type | Notes |
|---|---|---|
| `project_id` | TEXT NOT NULL | FK → projects.id (no cascade; daemon is projection). |
| `phase` | TEXT NOT NULL | Key from `.claude-plugin/phases.json`. |
| `state` | TEXT NOT NULL | `pending` \| `active` \| `approved` \| `skipped` \| `rejected`. Default `pending`. |
| `gate_score` | REAL | 0.0–1.0; NULL until gate decided. |
| `gate_verdict` | TEXT | `APPROVE` \| `CONDITIONAL` \| `REJECT`; NULL for non-terminal. |
| `gate_reviewer` | TEXT | Subagent type that wrote the verdict. |
| `started_at` | INTEGER | NULL until `wicked.phase.transitioned` lands. |
| `terminal_at` | INTEGER | NULL until terminal state. |
| `rework_iterations` | INTEGER NOT NULL DEFAULT 0 | Bumped on `wicked.rework.triggered`. |
| `updated_at` | INTEGER NOT NULL | |

`PRIMARY KEY (project_id, phase)`. Index: `CREATE INDEX idx_phases_project ON phases(project_id, updated_at DESC)`.

**cursor** — single-row bus cursor tracker (matches `_bus.py` cursor model).
| Column | Type | Notes |
|---|---|---|
| `bus_source` | TEXT PRIMARY KEY | Always `'wicked-bus'` in PR-1. |
| `cursor_id` | TEXT NOT NULL | Returned by `wicked-bus register`. |
| `last_event_id` | INTEGER NOT NULL DEFAULT 0 | Last successfully projected + acked event. |
| `acked_at` | INTEGER NOT NULL | |

**event_log** — append-only audit tail (last 10k retained).
Columns: `event_id INTEGER PRIMARY KEY`, `event_type TEXT NOT NULL`, `chain_id TEXT`, `payload_json TEXT NOT NULL`, `projection_status TEXT NOT NULL` (`applied` \| `ignored` \| `error`), `error_message TEXT` (NULL unless errored), `ingested_at INTEGER NOT NULL`. Index: `idx_event_log_type ON event_log(event_type, event_id DESC)`.

### Public API
- `connect(path: str | None = None) -> sqlite3.Connection` — opens DB at `path` or `WG_DAEMON_DB` or default; sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`; returns connection. Caller closes.
- `init_schema(conn: sqlite3.Connection) -> None` — idempotent; creates 4 tables + indexes if absent.
- `upsert_project(conn, project_id: str, fields: dict) -> None` — INSERT … ON CONFLICT DO UPDATE on `id`; updates `updated_at`. `fields` is a partial dict; missing keys preserve existing values.
- `upsert_phase(conn, project_id: str, phase: str, fields: dict) -> None` — same pattern keyed on `(project_id, phase)`.
- `get_project(conn, project_id: str) -> dict | None` — returns row as dict, or None.
- `list_projects(conn, status: str | None = None, limit: int = 100) -> list[dict]` — sorted `updated_at DESC`.
- `list_phases(conn, project_id: str) -> list[dict]` — ordered by `started_at NULLS LAST`.
- `get_cursor(conn, bus_source: str = 'wicked-bus') -> dict | None`
- `set_cursor(conn, bus_source: str, cursor_id: str, last_event_id: int) -> None`
- `append_event_log(conn, event_id: int, event_type: str, chain_id: str | None, payload: dict, projection_status: str, error_message: str | None = None) -> None`
- `prune_event_log(conn, keep_last: int = 10_000) -> int` — deletes oldest beyond `keep_last`; returns rows deleted.

## Module: daemon/server.py

### HTTP surface (port `WG_DAEMON_PORT` default 4244, host `127.0.0.1` only)
All responses: `Content-Type: application/json; charset=utf-8`. All timestamps in JSON: epoch-seconds integers. All error responses: `{"ok": false, "error": "<message>"}` with appropriate HTTP status.

| Method | Path | Query | Response (200) | Errors |
|---|---|---|---|---|
| GET | `/health` | — | `{"ok": true, "cursor_lag": <int>, "version": "<str>", "db_path": "<str>"}` | 503 if DB unreachable. `cursor_lag` = max(event_id seen on bus) − cursor.last_event_id; -1 if bus unavailable. |
| GET | `/projects` | `status=active\|completed\|archived` (optional), `limit=N` (default 100, max 500) | `[{"id": str, "name": str, "archetype": str\|null, "current_phase": str, "rigor_tier": str\|null, "complexity_score": float\|null, "status": str, "updated_at": int}]` | 400 on bad query. |
| GET | `/projects/{id}` | — | `{"id": str, "name": str, "workspace": str\|null, "directory": str\|null, "archetype": str\|null, "complexity_score": float\|null, "rigor_tier": str\|null, "current_phase": str, "status": str, "chain_id": str\|null, "yolo_revoked_count": int, "last_revoke_reason": str\|null, "created_at": int, "updated_at": int}` | 404 if unknown. |
| GET | `/projects/{id}/phases` | — | `[{"phase": str, "state": str, "gate_score": float\|null, "gate_verdict": str\|null, "gate_reviewer": str\|null, "started_at": int\|null, "terminal_at": int\|null, "rework_iterations": int, "updated_at": int}]` ordered by `started_at NULLS LAST` | 404 if project unknown. |
| GET | `/events` | `since=<int>` (event_id, default 0), `limit=<int>` (default 100, max 1000), `event_type=<prefix>` (optional) | `[{"event_id": int, "event_type": str, "chain_id": str\|null, "payload": dict, "projection_status": str, "ingested_at": int}]` ordered `event_id ASC` | 400 on bad query. |

### Public API
- `class ProjectionRequestHandler(http.server.BaseHTTPRequestHandler)` — implements `do_GET`; routes by `self.path` against the table above; never logs request bodies.
- `def make_server(host: str = '127.0.0.1', port: int = 4244, db_path: str | None = None) -> http.server.ThreadingHTTPServer` — returns a configured server (caller calls `serve_forever`).
- `def run(host: str | None = None, port: int | None = None, db_path: str | None = None) -> int` — blocking entrypoint; honors `WG_DAEMON_PORT`/`WG_DAEMON_HOST`; returns exit code on shutdown signal.

## Module: daemon/consumer.py

### Cursor-poll pattern (re-stating #572)
- Subscribe to wicked-bus by reusing `scripts/_bus.py::_ensure_registered` plumbing OR, if invoked from the daemon process, register via `subprocess` with `--filter wicked.*` and persist the returned `cursor_id` into the `cursor` table.
- Poll loop: every `WG_DAEMON_POLL_INTERVAL_MS` ms (default `1000`), call `wicked-bus replay --cursor-id <id> --from-event-id <last+1> --json`, project the batch, then `wicked-bus ack --cursor-id <id> --last-event-id <max>`.
- Persist cursor in DB AFTER each successful batch (not per event). Crash between project and ack → at-least-once redelivery; projector must be idempotent.
- Restart-safe: on start, read cursor from DB; if missing, register fresh and start at 0.
- Bus unavailable → consumer sleeps `WG_DAEMON_POLL_INTERVAL_MS` and retries; never raises.

### Public API
- `class ConsumerThread(threading.Thread)` — `__init__(self, conn_factory: Callable[[], sqlite3.Connection], stop_event: threading.Event, poll_interval_ms: int = 1000)`.
- `def run(self) -> None` — loop until `stop_event.is_set()`; one open conn per thread.
- `def process_batch(conn: sqlite3.Connection, events: list[dict]) -> tuple[int, int, int]` — projects each event via `projector.project_event`, writes to `event_log`, returns `(applied, ignored, errored)`. Caller advances cursor.
- `def start(stop_event: threading.Event, db_path: str | None = None, poll_interval_ms: int | None = None) -> ConsumerThread` — convenience launcher.
- `def cursor_lag(conn: sqlite3.Connection) -> int` — returns `max_known_event_id - cursor.last_event_id`, or `-1` if bus unavailable. Used by `/health`.

## Module: daemon/projector.py

### Event → projection rules
The 7 event types below mutate state. All others are appended to `event_log` with `projection_status='ignored'` and never raise. Idempotency: every projection is a deterministic UPSERT keyed on `project_id` (or `(project_id, phase)`); replaying the same event yields identical state.

| Bus event_type | Target | Mapping |
|---|---|---|
| `wicked.project.created` | `projects` UPSERT | `id=payload.project_id`, `name=payload.project_id`, `complexity_score=payload.complexity_score`, `chain_id=metadata.chain_id`, `created_at=event.created_at`, `updated_at=event.created_at`, `status='active'`. Touch only NULL fields on conflict (never overwrite richer state). |
| `wicked.project.complexity_scored` | `projects` UPDATE | `complexity_score=payload.complexity_score`, `rigor_tier=payload.rigor_tier` if present. |
| `wicked.phase.transitioned` | `phases` UPSERT × 2 + `projects` UPDATE | Source phase: `state='approved'`, `terminal_at=event.created_at`. Target phase (`payload.phase_to`, may be null): `state='active'`, `started_at=event.created_at`. Update `projects.current_phase=payload.phase_to or payload.phase_from`. |
| `wicked.phase.auto_advanced` | auto-advance variant: payload carries `phase` only, no `phase_from`/`phase_to`. Treated as a phase update with `state='approved'`. | `phases[phase].state='approved'`, `terminal_at=event.created_at`. `projects.current_phase=payload.phase`. Audit-only — also recorded in event_log. |
| `wicked.gate.decided` | `phases` UPDATE | Keyed `(project_id, phase=payload.phase)`. Set `gate_verdict=payload.result`, `gate_score=payload.score`, `gate_reviewer=payload.reviewer`. If `result == 'REJECT'`, also set `state='rejected'`, `terminal_at=event.created_at`. |
| `wicked.rework.triggered` | `phases` UPDATE | `rework_iterations=payload.iteration_count` (last-write-wins; payload is monotonic). |
| `wicked.project.completed` | `projects` UPDATE | `status='completed'`, `current_phase='completed'`. |
| `wicked.crew.yolo_revoked` | `projects` UPDATE | `yolo_revoked_count=payload.revoked_count`, `last_revoke_reason=payload.revoke_reason`. Project resolution: `payload.project` matches `projects.id` OR equals project directory basename. |

Skipped phases: PR-1 has no dedicated `wicked.phase.skipped` event in the catalog; if a future event lands or a skip is encoded as `wicked.phase.transitioned` with a sentinel, the projector uses `state='skipped'` mapping. Until then the state stays `pending` — documented limitation acknowledged in `test_parity.py`.

### Public API
- `def project_event(conn: sqlite3.Connection, event: dict) -> str` — returns `'applied'` \| `'ignored'` \| `'error'`. Internally dispatches via `_HANDLERS` table. Callers always pass the result to `db.append_event_log` along with the raw payload.
- `_HANDLERS: dict[str, Callable[[sqlite3.Connection, dict], None]]` — module-private dispatch table; one entry per row in the table above. Missing keys mean ignore.

## Parity test harness (tests/daemon/test_parity.py)

### What it asserts
Given a fixture event stream replayed into the daemon, the daemon's projection (read via `db.get_project` + `db.list_phases`) equals the direct-read result returned by `scripts/crew/phase_manager.load_project_state` + `scripts/crew/project_registry.get_project`, modulo whitelisted noise (`updated_at`, free-form dispatch logs, `last_event_id` itself).

### 5 fixture scenarios (named, each with a one-line "what it tests")
1. **`single_phase_approve`** — project created, one phase transitions, gate APPROVE; assert project + 1 phase row aligned.
2. **`reject_then_rework`** — phase gets REJECT then a `rework.triggered`; assert `state='rejected'`, `rework_iterations=1`, `gate_verdict='REJECT'`.
3. **`multi_phase_lifecycle`** — clarify → design → build with APPROVE at each gate; assert `current_phase` advances, every phase `state='approved'` with `terminal_at` populated.
4. **`auto_advance_low_complexity`** — project with `complexity_score < 3` triggers `wicked.phase.auto_advanced`; assert same projection as a normal `wicked.phase.transitioned`.
5. **`yolo_revoke_audit`** — scope-increase mutation fires `wicked.crew.yolo_revoked`; assert `yolo_revoked_count` and `last_revoke_reason` populated.
6. **`unknown_event_survives`** (bonus, recommended) — fixture includes an unknown `wicked.future.event`; assert daemon ignores, logs to `event_log` with `projection_status='ignored'`, advances cursor, and does not raise.

### Fixture format
Per-fixture directory under `tests/daemon/fixtures/<name>/`:
- `events.jsonl` — one JSON object per line: `{"event_id": int, "event_type": str, "created_at": int, "chain_id": str | null, "payload": {...}}`. Strictly ordered by `event_id`.
- `expected_project.json` — single object matching `GET /projects/{id}` response shape (timestamps replaced with sentinel `0` are wildcarded by the comparator).
- `expected_phases.json` — array matching `GET /projects/{id}/phases` shape, same wildcarding.

Comparator helper `_assert_projection_equals(actual, expected)` ignores `updated_at`, `created_at`, `started_at`, `terminal_at`, `ingested_at` when expected value is `0`; otherwise asserts equality.

## WG_DAEMON_ENABLED fallback

- **Default `false`**: daemon process not started; consumers/skills follow the existing direct-read path; zero behavioral change vs v7.2.x.
- **`true`**: daemon process is the preferred reader; designated skill (`commands/crew/status.md`'s helper script `scripts/crew/status_reader.py` — added in PR-1 as the single migration site) attempts `GET /health` with `WG_DAEMON_HEALTH_TIMEOUT_MS` (default 500ms) cap; on success, reads via daemon HTTP; on failure (non-200 or timeout), falls back to direct-read with a one-shot stderr warning per session.
- **`always`** (CI / parity): daemon-only; no fallback; surface daemon failures as test failures.
- Detection: env var read at module load time in the migrated reader; module-level `_DAEMON_MODE` constant ensures one decision per process. NO hooks read this env var in PR-1.

## Non-goals (do NOT implement in PR-1)
- Mutation endpoints (POST/PUT/DELETE) — PR-2.
- Phase state-machine validation / typed transitions — PR-3.
- Council orchestration / dispatch-from-daemon — PR-4.
- Specialist registry endpoint (canonical naming) — PR-5.
- AC structured-records endpoint — separate PR.
- Autonomy flag consolidation — separate PR.
- Typed hook subscribers (daemon-driven hook invocation) — separate PR.
- Live progress TUI — separate PR.
- Migrating more than one read site to daemon — defer to post-soak.
- Modifying `scripts/crew/phase_manager.py` or `scripts/_bus.py` — PR-1 is additive only.

## Acceptance (verbatim from #589)
1. `wicked-garden-daemon start` runs on port 4244.
2. `curl localhost:4244/health` returns `{ok: true, cursor_lag: N}`.
3. Creating a crew project causes a row in `projects` within 3s.
4. `WG_DAEMON_ENABLED=false` keeps existing tests green, 0 regressions.
5. `test_parity.py` runs both paths on 5+ fixture scenarios with matching output.
6. Stopping the daemon + `WG_DAEMON_ENABLED=true` falls back cleanly.
