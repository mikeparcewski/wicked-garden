"""Shared helpers for the E2E harness.

The key lesson these helpers encode: E2E tests must NOT assume the developer's
configured/onboarded machine. A fresh CI checkout has no
``~/.something-wicked/wicked-garden/config.json``, so prompt_submit's setup gate
hard-blocks (exit 2) — correct behavior, but it means a test asserting exit 0
fails in CI while passing locally. These helpers give each test an isolated,
explicitly-(un)configured HOME so it behaves identically everywhere.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def configured_home() -> tempfile.TemporaryDirectory:
    """A temp dir usable as $HOME with a minimal setup_complete config, so the
    prompt_submit setup gate proceeds (exit 0) rather than hard-blocking. Caller
    keeps the returned TemporaryDirectory alive for the subprocess lifetime and
    passes ``{"HOME": tmp.name}`` in the subprocess env."""
    tmp = tempfile.TemporaryDirectory()
    cfg = Path(tmp.name) / ".something-wicked" / "wicked-garden"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.json").write_text(
        json.dumps({"setup_complete": True, "storage_mode": "local"}),
        encoding="utf-8")
    return tmp


def unconfigured_home() -> tempfile.TemporaryDirectory:
    """A temp dir usable as $HOME with NO config — exercises the setup gate's
    hard-block (exit 2)."""
    return tempfile.TemporaryDirectory()


def has_python_traceback(stderr: str) -> bool:
    """True if stderr contains an uncaught Python traceback — the crash
    signature a fail-open / controlled-exit hook must never produce."""
    return "Traceback (most recent call last)" in (stderr or "")
