"""install.mjs honours CLAUDE_CONFIG_DIR, --claude-home and --dry-run (#1117).

Black-box over the REAL CLI (``node install.mjs …``): every case runs against a
temp HOME and a temp CLAUDE_CONFIG_DIR, with PATH reduced to an EMPTY directory
so ``uv`` can never be found (nothing syncs, nothing downloads) and node is
invoked by absolute path. The operator's config dirs are never touched.

Target resolution mirrors wicked-installer's ``install-claude.ts``:
``--claude-home`` flags are the full set → ``CLAUDE_CONFIG_DIR`` (authoritative;
may list several dirs, split on the platform list separator + ',') → ``~/.claude``.
Registration is the installer's job (wicked-installer#18): the copy is reported
as unregistered and the note points at ``npx wicked-installer install wicked-garden``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INSTALL_MJS = _REPO_ROOT / "install.mjs"
_NODE = shutil.which("node")
_PKG_VERSION = json.loads((_REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]

_REGISTER_NOTE = (
    "copied (unregistered). Claude Code loads plugins through its marketplace registry — "
    "run `npx wicked-installer install wicked-garden` to register it in the active config dir."
)

pytestmark = pytest.mark.skipif(_NODE is None, reason="node not on PATH")


class Sandbox:
    """A temp HOME + an empty PATH dir; ``run`` drives install.mjs inside it."""

    def __init__(self, root: Path):
        self.home = root / "home"
        self.home.mkdir()
        self.empty_path = root / "empty-path"
        self.empty_path.mkdir()
        self.root = root

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            "PATH": str(self.empty_path),      # uv is unreachable — no sync, ever
            "HOME": str(self.home),            # os.homedir() on POSIX
            "USERPROFILE": str(self.home),     # os.homedir() on Windows
        }
        for key in ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "LANG", "LC_ALL"):
            if key in os.environ:
                env[key] = os.environ[key]
        env.update(extra)
        return env

    def run(self, *args: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [_NODE, str(_INSTALL_MJS), *args],
            cwd=str(self.root),
            env=self.env(**extra_env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )

    def cfg(self, name: str) -> Path:
        return self.root / name


def dest_of(config_dir: Path) -> Path:
    return config_dir / "plugins" / "wicked-garden"


def installed_version(config_dir: Path) -> str:
    manifest = dest_of(config_dir) / ".claude-plugin" / "plugin.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


# --- target resolution ------------------------------------------------------


def test_default_target_is_home_dot_claude(sandbox: Sandbox) -> None:
    res = sandbox.run("install")
    assert res.returncode == 0, res.stderr
    default_dir = sandbox.home / ".claude"
    assert installed_version(default_dir) == _PKG_VERSION
    assert f"config dir: {default_dir} (default)" in res.stdout
    # the copy is honest about what it is and who registers it
    assert _REGISTER_NOTE in res.stdout
    # dev-only scripts/ subdirs are stripped; runtime dirs land
    dest = dest_of(default_dir)
    assert (dest / "hooks").is_dir() and (dest / "skills").is_dir()
    assert not (dest / "scripts" / "ci").exists()
    assert not (dest / "scripts" / "wg").exists()
    # uv was unreachable, so the copy never synced
    assert "uv sync" not in res.stdout
    assert not (dest / ".venv").exists()


def test_claude_config_dir_wins_over_home(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert installed_version(cfg) == _PKG_VERSION
    assert f"config dir: {cfg} (CLAUDE_CONFIG_DIR)" in res.stdout
    assert not (sandbox.home / ".claude").exists(), "must not fall back to ~/.claude"


@pytest.mark.parametrize("sep", [os.pathsep, ","], ids=["pathsep", "comma"])
def test_claude_config_dir_may_list_several_dirs(sandbox: Sandbox, sep: str) -> None:
    a, b = sandbox.cfg("a"), sandbox.cfg("b")
    # whitespace, a duplicate and a trailing separator are all tolerated
    value = f" {a} {sep}{b}{sep}{a}{sep}"
    res = sandbox.run("install", "--dry-run", CLAUDE_CONFIG_DIR=value)
    assert res.returncode == 0, res.stderr
    for d in (a, b):
        assert f"config dir: {d} (CLAUDE_CONFIG_DIR)" in res.stdout
        assert f"would copy skills/ -> {dest_of(d) / 'skills'}" in res.stdout
    assert res.stdout.count("[dry-run] Installing") == 2, "duplicate dir must be de-duplicated"
    assert "would be copied into 2 config dirs" in res.stdout


def test_claude_home_flags_are_the_full_set(sandbox: Sandbox) -> None:
    x, y, z = sandbox.cfg("x"), sandbox.cfg("y"), sandbox.cfg("z")
    res = sandbox.run(
        "install", "--dry-run", "--claude-home", str(x), f"--claude-home={y}",
        CLAUDE_CONFIG_DIR=str(z),
    )
    assert res.returncode == 0, res.stderr
    assert f"config dir: {x} (--claude-home)" in res.stdout
    assert f"config dir: {y} (--claude-home)" in res.stdout
    assert str(z) not in res.stdout, "CLAUDE_CONFIG_DIR must be ignored when flags are given"


def test_tilde_expands_against_the_sandbox_home(sandbox: Sandbox) -> None:
    res = sandbox.run("install", "--dry-run", CLAUDE_CONFIG_DIR="~/cfg")
    assert res.returncode == 0, res.stderr
    assert f"config dir: {sandbox.home / 'cfg'} (CLAUDE_CONFIG_DIR)" in res.stdout


# --- dry-run ----------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [["install", "--dry-run"], ["--dry-run", "install"], ["--dry-run"], ["update", "--dry-run"]],
    ids=["after-cmd", "before-cmd", "bare", "update"],
)
def test_dry_run_prints_the_plan_and_writes_nothing(sandbox: Sandbox, argv: list[str]) -> None:
    cfg = sandbox.cfg("cfg")
    res = sandbox.run(*argv, CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert f"[dry-run] Installing wicked-garden v{_PKG_VERSION} to {dest_of(cfg)}" in res.stdout
    for planned in (".claude-plugin/", "hooks/", "scripts/", "skills/", "schemas/", "pyproject.toml"):
        assert f"would copy {planned}" in res.stdout
    assert "uv not found — would skip Python deps" in res.stdout
    assert "[dry-run] Nothing was written" in res.stdout
    assert not cfg.exists(), "dry-run must not create the config dir"
    assert not (sandbox.home / ".claude").exists()
    assert _REGISTER_NOTE not in res.stdout, "nothing was copied, so no copy note"


# --- status -----------------------------------------------------------------


def test_status_reports_per_config_dir(sandbox: Sandbox) -> None:
    a, b = sandbox.cfg("a"), sandbox.cfg("b")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(a)).returncode == 0

    res = sandbox.run("status", CLAUDE_CONFIG_DIR=f"{a}{os.pathsep}{b}")
    assert res.returncode == 0, res.stderr
    assert f"config dir: {a} (CLAUDE_CONFIG_DIR)" in res.stdout
    assert f"config dir: {b} (CLAUDE_CONFIG_DIR)" in res.stdout
    assert "wicked-garden: installed (copy)" in res.stdout
    assert f"path:    {dest_of(a)}" in res.stdout
    assert f"version: {_PKG_VERSION}" in res.stdout
    assert "wicked-garden: not installed" in res.stdout
    assert "registration: owned by wicked-installer" in res.stdout

    # a stale copy is flagged against the package version
    manifest = dest_of(a) / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = "0.0.1"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    res = sandbox.run("status", "--claude-home", str(a))
    assert f"version: 0.0.1 (package: {_PKG_VERSION} — run install to update)" in res.stdout
    assert f"config dir: {a} (--claude-home)" in res.stdout


def test_status_hint_reproduces_an_explicit_claude_home(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    res = sandbox.run("status", "--claude-home", str(cfg))
    assert res.returncode == 0, res.stderr
    assert f'Run: npx wicked-garden@{_PKG_VERSION} install --claude-home "{cfg}"' in res.stdout


# --- argument handling ------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [["install", "--bogus"], ["install", "--claude-home"], ["install", "extra"], ["install", "--claude-home="]],
    ids=["unknown-option", "missing-dir", "stray-positional", "empty-dir"],
)
def test_usage_errors_exit_2_and_write_nothing(sandbox: Sandbox, argv: list[str]) -> None:
    cfg = sandbox.cfg("cfg")
    res = sandbox.run(*argv, CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 2
    assert res.stderr.startswith("Error: ")
    assert "Usage:" in res.stderr
    assert not cfg.exists()


@pytest.mark.parametrize(
    "argv",
    [["foo"], ["--bogus"], ["-x"], ["status", "--dry-run"]],
    ids=["unknown-command", "unknown-option", "unknown-short-option", "dry-run-on-status"],
)
def test_unknown_commands_exit_2_with_usage_on_stderr(sandbox: Sandbox, argv: list[str]) -> None:
    cfg = sandbox.cfg("cfg")
    res = sandbox.run(*argv, CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 2
    assert res.stdout == "", "errors never go to stdout"
    assert res.stderr.startswith("Error: ")
    assert "Usage:" in res.stderr
    assert not cfg.exists()


def test_dry_run_on_status_names_the_rule(sandbox: Sandbox) -> None:
    res = sandbox.run("status", "--dry-run")
    assert res.returncode == 2
    assert "--dry-run applies to install/update only (status is read-only)" in res.stderr


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_prints_usage_on_stdout(sandbox: Sandbox, flag: str) -> None:
    res = sandbox.run(flag)
    assert res.returncode == 0, res.stderr
    assert res.stderr == ""
    assert res.stdout.startswith(f"wicked-garden v{_PKG_VERSION}")
    assert "Usage:" in res.stdout
    assert "--dry-run" in res.stdout and "install/update only" in res.stdout
    assert not (sandbox.home / ".claude").exists()


def test_version_and_pack_usage_are_unchanged(sandbox: Sandbox) -> None:
    res = sandbox.run("--version")
    assert res.returncode == 0 and res.stdout.strip() == _PKG_VERSION
    res = sandbox.run("pack")
    assert res.returncode == 0
    assert "Usage: npx wicked-garden pack <verb>" in res.stdout
    assert not (sandbox.home / ".claude").exists()
