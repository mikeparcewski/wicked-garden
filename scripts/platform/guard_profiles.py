#!/usr/bin/env python3
"""
guard_profiles.py — Profile definitions + auto-select logic for the
autonomous session-close guard pipeline (Issue #448).

Three tiered profiles govern how much work the guard pipeline does at
session close or phase checkpoints:

    scalpel  (~1s)  — always runs. Regex/line-pattern scans only.
                      Debug artifacts + R1-R6 surface-level bulletproof
                      heuristics.  Cheap enough to run on every Stop hook.

    standard (~5s)  — runs at build-phase close or session close after
                      substantial changes.  Adds ADR constraint scan,
                      spec-drift semantic review (optional), and unresolved
                      skip-reeval entries.

    deep     (~30s) — runs on explicit invocation or release-branch sessions.
                      Full checks + deeper semantic review pass.

Auto-select rules (one-liner per profile):

    deep     — on release/main branch sessions OR explicit WG_GUARD_PROFILE=deep
    standard — build-phase just closed, or >= 10 changed files in diff
    scalpel  — everything else (default, fail-open minimum)

The selector never raises; every branch falls back to ``scalpel`` on error.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


# ---------------------------------------------------------------------------
# Budgets — seconds
# ---------------------------------------------------------------------------

SCALPEL_BUDGET_SECONDS = 1.0
STANDARD_BUDGET_SECONDS = 5.0
DEEP_BUDGET_SECONDS = 30.0

# Threshold of changed files that promotes scalpel → standard.
_SUBSTANTIAL_CHANGE_THRESHOLD = 10

# Branch names that auto-promote to deep.
_RELEASE_BRANCH_NAMES = frozenset({"main", "master", "release", "production"})


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GuardProfile:
    """Runtime profile for the guard pipeline."""

    name: str
    budget_seconds: float
    checks: tuple  # tuple of check-name strings
    include_semantic_review: bool
    description: str


# Check names — must match keys in guard_pipeline.CHECK_REGISTRY
_SCALPEL_CHECKS = ("bulletproof_scan", "debug_artifacts")
_STANDARD_CHECKS = (
    "bulletproof_scan",
    "debug_artifacts",
    "adr_constraints",
    "semantic_review",
    "skip_log",
)
_DEEP_CHECKS = _STANDARD_CHECKS  # same check set, deeper semantic review


SCALPEL = GuardProfile(
    name="scalpel",
    budget_seconds=SCALPEL_BUDGET_SECONDS,
    checks=_SCALPEL_CHECKS,
    include_semantic_review=False,
    description="Fast regex-only scan (<1s). Always runs.",
)

STANDARD = GuardProfile(
    name="standard",
    budget_seconds=STANDARD_BUDGET_SECONDS,
    checks=_STANDARD_CHECKS,
    include_semantic_review=True,
    description="Build-phase close or substantial changes (~5s).",
)

DEEP = GuardProfile(
    name="deep",
    budget_seconds=DEEP_BUDGET_SECONDS,
    checks=_DEEP_CHECKS,
    include_semantic_review=True,
    description="Release branch or explicit invocation (~30s).",
)

_PROFILES_BY_NAME = {p.name: p for p in (SCALPEL, STANDARD, DEEP)}


def get_profile(name: str) -> GuardProfile:
    """Return the named profile, falling back to scalpel on miss."""
    return _PROFILES_BY_NAME.get((name or "").strip().lower(), SCALPEL)


# ---------------------------------------------------------------------------
# Auto-select logic
# ---------------------------------------------------------------------------

def _current_branch(cwd: Optional[Path] = None) -> Optional[str]:
    """Return the current git branch, or None on error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch or None
    except Exception:
        pass  # fail open — callers treat None as "unknown branch"
    return None


def _count_changed_files(cwd: Optional[Path] = None) -> int:
    """Count changed files vs HEAD (staged + unstaged + untracked tracked)."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            return len(lines)
    except Exception:
        pass  # fail open — treat unknowable diffs as "zero" (safest profile)
    return 0


def auto_select(
    *,
    build_phase_just_closed: bool = False,
    explicit_profile: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> GuardProfile:
    """Auto-select the guard profile based on session context.

    Args:
        build_phase_just_closed: True if the crew build phase was just approved
            (promotes scalpel → standard).
        explicit_profile: Overrides auto-selection.  Takes env var
            ``WG_GUARD_PROFILE`` into account when not supplied.
        cwd: Working directory for git probes.  Defaults to process cwd.

    Returns:
        The selected GuardProfile.  Never raises — falls back to SCALPEL on error.
    """
    # Explicit arg wins
    chosen = (explicit_profile or os.environ.get("WG_GUARD_PROFILE") or "").strip().lower()
    if chosen in _PROFILES_BY_NAME:
        return _PROFILES_BY_NAME[chosen]

    try:
        branch = _current_branch(cwd)
        if branch and branch in _RELEASE_BRANCH_NAMES:
            return DEEP

        if build_phase_just_closed:
            return STANDARD

        changed = _count_changed_files(cwd)
        if changed >= _SUBSTANTIAL_CHANGE_THRESHOLD:
            return STANDARD
    except Exception:
        # Any unexpected error → safest (cheapest) profile
        return SCALPEL

    return SCALPEL


# ---------------------------------------------------------------------------
# CLI for debugging: `python3 guard_profiles.py --explain`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    args = sys.argv[1:]
    if "--explain" in args:
        profile = auto_select(cwd=Path.cwd())
        out = {
            "profile": profile.name,
            "budget_seconds": profile.budget_seconds,
            "checks": list(profile.checks),
            "description": profile.description,
        }
        sys.stdout.write(json.dumps(out, indent=2))
        sys.stdout.write("\n")
        sys.exit(0)

    sys.stdout.write("Usage: guard_profiles.py --explain\n")
    sys.exit(1)
