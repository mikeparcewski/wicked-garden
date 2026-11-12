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


def offline_pytest_seed(dest: Path) -> Path:
    """The shipped pytest seed with its install step swapped for the environment's pytest.

    The seed must keep installing pytest for the repos it ships to; a test must not reach the network,
    so it rehearses this copy, whose install gate only checks that pytest imports.
    """
    guide = json.loads((SEEDS / "pytest-short-summary.json").read_text(encoding="utf-8"))
    install = next(c for c in guide["checks"] if c["name"] == "install")
    install["run"] = ["python3", "-c", "import pytest"]
    path = dest / "pytest-short-summary-offline.json"
    path.write_text(json.dumps(guide), encoding="utf-8")
    return path


def pytest_older_than(major: int) -> bool:
    import pytest

    return pytest.version_tuple[0] < major
