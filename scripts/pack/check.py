#!/usr/bin/env python3
"""check.py — the shipped pack conformance gate (extension-contract gap 3).

Validates a third-party pack against the catalog rules the ruling codified
(SKILL-RATIONALIZATION §4 naming rules + SKILLS-GUIDELINES disclosure tiers),
executable OUTSIDE garden's dev tree: this file ships in the npm package and
the installed plugin, so pack authors run it as

    npx wicked-garden pack check <pack-dir>
    # or directly:
    python3 scripts/pack/check.py <pack-dir> [--json] [--garden-root DIR]

Exit code 0 = conformant (warnings allowed), 1 = errors found, 2 = usage.

Rule codes
----------
  PK001  wicked-pack.json missing or unparseable
  PK002  manifest structural error (spec/name/vendor/version/skills_dir/domains)
  PK010  skills tree empty
  PK011  SKILL.md missing frontmatter, name, or description
  PK012  skill name not kebab-case or > 64 chars
  PK013  skill name not prefixed with "{vendor}-"
  PK014  declared domain has no router skill "{vendor}-{domain}"
  PK015  router skill must not declare context: fork
  PK016  worker skill "{vendor}-{domain}-{role}" must declare context: fork
  PK017  skill directory name must match frontmatter name
  PK018  skill does not belong to any declared domain
  PK020  non-fork SKILL.md exceeds 200 lines (tier-2 disclosure cap)
  PK021  frontmatter description exceeds ~120 words (tier-1 cap) [warn]
  PK022  refs/ file exceeds 350 lines (tier-3 band is 200-300) [warn]
  PK030  NOT-THIS-WHEN reciprocity: same-pack twin does not point back
  PK031  NOT-THIS-WHEN target skill not found [warn]
  PK040  produces contract names an unknown archetype
  PK041  produces id not kebab-case
  PK042  specialist "enhances" phase not a known crew phase [warn]
  PK050  peer floor range malformed (expected ">=X.Y.Z" or "^X.Y.Z")

stdlib-only. Imports the manifest loader from scripts/_pack_registry.py
(same package layout in the repo, the npm tarball, and the installed
plugin), so validation and discovery can never drift apart.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# scripts/ on sys.path so _pack_registry resolves in-repo, in the npm
# tarball, and in the installed plugin (all share the scripts/ layout).
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _pack_registry import (  # noqa: E402
    MANIFEST_NAME,
    _KEBAB_RE,
    _FLOOR_RE,
    _MAX_NAME_LEN,
    load_manifest,
    structural_errors,
)

# Fallback archetype catalog — kept in sync with .claude-plugin/archetypes.json;
# when a garden root is locatable the live file wins (see _known_archetypes).
_FALLBACK_ARCHETYPES = (
    "triage", "explore", "specify", "decide", "ship",
    "review", "incident", "build", "migrate", "modernize",
)

# Crew phases a specialist may declare in "enhances" (specialist.json usage).
_KNOWN_PHASES = {"clarify", "design", "qe", "build", "review", "operate", "*"}

_FRONTMATTER_FENCE = "---"
_MAX_BODY_LINES = 200
_MAX_DESC_WORDS = 120
_MAX_REF_LINES = 350
_NOT_THIS_WHEN_RE = re.compile(r"NOT[ -]THIS[ -]WHEN", re.IGNORECASE)
_BACKTICK_NAME_RE = re.compile(r"`([a-z0-9][a-z0-9-]*)`")


class Finding:
    __slots__ = ("code", "level", "where", "message")

    def __init__(self, code: str, level: str, where: str, message: str):
        self.code = code
        self.level = level  # "error" | "warn"
        self.where = where
        self.message = message

    def as_dict(self) -> dict:
        return {"code": self.code, "level": self.level,
                "where": self.where, "message": self.message}

    def render(self) -> str:
        return f"{self.code} [{self.level.upper()}] {self.where}: {self.message}"


def _parse_frontmatter(text: str) -> tuple:
    """Return ``(frontmatter_dict, fm_line_count)``.

    Scalar top-level keys only, plus multi-line ``description: |`` blocks
    captured verbatim — mirrors the resolver's line-scan (no YAML lib).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return {}, 0
    fm: dict = {}
    desc_lines: list = []
    in_desc = False
    end = 0
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_FENCE:
            end = i
            break
        if in_desc:
            if line.startswith((" ", "\t")) or not line.strip():
                desc_lines.append(line.strip())
                continue
            in_desc = False
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if key == "description" and val in ("|", ">", "|-", ">-"):
                in_desc = True
                continue
            fm.setdefault(key, val)
    if desc_lines:
        fm["description"] = " ".join(l for l in desc_lines if l)
    return fm, end


def _known_archetypes(garden_root: "Path | None") -> set:
    roots = [garden_root] if garden_root else []
    import os
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        roots.append(Path(env_root))
    roots.append(_SCRIPTS_DIR.parent)  # in-repo / installed-plugin layout
    for root in roots:
        try:
            data = json.loads(
                (Path(root) / ".claude-plugin" / "archetypes.json").read_text(encoding="utf-8"))
            names = set(data.get("archetypes", {}).keys())
            if names:
                return names
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return set(_FALLBACK_ARCHETYPES)


def _garden_skill_exists(name: str, garden_root: "Path | None") -> "bool | None":
    """True/False when a garden skills tree is locatable; None when unknown."""
    import os
    roots = [garden_root] if garden_root else []
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        roots.append(Path(env_root))
    roots.append(_SCRIPTS_DIR.parent)
    for root in roots:
        skills = Path(root) / "skills"
        if skills.is_dir():
            return (skills / name / "SKILL.md").is_file()
    return None


def check_pack(pack_root: Path, *, garden_root: "Path | None" = None) -> list:
    """Run every rule; return the full findings list (errors + warnings)."""
    findings: list = []
    err = lambda code, where, msg: findings.append(Finding(code, "error", where, msg))  # noqa: E731
    warn = lambda code, where, msg: findings.append(Finding(code, "warn", where, msg))  # noqa: E731

    pack_root = Path(pack_root).resolve()
    manifest, load_errs = load_manifest(pack_root)
    if manifest is None:
        for e in load_errs:
            err("PK001", MANIFEST_NAME, e)
        return findings

    for e in structural_errors(manifest, pack_root):
        err("PK002", MANIFEST_NAME, e)
    if any(f.code == "PK002" and "skills dir" in f.message for f in findings):
        return findings  # cannot walk a missing tree

    vendor = str(manifest.get("vendor", ""))
    skills_dir = pack_root / str(manifest.get("skills_dir", "skills"))
    domain_names = [d.get("name", "") for d in manifest.get("domains", [])
                    if isinstance(d, dict)]

    # ---- walk the skills tree -------------------------------------------
    skill_files = sorted(skills_dir.rglob("SKILL.md")) if skills_dir.is_dir() else []
    if not skill_files:
        err("PK010", str(skills_dir), "no SKILL.md files found")
        return findings

    skills: dict = {}   # name -> {fm, path, text, is_fork}
    for skill_md in skill_files:
        rel = str(skill_md.relative_to(pack_root))
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError as exc:
            err("PK011", rel, f"unreadable: {exc}")
            continue
        fm, _ = _parse_frontmatter(text)
        name = fm.get("name", "")
        if not fm or not name or not fm.get("description"):
            err("PK011", rel, "frontmatter must declare name + description")
            continue
        if not _KEBAB_RE.match(name) or len(name) > _MAX_NAME_LEN:
            err("PK012", rel, f"skill name {name!r} must be kebab-case, <= {_MAX_NAME_LEN} chars")
        if vendor and not (name == vendor or name.startswith(vendor + "-")):
            err("PK013", rel, f"skill name {name!r} must be prefixed with vendor {vendor!r}")
        if skill_md.parent.name != name:
            err("PK017", rel, f"directory {skill_md.parent.name!r} must match skill name {name!r}")
        skills[name] = {
            "fm": fm, "path": rel, "text": text,
            "is_fork": fm.get("context", "") == "fork",
        }

    # ---- router / worker shape per declared domain ----------------------
    router_names = {f"{vendor}-{d}" for d in domain_names}
    for d in domain_names:
        router = f"{vendor}-{d}"
        if router not in skills:
            err("PK014", MANIFEST_NAME,
                f"domain {d!r} has no router skill {router!r} (one router per domain)")
        elif skills[router]["is_fork"]:
            err("PK015", skills[router]["path"],
                f"router {router!r} must be user-invocable, not context: fork")

    for name, info in skills.items():
        if name in router_names:
            continue
        owner = next((d for d in sorted(domain_names, key=len, reverse=True)
                      if name.startswith(f"{vendor}-{d}-")), None)
        if owner is None:
            err("PK018", info["path"],
                f"skill {name!r} does not belong to any declared domain "
                f"(expected {vendor}-{{domain}}-{{role}} with domain in {domain_names})")
            continue
        if not info["is_fork"]:
            err("PK016", info["path"],
                f"worker {name!r} must declare context: fork (isolated subagent)")

    # ---- disclosure tiers ------------------------------------------------
    for name, info in skills.items():
        line_count = len(info["text"].splitlines())
        if not info["is_fork"] and line_count > _MAX_BODY_LINES:
            err("PK020", info["path"],
                f"{line_count} lines (tier-2 cap is {_MAX_BODY_LINES}; "
                "move detail into refs/)")
        desc_words = len(str(info["fm"].get("description", "")).split())
        if desc_words > _MAX_DESC_WORDS:
            warn("PK021", info["path"],
                 f"frontmatter description is {desc_words} words "
                 f"(tier-1 guidance is ~100, cap {_MAX_DESC_WORDS})")
    if skills_dir.is_dir():
        for ref in sorted(skills_dir.rglob("refs/*.md")):
            try:
                ref_lines = len(ref.read_text(encoding="utf-8").splitlines())
            except OSError:
                continue
            if ref_lines > _MAX_REF_LINES:
                warn("PK022", str(ref.relative_to(pack_root)),
                     f"{ref_lines} lines (tier-3 band is 200-300)")

    # ---- NOT-THIS-WHEN reciprocity ---------------------------------------
    ntw: dict = {}
    for name, info in skills.items():
        refs = set()
        for chunk in (str(info["fm"].get("description", "")), info["text"]):
            for block in _NOT_THIS_WHEN_RE.split(chunk)[1:]:
                # names referenced in the sentence(s) after the marker
                refs.update(_BACKTICK_NAME_RE.findall(block[:400]))
        ntw[name] = {r for r in refs if r != name}
    for name, targets in ntw.items():
        for target in sorted(targets):
            if target in skills:
                if name not in ntw.get(target, set()):
                    err("PK030", skills[name]["path"],
                        f"NOT-THIS-WHEN names `{target}` but `{target}` does not "
                        f"point back at `{name}` (twins must be reciprocal)")
            elif target.startswith("wicked-garden-"):
                exists = _garden_skill_exists(target, garden_root)
                if exists is False:
                    warn("PK031", skills[name]["path"],
                         f"NOT-THIS-WHEN target `{target}` not found in the garden catalog")
            elif target.startswith(vendor + "-") or target in router_names:
                warn("PK031", skills[name]["path"],
                     f"NOT-THIS-WHEN target `{target}` not found in this pack")

    # ---- produces contracts + specialist blocks ---------------------------
    archetypes = _known_archetypes(garden_root)
    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict):
            continue
        d = domain.get("name", "?")
        for contract in domain.get("produces", []) or []:
            if not isinstance(contract, dict):
                err("PK040", MANIFEST_NAME, f"domain {d!r}: produces entry must be an object")
                continue
            archetype = contract.get("archetype", "")
            if archetype not in archetypes:
                err("PK040", MANIFEST_NAME,
                    f"domain {d!r}: unknown archetype {archetype!r} "
                    f"(known: {', '.join(sorted(archetypes))})")
            for pid in contract.get("produces", []) or []:
                if not isinstance(pid, str) or not _KEBAB_RE.match(pid):
                    err("PK041", MANIFEST_NAME,
                        f"domain {d!r}: produces id {pid!r} must be kebab-case")
        spec = domain.get("specialist")
        if isinstance(spec, dict):
            for phase in spec.get("enhances", []) or []:
                if phase not in _KNOWN_PHASES:
                    warn("PK042", MANIFEST_NAME,
                         f"domain {d!r}: enhances phase {phase!r} is not a known "
                         f"crew phase ({', '.join(sorted(_KNOWN_PHASES))})")

    # ---- peer floors -------------------------------------------------------
    peers = manifest.get("peers", {})
    if isinstance(peers, dict):
        for peer, range_str in sorted(peers.items()):
            if not _FLOOR_RE.match(str(range_str).strip()):
                err("PK050", MANIFEST_NAME,
                    f"peer {peer!r} floor {range_str!r} malformed "
                    "(expected \">=X.Y.Z\" or \"^X.Y.Z\")")

    return findings


def main(argv: "list | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pack check", description="wicked-garden pack conformance gate")
    parser.add_argument("pack_root", help="pack directory (contains wicked-pack.json)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--garden-root", default=None,
                        help="garden plugin root for cross-catalog checks (optional)")
    args = parser.parse_args(argv)

    pack_root = Path(args.pack_root)
    if not pack_root.is_dir():
        print(f"ERROR: not a directory: {pack_root}", file=sys.stderr)
        return 2

    findings = check_pack(pack_root,
                          garden_root=Path(args.garden_root) if args.garden_root else None)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warn"]

    if args.json:
        print(json.dumps({
            "pack_root": str(pack_root.resolve()),
            "ok": not errors,
            "errors": [f.as_dict() for f in errors],
            "warnings": [f.as_dict() for f in warnings],
        }, indent=2))
    else:
        for f in findings:
            print(f.render())
        verdict = "PASS" if not errors else "FAIL"
        print(f"\npack check: {verdict} ({len(errors)} errors, {len(warnings)} warnings)")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
