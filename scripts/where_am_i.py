#!/usr/bin/env python3
"""
where_am_i.py — Emit a compact path manifest for the current session.

Resolves the five storage roots used by wicked-garden subagent dispatches
so callers don't have to re-enumerate them in every prompt:

  1. plugin_root       — the wicked-garden plugin checkout
  2. source_cwd        — the working directory at invocation
  3. project_artifacts — ~/.something-wicked/wicked-garden/projects/{slug}/...
  4. brain             — ~/.wicked-brain/projects/{basename}/_meta/config.json
  5. bus_db            — ~/.something-wicked/wicked-bus/bus.db

Usage:
    where_am_i.py            # JSON manifest (default)
    where_am_i.py --fence    # wrap in ```json fence
    where_am_i.py --env      # substitute env-var forms (e.g. $CLAUDE_PLUGIN_ROOT)

Fail-open contract: any resolution failure emits `null` for that field and
a one-line note on stderr; the script never raises to the caller.

Provenance: Issue #576 — reduce per-dispatch prompt bloat.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Named constants — avoid magic strings.
_ENV_PLUGIN_ROOT = "CLAUDE_PLUGIN_ROOT"
_CREW_DOMAIN = "wicked-crew"
_CREW_PROJECTS_SUB = "projects"
_BRAIN_ROOT = Path.home() / ".wicked-brain"
_BRAIN_PROJECTS = _BRAIN_ROOT / "projects"
_BRAIN_META_CONFIG = Path("_meta") / "config.json"
_ROOT_BRAIN_CONFIG = _BRAIN_ROOT / "_meta" / "config.json"
_BUS_DB_PATH = Path.home() / ".something-wicked" / "wicked-bus" / "bus.db"

_FENCE_OPEN = "```json"
_FENCE_CLOSE = "```"

# Ensure scripts/ is importable when invoked directly.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))


def _note(msg: str) -> None:
    """Emit a single-line stderr note; never raises."""
    try:
        sys.stderr.write(f"[where-am-i] {msg}\n")
    except OSError:
        pass  # fail open — stderr unavailable is non-fatal


def _resolve_plugin_root() -> str | None:
    """Return the plugin checkout path, preferring CLAUDE_PLUGIN_ROOT."""
    env_val = os.environ.get(_ENV_PLUGIN_ROOT)
    if env_val:
        return env_val
    try:
        # Fail-safe: the helper lives at <plugin_root>/scripts/where_am_i.py
        return str(Path(__file__).resolve().parents[1])
    except (OSError, IndexError) as exc:
        _note(f"plugin_root fallback failed: {exc}")
        return None


def _resolve_source_cwd() -> str | None:
    """Return the caller's working directory."""
    try:
        return os.getcwd()
    except OSError as exc:
        _note(f"source_cwd unresolved: {exc}")
        return None


def _resolve_project_artifacts() -> tuple[str | None, str | None]:
    """Resolve (project_artifacts_path, active_project_id).

    When SessionState.active_project_id is set, returns the project-specific
    artifacts directory; otherwise returns the crew projects domain root.
    """
    try:
        from _paths import get_local_path
    except Exception as exc:
        _note(f"_paths import failed: {exc}")
        return None, None

    try:
        from _session import SessionState
        state = SessionState.load()
        active_id = state.active_project_id
    except Exception as exc:
        _note(f"SessionState load failed: {exc}")
        active_id = None

    try:
        base = get_local_path(_CREW_DOMAIN, _CREW_PROJECTS_SUB)
    except Exception as exc:
        _note(f"get_local_path failed: {exc}")
        return None, active_id

    if active_id:
        return str(base / active_id), active_id
    return str(base), active_id


def _resolve_brain() -> dict | None:
    """Resolve brain config path + port for the current cwd.

    Prefers the project brain at ~/.wicked-brain/projects/{cwd_basename}/.
    Falls back to the root brain config. Returns None when neither exists.
    """
    try:
        cwd_name = Path(os.getcwd()).name
    except OSError as exc:
        _note(f"brain cwd basename failed: {exc}")
        cwd_name = ""

    candidates: list[Path] = []
    if cwd_name:
        candidates.append(_BRAIN_PROJECTS / cwd_name / _BRAIN_META_CONFIG)
    candidates.append(_ROOT_BRAIN_CONFIG)

    for cfg_path in candidates:
        if not cfg_path.is_file():
            continue
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError) as exc:
            _note(f"brain config read failed at {cfg_path}: {exc}")
            continue
        port_val = cfg.get("server_port")
        try:
            port = int(port_val) if port_val is not None else None
        except (TypeError, ValueError):
            port = None
        # cfg_path is .../<project>/_meta/config.json — emit the project dir.
        brain_path = cfg.get("brain_path") or str(cfg_path.parent.parent)
        return {"path": brain_path, "port": port}

    _note("brain config not found")
    return None


def _resolve_bus_db() -> str | None:
    """Return the bus DB path if present, else None."""
    try:
        if _BUS_DB_PATH.is_file():
            return str(_BUS_DB_PATH)
    except OSError as exc:
        _note(f"bus_db stat failed: {exc}")
        return None
    _note("bus_db not present")
    return None


def build_manifest() -> dict:
    """Compose the manifest dict. Never raises."""
    plugin_root = _resolve_plugin_root()
    source_cwd = _resolve_source_cwd()
    project_artifacts, active_project_id = _resolve_project_artifacts()
    brain = _resolve_brain()
    bus_db = _resolve_bus_db()

    return {
        "plugin_root": plugin_root,
        "source_cwd": source_cwd,
        "active_project_id": active_project_id,
        "project_artifacts": project_artifacts,
        "brain": brain,
        "bus_db": bus_db,
    }


def apply_env_substitutions(manifest: dict) -> dict:
    """Replace concrete paths with env-var forms when the env is present.

    Currently maps plugin_root -> $CLAUDE_PLUGIN_ROOT. Other fields stay
    as-is so consumers still get usable absolute paths.
    """
    out = dict(manifest)
    env_plugin = os.environ.get(_ENV_PLUGIN_ROOT)
    if env_plugin and out.get("plugin_root") == env_plugin:
        out["plugin_root"] = f"${_ENV_PLUGIN_ROOT}"
    return out


def render(manifest: dict, *, fence: bool) -> str:
    """Serialize the manifest to JSON, optionally fenced for paste."""
    body = json.dumps(manifest, indent=2, sort_keys=True)
    if fence:
        return f"{_FENCE_OPEN}\n{body}\n{_FENCE_CLOSE}"
    return body


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="where_am_i",
        description="Emit a compact path manifest for the current session.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit JSON manifest (default).",
    )
    parser.add_argument(
        "--fence",
        action="store_true",
        help="Wrap the JSON manifest in a ```json fence.",
    )
    parser.add_argument(
        "--env",
        action="store_true",
        help="Substitute env-var forms (e.g. $CLAUDE_PLUGIN_ROOT).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    manifest = build_manifest()
    if args.env:
        manifest = apply_env_substitutions(manifest)
    output = render(manifest, fence=args.fence)
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
