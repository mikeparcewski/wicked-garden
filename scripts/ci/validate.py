#!/usr/bin/env python3
"""
Standalone structural validation for wicked-garden plugin.

Runs with stdlib only — no third-party dependencies.
Suitable for CI (GitHub Actions) without needing Claude Code.

Checks:
  1. plugin.json is valid JSON with required fields
  2. All SKILL.md files are <= 200 lines
  3. All script paths in hooks.json exist
  4. All agent files have required frontmatter fields
  5. No stale presentation/prezzie references in commands/agents
  6. Self-referential integrity: script paths in commands/agents resolve
  7. specialist.json roles match ROLE_CATEGORIES in specialist_discovery.py
"""

import json
import os
import re
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent.parent
    os.chdir(root)

    errors = []
    warnings = []

    # --- 1. plugin.json validity ---
    plugin_json = root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        errors.append("Missing .claude-plugin/plugin.json")
    else:
        try:
            plugin = json.loads(plugin_json.read_text())
            for field in ("name", "version", "description"):
                if field not in plugin:
                    errors.append(f"plugin.json missing required field: {field}")
            version = plugin.get("version", "")
            # Allow semver core X.Y.Z plus optional pre-release (-alpha.N, -beta.N, -rc.N)
            # per semver.org; v6 ships as 6.0.0-beta.1.
            if not re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$", version):
                errors.append(f"plugin.json version is not semver: {version}")
        except json.JSONDecodeError as e:
            errors.append(f"plugin.json is invalid JSON: {e}")

    # --- 2. SKILL.md line counts ---
    for skill_md in sorted(root.glob("skills/**/SKILL.md")):
        lines = len(skill_md.read_text().splitlines())
        if lines > 200:
            rel = skill_md.relative_to(root)
            errors.append(f"{rel} is {lines} lines (max 200)")

    # --- 3. hooks.json script paths ---
    hooks_json = root / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            hooks_data = json.loads(hooks_json.read_text())
            hook_events = hooks_data.get("hooks", {})
            for event_name, matchers in hook_events.items():
                for matcher_block in matchers:
                    for hook in matcher_block.get("hooks", []):
                        cmd = hook.get("command", "")
                        # Extract script paths from the command string
                        # Pattern: ${CLAUDE_PLUGIN_ROOT}/path/to/script.py
                        paths = re.findall(
                            r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"]+\.py)',
                            cmd,
                        )
                        for p in paths:
                            if not (root / p).exists():
                                errors.append(
                                    f"hooks.json [{event_name}]: "
                                    f"script not found: {p}"
                                )
        except json.JSONDecodeError as e:
            errors.append(f"hooks.json is invalid JSON: {e}")

    # --- 4. Agent frontmatter ---
    for agent_md in sorted(root.glob("agents/**/*.md")):
        text = agent_md.read_text()
        rel = agent_md.relative_to(root)
        # Check for YAML frontmatter
        if not text.startswith("---"):
            errors.append(f"{rel}: missing YAML frontmatter")
            continue
        # Extract frontmatter block
        fm_match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
        if not fm_match:
            errors.append(f"{rel}: malformed YAML frontmatter")
            continue
        fm = fm_match.group(1)
        if "description:" not in fm:
            errors.append(f"{rel}: missing 'description' in frontmatter")

    # --- 5. No stale prezzie/presentation references ---
    stale_pattern = re.compile(
        r"\bprezzie\b|\bpresentation[-_]?plugin\b",
        re.IGNORECASE,
    )
    for md_file in sorted(
        list(root.glob("commands/**/*.md"))
        + list(root.glob("agents/**/*.md"))
    ):
        text = md_file.read_text()
        rel = md_file.relative_to(root)
        matches = stale_pattern.findall(text)
        if matches:
            warnings.append(
                f"{rel}: contains stale reference(s): {', '.join(set(matches))}"
            )

    # --- 6. Self-referential integrity: script paths in commands/agents ---
    script_ref_pattern = re.compile(
        r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"]+\.(?:py|sh))'
    )
    for md_file in sorted(
        list(root.glob("commands/**/*.md"))
        + list(root.glob("agents/**/*.md"))
    ):
        text = md_file.read_text()
        rel = md_file.relative_to(root)
        refs = script_ref_pattern.findall(text)
        for ref in refs:
            # Skip template placeholders like {language}_generator.py
            if re.search(r"\{[^}]+\}", ref):
                continue
            if not (root / ref).exists():
                errors.append(f"{rel}: broken script path: {ref}")

    # --- 7. specialist.json roles vs ROLE_CATEGORIES ---
    specialist_json = root / ".claude-plugin" / "specialist.json"
    discovery_py = root / "scripts" / "crew" / "specialist_discovery.py"
    if specialist_json.exists() and discovery_py.exists():
        try:
            spec_data = json.loads(specialist_json.read_text())
            specialists = spec_data.get("specialists", [])

            # Extract ROLE_CATEGORIES keys from specialist_discovery.py
            disc_text = discovery_py.read_text()
            cat_match = re.search(
                r"ROLE_CATEGORIES\s*=\s*\{([^}]+)\}",
                disc_text,
                re.DOTALL,
            )
            if cat_match:
                # Parse the dict keys (quoted strings before colons)
                role_keys = set(
                    re.findall(r'"([^"]+)"\s*:', cat_match.group(1))
                )
                for spec in specialists:
                    role = spec.get("role", "")
                    if role and role not in role_keys:
                        errors.append(
                            f"specialist.json: role '{role}' for "
                            f"specialist '{spec.get('name', '?')}' "
                            f"not in ROLE_CATEGORIES "
                            f"({', '.join(sorted(role_keys))})"
                        )
            else:
                warnings.append(
                    "Could not parse ROLE_CATEGORIES from "
                    "specialist_discovery.py"
                )
        except json.JSONDecodeError as e:
            errors.append(f"specialist.json is invalid JSON: {e}")

    # --- 8. All JSON files valid ---
    for json_file in sorted(root.glob("**/*.json")):
        # Skip node_modules, .git, __pycache__
        rel = json_file.relative_to(root)
        parts = rel.parts
        if any(
            p in (".git", "node_modules", "__pycache__", ".venv")
            for p in parts
        ):
            continue
        try:
            json.loads(json_file.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: invalid JSON: {e}")

    # --- Report ---
    print("=" * 60)
    print("wicked-garden structural validation")
    print("=" * 60)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ERROR: {e}")
        print(f"\nRESULT: FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    else:
        print(f"\nRESULT: PASS (0 errors, {len(warnings)} warnings)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
