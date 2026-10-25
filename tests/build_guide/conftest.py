"""Shared fixtures for the build-guide skill tests (skills/build-guide, scripts/build_guide).

The fixture repos under fixtures/ are test SUBJECTS, not garden tests: pytest-repo carries a
real pytest suite and must never be collected by the garden run.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

collect_ignore_glob = ["fixtures/*"]

from bg_helpers import FIXTURES  # noqa: E402


@pytest.fixture
def python3_on_path(tmp_path: Path) -> dict:
    """An environment whose ``python3`` is this interpreter (the guides run ``python3 …``)."""
    if sys.platform == "win32":
        pytest.skip("the python3 shim is a POSIX script")
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim = shim_dir / "python3"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return {**os.environ, "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"}


@pytest.fixture
def fixture_copy(tmp_path: Path):
    """Copy a fixture repo into tmp_path, so a test can change it without touching the original."""

    def _copy(name: str) -> Path:
        dest = tmp_path / name
        shutil.copytree(FIXTURES / name, dest)
        return dest

    return _copy
