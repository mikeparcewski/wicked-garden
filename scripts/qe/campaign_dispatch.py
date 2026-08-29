#!/usr/bin/env python3
"""qe dispatch guard (TH-7, guard half of the retired agent-surface cleanup).

Every qe dispatch resolves its specialist through `resolve_specialist()`
before the Skill call. The guard asserts the resolved specialist is a garden
`wicked-garden-qe-*` worker that actually ships in the catalog, and BLOCKS
retired surfaces at dispatch with a clear error:

- `wicked-testing-*` — wicked-testing retired 2026-08 (Phase 6); its 40
  specialists live on as garden's qe domain. The error names the garden
  replacement; resolution is never silently rewritten.
- `wicked-brain-*` — wicked-brain retired 2026-08 (Phase 5-S7); the agent
  surface is wicked-garden-mem / wicked-garden-search.

Accepted spellings: canonical `wicked-garden-qe-<role>` and the bare
`qe-<role>` shorthand (expanded to canonical). Anything else is not a
garden qe specialist and is refused.

Cross-platform: pure stdlib (pathlib/re), no shell.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

GARDEN_QE_PREFIX = "wicked-garden-qe-"

_RETIRED = {
    "wicked-testing-": (
        "wicked-testing retired 2026-08 (Phase 6); its specialists are "
        "garden's qe domain"
    ),
    "wicked-brain-": (
        "wicked-brain retired 2026-08 (Phase 5-S7); the agent surface is "
        "wicked-garden-mem / wicked-garden-search"
    ),
}

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


class DispatchGuardError(ValueError):
    """Dispatch refused: retired, non-qe, or unknown specialist."""


def _catalog_name(role: str, skills_dir: Path) -> str | None:
    """The frontmatter `name:` of skills/qe-<role>/SKILL.md, if it exists."""
    skill_md = skills_dir / f"qe-{role}" / "SKILL.md"
    if not skill_md.is_file():
        return None
    match = _FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
    if not match:
        return None
    name = _NAME_RE.search(match.group(1))
    return name.group(1) if name else None


def resolve_specialist(requested: str, skills_dir: Path | None = None) -> str:
    """Resolve a requested specialist to its canonical garden qe name.

    Returns the canonical `wicked-garden-qe-<role>` name, or raises
    DispatchGuardError. Never rewrites a retired name silently — the caller
    (and the transcript) must see the block.
    """
    skills_dir = Path(skills_dir) if skills_dir else _REPO_ROOT / "skills"
    name = (requested or "").strip()
    if not name:
        raise DispatchGuardError("dispatch guard: empty specialist name")

    for prefix, why in _RETIRED.items():
        if name.startswith(prefix):
            role = name[len(prefix):]
            hint = ""
            if prefix == "wicked-testing-" and _catalog_name(role, skills_dir):
                hint = (
                    f" Dispatch '{GARDEN_QE_PREFIX}{role}' instead."
                )
            raise DispatchGuardError(
                f"dispatch guard: BLOCKED retired specialist {name!r} — "
                f"{why}.{hint}"
            )

    if name.startswith(GARDEN_QE_PREFIX):
        canonical = name
    elif name.startswith("qe-"):
        canonical = "wicked-garden-" + name
    else:
        raise DispatchGuardError(
            f"dispatch guard: {name!r} is not a garden qe-* specialist — qe "
            f"dispatch only resolves '{GARDEN_QE_PREFIX}<role>' workers "
            "(see the roster in skills/qe/SKILL.md)"
        )

    role = canonical[len(GARDEN_QE_PREFIX):]
    if not role:
        raise DispatchGuardError(
            "dispatch guard: dispatch a qe specialist, not the "
            "'wicked-garden-qe' router itself"
        )
    catalog = _catalog_name(role, skills_dir)
    if catalog != canonical:
        raise DispatchGuardError(
            f"dispatch guard: {canonical!r} is not in the qe catalog "
            f"(no skills/qe-{role}/SKILL.md with that name) — see the "
            "roster in skills/qe/SKILL.md"
        )
    return canonical


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: campaign_dispatch.py <specialist> [--skills-dir DIR]")
        return 0
    skills_dir = None
    if "--skills-dir" in argv:
        i = argv.index("--skills-dir")
        skills_dir = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    try:
        print(resolve_specialist(argv[0], skills_dir=skills_dir))
    except DispatchGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
