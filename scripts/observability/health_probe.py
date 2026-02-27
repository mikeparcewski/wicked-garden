"""
health_probe.py — CI-runnable health checker for wicked-garden plugins.

Validates all installed plugins against structural contracts:
  1. Hook event names (valid set; TaskCompleted flagged as WARNING)
  2. Script paths referenced in hooks.json commands (must exist)
  3. Cross-plugin subagent_type refs in commands/*.md and agents/*.md
  4. Ghost specialist checks (role, personas, enhances fields)
  5. plugin.json required fields (name, version, description)

Exit codes:
  0  healthy — no violations
  1  degraded — warnings only
  2  unhealthy — one or more errors

Output is persisted via StorageManager("wicked-observability").
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager

_sm = StorageManager("wicked-observability")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_HOOK_EVENTS: frozenset[str] = frozenset(
    [
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStart",
        "SubagentStop",
        "Stop",
        "PreCompact",
        "Notification",
        "PermissionRequest",
        "TeammateIdle",
        "SessionEnd",
    ]
)

# TaskCompleted is documented in some places but silently never fires.
SILENT_EVENTS: frozenset[str] = frozenset(["TaskCompleted"])

REQUIRED_PLUGIN_FIELDS: tuple[str, ...] = ("name", "version", "description")

REQUIRED_SPECIALIST_FIELDS: tuple[str, ...] = ("specialist", "personas", "enhances")

# Pattern for subagent_type references to wicked-* plugins
# Matches: subagent_type="wicked-foo:agent-name"
# Does NOT match template placeholders like wicked-{specialist}:{agent}
SUBAGENT_REF_RE = re.compile(
    r'subagent_type\s*=\s*["\']wicked-([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)["\']'
)

# Pattern for extracting a script path from a hook command string.
# Handles: python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/foo.py" --arg
# and:     cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/foo.py
SCRIPT_PATH_RE = re.compile(
    r'\$\{CLAUDE_PLUGIN_ROOT\}[/\\]([^\s"\']+\.py)'
)


# ---------------------------------------------------------------------------
# Violation dataclass (plain dict for stdlib compatibility)
# ---------------------------------------------------------------------------

def make_violation(
    plugin: str,
    vtype: str,
    severity: str,
    message: str,
    file: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    return {
        "plugin": plugin,
        "type": vtype,
        "severity": severity,
        "message": message,
        "file": file,
        "line": line,
    }


# ---------------------------------------------------------------------------
# Check 1: Hook event names
# ---------------------------------------------------------------------------

def check_hook_events(
    plugin_name: str,
    hooks_json: Path,
    hooks_data: dict[str, Any],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    hooks_block = hooks_data.get("hooks", {})

    # Normalise: dict keyed by event name, or list of objects with "event" key
    if isinstance(hooks_block, dict):
        event_names = list(hooks_block.keys())
    elif isinstance(hooks_block, list):
        event_names = [
            entry.get("event", "")
            for entry in hooks_block
            if isinstance(entry, dict) and "event" in entry
        ]
    else:
        return violations

    rel_file = _rel(hooks_json)
    for event in event_names:
        if not event:
            continue
        if event in VALID_HOOK_EVENTS:
            continue
        if event in SILENT_EVENTS:
            violations.append(
                make_violation(
                    plugin=plugin_name,
                    vtype="invalid_event",
                    severity="warning",
                    message=(
                        f"Hook event '{event}' is documented but silently never fires "
                        "in the Claude Code runtime. Scripts bound to it will not execute."
                    ),
                    file=rel_file,
                )
            )
        else:
            violations.append(
                make_violation(
                    plugin=plugin_name,
                    vtype="invalid_event",
                    severity="error",
                    message=f"Unknown hook event '{event}'. Not in the valid event set.",
                    file=rel_file,
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Check 2: Script paths referenced in hooks
# ---------------------------------------------------------------------------

def _extract_script_paths(command_str: str) -> list[str]:
    """Return relative paths (after CLAUDE_PLUGIN_ROOT) found in a command string."""
    return SCRIPT_PATH_RE.findall(command_str)


def check_script_paths(
    plugin_name: str,
    plugin_root: Path,
    hooks_json: Path,
    hooks_data: dict[str, Any],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    hooks_block = hooks_data.get("hooks", {})
    rel_file = _rel(hooks_json)

    # Gather all command strings regardless of format
    command_strings: list[str] = []

    if isinstance(hooks_block, dict):
        for event_entries in hooks_block.values():
            if not isinstance(event_entries, list):
                continue
            for matcher_block in event_entries:
                if not isinstance(matcher_block, dict):
                    continue
                inner_hooks = matcher_block.get("hooks", [])
                for hook in inner_hooks:
                    cmd = hook.get("command", "")
                    if cmd:
                        command_strings.append(cmd)

    elif isinstance(hooks_block, list):
        for entry in hooks_block:
            if isinstance(entry, dict):
                cmd = entry.get("command", "")
                if cmd:
                    command_strings.append(cmd)

    for cmd in command_strings:
        for rel_script in _extract_script_paths(cmd):
            script_path = plugin_root / rel_script
            if not script_path.exists():
                violations.append(
                    make_violation(
                        plugin=plugin_name,
                        vtype="missing_script",
                        severity="error",
                        message=(
                            f"Script referenced in hook command does not exist: "
                            f"{rel_script}"
                        ),
                        file=rel_file,
                    )
                )

    return violations


# ---------------------------------------------------------------------------
# Check 3: Cross-plugin subagent_type references
# ---------------------------------------------------------------------------

def check_cross_plugin_refs(
    plugin_name: str,
    plugin_root: Path,
    plugins_dir: Path,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    md_files: list[Path] = []
    for subdir in ("commands", "agents"):
        target = plugin_root / subdir
        if target.is_dir():
            md_files.extend(target.glob("*.md"))

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for match in SUBAGENT_REF_RE.finditer(content):
            ref_plugin_name = f"wicked-{match.group(1)}"
            ref_agent_name = match.group(2)

            ref_plugin_dir = plugins_dir / ref_plugin_name
            if not ref_plugin_dir.is_dir():
                violations.append(
                    make_violation(
                        plugin=plugin_name,
                        vtype="ghost_reference",
                        severity="error",
                        message=(
                            f"References subagent_type=\"{ref_plugin_name}:{ref_agent_name}\" "
                            f"but plugin directory '{ref_plugin_name}' does not exist."
                        ),
                        file=_rel_from(md_file, plugin_root.parent.parent),
                    )
                )
                continue

            # Plugin exists — check the agent file
            agent_file = ref_plugin_dir / "agents" / f"{ref_agent_name}.md"
            if not agent_file.exists():
                violations.append(
                    make_violation(
                        plugin=plugin_name,
                        vtype="ghost_reference",
                        severity="error",
                        message=(
                            f"References subagent_type=\"{ref_plugin_name}:{ref_agent_name}\" "
                            f"but agent file 'agents/{ref_agent_name}.md' not found in {ref_plugin_name}."
                        ),
                        file=_rel_from(md_file, plugin_root.parent.parent),
                    )
                )

    return violations


# ---------------------------------------------------------------------------
# Check 4: Ghost specialist validation
# ---------------------------------------------------------------------------

def check_specialist(
    plugin_name: str,
    plugin_root: Path,
    specialist_json: Path,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    rel_file = _rel_from(specialist_json, plugin_root.parent.parent)

    try:
        data = json.loads(specialist_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            make_violation(
                plugin=plugin_name,
                vtype="ghost_specialist",
                severity="error",
                message=f"Could not parse specialist.json: {exc}",
                file=rel_file,
            )
        ]

    # Validate top-level required fields
    for field in REQUIRED_SPECIALIST_FIELDS:
        if field not in data:
            violations.append(
                make_violation(
                    plugin=plugin_name,
                    vtype="ghost_specialist",
                    severity="error",
                    message=f"specialist.json missing required field '{field}'.",
                    file=rel_file,
                )
            )

    # Validate specialist sub-object has 'role'
    specialist_block = data.get("specialist", {})
    if not isinstance(specialist_block, dict) or not specialist_block.get("role"):
        violations.append(
            make_violation(
                plugin=plugin_name,
                vtype="ghost_specialist",
                severity="error",
                message="specialist.json 'specialist' block missing or has no 'role'.",
                file=rel_file,
            )
        )

    # Validate personas is a non-empty list
    personas = data.get("personas", [])
    if not isinstance(personas, list) or not personas:
        violations.append(
            make_violation(
                plugin=plugin_name,
                vtype="ghost_specialist",
                severity="error",
                message="specialist.json 'personas' must be a non-empty list.",
                file=rel_file,
            )
        )
    else:
        # Each persona should have a name and agent path that exists
        for persona in personas:
            if not isinstance(persona, dict):
                continue
            agent_rel = persona.get("agent", "")
            if not agent_rel:
                continue
            agent_path = plugin_root / agent_rel
            if not agent_path.exists():
                violations.append(
                    make_violation(
                        plugin=plugin_name,
                        vtype="ghost_specialist",
                        severity="error",
                        message=(
                            f"Persona '{persona.get('name', '?')}' references agent "
                            f"'{agent_rel}' which does not exist."
                        ),
                        file=rel_file,
                    )
                )

    # Validate enhances is a non-empty list
    enhances = data.get("enhances", [])
    if not isinstance(enhances, list) or not enhances:
        violations.append(
            make_violation(
                plugin=plugin_name,
                vtype="ghost_specialist",
                severity="error",
                message="specialist.json 'enhances' must be a non-empty list.",
                file=rel_file,
            )
        )

    return violations


# ---------------------------------------------------------------------------
# Check 5: plugin.json required fields
# ---------------------------------------------------------------------------

def check_plugin_json(
    plugin_name: str,
    plugin_root: Path,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    plugin_json_path = plugin_root / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        return [
            make_violation(
                plugin=plugin_name,
                vtype="missing_field",
                severity="error",
                message=".claude-plugin/plugin.json not found.",
                file=".claude-plugin/plugin.json",
            )
        ]

    rel_file = _rel_from(plugin_json_path, plugin_root.parent.parent)

    try:
        data = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            make_violation(
                plugin=plugin_name,
                vtype="missing_field",
                severity="error",
                message=f"Could not parse plugin.json: {exc}",
                file=rel_file,
            )
        ]

    for field in REQUIRED_PLUGIN_FIELDS:
        if field not in data or not data[field]:
            violations.append(
                make_violation(
                    plugin=plugin_name,
                    vtype="missing_field",
                    severity="error",
                    message=f"plugin.json missing required field '{field}'.",
                    file=rel_file,
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Per-plugin orchestration
# ---------------------------------------------------------------------------

def probe_plugin(plugin_root: Path, plugins_dir: Path) -> list[dict[str, Any]]:
    plugin_name = plugin_root.name
    violations: list[dict[str, Any]] = []

    # Check 5 first (plugin.json) — always run regardless of other structure
    violations.extend(check_plugin_json(plugin_name, plugin_root))

    # Check 1 & 2: hooks
    hooks_json_path = plugin_root / "hooks" / "hooks.json"
    if hooks_json_path.exists():
        try:
            hooks_data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(
                make_violation(
                    plugin=plugin_name,
                    vtype="missing_field",
                    severity="error",
                    message=f"Could not parse hooks/hooks.json: {exc}",
                    file="hooks/hooks.json",
                )
            )
            hooks_data = None

        if hooks_data is not None:
            violations.extend(
                check_hook_events(plugin_name, hooks_json_path, hooks_data)
            )
            violations.extend(
                check_script_paths(plugin_name, plugin_root, hooks_json_path, hooks_data)
            )

    # Check 3: cross-plugin refs
    violations.extend(
        check_cross_plugin_refs(plugin_name, plugin_root, plugins_dir)
    )

    # Check 4: specialist
    specialist_json_path = plugin_root / ".claude-plugin" / "specialist.json"
    if specialist_json_path.exists():
        violations.extend(
            check_specialist(plugin_name, plugin_root, specialist_json_path)
        )

    return violations


# ---------------------------------------------------------------------------
# Result assembly and persistence
# ---------------------------------------------------------------------------

def _determine_plugin_status(plugin_violations: list[dict[str, Any]]) -> str:
    severities = {v["severity"] for v in plugin_violations}
    if "error" in severities:
        return "unhealthy"
    if "warning" in severities:
        return "degraded"
    return "healthy"


def _determine_overall_status(violations: list[dict[str, Any]]) -> str:
    severities = {v["severity"] for v in violations}
    if "error" in severities:
        return "unhealthy"
    if "warning" in severities:
        return "degraded"
    return "healthy"


def build_report(
    all_violations: list[dict[str, Any]],
    plugins_checked: int,
    per_plugin_violations: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    errors = sum(1 for v in all_violations if v["severity"] == "error")
    warnings = sum(1 for v in all_violations if v["severity"] == "warning")

    healthy = degraded = unhealthy = 0
    for violations in per_plugin_violations.values():
        status = _determine_plugin_status(violations)
        if status == "healthy":
            healthy += 1
        elif status == "degraded":
            degraded += 1
        else:
            unhealthy += 1

    return {
        "status": _determine_overall_status(all_violations),
        "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugins_checked": plugins_checked,
        "violations": all_violations,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "plugins_healthy": healthy,
            "plugins_degraded": degraded,
            "plugins_unhealthy": unhealthy,
        },
    }


def persist_report(report: dict[str, Any]) -> str | None:
    """Persist the report via StorageManager. Returns the record ID on success."""
    try:
        # Upsert: try update first, fall back to create
        record = dict(report)
        record["id"] = "latest"

        existing = _sm.get("health", "latest")
        if existing:
            result = _sm.update("health", "latest", record)
        else:
            result = _sm.create("health", record)

        return "latest" if result else None
    except Exception as exc:
        print(f"WARNING: Could not persist health report: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Human-readable console output
# ---------------------------------------------------------------------------

def print_report(report: dict[str, Any], record_id: str | None = None) -> None:
    status = report["status"].upper()
    checked = report["plugins_checked"]
    summary = report["summary"]

    # Status line
    status_icon = {"HEALTHY": "[OK]", "DEGRADED": "[WARN]", "UNHEALTHY": "[FAIL]"}.get(
        status, "[?]"
    )
    print(f"\n{status_icon} Health probe: {status}")
    print(
        f"   Plugins checked: {checked}  |  "
        f"Errors: {summary['errors']}  |  "
        f"Warnings: {summary['warnings']}"
    )
    print(
        f"   Healthy: {summary['plugins_healthy']}  |  "
        f"Degraded: {summary['plugins_degraded']}  |  "
        f"Unhealthy: {summary['plugins_unhealthy']}"
    )

    violations = report["violations"]
    if not violations:
        print("\n   All plugins passed health checks.")
    else:
        print(f"\n   Violations ({len(violations)}):")
        for v in violations:
            sev = v["severity"].upper()
            loc = f"  ({v['file']})" if v.get("file") else ""
            print(f"   [{sev}] {v['plugin']}{loc}")
            print(f"          {v['message']}")

    if record_id:
        print(f"\n   Report persisted as: wicked-observability/health/{record_id}\n")
    else:
        print("\n   Report not persisted.\n")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    """Return path relative to its plugin root (plugins/wicked-x/ stripped)."""
    parts = path.parts
    try:
        # Find 'plugins' segment and skip two more (plugins, wicked-x)
        idx = next(i for i, p in enumerate(parts) if p == "plugins")
        return str(Path(*parts[idx + 2 :]))
    except StopIteration:
        return str(path)


def _rel_from(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Plugins directory discovery
# ---------------------------------------------------------------------------

def find_plugins_dir(start: Path) -> Path:
    """Walk up from start to find a 'plugins/' directory in the monorepo root."""
    candidate = start
    for _ in range(10):
        plugins = candidate / "plugins"
        if plugins.is_dir():
            return plugins
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    # Fallback: relative to script location (scripts/ → wicked-observability/ → plugins/)
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # Fast-path: --health-check emits a sample report for contract testing
    if "--health-check" in sys.argv:
        print(json.dumps({
            "status": "healthy",
            "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "plugins_checked": 0,
            "violations": [],
            "summary": {
                "errors": 0, "warnings": 0,
                "plugins_healthy": 0, "plugins_degraded": 0, "plugins_unhealthy": 0,
            },
        }))
        return 0

    parser = argparse.ArgumentParser(
        description="Validate wicked-garden plugin health."
    )
    parser.add_argument(
        "--plugin",
        metavar="PLUGIN_NAME",
        help="Only probe a single plugin (e.g. wicked-kanban).",
    )
    parser.add_argument(
        "--plugins-dir",
        metavar="PATH",
        help="Path to the plugins/ directory. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--json",
        dest="json_only",
        action="store_true",
        help="Print JSON to stdout only, no human-readable output.",
    )
    args = parser.parse_args()

    # Resolve plugins directory
    if args.plugins_dir:
        plugins_dir = Path(args.plugins_dir).resolve()
    else:
        plugins_dir = find_plugins_dir(Path.cwd())

    if not plugins_dir.is_dir():
        print(f"ERROR: plugins directory not found: {plugins_dir}", file=sys.stderr)
        return 2

    # Determine which plugins to probe
    if args.plugin:
        plugin_root = plugins_dir / args.plugin
        if not plugin_root.is_dir():
            print(
                f"ERROR: plugin '{args.plugin}' not found in {plugins_dir}",
                file=sys.stderr,
            )
            return 2
        plugin_roots = [plugin_root]
    else:
        plugin_roots = sorted(
            p for p in plugins_dir.iterdir() if p.is_dir() and p.name.startswith("wicked-")
        )

    # Run probes
    all_violations: list[dict[str, Any]] = []
    per_plugin_violations: dict[str, list[dict[str, Any]]] = {}

    for plugin_root in plugin_roots:
        plugin_name = plugin_root.name
        violations = probe_plugin(plugin_root, plugins_dir)
        per_plugin_violations[plugin_name] = violations
        all_violations.extend(violations)

    # Build report
    report = build_report(all_violations, len(plugin_roots), per_plugin_violations)

    # Persist
    record_id = persist_report(report)

    # Output
    if args.json_only:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report, record_id)

    # Exit code
    status = report["status"]
    if status == "healthy":
        return 0
    if status == "degraded":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
