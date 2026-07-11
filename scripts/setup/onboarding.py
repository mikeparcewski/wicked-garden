#!/usr/bin/env python3
"""onboarding.py — onboarding-gate state mutations for the wicked-garden-core setup action.

Section 6 of the setup action flips a handful of SessionState fields
once onboarding finishes (or is skipped). The mutation was inlined in
markdown; this module wraps it so the command body stays slim and the
fields stay in one place.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT))


_VALID_MODES = ("full", "quick", "skip")


def clear_gate(mode: str, complete: bool) -> dict:
    """Update SessionState onboarding fields and return the post-update dict.

    ``mode`` is one of ``full``, ``quick``, ``skip``. ``complete`` is True
    for full / quick paths and False for skip.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
    from _session import SessionState  # type: ignore

    state = SessionState.load()
    state.update(
        needs_onboarding=False,
        setup_in_progress=False,
        setup_confirmed=True,
        onboarding_mode=mode,
        onboarding_complete=bool(complete),
    )
    return {
        "needs_onboarding": False,
        "setup_in_progress": False,
        "setup_confirmed": True,
        "onboarding_mode": mode,
        "onboarding_complete": bool(complete),
    }


def mark_setup_complete() -> dict:
    """Section 4 helper: write setup_complete + setup_confirmed to SessionState."""
    from _session import SessionState  # type: ignore

    state = SessionState.load()
    state.update(setup_complete=True, setup_confirmed=True)
    return {"setup_complete": True, "setup_confirmed": True}


def write_local_config() -> dict:
    """Write the default local-mode config.json. Idempotent — overwrites."""
    config_dir = Path.home() / ".something-wicked" / "wicked-garden"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {"mode": "local", "setup_complete": True}
    (config_dir / "config.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return {"path": str(config_dir / "config.json"), "config": payload}


def save_domain_pref(selection: str) -> dict:
    """Persist the chosen issue tracker to config.json domain_prefs.delivery."""
    config_path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = {}
    config.setdefault("domain_prefs", {})["delivery"] = selection
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return {"path": str(config_path), "selection": selection}


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    gate = sub.add_parser("clear-gate", help="Clear onboarding gate after onboarding")
    gate.add_argument("--mode", required=True, choices=_VALID_MODES)
    gate.add_argument("--complete", action="store_true")
    sub.add_parser("mark-setup-complete", help="Set setup_complete + setup_confirmed in SessionState")
    sub.add_parser("write-local-config", help="Write the default local-mode config.json")
    pref = sub.add_parser("save-domain-pref", help="Persist chosen issue tracker")
    pref.add_argument("selection", help="github | linear | jira | ado | rally | local")
    args = parser.parse_args()
    if args.cmd == "clear-gate":
        result = clear_gate(args.mode, args.complete)
    elif args.cmd == "mark-setup-complete":
        result = mark_setup_complete()
    elif args.cmd == "write-local-config":
        result = write_local_config()
    elif args.cmd == "save-domain-pref":
        result = save_domain_pref(args.selection)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
