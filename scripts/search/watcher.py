#!/usr/bin/env python3
"""
watcher.py — Directory watcher for stale search index detection.

Uses polling via os.stat() mtime for broad compatibility. Optionally uses
watchdog if available for event-driven watching.

Commands:
  check [--dirs D1 D2...] [--state PATH] [--json]   One-shot check for changes
  status [--dirs D1 D2...] [--state PATH] [--json]  Show watcher state summary

Integration:
  The SessionStart hook can invoke `watcher.py check` to detect stale indexes
  before a user session begins.

Usage examples:
  watcher.py check --dirs /path/to/project --state /tmp/watcher-state.json
  watcher.py check --dirs /path/to/project --state /tmp/watcher-state.json --json
  watcher.py status --dirs /path/to/project --state /tmp/watcher-state.json --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional watchdog integration
# ---------------------------------------------------------------------------

try:
    from watchdog.observers import Observer  # type: ignore
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None  # type: ignore

# ---------------------------------------------------------------------------
# Logging integration
# ---------------------------------------------------------------------------

# Add parent scripts/ dir so we can import shared modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from _logger import log as _ops_log
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False

    def _ops_log(domain, level, event, ok=True, ms=None, detail=None):  # type: ignore
        pass


def _log(level: str, event: str, ok: bool = True, ms: float | None = None, detail: dict | None = None) -> None:
    _ops_log("search", level, event, ok=ok, ms=ms, detail=detail)


# ---------------------------------------------------------------------------
# File extensions that are considered indexable source files
# ---------------------------------------------------------------------------

_INDEXABLE_EXTENSIONS = {
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".cs",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".php", ".swift", ".kt", ".scala",
    # Docs
    ".md", ".markdown", ".rst", ".txt", ".html", ".htm",
}

_SKIP_DIRS = {
    ".git", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".tox", ".eggs",
}


# ---------------------------------------------------------------------------
# MtimeCache — the persisted state
# ---------------------------------------------------------------------------

class MtimeCache:
    """Snapshot of file mtimes for a set of directories.

    Persisted as JSON with schema:
    {
        "version": "1.0",
        "checked_at": "<iso8601>",
        "dirs": ["..."],
        "files": {
            "/abs/path/to/file.py": {"mtime": 1234567890.1, "size": 1024}
        }
    }
    """

    VERSION = "1.0"

    def __init__(self, dirs: List[str], files: Dict[str, dict] | None = None, checked_at: str | None = None):
        self.dirs = dirs
        self.files: Dict[str, dict] = files or {}
        self.checked_at: str = checked_at or datetime.now(timezone.utc).isoformat()

    @classmethod
    def empty(cls, dirs: List[str]) -> "MtimeCache":
        return cls(dirs=dirs, files={}, checked_at=None)

    @classmethod
    def from_json(cls, data: dict) -> "MtimeCache":
        return cls(
            dirs=data.get("dirs", []),
            files=data.get("files", {}),
            checked_at=data.get("checked_at"),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.VERSION,
            "checked_at": self.checked_at,
            "dirs": self.dirs,
            "files": self.files,
        }


# ---------------------------------------------------------------------------
# DirectoryWatcher
# ---------------------------------------------------------------------------

class DirectoryWatcher:
    """Polling-based directory watcher for mtime-change detection.

    Args:
        watched_dirs: List of directory paths to watch.
        debounce_seconds: Minimum seconds between batching rapid changes.
            Not enforced in one-shot `check_changes()` mode — relevant for
            continuous watching loops.
    """

    def __init__(self, watched_dirs: List[str], debounce_seconds: float = 5.0):
        self.watched_dirs = [str(Path(d).resolve()) for d in watched_dirs]
        self.debounce_seconds = debounce_seconds
        self._last_check_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_changes(self, previous_cache: MtimeCache) -> Tuple[List[str], MtimeCache]:
        """Compare current filesystem state against a previous cache.

        Returns:
            (changed_files, new_cache): List of changed/added file paths and
            an updated MtimeCache representing the current state.
        """
        t0 = time.monotonic()
        current_files = self._scan_dirs()
        changed: List[str] = []

        for path, stat_info in current_files.items():
            if path not in previous_cache.files:
                # New file
                changed.append(path)
            else:
                prev = previous_cache.files[path]
                if stat_info["mtime"] != prev.get("mtime") or stat_info["size"] != prev.get("size"):
                    changed.append(path)

        # Deleted files are noted but not included in "changed" — the indexer
        # handles removal separately via IncrementalUpdater.remove_file().
        deleted = [p for p in previous_cache.files if p not in current_files]

        new_cache = MtimeCache(
            dirs=self.watched_dirs,
            files=current_files,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

        elapsed_ms = (time.monotonic() - t0) * 1000
        _log(
            "verbose",
            "watcher.check.complete",
            detail={
                "dirs": self.watched_dirs,
                "changed": len(changed),
                "deleted": len(deleted),
                "total_files": len(current_files),
            },
            ms=elapsed_ms,
        )

        return changed, new_cache

    def persist_state(self, cache: MtimeCache, path: str) -> None:
        """Persist mtime cache to a JSON file.

        Args:
            cache: The cache to save.
            path: File path to write.
        """
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = state_path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")
            tmp_path.rename(state_path)
        except OSError as e:
            _log("normal", "watcher.persist.error", ok=False, detail={"error": str(e), "path": path})
            # Clean up temp file if it exists
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def load_state(self, path: str) -> MtimeCache:
        """Load mtime cache from a JSON file.

        Returns an empty cache if the file does not exist or is unreadable.

        Args:
            path: File path to read.
        """
        state_path = Path(path)
        if not state_path.exists():
            _log("verbose", "watcher.state.missing", detail={"path": path})
            return MtimeCache.empty(self.watched_dirs)

        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            return MtimeCache.from_json(data)
        except (OSError, json.JSONDecodeError) as e:
            _log("normal", "watcher.state.corrupt", ok=False, detail={"error": str(e), "path": path})
            return MtimeCache.empty(self.watched_dirs)

    def trigger_incremental_reindex(self, changed_files: List[str]) -> bool:
        """Trigger incremental reindex for a list of changed files.

        Calls the unified_search.py indexer for the specific changed files.
        Batches by watched directory to minimise subprocess calls.

        Args:
            changed_files: Absolute paths to files that changed.

        Returns:
            True if reindex succeeded for all files, False if any failed.
        """
        if not changed_files:
            return True

        t0 = time.monotonic()
        _log(
            "verbose",
            "watcher.reindex.triggered",
            detail={"files": changed_files, "count": len(changed_files)},
        )

        # Group changed files by their watched parent directory
        dir_to_files: Dict[str, List[str]] = {}
        for f in changed_files:
            parent = self._find_watched_dir(f)
            if parent:
                dir_to_files.setdefault(parent, []).append(f)
            else:
                # File outside watched dirs — use its parent dir directly
                dir_to_files.setdefault(str(Path(f).parent), []).append(f)

        import subprocess

        scripts_dir = Path(__file__).resolve().parent
        plugin_root = scripts_dir.parent.parent  # scripts/search -> scripts -> wicked-garden

        success = True
        for watched_dir, files in dir_to_files.items():
            try:
                result = subprocess.run(
                    [
                        "uv", "run", "python",
                        str(scripts_dir / "unified_search.py"),
                        "index", watched_dir,
                    ],
                    cwd=str(plugin_root),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    _log(
                        "normal",
                        "watcher.reindex.failed",
                        ok=False,
                        detail={"dir": watched_dir, "stderr": result.stderr[:500]},
                    )
                    success = False
            except (subprocess.TimeoutExpired, OSError) as e:
                _log(
                    "normal",
                    "watcher.reindex.error",
                    ok=False,
                    detail={"dir": watched_dir, "error": str(e)},
                )
                success = False

        elapsed_ms = (time.monotonic() - t0) * 1000
        _log(
            "verbose",
            "watcher.reindex.done",
            ok=success,
            ms=elapsed_ms,
            detail={"dirs_processed": len(dir_to_files)},
        )
        return success

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_dirs(self) -> Dict[str, dict]:
        """Walk watched directories and collect mtime+size for each indexable file."""
        result: Dict[str, dict] = {}
        for watched_dir in self.watched_dirs:
            dir_path = Path(watched_dir)
            if not dir_path.is_dir():
                _log(
                    "normal",
                    "watcher.scan.dir_missing",
                    ok=False,
                    detail={"dir": watched_dir},
                )
                continue

            for root, dirs, files in os.walk(watched_dir):
                # Prune skip directories in-place (modifies dirs to prevent descent)
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]

                for filename in files:
                    ext = Path(filename).suffix.lower()
                    if ext not in _INDEXABLE_EXTENSIONS:
                        continue

                    abs_path = os.path.join(root, filename)
                    try:
                        st = os.stat(abs_path)
                        result[abs_path] = {
                            "mtime": st.st_mtime,
                            "size": st.st_size,
                        }
                    except OSError:
                        # File disappeared between scan and stat — skip it
                        pass

        return result

    def _find_watched_dir(self, file_path: str) -> Optional[str]:
        """Return the watched directory that contains file_path, or None."""
        for d in self.watched_dirs:
            if file_path.startswith(d + os.sep) or file_path == d:
                return d
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="wicked-search directory watcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- check --
    check_p = sub.add_parser("check", help="One-shot check for changed files")
    check_p.add_argument(
        "--dirs", nargs="+", metavar="DIR",
        help="Directories to watch (default: current directory)",
    )
    check_p.add_argument(
        "--state", metavar="PATH",
        help="Path to state JSON file (default: ~/.something-wicked/wicked-search/watcher-state.json)",
    )
    check_p.add_argument(
        "--reindex", action="store_true",
        help="Trigger incremental reindex for changed files",
    )
    check_p.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")

    # -- status --
    status_p = sub.add_parser("status", help="Show watcher state summary")
    status_p.add_argument(
        "--dirs", nargs="+", metavar="DIR",
        help="Directories to watch (default: current directory)",
    )
    status_p.add_argument(
        "--state", metavar="PATH",
        help="Path to state JSON file",
    )
    status_p.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")

    return parser.parse_args()


def _default_state_path() -> str:
    """Resolve default state path via resolve_path.py, falling back to DomainStore convention."""
    try:
        import subprocess as _sp
        plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parents[2]))
        result = _sp.run(
            ["python3", os.path.join(plugin_root, "scripts", "resolve_path.py"), "search"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return str(Path(result.stdout.strip()) / "watcher-state.json")
    except Exception:
        pass
    # Fallback — use DomainStore path resolution
    import sys as _sys
    _scripts = str(Path(__file__).resolve().parents[1])
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)
    from _domain_store import get_local_path
    return str(get_local_path("wicked-search") / "watcher-state.json")


def _resolve_dirs(dirs: Optional[List[str]]) -> List[str]:
    if dirs:
        return [str(Path(d).resolve()) for d in dirs]
    return [str(Path.cwd())]


def cmd_check(args: argparse.Namespace) -> int:
    dirs = _resolve_dirs(args.dirs)
    state_path = args.state or _default_state_path()
    json_output: bool = args.json_output

    watcher = DirectoryWatcher(watched_dirs=dirs)

    # Load previous state
    previous_cache = watcher.load_state(state_path)

    # Detect changes
    changed_files, new_cache = watcher.check_changes(previous_cache)

    # Persist updated state
    watcher.persist_state(new_cache, state_path)

    stale = len(changed_files) > 0

    # Optionally trigger reindex
    reindex_ok: Optional[bool] = None
    if getattr(args, "reindex", False) and stale:
        reindex_ok = watcher.trigger_incremental_reindex(changed_files)

    result = {
        "stale": stale,
        "changed_files": changed_files,
        "changed_count": len(changed_files),
        "watched_dirs": dirs,
        "state_path": state_path,
        "checked_at": new_cache.checked_at,
    }
    if reindex_ok is not None:
        result["reindex_ok"] = reindex_ok

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        if stale:
            print(f"Index is STALE — {len(changed_files)} file(s) changed:")
            for f in changed_files:
                print(f"  {f}")
        else:
            print("Index is UP TO DATE — no changes detected.")
        if reindex_ok is not None:
            status = "succeeded" if reindex_ok else "FAILED"
            print(f"Incremental reindex: {status}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    dirs = _resolve_dirs(args.dirs)
    state_path = args.state or _default_state_path()
    json_output: bool = args.json_output

    watcher = DirectoryWatcher(watched_dirs=dirs)
    cache = watcher.load_state(state_path)

    result = {
        "watched_dirs": dirs,
        "state_path": state_path,
        "state_exists": Path(state_path).exists(),
        "last_checked": cache.checked_at,
        "tracked_files": len(cache.files),
        "has_watchdog": HAS_WATCHDOG,
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Watched dirs: {', '.join(dirs)}")
        print(f"State file:   {state_path}")
        print(f"State exists: {result['state_exists']}")
        print(f"Last checked: {cache.checked_at or 'never'}")
        print(f"Tracked files: {len(cache.files)}")
        print(f"Watchdog available: {HAS_WATCHDOG}")

    return 0


def main() -> int:
    args = _parse_args()

    try:
        if args.command == "check":
            return cmd_check(args)
        elif args.command == "status":
            return cmd_status(args)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        _log("normal", "watcher.cli.error", ok=False, detail={"error": str(e)})
        if os.environ.get("WICKED_DEBUG"):
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
