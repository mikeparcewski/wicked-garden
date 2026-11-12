"""Record and refuse accidental network installs during default pytest sessions.

The shims inherit into subprocesses, including tests of command-line entry points.
They deliberately guard package-manager entry points, not arbitrary network I/O.
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
NPM_NETWORK = {
    "install", "i", "in", "ins", "inst", "insta", "instal", "isnt", "isntall",
    "add", "ci", "clean-install", "update", "up", "upgrade", "exec", "x", "create", "view",
}


def without_shims(env, directory=None):
    shim = directory if directory is not None else env.get(SHIM_ENV)
    shim = Path(shim).resolve() if shim is not None else None
    return os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep) if Path(p).resolve() != shim
    )


def _command(argv, value_options=()):
    """Return the subcommand and remaining arguments, skipping global options."""
    args = iter(argv)
    for arg in args:
        if arg == "--":
            return next(args, ""), list(args)
        if arg in value_options:
            next(args, None)
        elif not arg.startswith("-"):
            return arg, list(args)
    return "", []


def is_network_install(cmd, argv, path):
    if cmd == "npm":
        subcommand, rest = _command(argv, {
            "--prefix", "--registry", "--cache", "--userconfig", "--workspace", "-w",
            "-C", "--loglevel", "--location", "--tag", "--access", "--scope", "--otp",
        })
        if "--offline" in argv or "--offline=true" in argv:
            return False
        if subcommand == "init":
            package, _ = _command(rest, {"--scope", "--workspace", "-w"})
            return bool(package)
        return subcommand in NPM_NETWORK
    if cmd in {"pip", "pip3"}:
        subcommand, _ = _command(argv, {"--python", "--proxy", "--timeout", "--retries", "--cache-dir", "--log"})
        return subcommand in {"install", "download", "wheel"}
    # npx options precede the command; options after it belong to the command.
    command = ""
    args = iter(argv)
    for arg in args:
        if arg in {"-p", "--package"} or arg.startswith(("--package=", "-p=")) or (arg.startswith("-p") and len(arg) > 2):
            return True
        if arg in {"-c", "--call"} or arg.startswith("--call="):
            call = arg.partition("=")[2] if "=" in arg else next(args, "")
            try:
                words = shlex.split(call)
            except ValueError:
                return True
            command = words[0] if words else ""
            # Continue to catch a --package following -c.
        elif arg == "--":
            command = next(args, "")
            break
        elif not arg.startswith("-"):
            command = arg
            break
    if not command:  # npx --version / --help do not fetch a package
        return False
    local = Path.cwd() / "node_modules" / ".bin" / command
    return not (shutil.which(command, path=path) or (local.is_file() and os.access(local, os.X_OK)))


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
    os.execv(binary, [binary, *argv])


def guard_environment(directory, env):
    """Create independent shims/recording for a session (or a shim unit test)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    source = f"#!{sys.executable}\n" + Path(__file__).read_text(encoding="utf-8")
    for cmd in ("npm", "npx", "pip", "pip3"):
        shim = directory / cmd
        shim.write_text(source, encoding="utf-8")
        shim.chmod(0o755)
    record = directory / "calls.jsonl"
    record.touch()
    return {**env, "PATH": str(directory) + os.pathsep + without_shims(env),
            SHIM_ENV: str(directory), RECORD_ENV: str(record)}


def pytest_configure(config):
    if os.name == "nt" or os.environ.get("WICKED_GARDEN_E2E_NPM") == "1":
        return
    directory = tempfile.mkdtemp(prefix="garden-install-guard-")
    config._install_guard = (directory, {key: os.environ.get(key) for key in ("PATH", SHIM_ENV, RECORD_ENV)})
    os.environ.update(guard_environment(directory, os.environ))


def pytest_sessionfinish(session, exitstatus):
    state = getattr(session.config, "_install_guard", None)
    if state is None:
        return
    directory, original = state
    try:
        lines = (Path(directory) / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if lines:
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
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(shim_main())
