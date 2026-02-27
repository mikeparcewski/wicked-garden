#!/usr/bin/env python3
"""
_storage.py — StorageManager: unified interface for data operations.

Domain scripts call StorageManager — never the control plane directly.
This isolates all fallback logic in one place.

Storage hierarchy:
    Primary:  wicked-control-plane HTTP API (when available)
    Fallback: local JSON files at ~/.something-wicked/wicked-garden/local/{domain}/{source}/{id}.json
    Queue:    offline writes appended to local/_queue.jsonl, replayed on reconnect

Usage:
    from _storage import StorageManager

    sm = StorageManager("wicked-mem")
    items = sm.list("memories", project="my-project")
    item  = sm.get("memories", "abc123")
    new   = sm.create("memories", {"title": "...", "content": "..."})
    sm.update("memories", "abc123", {"title": "new title"})
    sm.delete("memories", "abc123")
"""

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
# StorageManager
# ---------------------------------------------------------------------------


class StorageManager:
    """Unified read/write interface for plugin data.

    Transparent fallback: tries the control plane first; on failure (or when
    the session is in fallback mode) uses local JSON files.  Offline writes
    are queued for later replay.
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

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list(self, source: str, **params) -> list[dict]:
        """List records for a source, with optional filter params.

        Returns:
            List of record dicts. Empty list on any error.
        """
        if self._cp_available():
            result = self._cp.request(
                self._domain, source, "list", params=params or None
            )
            if result is not None:
                return _extract_list(result)

        return self._local_list(source, params)

    def get(self, source: str, id: str) -> dict | None:
        """Fetch a single record by ID.

        Returns:
            Record dict, or None if not found.
        """
        if self._cp_available():
            result = self._cp.request(self._domain, source, "get", id=id)
            if result is not None:
                return _extract_item(result)

        return self._local_get(source, id)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, source: str, payload: dict) -> dict | None:
        """Create a new record.

        Returns:
            Created record dict, or None on failure.
        """
        if self._cp_available():
            result = self._cp.request(
                self._domain, source, "create", payload=payload
            )
            if result is not None:
                return _extract_item(result)

        # Fallback: assign a local ID and persist
        record = dict(payload)
        if "id" not in record:
            record["id"] = str(uuid.uuid4())
        record.setdefault("created_at", _now())
        record.setdefault("updated_at", _now())

        self._local_write(source, record["id"], record)
        self._enqueue("create", source, record)
        return record

    def update(self, source: str, id: str, diff: dict) -> dict | None:
        """Patch an existing record with the fields in diff.

        Returns:
            Updated record dict, or None if not found.
        """
        if self._cp_available():
            result = self._cp.request(
                self._domain, source, "update", id=id, payload=diff
            )
            if result is not None:
                return _extract_item(result)

        # Fallback: read-modify-write
        existing = self._local_get(source, id)
        if existing is None:
            return None

        existing.update(diff)
        existing["updated_at"] = _now()
        self._local_write(source, id, existing)
        self._enqueue("update", source, {"id": id, **diff})
        return existing

    def delete(self, source: str, id: str) -> bool:
        """Delete a record (soft-delete in local fallback).

        Returns:
            True if the record was found and removed/marked deleted.
        """
        if self._cp_available():
            result = self._cp.request(self._domain, source, "delete", id=id)
            if result is not None:
                return True

        # Fallback: mark deleted in local file
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

        Called by bootstrap.py on successful health check after a period of
        offline operation.

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

            try:
                if verb == "create":
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
        is: ~/.something-wicked/wicked-{domain}/... (without the wicked- prefix
        strip, since we store the full domain name like "wicked-mem").
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
        """Append a write operation to the offline queue."""
        entry = {
            "queued_at": _now(),
            "domain": self._domain,
            "source": source,
            "verb": verb,
            "payload": payload,
        }
        _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with _QUEUE_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            print(
                f"[wicked-garden] Failed to enqueue {verb} {source}: {exc}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Private: availability check
    # ------------------------------------------------------------------

    def _cp_available(self) -> bool:
        """Return True if the session has a live control plane connection."""
        try:
            state = SessionState.load()
            return state.cp_available and not state.fallback_mode
        except Exception:
            return False


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
