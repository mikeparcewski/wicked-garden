#!/usr/bin/env python3
"""Pattern A migration validation gate for wg-check (#665).

When a PR shrinks a skills/**/SKILL.md substantially AND adds a new
agents/**/*.md in the same diff, that's the Pattern A migration shape from
PR #666 (jam slim) and PR #670 (propose-process slim). The gate enforces:
**every Pattern A migration must ship with a passing acceptance scenario** so
reviewers can verify the new agent is wired correctly and the slimmed skill
still delegates to the right place.

Signal: a SKILL.md shrunk by >= 40% (lines-removed / lines-before) AND a new
agents/**/*.md file added in the same `git diff <base>...HEAD`.

Requirement: the same diff must add a scenario file matching:
    scenarios/**/*-pattern-a.md
    scenarios/**/*-shape.md
    scenarios/**/*-dispatch.md
    scenarios/**/*pattern*.md, *shape*.md, *dispatch*.md

Behavior: ERROR (exit 1, blocks CI) if signal detected and no matching
scenario. Fail-open (exit 0) if `git diff` returns empty -- e.g. running on
main with no PR context.

Threshold rationale: 40% shrink + same-PR new agent is the safe combo.
PR #666 went from ~120 to 43 lines (64% drop). Tuning lower would catch
incremental polish; tuning higher would miss legitimate slim migrations.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# See module docstring for tuning rationale.
SHRINK_RATIO = 0.40

SCENARIO_PATTERNS = [
    re.compile(r"^scenarios/.+-pattern-a\.md$"),
    re.compile(r"^scenarios/.+-shape\.md$"),
    re.compile(r"^scenarios/.+-dispatch\.md$"),
    re.compile(r"^scenarios/.*pattern.*\.md$", re.IGNORECASE),
    re.compile(r"^scenarios/.*shape.*\.md$", re.IGNORECASE),
    re.compile(r"^scenarios/.*dispatch.*\.md$", re.IGNORECASE),
]


def run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001 -- fail-open per design
        return ""


def resolve_base_ref() -> str:
    """Resolve the PR base ref. CI sets GITHUB_BASE_REF; locally use origin/main."""
    base = os.environ.get("WG_PR_BASE_REF") or os.environ.get("GITHUB_BASE_REF") or "origin/main"
    if base and not base.startswith("origin/") and base != "main":
        base = f"origin/{base}"
    return base


def main() -> int:
    base_ref = resolve_base_ref()
    diff_range = f"{base_ref}...HEAD"

    name_status = run(["git", "diff", "--name-status", diff_range])
    if not name_status.strip():
        print(f"OK: no PR diff against {base_ref} -- Pattern A gate skipped (fail-open)")
        return 0

    slimmed_skills: list[tuple[str, int, float]] = []
    new_agents: list[str] = []
    new_scenarios: list[str] = []

    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()
        path = parts[-1].strip()

        if status.startswith("A") and path.startswith("agents/") and path.endswith(".md"):
            new_agents.append(path)
        if status.startswith("A") and path.startswith("scenarios/") and path.endswith(".md"):
            new_scenarios.append(path)

        # Modified or renamed SKILL.md files -- measure shrink.
        if (
            path.startswith("skills/")
            and path.endswith("SKILL.md")
            and status.startswith(("M", "R"))
        ):
            numstat = run(["git", "diff", "--numstat", diff_range, "--", path])
            if not numstat.strip():
                continue
            for nl in numstat.splitlines():
                np_ = nl.split("\t")
                if len(np_) < 3:
                    continue
                try:
                    added = int(np_[0])
                    deleted = int(np_[1])
                except ValueError:
                    continue
                base_blob = run(["git", "show", f"{base_ref}:{path}"])
                base_lines = base_blob.count("\n") if base_blob else 0
                if base_lines == 0:
                    continue
                shrink = (deleted - added) / base_lines if base_lines else 0
                if shrink >= SHRINK_RATIO:
                    slimmed_skills.append((path, base_lines, shrink))

    if not slimmed_skills or not new_agents:
        if slimmed_skills:
            for p, bl, sr in slimmed_skills:
                print(
                    f"INFO: {p} shrunk by {sr * 100:.0f}% (was {bl} lines) -- "
                    f"no new agent in this PR, not a Pattern A migration"
                )
        print("OK: no Pattern A migration signal in this PR (#665)")
        return 0

    matching = [s for s in new_scenarios if any(p.match(s) for p in SCENARIO_PATTERNS)]

    print("Pattern A migration detected:")
    for p, bl, sr in slimmed_skills:
        print(f"  slimmed skill: {p} (was {bl} lines, shrunk {sr * 100:.0f}%)")
    for a in new_agents:
        print(f"  new agent:     {a}")

    if matching:
        for s in matching:
            print(f"OK: Pattern A migration covered by scenario: {s} (#665)")
        return 0

    print("ERROR: Pattern A migration detected but no matching scenario added in this PR (#665).")
    print("       Add a scenario in scenarios/{domain}/ matching one of:")
    print("         *-pattern-a.md, *-shape.md, *-dispatch.md, *pattern*.md, *shape*.md, *dispatch*.md")
    print("       Reference scenarios:")
    print("         scenarios/crew/process-facilitator-pattern-a.md (PR #670)")
    print("         scenarios/jam/quick-facilitator-shape.md (PR #666)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
