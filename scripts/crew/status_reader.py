"""Status reader — reads from daemon HTTP if WG_DAEMON_ENABLED, else direct file read.

Single migration site for crew project status queries (v8 PR-1, #589).
Locked decision #3: ONE migration point; consumers call read_project_status()
rather than hitting the daemon directly or reading files.

Default: WG_DAEMON_ENABLED=false — full parity with v7 behaviour (0 regressions).
Set WG_DAEMON_ENABLED=true  to route reads through the daemon (port 4244).
Set WG_DAEMON_ENABLED=always to fail hard if the daemon is unreachable.

TODO(v8-pr2): Wire commands/crew/status.md and other callers to import and call
read_project_status() instead of invoking phase_manager.py directly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_project_status(project_id: str) -> dict:
    """Return project status dict for *project_id*.

    Routing:
      WG_DAEMON_ENABLED=false  (default) — direct subprocess call to phase_manager.py
      WG_DAEMON_ENABLED=true            — try daemon HTTP; fall back to direct on failure
      WG_DAEMON_ENABLED=always          — daemon HTTP; raise on failure (no fallback)
    """
    mode = os.environ.get("WG_DAEMON_ENABLED", "false").lower()
    if mode in ("true", "always"):
        try:
            import urllib.request
            host = os.environ.get("WG_DAEMON_HOST", "127.0.0.1")
            port = int(os.environ.get("WG_DAEMON_PORT", "4244"))
            url = f"http://{host}:{port}/projects/{project_id}"
            with urllib.request.urlopen(url, timeout=2) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if mode == "always":
                raise
            # fall through to direct read

    return _direct_file_read(project_id)


# ---------------------------------------------------------------------------
# Direct read (v7-compatible path, no daemon dependency)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PHASE_MANAGER = _SCRIPTS_DIR / "phase_manager.py"
_PYTHON_SH = _SCRIPTS_DIR.parent / "_python.sh"


def _direct_file_read(project_id: str) -> dict:
    """Call phase_manager.py {project_id} status --json and return parsed dict.

    This is the v7-compatible direct read path used when WG_DAEMON_ENABLED is
    false (the default).  It delegates to the same subprocess that
    commands/crew/status.md currently calls, preserving full parity.

    TODO(v8-pr2): Replace with a pure Python import of phase_manager once the
    daemon becomes the authoritative store and the subprocess round-trip is removed.
    """
    python_sh = str(_PYTHON_SH)
    if not os.path.exists(python_sh):
        # Fallback: use python3 directly when the shim is absent (test environments).
        python_sh = sys.executable

    cmd = [
        python_sh,
        str(_PHASE_MANAGER),
        project_id,
        "status",
        "--json",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {
                "error": f"phase_manager exited {result.returncode}",
                "stderr": result.stderr.strip(),
            }
        raw = result.stdout.strip()
        if not raw:
            return {"error": "phase_manager returned empty output"}
        return json.loads(raw)
    except subprocess.TimeoutExpired:
        return {"error": "phase_manager timed out"}
    except (FileNotFoundError, OSError) as exc:
        return {"error": f"phase_manager not found: {exc}"}
    except json.JSONDecodeError as exc:
        return {"error": f"phase_manager output is not valid JSON: {exc}"}
