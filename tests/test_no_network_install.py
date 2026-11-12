"""The default suite must not fetch packages, even when peers are absent."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests._install_guard import RECORD_ENV, REPORT, guard_environment, without_shims

pytestmark = pytest.mark.skipif(os.name == "nt", reason="install guard is POSIX-only")
ROOT = Path(__file__).resolve().parents[1]
REGRESSION_NODES = [
    "tests/crew/test_loom_resolver.py::InternalDispatchTests::test_compose_install_dispatches_internally",
    "tests/crew/test_loom_resolver.py::InternalDispatchTests::test_doctor_dispatches_internally",
    "tests/crew/test_phase_manager.py::TestCreateProjectArchetypeMode::test_archetype_mode_hydrates_phase_plan",
]


@pytest.fixture
def guard_env(tmp_path):
    # Independent record: intentionally blocked unit-test calls aren't suite violations.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), without_shims(env)])
    return guard_environment(tmp_path / "shims", env)


def invoke(env, *args, cwd=None):
    return subprocess.run(args, env=env, cwd=cwd, capture_output=True, text=True, timeout=30)


def records(env):
    return [json.loads(line) for line in Path(env[RECORD_ENV]).read_text().splitlines()]


@pytest.mark.parametrize("cmd,argv", [
    ("npm", ["install", "-g", "x"]),
    *[("npm", [alias, "x"]) for alias in (
        "i", "in", "ins", "inst", "insta", "instal", "isnt", "isntall", "add", "ci",
        "clean-install", "update", "up", "upgrade", "exec", "x", "create", "view", "init")],
    ("npm", ["--prefix", "somewhere", "install", "x"]),
    ("npm", ["--loglevel", "silent", "install", "x"]),
    ("npm", ["--location", "global", "install", "x"]),
    ("npx", ["some-missing-cmd-xyz"]),
    ("npx", ["--yes", "some-missing-cmd-xyz"]),
    ("npx", ["-y", "some-missing-cmd-xyz"]),
    ("npx", ["--no", "some-missing-cmd-xyz"]),
    ("npx", ["-p", "x", "python"]),
    ("npx", ["--package=x", "python"]),
    ("npx", ["--package", "x", "python"]),
    ("npx", ["-c", "some-missing-cmd-xyz --version"]),
    *[(cmd, [action, "x"]) for cmd in ("pip", "pip3") for action in ("install", "download", "wheel")],
])
def test_network_installs_are_recorded_and_refused(guard_env, tmp_path, cmd, argv):
    result = invoke(guard_env, cmd, *argv, cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert records(guard_env) == [{"cmd": cmd, "argv": argv,
                                  "test": guard_env["PYTEST_CURRENT_TEST"], "cwd": str(tmp_path)}]


@pytest.mark.parametrize("cmd", ["npm", "pip"])
def test_real_version_passes_through(guard_env, cmd):
    if shutil.which(cmd, path=without_shims(guard_env)) is None:
        pytest.skip(f"no real {cmd} on PATH")
    result = invoke(guard_env, cmd, "--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert records(guard_env) == []


def fake_executable(path, body="print('real binary')"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o755)


@pytest.mark.parametrize("path_entry", ["absolute", "relative", "symlink"])
@pytest.mark.parametrize("argv,expected_code", [(["--version"], 0), (["install", "x"], 1)])
def test_shims_work_with_only_path_in_environment(tmp_path, path_entry, argv, expected_code):
    shim_dir = tmp_path / "shims"
    binary_dir = tmp_path / "bin"
    fake_executable(binary_dir / "npm")
    guard_environment(shim_dir, {})
    if path_entry == "relative":
        entry = shim_dir.name
    elif path_entry == "symlink":
        link = tmp_path / "shim-link"
        link.symlink_to(shim_dir, target_is_directory=True)
        entry = str(link)
    else:
        entry = str(shim_dir)
    env = {"PATH": entry + os.pathsep + str(binary_dir)}

    result = invoke(env, "npm", *argv, cwd=tmp_path)

    assert result.returncode == expected_code, result.stderr
    recorded = [json.loads(line) for line in (shim_dir / "calls.jsonl").read_text().splitlines()]
    if expected_code == 0:
        assert result.stdout.strip() == "real binary"
        assert recorded == []
    else:
        assert recorded == [{"cmd": "npm", "argv": argv, "test": "", "cwd": str(tmp_path)}]


@pytest.mark.parametrize("cmd,argv,local", [
    ("npm", ["install", "--offline", "x"], False),
    ("npm", ["pack"], False),
    ("npm", ["run", "build"], False),
    ("npm", ["init", "--yes"], False),
    ("npm", ["init", "--scope", "example"], False),
    ("npx", ["--yes", "wicked-vault", "--version"], False),
    ("npx", ["--no", "wicked-vault", "--version"], True),
    ("npx", ["-c", "wicked-vault --version"], True),
])
def test_safe_calls_pass_through_without_fetching(tmp_path, cmd, argv, local):
    binary_dir = tmp_path / "bin"
    fake_executable(binary_dir / cmd)
    peer = tmp_path / "node_modules" / ".bin" if local else binary_dir
    fake_executable(peer / "wicked-vault")
    env = guard_environment(tmp_path / "shims", {**os.environ, "PATH": str(binary_dir)})
    result = invoke(env, cmd, *argv, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "real binary"
    assert records(env) == []


def test_missing_real_binary_exits_127(tmp_path):
    env = guard_environment(tmp_path / "shims", {**os.environ, "PATH": ""})
    result = invoke(env, "npm", "--version")
    assert result.returncode == 127
    assert "no real npm" in result.stderr
    assert records(env) == []


def test_default_dispatch_and_phase_creation_never_install():
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"])
    env.pop("WICKED_GARDEN_E2E_NPM", None)
    # The child must prove its own fixture disables the bus, not inherit ours.
    env.pop("WICKED_BUS_DISABLED", None)
    for peer in ("BUS", "VAULT", "LEDGER"):
        env.pop(f"WICKED_{peer}_BIN", None)
        assert shutil.which(f"wicked-{peer.lower()}", path=env["PATH"]) is None
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *REGRESSION_NODES],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert REPORT not in output, output


def test_safe_command_keeps_descendant_installs_guarded(tmp_path):
    binary_dir = tmp_path / "bin"
    fake_executable(binary_dir / "npm", "import subprocess; subprocess.run(['pip', 'install', 'x'])")
    env = guard_environment(tmp_path / "shims", {**os.environ, "PATH": str(binary_dir)})
    result = invoke(env, "npm", "run", "build")
    assert result.returncode == 0  # the parent deliberately swallows the failure
    assert [(r["cmd"], r["argv"]) for r in records(env)] == [("pip", ["install", "x"])]


@pytest.mark.parametrize("disabled_by", ["windows", "opt_in"])
def test_guard_is_inactive_for_windows_or_opt_in(monkeypatch, disabled_by):
    from types import SimpleNamespace
    from tests import _install_guard

    config = SimpleNamespace()
    before = dict(os.environ)
    with monkeypatch.context() as patch:
        if disabled_by == "windows":
            patch.setattr(_install_guard.os, "name", "nt")
        else:
            patch.setenv("WICKED_GARDEN_E2E_NPM", "1")
        _install_guard.pytest_configure(config)
        _install_guard.pytest_sessionfinish(SimpleNamespace(config=config), 0)
    assert not hasattr(config, "_install_guard")
    assert dict(os.environ) == before
