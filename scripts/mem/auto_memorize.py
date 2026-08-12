#!/usr/bin/env python3
"""auto_memorize.py — the estate rebuild of brain's auto-memorize loop.

wicked-brain's server ran a wicked-bus subscriber (memory-subscriber.mjs)
that consumed ``wicked.garden.fact.extracted`` events and wrote memory files.
Brain retires at S7; this module is the garden-run replacement: the SAME
promotion policy (promoteFact: decision/discovery only, length floor,
importance→tier) and the SAME content-hash dedup, but persistence goes to
**wicked-estate** via ``memory.capture`` through the mem backend plumbing.
Estate itself stays bus-free by design — garden owns the consumer.

Consumption model — drain-on-invoke
-----------------------------------
No daemon. The Stop hook (and anything else that wants to) invokes
``drain``, which:

  1. runs ``wicked-bus subscribe --once --no-ack`` under the dedicated
     subscriber identity (plugin ``wicked-garden-mem``, durable cursor,
     ``cursor_init latest`` on first registration — no historical replay);
  2. processes each pending event in order: promote → content-hash dedup →
     ``memory.capture`` via the estate shim;
  3. advances the durable cursor (CLI ``ack``) only past events that were
     stored, deduped, skipped, or dead-lettered.

At-least-once is preserved: a failed estate write leaves the cursor put, so
the event redelivers on the next drain (the retry "backoff" is the next hook
invocation). Retry bookkeeping and dead-letters use wicked-bus's OWN tables
(``delivery_attempts``, ``dead_letters``) so ``wicked-bus dlq list|replay``
sees them exactly as it saw brain's — after ``MAX_ATTEMPTS`` failed drains an
event is dead-lettered and the cursor moves on (the pipeline never wedges).

Dedup
-----
Brain deduped via findByContentHash over its index. Estate has no
content-hash lookup, so the consumer keeps its own ledger (JSON,
``~/.something-wicked/wicked-garden/local/wicked-mem/auto_memorize_hashes.json``)
keyed by the same normalization brain used: trim, collapse whitespace,
lowercase, sha256.

Fail-open contract: bus or estate absent → ``{"ok": false, "reason": ...}``,
exit 0; only usage errors exit 1. Stdlib-only; direct sqlite is used ONLY for
the two native bus tables above plus the cursor lookup (the same pattern
brain's fastForwardStaleCursor used).

Usage
-----
  python3 scripts/mem/auto_memorize.py drain '{}'
  python3 scripts/mem/auto_memorize.py status '{}'
"""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mem import estate_memory  # noqa: E402

PLUGIN = "wicked-garden-mem"
FACT_FILTER = "wicked.garden.fact.extracted"
MAX_ATTEMPTS = 3          # mirrors brain's subscriber (maxRetries: 3)
_CLI_TIMEOUT = 30.0

# promoteFact policy — ported from brain server/lib/memory-promoter.mjs.
_ALLOWED_TYPES = frozenset({"decision", "discovery"})
_MIN_CONTENT_LENGTH = 15
_IMPORTANCE_BY_TYPE = {"decision": 7, "discovery": 4}
_MAX_TAGS = 15
# fact type → estate memory kind (skills/mem/refs/scopes.md mapping).
_KIND_BY_TYPE = {"decision": "fact", "discovery": "episode"}


def _emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")


# ── promotion policy (pure) ──────────────────────────────────────────────────

def content_hash(content):
    """Brain-compatible content hash: trim, collapse whitespace, lowercase."""
    normalized = re.sub(r"\s+", " ", str(content or "").strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def promote_fact(event):
    """Apply brain's auto-memorize promotion policy to a bus event.

    Pure function. Returns ``(memory_args, None)`` where memory_args feeds
    ``estate_memory._capture_one``, or ``(None, skip_reason)``.
    """
    if not isinstance(event, dict) or event.get("event_type") != FACT_FILTER:
        return None, "wrong event_type"
    payload = event.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None, "malformed payload"
    if not isinstance(payload, dict):
        return None, "malformed payload"

    fact_type = payload.get("type")
    if fact_type not in _ALLOWED_TYPES:
        return None, f"type {fact_type} not auto-promoted"
    content = payload.get("content")
    if not isinstance(content, str):
        return None, "missing payload.content"
    trimmed = content.strip()
    if len(trimmed) < _MIN_CONTENT_LENGTH:
        return None, "content too short"

    importance = _IMPORTANCE_BY_TYPE[fact_type]
    tier = "semantic" if importance >= 7 else "episodic"
    entities = payload.get("entities")
    about = []
    if isinstance(entities, list):
        about = [str(e) for e in entities if e][: _MAX_TAGS - 1]
    if fact_type not in about:
        about.append(fact_type)

    return {
        "content": trimmed,
        "kind": _KIND_BY_TYPE[fact_type],
        "tier": tier,
        "about": about[:_MAX_TAGS],
        "content_hash": content_hash(trimmed),
        "session_id": payload.get("session_id") or "",
    }, None


# ── dedup ledger ─────────────────────────────────────────────────────────────

def _ledger_path():
    override = os.environ.get("WICKED_MEM_LEDGER_DIR")
    base = Path(override) if override else (
        Path.home() / ".something-wicked" / "wicked-garden" / "local" / "wicked-mem"
    )
    return base / "auto_memorize_hashes.json"


def _load_ledger():
    try:
        data = json.loads(_ledger_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_ledger(ledger):
    try:
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger), encoding="utf-8")
    except OSError:
        pass  # fail open — worst case is a duplicate memory next drain


# ── wicked-bus plumbing (CLI first; direct sqlite only for native tables) ────

def _bus_cmd(*args):
    return ["npx", "--yes", "wicked-bus", *args]


def _run_cli(*args, timeout=_CLI_TIMEOUT):
    """Run a wicked-bus CLI command. Returns (returncode, stdout) — (-1, "") on spawn failure."""
    try:
        proc = subprocess.run(
            _bus_cmd(*args), capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout or ""
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return -1, ""


def _bus_db_path():
    """Resolve the bus DB the same way wicked-bus paths.js does (env → home)."""
    override = os.environ.get("WICKED_BUS_DATA_DIR")
    base = Path(override) if override else (
        Path.home() / ".something-wicked" / "wicked-bus"
    )
    return base / "bus.db"


def _bus_db():
    path = _bus_db_path()
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(path), timeout=3.0)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _find_cursor(conn):
    """(cursor_id, subscription_id, last_event_id) for our plugin+filter, or None."""
    try:
        row = conn.execute(
            """SELECT c.cursor_id, c.subscription_id, c.last_event_id
                 FROM subscriptions s
                 JOIN cursors c ON c.subscription_id = s.subscription_id
                WHERE s.plugin = ? AND s.event_type_filter = ?
                  AND s.role = 'subscriber'
                  AND s.deregistered_at IS NULL AND c.deregistered_at IS NULL
                ORDER BY s.registered_at DESC LIMIT 1""",
            (PLUGIN, FACT_FILTER),
        ).fetchone()
        return (row["cursor_id"], row["subscription_id"], row["last_event_id"]) if row else None
    except sqlite3.Error:
        return None


def _get_attempts(conn, cursor_id, event_id):
    try:
        row = conn.execute(
            "SELECT attempts FROM delivery_attempts WHERE cursor_id = ? AND event_id = ?",
            (cursor_id, event_id),
        ).fetchone()
        return int(row["attempts"]) if row else 0
    except sqlite3.Error:
        return 0


def _record_attempt(conn, cursor_id, event_id, attempts, error):
    try:
        conn.execute(
            """INSERT INTO delivery_attempts (cursor_id, event_id, attempts, last_attempt_at, last_error)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(cursor_id, event_id) DO UPDATE SET
                 attempts = excluded.attempts,
                 last_attempt_at = excluded.last_attempt_at,
                 last_error = excluded.last_error""",
            (cursor_id, event_id, attempts, int(time.time() * 1000), str(error)[:500]),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def _clear_attempts(conn, cursor_id, event_id):
    try:
        conn.execute(
            "DELETE FROM delivery_attempts WHERE cursor_id = ? AND event_id = ?",
            (cursor_id, event_id),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def _dead_letter(conn, cursor_id, subscription_id, event, attempts, reason):
    """Native dead-letter insert — the same row subscribe()'s moveToDeadLetter
    writes, so ``wicked-bus dlq list|replay|drop`` operate on it unchanged."""
    try:
        payload = event.get("payload")
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        conn.execute(
            """INSERT INTO dead_letters (
                 cursor_id, subscription_id, event_id, event_type, domain,
                 subdomain, payload, emitted_at, attempts, last_error, dead_lettered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cursor_id, subscription_id, event.get("event_id"),
                event.get("event_type", ""), event.get("domain", ""),
                event.get("subdomain") or "", payload,
                int(event.get("emitted_at") or time.time() * 1000),
                attempts, str(reason)[:500], int(time.time() * 1000),
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False


# ── the drain ────────────────────────────────────────────────────────────────

def _handle_promoted(memory, ledger):
    """Promote-result → estate write with dedup. Returns (ok, err)."""
    if memory["content_hash"] in ledger:
        return True, "dedup"
    memory_id, err = estate_memory._capture_one({
        "content": memory["content"],
        "kind": memory["kind"],
        "tier": memory["tier"],
        "about": memory["about"],
    })
    if memory_id:
        ledger[memory["content_hash"]] = memory_id
        return True, None
    return False, err


def _drain_replays(conn, cursor_id, ledger):
    """Honor `wicked-bus dlq replay` — mirror subscribe()'s drainReplays():
    one attempt per replayed row; success deletes the DLQ row, failure clears
    the replay mark and bumps attempts/last_error so the operator can re-replay
    after fixing the fault. Returns (replayed, failed)."""
    replayed = failed = 0
    while True:
        try:
            row = conn.execute(
                """SELECT dl_id, event_id, event_type, domain, subdomain, payload, emitted_at
                     FROM dead_letters
                    WHERE cursor_id = ? AND replay_requested_at IS NOT NULL
                    ORDER BY dl_id ASC LIMIT 1""",
                (cursor_id,),
            ).fetchone()
        except sqlite3.Error:
            return replayed, failed
        if not row:
            return replayed, failed
        event = {
            "event_id": row["event_id"], "event_type": row["event_type"],
            "domain": row["domain"], "subdomain": row["subdomain"],
            "payload": row["payload"], "emitted_at": row["emitted_at"],
        }
        memory, _skip = promote_fact(event)
        ok, err = (True, "skip") if memory is None else _handle_promoted(memory, ledger)
        try:
            if ok:
                conn.execute("DELETE FROM dead_letters WHERE dl_id = ?", (row["dl_id"],))
                conn.commit()
                replayed += 1
            else:
                conn.execute(
                    """UPDATE dead_letters
                          SET replay_requested_at = NULL,
                              attempts = attempts + 1,
                              last_error = ?
                        WHERE dl_id = ?""",
                    (str(err)[:500], row["dl_id"]),
                )
                conn.commit()
                failed += 1
                return replayed, failed  # stop on failure; operator re-replays
        except sqlite3.Error:
            return replayed, failed


def do_drain(_args):
    # 1. Pull pending events without moving the durable cursor.
    code, out = _run_cli(
        "subscribe", "--plugin", PLUGIN, "--filter", FACT_FILTER,
        "--once", "--no-ack",
    )
    if code != 0:
        _emit({"ok": False, "reason": "wicked-bus unavailable or drain failed"})
        return 0
    events = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("event_id") is not None:
            events.append(obj)
    events.sort(key=lambda e: e["event_id"])

    conn = _bus_db()
    cursor = _find_cursor(conn) if conn else None
    if not cursor:
        # The subscribe call registers the cursor, so this is only reachable
        # when the DB is unreadable — degrade (events redeliver next drain).
        if conn:
            conn.close()
        if events:
            _emit({"ok": False, "reason": "subscriber cursor not found in bus db"})
        else:
            _emit({"ok": True, "drained": 0, "stored": 0, "deduped": 0,
                   "skipped": 0, "dead_lettered": 0, "replayed": 0,
                   "replay_failed": 0, "pending_retry": False})
        return 0
    cursor_id, subscription_id, floor = cursor

    ledger = _load_ledger()
    replayed, replay_failed = _drain_replays(conn, cursor_id, ledger)
    stored = deduped = skipped = dead = 0
    advance_to = floor
    pending_retry = False

    for event in events:
        event_id = event["event_id"]
        memory, _skip_reason = promote_fact(event)

        if memory is None:
            skipped += 1
            advance_to = event_id
            continue

        ok, err = _handle_promoted(memory, ledger)
        if ok:
            if err == "dedup":
                deduped += 1
            else:
                stored += 1
                _clear_attempts(conn, cursor_id, event_id)
            advance_to = event_id
            continue

        # Estate write failed — retry budget, then native dead-letter.
        attempts = _get_attempts(conn, cursor_id, event_id) + 1
        if attempts >= MAX_ATTEMPTS:
            if _dead_letter(conn, cursor_id, subscription_id, event, attempts, err):
                _clear_attempts(conn, cursor_id, event_id)
                dead += 1
                advance_to = event_id
                continue
            # Could not even dead-letter — leave the cursor put and stop.
            _record_attempt(conn, cursor_id, event_id, attempts, err)
            pending_retry = True
            break
        _record_attempt(conn, cursor_id, event_id, attempts, err)
        pending_retry = True
        break  # do not advance past a retryable failure (at-least-once)

    # 2. Advance the durable cursor past everything conclusively handled.
    if advance_to > floor:
        _run_cli("ack", "--cursor-id", cursor_id, "--last-event-id", str(advance_to))
    conn.close()
    _save_ledger(ledger)

    _emit({"ok": True, "drained": len(events), "stored": stored,
           "deduped": deduped, "skipped": skipped, "dead_lettered": dead,
           "replayed": replayed, "replay_failed": replay_failed,
           "pending_retry": pending_retry})
    return 0


def do_status(_args):
    out = {"ok": True, "plugin": PLUGIN, "filter": FACT_FILTER,
           "ledger_size": len(_load_ledger())}
    conn = _bus_db()
    if conn:
        cursor = _find_cursor(conn)
        if cursor:
            cursor_id, _, floor = cursor
            out["cursor_id"] = cursor_id
            out["cursor_last_event_id"] = floor
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM dead_letters WHERE cursor_id = ?",
                    (cursor_id,),
                ).fetchone()
                out["dead_letters"] = int(row["c"])
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM events WHERE event_type = ? AND event_id > ?",
                    (FACT_FILTER, floor),
                ).fetchone()
                out["pending"] = int(row["c"])
            except sqlite3.Error:
                pass
        else:
            out["cursor_id"] = None
        conn.close()
    else:
        out["bus"] = "unavailable"
    _emit(out)
    return 0


_ACTIONS = {"drain": do_drain, "status": do_status}


def main(argv):
    if not argv or argv[0] not in _ACTIONS:
        _emit({"error": "usage: auto_memorize.py <drain|status> ['<json-args>']"})
        return 1
    raw = argv[1] if len(argv) > 1 else "{}"
    try:
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        args = {}
    return _ACTIONS[argv[0]](args if isinstance(args, dict) else {})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
