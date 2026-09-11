"""The `wicked-garden` launcher (scripts/wicked-garden.mjs + its PATH twins + the npm bin).

Black-box over the real CLI (``node scripts/wicked-garden.mjs …``) inside a sandbox whose
environment is built from scratch — the operator's shell may carry ``CLAUDE_PLUGIN_ROOT``
(Claude Code exports it) or ``WICKED_GARDEN_ROOT`` (a crew seat), and neither may leak into
a test. PATH holds ONE directory with a ``node`` symlink and whatever interpreter shims a
test plants (a recording ``python3``, a recording ``uv``), HOME/XDG_CACHE_HOME are temp dirs,
and every fake plugin root is a temp tree carrying ``.claude-plugin/plugin.json``.

Covered: root resolution order (WICKED_GARDEN_ROOT → CLAUDE_PLUGIN_ROOT → own package),
the loud refusal of an invalid WICKED_GARDEN_ROOT, the venv preference, uv only with a
lockfile and only with UV_PROJECT_ENVIRONMENT OUTSIDE the root (the launcher never creates
``<root>/.venv``), the python3 fallback, cwd preservation, the env handoff to the child,
``python -c`` / stdin pass-through, ``path``/``root``/``doctor`` output, twins present with
the executable bit, Windows path building via the exported pure functions, and the
``install.mjs`` bin delegating the launcher verbs.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LAUNCHER = REPO / "scripts" / "wicked-garden.mjs"
SH_TWIN = REPO / "scripts" / "wicked-garden"
CMD_TWIN = REPO / "scripts" / "wicked-garden.cmd"
INSTALL_MJS = REPO / "install.mjs"
NODE = shutil.which("node")
REAL_PYTHON = sys.executable

pytestmark = pytest.mark.skipif(NODE is None, reason="node not on PATH")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="sh shims / chmod / symlinks")

HELLO_PY = (
    "import json, os, sys\n"
    "print(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:], 'exe': sys.executable,\n"
    "  'WICKED_GARDEN_ROOT': os.environ.get('WICKED_GARDEN_ROOT'),\n"
    "  'CLAUDE_PLUGIN_ROOT': os.environ.get('CLAUDE_PLUGIN_ROOT')}))\n"
)
HELLO_MJS = (
    "console.log(JSON.stringify({cwd: process.cwd(), argv: process.argv.slice(2),\n"
    "  WICKED_GARDEN_ROOT: process.env.WICKED_GARDEN_ROOT}));\n"
)
HELLO_SH = '#!/bin/sh\nprintf \'%s\\n\' "sh-ok $WICKED_GARDEN_ROOT $1"\n'


def _executable(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def make_root(path: Path, *, name: str = "wicked-garden", version: str = "0.0.0-test",
              uv_lock: bool = False, venv: bool = False, venv_mark: Path | None = None) -> Path:
    (path / ".claude-plugin").mkdir(parents=True)
    (path / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
    (path / "scripts").mkdir()
    (path / "scripts" / "hello.py").write_text(HELLO_PY, encoding="utf-8")
    (path / "scripts" / "hello.mjs").write_text(HELLO_MJS, encoding="utf-8")
    _executable(path / "scripts" / "hello.sh", HELLO_SH)
    (path / "scripts" / "lib").mkdir()
    if uv_lock:
        (path / "uv.lock").write_text("# test lock\n", encoding="utf-8")
    if venv:
        (path / ".venv" / "bin").mkdir(parents=True)
        _executable(path / ".venv" / "bin" / "python3",
                    f'#!/bin/sh\nprintf \'%s\\n\' "$0" >> "{venv_mark}"\nexec "{REAL_PYTHON}" "$@"\n')
    return path


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.home.mkdir()
        self.bin = root / "bin"          # the ONLY PATH entry
        self.bin.mkdir()
        os.symlink(NODE, self.bin / "node")
        self.cache = root / "xdg-cache"
        self.py_mark = root / "python3.calls"
        self.uv_log = root / "uv.log"
        self.venv_mark = root / "venv.calls"

    def add_python3(self) -> None:
        _executable(self.bin / "python3",
                    f'#!/bin/sh\nprintf \'%s\\n\' "$0" >> "{self.py_mark}"\nexec "{REAL_PYTHON}" "$@"\n')

    def add_uv(self, exit_code: int = 0) -> None:
        _executable(self.bin / "uv",
                    "#!/bin/sh\n"
                    f'{{ printf \'ARGV:\'; for a in "$@"; do printf \' %s\' "$a"; done; printf \'\\n\';\n'
                    f'  printf \'UV_PROJECT_ENVIRONMENT=%s\\n\' "$UV_PROJECT_ENVIRONMENT"; }} >> "{self.uv_log}"\n'
                    f"exit {exit_code}\n")

    def env(self, **extra: str) -> dict[str, str]:
        base = {
            "PATH": str(self.bin),
            "HOME": str(self.home),
            "XDG_CACHE_HOME": str(self.cache),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        if os.environ.get("TMPDIR"):
            base["TMPDIR"] = os.environ["TMPDIR"]
        base.update(extra)
        return base

    def run(self, *args: str, script: Path = LAUNCHER, cwd: Path | None = None,
            stdin: str | None = None, **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [NODE, str(script), *args], env=self.env(**extra_env), cwd=cwd or self.root,
            input=stdin, capture_output=True, text=True, timeout=60,
        )


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _json_err(res: subprocess.CompletedProcess[str]) -> dict:
    line = res.stderr.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["ok"] is False
    return payload


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------

def test_wicked_garden_root_wins_over_claude_plugin_root(sandbox: Sandbox, tmp_path: Path) -> None:
    a = make_root(tmp_path / "a")
    b = make_root(tmp_path / "b")
    res = sandbox.run("root", WICKED_GARDEN_ROOT=str(a), CLAUDE_PLUGIN_ROOT=str(b))
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == a.resolve()


@pytest.mark.parametrize("bad", ["empty-dir", "other-plugin", ""])
def test_invalid_wicked_garden_root_refuses_loudly_and_never_falls_back(sandbox: Sandbox, tmp_path: Path, bad: str) -> None:
    if bad == "empty-dir":
        target = tmp_path / "empty"
        target.mkdir()
        value = str(target)
    elif bad == "other-plugin":
        value = str(make_root(tmp_path / "other", name="some-other-plugin"))
    else:
        value = ""
    good = make_root(tmp_path / "good")
    res = sandbox.run("root", WICKED_GARDEN_ROOT=value, CLAUDE_PLUGIN_ROOT=str(good))
    assert res.returncode == 2, (res.stdout, res.stderr)
    assert res.stdout == ""
    err = _json_err(res)
    assert "WICKED_GARDEN_ROOT" in err["reason"]
    assert err["tried"] and err["tried"][0]["source"] == "WICKED_GARDEN_ROOT"
    assert str(good) not in res.stdout


def test_claude_plugin_root_is_used_when_no_override(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "plugin")
    res = sandbox.run("root", CLAUDE_PLUGIN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == root.resolve()


def test_foreign_claude_plugin_root_is_skipped_not_fatal(sandbox: Sandbox, tmp_path: Path) -> None:
    other = make_root(tmp_path / "other", name="some-other-plugin")
    sandbox.add_python3()
    res = sandbox.run("doctor", CLAUDE_PLUGIN_ROOT=str(other))
    report = json.loads(res.stdout)
    assert Path(report["root"]).resolve() == REPO.resolve()
    assert report["root_source"] == "package"
    assert any(t.get("source") == "CLAUDE_PLUGIN_ROOT" for t in report["tried"])


def test_package_root_is_the_launchers_own_plugin(sandbox: Sandbox) -> None:
    res = sandbox.run("root")
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == REPO.resolve()


def test_copied_launcher_with_wicked_garden_root_resolves_the_snapshot(sandbox: Sandbox, tmp_path: Path) -> None:
    """The crew case: the .mjs sits somewhere else, WICKED_GARDEN_ROOT names the snapshot."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    copied = elsewhere / "wicked-garden.mjs"
    shutil.copy(LAUNCHER, copied)
    snap = make_root(tmp_path / "snapshot", version="12.99.0-snap", venv=True, venv_mark=sandbox.venv_mark)
    res = sandbox.run("doctor", script=copied, WICKED_GARDEN_ROOT=str(snap))
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["ok"] is True
    assert report["root_source"] == "WICKED_GARDEN_ROOT"
    assert Path(report["root"]).resolve() == snap.resolve()
    assert report["version"] == "12.99.0-snap"
    assert report["python"]["kind"] == "venv"
    assert Path(report["launcher"]).resolve() == copied.resolve()


# ---------------------------------------------------------------------------
# Interpreter ladder
# ---------------------------------------------------------------------------

@posix_only
def test_run_prefers_the_roots_venv_python(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root", venv=True, venv_mark=sandbox.venv_mark)
    sandbox.add_python3()
    res = sandbox.run("run", "scripts/hello.py", "x", "y", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["argv"] == ["x", "y"]
    assert sandbox.venv_mark.exists(), "the .venv python was not used"
    assert not sandbox.py_mark.exists(), "PATH python3 was used although a .venv exists"


@posix_only
def test_run_uses_uv_with_env_outside_root_and_never_creates_root_venv(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root", uv_lock=True)
    root.chmod(root.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)  # read-only like a snapshot
    try:
        sandbox.add_uv()
        sandbox.add_python3()
        res = sandbox.run("run", "scripts/hello.py", WICKED_GARDEN_ROOT=str(root))
        assert res.returncode == 0, res.stderr
        log = sandbox.uv_log.read_text(encoding="utf-8")
        assert f"ARGV: run --project {root} --frozen --no-dev python {root / 'scripts' / 'hello.py'}" in log
        env_line = [l for l in log.splitlines() if l.startswith("UV_PROJECT_ENVIRONMENT=")][0]
        project_env = Path(env_line.split("=", 1)[1])
        assert project_env.is_absolute()
        assert not str(project_env).startswith(str(root)), "uv env must never live under the root"
        assert str(project_env).startswith(str(sandbox.cache / "wicked-garden" / "venvs"))
        assert not (root / ".venv").exists()
        assert not sandbox.py_mark.exists(), "python3 must not be used when uv can serve the root"
    finally:
        root.chmod(root.stat().st_mode | stat.S_IWUSR)


@posix_only
def test_uv_is_skipped_without_a_lockfile_and_python3_serves(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")  # no uv.lock, no .venv
    sandbox.add_uv(exit_code=99)          # would fail loudly if called
    sandbox.add_python3()
    res = sandbox.run("run", "scripts/hello.py", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert sandbox.py_mark.exists()
    assert not sandbox.uv_log.exists()
    assert not (root / ".venv").exists()
    doc = json.loads(sandbox.run("doctor", WICKED_GARDEN_ROOT=str(root)).stdout)
    assert doc["python"]["kind"] == "python3"
    assert any(t.get("kind") == "uv" and "uv.lock" in t.get("reason", "") for t in doc["tried"])


def test_no_python_anywhere_is_one_json_error(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run("run", "scripts/hello.py", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 1
    err = _json_err(res)
    assert "Python 3 not found" in err["reason"]
    assert any(t.get("kind") == "python3" for t in err["tried"])
    doc = sandbox.run("doctor", WICKED_GARDEN_ROOT=str(root))
    assert doc.returncode == 1
    assert json.loads(doc.stdout)["ok"] is False


# ---------------------------------------------------------------------------
# run / python / path semantics
# ---------------------------------------------------------------------------

@posix_only
def test_run_keeps_the_callers_cwd_and_hands_both_root_vars_to_the_child(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    sandbox.add_python3()
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    res = sandbox.run("run", "scripts/hello.py", cwd=worktree, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert Path(out["cwd"]).resolve() == worktree.resolve()
    assert Path(out["WICKED_GARDEN_ROOT"]).resolve() == root.resolve()
    assert Path(out["CLAUDE_PLUGIN_ROOT"]).resolve() == root.resolve()


def test_run_dispatches_node_targets_with_the_running_node(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run("run", "scripts/hello.mjs", "--flag", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["argv"] == ["--flag"]
    assert Path(out["WICKED_GARDEN_ROOT"]).resolve() == root.resolve()


@posix_only
def test_run_dispatches_sh_targets(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run("run", "scripts/hello.sh", "arg1", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == f"sh-ok {root} arg1"


@posix_only
def test_python_verb_passes_dash_c_and_stdin_through(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    sandbox.add_python3()
    res = sandbox.run("python", "-c", "import os; print(os.environ['WICKED_GARDEN_ROOT'])", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == root.resolve()
    res = sandbox.run("python", "-", "a", "b", stdin="import sys; print('stdin', sys.argv[1:])", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "stdin ['a', 'b']"


@posix_only
def test_python_verb_forces_python_for_a_root_relative_file(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    sandbox.add_python3()
    res = sandbox.run("python", "scripts/hello.py", "z", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["argv"] == ["z"]


def test_path_prints_the_absolute_path_and_missing_targets_error(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run("path", "scripts/lib", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()) == (root / "scripts" / "lib").resolve()
    res = sandbox.run("path", "scripts/nope", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 1
    err = _json_err(res)
    assert "not found under the plugin root" in err["reason"]
    assert err["tried"][0]["path"].endswith("scripts/nope")


@pytest.mark.parametrize("rel", ["/etc/passwd", "../outside.py", "scripts/../../x.py"])
def test_run_rejects_absolute_and_escaping_paths(sandbox: Sandbox, tmp_path: Path, rel: str) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run("run", rel, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 2, (res.stdout, res.stderr)
    _json_err(res)


def test_run_rejects_unknown_extensions_and_missing_files(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    (root / "scripts" / "data.json").write_text("{}", encoding="utf-8")
    res = sandbox.run("run", "scripts/data.json", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 2
    assert "unsupported extension" in _json_err(res)["reason"]
    res = sandbox.run("run", "scripts/missing.py", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 1
    assert "not found under the plugin root" in _json_err(res)["reason"]


@pytest.mark.parametrize("argv", [["bogus"], ["run"], ["path"], ["python"], []])
def test_usage_errors_exit_2(sandbox: Sandbox, tmp_path: Path, argv: list[str]) -> None:
    root = make_root(tmp_path / "root")
    res = sandbox.run(*argv, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 2, (argv, res.stdout, res.stderr)


def test_help_and_version(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root", version="1.2.3")
    res = sandbox.run("--help", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0 and "wicked-garden run" in res.stdout
    res = sandbox.run("--version", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0 and res.stdout.strip() == "1.2.3"


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

@posix_only
def test_doctor_reports_root_source_python_and_tried(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root", version="9.9.9")
    sandbox.add_python3()
    res = sandbox.run("doctor", WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["ok"] is True
    assert report["version"] == "9.9.9"
    assert Path(report["root"]).resolve() == root.resolve()
    assert report["root_source"] == "WICKED_GARDEN_ROOT"
    assert report["venv"] is False
    assert report["uv"] is None
    assert report["python"]["kind"] == "python3"
    assert report["python"]["version"].startswith("Python 3")
    assert report["node"].startswith("v")
    assert isinstance(report["tried"], list) and any(t.get("kind") == "venv" for t in report["tried"])


# ---------------------------------------------------------------------------
# Twins, Windows path building, bin delegation
# ---------------------------------------------------------------------------

def test_twins_are_present_and_the_posix_one_is_executable() -> None:
    assert SH_TWIN.is_file() and CMD_TWIN.is_file() and LAUNCHER.is_file()
    if sys.platform != "win32":
        assert SH_TWIN.stat().st_mode & stat.S_IXUSR, "scripts/wicked-garden must be executable (git mode 100755)"
    sh = SH_TWIN.read_text(encoding="utf-8")
    assert sh.startswith("#!/bin/sh\n")
    assert 'exec node "$dir/wicked-garden.mjs" "$@"' in sh
    assert "dirname" not in sh, "the twin must not depend on coreutils (a seat PATH may carry only node)"
    cmd = CMD_TWIN.read_bytes()
    assert b"%~dp0wicked-garden.mjs" in cmd
    assert b"\r\n" in cmd, "the .cmd twin must keep CRLF line endings (see .gitattributes)"
    assert (REPO / ".gitattributes").read_text(encoding="utf-8").find("*.cmd text eol=crlf") >= 0


@posix_only
def test_sh_twin_delegates_to_the_mjs(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    res = subprocess.run(["/bin/sh", str(SH_TWIN), "root"], env=sandbox.env(WICKED_GARDEN_ROOT=str(root)),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == root.resolve()


def test_windows_path_building_via_pure_functions(sandbox: Sandbox) -> None:
    script = (
        "import(process.env.LAUNCHER_URL).then(m => {"
        " const out = {"
        "  venv: m.venvPythonCandidates('C:\\\\snap\\\\000002', 'win32'),"
        "  venvPosix: m.venvPythonCandidates('/snap/000002', 'linux'),"
        "  cache: m.cacheDir({LOCALAPPDATA: 'C:\\\\Users\\\\x\\\\AppData\\\\Local'}, 'win32', 'C:\\\\Users\\\\x'),"
        "  cacheDefault: m.cacheDir({}, 'win32', 'C:\\\\Users\\\\x'),"
        "  cacheXdg: m.cacheDir({XDG_CACHE_HOME: '/xdg'}, 'linux', '/home/x'),"
        "  uvEnv: m.uvProjectEnvironment('C:\\\\snap\\\\000002', 'C:\\\\Users\\\\x\\\\AppData\\\\Local\\\\wicked-garden\\\\cache', 'win32'),"
        "  kinds: ['scripts\\\\x.py', 'scripts/x.mjs', 'a.js', 'b.cjs', 'c.sh', 'd.json'].map(m.interpreterKindFor),"
        "  shimOnly: m.findOnPath('python', {PATH: 'C:\\\\py'}, 'win32', {existsSync: p => p === 'C:\\\\py\\\\python.bat', statSync: () => ({isFile: () => true})}),"
        "  shimSkipped: m.skippedShimsOnPath('python', {PATH: 'C:\\\\py'}, 'win32', {existsSync: p => p === 'C:\\\\py\\\\python.bat', statSync: () => ({isFile: () => true})}),"
        "  exe: m.findOnPath('python', {PATH: 'C:\\\\py'}, 'win32', {existsSync: p => p === 'C:\\\\py\\\\python.exe', statSync: () => ({isFile: () => true})}),"
        "  posix: m.findOnPath('python3', {PATH: '/usr/bin'}, 'linux', {existsSync: p => p === '/usr/bin/python3', statSync: () => ({isFile: () => true})}),"
        "  posixNoShimScan: m.skippedShimsOnPath('python', {PATH: '/usr/bin'}, 'linux', {existsSync: () => true, statSync: () => ({isFile: () => true})}),"
        " };"
        " console.log(JSON.stringify(out)); })"
    )
    res = subprocess.run([NODE, "-e", script], env=sandbox.env(LAUNCHER_URL=LAUNCHER.resolve().as_uri()),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["venv"] == ["C:\\snap\\000002\\.venv\\Scripts\\python.exe"]
    assert out["venvPosix"] == ["/snap/000002/.venv/bin/python3", "/snap/000002/.venv/bin/python"]
    assert out["cache"] == "C:\\Users\\x\\AppData\\Local\\wicked-garden\\cache"
    assert out["cacheDefault"] == "C:\\Users\\x\\AppData\\Local\\wicked-garden\\cache"
    assert out["cacheXdg"] == "/xdg/wicked-garden"
    assert out["uvEnv"].startswith("C:\\Users\\x\\AppData\\Local\\wicked-garden\\cache\\venvs\\")
    assert not out["uvEnv"].startswith("C:\\snap")
    assert out["kinds"] == ["python", "node", "node", "node", "sh", None]
    # .cmd/.bat shims cannot be spawned shell-less on Node >= 20 (CVE-2024-27980) and running
    # them through cmd.exe would build a command line from PATH-derived values — so on Windows
    # only real .exe files qualify; the skipped shim is reported (doctor's `tried`), never run.
    assert out["shimOnly"] is None
    assert out["shimSkipped"] == ["C:\\py\\python.bat"]
    assert out["exe"] == "C:\\py\\python.exe"
    assert out["posix"] == "/usr/bin/python3"
    assert out["posixNoShimScan"] == []


@posix_only
def test_sh_twin_works_through_a_symlink(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root")
    bindir = tmp_path / "userbin"
    bindir.mkdir()
    link = bindir / "wicked-garden"
    link.symlink_to(SH_TWIN)
    sandbox.bin.joinpath("readlink").symlink_to(shutil.which("readlink"))
    res = subprocess.run([str(link), "root"], env=sandbox.env(WICKED_GARDEN_ROOT=str(root)),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == root.resolve()
    # without readlink on PATH the twin degrades to $0 (documented) — but never to a raw stack trace
    sandbox.bin.joinpath("readlink").unlink()
    res = subprocess.run([str(link), "root"], env=sandbox.env(WICKED_GARDEN_ROOT=str(root)),
                         capture_output=True, text=True, timeout=60)
    assert res.returncode != 0


def test_install_mjs_bin_delegates_the_launcher_verbs(sandbox: Sandbox, tmp_path: Path) -> None:
    root = make_root(tmp_path / "root", version="7.7.7")
    res = sandbox.run("root", script=INSTALL_MJS, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).resolve() == root.resolve()
    res = sandbox.run("path", "scripts/lib", script=INSTALL_MJS, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 0 and Path(res.stdout.strip()) == (root / "scripts" / "lib").resolve()
    res = sandbox.run("doctor", script=INSTALL_MJS, WICKED_GARDEN_ROOT=str(root))
    assert json.loads(res.stdout)["version"] == "7.7.7"
    # install-only flags never apply to launcher verbs — usage error, nothing runs
    res = sandbox.run("--dry-run", "doctor", script=INSTALL_MJS, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 2 and "applies to install/update/status only" in res.stderr
    # the launcher's own flags pass through untouched (unknown → the launcher's exit 2)
    res = sandbox.run("run", "--weird", script=INSTALL_MJS, WICKED_GARDEN_ROOT=str(root))
    assert res.returncode == 2
    assert json.loads(res.stderr.strip().splitlines()[-1])["ok"] is False
