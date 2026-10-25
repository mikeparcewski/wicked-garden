"""Paths and the script runner shared by the build-guide tests (imported by name, like tests/mcp's daemon_fixture)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SCRIPTS = REPO / "scripts" / "build_guide"
FIXTURES = HERE / "fixtures"
CAPTURED = HERE / "captured"
GUIDES = HERE / "guides"
SEEDS = REPO / "skills" / "build-guide" / "assets" / "seeds"


def run_script(name: str, *args: str, env: dict | None = None, timeout: int = 120) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), *args], capture_output=True,
                          text=True, env=env, timeout=timeout)
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = {"_stdout": proc.stdout, "_stderr": proc.stderr}
    return proc.returncode, payload
