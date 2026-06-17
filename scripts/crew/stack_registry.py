#!/usr/bin/env python3
"""stack_registry.py — legacy-stack-class -> dispatch reader for `modernize`.

The §B11/G2 seam: `.claude-plugin/stack-registry.json` is the machine-readable
dispatch truth (stack -> {blueprint, fixes, transform, validate, status}); this
module is the thin reader the `modernize` archetype's `discover` phase consults.

The load-bearing honesty contract (garden ETHOS — "never invent a pass"):
on an UNKNOWN stack, or a stack whose ``status`` is ``planned``/``none``, the
reader does NOT fabricate a transform. It returns a **capability-gap task** dict
(for the caller to hand to ``TaskCreate``) and fires a ``wicked.modernize.stack_gap``
bus event (fire-and-forget, fail-open). Only ``status: wired`` returns a runnable
dispatch. This mirrors the loom gate's fail-closed posture in dispatch data.

Pure resolution; the only I/O is reading the catalog + a fire-and-forget bus emit.

Usage (library):
    from stack_registry import resolve_dispatch
    r = resolve_dispatch("node-legacy-to-modern")
    # r["status"] == "wired"  -> r["dispatch"] = {blueprint, transform, validate}
    # else                    -> r["gap_task"] = {title, body, ...}, dispatch is None

Usage (CLI):
    sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \\
      "${CLAUDE_PLUGIN_ROOT}/scripts/crew/stack_registry.py" \\
      resolve --stack node-legacy-to-modern
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_THIS_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parents[1]
_REGISTRY_PATH = _PLUGIN_ROOT / ".claude-plugin" / "stack-registry.json"

# The ONLY status that returns a runnable dispatch. Everything else —
# `planned`, `none`, a typo, or any novel/unknown status — fails closed to a
# capability-gap (the load-bearing honesty contract: dispatch is wired-only).
_WIRED = "wired"


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the stack-registry catalog dict. Raises FileNotFoundError when
    the registry isn't present — callers must not silently fall back."""
    return json.loads((path or _REGISTRY_PATH).read_text(encoding="utf-8"))


def _gap_task(stack_id: str, label: str, status: str, reason: str) -> Dict[str, Any]:
    """Build a capability-gap task dict for the caller to hand to TaskCreate.
    This is what we emit INSTEAD of a fabricated migration."""
    return {
        "title": f"modernize: capability gap for stack '{stack_id}' (status={status})",
        "body": (
            f"{reason}\n\n"
            f"The `modernize` archetype refuses to fabricate a transform for a "
            f"stack it cannot actually handle. Wire a transform + validate for "
            f"'{label}' in .claude-plugin/stack-registry.json (flip status to "
            f"'wired'), or route this work to a stack that is already wired."
        ),
        "stack": stack_id,
        "status": status,
        "kind": "capability-gap",
    }


def resolve_dispatch(
    stack_id: str,
    *,
    registry: Optional[Dict[str, Any]] = None,
    emit: bool = True,
) -> Dict[str, Any]:
    """Resolve a legacy stack class to a dispatch decision.

    Returns a dict ``{stack, status, dispatch, gap_task}`` where exactly one of
    ``dispatch`` / ``gap_task`` is non-None:
      - status == "wired"           -> dispatch = {blueprint, fixes, transform, validate}
      - anything else (unknown /
        planned / none / a typo /
        any novel status)           -> gap_task = {...}, dispatch = None, and a
        ``wicked.modernize.stack_gap`` event is emitted (when ``emit``).

    Dispatch is strictly **wired-only**: a stack whose status is anything other
    than ``wired`` — including an unrecognised/misspelled status — fails closed
    to a capability-gap rather than fabricating a migration.
    """
    reg = registry if registry is not None else load_registry()
    stacks = reg.get("stacks", {})
    entry = stacks.get(stack_id)

    if entry is None:
        gap = _gap_task(stack_id, stack_id, "unknown",
                        f"Stack '{stack_id}' is not in the registry.")
        _emit_gap(gap, emit)
        return {"stack": stack_id, "status": "unknown", "dispatch": None, "gap_task": gap}

    status = entry.get("status") or "none"
    if status != _WIRED:
        # Fail closed: planned/none AND any unknown/typo'd status land here.
        gap = _gap_task(stack_id, entry.get("label", stack_id), status,
                        f"Stack '{stack_id}' is registered as status={status} "
                        f"(only status='{_WIRED}' returns a runnable dispatch).")
        _emit_gap(gap, emit)
        return {"stack": stack_id, "status": status, "dispatch": None, "gap_task": gap}

    # status == "wired": return the runnable dispatch. `or default` (not
    # .get(k, default)) so an explicit JSON null coalesces to the empty
    # container instead of crashing list(None) / passing None downstream.
    return {
        "stack": stack_id,
        "status": status,
        "dispatch": {
            "blueprint": entry.get("blueprint"),
            "fixes": list(entry.get("fixes") or []),
            "transform": entry.get("transform") or {},
            "validate": entry.get("validate") or {},
        },
        "gap_task": None,
    }


def _emit_gap(gap_task: Dict[str, Any], emit: bool) -> None:
    """Fire the stack-gap bus event. Fire-and-forget, fail-open — bus absent
    must never block the dispatch decision (the gap_task is the source of truth)."""
    if not emit:
        return
    try:
        scripts_dir = str(_THIS_DIR.parent)  # scripts/ for _bus
        if scripts_dir not in sys.path:      # guard: don't accumulate dups
            sys.path.insert(0, scripts_dir)
        from _bus import emit_event  # type: ignore
        emit_event(
            "wicked.modernize.stack_gap",
            {"stack": gap_task["stack"], "status": gap_task["status"],
             "title": gap_task["title"]},
            chain_id=f"modernize.{gap_task['stack']}.{gap_task['status']}.gap",
        )
    except Exception:
        pass  # bus is optional infrastructure


def list_stacks(registry: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Return [{id, label, status}, ...] for roadmap display."""
    reg = registry if registry is not None else load_registry()
    return [
        {"id": sid, "label": s.get("label", sid), "status": s.get("status", "none")}
        for sid, s in reg.get("stacks", {}).items()
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="modernize stack-registry dispatch reader (fail-closed)."
    )
    sub = parser.add_subparsers(dest="action", required=True)

    resolve = sub.add_parser("resolve", help="Resolve a stack to a dispatch decision.")
    resolve.add_argument("--stack", required=True)
    resolve.add_argument("--no-emit", action="store_true",
                         help="Do not emit the stack-gap bus event (testing/dry-run).")

    sub.add_parser("list", help="List registered stacks + statuses (roadmap).")

    args = parser.parse_args()

    if args.action == "resolve":
        result = resolve_dispatch(args.stack, emit=not args.no_emit)
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        # Exit 0 when wired (dispatch ready); exit 3 on a gap (fail-closed,
        # matching prove.py's "backend down / no-pass" convention).
        sys.exit(0 if result["dispatch"] is not None else 3)

    if args.action == "list":
        json.dump(list_stacks(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return


if __name__ == "__main__":
    _cli()
