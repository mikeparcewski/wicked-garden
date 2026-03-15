#!/usr/bin/env python3
"""
migrate_capabilities.py — Add tool-capabilities to agent frontmatter.

Only adds capabilities that require runtime discovery (MCP servers, CLIs).
Built-in tools (Read, Write, Grep, etc.) are NOT listed — the model
already knows about those.

Usage:
    python3 scripts/migrate_capabilities.py [--dry-run] [agent-file ...]

Flags:
    --dry-run   Show what would change without writing files

If specific agent files are given, only those are migrated.
Otherwise, all default targets are migrated.

stdlib-only — no external dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Migration targets: agent_path -> capabilities that need runtime discovery
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
}


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
    capabilities: list[str],
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

    if not capabilities:
        return False, f"SKIP (no discoverable capabilities): {agent_path.name}"

    new_content = _add_tool_capabilities(content, capabilities)

    if dry_run:
        return True, f"WOULD MIGRATE: {agent_path.name} -> {capabilities}"

    agent_path.write_text(new_content, encoding="utf-8")
    return True, f"MIGRATED: {agent_path.name} -> {capabilities}"


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
            rel = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
            caps = MIGRATION_TARGETS.get(rel, [])
            targets[path] = caps
    else:
        # Migrate all default targets
        targets = {
            repo_root / rel_path: caps
            for rel_path, caps in MIGRATION_TARGETS.items()
        }

    print(f"{'DRY RUN — ' if dry_run else ''}Migrating {len(targets)} agent(s)...")
    print()

    changed = 0
    for path, caps in sorted(targets.items()):
        was_changed, msg = migrate_agent(path, caps, dry_run=dry_run)
        print(f"  {msg}")
        if was_changed:
            changed += 1

    print()
    print(f"{'Would change' if dry_run else 'Changed'}: {changed}/{len(targets)} agents")

    return 0


if __name__ == "__main__":
    sys.exit(main())
