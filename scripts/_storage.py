#!/usr/bin/env python3
"""
_storage.py — StorageManager: unified interface for data operations.

Domain scripts call StorageManager — never the control plane directly.
This isolates all fallback logic in one place.

Three modes (set in config.json):
    remote:        CP on a team server (required, local for reads only)
    local-install: CP on localhost (default, local fallback on miss)
    offline:       Local JSON files always, every write queued for replay

Storage paths:
    Local:  ~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json
    Queue:  ~/.something-wicked/wicked-garden/local/_queue.jsonl
    Failed: ~/.something-wicked/wicked-garden/local/_queue_failed.jsonl

Conflict resolution on queue drain:
    - create: dedup-before-create (list by business keys, skip if match exists)
    - update/delete: append-wins (last write wins, idempotent by ID)

Usage:
    from _storage import StorageManager

    sm = StorageManager("wicked-mem")
    items = sm.list("memories", project="my-project")
    item  = sm.get("memories", "abc123")
    new   = sm.create("memories", {"title": "...", "content": "..."})
    sm.update("memories", "abc123", {"title": "new title"})
    sm.delete("memories", "abc123")

    # For truly ephemeral files (caches, temp session state) only:
    from _storage import get_local_path
    cache_dir = get_local_path("wicked-smaht", "cache", "context7")
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Internal import — same scripts/ directory
sys.path.insert(0, str(Path(__file__).parent))
from _control_plane import get_client, load_config
from _schema_adapters import to_cp as _to_cp, from_cp as _from_cp, set_cp_client as _set_cp_client
from _session import SessionState

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_LOCAL_ROOT = Path.home() / ".something-wicked" / "wicked-garden" / "local"
_QUEUE_FILE = _LOCAL_ROOT / "_queue.jsonl"
_QUEUE_FAILED_FILE = _LOCAL_ROOT / "_queue_failed.jsonl"

# Migration-mode compatibility shim path prefix (gated by config flag)
_LEGACY_ROOT = Path.home() / ".something-wicked"

# ---------------------------------------------------------------------------
# Dedup keys: (domain, source) → list of business key field names.
# Used by drain_queue() to skip creating duplicates that already exist in CP.
# ---------------------------------------------------------------------------

_DEDUP_KEYS: dict[tuple[str, str], list[str]] = {
    ("wicked-mem", "memories"): ["title", "scope", "project"],
    ("wicked-crew", "projects"): ["name"],
    ("wicked-kanban", "tasks"): ["subject", "initiative_id"],
    ("wicked-kanban", "initiatives"): ["name"],
    ("wicked-jam", "sessions"): ["name", "project"],
}

# ---------------------------------------------------------------------------
# Valid modes
# ---------------------------------------------------------------------------

_VALID_MODES = frozenset({"remote", "local-install", "offline"})


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_local_path(domain: str, *subpath: str) -> Path:
    """Delegate to _paths.get_local_path — see _paths.py for docs."""
    from _paths import get_local_path as _glp
    return _glp(domain, *subpath)


def get_local_file(domain: str, *subpath: str) -> Path:
    """Delegate to _paths.get_local_file — see _paths.py for docs."""
    from _paths import get_local_file as _glf
    return _glf(domain, *subpath)


def drain_offline_queue(domain: str = "wicked-garden", *, hook_mode: bool = False) -> tuple[int, int]:
    """Convenience wrapper: instantiate StorageManager and drain the offline queue.

    Called by bootstrap.py at session start and by prompt_submit.py on
    mid-session reconnect.

    Returns:
        (replayed, failed) counts.
    """
    sm = StorageManager(domain, hook_mode=hook_mode)
    return sm.drain_queue()


# ---------------------------------------------------------------------------
# StorageManager
# ---------------------------------------------------------------------------


class StorageManager:
    """Unified read/write interface for plugin data.

    Mode routing:
        remote / local-install: CP primary, local fallback, queue on miss.
        offline: local always, every write enqueued for future replay.

    The mode is read from config.json at construction time. Callers do not
    need to know or care about the mode — the API is identical.
    """

    def __init__(self, domain: str, *, hook_mode: bool = False):
        """
        Args:
            domain:    Plugin domain, e.g. "wicked-mem", "wicked-kanban".
            hook_mode: Pass True from hook scripts to use shorter CP timeouts.
        """
        self._domain = domain
        self._hook_mode = hook_mode
        self._cp = get_client(hook_mode=hook_mode)
        self._cfg = load_config()
        self._mode = self._cfg.get("mode") or "local-install"
        if self._mode not in _VALID_MODES:
            self._mode = "local-install"
        # Inject CP client into schema adapters for manifest_detail lookups
        _set_cp_client(self._cp)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list(self, source: str, **params) -> list[dict]:
        """List records for a source, with optional filter params.

        Returns:
            List of record dicts. Empty list on any error.
        """
        if self._should_use_cp():
            result = self._cp.request(
                self._domain, source, "list", params=params or None
            )
            if result is not None:
                items = _extract_list(result)
                return [_from_cp(self._domain, source, "list", r) for r in items]
            return []

        return self._local_list(source, params)

    def get(self, source: str, id: str) -> dict | None:
        """Fetch a single record by ID.

        Returns:
            Record dict, or None if not found.
        """
        if self._should_use_cp():
            result = self._cp.request(self._domain, source, "get", id=id)
            if result is not None:
                item = _extract_item(result)
                return _from_cp(self._domain, source, "get", item) if item else None
            return None

        return self._local_get(source, id)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, source: str, payload: dict) -> dict | None:
        """Create a new record.

        Returns:
            Created record dict, or None on failure.
        """
        if self._should_use_cp():
            cp_payload = _to_cp(self._domain, source, "create", dict(payload))
            result = self._cp.request(
                self._domain, source, "create", payload=cp_payload
            )
            if result is not None:
                item = _extract_item(result)
                return _from_cp(self._domain, source, "create", item) if item else None
            return None

        # Offline / CP down: local write + queue for later replay.
        record = dict(payload)
        if "id" not in record:
            record["id"] = str(uuid.uuid4())
        record.setdefault("created_at", _now())
        record.setdefault("updated_at", _now())

        self._local_write(source, record["id"], record)
        cp_record = _to_cp(self._domain, source, "create", dict(record))
        self._enqueue("create", source, cp_record)
        return record

    def update(self, source: str, id: str, diff: dict) -> dict | None:
        """Patch an existing record with the fields in diff.

        Returns:
            Updated record dict, or None if not found.
        """
        if self._should_use_cp():
            cp_diff = _to_cp(self._domain, source, "update", dict(diff))
            result = self._cp.request(
                self._domain, source, "update", id=id, payload=cp_diff
            )
            if result is not None:
                item = _extract_item(result)
                return _from_cp(self._domain, source, "update", item) if item else None
            return None

        # Offline / CP down: local read-modify-write + queue.
        existing = self._local_get(source, id)
        if existing is None:
            return None

        existing.update(diff)
        existing["updated_at"] = _now()
        self._local_write(source, id, existing)
        cp_diff = _to_cp(self._domain, source, "update", {"id": id, **diff})
        self._enqueue("update", source, cp_diff)
        return existing

    def delete(self, source: str, id: str) -> bool:
        """Delete a record.

        Returns:
            True if the record was found and removed/marked deleted.
        """
        if self._should_use_cp():
            result = self._cp.request(self._domain, source, "delete", id=id)
            if result is not None:
                return True
            return False

        # Offline / CP down: soft-delete locally + queue.
        existing = self._local_get(source, id)
        if existing is None:
            return False

        existing["deleted"] = True
        existing["deleted_at"] = _now()
        self._local_write(source, id, existing)
        self._enqueue("delete", source, {"id": id})
        return True

    # ------------------------------------------------------------------
    # Queue drain
    # ------------------------------------------------------------------

    def drain_queue(self) -> tuple[int, int]:
        """Replay queued offline writes against the control plane.

        Called by bootstrap.py on successful health check and by
        prompt_submit.py on mid-session reconnect.

        Conflict resolution:
            - create with dedup_keys: list CP by business keys first,
              skip if a matching record already exists.
            - create without dedup_keys: proceed directly (old queue entries).
            - update/delete: append-wins (last write wins).

        Failed entries are moved to _queue_failed.jsonl with an error note.

        Returns:
            (replayed: int, failed: int) counts.
        """
        if not _QUEUE_FILE.exists():
            return 0, 0

        lines = _QUEUE_FILE.read_text(encoding="utf-8").splitlines()
        if not lines:
            return 0, 0

        replayed = 0
        failed_entries: list[str] = []

        for raw_line in lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                failed_entries.append(
                    json.dumps({"raw": raw_line, "error": "invalid JSON in queue"})
                )
                continue

            verb = entry.get("verb")
            domain = entry.get("domain")
            source = entry.get("source")
            payload = entry.get("payload", {})
            record_id = payload.get("id")
            dedup_keys = entry.get("dedup_keys")

            try:
                if verb == "create":
                    # Dedup-before-create: check if record already exists in CP
                    if dedup_keys and self._dedup_exists(domain, source, dedup_keys):
                        replayed += 1  # count as "handled" — record is already there
                        continue
                    result = self._cp.request(domain, source, "create", payload=payload)
                elif verb == "update" and record_id:
                    diff = {k: v for k, v in payload.items() if k != "id"}
                    result = self._cp.request(
                        domain, source, "update", id=record_id, payload=diff
                    )
                elif verb == "delete" and record_id:
                    result = self._cp.request(domain, source, "delete", id=record_id)
                else:
                    result = None
            except Exception as exc:
                result = None
                print(
                    f"[wicked-garden] Queue drain error for {verb} {source}/{record_id}: {exc}",
                    file=sys.stderr,
                )

            if result is not None:
                replayed += 1
            else:
                entry["_drain_failed_at"] = _now()
                entry["_error"] = "control plane returned None"
                failed_entries.append(json.dumps(entry))

        # Clear the processed queue
        _QUEUE_FILE.unlink(missing_ok=True)

        # Persist failures for manual inspection
        if failed_entries:
            _QUEUE_FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _QUEUE_FAILED_FILE.open("a", encoding="utf-8") as fh:
                for line in failed_entries:
                    fh.write(line + "\n")

        return replayed, len(failed_entries)

    # ------------------------------------------------------------------
    # Migration compatibility shim
    # ------------------------------------------------------------------

    def _compat_read_legacy(self, source: str, id: str) -> dict | None:
        """Read from old plugin storage layout during migration window.

        Only active when config flag migration_mode == true. The legacy path
        is: ~/.something-wicked/wicked-{domain}/...
        """
        if not self._cfg.get("migration_mode"):
            return None

        legacy_path = _LEGACY_ROOT / self._domain / source / f"{id}.json"
        if not legacy_path.exists():
            return None

        try:
            return json.loads(legacy_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Private: mode-aware CP availability
    # ------------------------------------------------------------------

    def _should_use_cp(self) -> bool:
        """Return True if the current mode and session state allow CP access.

        offline mode: always False (never call CP).
        remote/local-install: True when session reports CP is available.
        """
        if self._mode == "offline":
            return False
        try:
            state = SessionState.load()
            return state.cp_available and not state.fallback_mode
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Private: dedup check for queue drain
    # ------------------------------------------------------------------

    def _dedup_exists(self, domain: str, source: str, dedup_keys: dict) -> bool:
        """Check if a record matching dedup_keys already exists in CP.

        Returns True if a matching record is found (create should be skipped).
        Returns False on any error (proceed with create — fail open).
        """
        try:
            result = self._cp.request(
                domain, source, "list", params=dedup_keys
            )
            if result is not None:
                records = _extract_list(result)
                return len(records) > 0
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Private: local file operations
    # ------------------------------------------------------------------

    def _local_dir(self, source: str) -> Path:
        return _LOCAL_ROOT / self._domain / source

    def _local_file(self, source: str, id: str) -> Path:
        return self._local_dir(source) / f"{id}.json"

    def _local_list(self, source: str, params: dict) -> list[dict]:
        """Scan local JSON files and return non-deleted records."""
        source_dir = self._local_dir(source)
        if not source_dir.exists():
            return []

        records: list[dict] = []
        for json_file in sorted(source_dir.glob("*.json")):
            try:
                record = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            # Skip soft-deleted records
            if record.get("deleted"):
                continue

            # Apply simple equality filters from params
            if not _matches_params(record, params):
                continue

            records.append(record)

        return records

    def _local_get(self, source: str, id: str) -> dict | None:
        """Read a single local JSON file. Falls back to legacy path."""
        path = self._local_file(source, id)

        if path.exists():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("deleted"):
                    return None
                return record
            except (json.JSONDecodeError, OSError):
                return None

        # Try migration legacy path
        return self._compat_read_legacy(source, id)

    def _local_write(self, source: str, id: str, record: dict) -> None:
        """Atomically write a record to its local JSON file."""
        path = self._local_file(source, id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            print(
                f"[wicked-garden] Local write failed for {source}/{id}: {exc}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Private: offline queue
    # ------------------------------------------------------------------

    def _enqueue(self, verb: str, source: str, payload: dict) -> None:
        """Append a write operation to the offline queue.

        Stamps dedup_keys from _DEDUP_KEYS when available, so drain_queue()
        can skip duplicates on replay.
        """
        entry: dict[str, Any] = {
            "queued_at": _now(),
            "domain": self._domain,
            "source": source,
            "verb": verb,
            "payload": payload,
        }

        # Stamp dedup keys for create operations
        if verb == "create":
            key_fields = _DEDUP_KEYS.get((self._domain, source))
            if key_fields:
                dedup = {}
                for field in key_fields:
                    val = payload.get(field)
                    if val is not None:
                        dedup[field] = val
                if dedup:
                    entry["dedup_keys"] = dedup

        _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with _QUEUE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to enqueue {verb} {source}: {exc}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_list(response: dict) -> list[dict]:
    """Pull the data array from a control plane envelope."""
    data = response.get("data", [])
    if isinstance(data, list):
        return data
    return []


def _extract_item(response: dict) -> dict | None:
    """Pull the single record from a control plane envelope."""
    data = response.get("data")
    if isinstance(data, dict):
        return data
    return None


def _matches_params(record: dict, params: dict) -> bool:
    """Simple equality filter for local list queries.

    Only string/int/bool equality is supported — complex filter expressions
    go through the control plane.
    """
    for key, value in params.items():
        if record.get(key) != value:
            return False
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
