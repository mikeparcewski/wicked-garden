"""The default suite must not fetch packages, even when peers are absent."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests._install_guard import RECORD_ENV, REPORT, SHIM_ENV, guard_environment, without_shims

pytestmark = pytest.mark.skipif(os.name == "nt", reason="install guard is POSIX-only")
ROOT = Path(__file__).resolve().parents[1]
REGRESSION_NODES = [
    "tests/crew/test_loom_resolver.py::InternalDispatchTests::test_compose_install_dispatches_internally",
    "tests/crew/test_loom_resolver.py::InternalDispatchTests::test_doctor_dispatches_internally",
    "tests/crew/test_phase_manager.py::TestCreateProjectArchetypeMode::test_archetype_mode_hydrates_phase_plan",
]


def fake_executable(path, body="print('real binary')"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o755)


@pytest.fixture
def guard_env(tmp_path):
    # Independent record: intentionally blocked calls aren't suite violations.
    binary_dir = tmp_path / "bin"
    for cmd in ("npm", "npx", "pip", "pip3"):
        fake_executable(binary_dir / cmd)
    # A PATH executable outside npm's global bin is insufficient for npx.
    fake_executable(tmp_path / "unrelated-bin" / "sh")
    env = {**os.environ, "PATH": os.pathsep.join([str(binary_dir), str(tmp_path / "unrelated-bin")])}
    return guard_environment(tmp_path / "shims", env)


def invoke(env, *args, cwd=None, timeout=30):
    return subprocess.run(args, env=env, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def records(env):
    return [json.loads(line) for line in Path(env[RECORD_ENV]).read_text().splitlines()]


@pytest.mark.parametrize("cmd,argv", [
    *[("npm", [action, "x"]) for action in (
        "install", "ic", "isnta", "install-test", "install-ci-test", "i", "ci", "exec", "init")],
    ("npm", ["--fetch-retries", "0", "install", "x"]),
    ("npm", ["install", "--offline", "x"]),
    ("npm", ["install", "--offline", "--offline=false", "x"]),
    ("npm", ["exec", "--", "missing-cmd", "--offline"]),
    ("npm", ["--version", "install", "x"]),
    ("npm", ["pack", "some-package"]),
    ("npm", ["pack", "--dry-run", "git+https://example.invalid/r.git"]),
    ("npm", ["pack", "./x"]),
    ("npm", []),
    ("npx", ["sh", "--version"]),
    ("npx", ["-c", "if true; then echo ok; fi"]),
    ("npx", ["--call", "echo ok"]),
    ("npx", ["--cache", "x", "cmd"]),
    ("npx", ["-p", "x", "cmd"]),
    ("npx", ["--package=x", "cmd"]),
    ("npx", ["--script-shell", "/bin/sh", "missing-cmd"]),
    *[("npx", [*flag, "some-missing-cmd-xyz"]) for flag in ([], ["--yes"], ["-y"], ["--no"])],
    ("npx", []),
    ("npx", ["--yes"]),
    ("npx", ["--version", "missing-cmd"]),
    *[(cmd, ["--cert", "ca.pem", "install", "x"]) for cmd in ("pip", "pip3")],
    *[(cmd, [action, "x"]) for cmd in ("pip", "pip3") for action in ("install", "download", "wheel")],
])
def test_calls_outside_allow_lists_are_recorded_and_refused(guard_env, tmp_path, cmd, argv):
    result = invoke(guard_env, cmd, *argv, cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert records(guard_env) == [{"cmd": cmd, "argv": argv,
                                  "test": guard_env["PYTEST_CURRENT_TEST"], "cwd": str(tmp_path)}]


@pytest.mark.parametrize("cmd", ["npm", "pip"])
def test_real_version_passes_through(tmp_path, cmd):
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), without_shims(env)])
    if shutil.which(cmd, path=env["PATH"]) is None:
        pytest.skip(f"no real {cmd} on PATH")
    env = guard_environment(tmp_path / "shims", env)
    result = invoke(env, cmd, "--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert records(env) == []


@pytest.mark.parametrize("path_entry", ["absolute", "relative", "symlink"])
@pytest.mark.parametrize("argv,expected_code", [(["--version"], 0), (["install", "x"], 1)])
def test_shims_work_with_only_path_in_environment(tmp_path, path_entry, argv, expected_code):
    shim_dir = tmp_path / "shims"
    binary_dir = tmp_path / "bin"
    fake_executable(binary_dir / "npm")
    guard_environment(shim_dir, {"PATH": str(binary_dir)})
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


@pytest.mark.parametrize("cmd,argv", [
    *[("npm", [query]) for query in ("--version", "-v", "-h", "--help")],
    ("npm", ["pack"]),
    ("npm", ["pack", "--dry-run", "--json", "--ignore-scripts"]),
    ("npm", ["run", "build"]),
    *[("npm", [command]) for command in (
        "run-script", "test", "config", "prefix", "root", "ls", "list", "help", "version", "explain", "why")],
    ("npm", ["help", "install"]),
    *[("npx", [query]) for query in ("--version", "-v", "--help")],
    *[(cmd, [query]) for cmd in ("pip", "pip3") for query in ("--version", "-V", "-h", "--help")],
    *[(cmd, [command, "x"]) for cmd in ("pip", "pip3") for command in (
        "show", "list", "freeze", "help", "check", "config", "inspect", "debug")],
])
def test_allow_list_calls_pass_through(guard_env, tmp_path, cmd, argv):
    result = invoke(guard_env, cmd, *argv, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "real binary"
    assert records(guard_env) == []


@pytest.mark.parametrize("cmd", ["npm", "npx", "pip", "pip3"])
def test_only_npm_and_npx_pass_through_with_offline_environment(guard_env, tmp_path, cmd):
    guard_env.pop("npm_config_offline", None)
    fake_executable(tmp_path / "bin" / cmd,
                    "import os; print(os.environ.get('npm_config_offline'))")
    result = invoke(guard_env, cmd, "--version", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("true" if cmd in {"npm", "npx"} else "None")
    assert records(guard_env) == []


def test_independent_guard_refusals_do_not_leak_to_session_record(guard_env, tmp_path):
    parent_record = Path(os.environ[RECORD_ENV])
    before = parent_record.read_bytes()
    assert Path(guard_env[RECORD_ENV]) != parent_record
    result = invoke(guard_env, "npm", "install", "x", cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert len(records(guard_env)) == 1
    assert parent_record.read_bytes() == before


@pytest.mark.parametrize("local", [False, True], ids=["global-bin", "local-bin"])
@pytest.mark.parametrize("flag", [[], ["--yes"], ["-y"], ["--no"]])
def test_npx_allows_executables_in_npm_bin_directories(guard_env, tmp_path, local, flag):
    peer = tmp_path / "node_modules" / ".bin" if local else tmp_path / "bin"
    fake_executable(peer / "wicked-vault")
    result = invoke(guard_env, "npx", *flag, "wicked-vault", "--version", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert records(guard_env) == []


def test_real_npx_runs_globally_installed_vault(tmp_path):
    env = dict(os.environ)
    env["PATH"] = without_shims(env)
    npx = shutil.which("npx", path=env["PATH"])
    if npx is None or shutil.which("wicked-vault", path=str(Path(npx).parent)) is None:
        pytest.skip("requires wicked-vault installed beside npx")
    env = guard_environment(tmp_path / "shims", env)
    result = invoke(env, "npx", "--no", "wicked-vault", "--version", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip()
    assert records(env) == []


@pytest.mark.parametrize("cmd", ["npm", "npx", "pip", "pip3"])
def test_absent_tools_stay_absent(tmp_path, cmd):
    env = guard_environment(tmp_path / "shims", {**os.environ, "PATH": str(tmp_path / "empty-bin")})
    assert shutil.which(cmd, path=env["PATH"]) is None
    assert not (Path(env[SHIM_ENV]) / cmd).exists()


def test_vanished_real_binary_exits_127(tmp_path):
    binary = tmp_path / "bin" / "npm"
    fake_executable(binary)
    env = guard_environment(tmp_path / "shims", {**os.environ, "PATH": str(binary.parent)})
    binary.unlink()
    result = invoke(env, "npm", "--version")
    assert result.returncode == 127
    assert "no real npm" in result.stderr
    assert records(env) == []


def session_environment(tmp_path):
    """An independent pytest owner, with no inherited suite recording or plugins."""
    binary_dir = tmp_path / "bin"
    fake_executable(binary_dir / "npm")
    env = {**os.environ, "PATH": str(binary_dir), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    for key in (SHIM_ENV, RECORD_ENV, "WICKED_GARDEN_E2E_NPM", "PYTEST_ADDOPTS"):
        env.pop(key, None)
    return env


def pytest_args(test_file):
    return ["-q", "-p", "tests._install_guard", "-p", "no:cacheprovider", "--noconftest",
            "--rootdir", str(test_file.parent), "-c", os.devnull, str(test_file)]


def test_swallowed_refusal_fails_otherwise_passing_session(tmp_path):
    test_file = tmp_path / "test_swallow.py"
    test_file.write_text("import subprocess\ndef test_swallow():\n    subprocess.run(['npm', 'install', 'x'])\n")
    result = invoke(session_environment(tmp_path), sys.executable, "-m", "pytest", *pytest_args(test_file), cwd=ROOT)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "1 passed" in output and REPORT in output, output
    assert "npm install x" in output, output


@pytest.mark.parametrize("reset_path", [False, True], ids=["inherited-path", "rebuilt-path"])
def test_nested_refusal_fails_outer_session_even_when_inner_result_is_ignored(tmp_path, reset_path):
    inner = tmp_path / "test_inner.py"
    inner.write_text("import subprocess\ndef test_inner():\n    subprocess.run(['npm', 'install', 'x'])\n")
    outer = tmp_path / "test_outer.py"
    command = [sys.executable, "-m", "pytest", *pytest_args(inner)]
    outer.write_text("import os, subprocess\ndef test_outer():\n"
                     "    env = dict(os.environ)\n"
                     + (f"    env['PATH'] = {str(tmp_path / 'bin')!r}\n" if reset_path else "")
                     + f"    subprocess.run({command!r}, env=env, capture_output=True, timeout=60)\n")
    result = invoke(session_environment(tmp_path), sys.executable, "-m", "pytest", *pytest_args(outer),
                    cwd=ROOT, timeout=120)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "1 passed" in output and REPORT in output, output
    assert "npm install x" in output and "test_inner" in output, output


@pytest.mark.parametrize("inherited", [False, True], ids=["owner", "inherited"])
def test_session_restores_environment_and_only_owner_removes_shims(tmp_path, inherited):
    env = session_environment(tmp_path)
    if inherited:
        env = guard_environment(tmp_path / "shared-shims", env)
    marker = tmp_path / "shim-path.txt"
    test_file = tmp_path / "test_environment.py"
    test_file.write_text("import os\nfrom pathlib import Path\ndef test_environment():\n"
                         f"    Path({str(marker)!r}).write_text(os.environ[{SHIM_ENV!r}])\n"
                         + (f"    assert os.environ['PATH'] == {env['PATH']!r}\n" if inherited else ""))
    script = f"""
import os
from pathlib import Path
import pytest
keys = ('PATH', {SHIM_ENV!r}, {RECORD_ENV!r})
before = {{key: os.environ.get(key) for key in keys}}
code = pytest.main({pytest_args(test_file)!r})
assert {{key: os.environ.get(key) for key in keys}} == before
shim = Path(Path({str(marker)!r}).read_text())
assert shim.exists() == {inherited!r}
if {inherited!r}:
    assert str(shim) == before[{SHIM_ENV!r}]
print('environment restored')
raise SystemExit(code)
"""
    result = invoke(env, sys.executable, "-c", script, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "environment restored" in result.stdout


def test_inherited_session_ignores_earlier_records_and_preserves_them(tmp_path):
    env = guard_environment(tmp_path / "shared-shims", session_environment(tmp_path))
    refused = invoke(env, "npm", "install", "earlier")
    assert refused.returncode == 1
    test_file = tmp_path / "test_clean.py"
    test_file.write_text("def test_clean():\n    pass\n")
    result = invoke(env, sys.executable, "-m", "pytest", *pytest_args(test_file), cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert REPORT not in result.stdout
    assert records(env)[0]["argv"] == ["install", "earlier"]


def test_default_dispatch_and_phase_creation_never_install(tmp_path):
    env = dict(os.environ)
    # Available package managers, absent peers: accidental probes must reach the
    # child guard even on hosts with no Node installation.
    binary_dir = tmp_path / "bin"
    for cmd in ("npm", "npx"):
        fake_executable(binary_dir / cmd)
    env["PATH"] = os.pathsep.join([str(binary_dir), str(Path(sys.executable).parent), "/usr/bin", "/bin"])
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
    fake_executable(binary_dir / "pip")
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
