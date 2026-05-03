#!/usr/bin/env python3
"""Lightweight gate-policy.json reader for scripts that cannot import phase_manager.

``phase_manager.py`` owns the authoritative ``_load_gate_policy()`` with a
process-lifetime cache.  This module provides a minimal, uncached reader for
scripts (tests, CLI utilities, hook helpers) that need the policy without
pulling in phase_manager's full dependency surface.

Stdlib only — no DomainStore, no _session, no external deps.

Exported functions
------------------
load_gate_policy(policy_path=None) -> dict
    Load and return the full gate-policy.json dict.  Raises FileNotFoundError
    when the file is absent; raises json.JSONDecodeError when malformed.

load_bus_health(policy_path=None) -> dict
    Return the ``bus_health`` block from gate-policy.json, or a dict of safe
    defaults when the block is absent.  Never raises.

    Returns::

        {
            "emit_success_threshold": float,   # default 0.999
            "min_n_for_assertion": int,        # default 500
        }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _default_policy_path() -> Path:
    """Resolve the canonical gate-policy.json path relative to this file.

    This file lives at ``scripts/crew/_gate_policy.py``.  The plugin root is
    three directories up (scripts/crew/ → scripts/ → repo root) and
    gate-policy.json lives at ``.claude-plugin/gate-policy.json``.
    """
    return Path(__file__).resolve().parents[2] / ".claude-plugin" / "gate-policy.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_gate_policy(
    policy_path: Optional["Path | str"] = None,
) -> Dict[str, Any]:
    """Load gate-policy.json and return the full dict.

    Args:
        policy_path: Optional override path.  When None, resolves via
            ``_default_policy_path()``.

    Raises:
        FileNotFoundError: when the file does not exist.
        json.JSONDecodeError: when the file is malformed JSON.
    """
    path = Path(policy_path) if policy_path is not None else _default_policy_path()
    return json.loads(path.read_text(encoding="utf-8"))


def load_bus_health(
    policy_path: Optional["Path | str"] = None,
) -> Dict[str, Any]:
    """Return the ``bus_health`` block from gate-policy.json.

    Fails open — when the file is missing, malformed, or the block is absent,
    returns defaults so callers (tests, health checks) continue to function
    without crashing.

    Default values mirror the gate-policy.json v1.1.0 entry:
        emit_success_threshold: 0.999
        min_n_for_assertion:    500

    Args:
        policy_path: Optional override path for testing.

    Returns:
        dict with ``emit_success_threshold`` (float) and
        ``min_n_for_assertion`` (int).
    """
    _DEFAULTS: Dict[str, Any] = {
        "emit_success_threshold": 0.999,
        "min_n_for_assertion": 500,
    }
    try:
        policy = load_gate_policy(policy_path)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)

    bus_health = policy.get("bus_health")
    if not isinstance(bus_health, dict):
        return dict(_DEFAULTS)

    result = dict(_DEFAULTS)
    try:
        result["emit_success_threshold"] = float(
            bus_health.get("emit_success_threshold", _DEFAULTS["emit_success_threshold"])
        )
    except (TypeError, ValueError):
        pass  # keep default

    try:
        result["min_n_for_assertion"] = int(
            bus_health.get("min_n_for_assertion", _DEFAULTS["min_n_for_assertion"])
        )
    except (TypeError, ValueError):
        pass  # keep default

    return result
