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

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
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
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks / sh sentinel")


class Sandbox:
    """A temp HOME + an empty PATH dir; ``run`` drives install.mjs inside it."""

    def __init__(self, root: Path):
        self.home = root / "home"
        self.home.mkdir()
        self.path_dir = root / "path-dir"      # the ONLY PATH entry; empty unless a sentinel is planted
        self.path_dir.mkdir()
        self.root = root

    def sentinel_uv(self) -> Path:
        """Plant an executable ``uv`` that records its argv to a marker and exits 1."""
        marker = self.root / "uv-invocations.log"
        script = self.path_dir / "uv"
        script.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"uv $*\" >> \"{marker}\"\n"
            "printf '%s\\n' 'sentinel uv: boom' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return marker

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            "PATH": str(self.path_dir),        # uv is unreachable unless a sentinel is planted
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


def tree(root: Path) -> dict[str, str]:
    """Content snapshot of a tree: relpath -> dir | symlink:<target> | sha256(bytes)."""
    if not root.exists():
        return {"<absent>": ""}
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            out[rel] = "symlink:" + os.readlink(p)
        elif p.is_dir():
            out[rel] = "dir"
        else:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


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


@pytest.mark.parametrize(
    "argv",
    [["--dry-run", "pack", "check", "."], ["--claude-home", "x", "pack", "list"], ["--version", "--dry-run"], ["--dry-run", "--help"]],
    ids=["dry-run-before-pack", "claude-home-before-pack", "version", "help"],
)
def test_install_only_flags_are_rejected_for_other_commands(sandbox: Sandbox, argv: list[str]) -> None:
    # never "accepted and ignored" while the command runs for real (a pack check would run un-dry)
    res = sandbox.run(*argv)
    assert res.returncode == 2
    assert res.stdout == ""
    assert "applies to install/update/status only" in res.stderr
    if "pack" in argv:
        assert "pack verbs own their flags" in res.stderr
    assert not (sandbox.home / ".claude").exists()


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


# --- option consumption -----------------------------------------------------


@pytest.mark.parametrize("value", ["--dry-run", "-v", "   "], ids=["long-option", "short-option", "blank"])
def test_claude_home_never_swallows_an_option(sandbox: Sandbox, value: str) -> None:
    res = sandbox.run("install", "--claude-home", value)
    assert res.returncode == 2
    assert res.stdout == ""
    assert "--claude-home requires a directory" in res.stderr
    assert not (sandbox.root / "--dry-run").exists(), "the option must not become a directory"
    assert not (sandbox.home / ".claude").exists()
    assert not (sandbox.root / "-v").exists()


def test_claude_home_equals_form_accepts_a_dir_named_like_an_option(sandbox: Sandbox) -> None:
    # the explicit `=` form is unambiguous, so a dir literally called "-x" is allowed there
    res = sandbox.run("install", "--dry-run", f"--claude-home={sandbox.root / '-x'}")
    assert res.returncode == 0, res.stderr
    assert f"config dir: {sandbox.root / '-x'} (--claude-home)" in res.stdout


# --- CLAUDE_CONFIG_DIR fail-closed -----------------------------------------


@pytest.mark.parametrize(
    "value",
    [f"{os.pathsep},", "   ", " , ", ",", f"{os.pathsep}{os.pathsep}"],
    ids=["seps", "blank", "blank-entries", "comma", "pathseps"],
)
def test_malformed_claude_config_dir_fails_closed(sandbox: Sandbox, value: str) -> None:
    for argv in (["install"], ["install", "--dry-run"], ["status"]):
        res = sandbox.run(*argv, CLAUDE_CONFIG_DIR=value)
        assert res.returncode == 2, (argv, res.stderr)
        assert res.stdout == ""
        assert "CLAUDE_CONFIG_DIR is set but names no directory" in res.stderr
    assert not (sandbox.home / ".claude").exists(), "must never fall back to ~/.claude"


def test_empty_claude_config_dir_counts_as_unset(sandbox: Sandbox) -> None:
    # ${CLAUDE_CONFIG_DIR:-~/.claude}: the empty string is the shell's "unset"
    res = sandbox.run("install", "--dry-run", CLAUDE_CONFIG_DIR="")
    assert res.returncode == 0, res.stderr
    assert f"config dir: {sandbox.home / '.claude'} (default)" in res.stdout


# --- symlink containment ----------------------------------------------------


@posix_only
@pytest.mark.parametrize("owned", ["plugins", "plugins/wicked-garden"], ids=["plugins-dir", "plugin-dir"])
def test_symlinked_owned_path_is_refused_by_install(sandbox: Sandbox, owned: str) -> None:
    elsewhere = sandbox.root / "elsewhere"
    elsewhere.mkdir()
    cfg = sandbox.cfg("cfg")
    link = cfg / owned
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(elsewhere, link, target_is_directory=True)

    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 1
    assert "refusing to install" in res.stderr and "symlink" in res.stderr
    assert str(link) in res.stderr
    assert "Installing" not in res.stdout, "refusal happens before any copy starts"
    assert list(elsewhere.iterdir()) == [], "nothing may be written through the link"
    assert os.path.islink(link)


@posix_only
def test_symlinked_config_dir_itself_is_allowed_and_contained(sandbox: Sandbox) -> None:
    # dotfiles-managed ~/.claude is a symlink in many setups — we never create it, so we honour it
    real = sandbox.root / "dotfiles-claude"
    real.mkdir()
    cfg = sandbox.cfg("cfg")
    os.symlink(real, cfg, target_is_directory=True)
    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert installed_version(real) == _PKG_VERSION


@posix_only
def test_symlinked_manifest_is_refused_by_status_and_install(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0
    manifest = dest_of(cfg) / ".claude-plugin" / "plugin.json"
    fake = sandbox.root / "fake.json"
    fake.write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    manifest.unlink()
    os.symlink(fake, manifest)

    res = sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 1
    assert "refused" in res.stderr and "symlink" in res.stderr and str(manifest) in res.stderr
    assert "9.9.9" not in res.stdout, "a symlinked manifest is never read"
    assert "installed (copy)" not in res.stdout

    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 1
    assert "refusing to install" in res.stderr
    assert json.loads(fake.read_text(encoding="utf-8")) == {"version": "9.9.9"}, "never written through"


# --- uv failure surfaced ----------------------------------------------------


@posix_only
def test_uv_sync_failure_is_surfaced_not_swallowed(sandbox: Sandbox) -> None:
    marker = sandbox.sentinel_uv()
    cfg = sandbox.cfg("cfg")
    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 1
    assert "Python deps (uv sync)... FAILED" in res.stdout
    assert f"WARNING: uv sync failed in {dest_of(cfg)}" in res.stderr
    assert "sentinel uv: boom" in res.stderr, "the uv error itself is shown"
    assert "FAILED to sync" in res.stderr, "the summary is a non-success"
    assert "Then, in Claude Code" not in res.stdout, "no success epilogue after a failed step"
    assert installed_version(cfg) == _PKG_VERSION, "the copy itself still landed"
    assert _REGISTER_NOTE in res.stdout
    assert marker.read_text(encoding="utf-8").splitlines() == ["uv sync --quiet"]


# --- idempotence / dry-run byte-identical -----------------------------------


def test_repeat_install_is_idempotent(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    first = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert first.returncode == 0, first.stderr
    assert "Installing wicked-garden" in first.stdout
    before = tree(dest_of(cfg))

    second = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert second.returncode == 0, second.stderr
    assert "Updating wicked-garden" in second.stdout
    assert tree(dest_of(cfg)) == before
    assert installed_version(cfg) == _PKG_VERSION


@posix_only
def test_dry_run_leaves_the_tree_byte_identical_and_spawns_nothing(sandbox: Sandbox) -> None:
    marker = sandbox.sentinel_uv()
    cfg = sandbox.cfg("cfg")
    (cfg / "plugins" / "other").mkdir(parents=True)
    (cfg / "plugins" / "other" / "x.txt").write_text("keep me", encoding="utf-8")
    (cfg / "settings.json").write_text("{}", encoding="utf-8")
    before = tree(cfg)

    res = sandbox.run("install", "--dry-run", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert "would run: uv sync --quiet" in res.stdout, "uv is detected on PATH…"
    assert not marker.exists(), "…but never spawned"
    assert tree(cfg) == before
    assert not dest_of(cfg).exists()
    assert not (sandbox.home / ".claude").exists()
