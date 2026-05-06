#!/usr/bin/env python3
"""scripts/wg/_relevance_bulkadd.py — Issue #725 bulk-pass tooling.

One-shot script that adds `phase_relevance` and `archetype_relevance`
frontmatter fields to every command/skill that lacks them. Directory-derived
defaults — every file gets a value that reflects its purpose rather than a
blanket `["*"]`.

This file lives under `scripts/wg/` (the dev-tools tree). After the bulk pass
ships and `WG_RELEVANCE_LINT` flips to `deny`, this script becomes legacy —
it's safe to delete in a future cleanup. We keep it for one release in case
a follow-up domain pass reuses the per-domain map.

Usage:
    sh scripts/_python.sh scripts/wg/_relevance_bulkadd.py [--dry-run]

R1: no dead code — each helper is called from main().
R3: constants named (DEFAULTS_BY_DOMAIN, REQUIRED_FIELDS).
R5: subprocess-free — pure stdlib.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Per-domain phase defaults. Archetype is "*" everywhere — narrowing per
# directory adds no signal at the bulk-pass stage.
DEFAULTS_BY_DOMAIN: dict[tuple[str, str], list[str]] = {
    # commands/
    ("commands", "<top>"): ["*"],
    ("commands", "crew"): ["*"],
    ("commands", "platform"): ["build", "review", "operate"],
    ("commands", "product"): ["clarify", "design", "review"],
    ("commands", "engineering"): ["design", "build"],
    ("commands", "search"): ["*"],
    ("commands", "jam"): ["clarify", "design"],
    ("commands", "delivery"): ["build", "review", "operate"],
    ("commands", "data"): ["design", "build"],
    ("commands", "agentic"): ["design", "review"],
    ("commands", "smaht"): ["*"],
    ("commands", "persona"): ["*"],
    ("commands", "mem"): ["*"],
    # skills/
    ("skills", "engineering"): ["design", "build"],
    ("skills", "product"): ["clarify", "design", "review"],
    ("skills", "platform"): ["build", "review", "operate"],
    ("skills", "agentic"): ["design", "review"],
    ("skills", "propose-process"): ["bootstrap", "clarify"],
    ("skills", "multi-model"): ["clarify", "design"],
    ("skills", "deliberate"): ["clarify", "design"],
    ("skills", "crew"): ["*"],
    ("skills", "delivery"): ["build", "review", "operate"],
    ("skills", "wickedizer"): ["*"],
    ("skills", "workflow"): ["*"],
    ("skills", "data"): ["design", "build"],
    ("skills", "integration-discovery"): ["bootstrap"],
    ("skills", "smaht"): ["*"],
    ("skills", "jam"): ["clarify", "design"],
    ("skills", "worktrees"): ["build"],
    ("skills", "search"): ["*"],
    ("skills", "runtime-exec"): ["*"],
    ("skills", "ground"): ["*"],
    ("skills", "facilitator-score"): ["clarify"],
    ("skills", "persona"): ["*"],
}

DEFAULT_ARCHETYPE: list[str] = ["*"]
REQUIRED_FIELDS: tuple[str, ...] = ("phase_relevance", "archetype_relevance")
_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _domain_key(path: Path) -> tuple[str, str]:
    """Return (root, domain) for a command/skill path. Top-level files
    under commands/ get domain "<top>"."""
    parts = path.parts
    if len(parts) >= 3:
        return (parts[0], parts[1])
    return (parts[0], "<top>")


def _phase_for(path: Path) -> list[str]:
    key = _domain_key(path)
    return DEFAULTS_BY_DOMAIN.get(key, ["*"])


def _has_field(text: str, field: str) -> bool:
    m = _FRONTMATTER_BLOCK.match(text)
    if not m:
        return False
    block = m.group(1)
    pat = re.compile(rf"^{re.escape(field)}\s*:", re.MULTILINE)
    return bool(pat.search(block))


def _format_list(values: list[str]) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


def _insert_fields(text: str, phase_values: list[str]) -> str:
    """Insert missing fields before the closing `---` of the frontmatter
    block. If no frontmatter exists, prepend a new one."""
    new_lines: list[str] = []
    if not _has_field(text, "phase_relevance"):
        new_lines.append(f"phase_relevance: {_format_list(phase_values)}")
    if not _has_field(text, "archetype_relevance"):
        new_lines.append(f"archetype_relevance: {_format_list(DEFAULT_ARCHETYPE)}")

    if not new_lines:
        return text  # nothing to add — both fields already present

    m = _FRONTMATTER_BLOCK.match(text)
    if m:
        # Insert before the closing ---. Frontmatter ends at m.end().
        # The closing fence is the second "---". m.end() includes it.
        # We want to insert the new lines RIGHT before the closing fence.
        inner = m.group(1)
        # Find offset of closing ---. m.end() points to char after the
        # closing ---, but text[m.start():m.end()] = "---\n<inner>\n---".
        # Easiest: rebuild the frontmatter from inner + new + closing fence.
        rebuilt = "---\n" + inner.rstrip() + "\n" + "\n".join(new_lines) + "\n---"
        return rebuilt + text[m.end():]
    # No frontmatter at all — prepend a new block.
    return "---\n" + "\n".join(new_lines) + "\n---\n" + text


def _iter_targets(repo_root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in ("commands", "skills"):
        root = repo_root / sub
        if root.is_dir():
            out.extend(sorted(root.rglob("*.md")))
    return out


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dry_run = "--dry-run" in argv

    targets = _iter_targets(repo_root)
    edited = 0
    skipped = 0
    for path in targets:
        rel = path.relative_to(repo_root)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            sys.stderr.write(f"WARN: cannot read {rel}: {e}\n")
            continue

        if _has_field(text, "phase_relevance") and _has_field(text, "archetype_relevance"):
            skipped += 1
            continue

        new_text = _insert_fields(text, _phase_for(rel))
        if new_text == text:
            skipped += 1
            continue

        if not dry_run:
            path.write_text(new_text, encoding="utf-8")
        edited += 1

    label = "WOULD EDIT" if dry_run else "EDITED"
    sys.stdout.write(
        f"{label}: {edited} files; SKIPPED (already complete): {skipped} files\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
