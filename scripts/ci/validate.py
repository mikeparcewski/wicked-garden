#!/usr/bin/env python3
"""
Standalone structural validation for wicked-garden plugin.

Runs with stdlib only — no third-party dependencies.
Suitable for CI (GitHub Actions) without needing Claude Code.

Checks (skills-only layout: former commands/ + agents/ are now skills/):
  1. plugin.json is valid JSON with required fields
  2. All SKILL.md files are <= 200 lines
  3. All script paths in hooks.json exist
  4. All worker skills (metadata.role: worker) have required frontmatter fields
  5. No stale presentation/prezzie references in skills/
  6. Self-referential integrity: script paths referenced in skills/ resolve
  7. specialist.json roles match ROLE_CATEGORIES in specialist_discovery.py
"""

import json
import os
import re
import sys
from pathlib import Path

# scripts/ is not always on sys.path (hooks import by path; CI runs from a subdir).
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1])
if _SCRIPTS_DIR not in sys.path:
    sys.path.append(_SCRIPTS_DIR)
from _skill_meta import skill_role, skill_role_of  # noqa: E402


def _frontmatter_structure_error(block: str) -> str | None:
    """Stdlib structural fallback for the rare case PyYAML is not importable (CI installs it; this keeps the
    guard working if run bare). Catches the frontmatter-drop class: an orphaned value under a SCALAR key,
    and a bare-token list item absorbed into a ``|``/``>`` block scalar. Not a full YAML parser."""
    kind = None
    key = None
    for raw in block.split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][\w-]*):(.*)$", raw)
        if top:
            key = top.group(1); val = top.group(2).strip()
            kind = "literal" if val in ("|", ">", "|-", ">-", "|+", ">+") else ("nested" if val == "" else "scalar")
            continue
        if raw[:1] in (" ", "\t"):
            if kind == "scalar" and re.match(r"^\s+(?:-\s|[\w-]+:)", raw):
                return (f"orphaned value under scalar key {key!r} ({raw.strip()!r}) — a dropped key must "
                        "take its value lines with it (frontmatter-drop class)")
            if kind == "literal" and re.match(r"^\s+-\s+[\w-]+\s*$", raw):
                return (f"orphaned list value {raw.strip()!r} absorbed into the {key!r} block scalar — a "
                        "dropped key must take its value lines with it (frontmatter-drop class)")
    return None


def ci_yaml_requirement_error(yaml_available: bool, env) -> str | None:
    """N1 durability guard: in a CI context the frontmatter guard MUST run the real ``yaml.safe_load``
    (the publish's parser), never the weaker stdlib fallback — so a future edit that drops
    ``pip install pyyaml`` from a workflow can never silently re-weaken the guard. Locally (no CI env) the
    graceful stdlib fallback stays. Returns an error string when PyYAML is missing in CI, else ``None``."""
    if not yaml_available and (env.get("CI") or env.get("GITHUB_ACTIONS")):
        return ("PyYAML is not importable in a CI context — the SKILL.md frontmatter guard requires the real "
                "yaml.safe_load (the skills-publish parser), not the stdlib fallback; add `pip install pyyaml` "
                "to the workflow (validate.yml / test.yml / release.yml)")
    return None


def frontmatter_yaml_error(text: str) -> str | None:
    """Strict frontmatter guard — the EXACT mirror of the skills publish's parser. Runs ``yaml.safe_load``
    on the ``---`` block (PyYAML is installed on the ``validate`` / ``test`` / release pre-publish CI legs,
    as ``test.yml`` installs pytest), so anything the publish would reject is rejected here — including the
    frontmatter-drop class under a NESTED ``metadata:`` / ``mandates:`` key (the exact block every wave-2
    skill carries). Also flags the SILENT subclass a plain parse accepts: a bare-token list value absorbed
    into a ``|`` / ``>`` block scalar. Falls back to a stdlib structural check only if PyYAML is unimportable.
    Returns an error string on a defect, else ``None``."""
    if not text.startswith("---"):
        return "missing YAML frontmatter"
    m = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    if not m:
        return "malformed YAML frontmatter"
    block = m.group(1)
    data = None
    try:
        import yaml  # installed on the CI legs that run this guard (see validate.yml / test.yml / release.yml)
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError as e:
            first = str(e).splitlines()[0]
            return (f"frontmatter is not valid YAML ({first}) — a dropped key must take its value lines "
                    "with it (frontmatter-drop class)")
        if data is not None and not isinstance(data, dict):
            return f"frontmatter is not a mapping (parsed as {type(data).__name__})"
    else:
        err = _frontmatter_structure_error(block)
        if err:
            return err
    # SILENT subclass: valid YAML, corrupt content — a bare-token list value absorbed into a block scalar.
    desc = data.get("description") if isinstance(data, dict) else None
    if isinstance(desc, str):
        for ln in desc.splitlines():
            if re.match(r"^\s*-\s+[\w-]+\s*$", ln):
                return (f"frontmatter description absorbed an orphaned list value ({ln.strip()!r}) — a "
                        "dropped key must take its value lines with it (frontmatter-drop class)")
    return None


# --- Core-closure guard: the skills-publish "core-by-reference closure" (wicked-crew
#     packages/crew/src/skills/core-closure.ts) ---
# The skills publish computes a REGISTERED-REFERENCE CLOSURE: from every workflow phase's `skill_ref`
# it follows each skill's mandates — the frontmatter `mandates:` list AND the SKILL.md BODY's
# qualified-name mentions (`wicked-garden-<x>` / `wicked-garden:<x>`) — and REFUSES the whole publish
# when a reference names no catalog skill (`core-missing`, blocking, fail-closed). Crucially the body
# scan does NOT honor the `<!-- not-a-skill -->` HTML-comment shield that garden's own
# tests/test_skill_portability.py `unresolved-skill-name` check honors: to the publish, a shielded
# prose mention of a DELETED skill is still a dangling ref. That divergence shipped the garden 12.38.0
# blocker — skills/governed-worker/SKILL.md named three skills batch B18 (#1169) deleted; the shield
# satisfied garden's own linters, but the daemon's core-closure refused the publish (crew 0.7.38 smoke
# S02, both legs; it passed on 12.37.2, which still had the stub skills). This guard mirrors the
# publish's rule so garden CI catches the class BEFORE publish.
#
# Scope: garden cannot know which skills the workflow registry (in wicked-core / wicked-crew) makes
# core-reachable, and a dangling ref becomes a live publish-blocker the moment its skill enters the
# closure, so this guard scans EVERY catalog skill (a superset of the publish's reachable-only check)
# — the safe, self-contained garden-side mirror.

_PLUGIN_NAME = "wicked-garden"
_SKILL_NAME_PREFIX = _PLUGIN_NAME + "-"
# crew core-closure.ts NAME_TOKEN_RE: `wicked-garden-<x>` / `wicked-garden:<x>` not glued to a preceding
# name character; a trailing `-`/`_` is a glob/prefix (not a name); a `:`-continued token is a Claude
# subagent type (not a skill). Ported verbatim; the `<!-- not-a-skill -->` shield is NOT honored.
_NAME_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])" + re.escape(_PLUGIN_NAME) + r"[:-]([A-Za-z0-9_-]+)(:?)"
)


def _body_with_frontmatter_blanked(text: str) -> str:
    """``text`` with its ``---``-fenced frontmatter replaced by blank chars (newlines preserved, so a
    prose line number is the file line number). Mirror of crew frontmatter.ts::bodyWithFrontmatterBlanked
    — a frontmatter scalar is the parser's business, not a prose mention."""
    src = text.replace("\r\n", "\n")
    if not src.startswith("---\n"):
        return src
    m = re.match(r"^---\n.*?\n---", src, re.DOTALL)
    if not m:
        return src
    end = m.end()
    return re.sub(r"[^\n]", "", src[:end]) + src[end:]


def _prose_mentions(body: str) -> list[tuple[str, int]]:
    """Every well-formed qualified-name token in ``body`` with its 1-based line. Glob/prefix tokens
    (trailing ``-``/``_``) and ``:``-continued subagent types are not names. Mirror of
    crew core-closure.ts::mentionedTokens. Callers hand this the frontmatter-blanked body."""
    out: list[tuple[str, int]] = []
    for i, line in enumerate(body.split("\n"), start=1):
        for m in _NAME_TOKEN_RE.finditer(line):
            raw = m.group(1) or ""
            if m.group(2) == ":" or raw.endswith("-") or raw.endswith("_"):
                continue
            out.append((_SKILL_NAME_PREFIX + raw, i))
    return out


def _declared_mandate_names(text: str) -> list[tuple[str, int]]:
    """The frontmatter ``mandates:`` entries as (normalized catalog name, 1-based line). The Claude
    plugin form ``wicked-garden:x`` normalizes to ``wicked-garden-x``. Mirror of the declared half of
    crew core-closure.ts::mandateMentions (frontmatter.ts::declaredMandates). Best-effort without YAML."""
    m = re.match(r"^---\n(.*?\n)---", text.replace("\r\n", "\n"), re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    try:
        import yaml
        data = yaml.safe_load(block)
    except Exception:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("mandates"), list):
        return []
    block_lines = block.split("\n")
    out: list[tuple[str, int]] = []
    for entry in data["mandates"]:
        if not isinstance(entry, str) or entry == "":
            continue
        name = (
            _SKILL_NAME_PREFIX + entry[len(_PLUGIN_NAME) + 1:]
            if entry.startswith(_PLUGIN_NAME + ":")
            else entry
        )
        ln = 2
        for j, bl in enumerate(block_lines):
            if bl.strip() in (f"- {entry}", f'- "{entry}"', f"- '{entry}'"):
                ln = 2 + j
                break
        out.append((name, ln))
    return out


def catalog_skill_names(skills_root: Path) -> set[str]:
    """Every catalog skill name — ``wicked-garden-<dir path under skills/ joined by '-'>`` for each
    ``skills/**/SKILL.md``. Matches wicked-core's derived_name and crew's one-name-per-skill manifest."""
    names: set[str] = set()
    for skill_md in Path(skills_root).glob("**/SKILL.md"):
        rel = skill_md.parent.relative_to(skills_root).as_posix()
        names.add(_SKILL_NAME_PREFIX + rel.replace("/", "-"))
    return names


def dangling_skill_refs(skill_md_text: str, self_name: str, catalog: set[str]) -> list[tuple[str, int]]:
    """The qualified skill references in one SKILL.md (declared ``mandates:`` + BODY prose mentions) that
    name NO catalog skill — the publish's ``absentMandates``. Self-references are excluded. The
    ``<!-- not-a-skill -->`` shield is NOT honored: the publish does not honor it, so neither does this
    guard (that shield hiding a deleted-skill mention IS the class the guard exists to catch)."""
    mentions = _declared_mandate_names(skill_md_text) + _prose_mentions(
        _body_with_frontmatter_blanked(skill_md_text)
    )
    out: list[tuple[str, int]] = []
    for name, line in mentions:
        if name != self_name and name not in catalog:
            out.append((name, line))
    return out


def main():
    root = Path(__file__).resolve().parent.parent.parent
    os.chdir(root)

    errors = []
    warnings = []

    # N1: in CI, refuse to run the frontmatter guard on the weaker stdlib fallback (PyYAML must be installed).
    try:
        import yaml as _yaml_probe  # noqa: F401
        _yaml_ok = True
    except ImportError:
        _yaml_ok = False
    _ci_err = ci_yaml_requirement_error(_yaml_ok, os.environ)
    if _ci_err:
        errors.append(_ci_err)

    # --- 1. plugin.json validity ---
    plugin_json = root / ".claude-plugin" / "plugin.json"
    plugin_version = None
    if not plugin_json.exists():
        errors.append("Missing .claude-plugin/plugin.json")
    else:
        try:
            plugin = json.loads(plugin_json.read_text())
            for field in ("name", "version", "description"):
                if field not in plugin:
                    errors.append(f"plugin.json missing required field: {field}")
            plugin_version = plugin.get("version", "")
            # Allow semver core X.Y.Z plus optional pre-release (-alpha.N, -beta.N, -rc.N)
            # per semver.org; v6 ships as 6.0.0-beta.1.
            if not re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$", plugin_version):
                errors.append(f"plugin.json version is not semver: {plugin_version}")
        except json.JSONDecodeError as e:
            errors.append(f"plugin.json is invalid JSON: {e}")

    # --- 1b. marketplace.json must agree with plugin.json on plugin version ---
    # Drift caught at v11.1.1: plugins[0].version was stuck at 8.8.1 across
    # 3 v11 releases because nobody bumped it. The marketplace registration
    # is the public-facing version; the plugin manifest is the runtime-
    # facing version; if they diverge, marketplace consumers see a stale
    # number.
    marketplace_json = root / ".claude-plugin" / "marketplace.json"
    if marketplace_json.exists() and plugin_version:
        try:
            mkt = json.loads(marketplace_json.read_text())
            for entry in mkt.get("plugins") or []:
                if entry.get("name") == plugin.get("name"):
                    mkt_version = entry.get("version")
                    if mkt_version != plugin_version:
                        errors.append(
                            f"marketplace.json plugins[name={entry['name']}].version "
                            f"= {mkt_version!r} does not match plugin.json version "
                            f"= {plugin_version!r}. Bump both together."
                        )
                    break
        except json.JSONDecodeError as e:
            errors.append(f"marketplace.json is invalid JSON: {e}")

    # --- 2. SKILL.md line counts ---
    # The cap targets ROUTER / MODULE skills that load into the parent context
    # (parent-context bloat is the problem it guards). WORKER skills load into
    # an isolated, short-lived context and the FLOOR skill
    # (wicked-garden-governed-worker) is handed whole to every governed unit —
    # both are exempt, exactly as agents/ files were pre-cutover. Role comes
    # from scripts/_skill_meta.skill_role (metadata.role first; the legacy
    # context: fork / user-invocable keys are inferred). Cap 200 → 500 with the
    # cross-CLI format — the `skill-too-large` lint token carries the same bound.
    for skill_md in sorted(root.glob("skills/**/SKILL.md")):
        text = skill_md.read_text()
        rel = skill_md.relative_to(root)
        if skill_role_of(skill_md) in ("worker", "floor"):
            continue  # worker / floor skill — no parent-context cap
        lines = len(text.splitlines())
        if lines > 500:
            errors.append(f"{rel} is {lines} lines (max 500)")

    # --- 3. hooks.json script paths ---
    hooks_json = root / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            hooks_data = json.loads(hooks_json.read_text())
            hook_events = hooks_data.get("hooks", {})
            for event_name, matchers in hook_events.items():
                for matcher_block in matchers:
                    for hook in matcher_block.get("hooks", []):
                        cmd = hook.get("command", "")
                        # Extract script paths from the command string
                        # Pattern: ${CLAUDE_PLUGIN_ROOT}/path/to/script.py
                        paths = re.findall(
                            r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"]+\.py)',
                            cmd,
                        )
                        for p in paths:
                            if not (root / p).exists():
                                errors.append(
                                    f"hooks.json [{event_name}]: "
                                    f"script not found: {p}"
                                )
        except json.JSONDecodeError as e:
            errors.append(f"hooks.json is invalid JSON: {e}")

    # --- 4. Worker-skill frontmatter ---
    # Skills-only: the former agents/ are now worker skills (metadata.role:
    # worker; legacy context: fork inferred). Every worker skill must carry
    # frontmatter with a description.
    for skill_md in sorted(root.glob("skills/**/SKILL.md")):
        text = skill_md.read_text()
        rel = skill_md.relative_to(root)
        # Strict YAML frontmatter guard (runs for EVERY SKILL.md, not just workers): the durable fix for
        # the frontmatter-drop class that shipped a broken 12.37.1 (data-engineer left an orphaned
        # `  - data-query` after its key was dropped) — the skills publish `yaml.safe_load`s this block and
        # refuses the whole publish on a parse error.
        yaml_err = frontmatter_yaml_error(text)
        if yaml_err is not None:
            errors.append(f"{rel}: {yaml_err}")
            continue
        # Extract frontmatter block (parse already succeeded above)
        fm_match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
        fm = fm_match.group(1)
        # Only worker skills are validated here — they are the former agents/
        # definitions and must declare a description.
        if skill_role(fm) != "worker":
            continue
        if "description:" not in fm:
            errors.append(f"{rel}: missing 'description' in frontmatter")

    # --- 4b. Core-closure: no dangling skill references (skills-publish blocker class) ---
    # Mirror the skills publish's core-by-reference closure (see the module comment above): a SKILL.md
    # that mandates or names a skill absent from the catalog makes the daemon refuse the whole publish,
    # even when a `<!-- not-a-skill -->` shield satisfies garden's own linters. Scanned over EVERY
    # catalog skill so garden CI fails here first (garden 12.38.0 / crew 0.7.38 smoke S02 regression).
    skills_root = root / "skills"
    catalog = catalog_skill_names(skills_root)
    for skill_md in sorted(skills_root.glob("**/SKILL.md")):
        rel = skill_md.relative_to(root)
        dir_rel = skill_md.parent.relative_to(skills_root).as_posix()
        self_name = _SKILL_NAME_PREFIX + dir_rel.replace("/", "-")
        for name, line in dangling_skill_refs(
            skill_md.read_text(encoding="utf-8"), self_name, catalog
        ):
            errors.append(
                f"{rel}:{line}: references skill `{name}`, which is not in the catalog — the skills "
                f"publish's core-by-reference closure refuses this (a `<!-- not-a-skill -->` shield does "
                f"NOT exempt it); remove the reference or fix the name"
            )

    # --- 5. No stale prezzie/presentation references ---
    stale_pattern = re.compile(
        r"\bprezzie\b|\bpresentation[-_]?plugin\b",
        re.IGNORECASE,
    )
    for md_file in sorted(root.glob("skills/**/*.md")):
        text = md_file.read_text()
        rel = md_file.relative_to(root)
        matches = stale_pattern.findall(text)
        if matches:
            warnings.append(
                f"{rel}: contains stale reference(s): {', '.join(set(matches))}"
            )

    # --- 6. Self-referential integrity: explicit script paths in skills/ ---
    # Skills-only note: this check formerly ran over the thin, curated
    # commands/ + agents/ surface, where three reference shapes (explicit
    # ${CLAUDE_PLUGIN_ROOT} paths, bare scripts/ paths, and `from … import`)
    # were all reliable signals. Skill bodies are different: their refs/
    # (tier-3) docs and examples legitimately contain PLACEHOLDER paths
    # (e.g. `scripts/some/script.py`) and illustrative code-fence imports
    # (rapidfuzz, pydantic, …) that are not real references. Applying the
    # bare-path / import heuristics to the skills tree produces false
    # positives, so we keep only the reliable shape-1 check (explicit
    # ${CLAUDE_PLUGIN_ROOT}/<path>.py|.sh) and surface hits as WARNINGS
    # (advisory) rather than hard errors — a genuinely broken skill-body
    # path is a content fix owned by the skill's author, not a reason to
    # fail the structural gate.
    # Since 12.33 (cross-CLI skills, F-079) skill text reaches plugin files only
    # through the launcher — `wicked-garden run|python|path <root-relative>` — so
    # that shape is checked too; the plugin-root shape is kept for any regression
    # (the hard gate for it is tests/test_skill_portability.py).
    script_ref_pattern = re.compile(
        r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s"]+\.(?:py|sh))'
    )
    launcher_ref_pattern = re.compile(
        r'(?<![A-Za-z0-9_-])(?:npx\s+)?wicked-garden(?:@[A-Za-z0-9_.^~-]+)?\s+'
        r'(?:run|python|path)\s+([A-Za-z0-9_][A-Za-z0-9_./{}-]*)'
    )
    for md_file in sorted(root.glob("skills/**/*.md")):
        text = md_file.read_text()
        rel = md_file.relative_to(root)
        for ref in script_ref_pattern.findall(text):
            if re.search(r"\{[^}]+\}", ref):
                continue
            if not (root / ref).exists():
                warnings.append(f"{rel}: broken script path: {ref}")
        for ref in launcher_ref_pattern.findall(text):
            if re.search(r"\{[^}]+\}", ref) or ref.startswith("-"):
                continue
            if not (root / ref).exists():
                warnings.append(f"{rel}: broken launcher path: {ref}")

    # --- 7. specialist.json roles vs ROLE_CATEGORIES ---
    specialist_json = root / ".claude-plugin" / "specialist.json"
    discovery_py = root / "scripts" / "crew" / "specialist_discovery.py"
    if specialist_json.exists() and discovery_py.exists():
        try:
            spec_data = json.loads(specialist_json.read_text())
            specialists = spec_data.get("specialists", [])

            # Extract ROLE_CATEGORIES keys from specialist_discovery.py
            disc_text = discovery_py.read_text()
            cat_match = re.search(
                r"ROLE_CATEGORIES\s*=\s*\{([^}]+)\}",
                disc_text,
                re.DOTALL,
            )
            if cat_match:
                # Parse the dict keys (quoted strings before colons)
                role_keys = set(
                    re.findall(r'"([^"]+)"\s*:', cat_match.group(1))
                )
                for spec in specialists:
                    role = spec.get("role", "")
                    if role and role not in role_keys:
                        errors.append(
                            f"specialist.json: role '{role}' for "
                            f"specialist '{spec.get('name', '?')}' "
                            f"not in ROLE_CATEGORIES "
                            f"({', '.join(sorted(role_keys))})"
                        )
            else:
                warnings.append(
                    "Could not parse ROLE_CATEGORIES from "
                    "specialist_discovery.py"
                )
        except json.JSONDecodeError as e:
            errors.append(f"specialist.json is invalid JSON: {e}")

    # --- 8. All JSON files valid ---
    for json_file in sorted(root.glob("**/*.json")):
        # Skip node_modules, .git, __pycache__
        rel = json_file.relative_to(root)
        parts = rel.parts
        if any(
            p in (".git", "node_modules", "__pycache__", ".venv")
            for p in parts
        ):
            continue
        try:
            json.loads(json_file.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: invalid JSON: {e}")

    # --- Report ---
    print("=" * 60)
    print("wicked-garden structural validation")
    print("=" * 60)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ERROR: {e}")
        print(f"\nRESULT: FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    else:
        print(f"\nRESULT: PASS (0 errors, {len(warnings)} warnings)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
