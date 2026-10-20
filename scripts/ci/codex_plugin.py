#!/usr/bin/env python3
"""Structural check for garden's Codex plugin manifest (`.codex-plugin/plugin.json`).

Codex (codex-cli >= 0.163) loads garden as a plugin: `codex plugin marketplace add <garden root>`
reads `.claude-plugin/marketplace.json`, and `codex plugin add wicked-garden@wicked-garden` copies
the root into `$CODEX_HOME/plugins/cache/wicked-garden/wicked-garden/<version>/` and reads
`.codex-plugin/plugin.json` (it is preferred over `.claude-plugin/plugin.json`). This module
mirrors the rules Codex applies to that manifest and to the skills under it, so a manifest Codex
would ignore, or a skill it would silently drop, fails garden's CI instead of a user's session:

  * the manifest is a JSON object; `name` is `wicked-garden` and equals the Claude manifest's;
    `version` equals package.json's (lockstep — `.github/scripts/sync-plugin-version.mjs` bumps it);
  * every path field starts with `./`, has no `..`, stays under the root, and exists;
  * `hooks` is the explicit inline opt-out (an empty hooks object): without it Codex would load
    `hooks/hooks.json`, which is Claude Code's event model;
  * `mcpServers` names a file whose `wicked-estate` server is launched through the garden launcher,
    never through an absolute or `~/.cargo` path;
  * the skills Codex discovers from the declared roots (recursive, depth <= 6, hidden directories
    skipped, `SKILL.md` files) are exactly the catalog's `skills/**/SKILL.md`; each has a name of
    at most 64 characters (frontmatter `name`, else the directory name), a non-empty description
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
        out: dict = {}
        for key in ("name", "description"):
            km = re.search(rf"^{key}:\s*(.*)$", block, re.MULTILINE)
            if km:
                out[key] = km.group(1).strip().strip("'\"")
        return out
    except Exception:
        return {}


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
            name = " ".join(str(fm.get("name") or "").split()) or skill_md.parent.name
            description = " ".join(str(fm.get("description") or "").split())
            if len(name) > MAX_NAME_LEN:
                errors.append(f"{rel}: skill name {name!r} is {len(name)} chars (Codex max {MAX_NAME_LEN}) — Codex drops it")
            if not description:
                errors.append(f"{rel}: no description — Codex drops a skill without one")
            qualified = f"{PLUGIN_NAME}:{name}"
            if len(qualified) > MAX_QUALIFIED_NAME_LEN:
                errors.append(f"{rel}: qualified name {qualified!r} exceeds {MAX_QUALIFIED_NAME_LEN} chars")
            if qualified in names:
                errors.append(f"{rel}: duplicate skill name {qualified!r} (also {names[qualified].relative_to(root)})")
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
        if claude.get("name") != manifest.get("name"):
            errors.append(f"{MANIFEST_REL}: name differs from {CLAUDE_MANIFEST_REL} ({claude.get('name')!r})")
    except (OSError, json.JSONDecodeError):
        pass  # validate.py reports the Claude manifest itself
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
                elif not (root / args[1]).is_file():
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` script {args[1]!r} does not exist")
                if "cwd" in server:
                    errors.append(f"{mcp_value}: `{MCP_SERVER}` must not set cwd (estate resolves its store from the session cwd)")
        except json.JSONDecodeError as exc:
            errors.append(f"{mcp_value} is invalid JSON: {exc}")

    # Skills: what Codex discovers == the catalog.
    names, skill_errors = codex_skill_names(root, skills_roots)
    errors.extend(skill_errors)
    discovered = set(names.values())
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
