#!/usr/bin/env python3
"""
_wicked_testing_probe.py — wicked-testing version probe.

Checks that `wicked-testing` (npm) is installed and satisfies the semver
range pinned in .claude-plugin/plugin.json:wicked_testing_version.

Public API:
    probe(session_state) -> ProbeResult
    read_pin_from_plugin_json(plugin_json_path: str) -> str
    is_version_in_range(installed: str, pin: str) -> bool

Stdlib-only: no third-party imports (packaging, semver, etc.).

Escape hatch: WG_SKIP_WICKED_TESTING_CHECK=1 bypasses subprocess entirely and
returns status "ok". Documented in CONTRIBUTING.md. Do NOT use in production.

CH-02 hardening: the exception path in probe() logs actionable detail —
subprocess stderr, the exact command that was run, and timeout context — not
just the bare exception string. crew_command_gate() treats a missing probe key
as a failure (fail-closed), closing the fail-open gap at the crew layer.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    from typing import TypedDict

    class ProbeResult(TypedDict):
        status: str          # "ok" | "missing" | "out-of-range" | "error"
        version: Optional[str]
        pin: str
        error: Optional[str]

except ImportError:
    # Python 3.7 fallback — TypedDict not available as class syntax
    ProbeResult = dict  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
_PLUGIN_JSON_PATH = str(_PLUGIN_ROOT / ".claude-plugin" / "plugin.json")

# Subprocess command for the probe. Factored out so tests can assert it.
_PROBE_CMD = ["npx", "wicked-testing", "--version"]
_PROBE_TIMEOUT_S = 3


# ---------------------------------------------------------------------------
# Semver-lite caret-range parser (stdlib only, no packaging import)
# ---------------------------------------------------------------------------

def is_version_in_range(installed: str, pin: str) -> bool:
    """Evaluate a caret semver range.

    Supports caret range only: "^X.Y.Z" means:
      - X > 0:  >=X.Y.Z and <(X+1).0.0
      - X == 0: >=0.Y.Z and <0.(Y+1).0

    Prerelease tags (e.g. "0.1.1-beta.1") are rejected — strip the prerelease
    suffix from installed before the numeric comparison.

    Returns False for any malformed input.
    """
    if not pin.startswith("^"):
        return False

    pin_bare = pin[1:]  # strip "^"

    def _parse(v: str):
        """Parse "X.Y.Z" (possibly with prerelease tag) → (major, minor, patch) or None."""
        # Strip prerelease tag — "0.1.1-beta.1" → "0.1.1"
        numeric_part = v.split("-")[0]
        parts = numeric_part.split(".")
        if len(parts) != 3:
            return None
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return None

    inst_tuple = _parse(installed)
    pin_tuple = _parse(pin_bare)

    if inst_tuple is None or pin_tuple is None:
        return False

    inst_major, inst_minor, inst_patch = inst_tuple
    pin_major, pin_minor, pin_patch = pin_tuple

    # Reject prerelease tags (original installed string has "-")
    if "-" in installed.split("+")[0]:  # ignore build metadata "+" but reject "-"
        return False

    # Must be >= pin
    if inst_tuple < pin_tuple:
        return False

    # Upper bound: <(X+1).0.0 when X>0, or <0.(Y+1).0 when X==0
    if pin_major > 0:
        if inst_major >= pin_major + 1:
            return False
    else:
        # pin_major == 0 — locked to minor
        if inst_major != 0:
            return False
        if inst_minor >= pin_minor + 1:
            return False

    return True


# ---------------------------------------------------------------------------
# Read pin from plugin.json
# ---------------------------------------------------------------------------

def read_pin_from_plugin_json(plugin_json_path: str) -> str:
    """Read the wicked_testing_version field from plugin.json.

    Raises ValueError with an actionable message when:
    - The file does not exist or cannot be read.
    - The JSON is malformed.
    - The wicked_testing_version field is absent.
    - The field value is not a string.
    """
    path = Path(plugin_json_path)
    if not path.exists():
        raise ValueError(
            f"plugin.json not found at {plugin_json_path}. "
            "Ensure CLAUDE_PLUGIN_ROOT is set correctly."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"plugin.json unreadable ({plugin_json_path}): {e}") from e

    value = data.get("wicked_testing_version")
    if value is None:
        raise ValueError(
            f"plugin.json missing wicked_testing_version field ({plugin_json_path}). "
            "Add: \"wicked_testing_version\": \"^0.1.0\""
        )
    if not isinstance(value, str):
        raise ValueError(
            f"plugin.json wicked_testing_version must be a string, "
            f"got {type(value).__name__} ({plugin_json_path})"
        )
    return value


# ---------------------------------------------------------------------------
# Main probe
# ---------------------------------------------------------------------------

def probe(session_state=None) -> "ProbeResult":
    """Run the wicked-testing availability probe.

    1. Check WG_SKIP_WICKED_TESTING_CHECK escape hatch.
    2. Read version pin from plugin.json.
    3. Run `npx wicked-testing --version` with a 3s timeout.
    4. Compare version string against the caret pin.

    Returns a ProbeResult dict with keys:
        status:  "ok" | "missing" | "out-of-range" | "error"
        version: installed version string or None
        pin:     required range string (or "skipped")
        error:   error detail or None

    CH-02 hardening: exception paths log subprocess stderr + command + timeout
    context. The caller (_probe_wicked_testing in bootstrap.py) catches any
    exceptions that escape this function and fails-open. crew_command_gate()
    treats an absent probe key as a failure — fail-closed at the crew layer.
    """
    # 1. Escape hatch — for CI / offline dev without npm access.
    if os.environ.get("WG_SKIP_WICKED_TESTING_CHECK", "").strip() == "1":
        print(
            "[wicked-garden] WG_SKIP_WICKED_TESTING_CHECK is set — "
            "wicked-testing version check bypassed (offline dev mode). "
            "Do not use in production.",
            file=sys.stderr,
        )
        return {"status": "ok", "version": "skipped", "pin": "skipped", "error": None}

    # 2. Read the version pin.
    try:
        pin = read_pin_from_plugin_json(_PLUGIN_JSON_PATH)
    except ValueError as exc:
        return {
            "status": "error",
            "version": None,
            "pin": "unknown",
            "error": str(exc),
        }

    # 3. Run the probe subprocess.
    try:
        result = subprocess.run(
            _PROBE_CMD,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
        )
    except FileNotFoundError:
        # npx binary not found — Node.js is not installed.
        return {
            "status": "missing",
            "version": None,
            "pin": pin,
            "error": "npx not found — install Node.js",
        }
    except subprocess.TimeoutExpired as exc:
        # CH-02 hardening: include command + timeout context in the log line.
        cmd_str = " ".join(_PROBE_CMD)
        stderr_excerpt = ""
        if exc.stderr:
            raw = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
            stderr_excerpt = raw.strip()[:200]
        print(
            f"[wicked-garden] wicked-testing probe timeout: "
            f"command={cmd_str!r} timeout={_PROBE_TIMEOUT_S}s "
            f"stderr={stderr_excerpt!r}",
            file=sys.stderr,
        )
        return {
            "status": "error",
            "version": None,
            "pin": pin,
            "error": f"probe timeout ({_PROBE_TIMEOUT_S}s)",
        }
    except Exception as exc:
        # CH-02 hardening: include command context in the actionable log line.
        cmd_str = " ".join(_PROBE_CMD)
        print(
            f"[wicked-garden] wicked-testing probe exception: "
            f"command={cmd_str!r} error={exc!r}",
            file=sys.stderr,
        )
        return {
            "status": "error",
            "version": None,
            "pin": pin,
            "error": str(exc),
        }

    # 4. Non-zero exit → wicked-testing not installed (or broken install).
    if result.returncode != 0:
        stderr_excerpt = result.stderr.strip()[:200] if result.stderr else "non-zero exit"
        return {
            "status": "missing",
            "version": None,
            "pin": pin,
            "error": stderr_excerpt or "non-zero exit",
        }

    # 5. Parse and validate the version string.
    version = result.stdout.strip().lstrip("v")
    if not is_version_in_range(version, pin):
        return {
            "status": "out-of-range",
            "version": version,
            "pin": pin,
            "error": None,
        }

    return {"status": "ok", "version": version, "pin": pin, "error": None}
