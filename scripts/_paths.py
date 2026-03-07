#!/usr/bin/env python3
"""
_paths.py — Lightweight local storage path resolution.

Zero transitive dependencies. Safe to import from any script including hooks.

Storage is project-scoped: each working directory gets its own isolated state.
Project identity is derived from the resolved cwd at import time.

Layout:
    ~/.something-wicked/wicked-garden/projects/{project-slug}/{domain}/{subpath}

Global (shared across projects):
    ~/.something-wicked/wicked-garden/config.json
"""

import hashlib
import os
from pathlib import Path

_WG_ROOT = Path.home() / ".something-wicked" / "wicked-garden"
_PROJECTS_ROOT = _WG_ROOT / "projects"


def _get_project_slug() -> str:
    """Derive a stable, human-readable project slug from the working directory.

    Format: {dir-name}-{hash[:8]}
    The hash ensures uniqueness even for directories with the same name
    in different locations (e.g., ~/Projects/foo vs ~/work/foo).
    """
    cwd = Path(os.environ.get("CLAUDE_CWD", os.getcwd())).resolve()
    dir_name = cwd.name.lower().replace(" ", "-")[:32]
    path_hash = hashlib.sha256(str(cwd).encode()).hexdigest()[:8]
    return f"{dir_name}-{path_hash}"


def _get_project_root() -> Path:
    """Return the project-scoped storage root."""
    return _PROJECTS_ROOT / _get_project_slug()


# Project-scoped local root
_LOCAL_ROOT = _get_project_root()


def get_project_slug() -> str:
    """Public accessor for the current project slug."""
    return _get_project_slug()


def get_project_root() -> Path:
    """Public accessor for the current project storage root."""
    return _get_project_root()


def get_local_path(domain: str, *subpath: str) -> Path:
    """Return a directory path under the project-scoped storage root.

    Creates the directory if it does not exist.

    Example:
        get_local_path("wicked-crew", "projects")
        # → ~/.something-wicked/wicked-garden/projects/{slug}/wicked-crew/projects/
    """
    p = _LOCAL_ROOT / domain
    for part in subpath:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_local_file(domain: str, *subpath: str) -> Path:
    """Return a file path under the project-scoped storage root.

    Parent directories are created automatically. Does not create the file.

    Example:
        get_local_file("wicked-search", "unified_search.db")
        # → ~/.something-wicked/wicked-garden/projects/{slug}/wicked-search/unified_search.db
    """
    p = _LOCAL_ROOT / domain
    for part in subpath:
        p = p / part
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def list_projects() -> list[dict]:
    """List all known projects with their slugs and sizes."""
    if not _PROJECTS_ROOT.exists():
        return []
    results = []
    for project_dir in sorted(_PROJECTS_ROOT.iterdir()):
        if not project_dir.is_dir():
            continue
        size = sum(f.stat().st_size for f in project_dir.rglob("*") if f.is_file())
        domains = [d.name for d in project_dir.iterdir() if d.is_dir()]
        results.append({
            "slug": project_dir.name,
            "path": str(project_dir),
            "domains": domains,
            "size_bytes": size,
            "is_current": project_dir.name == _get_project_slug(),
        })
    return results
