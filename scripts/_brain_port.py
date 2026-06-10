"""
Resolve the wicked-brain server port dynamically, and auto-start the server.

The brain server binds 4242 only when free — it probes upward on
EADDRINUSE and writes the actual port back to _meta/config.json. With one
brain per project, non-default ports are the norm, so callers must use
resolve_port() rather than hardcoding a default.

Resolution order:
1. WICKED_BRAIN_PORT env var (explicit override)
2. Project brain config matching cwd (source_path match)
3. Per-project brain config by directory-name convention
   (~/.wicked-brain/projects/{cwd basename}/_meta/config.json) — mirrors
   wicked-brain-call's own brain resolution. Covers configs written before
   source_path persistence existed.
4. Root brain config (~/.wicked-brain/_meta/config.json)
5. Fallback: 4242

This module also owns ensure_server(): a lock-safe, fail-open auto-start
used by hooks. Server lifecycle is a deterministic operation — hooks must
perform it themselves, never delegate it to the model via a directive.
"""

import json
import os
from pathlib import Path

_DEFAULT_PORT = 4242


def resolve_port() -> int:
    """Return the brain server port for the current context."""
    # 1. Explicit env var override
    env_port = os.environ.get("WICKED_BRAIN_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass  # Invalid value — fall through to config discovery

    brain_root = Path.home() / ".wicked-brain"

    # 2. Project brain matching cwd
    projects_dir = brain_root / "projects"
    if projects_dir.is_dir():
        try:
            cwd = Path.cwd().resolve()
            for project_dir in projects_dir.iterdir():
                config_path = project_dir / "_meta" / "config.json"
                if config_path.is_file():
                    try:
                        with open(config_path) as f:
                            cfg = json.load(f)
                        source = cfg.get("source_path", "")
                        if source and cwd == Path(source).resolve():
                            return int(cfg.get("server_port", _DEFAULT_PORT))
                    except Exception:
                        pass  # fail open
        except Exception:
            pass  # fail open

    # 3. Per-project config by directory-name convention. wicked-brain-call
    #    resolves the brain as projects/{basename(cwd)}; configs that predate
    #    source_path persistence have no source_path field, so the scan above
    #    misses them and probes would fall through to 4242 while the server
    #    listens elsewhere.
    try:
        named_config = projects_dir / Path.cwd().resolve().name / "_meta" / "config.json"
        if named_config.is_file():
            with open(named_config) as f:
                cfg = json.load(f)
            return int(cfg.get("server_port", _DEFAULT_PORT))
    except Exception:
        pass  # fail open

    # 4. Root brain config
    root_config = brain_root / "_meta" / "config.json"
    if root_config.is_file():
        try:
            with open(root_config) as f:
                cfg = json.load(f)
            return int(cfg.get("server_port", _DEFAULT_PORT))
        except Exception:
            pass  # fail open

    # 5. Fallback
    return _DEFAULT_PORT


_AUTOSTART_ATTEMPTED = False


def _health_ok(timeout: float = 1.0) -> bool:
    """True if the brain server answers a health call on the resolved port."""
    try:
        import urllib.request

        payload = json.dumps({"action": "health", "params": {}}).encode("utf-8")
        req = urllib.request.Request(
            f"http://localhost:{resolve_port()}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosem: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL is localhost with int port from resolve_port()
            return json.loads(resp.read().decode("utf-8")).get("status") == "ok"
    except Exception:
        return False


def ensure_server(wait_secs: float = 3.0) -> bool:
    """Start the brain server if it is not answering. Returns reachability.

    Spawns `wicked-brain-call --start` detached — that CLI owns brain-path
    resolution, spawn locking (concurrent hooks cannot double-spawn), and
    crash logging to {brain}/_meta/server.log. One spawn attempt per
    process; later calls only re-probe. Never raises, never waits longer
    than wait_secs — hooks fail open.
    """
    global _AUTOSTART_ATTEMPTED
    if _health_ok():
        return True
    if _AUTOSTART_ATTEMPTED:
        return False
    _AUTOSTART_ATTEMPTED = True
    try:
        import shutil
        import subprocess
        import time

        exe = shutil.which("wicked-brain-call")
        if not exe:
            return False

        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([exe, "--start"], **kwargs)

        deadline = time.time() + wait_secs
        while time.time() < deadline:
            # Re-resolve every probe: the server may bind a different free
            # port and write it back to config mid-wait.
            if _health_ok():
                return True
            time.sleep(0.25)
        return False
    except Exception:
        return False  # fail open


if __name__ == "__main__":
    # CLI entrypoint so shell/markdown commands can resolve the port without
    # hardcoding it:  PORT=$(python3 scripts/_brain_port.py)
    print(resolve_port())
