"""garden as a Codex plugin: `.codex-plugin/plugin.json`, its MCP file and the estate launcher.

Covered: the shipped manifest passes the Codex-rules check (scripts/ci/codex_plugin.py) and
each rule fails a fixture that breaks it; the npm package ships exactly the skills Codex
discovers plus the manifest files; `sync-plugin-version.mjs` keeps the Codex manifest in
version lockstep; `scripts/estate_mcp.mjs` resolves the binary exactly as
`scripts/_estate_client.py` does and passes stdio, args, cwd and the exit code through.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "ci"))
from codex_plugin import codex_plugin_errors, codex_skill_names  # noqa: E402

NODE = shutil.which("node")
NPM = shutil.which("npm")
LAUNCHER = REPO / "scripts" / "estate_mcp.mjs"
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="shebang fakes")
needs_node = pytest.mark.skipif(NODE is None, reason="node not on PATH")


def test_the_shipped_codex_manifest_passes_the_codex_rules():
    assert codex_plugin_errors(REPO) == []


def test_codex_discovers_every_catalog_skill_under_the_plugin_namespace():
    names, errors = codex_skill_names(REPO, [REPO / "skills"])
    assert errors == []
    catalog = list((REPO / "skills").glob("**/SKILL.md"))
    assert len(names) == len(catalog) > 0
    assert all(n.startswith("wicked-garden:wicked-garden-") for n in names)


# --- fixture tree: one valid plugin, then one broken rule per test -------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "garden"
    _write(root / "package.json", json.dumps({"name": "wicked-garden", "version": "1.2.3"}))
    _write(root / ".claude-plugin" / "plugin.json", json.dumps({"name": "wicked-garden", "version": "1.2.3"}))
    _write(root / ".codex-plugin" / "plugin.json", json.dumps({
        "name": "wicked-garden", "version": "1.2.3", "description": "d",
        "skills": "./skills", "mcpServers": "./.codex-plugin/mcp.json",
        "hooks": {"hooks": {}},
    }))
    _write(root / ".codex-plugin" / "mcp.json", json.dumps({"mcpServers": {"wicked-estate": {
        "command": "wicked-garden", "args": ["run", "scripts/estate_mcp.mjs"],
        "env_vars": ["WICKED_ESTATE_MCP_BIN", "WICKED_ESTATE_DB", "WICKED_MEMORY_DB", "WICKED_KNOWLEDGE_DB", "WICKED_XEDGE_DB"]}}}))
    _write(root / "scripts" / "estate_mcp.mjs", "// stub\n")
    _write(root / "skills" / "alpha" / "SKILL.md", "---\nname: wicked-garden-alpha\ndescription: Alpha.\n---\nbody\n")
    _write(root / "skills" / "alpha" / "beta" / "SKILL.md", "---\nname: wicked-garden-alpha-beta\ndescription: Beta.\n---\n")
    return root


def _edit_manifest(root: Path, **changes) -> None:
    path = root / ".codex-plugin" / "plugin.json"
    data = json.loads(path.read_text())
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    path.write_text(json.dumps(data))


def test_fixture_is_valid(tmp_path):
    assert codex_plugin_errors(_fixture(tmp_path)) == []


def test_version_drift_from_package_json_fails(tmp_path):
    root = _fixture(tmp_path)
    _edit_manifest(root, version="1.2.2")
    assert any("sync-plugin-version" in e for e in codex_plugin_errors(root))


def test_claude_manifest_drift_fails_even_when_codex_matches_package_json(tmp_path):
    root = _fixture(tmp_path)
    # Claude manifest (and marketplace.json with it) moved; package.json + Codex did not.
    _write(root / ".claude-plugin" / "plugin.json", json.dumps({"name": "wicked-garden", "version": "1.2.4"}))
    errors = codex_plugin_errors(root)
    assert any(".claude-plugin/plugin.json: version = '1.2.4'" in e for e in errors), errors


def test_release_py_moves_every_version_anchor(tmp_path):
    root = _fixture(tmp_path)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import release; "
            "release.ReleaseManager(sys.argv[2]).update_other_version_anchors('2.0.0')")
    subprocess.run([sys.executable, "-c", code, str(REPO / ".claude" / "skills" / "releasing" / "scripts"), str(root)],
                   check=True, capture_output=True, timeout=60)
    assert json.loads((root / "package.json").read_text())["version"] == "2.0.0"
    assert json.loads((root / ".codex-plugin" / "plugin.json").read_text())["version"] == "2.0.0"


def test_missing_manifest_fails(tmp_path):
    root = _fixture(tmp_path)
    (root / ".codex-plugin" / "plugin.json").unlink()
    assert codex_plugin_errors(root) == ["Missing .codex-plugin/plugin.json (garden's Codex plugin manifest)"]


@pytest.mark.parametrize("value", ["skills", "./", "./../skills", "./nope"])
def test_skills_path_codex_would_ignore_fails(tmp_path, value):
    root = _fixture(tmp_path)
    _edit_manifest(root, skills=value)
    errors = codex_plugin_errors(root)
    assert any("`skills`" in e for e in errors), errors


@pytest.mark.parametrize("hooks", [None, [], {"hooks": {"Stop": []}}, "./hooks/hooks.json"])
def test_hooks_must_be_the_inline_opt_out(tmp_path, hooks):
    root = _fixture(tmp_path)
    _edit_manifest(root, hooks=hooks)
    assert any("`hooks`" in e for e in codex_plugin_errors(root))


@pytest.mark.parametrize("server", [
    {"command": "~/.cargo/bin/wicked-estate-mcp"},
    {"command": "/usr/local/bin/wicked-estate-mcp"},
    {"command": "wicked-estate-mcp"},
    {"command": "wicked-garden", "args": ["run", "scripts/missing.mjs"]},
    {"command": "wicked-garden", "args": ["run", "scripts/estate_mcp.mjs"], "cwd": "."},
    {"command": "wicked-garden", "args": ["run", "/usr/local/bin/wicked-estate-mcp"]},
    {"command": "wicked-garden", "args": ["run", "../outside.mjs"]},
    {"command": "wicked-garden", "args": ["run", 7]},
])
def test_estate_server_must_go_through_the_launcher(tmp_path, server):
    root = _fixture(tmp_path)
    _write(root / ".codex-plugin" / "mcp.json", json.dumps({"mcpServers": {"wicked-estate": server}}))
    assert any("wicked-estate" in e for e in codex_plugin_errors(root))


def test_estate_env_overrides_must_be_forwarded(tmp_path):
    root = _fixture(tmp_path)
    _write(root / ".codex-plugin" / "mcp.json", json.dumps({"mcpServers": {"wicked-estate": {
        "command": "wicked-garden", "args": ["run", "scripts/estate_mcp.mjs"], "env_vars": ["WICKED_ESTATE_DB"]}}}))
    errors = codex_plugin_errors(root)
    assert any("env_vars must forward WICKED_ESTATE_MCP_BIN" in e for e in errors), errors


# Codex 0.163 (codex-rs/rmcp-client/src/utils.rs DEFAULT_ENV_VARS, unix): what a stdio MCP server
# inherits besides the variables its config names in env_vars.
CODEX_DEFAULT_ENV = ("HOME", "LOGNAME", "PATH", "SHELL", "USER", "__CF_USER_TEXT_ENCODING", "LANG", "LC_ALL", "TERM", "TMPDIR", "TZ")


@needs_node
@posix_only
def test_override_survives_codex_env_filtering(tmp_path):
    """The shipped mcp.json forwards WICKED_ESTATE_MCP_BIN through Codex's env filter to the launcher."""
    bindir = tmp_path / "custom"
    fake = _fake_bin(bindir)
    server = json.loads((REPO / ".codex-plugin" / "mcp.json").read_text())["mcpServers"]["wicked-estate"]
    parent = {**_env(tmp_path, [Path(NODE).parent], override=str(fake)), "UNRELATED": "x"}
    child = {k: v for k, v in parent.items() if k in CODEX_DEFAULT_ENV or k in server["env_vars"]}
    res = subprocess.run([NODE, str(LAUNCHER)], env=child, input="", capture_output=True, text=True, timeout=60)
    assert res.returncode == 7, res.stderr
    assert "UNRELATED" not in child


def test_mcp_servers_must_name_a_file(tmp_path):
    root = _fixture(tmp_path)
    _edit_manifest(root, mcpServers="./.codex-plugin")
    assert any("must be a file" in e for e in codex_plugin_errors(root))


def test_duplicate_reports_once_not_as_undiscovered(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / "gamma" / "SKILL.md", "---\nname: wicked-garden-alpha\ndescription: dup.\n---\n")
    errors = codex_plugin_errors(root)
    assert [e for e in errors if "would not discover" in e] == []


def test_stdlib_frontmatter_fallback_reads_block_scalars(monkeypatch):
    import builtins
    import codex_plugin

    real_import = builtins.__import__

    def no_yaml(name, *a, **k):
        if name == "yaml":
            raise ImportError("no yaml")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_yaml)
    fm = codex_plugin._frontmatter("---\nname: x\ndescription: |\n  two\n  lines\nother: y\n---\n")
    assert fm == {"name": "x", "description": "two lines"}
    assert codex_plugin._frontmatter("---\nname: x\ndescription: |\n   \n---\n")["description"] == ""
    assert codex_plugin._frontmatter("---\ndescription:\nname: x\n---\n")["description"] == ""


def test_missing_estate_server_fails(tmp_path):
    root = _fixture(tmp_path)
    _write(root / ".codex-plugin" / "mcp.json", json.dumps({"mcpServers": {}}))
    assert any("no `wicked-estate` server" in e for e in codex_plugin_errors(root))


def test_skill_codex_would_drop_fails(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / "nodesc" / "SKILL.md", "---\nname: wicked-garden-nodesc\n---\n")
    _write(root / "skills" / "long" / "SKILL.md", f"---\nname: {'x' * 65}\ndescription: d\n---\n")
    _write(root / "skills" / "blank" / "SKILL.md", "---\nname: wicked-garden-blank\ndescription: |\n   \n---\n")
    errors = codex_plugin_errors(root)
    assert any("nodesc" in e and "no description" in e for e in errors)
    assert any("blank" in e and "no description" in e for e in errors)
    assert any("65 chars" in e for e in errors)


def test_names_are_whitespace_collapsed_like_codex(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / "spaced" / "SKILL.md", "---\nname: '  wicked-garden-spaced  '\ndescription: |\n  two\n  lines\n---\n")
    names, errors = codex_skill_names(root, [root / "skills"])
    assert errors == [] and "wicked-garden:wicked-garden-spaced" in names


@pytest.mark.parametrize("field,value", [
    ("name", "[invalid, list]"), ("name", "{a: b}"), ("description", "[one, two]"), ("description", "{k: v}"),
])
def test_non_string_name_or_description_fails(tmp_path, field, value):
    root = _fixture(tmp_path)
    other = "description: d" if field == "name" else "name: wicked-garden-alpha"
    _write(root / "skills" / "alpha" / "SKILL.md", f"---\n{field}: {value}\n{other}\n---\n")
    errors = codex_plugin_errors(root)
    assert any("skills/alpha/SKILL.md" in e and "not a string" in e for e in errors), errors


def test_scalar_name_is_accepted_like_serde_yaml(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / "num" / "SKILL.md", "---\nname: 12345\ndescription: 7\n---\n")
    names, errors = codex_skill_names(root, [root / "skills"])
    assert errors == [] and "wicked-garden:12345" in names


def test_duplicate_skill_name_fails(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / "gamma" / "SKILL.md", "---\nname: wicked-garden-alpha\ndescription: dup.\n---\n")
    assert any("duplicate skill name" in e for e in codex_plugin_errors(root))


def test_catalog_skill_codex_cannot_discover_fails(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "skills" / ".hidden" / "x" / "SKILL.md", "---\nname: wicked-garden-x\ndescription: d\n---\n")
    errors = codex_plugin_errors(root)
    assert any(".hidden" in e and "would not discover" in e for e in errors), errors


def test_skills_outside_the_catalog_fail(tmp_path):
    root = _fixture(tmp_path)
    _write(root / "extra" / "one" / "SKILL.md", "---\nname: wicked-garden-one\ndescription: d\n---\n")
    _edit_manifest(root, skills=["./skills", "./extra"])
    assert any("not a catalog skill" in e for e in codex_plugin_errors(root))


# --- what npm ships -----------------------------------------------------------------------


@pytest.mark.skipif(NPM is None and not os.environ.get("CI"), reason="npm not on PATH")
def test_npm_package_ships_the_manifest_and_exactly_the_codex_skills():
    assert NPM, "CI must have npm to check the shipped file list"
    out = subprocess.run([NPM, "pack", "--dry-run", "--json", "--ignore-scripts"], cwd=REPO,
                         capture_output=True, text=True, timeout=300, check=True).stdout
    files = {f["path"].replace("\\", "/") for f in json.loads(out)[0]["files"]}
    for required in (".codex-plugin/plugin.json", ".codex-plugin/mcp.json", "scripts/estate_mcp.mjs",
                     ".claude-plugin/marketplace.json"):
        assert required in files, f"{required} is not in the npm package"
    shipped = {f for f in files if f.startswith("skills/") and f.endswith("/SKILL.md")}
    names, _ = codex_skill_names(REPO, [REPO / "skills"])
    discovered = {p.relative_to(REPO).as_posix() for p in names.values()}
    assert shipped == discovered


# --- version lockstep ---------------------------------------------------------------------


@needs_node
def test_sync_plugin_version_bumps_the_codex_manifest(tmp_path):
    for rel in ("package.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                ".codex-plugin/plugin.json"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    pkg = json.loads((tmp_path / "package.json").read_text())
    pkg["version"] = "99.1.0"
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    subprocess.run([NODE, str(REPO / ".github" / "scripts" / "sync-plugin-version.mjs")],
                   cwd=tmp_path, check=True, capture_output=True, timeout=60)
    codex = json.loads((tmp_path / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text())
    assert codex["version"] == claude["version"] == "99.1.0"
    assert claude["wicked_vault_version"] == json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())["wicked_vault_version"]


# --- the estate launcher --------------------------------------------------------------------


def _fake_bin(directory: Path, name: str = "wicked-estate-mcp") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        f"#!{NODE}\n"
        "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{"
        "process.stdout.write(JSON.stringify({argv:process.argv.slice(2),cwd:process.cwd(),stdin:s}));"
        "process.exit(7);});\n"
    )
    path.chmod(0o755)
    return path


def _env(tmp_path: Path, path_dirs: list[Path], override: str | None = None) -> dict:
    env = {"HOME": str(tmp_path / "home"), "PATH": os.pathsep.join(str(d) for d in path_dirs)}
    if override is not None:
        env["WICKED_ESTATE_MCP_BIN"] = override
    if sys.platform == "win32":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
        env["USERPROFILE"] = env["HOME"]  # Node's homedir() and Python's Path.home() read it on Windows
    return env


def _node_resolve(env: dict) -> str | None:
    code = (f"import({json.dumps(LAUNCHER.as_uri())}).then(m=>process.stdout.write("
            "JSON.stringify(m.resolveEstateMcpBin().bin)))")
    out = subprocess.run([NODE, "-e", code], env=env, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


def _python_resolve(env: dict) -> str | None:
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); import _estate_client as c; "
            "print(json.dumps(c.resolve_mcp_bin()))")
    out = subprocess.run([sys.executable, "-c", code, str(REPO / "scripts")], env=env,
                         capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


@needs_node
@posix_only
@pytest.mark.parametrize("case", ["override", "stale-override", "path", "local-bin", "none", "non-executable-on-path"])
def test_launcher_resolves_like_the_estate_client(tmp_path, case):
    on_path = tmp_path / "on-path"
    local = tmp_path / "home" / ".local" / "bin"
    other = tmp_path / "other"
    node_dir = Path(NODE).parent
    override = None
    if case == "override":
        _fake_bin(on_path)
        override = str(_fake_bin(other))
    elif case == "stale-override":
        _fake_bin(on_path)
        override = str(other / "gone")
    elif case == "path":
        _fake_bin(on_path)
        _fake_bin(local)
    elif case == "local-bin":
        _fake_bin(local)
    elif case == "non-executable-on-path":
        _fake_bin(on_path).chmod(0o644)  # shutil.which skips it; so must the launcher
        _fake_bin(other)
    env = _env(tmp_path, [on_path, other, node_dir] if case == "non-executable-on-path" else [on_path, node_dir], override)
    expected = {
        "override": override,
        "stale-override": str(on_path / "wicked-estate-mcp"),
        "path": str(on_path / "wicked-estate-mcp"),
        "local-bin": str(local / "wicked-estate-mcp"),
        "none": None,
        "non-executable-on-path": str(other / "wicked-estate-mcp"),
    }[case]
    if case == "none" and (node_dir / "wicked-estate-mcp").exists():
        pytest.skip("a real wicked-estate-mcp sits next to node")
    assert _node_resolve(env) == expected
    assert _python_resolve(env) == expected


@needs_node
@posix_only
def test_launcher_passes_stdio_args_cwd_and_exit_code_through(tmp_path):
    bindir = tmp_path / "bin"
    _fake_bin(bindir)
    work = tmp_path / "work"
    work.mkdir()
    res = subprocess.run([NODE, str(LAUNCHER), "--readonly", "--db", "x.db"], cwd=work, input="ping",
                         env=_env(tmp_path, [bindir, Path(NODE).parent]), capture_output=True, text=True, timeout=60)
    assert res.returncode == 7
    out = json.loads(res.stdout)
    assert out["argv"] == ["--readonly", "--db", "x.db"]
    assert out["stdin"] == "ping"
    assert Path(out["cwd"]).resolve() == work.resolve()


@needs_node
def test_launcher_without_a_binary_fails_with_one_json_line(tmp_path):
    env = _env(tmp_path, [Path(NODE).parent])
    if (Path(NODE).parent / "wicked-estate-mcp").exists():
        pytest.skip("a real wicked-estate-mcp sits next to node")
    res = subprocess.run([NODE, str(LAUNCHER)], env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 1
    report = json.loads(res.stderr.strip().splitlines()[-1])
    assert report["ok"] is False and "wicked-estate-mcp not found" in report["reason"]
    assert "PATH" in report["tried"]
