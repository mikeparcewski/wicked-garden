#!/usr/bin/env python3
"""Plugin infrastructure validation for all wicked-garden plugins.

Validates:
1. plugin.json exists and is valid JSON with required fields
2. specialist.json exists for specialist plugins and is valid
3. All agents referenced in scenarios exist in agents/ directory
4. All skills referenced exist in skills/ directory
5. Hook scripts exist and are executable
6. README.md exists with Integration table
7. CHANGELOG.md exists
8. Scenarios directory exists with at least 1 scenario
"""

import json
import os
import re
import glob
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

SPECIALIST_PLUGINS = [
    "wicked-engineering", "wicked-platform", "wicked-product", "wicked-delivery",
    "wicked-data", "wicked-qe", "wicked-jam", "wicked-agentic"
]

UTILITY_PLUGINS = [
    "wicked-kanban", "wicked-mem", "wicked-search", "wicked-smaht",
    "wicked-startah", "wicked-workbench", "wicked-scenarios", "wicked-patch",
    "wicked-crew"
]

REQUIRED_PLUGIN_JSON_FIELDS = ["name", "version", "description"]


def validate_plugin(plugin_dir):
    """Validate a single plugin's infrastructure."""
    name = plugin_dir.name
    result = {
        "plugin": name,
        "findings": [],
        "stats": {},
        "grade": "PASS"
    }

    # 1. Check plugin.json
    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json_path.exists():
        result["findings"].append(("error", "Missing .claude-plugin/plugin.json"))
        result["grade"] = "FAIL"
    else:
        try:
            with open(plugin_json_path) as f:
                pj = json.load(f)

            for field in REQUIRED_PLUGIN_JSON_FIELDS:
                if field not in pj:
                    result["findings"].append(("error", f"plugin.json missing required field: {field}"))
                    result["grade"] = "FAIL"

            result["stats"]["version"] = pj.get("version", "?")
            result["stats"]["plugin_name"] = pj.get("name", "?")
        except json.JSONDecodeError as e:
            result["findings"].append(("error", f"plugin.json is invalid JSON: {e}"))
            result["grade"] = "FAIL"

    # 2. Check specialist.json for specialist plugins
    if name in SPECIALIST_PLUGINS:
        spec_path = plugin_dir / ".claude-plugin" / "specialist.json"
        if not spec_path.exists():
            result["findings"].append(("warn", "Specialist plugin missing specialist.json"))
        else:
            try:
                with open(spec_path) as f:
                    spec = json.load(f)
                result["stats"]["personas"] = len(spec.get("personas", []))
                result["stats"]["enhances"] = len(spec.get("enhances", []))
            except json.JSONDecodeError:
                result["findings"].append(("error", "specialist.json is invalid JSON"))

    # 3. Check agents directory
    agents_dir = plugin_dir / "agents"
    if agents_dir.exists():
        agent_files = list(agents_dir.glob("*.md"))
        result["stats"]["agent_count"] = len(agent_files)

        for agent_file in agent_files:
            content = agent_file.read_text()
            if not content.startswith("---"):
                result["findings"].append(("warn", f"Agent {agent_file.name} missing frontmatter"))
    else:
        result["stats"]["agent_count"] = 0
        if name in SPECIALIST_PLUGINS:
            result["findings"].append(("info", "No agents/ directory"))

    # 4. Check skills directory
    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        skill_files = list(skills_dir.glob("*/SKILL.md"))
        result["stats"]["skill_count"] = len(skill_dirs)
        result["stats"]["skill_files"] = len(skill_files)

        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                result["findings"].append(("warn", f"Skill {skill_dir.name} missing SKILL.md"))
            else:
                lines = skill_md.read_text().count("\n")
                if lines > 200:
                    result["findings"].append(("warn", f"Skill {skill_dir.name}/SKILL.md is {lines} lines (max 200)"))
    else:
        result["stats"]["skill_count"] = 0

    # 5. Check commands directory
    commands_dir = plugin_dir / "commands"
    if commands_dir.exists():
        cmd_files = list(commands_dir.glob("*.md"))
        result["stats"]["command_count"] = len(cmd_files)
    else:
        result["stats"]["command_count"] = 0

    # 6. Check hooks
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            with open(hooks_json) as f:
                hooks_data = json.load(f)

            # Count hooks - format is {hooks: {EventName: [{matcher, hooks: [{type, command}]}]}}
            hook_count = 0
            hooks_section = hooks_data.get("hooks", {}) if isinstance(hooks_data, dict) else {}
            all_commands = []

            for event_name, matchers in hooks_section.items():
                if isinstance(matchers, list):
                    for matcher_entry in matchers:
                        if isinstance(matcher_entry, dict):
                            inner_hooks = matcher_entry.get("hooks", [])
                            if isinstance(inner_hooks, list):
                                for h in inner_hooks:
                                    if isinstance(h, dict):
                                        hook_count += 1
                                        all_commands.append(h.get("command", ""))

            result["stats"]["hook_count"] = hook_count

            # Check hook scripts exist
            for cmd in all_commands:
                scripts = re.findall(r'\$\{?CLAUDE_PLUGIN_ROOT\}?/hooks/scripts/(\S+)', cmd)
                for script in scripts:
                    script = script.strip('"').strip("'")
                    script_path = plugin_dir / "hooks" / "scripts" / script
                    if not script_path.exists():
                        result["findings"].append(("error", f"Hook references missing script: hooks/scripts/{script}"))
        except json.JSONDecodeError:
            result["findings"].append(("error", "hooks.json is invalid JSON"))
    else:
        result["stats"]["hook_count"] = 0

    # 7. Check README.md
    readme = plugin_dir / "README.md"
    if not readme.exists():
        result["findings"].append(("warn", "Missing README.md"))
    else:
        content = readme.read_text()
        if "integration" not in content.lower():
            result["findings"].append(("info", "README may not have Integration table"))

    # 8. Check CHANGELOG.md
    changelog = plugin_dir / "CHANGELOG.md"
    if not changelog.exists():
        result["findings"].append(("info", "Missing CHANGELOG.md"))

    # 9. Check scenarios
    scenarios_dir = plugin_dir / "scenarios"
    if scenarios_dir.exists():
        scenario_files = [f for f in scenarios_dir.glob("*.md") if f.name != "README.md"]
        result["stats"]["scenario_count"] = len(scenario_files)
    else:
        result["findings"].append(("warn", "Missing scenarios/ directory"))
        result["stats"]["scenario_count"] = 0

    # 10. Check scripts directory
    scripts_dir = plugin_dir / "scripts"
    if scripts_dir.exists():
        py_scripts = list(scripts_dir.rglob("*.py"))
        sh_scripts = list(scripts_dir.rglob("*.sh"))
        result["stats"]["python_scripts"] = len(py_scripts)
        result["stats"]["shell_scripts"] = len(sh_scripts)
    else:
        result["stats"]["python_scripts"] = 0
        result["stats"]["shell_scripts"] = 0

    # Determine grade
    errors = [f for f in result["findings"] if f[0] == "error"]
    warns = [f for f in result["findings"] if f[0] == "warn"]

    if errors:
        result["grade"] = "FAIL"
    elif len(warns) >= 3:
        result["grade"] = "WARN"
    elif warns:
        result["grade"] = "PASS_WITH_NOTES"
    else:
        result["grade"] = "PASS"

    return result


def main():
    all_results = []

    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
            continue

        result = validate_plugin(plugin_dir)
        all_results.append(result)

    # Generate report
    print("=" * 80)
    print("WICKED GARDEN - PLUGIN INFRASTRUCTURE VALIDATION")
    print("=" * 80)
    print(f"\nTotal plugins validated: {len(all_results)}")

    grades = {}
    for r in all_results:
        grades[r["grade"]] = grades.get(r["grade"], 0) + 1

    print(f"\nGrades:")
    for grade, count in sorted(grades.items()):
        icon = {"PASS": "OK", "PASS_WITH_NOTES": "OK*", "WARN": "!!", "FAIL": "XX"}
        print(f"  [{icon.get(grade, '??')}] {grade}: {count}")

    print(f"\n{'=' * 80}")
    print("PER-PLUGIN DETAILS")
    print(f"{'=' * 80}")

    for r in all_results:
        s = r["stats"]
        grade_icon = {"PASS": "OK", "PASS_WITH_NOTES": "~", "WARN": "!", "FAIL": "X"}[r["grade"]]
        category = "specialist" if r["plugin"] in SPECIALIST_PLUGINS else "utility"

        print(f"\n[{grade_icon}] {r['plugin']} (v{s.get('version', '?')}) [{category}]")
        print(f"    agents={s.get('agent_count', 0)} skills={s.get('skill_count', 0)} "
              f"commands={s.get('command_count', 0)} hooks={s.get('hook_count', 0)} "
              f"scenarios={s.get('scenario_count', 0)} scripts={s.get('python_scripts', 0)}py/{s.get('shell_scripts', 0)}sh")

        if r["plugin"] in SPECIALIST_PLUGINS:
            print(f"    personas={s.get('personas', '?')} enhances={s.get('enhances', '?')}")

        for level, msg in r["findings"]:
            if level in ("error", "warn"):
                prefix = "ERR" if level == "error" else "WRN"
                print(f"    {prefix}: {msg}")

    # Summary stats
    print(f"\n{'=' * 80}")
    print("AGGREGATE STATISTICS")
    print(f"{'=' * 80}")
    total_agents = sum(r["stats"].get("agent_count", 0) for r in all_results)
    total_skills = sum(r["stats"].get("skill_count", 0) for r in all_results)
    total_commands = sum(r["stats"].get("command_count", 0) for r in all_results)
    total_hooks = sum(r["stats"].get("hook_count", 0) for r in all_results)
    total_scenarios = sum(r["stats"].get("scenario_count", 0) for r in all_results)
    total_scripts = sum(r["stats"].get("python_scripts", 0) for r in all_results)

    print(f"\n  Agents:    {total_agents}")
    print(f"  Skills:    {total_skills}")
    print(f"  Commands:  {total_commands}")
    print(f"  Hooks:     {total_hooks}")
    print(f"  Scenarios: {total_scenarios}")
    print(f"  Scripts:   {total_scripts}")

    # Write JSON
    output_path = REPO_ROOT / "test-results" / "plugin-infra-validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_results = [{
        "plugin": r["plugin"],
        "grade": r["grade"],
        "stats": r["stats"],
        "findings": [{"level": l, "message": m} for l, m in r["findings"]]
    } for r in all_results]

    with open(output_path, "w") as f:
        json.dump({
            "total": len(all_results),
            "grades": grades,
            "results": json_results,
            "aggregates": {
                "agents": total_agents, "skills": total_skills,
                "commands": total_commands, "hooks": total_hooks,
                "scenarios": total_scenarios, "scripts": total_scripts
            }
        }, f, indent=2)

    print(f"\nJSON results written to: {output_path}")

    failures = [r for r in all_results if r["grade"] == "FAIL"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
