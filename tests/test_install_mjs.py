"""install.mjs honours CLAUDE_CONFIG_DIR, --claude-home and --dry-run (#1117).

Black-box over the REAL CLI (``node install.mjs …``): every case runs against a
temp HOME and a temp CLAUDE_CONFIG_DIR, with PATH reduced to an EMPTY directory
so ``uv`` can never be found (nothing syncs, nothing downloads) and node is
invoked by absolute path. The operator's config dirs are never touched.

Target resolution mirrors wicked-installer's ``install-claude.ts``:
``--claude-home`` flags are the full set → ``CLAUDE_CONFIG_DIR`` (authoritative
whenever the key is PRESENT; may list several dirs, split on the platform list
separator + ',') → ``~/.claude`` only when the key is absent.

A copy lands stage → verify → atomic swap: it is written into a staging dir
the run creates (``plugins/.staging-wicked-garden-<pid>-<hex>``), lstat-walked,
then rename(2)'d over ``plugins/wicked-garden`` (a previous copy passes through
``plugins/.old-wicked-garden-<pid>-<hex>``). Registration is the installer's job
(wicked-installer#18): the copy is reported as unregistered and the note points
at ``npx wicked-installer install wicked-garden``.
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
_SPAWN_GUARD = _REPO_ROOT / "tests" / "fixtures" / "spawn_guard.cjs"
_NODE = shutil.which("node")
_PKG_VERSION = json.loads((_REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]

_REGISTER_NOTE = (
    "copied (unregistered). Claude Code loads plugins through its marketplace registry — "
    "run `npx wicked-installer install wicked-garden` to register it in the active config dir."
)

pytestmark = pytest.mark.skipif(_NODE is None, reason="node not on PATH")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks / sh sentinel / chmod")
not_root = pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
    reason="permission denials do not apply to root",
)


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

    def run(self, *args: str, node_flags: tuple[str, ...] = (), **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [_NODE, *node_flags, str(_INSTALL_MJS), *args],
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


def manifest_of(config_dir: Path) -> Path:
    return dest_of(config_dir) / ".claude-plugin" / "plugin.json"


def installed_version(config_dir: Path) -> str:
    return json.loads(manifest_of(config_dir).read_text(encoding="utf-8"))["version"]


def transients(config_dir: Path) -> list[str]:
    plugins = config_dir / "plugins"
    if not plugins.exists():
        return []
    return sorted(p.name for p in plugins.iterdir() if p.name.startswith((".staging-wicked-garden-", ".old-wicked-garden-")))


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


def test_default_target_is_home_dot_claude_when_key_absent(sandbox: Sandbox) -> None:
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
    assert transients(default_dir) == [], "staging/old dirs never outlive a successful install"


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


# --- CLAUDE_CONFIG_DIR fail-closed -----------------------------------------


@pytest.mark.parametrize(
    "value",
    ["", f"{os.pathsep},", "   ", " , ", ",", f"{os.pathsep}{os.pathsep}"],
    ids=["empty", "seps", "blank", "blank-entries", "comma", "pathseps"],
)
def test_claude_config_dir_present_but_naming_no_dir_fails_closed(sandbox: Sandbox, value: str) -> None:
    for argv in (["install"], ["install", "--dry-run"], ["status"]):
        res = sandbox.run(*argv, CLAUDE_CONFIG_DIR=value)
        assert res.returncode == 2, (argv, res.stderr)
        assert res.stdout == ""
        assert "CLAUDE_CONFIG_DIR is set but names no directory" in res.stderr
    assert not (sandbox.home / ".claude").exists(), "must never fall back to ~/.claude"


# --- option consumption -----------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["install", "--claude-home", "--dry-run"],
        ["install", "--claude-home", "--x"],
        ["install", "--claude-home", "-v"],
        ["install", "--claude-home", "   "],
        ["install", "--claude-home"],
        ["install", "--claude-home=--dry-run"],
        ["install", "--claude-home=-x"],
        ["install", "--claude-home=   "],
        ["install", "--claude-home="],
    ],
    ids=["space-long", "space-unknown-long", "space-short", "space-blank", "space-missing",
         "eq-long", "eq-short", "eq-blank", "eq-empty"],
)
def test_claude_home_rejects_option_like_and_blank_values_in_both_forms(sandbox: Sandbox, argv: list[str]) -> None:
    res = sandbox.run(*argv)
    assert res.returncode == 2
    assert res.stdout == ""
    assert "requires a directory" in res.stderr
    for stray in ("--dry-run", "--x", "-v", "-x"):
        assert not (sandbox.root / stray).exists(), "an option must never become a directory"
    assert not (sandbox.home / ".claude").exists()


def test_claude_home_accepts_a_dash_dir_when_spelled_as_a_path(sandbox: Sandbox) -> None:
    res = sandbox.run("install", "--dry-run", "--claude-home", "./-x")
    assert res.returncode == 0, res.stderr
    assert f"config dir: {sandbox.root / '-x'} (--claude-home)" in res.stdout


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
    assert "would stage into" in res.stdout and ".staging-wicked-garden-" in res.stdout
    for planned in (".claude-plugin/", "hooks/", "scripts/", "skills/", "schemas/", "pyproject.toml"):
        assert f"would copy {planned}" in res.stdout
    assert "would run: uv sync --quiet" in res.stdout and "not probed in dry-run" in res.stdout
    assert "[dry-run] Nothing was written" in res.stdout
    assert not cfg.exists(), "dry-run must not create the config dir"
    assert not (sandbox.home / ".claude").exists()
    assert _REGISTER_NOTE not in res.stdout, "nothing was copied, so no copy note"


def test_dry_run_spawns_no_child_process(sandbox: Sandbox) -> None:
    """Count child-process attempts directly: every child_process entry point is intercepted
    by the preload and logged; dry-run must leave the log absent."""
    guard = ("--require", str(_SPAWN_GUARD))
    log = sandbox.root / "spawn-guard.log"

    # positive control: the guard is live — `pack check` probes for python via execSync
    control = sandbox.run("pack", "check", ".", node_flags=guard, SPAWN_GUARD_LOG=str(log))
    assert control.returncode != 0
    attempts = log.read_text(encoding="utf-8").split()
    assert attempts and set(attempts) <= {"execSync"}, attempts
    log.unlink()

    cfg = sandbox.cfg("cfg")
    res = sandbox.run("install", "--dry-run", node_flags=guard, SPAWN_GUARD_LOG=str(log), CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert not log.exists(), "dry-run must not attempt a single child process (not even the uv probe)"
    assert "spawn-guard" not in res.stderr
    assert "would copy skills/" in res.stdout and "would run: uv sync --quiet" in res.stdout
    assert not cfg.exists()


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
    assert "would run: uv sync --quiet" in res.stdout
    assert not marker.exists(), "uv is never spawned (nor probed) in dry-run"
    assert tree(cfg) == before
    assert not dest_of(cfg).exists()
    assert transients(cfg) == []
    assert not (sandbox.home / ".claude").exists()


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
    manifest = manifest_of(a)
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


def test_status_reports_a_corrupt_manifest_and_exits_non_zero(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0
    manifest_of(cfg).write_text("{not json", encoding="utf-8")
    res = sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 1
    assert f"error: cannot read {manifest_of(cfg)}" in res.stderr
    assert "JSON" in res.stderr, "the parse failure is named"
    assert "re-run install to repair" in res.stderr
    assert "installed (copy)" not in res.stdout


@not_root
def test_status_reports_an_unreadable_manifest_and_exits_non_zero(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0
    manifest = manifest_of(cfg)
    manifest.chmod(0)
    try:
        res = sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg))
    finally:
        manifest.chmod(0o644)
    assert res.returncode == 1
    assert f"error: cannot read {manifest}" in res.stderr
    assert "EACCES" in res.stderr


def test_status_lists_leftover_transient_dirs(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    leftover = cfg / "plugins" / ".staging-wicked-garden-4242-deadbeef"
    leftover.mkdir(parents=True)
    res = sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert f"leftover transient dir from an interrupted install (not a plugin; safe to delete): {leftover}" in res.stdout
    assert "wicked-garden: not installed" in res.stdout


# --- argument handling ------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [["install", "--bogus"], ["install", "extra"]],
    ids=["unknown-option", "stray-positional"],
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
    assert ".staging-wicked-garden-" in res.stdout and ".old-wicked-garden-" in res.stdout
    assert not (sandbox.home / ".claude").exists()


def test_version_and_pack_usage_are_unchanged(sandbox: Sandbox) -> None:
    res = sandbox.run("--version")
    assert res.returncode == 0 and res.stdout.strip() == _PKG_VERSION
    res = sandbox.run("pack")
    assert res.returncode == 0
    assert "Usage: npx wicked-garden pack <verb>" in res.stdout
    assert not (sandbox.home / ".claude").exists()


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
    assert transients(cfg) == []


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
    assert transients(real) == []


@posix_only
def test_preexisting_tree_symlinks_are_never_followed_or_written_through(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0
    dest = dest_of(cfg)

    # plant: a symlinked top-level file, a symlinked top-level dir, a nested symlinked file
    victim_file = sandbox.root / "victim.md"
    victim_file.write_text("victim", encoding="utf-8")
    victim_dir = sandbox.root / "victim-dir"
    victim_dir.mkdir()
    nested_victim = sandbox.root / "nested-victim.json"
    nested_victim.write_text('{"version":"9.9.9"}', encoding="utf-8")
    (dest / "README.md").unlink()
    os.symlink(victim_file, dest / "README.md")
    shutil.rmtree(dest / "skills")
    os.symlink(victim_dir, dest / "skills", target_is_directory=True)
    manifest_of(cfg).unlink()
    os.symlink(nested_victim, manifest_of(cfg))

    # status refuses to read through the planted manifest link …
    st = sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg))
    assert st.returncode == 1 and "refused" in st.stderr and "symlink" in st.stderr
    assert "9.9.9" not in st.stdout

    # … and install replaces the whole tree via staging without touching any link target
    res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert res.returncode == 0, res.stderr
    assert "Updating" in res.stdout and "previous copy replaced" in res.stdout
    assert victim_file.read_text(encoding="utf-8") == "victim"
    assert list(victim_dir.iterdir()) == []
    assert json.loads(nested_victim.read_text(encoding="utf-8")) == {"version": "9.9.9"}
    assert not (dest / "README.md").is_symlink() and (dest / "README.md").read_bytes() == (_REPO_ROOT / "README.md").read_bytes()
    assert not (dest / "skills").is_symlink() and any((dest / "skills").iterdir())
    assert not manifest_of(cfg).is_symlink() and installed_version(cfg) == _PKG_VERSION
    assert transients(cfg) == []
    assert sandbox.run("status", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0


@not_root
def test_failed_install_leaves_the_previous_copy_intact(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    assert sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg)).returncode == 0
    before = tree(dest_of(cfg))
    plugins = cfg / "plugins"
    plugins.chmod(0o555)  # staging dir cannot be created -> the install must fail before touching the copy
    try:
        res = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    finally:
        plugins.chmod(0o755)
    assert res.returncode == 1
    assert res.stderr.startswith("Error:") and "EACCES" in res.stderr
    assert tree(dest_of(cfg)) == before
    assert transients(cfg) == []


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


# --- idempotence ------------------------------------------------------------


def test_repeat_install_is_idempotent(sandbox: Sandbox) -> None:
    cfg = sandbox.cfg("cfg")
    first = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert first.returncode == 0, first.stderr
    assert "Installing wicked-garden" in first.stdout
    before = tree(dest_of(cfg))

    second = sandbox.run("install", CLAUDE_CONFIG_DIR=str(cfg))
    assert second.returncode == 0, second.stderr
    assert "Updating wicked-garden" in second.stdout and "previous copy replaced" in second.stdout
    assert tree(dest_of(cfg)) == before
    assert installed_version(cfg) == _PKG_VERSION
    assert sorted(p.name for p in (cfg / "plugins").iterdir()) == ["wicked-garden"]
