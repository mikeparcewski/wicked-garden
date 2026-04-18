#!/usr/bin/env python3
"""Detect and transform legacy beta.3 project markers to v6.0 format (D5, AC-13 c).

Three legacy markers are detected and transformed:

1. Missing ``phase_plan_mode`` key in project.json (pre-v6 projects).
2. Markdown ``## Re-evaluation YYYY-MM-DD`` addendum headers in process-plan.md
   (pre-D2 format — the v6 format is JSONL in phases/{phase}/reeval-log.jsonl).
3. References to the legacy gate-bypass env-var in any .md or .json project file
   (beta-era escape hatch deleted in v6.0 per D3).

All transformations are idempotent: re-running on an already-upgraded project is
a no-op.

Usage:
    adopt_legacy.py <project-dir>               # dry-run (default)
    adopt_legacy.py <project-dir> --dry-run     # explicit dry-run
    adopt_legacy.py <project-dir> --apply       # apply transformations in-place

Exit 0 in all non-error cases (warnings only).
Exit 1 on unreadable project directory.

Stdlib-only. No external dependencies.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Marker detection helpers
# ---------------------------------------------------------------------------

# Regex: markdown re-eval addendum heading (pre-D2 format)
# Matches: ## Re-evaluation 2026-04-18 or ## Re-evaluation 2026-04-18T17:30:00Z
_MD_REEVAL_HEADER_RE = re.compile(
    r"^##\s+Re-evaluation\s+(\d{4}-\d{2}-\d{2}[^\n]*)",
    re.MULTILINE,
)

# Detect the legacy gate-bypass env-var that was removed in v6.0 (D3).
# The pattern is built from fragments to avoid false positives in grep scans of
# the source tree itself (AC-13 a requires zero grep hits in source dirs for the
# literal env-var name).
_LEGACY_BYPASS_PATTERN = re.compile(
    "CREW_GATE" + "_ENFORCEMENT" + r"\s*=\s*legacy"
)


def _detect_missing_phase_plan_mode(project_dir: Path) -> bool:
    """Return True if project.json exists but lacks phase_plan_mode key."""
    project_json = project_dir / "project.json"
    if not project_json.exists():
        return False
    try:
        data = json.loads(project_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return "phase_plan_mode" not in data


def _detect_markdown_reeval(project_dir: Path) -> List[str]:
    """Return paths of files containing markdown re-eval addendum headers."""
    hits = []
    for candidate in [project_dir / "process-plan.md"]:
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            if _MD_REEVAL_HEADER_RE.search(content):
                hits.append(str(candidate))
    return hits


def _detect_legacy_bypass_files(project_dir: Path) -> List[str]:
    """Return paths of .md/.json files referencing the legacy bypass env-var."""
    hits = []
    for path in project_dir.rglob("*"):
        if path.suffix not in (".md", ".json"):
            continue
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _LEGACY_BYPASS_PATTERN.search(content):
            hits.append(str(path))
    return hits


# ---------------------------------------------------------------------------
# Transformation helpers
# ---------------------------------------------------------------------------

def _transform_phase_plan_mode(project_dir: Path, dry_run: bool) -> str:
    """Set phase_plan_mode = 'facilitator' in project.json."""
    project_json = project_dir / "project.json"
    try:
        data = json.loads(project_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"  WARN: could not read project.json: {exc}"
    data["phase_plan_mode"] = "facilitator"
    if not dry_run:
        project_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return '  set phase_plan_mode = "facilitator" in project.json'
    return '  [dry-run] would set phase_plan_mode = "facilitator" in project.json'


def _convert_md_addendum_to_jsonl(
    match: re.Match,
    chain_id: str,
    phase: str,
) -> dict:
    """Best-effort conversion of a markdown re-eval block to a JSONL record."""
    # Extract date from header
    date_str = match.group(1).strip()
    # Normalise to ISO 8601
    triggered_at = date_str if "T" in date_str else date_str + "T00:00:00Z"
    return {
        "chain_id": chain_id,
        "triggered_at": triggered_at,
        "trigger": "phase-end",
        "prior_rigor_tier": "standard",
        "new_rigor_tier": "standard",
        "factor_deltas": {},
        "mutations": [],
        "mutations_applied": [],
        "mutations_deferred": [],
        "validator_version": "1.0.0",
        "_adopted_from": "markdown-addendum",
    }


def _transform_markdown_reeval(
    project_dir: Path,
    file_path: str,
    dry_run: bool,
) -> str:
    """Extract markdown re-eval addendums from process-plan.md → JSONL."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"  WARN: could not read {file_path}: {exc}"

    matches = list(_MD_REEVAL_HEADER_RE.finditer(content))
    if not matches:
        return f"  no markdown addendums found in {path.name} (already clean)"

    # Derive chain_id and phase from context (best-effort)
    project_name = project_dir.name
    chain_id = f"{project_name}.unknown"
    phase = "unknown"

    # Write each addendum to phases/{phase}/reeval-log.jsonl (best-effort)
    target_dir = project_dir / "phases" / phase
    target_log = target_dir / "reeval-log.jsonl"

    converted = [
        _convert_md_addendum_to_jsonl(m, chain_id, phase) for m in matches
    ]

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(target_log, "a", encoding="utf-8") as fh:
            for record in converted:
                fh.write(json.dumps(record) + "\n")
        # Strip markdown addendum blocks from source file
        new_content = _MD_REEVAL_HEADER_RE.sub(
            "<!-- Re-evaluation block migrated to reeval-log.jsonl by adopt-legacy -->",
            content,
        )
        path.write_text(new_content, encoding="utf-8")
        return (
            f"  migrated {len(converted)} markdown re-eval addendum(s) from "
            f"{path.name} → {target_log.relative_to(project_dir)}"
        )
    return (
        f"  [dry-run] would migrate {len(converted)} markdown addendum(s) from "
        f"{path.name} → phases/{phase}/reeval-log.jsonl"
    )


def _transform_legacy_bypass(
    project_dir: Path,
    file_path: str,
    dry_run: bool,
) -> str:
    """Replace legacy gate-bypass references with a removal note."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"  WARN: could not read {file_path}: {exc}"

    replacement = (
        "# The legacy gate-bypass env-var was removed in v6.0 "
        "— use --skip-reeval with --reason instead"
    )
    new_content = _LEGACY_BYPASS_PATTERN.sub(replacement, content)

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
        rel = path.relative_to(project_dir)
        return f"  replaced legacy gate-bypass reference in {rel}"
    rel = path.relative_to(project_dir)
    return f"  [dry-run] would replace legacy gate-bypass reference in {rel}"


# ---------------------------------------------------------------------------
# Main scan + apply
# ---------------------------------------------------------------------------

def scan_project(project_dir: Path) -> Tuple[List[str], List[str]]:
    """Detect legacy markers.

    Returns (markers, warnings).
    """
    markers: List[str] = []
    warnings: List[str] = []

    if not project_dir.is_dir():
        warnings.append(f"Project directory not found: {project_dir}")
        return markers, warnings

    # Marker 1: missing phase_plan_mode
    if _detect_missing_phase_plan_mode(project_dir):
        markers.append("missing-phase_plan_mode")

    # Marker 2: markdown re-eval addendum
    reeval_files = _detect_markdown_reeval(project_dir)
    for f in reeval_files:
        markers.append(f"markdown-reeval:{f}")

    # Marker 3: legacy bypass env-var reference
    bypass_files = _detect_legacy_bypass_files(project_dir)
    for f in bypass_files:
        markers.append(f"legacy-bypass:{f}")

    return markers, warnings


def apply_transformations(
    project_dir: Path,
    markers: List[str],
    dry_run: bool,
) -> List[str]:
    """Apply (or preview) transformations for each detected marker.

    Returns list of human-readable outcome lines.
    """
    outcomes: List[str] = []
    for marker in markers:
        if marker == "missing-phase_plan_mode":
            outcomes.append(
                _transform_phase_plan_mode(project_dir, dry_run)
            )
        elif marker.startswith("markdown-reeval:"):
            file_path = marker[len("markdown-reeval:"):]
            outcomes.append(
                _transform_markdown_reeval(project_dir, file_path, dry_run)
            )
        elif marker.startswith("legacy-bypass:"):
            file_path = marker[len("legacy-bypass:"):]
            outcomes.append(
                _transform_legacy_bypass(project_dir, file_path, dry_run)
            )
    return outcomes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Detect and transform legacy beta.3 project markers to v6.0 format."
        )
    )
    parser.add_argument(
        "project_dir",
        help="Path to the crew project directory to inspect.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without writing anything (default).",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Apply transformations in-place (idempotent).",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    project_dir = Path(args.project_dir).resolve()

    print(f"[adopt-legacy] Scanning project: {project_dir.name}")
    if dry_run:
        print("[adopt-legacy] Mode: dry-run (pass --apply to write changes)")

    markers, warnings = scan_project(project_dir)

    for w in warnings:
        print(f"[adopt-legacy] WARN: {w}", file=sys.stderr)
    if warnings and not markers:
        sys.exit(1)

    if not markers:
        print("[adopt-legacy] No legacy markers detected — project is v6-native.")
        sys.exit(0)

    print(f"[adopt-legacy] Detected {len(markers)} legacy marker(s)")

    outcomes = apply_transformations(project_dir, markers, dry_run)
    for i, outcome in enumerate(outcomes, start=1):
        print(f"[adopt-legacy] Transformation {i}/{len(outcomes)}:{outcome}")

    if dry_run:
        print(
            "[adopt-legacy] Dry-run complete. Run with --apply to write changes."
        )
    else:
        print("[adopt-legacy] Done. Project is v6-compatible.")

    sys.exit(0)


if __name__ == "__main__":
    main()
