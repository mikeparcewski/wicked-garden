"""Record and refuse accidental network installs during default pytest sessions.

POSIX PATH shims allow only short read-only/local forms of npm, npx, pip and
pip3, recording and refusing everything else. They inherit into subprocesses;
nested pytest sessions share the record. Disabled on Windows and when
WICKED_GARDEN_E2E_NPM=1. This catches accidental installs, not adversarial use:
python -m pip, uv, direct HTTP and other entry points are out of scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

RECORD_ENV = "WICKED_GARDEN_INSTALL_GUARD_RECORD"
SHIM_ENV = "WICKED_GARDEN_INSTALL_GUARD_SHIMS"
REPORT = "Network install guard violations"
NPM_ALLOWED = {
    "run", "run-script", "test", "config", "prefix", "root", "ls",
    "list", "help", "version", "explain", "why",
}
PIP_ALLOWED = {"show", "list", "freeze", "help", "check", "config", "inspect", "debug"}


def without_shims(env, directory=None):
    shim = directory if directory is not None else env.get(SHIM_ENV)
    shim = Path(shim).resolve() if shim is not None else None
    return os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if Path(p).resolve() != shim
    )


def is_network_install(cmd, argv, path):
    """Refuse anything outside the allow-list; do not parse global options."""
    if not argv:
        return True
    if cmd == "npm":
        return not (
            (len(argv) == 1 and argv[0] in {"--version", "-v", "-h", "--help"})
            or argv[0] in NPM_ALLOWED
            or (argv[0] == "pack" and all(arg.startswith("-") for arg in argv[1:]))
        )
    if cmd in {"pip", "pip3"}:
        return not (
            (len(argv) == 1 and argv[0] in {"--version", "-V", "-h", "--help"})
            or argv[0] in PIP_ALLOWED
        )
    if cmd != "npx":
        return True
    if len(argv) == 1 and argv[0] in {"--version", "-v", "--help"}:
        return False
    args = argv[1:] if argv[0] in {"--yes", "-y", "--no"} else argv
    if not args or args[0].startswith("-") or "/" in args[0]:
        return True
    binary = shutil.which("npx", path=path)
    locations = [Path.cwd() / "node_modules" / ".bin"]
    if binary:
        # Use the PATH entry's directory, not the npm package's symlink target.
        locations.append(Path(binary).parent)
    return not any(
        (directory / args[0]).is_file() and os.access(directory / args[0], os.X_OK)
        for directory in locations
    )


def shim_main():
    cmd = Path(sys.argv[0]).name
    argv = sys.argv[1:]
    directory = Path(__file__).resolve().parent
    path = without_shims(os.environ, directory)
    if is_network_install(cmd, argv, path):
        entry = {"cmd": cmd, "argv": argv, "test": os.environ.get("PYTEST_CURRENT_TEST", ""), "cwd": os.getcwd()}
        with (directory / "calls.jsonl").open("a", encoding="utf-8") as record:
            record.write(json.dumps(entry) + "\n")
        print(f"Network install guard blocked: {cmd} {shlex.join(argv)}", file=sys.stderr)
        return 1
    binary = shutil.which(cmd, path=path)
    if not binary:
        print(f"Network install guard: no real {cmd} on PATH", file=sys.stderr)
        return 127
    # Resolve by the cleaned PATH, but keep shims visible to descendant commands.
    env = dict(os.environ)
    if cmd in {"npm", "npx"}:
        env["npm_config_offline"] = "true"
    os.execve(binary, [binary, *argv], env)


def guard_environment(directory, env):
    """Create independent shims/recording for a session (or a shim unit test)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source = f"#!{sys.executable}\n" + Path(__file__).read_text(encoding="utf-8")
    path = without_shims(env)
    for cmd in ("npm", "npx", "pip", "pip3"):
        if shutil.which(cmd, path=path) is None:
            continue
        shim = directory / cmd
        shim.write_text(source, encoding="utf-8")
        shim.chmod(0o755)
    record = directory / "calls.jsonl"
    record.touch()
    return {**env, "PATH": str(directory) + os.pathsep + path,
            SHIM_ENV: str(directory), RECORD_ENV: str(record)}


def pytest_configure(config):
    if os.name == "nt" or os.environ.get("WICKED_GARDEN_E2E_NPM") == "1":
        return
    original = {key: os.environ.get(key) for key in ("PATH", SHIM_ENV, RECORD_ENV)}
    inherited = os.environ.get(SHIM_ENV)
    shared = (inherited is not None and Path(inherited).is_dir()
              and without_shims(os.environ) != os.environ.get("PATH", ""))
    directory = inherited if shared else tempfile.mkdtemp(prefix="garden-install-guard-")
    if not shared:
        os.environ.update(guard_environment(directory, os.environ))
    offset = (Path(directory) / "calls.jsonl").stat().st_size
    parent_record = Path(original[RECORD_ENV]) if original[RECORD_ENV] else None
    if (shared or parent_record is None or not parent_record.is_file()
            or parent_record.resolve() == (Path(directory) / "calls.jsonl").resolve()):
        parent_record = None
    config._install_guard = (directory, original, offset, not shared, parent_record)


def pytest_sessionfinish(session, exitstatus):
    state = getattr(session.config, "_install_guard", None)
    if state is None:
        return
    directory, original, offset, owner, parent_record = state
    try:
        with (Path(directory) / "calls.jsonl").open("rb") as record:
            record.seek(offset)
            lines = record.read().decode("utf-8").splitlines()
        if lines:
            if parent_record is not None:
                with parent_record.open("a", encoding="utf-8") as record:
                    record.write("\n".join(lines) + "\n")
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            write = reporter.write_line if reporter else print
            write("")
            write(REPORT)
            for line in lines:
                entry = json.loads(line)
                write(f"  {entry['cmd']} {shlex.join(entry['argv'])} | {entry['test']}")
            session.exitstatus = 1
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if owner:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(shim_main())
