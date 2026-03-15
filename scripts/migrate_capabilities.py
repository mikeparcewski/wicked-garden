#!/usr/bin/env python3
"""
migrate_capabilities.py — Add tool-capabilities to agent frontmatter.

Reads each target agent's allowed-tools list, maps it to the most
appropriate set of capabilities from the registry, and adds a
tool-capabilities: section to the YAML frontmatter.

Does NOT modify allowed-tools — the existing list is preserved as
the baseline. tool-capabilities adds tools on top.

Usage:
    python3 scripts/migrate_capabilities.py [--dry-run] [agent-file ...]

Flags:
    --dry-run   Show what would change without writing files

If specific agent files are given, only those are migrated.
Otherwise, all 10 default targets are migrated.

stdlib-only — no external dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Tool-to-capability reverse mapping (used for inference)
# ---------------------------------------------------------------------------

TOOL_CAPABILITY_MAP: dict[str, str] = {
    "Read": "code-edit",
    "Write": "code-edit",
    "Edit": "code-edit",
    "Grep": "code-search",
    "Glob": "code-search",
    "Bash": "code-execution",
    "WebFetch": "web-access",
    "WebSearch": "web-access",
    "Task": "subagent-dispatch",
}

# ---------------------------------------------------------------------------
# Migration targets: agent_path -> additional capabilities beyond inference
# ---------------------------------------------------------------------------

MIGRATION_TARGETS: dict[str, list[str]] = {
    "agents/platform/security-engineer.md": ["security-scanning", "version-control"],
    "agents/platform/sre.md": ["error-tracking", "ci-cd"],
    "agents/engineering/senior-engineer.md": ["version-control"],
    "agents/engineering/backend-engineer.md": ["version-control"],
    "agents/qe/code-analyzer.md": ["security-scanning"],
    "agents/data/data-engineer.md": ["data-query"],
    "agents/delivery/progress-tracker.md": ["project-management"],
    "agents/agentic/safety-reviewer.md": ["security-scanning"],
    "agents/crew/implementer.md": ["version-control"],
    "agents/agentic/framework-researcher.md": ["web-access"],
}


def _infer_capabilities(allowed_tools_line: str) -> list[str]:
    """Infer capabilities from an allowed-tools line.

    Parses the comma-separated tool list and maps each to a capability
    via TOOL_CAPABILITY_MAP. Returns deduplicated list preserving order.
    """
    tools = [t.strip() for t in allowed_tools_line.split(",") if t.strip()]
    seen: set[str] = set()
    caps: list[str] = []
    for tool in tools:
        cap = TOOL_CAPABILITY_MAP.get(tool)
        if cap and cap not in seen:
            seen.add(cap)
            caps.append(cap)
    return caps


def _add_tool_capabilities(content: str, capabilities: list[str]) -> str:
    """Add tool-capabilities to an agent's frontmatter.

    Inserts the tool-capabilities block after the allowed-tools line.
    If tool-capabilities already exists, returns content unchanged.
    """
    if "tool-capabilities:" in content:
        return content  # Already migrated

    lines = content.split("\n")
    insert_idx = None

    # Find allowed-tools line in frontmatter
    in_frontmatter = False
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break  # End of frontmatter
        if in_frontmatter and line.startswith("allowed-tools:"):
            insert_idx = i + 1
            break

    if insert_idx is None:
        # No allowed-tools found; insert before closing ---
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "---":
                insert_idx = i
                break

    if insert_idx is None:
        return content  # Can't find frontmatter

    # Build the tool-capabilities block
    cap_lines = ["tool-capabilities:"]
    for cap in capabilities:
        cap_lines.append(f"  - {cap}")

    # Insert
    result_lines = lines[:insert_idx] + cap_lines + lines[insert_idx:]
    return "\n".join(result_lines)


def migrate_agent(
    agent_path: Path,
    extra_capabilities: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Migrate a single agent file.

    Returns (changed, message).
    """
    if not agent_path.exists():
        return False, f"NOT FOUND: {agent_path}"

    content = agent_path.read_text(encoding="utf-8")

    if "tool-capabilities:" in content:
        return False, f"SKIP (already migrated): {agent_path.name}"

    # Extract allowed-tools line
    allowed_tools_line = ""
    for line in content.split("\n"):
        if line.startswith("allowed-tools:"):
            allowed_tools_line = line.split(":", 1)[1].strip()
            break

    # Infer capabilities from allowed-tools
    inferred = _infer_capabilities(allowed_tools_line)

    # Add extra capabilities (domain-specific)
    all_caps = list(inferred)
    for cap in (extra_capabilities or []):
        if cap not in all_caps:
            all_caps.append(cap)

    if not all_caps:
        return False, f"SKIP (no capabilities to add): {agent_path.name}"

    new_content = _add_tool_capabilities(content, all_caps)

    if dry_run:
        return True, f"WOULD MIGRATE: {agent_path.name} -> {all_caps}"

    agent_path.write_text(new_content, encoding="utf-8")
    return True, f"MIGRATED: {agent_path.name} -> {all_caps}"


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Determine repo root
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    if args:
        # Migrate specific files
        targets = {}
        for arg in args:
            path = Path(arg)
            if not path.is_absolute():
                path = repo_root / arg
            # Find matching target for extra capabilities
            rel = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
            extra = MIGRATION_TARGETS.get(rel, [])
            targets[path] = extra
    else:
        # Migrate all default targets
        targets = {
            repo_root / rel_path: extra_caps
            for rel_path, extra_caps in MIGRATION_TARGETS.items()
        }

    print(f"{'DRY RUN — ' if dry_run else ''}Migrating {len(targets)} agent(s)...")
    print()

    changed = 0
    for path, extra_caps in sorted(targets.items()):
        was_changed, msg = migrate_agent(path, extra_caps, dry_run=dry_run)
        print(f"  {msg}")
        if was_changed:
            changed += 1

    print()
    print(f"{'Would change' if dry_run else 'Changed'}: {changed}/{len(targets)} agents")

    return 0


if __name__ == "__main__":
    sys.exit(main())
