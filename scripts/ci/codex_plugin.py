#!/usr/bin/env python3
"""Structural check for garden's Codex plugin manifest (`.codex-plugin/plugin.json`).

Codex (codex-cli >= 0.163) loads garden as a plugin: `codex plugin marketplace add <garden root>`
reads `.claude-plugin/marketplace.json`, and `codex plugin add wicked-garden@wicked-garden` copies
the root into `$CODEX_HOME/plugins/cache/wicked-garden/wicked-garden/<version>/` and reads
`.codex-plugin/plugin.json` (it is preferred over `.claude-plugin/plugin.json`). This module
mirrors the rules Codex applies to that manifest and to the skills under it, so a manifest Codex
would ignore, or a skill it would silently drop, fails garden's CI instead of a user's session:

  * the manifest is a JSON object; `name` is `wicked-garden` and equals the Claude manifest's;
    `version` equals package.json's, and so does the Claude manifest's (lockstep —
    `.github/scripts/sync-plugin-version.mjs` bumps all of them);
  * every path field starts with `./`, has no `..`, stays under the root, and exists;
  * `hooks` is the explicit inline opt-out (an empty hooks object): without it Codex would load
    `hooks/hooks.json`, which is Claude Code's event model;
  * `mcpServers` names a file whose `wicked-estate` server is launched through the garden launcher,
    never through an absolute or `~/.cargo` path, and forwards the estate env overrides
    (`env_vars`: Codex passes a stdio server only its default allowlist plus those);
  * the skills Codex discovers from the declared roots (recursive, depth <= 6, hidden directories
    skipped, `SKILL.md` files) are exactly the catalog's `skills/**/SKILL.md`; each has a name of
    at most 64 characters (frontmatter `name`, else the directory name; a list/map name or
    description fails Codex's parse), a non-empty description
    (both whitespace-collapsed first, as Codex does), and a unique qualified name
    `wicked-garden:<name>` of at most 129 characters.

The npm-shipped side of "exactly the shipped skills" (`npm pack --dry-run`) is checked in
tests/test_codex_plugin_manifest.py, which has npm available; this module is stdlib (+ optional
PyYAML) so validate.py can run it anywhere.

Codex sources these rules come from (openai/codex at rust-v0.163.0): codex-rs/core-plugins/src/
manifest.rs (fields, `./` paths), codex-rs/exec-server-protocol/src/protocol.rs
(DISCOVERABLE_PLUGIN_MANIFEST_PATHS), codex-rs/core-plugins/src/loader.rs (default skills dir,
default hooks file), codex-rs/ext/skills/src/loader/{mod.rs,discovery.rs,host.rs} (limits,
traversal, default name), codex-rs/skills/src/parser.rs (whitespace collapse, name length,
required description).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN_NAME = "wicked-garden"
MANIFEST_REL = Path(".codex-plugin") / "plugin.json"
CLAUDE_MANIFEST_REL = Path(".claude-plugin") / "plugin.json"
MCP_SERVER = "wicked-estate"
MAX_SCAN_DEPTH = 6  # codex-rs/exec-server/src/capability_discovery.rs / ext/skills discovery
MAX_NAME_LEN = 64
MAX_QUALIFIED_NAME_LEN = MAX_NAME_LEN * 2 + 1
PATH_FIELDS = ("skills", "mcpServers", "apps", "hooks")
# What the launcher (WICKED_ESTATE_MCP_BIN) and estate itself (store paths) read from the environment.
ESTATE_ENV_VARS = ("WICKED_ESTATE_MCP_BIN", "WICKED_ESTATE_DB", "WICKED_MEMORY_DB", "WICKED_KNOWLEDGE_DB", "WICKED_XEDGE_DB")


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\r?\n(.*?\r?\n)---", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    try:
        import yaml  # validate.yml / test.yml install PyYAML

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except ImportError:
        # Stdlib fallback (CI always has PyYAML — validate.py refuses to run without it there):
        # a `key:` line, its inline value, or the indented lines of a block scalar.
        out: dict = {}
        for key in ("name", "description"):
            km = re.search(rf"^{key}:[ \t]*(.*)$", block, re.MULTILINE)
            if not km:
                continue
            val = km.group(1).strip()
            if val in ("", "|", ">", "|-", ">-", "|+", ">+"):
                lines = []
                for line in block[km.end():].splitlines()[1:]:
                    if line.strip() and not line[:1].isspace():
                        break
                    lines.append(line.strip())
                val = " ".join(x for x in lines if x)
            out[key] = val.strip("'\"")
        return out
    except Exception:
        return {}


def _scalar(value) -> str:
    """A YAML scalar as serde_yaml hands it to a String field (None -> empty)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _inside(root: Path, rel) -> bool:
    """`rel` is a relative path naming an existing file under `root`."""
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or "\\" in rel:
        return False
    target = (root / rel).resolve()
    return root.resolve() in target.parents and target.is_file()


def _manifest_path_error(root: Path, field: str, value) -> str | None:
    if not isinstance(value, str) or not value:
        return f"{MANIFEST_REL}: `{field}` must be a non-empty path string"
    if not value.startswith("./") or value == "./":
        return f"{MANIFEST_REL}: `{field}` = {value!r} must start with `./` relative to the plugin root (Codex ignores it otherwise)"
    if ".." in value[2:].split("/"):
        return f"{MANIFEST_REL}: `{field}` = {value!r} must not contain `..`"
    target = (root / value[2:]).resolve()
    if root.resolve() not in (target, *target.parents):
        return f"{MANIFEST_REL}: `{field}` = {value!r} escapes the plugin root"
    if not target.exists():
        return f"{MANIFEST_REL}: `{field}` = {value!r} does not exist"
    return None


def discover_skill_files(skills_root: Path) -> list[Path]:
    """The SKILL.md files Codex finds under one declared skills root (Recursive mode)."""
    found: list[Path] = []
    if not skills_root.is_dir():
        return found

    def walk(directory: Path, depth: int) -> None:
        for entry in sorted(directory.iterdir()):
            if entry.is_dir() and not entry.is_symlink():
                if entry.name.startswith("."):
                    continue
                if depth < MAX_SCAN_DEPTH:
                    walk(entry, depth + 1)
            elif entry.is_file() and entry.name == "SKILL.md":
                found.append(entry)

    walk(skills_root, 1)
    return found


def codex_skill_names(root: Path, skills_roots: list[Path]) -> tuple[dict[str, Path], list[str]]:
    """Qualified name -> SKILL.md for every skill Codex would load; plus the per-skill errors."""
    names: dict[str, Path] = {}
    errors: list[str] = []
    for skills_root in skills_roots:
        for skill_md in discover_skill_files(skills_root):
            rel = skill_md.relative_to(root)
            fm = _frontmatter(skill_md.read_text(encoding="utf-8"))
            # Codex deserializes name/description as Option<String>: a YAML scalar is accepted,
            # a list or a map makes the whole SKILL.md fail to parse (the skill is dropped).
            bad = [k for k in ("name", "description") if isinstance(fm.get(k), (list, dict))]
            if bad:
                errors.append(f"{rel}: frontmatter {', '.join(bad)} is not a string — Codex drops the skill")
                continue
            name = " ".join(_scalar(fm.get("name")).split()) or skill_md.parent.name
            description = " ".join(_scalar(fm.get("description")).split())
            if len(name) > MAX_NAME_LEN:
                errors.append(f"{rel}: skill name {name!r} is {len(name)} chars (Codex max {MAX_NAME_LEN}) — Codex drops it")
            if not description:
                errors.append(f"{rel}: no description — Codex drops a skill without one")
            qualified = f"{PLUGIN_NAME}:{name}"
            if len(qualified) > MAX_QUALIFIED_NAME_LEN:
                errors.append(f"{rel}: qualified name {qualified!r} exceeds {MAX_QUALIFIED_NAME_LEN} chars")
            if qualified in names:
                errors.append(f"{rel}: duplicate skill name {qualified!r} (also {names[qualified].relative_to(root)})")
                continue
            names[qualified] = skill_md
    return names, errors


def catalog_skill_files(root: Path) -> set[Path]:
    return set((root / "skills").glob("**/SKILL.md"))


def codex_plugin_errors(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    manifest_path = root / MANIFEST_REL
    if not manifest_path.is_file():
        return [f"Missing {MANIFEST_REL} (garden's Codex plugin manifest)"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{MANIFEST_REL} is invalid JSON: {exc}"]
    if not isinstance(manifest, dict):
        return [f"{MANIFEST_REL} must be a JSON object"]

    if manifest.get("name") != PLUGIN_NAME:
        errors.append(f"{MANIFEST_REL}: name = {manifest.get('name')!r}, expected {PLUGIN_NAME!r}")
    try:
        claude = json.loads((root / CLAUDE_MANIFEST_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        claude = None  # validate.py reports the Claude manifest itself
    try:
        pkg_version = json.loads((root / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError) as exc:
        pkg_version = None
        errors.append(f"package.json unreadable: {exc}")
    if pkg_version is not None and manifest.get("version") != pkg_version:
        errors.append(
            f"{MANIFEST_REL}: version = {manifest.get('version')!r} does not match package.json "
            f"{pkg_version!r} — run `node .github/scripts/sync-plugin-version.mjs`"
        )
    if isinstance(claude, dict):
        if claude.get("name") != manifest.get("name"):
            errors.append(f"{MANIFEST_REL}: name differs from {CLAUDE_MANIFEST_REL} ({claude.get('name')!r})")
        # Lockstep is all three anchors: the Claude manifest (and marketplace.json, which
        # validate.py ties to it) must carry package.json's version too.
        if pkg_version is not None and claude.get("version") != pkg_version:
            errors.append(
                f"{CLAUDE_MANIFEST_REL}: version = {claude.get('version')!r} does not match package.json "
                f"{pkg_version!r} — run `node .github/scripts/sync-plugin-version.mjs`"
            )
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        errors.append(f"{MANIFEST_REL}: missing description")

    # Path fields (string or list of strings for skills; strings for the others).
    skills_field = manifest.get("skills")
    skills_values = skills_field if isinstance(skills_field, list) else [skills_field]
    if skills_field is None:
        errors.append(f"{MANIFEST_REL}: `skills` must name the skills directory (./skills)")
        skills_values = []
    skills_roots: list[Path] = []
    for value in skills_values:
        err = _manifest_path_error(root, "skills", value)
        if err:
            errors.append(err)
        else:
            skills_roots.append(root / value[2:])
    for field in ("mcpServers", "apps"):
        value = manifest.get(field)
        if isinstance(value, str):
            err = _manifest_path_error(root, field, value)
            if err:
                errors.append(err)

    hooks = manifest.get("hooks")
    if not (isinstance(hooks, dict) and isinstance(hooks.get("hooks"), dict) and not hooks["hooks"]):
        errors.append(
            f"{MANIFEST_REL}: `hooks` must be the inline opt-out {{\"hooks\": {{}}}} — without it Codex "
            "loads hooks/hooks.json, which is Claude Code's hook model"
        )

    # MCP: the estate server goes through the launcher (same resolution as the Claude plugin's scripts).
    mcp_value = manifest.get("mcpServers")
    if not isinstance(mcp_value, str):
        errors.append(f"{MANIFEST_REL}: `mcpServers` must name the MCP file (./.codex-plugin/mcp.json)")
    elif mcp_value.startswith("./") and (root / mcp_value[2:]).exists() and not (root / mcp_value[2:]).is_file():
        errors.append(f"{MANIFEST_REL}: `mcpServers` = {mcp_value!r} must be a file")
    elif (root / mcp_value[2:]).is_file() and mcp_value.startswith("./"):
        try:
            mcp = json.loads((root / mcp_value[2:]).read_text(encoding="utf-8"))
            servers = mcp.get("mcpServers", mcp) if isinstance(mcp, dict) else {}
            server = servers.get(MCP_SERVER) if isinstance(servers, dict) else None
            if not isinstance(server, dict):
                errors.append(f"{mcp_value}: no `{MCP_SERVER}` server")
            else:
                command = str(server.get("command", ""))
                args = server.get("args", [])
                if "/" in command or "\\" in command or ".cargo" in command:
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` command {command!r} must be a bare name, not an install path")
                if command != "wicked-garden" or not isinstance(args, list) or args[:1] != ["run"] or len(args) < 2:
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` must launch through `wicked-garden run <script>`")
                elif not _inside(root, args[1]):
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` script {args[1]!r} must be a file under the plugin root")
                if "cwd" in server:
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` must not set cwd (estate resolves its store from the session cwd)")
                # Codex hands a stdio MCP server only its default env allowlist plus `env_vars`
                # (codex-rs/rmcp-client/src/utils.rs), so the overrides garden's resolver and
                # estate read must be named or they never arrive.
                forwarded = server.get("env_vars", [])
                missing = [v for v in ESTATE_ENV_VARS if not isinstance(forwarded, list) or v not in forwarded]
                if missing:
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` env_vars must forward {', '.join(missing)} (Codex drops other variables)")
        except json.JSONDecodeError as exc:
            errors.append(f"{mcp_value} is invalid JSON: {exc}")

    # Skills: what Codex discovers == the catalog.
    _, skill_errors = codex_skill_names(root, skills_roots)
    errors.extend(skill_errors)
    discovered = {p for r in skills_roots for p in discover_skill_files(r)}
    catalog = catalog_skill_files(root)
    for missing in sorted(catalog - discovered):
        errors.append(f"{missing.relative_to(root)}: in the catalog but Codex would not discover it from the manifest's skills roots")
    for extra in sorted(discovered - catalog):
        errors.append(f"{extra.relative_to(root)}: Codex would load it but it is not a catalog skill")
    return errors


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    problems = codex_plugin_errors(target)
    for p in problems:
        print(f"ERROR: {p}")
    names, _ = codex_skill_names(target, [target / "skills"])
    print(f"{len(names)} Codex skills; {len(problems)} errors")
    sys.exit(1 if problems else 0)
