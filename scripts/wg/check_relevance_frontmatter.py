#!/usr/bin/env python3
"""scripts/wg/check_relevance_frontmatter.py — phase + archetype frontmatter lint.

Scans ``skills/**/*.md`` for the ``phase_relevance`` and
``archetype_relevance`` fields introduced by the Issue #725 reframe
(context-aware ``crew:guide``). Skills-only cutover: the former
``commands/**/*.md`` leg was absorbed into the per-domain skills, so only
the skills tree is scanned now.

Modes (env: ``WG_RELEVANCE_LINT``)
  - ``deny`` (default since v9.2.9): same scan, but exit non-zero so CI fails.
    The bulk-pass PR (#834, v9.2.9) added frontmatter to the remaining 384
    commands/skills, so the lint can now block regressions.
  - ``warn``: emit a single WARN line listing the first ``MAX_LISTED`` offending
    paths and exit 0. Useful as a temporary opt-out during a refactor that
    intentionally adds files without frontmatter.
  - ``off``: skip the scan entirely (rollback lever for emergencies).

R1: no dead code — every helper is called from main().
R3: constants named (``MAX_LISTED``, ``ENV_MODE`` etc.).
R4: errors surface — broken frontmatter prints a WARN, doesn't silently pass.
R5: subprocess-free — pure stdlib, no external calls.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants  (R3)
# ---------------------------------------------------------------------------

ENV_MODE: str = "WG_RELEVANCE_LINT"
MODE_WARN: str = "warn"
MODE_DENY: str = "deny"
MODE_OFF: str = "off"
DEFAULT_MODE: str = MODE_DENY
VALID_MODES: tuple[str, ...] = (MODE_WARN, MODE_DENY, MODE_OFF)
MAX_LISTED: int = 5

REQUIRED_FIELDS: tuple[str, ...] = ("phase_relevance", "archetype_relevance")

# Repo root resolution: this file lives at scripts/wg/, so parents[2] is repo.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Frontmatter detector — same shape as scripts/crew/guide.py and
# hooks/scripts/pre_tool.py. Kept inline so this stays stdlib-only.
_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _resolve_mode() -> str:
    """Read the lint mode from the environment, defaulting to ``warn``.

    Unknown values fall back to ``warn`` and emit a stderr notice — silent
    drops would let typos turn lint into a no-op.
    """
    raw = (os.environ.get(ENV_MODE) or DEFAULT_MODE).strip().lower()
    if raw not in VALID_MODES:
        sys.stderr.write(
            f"WARNING: {ENV_MODE}={raw!r} is not one of {VALID_MODES} — "
            f"falling back to {DEFAULT_MODE!r}\n"
        )
        return DEFAULT_MODE
    return raw


def _has_field(text: str, field: str) -> bool:
    """Return True if ``text`` declares ``field`` in its YAML frontmatter."""
    m = _FRONTMATTER_BLOCK.match(text)
    if not m:
        return False
    block = m.group(1)
    pattern = re.compile(rf"^{re.escape(field)}\s*:", re.MULTILINE)
    return bool(pattern.search(block))


def _scan_one(path: Path) -> set[str]:
    """Return the set of REQUIRED_FIELDS missing from ``path``."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # Unreadable file — surface every field as missing so it doesn't
        # silently pass.
        return set(REQUIRED_FIELDS)
    return {f for f in REQUIRED_FIELDS if not _has_field(text, f)}


def _iter_targets(repo_root: Path) -> list[Path]:
    """Yield every ``skills/**/*.md`` path (skills-only cutover)."""
    out: list[Path] = []
    root = repo_root / "skills"
    if root.is_dir():
        out.extend(sorted(root.rglob("*.md")))
    return out


def main(argv: list[str]) -> int:
    """Entry point — returns the process exit code.

    Supports an optional ``--root <path>`` flag for tests; defaults to the
    repo root inferred from this file's location.
    """
    repo_root = _REPO_ROOT
    if "--root" in argv:
        idx = argv.index("--root")
        if idx + 1 < len(argv):
            repo_root = Path(argv[idx + 1]).resolve()

    mode = _resolve_mode()
    if mode == MODE_OFF:
        sys.stdout.write(f"OK: {ENV_MODE}=off — relevance frontmatter lint skipped\n")
        return 0

    targets = _iter_targets(repo_root)
    offenders: list[Path] = []
    for path in targets:
        missing = _scan_one(path)
        if missing:
            offenders.append(path)

    if not offenders:
        sys.stdout.write(
            "OK: every skill declares phase_relevance + archetype_relevance\n"
        )
        return 0

    listed = ", ".join(
        str(p.relative_to(repo_root)) for p in offenders[:MAX_LISTED]
    )
    suffix = "" if len(offenders) <= MAX_LISTED else f" (and {len(offenders) - MAX_LISTED} more)"
    label = "ERROR" if mode == MODE_DENY else "WARN"
    sys.stdout.write(
        f"{label}: missing relevance frontmatter — {len(offenders)} files: "
        f"{listed}{suffix}\n"
    )
    if mode == MODE_WARN:
        sys.stdout.write(
            f"NOTE: {ENV_MODE}={MODE_WARN} (default since v9.2.9 is "
            f"{MODE_DENY!r}; warn mode is the temporary opt-out).\n"
        )
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
