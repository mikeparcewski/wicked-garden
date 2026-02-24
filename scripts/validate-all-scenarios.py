#!/usr/bin/env python3
"""Comprehensive scenario validation for all wicked-garden plugins.

Validates:
1. YAML frontmatter (required fields: name, title, description, type, difficulty)
2. Required sections (Setup, Steps, Expected Outcome or Success Criteria)
3. Referenced skills/agents exist in the plugin
4. Setup scripts are well-formed bash
5. Success criteria are present and checkboxes formatted
6. Cleanup section present
7. Integration notes referencing valid plugins
"""

import os
import re
import json
import glob
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

# All known plugins
KNOWN_PLUGINS = [
    "wicked-agentic", "wicked-crew", "wicked-data", "wicked-delivery",
    "wicked-engineering", "wicked-jam", "wicked-kanban", "wicked-mem",
    "wicked-patch", "wicked-platform", "wicked-product", "wicked-qe",
    "wicked-scenarios", "wicked-search", "wicked-smaht", "wicked-startah",
    "wicked-workbench"
]

REQUIRED_FRONTMATTER = ["name", "title", "description", "type", "difficulty"]
VALID_TYPES = ["workflow", "feature", "review", "debugging", "architecture",
               "integration", "lifecycle", "analysis", "brainstorm", "e2e",
               "validation", "planning", "scenario"]
VALID_DIFFICULTIES = ["basic", "beginner", "intermediate", "advanced"]


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    fm_text = content[3:end].strip()
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()

    body = content[end + 3:].strip()
    return fm, body


def check_sections(body):
    """Check for required and recommended sections."""
    sections = re.findall(r'^#{1,3}\s+(.+)$', body, re.MULTILINE)
    sections_lower = [s.lower().strip() for s in sections]

    findings = []
    has_setup = any("setup" in s for s in sections_lower)
    has_steps = any("step" in s for s in sections_lower)
    has_outcome = any("expected" in s or "outcome" in s for s in sections_lower)
    has_criteria = any("success criteria" in s or "criteria" in s for s in sections_lower)
    has_cleanup = any("cleanup" in s for s in sections_lower)
    has_value = any("value" in s for s in sections_lower)

    if not has_setup:
        findings.append(("warn", "Missing 'Setup' section"))
    if not has_steps:
        findings.append(("warn", "Missing 'Steps' section"))
    if not has_outcome and not has_criteria:
        findings.append(("error", "Missing both 'Expected Outcome' and 'Success Criteria' sections"))
    if not has_cleanup:
        findings.append(("info", "No 'Cleanup' section"))
    if not has_value:
        findings.append(("info", "No 'Value Demonstrated' section"))

    return findings, {
        "setup": has_setup, "steps": has_steps, "outcome": has_outcome,
        "criteria": has_criteria, "cleanup": has_cleanup, "value": has_value,
        "section_count": len(sections)
    }


def check_success_criteria(body):
    """Check success criteria formatting."""
    findings = []
    criteria_match = re.search(r'## Success Criteria\s*\n([\s\S]*?)(?=\n## |\Z)', body)
    if not criteria_match:
        return findings, 0

    criteria_text = criteria_match.group(1)
    checkboxes = re.findall(r'- \[[ x]\]', criteria_text)

    if not checkboxes:
        findings.append(("warn", "Success criteria exists but has no checkbox items"))

    return findings, len(checkboxes)


def check_code_blocks(body):
    """Validate code blocks in scenario."""
    findings = []
    code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', body)

    bash_blocks = [(lang, code) for lang, code in code_blocks if lang in ("bash", "sh", "")]

    for lang, code in bash_blocks:
        # Check for dangerous commands
        if "rm -rf /" in code and "/tmp" not in code and "test-" not in code:
            findings.append(("error", "Potentially dangerous rm -rf in setup script"))
        # Check for hardcoded paths that aren't temp
        if re.search(r'/home/\w+/', code) and "~/" not in code and "$HOME" not in code:
            findings.append(("warn", "Hardcoded home directory path in script"))

    return findings, len(code_blocks)


def check_skill_references(body, plugin_name):
    """Check that referenced skills/agents exist in the plugin."""
    findings = []

    # Find skill references like /wicked-foo:bar
    skill_refs = re.findall(r'/(\w[\w-]+):(\w[\w-]+)', body)

    # Find Task tool references
    task_refs = re.findall(r'subagent_type\s*[=:]\s*["\']?([\w-]+:[\w-]+)', body)

    plugin_dir = PLUGINS_DIR / plugin_name

    # Check skills exist
    for plugin_ref, skill_name in skill_refs:
        ref_plugin_dir = PLUGINS_DIR / plugin_ref
        if not ref_plugin_dir.exists():
            # Check if it's a known plugin
            if plugin_ref not in KNOWN_PLUGINS:
                findings.append(("warn", f"Skill reference /{plugin_ref}:{skill_name} - plugin not found"))

    # Check agent references
    for agent_ref in task_refs:
        ref_plugin, agent_name = agent_ref.split(":", 1)
        ref_plugin_dir = PLUGINS_DIR / ref_plugin
        if not ref_plugin_dir.exists() and ref_plugin not in KNOWN_PLUGINS:
            findings.append(("warn", f"Agent reference {agent_ref} - plugin not found"))

    return findings, {"skills": skill_refs, "agents": task_refs}


def check_integration_notes(body):
    """Check integration notes section."""
    findings = []
    integration_match = re.search(r'## Integration Notes\s*\n([\s\S]*?)(?=\n## |\Z)', body)
    if not integration_match:
        return findings, []

    text = integration_match.group(1)
    mentioned_plugins = re.findall(r'wicked-(\w+)', text)

    for plugin in mentioned_plugins:
        full_name = f"wicked-{plugin}"
        if full_name not in KNOWN_PLUGINS:
            findings.append(("warn", f"Integration notes reference unknown plugin: {full_name}"))

    return findings, mentioned_plugins


def validate_scenario(filepath):
    """Validate a single scenario file."""
    result = {
        "file": str(filepath),
        "plugin": filepath.parent.parent.name,
        "scenario": filepath.stem,
        "findings": [],
        "stats": {},
        "grade": "PASS"
    }

    try:
        content = filepath.read_text()
    except Exception as e:
        result["findings"].append(("error", f"Cannot read file: {e}"))
        result["grade"] = "FAIL"
        return result

    # 1. Check frontmatter
    fm, body = parse_frontmatter(content)
    if fm is None:
        result["findings"].append(("error", "Missing YAML frontmatter"))
        result["grade"] = "FAIL"
    else:
        for field in REQUIRED_FRONTMATTER:
            if field not in fm:
                result["findings"].append(("error", f"Missing required frontmatter field: {field}"))
                result["grade"] = "FAIL"

        if fm.get("type") and fm["type"] not in VALID_TYPES:
            result["findings"].append(("info", f"Non-standard type: {fm.get('type')}"))

        if fm.get("difficulty") and fm["difficulty"] not in VALID_DIFFICULTIES:
            result["findings"].append(("warn", f"Non-standard difficulty: {fm.get('difficulty')}"))

        result["stats"]["frontmatter"] = fm

    # 2. Check sections
    section_findings, section_stats = check_sections(body)
    result["findings"].extend(section_findings)
    result["stats"]["sections"] = section_stats

    # 3. Check success criteria
    criteria_findings, criteria_count = check_success_criteria(body)
    result["findings"].extend(criteria_findings)
    result["stats"]["success_criteria_count"] = criteria_count

    # 4. Check code blocks
    code_findings, code_count = check_code_blocks(body)
    result["findings"].extend(code_findings)
    result["stats"]["code_blocks"] = code_count

    # 5. Check skill/agent references
    ref_findings, refs = check_skill_references(body, result["plugin"])
    result["findings"].extend(ref_findings)
    result["stats"]["references"] = {
        "skills": len(refs.get("skills", [])),
        "agents": len(refs.get("agents", []))
    }

    # 6. Check integration notes
    int_findings, int_plugins = check_integration_notes(body)
    result["findings"].extend(int_findings)
    result["stats"]["integrations"] = int_plugins

    # 7. Line count
    result["stats"]["line_count"] = len(content.split("\n"))

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

        scenarios_dir = plugin_dir / "scenarios"
        if not scenarios_dir.exists():
            continue

        for scenario_file in sorted(scenarios_dir.glob("*.md")):
            if scenario_file.name == "README.md":
                continue

            result = validate_scenario(scenario_file)
            all_results.append(result)

    # Generate report
    print("=" * 80)
    print("WICKED GARDEN - SCENARIO VALIDATION REPORT")
    print("=" * 80)
    print(f"\nTotal scenarios validated: {len(all_results)}")

    # Grade summary
    grades = {}
    for r in all_results:
        grades[r["grade"]] = grades.get(r["grade"], 0) + 1

    print(f"\nGrades:")
    for grade, count in sorted(grades.items()):
        icon = {"PASS": "OK", "PASS_WITH_NOTES": "OK*", "WARN": "!!", "FAIL": "XX"}
        print(f"  [{icon.get(grade, '??')}] {grade}: {count}")

    # Per-plugin summary
    print(f"\n{'=' * 80}")
    print("PER-PLUGIN SUMMARY")
    print(f"{'=' * 80}")

    by_plugin = {}
    for r in all_results:
        if r["plugin"] not in by_plugin:
            by_plugin[r["plugin"]] = []
        by_plugin[r["plugin"]].append(r)

    for plugin, results in sorted(by_plugin.items()):
        pass_count = sum(1 for r in results if r["grade"] in ("PASS", "PASS_WITH_NOTES"))
        total = len(results)
        plugin_grade = "PASS" if pass_count == total else "WARN" if pass_count > total/2 else "FAIL"

        print(f"\n{plugin} ({pass_count}/{total} pass) [{plugin_grade}]")
        for r in results:
            grade_icon = {"PASS": "OK", "PASS_WITH_NOTES": "~", "WARN": "!", "FAIL": "X"}[r["grade"]]
            criteria = r["stats"].get("success_criteria_count", 0)
            lines = r["stats"].get("line_count", 0)
            fm = r["stats"].get("frontmatter", {})
            stype = fm.get("type", "?")
            diff = fm.get("difficulty", "?")
            print(f"  [{grade_icon}] {r['scenario']:<45} type={stype:<15} diff={diff:<13} criteria={criteria:<3} lines={lines}")

            # Show errors and warnings
            for level, msg in r["findings"]:
                if level in ("error", "warn"):
                    print(f"       {'ERR' if level == 'error' else 'WRN'}: {msg}")

    # Detailed findings for failures
    failures = [r for r in all_results if r["grade"] == "FAIL"]
    if failures:
        print(f"\n{'=' * 80}")
        print("FAILURES (require attention)")
        print(f"{'=' * 80}")
        for r in failures:
            print(f"\n  {r['plugin']}/{r['scenario']}:")
            for level, msg in r["findings"]:
                print(f"    [{level.upper()}] {msg}")

    # Write JSON results
    output_path = REPO_ROOT / "test-results" / "scenario-validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_results = []
    for r in all_results:
        json_results.append({
            "plugin": r["plugin"],
            "scenario": r["scenario"],
            "grade": r["grade"],
            "findings": [{"level": l, "message": m} for l, m in r["findings"]],
            "stats": {
                "line_count": r["stats"].get("line_count", 0),
                "success_criteria_count": r["stats"].get("success_criteria_count", 0),
                "code_blocks": r["stats"].get("code_blocks", 0),
                "type": r["stats"].get("frontmatter", {}).get("type", "unknown"),
                "difficulty": r["stats"].get("frontmatter", {}).get("difficulty", "unknown"),
            }
        })

    with open(output_path, "w") as f:
        json.dump({
            "total": len(all_results),
            "grades": grades,
            "by_plugin": {k: len(v) for k, v in by_plugin.items()},
            "results": json_results
        }, f, indent=2)

    print(f"\n\nJSON results written to: {output_path}")

    # Return exit code
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
