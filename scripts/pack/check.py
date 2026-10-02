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
  PK015  router skill must not be a worker (metadata.role: worker / legacy context: fork)
  PK016  worker skill "{vendor}-{domain}-{role}" must declare metadata.role: worker
         (a role-less worker-shaped skill FAILS — never a silent drop; the legacy
         context: fork is inferred during the cross-CLI transition)
  PK017  skill directory name must match frontmatter name
  PK018  skill does not belong to any declared domain
  PK020  router/module SKILL.md exceeds 200 lines (tier-2 disclosure cap; worker + floor exempt)
  PK021  frontmatter description exceeds ~120 words (tier-1 cap) [warn]
  PK022  refs/ file exceeds 350 lines (tier-3 band is 200-300) [warn]
  PK030  NOT-THIS-WHEN reciprocity: same-pack twin does not point back
  PK031  NOT-THIS-WHEN target skill not found [warn]
  PK040  produces contract names an unknown archetype
  PK041  produces id not kebab-case
  PK042  specialist "enhances" phase not a known crew phase [warn]
  PK050  peer floor range malformed (expected ">=X.Y.Z" or "^X.Y.Z")

  Manifest spec 2 (DES-artifact-editor-plugins §5.2):
  PK060  editor entry malformed (a missing or ill-typed field, an unknown field, a duplicate id)
  PK061  editor id uses the reserved "wicked" prefix (refused in every pack)
  PK062  editor entry is not one .html file inside the pack
  PK063  editor entry over its limits.bundleBytes or the host cap, or a limit above the host's
  PK064  editor entry sha256 does not match the file
  PK065  editor entry loads a script, stylesheet or frame from outside itself
  PK066  editor kinds value is not an artifact kind (^[a-z][a-z0-9-]{1,40}$)
  PK067  editor sizes must include "inline" (and only inline | pane | full)
  PK068  editor permission unknown, or without its "why"
  PK070  block malformed (id, label, preset file, produces_kind)
  PK071  block names a skill that is not in this pack
  PK072  block id uses the reserved "wicked" prefix

stdlib-only. Imports the manifest loader from scripts/_pack_registry.py
(same package layout in the repo, the npm tarball, and the installed
plugin), so validation and discovery can never drift apart.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# scripts/ on sys.path so _pack_registry resolves in-repo, in the npm
# tarball, and in the installed plugin (all share the scripts/ layout).
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _skill_meta import skill_role, split_frontmatter  # noqa: E402
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

# ---- manifest spec 2: editors + blocks (DES-artifact-editor-plugins §5.1, §5.2, §6.1, §8.5) ----
_KIND_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EDITOR_SIZES = ("inline", "pane", "full")
_EDITOR_PANELS = ("checks",)
# §6.1: what a plugin can ask for. Anything else (network calls, agents, gates, other artifacts) has no permission.
EDITOR_PERMISSIONS = (
    "artifact.read", "artifact.write", "selection.chip", "composer.draft", "checks.read",
    "checks.contribute", "sources.read", "media.read", "artifact.export", "ui.fullscreen", "network.media",
)
_EDITOR_FIELDS = {"id", "title", "version", "protocol", "kinds", "entry", "sha256", "sizes", "panels",
                  "permissions", "limits"}
_EDITOR_REQUIRED = ("id", "title", "version", "protocol", "kinds", "entry", "sha256", "sizes", "permissions")
_BLOCK_FIELDS = {"id", "label", "preset", "produces_kind", "skills"}
HOST_BUNDLE_CAP = 5 * 1024 * 1024  # the host's cap on an editor entry (§8.5); a pack's limit may only be lower


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
    Frontmatter without a CLOSING fence is malformed and yields ``({}, 0)``
    so the caller reports PK011 instead of trusting a half-open block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return {}, 0
    fm: dict = {}
    desc_lines: list = []
    in_desc = False
    closed = False
    end = 0
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_FENCE:
            closed = True
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
    if not closed:
        return {}, 0
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


def _is_reserved(name: str) -> bool:
    return name == "wicked" or name.startswith("wicked-")


def _inside(pack_root: Path, rel: object) -> "Path | None":
    """The resolved file a manifest path names, or None when it could leave the pack (`..`, absolute, a symlink out)."""
    if not isinstance(rel, str) or not rel:
        return None
    normalized = rel.replace("\\", "/")
    if ".." in normalized.split("/") or normalized.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return None
    target = (pack_root / rel).resolve()
    try:
        target.relative_to(pack_root)
    except ValueError:
        return None
    return target


class _ExternalRefs(HTMLParser):
    """Collects the tags that would load something from outside the entry file itself."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("src", "").strip():
            self.found.append(f'<script src="{a["src"]}">')
        elif tag == "iframe" and a.get("src", "").strip() not in ("", "about:blank"):
            self.found.append(f'<iframe src="{a["src"]}">')
        elif tag == "link" and "stylesheet" in a.get("rel", "").lower().split() and a.get("href", "").strip():
            self.found.append(f'<link rel="stylesheet" href="{a["href"]}">')


def _check_editors(manifest: dict, pack_root: Path, err) -> None:
    editors = manifest.get("editors")
    if editors is None:
        return
    if not isinstance(editors, list) or not editors:
        err("PK060", MANIFEST_NAME, "editors must be a non-empty array of editor objects")
        return
    seen: set = set()
    for i, ed in enumerate(editors):
        where = f"{MANIFEST_NAME} editors[{i}]"
        if not isinstance(ed, dict):
            err("PK060", where, "an editor must be an object")
            continue
        eid = ed.get("id")
        if isinstance(eid, str):
            where = f"{MANIFEST_NAME} editor {eid!r}"
        for key in sorted(set(ed) - _EDITOR_FIELDS):
            err("PK060", where, f"unknown field {key!r} (spec 2 editor fields: {', '.join(sorted(_EDITOR_FIELDS))})")
        for key in _EDITOR_REQUIRED:
            if key not in ed:
                err("PK060", where, f"missing required field {key!r}")
        if "id" in ed:
            if not isinstance(eid, str) or not _KEBAB_RE.match(eid) or len(eid) > _MAX_NAME_LEN:
                err("PK060", where, f"id must be kebab-case, <= {_MAX_NAME_LEN} chars (got {eid!r})")
            elif _is_reserved(eid):
                err("PK061", where, f"editor id {eid!r} uses the reserved prefix 'wicked': first-party editors "
                    "ship inside studio, never in a pack")
            elif eid in seen:
                err("PK060", where, f"duplicate editor id {eid!r}")
            if isinstance(eid, str):
                seen.add(eid)
        if "title" in ed and (not isinstance(ed["title"], str) or not ed["title"].strip()):
            err("PK060", where, "title must be plain words shown in Settings → Editors (got an empty value)")
        if "version" in ed and (not isinstance(ed["version"], str) or not re.match(r"^\d+\.\d+\.\d+", ed["version"])):
            err("PK060", where, f"version must be the editor's semver (got {ed['version']!r})")
        protocol = ed.get("protocol")
        if "protocol" in ed and (not isinstance(protocol, list) or not protocol
                                 or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in protocol)):
            err("PK060", where, f"protocol must list the wicked.editor protocol versions it speaks, e.g. [1] (got {protocol!r})")
        panels = ed.get("panels", [])
        if not isinstance(panels, list) or any(p not in _EDITOR_PANELS for p in panels):
            err("PK060", where, f"panels may only name host-fed panels {list(_EDITOR_PANELS)} (got {panels!r})")
        sha = ed.get("sha256")
        sha_ok = isinstance(sha, str) and bool(_SHA256_RE.match(sha))
        if "sha256" in ed and not sha_ok:
            err("PK060", where, "sha256 must be the 64-hex lowercase sha256 of the entry file")

        kinds = ed.get("kinds")
        if "kinds" in ed:
            if not isinstance(kinds, list) or not kinds:
                err("PK066", where, "kinds must list at least one artifact kind it can open")
            else:
                for k in kinds:
                    if not isinstance(k, str) or not _KIND_RE.match(k):
                        err("PK066", where, f"kind {k!r} is not an artifact kind (^[a-z][a-z0-9-]{{1,40}}$)")

        sizes = ed.get("sizes")
        if "sizes" in ed:
            if not isinstance(sizes, list):
                err("PK067", where, 'sizes must be a list that must include "inline"')
            else:
                for size in sizes:
                    if size not in _EDITOR_SIZES:
                        err("PK067", where, f"unknown size {size!r} (sizes: {', '.join(_EDITOR_SIZES)})")
                if "inline" not in sizes:
                    err("PK067", where, 'sizes must include "inline" (a missing "pane" morphs inline to full)')

        perms = ed.get("permissions")
        if "permissions" in ed:
            if not isinstance(perms, list):
                err("PK068", where, "permissions must be a list of {id, why}")
            else:
                for perm in perms:
                    pid = perm.get("id") if isinstance(perm, dict) else perm
                    if pid not in EDITOR_PERMISSIONS:
                        err("PK068", where, f"unknown permission {pid!r} (known: {', '.join(EDITOR_PERMISSIONS)})")
                    why = perm.get("why") if isinstance(perm, dict) else None
                    if not isinstance(why, str) or not why.strip():
                        err("PK068", where, f'permission {pid!r} needs a "why": the reason shown at install')

        limit = HOST_BUNDLE_CAP
        limits = ed.get("limits")
        if limits is not None:
            bb = limits.get("bundleBytes") if isinstance(limits, dict) else None
            if not isinstance(limits, dict) or set(limits) - {"bundleBytes"} or (
                    "bundleBytes" in limits and (not isinstance(bb, int) or isinstance(bb, bool) or bb < 1)):
                err("PK060", where, f"limits may only set a positive bundleBytes (got {limits!r})")
            elif isinstance(bb, int):
                if bb > HOST_BUNDLE_CAP:
                    err("PK063", where, f"limits.bundleBytes {bb} is above the host cap {HOST_BUNDLE_CAP}: a limit "
                        "may only be lower than the host's")
                limit = min(bb, HOST_BUNDLE_CAP)

        if "entry" not in ed:
            continue
        entry = ed["entry"]
        path = _inside(pack_root, entry)
        if path is None:
            err("PK062", where, f"entry must be a relative path inside the pack (got {entry!r})")
            continue
        if path.suffix.lower() != ".html":
            err("PK062", where, f"entry must be a single .html file with its scripts inline (got {entry!r})")
            continue
        if not path.is_file():
            err("PK062", where, f"entry not found: {entry!r}")
            continue
        data = path.read_bytes()
        if len(data) > limit:
            which = "limits.bundleBytes" if limit < HOST_BUNDLE_CAP else "the host cap"
            err("PK063", where, f"entry is {len(data)} bytes, over {which} ({limit}; bundleBytes may only lower the host's)")
        if sha_ok and hashlib.sha256(data).hexdigest() != sha:
            err("PK064", where, f"sha256 {sha} does not match the entry file "
                f"({hashlib.sha256(data).hexdigest()}): pin the hash of the file you ship")
        refs = _ExternalRefs()
        try:
            refs.feed(data.decode("utf-8", errors="replace"))
            refs.close()
        except Exception as exc:  # noqa: BLE001 — an unparseable entry is reported, never a crash
            err("PK065", where, f"entry could not be read as HTML ({exc})")
            continue
        for tag in refs.found:
            err("PK065", where, f"entry must be self-contained: {tag} loads from outside the file "
                "(the editor CSP blocks it; inline it instead)")


def _check_blocks(manifest: dict, pack_root: Path, skill_names: set, err) -> None:
    blocks = manifest.get("blocks")
    if blocks is None:
        return
    if not isinstance(blocks, list):
        err("PK070", MANIFEST_NAME, "blocks must be an array of block objects")
        return
    seen: set = set()
    for i, blk in enumerate(blocks):
        where = f"{MANIFEST_NAME} blocks[{i}]"
        if not isinstance(blk, dict):
            err("PK070", where, "a block must be an object")
            continue
        bid = blk.get("id")
        if isinstance(bid, str):
            where = f"{MANIFEST_NAME} block {bid!r}"
        for key in sorted(set(blk) - _BLOCK_FIELDS):
            err("PK070", where, f"unknown field {key!r} (block fields: {', '.join(sorted(_BLOCK_FIELDS))})")
        if not isinstance(bid, str) or not _KEBAB_RE.match(bid) or len(bid) > _MAX_NAME_LEN:
            err("PK070", where, f"id must be kebab-case, <= {_MAX_NAME_LEN} chars (got {bid!r})")
        elif _is_reserved(bid):
            err("PK072", where, f"block id {bid!r} uses the reserved prefix 'wicked': first-party blocks are core "
                "presets, never pack presets")
        elif bid in seen:
            err("PK070", where, f"duplicate block id {bid!r}")
        if isinstance(bid, str):
            seen.add(bid)
        label = blk.get("label")
        if not isinstance(label, str) or not label.strip():
            err("PK070", where, "label must be the plain words the block is offered with (got an empty value)")
        kind = blk.get("produces_kind")
        if not isinstance(kind, str) or not _KIND_RE.match(kind):
            err("PK070", where, f"produces_kind must be an artifact kind (^[a-z][a-z0-9-]{{1,40}}$) (got {kind!r})")
        preset = blk.get("preset")
        path = _inside(pack_root, preset)
        if path is None:
            err("PK070", where, f"preset must be a relative path inside the pack (got {preset!r})")
        elif not path.is_file():
            err("PK070", where, f"preset file not found: {preset!r}")
        else:
            try:
                ok = isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
            except (OSError, ValueError):
                ok = False
            if not ok:
                err("PK070", where, f"preset {preset!r} must be a JSON object (a crew preset)")
        skills = blk.get("skills", [])
        if not isinstance(skills, list):
            err("PK070", where, "skills must be a list of this pack's skill names")
            skills = []
        for name in skills:
            if name not in skill_names:
                err("PK071", where, f"skill {name!r} is not a skill in this pack "
                    "(a block may only name skills the pack ships, so they are approved together)")


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
        # The editor-id reservation is reported once, under its own code, by _check_editors.
        if not e.startswith("editor id "):
            err("PK002", MANIFEST_NAME, e)
    if any(f.code == "PK002" and ("skills dir" in f.message or "skills_dir" in f.message)
           for f in findings):
        return findings  # cannot walk a missing/escaping tree

    # ---- manifest spec 2: editors (no skills needed) ---------------------
    _check_editors(manifest, pack_root, err)

    vendor = str(manifest.get("vendor", ""))
    skills_dir = pack_root / str(manifest.get("skills_dir", "skills"))
    domain_names = [d.get("name", "") for d in manifest.get("domains", []) or []
                    if isinstance(d, dict)]

    # ---- walk the skills tree -------------------------------------------
    skill_files = sorted(skills_dir.rglob("SKILL.md")) if skills_dir.is_dir() else []
    if not skill_files:
        if domain_names or manifest.get("blocks"):
            err("PK010", str(skills_dir), "no SKILL.md files found")
            _check_blocks(manifest, pack_root, set(), err)
        return findings  # an editor-only pack (spec 2) ships no skills

    skills: dict = {}   # name -> {fm, path, text, role}
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
            # ONE reader of role (scripts/_skill_meta): metadata.role first,
            # legacy context: fork / user-invocable inferred.
            "role": skill_role(split_frontmatter(text)[0]),
        }

    # ---- router / worker shape per declared domain ----------------------
    router_names = {f"{vendor}-{d}" for d in domain_names}
    for d in domain_names:
        router = f"{vendor}-{d}"
        if router not in skills:
            err("PK014", MANIFEST_NAME,
                f"domain {d!r} has no router skill {router!r} (one router per domain)")
        elif skills[router]["role"] == "worker":
            err("PK015", skills[router]["path"],
                f"router {router!r} must be a router (metadata.role: router / user-invocable), "
                "not a worker")

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
        if info["role"] != "worker":
            err("PK016", info["path"],
                f"worker {name!r} must declare metadata.role: worker — a worker-shaped name "
                f"with role {info['role']!r} is refused, never silently dropped (the legacy "
                "context: fork is inferred during the cross-CLI transition)")

    # ---- disclosure tiers ------------------------------------------------
    for name, info in skills.items():
        line_count = len(info["text"].splitlines())
        if info["role"] not in ("worker", "floor") and line_count > _MAX_BODY_LINES:
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
    for domain in manifest.get("domains", []) or []:
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

    # ---- manifest spec 2: blocks ------------------------------------------
    _check_blocks(manifest, pack_root, set(skills), err)

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
