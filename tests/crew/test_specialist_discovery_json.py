"""tests/crew/test_specialist_discovery_json.py — issue #561 regression.

Covers the --json contract: stdout is exactly one parseable JSON object and
logging never leaks onto it, even when callers merge streams (`2>&1`).

Rules:
  T1: deterministic — subprocess invocation with fixed env
  T3: isolated — no external dependencies
  T4: single behavior per test
  T5: descriptive names
  T6: docstrings cite the tracking issue
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "crew" / "specialist_discovery.py"


def _run_json(merge_stderr: bool):
    """Invoke specialist_discovery.py --json and return (stdout, stderr, rc)."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
        text=True,
        env=env,
    )
    stderr = "" if merge_stderr else (proc.stderr or "")
    return proc.stdout, stderr, proc.returncode


def test_json_stdout_parses_cleanly():
    """Issue #561: --json must yield exactly one parseable JSON object on stdout."""
    stdout, _, rc = _run_json(merge_stderr=False)
    assert rc == 0, f"non-zero exit: {rc}"
    data = json.loads(stdout)
    assert isinstance(data, dict), "root must be an object"
    assert data, "expected at least one specialist in the built-in manifest"


def test_json_stdout_first_byte_is_brace():
    """Issue #561: no log prefix may precede the JSON payload on stdout."""
    stdout, _, rc = _run_json(merge_stderr=False)
    assert rc == 0
    assert stdout.lstrip().startswith("{"), (
        f"expected stdout to begin with '{{' — got: {stdout[:120]!r}"
    )


def test_json_survives_stderr_merge():
    """Issue #561: merging stderr into stdout must still yield parseable JSON.

    This guards the common subprocess pattern where callers use `2>&1` or
    subprocess.STDOUT. In --json mode logging level is raised to WARNING, so
    no INFO chatter should appear on either stream under normal operation.
    """
    merged, _, rc = _run_json(merge_stderr=True)
    assert rc == 0
    assert merged.lstrip().startswith("{"), (
        f"merged stream must start with '{{' — got: {merged[:200]!r}"
    )
    json.loads(merged)  # raises on failure
