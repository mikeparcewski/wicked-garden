#!/usr/bin/env python3
"""
_paths.py — Lightweight local storage path resolution.

Zero transitive dependencies. Safe to import from any script including hooks.
For full CP-backed storage operations (with offline queue), use _storage.py.

All domain data goes through the Control Plane when available.
Local path is the offline fallback only:
    ~/.something-wicked/wicked-garden/local/{domain}/{subpath}

Legacy fallback: if data exists at the old per-plugin location
(~/.something-wicked/{domain}/...) but not at the unified location,
returns the legacy path so existing data is found.
"""

from pathlib import Path

_LOCAL_ROOT = Path.home() / ".something-wicked" / "wicked-garden" / "local"
_LEGACY_ROOT = Path.home() / ".something-wicked"


def get_local_path(domain: str, *subpath: str) -> Path:
    """Return a directory path under the wicked-garden local root.

    This is the offline fallback location. CP is the primary store.
    Creates the directory if it does not exist.

    Example:
        get_local_path("wicked-crew", "projects")
        # → ~/.something-wicked/wicked-garden/local/wicked-crew/projects/
    """
    new_p = _LOCAL_ROOT / domain
    for part in subpath:
        new_p = new_p / part

    legacy_p = _LEGACY_ROOT / domain
    for part in subpath:
        legacy_p = legacy_p / part
    if legacy_p.is_dir() and not new_p.exists():
        return legacy_p

    new_p.mkdir(parents=True, exist_ok=True)
    return new_p


def get_local_file(domain: str, *subpath: str) -> Path:
    """Return a file path under the wicked-garden local root.

    This is the offline fallback location. CP is the primary store.
    Parent directories are created automatically. Does not create the file.

    Example:
        get_local_file("wicked-search", "unified_search.db")
        # → ~/.something-wicked/wicked-garden/local/wicked-search/unified_search.db
    """
    new_p = _LOCAL_ROOT / domain
    for part in subpath:
        new_p = new_p / part

    legacy_p = _LEGACY_ROOT / domain
    for part in subpath:
        legacy_p = legacy_p / part
    if legacy_p.is_file() and not new_p.exists():
        return legacy_p

    new_p.parent.mkdir(parents=True, exist_ok=True)
    return new_p
