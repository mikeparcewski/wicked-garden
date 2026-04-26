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


def run(cmd: list[str]) -> str | None:
    """Run a git command and return stdout (possibly empty) on success, or None on error.

    F10 (#675 sweep): the previous implementation collapsed both "command failed"
    and "command succeeded with empty output" into the same empty-string return
    value, so a missing `origin/main` ref looked identical to a clean diff. We
    now return ``None`` on any non-zero exit (or exception) so the caller can
    distinguish the two and surface a useful message.
    """
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            stderr = (r.stderr or "").strip()
            sys.stderr.write(
                f"WARNING: `{' '.join(cmd)}` exited {r.returncode}: {stderr}\n"
            )
            return None
        return r.stdout
    except Exception as exc:  # noqa: BLE001 -- fail-open per design, but log the cause
        sys.stderr.write(f"WARNING: `{' '.join(cmd)}` raised {exc!r}\n")
        return None


def resolve_base_ref() -> str:
    """Resolve the PR base ref for `git diff <base>...HEAD`.

    Resolution order:
      1. ``WG_PR_BASE_REF`` env var (escape hatch for local testing).
      2. ``GITHUB_BASE_REF`` env var (set by GitHub Actions on pull_request).
      3. Default: ``origin/main``.

    F11 (#675 sweep): the previous implementation special-cased the literal
    ``"main"`` as already-fully-qualified, but that left ambiguity between the
    local branch and the remote-tracking ref. We now ALWAYS prepend ``origin/``
    when the ref doesn't already include a remote prefix, matching the
    "compare PR head to the remote base" semantics the gate is documented to
    enforce. To opt out, set ``WG_PR_BASE_REF=main`` explicitly with a
    pre-stripped value -- the env var wins regardless and short-circuits the
    normalization (the env var is treated as caller-authoritative).
    """
    explicit = os.environ.get("WG_PR_BASE_REF")
    if explicit:
        return explicit
    base = os.environ.get("GITHUB_BASE_REF") or "origin/main"
    if "/" not in base:
        base = f"origin/{base}"
    return base


def main() -> int:
    base_ref = resolve_base_ref()
    diff_range = f"{base_ref}...HEAD"

    name_status = run(["git", "diff", "--name-status", diff_range])
    if name_status is None:
        # F10 (#675 sweep): a real git error (missing ref, shallow checkout) --
        # surface explicitly instead of pretending the diff was empty. Still
        # exit 0 so we don't break local `wg-check` runs that happen to be on
        # main without the remote fetched, but the warning makes the cause
        # visible.
        print(
            f"WARNING: `git diff --name-status {diff_range}` failed -- "
            "Pattern A gate skipped (fail-open). Check that the base ref "
            "exists locally (`git fetch origin`) and that the working tree "
            "is not a shallow clone."
        )
        return 0
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

        # F9 (#675 sweep): renames are reported as `R<score>\told_path\tnew_path`.
        # Previously we only looked at parts[-1] (the new path) and then ran
        # `git show base_ref:new_path` -- which fails silently if the file had
        # a different name in the base ref. Result: renamed SKILL.md files were
        # invisible to the shrink computation. We now keep both paths and use
        # the OLD path against base_ref / NEW path against HEAD.
        if status.startswith("R") and len(parts) >= 3:
            old_path = parts[1].strip()
            new_path = parts[2].strip()
        else:
            old_path = parts[-1].strip()
            new_path = parts[-1].strip()
        path = new_path

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
            # F9 (#675 sweep): for a rename, the most reliable shrink estimate
            # is comparing line counts directly: base_lines (from old_path in
            # base_ref) vs head_lines (from new_path at HEAD). git's --numstat
            # output is ambiguous for renames -- if you path-restrict it, you
            # get bogus add-only / delete-only rows; if you don't restrict,
            # you get the rename row but still need to parse the path arrow.
            # Direct line-count comparison sidesteps both problems.
            base_blob = run(["git", "show", f"{base_ref}:{old_path}"])
            head_blob = run(["git", "show", f"HEAD:{new_path}"])
            base_lines = base_blob.count("\n") if base_blob else 0
            head_lines = head_blob.count("\n") if head_blob else 0
            if base_lines == 0:
                continue
            shrink = (base_lines - head_lines) / base_lines
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
