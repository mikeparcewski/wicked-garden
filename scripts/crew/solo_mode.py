"""Solo-mode HITL dispatch — inline human review for crew workflow gates.

Issue #651.

When a project is started with ``--hitl=inline`` (or ``--solo-mode``), every
gate that would normally be dispatched to a council or sequential/parallel
specialist is instead presented to the user inline.  The user types a verdict;
this module writes a ``gate-result.json`` + ``inline-review-context.md`` and
(for CONDITIONAL verdicts) a ``conditions-manifest.json``.

Public API
----------
``is_solo_mode(state)``
    Return True when the project has solo-mode enabled.

``load_global_config()``
    Load ``~/.wicked-brain/config/crew-defaults.json`` and return the dict
    (or ``{}`` on any error).  Used to honour ``default_hitl_mode: inline``.

``resolve_solo_mode(state, flag)``
    Precedence: explicit flag > project state extras > global config > False.

``reject_full_rigor_solo(state)``
    Raise ``SoloModeUnavailableError`` when the project is at full rigor.

``dispatch_human_inline(state, phase, gate_name, gate_policy_entry, ...)``
    Present the inline gate UI, parse the response, and return a merged
    gate_result dict with the same shape as the other dispatch helpers.

Constants
---------
``REVIEWER_NAME``   = ``"human-inline"``
``DISPATCH_MODE``   = ``"human-inline"``

Stdlib-only.  No I/O side effects until dispatch_human_inline() is called.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants  (R3: no magic values)
# ---------------------------------------------------------------------------

REVIEWER_NAME: str = "human-inline"
DISPATCH_MODE: str = "human-inline"

# Scores by verdict (R3)
_APPROVE_SCORE: float = 1.0
_CONDITIONAL_SCORE: float = 0.7
_REJECT_SCORE: float = 0.0

# Re-prompt limit: ask for clarification at most once before giving up
_MAX_REPROMPTS: int = 1

# Headless-fallback env var: if set to "true" the session is treated as
# non-interactive and falls back to council dispatch.
_ENV_HEADLESS: str = "WG_HEADLESS"

# Global config path (R3)
_GLOBAL_CONFIG_PATH: Path = (
    Path.home() / ".wicked-brain" / "config" / "crew-defaults.json"
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SoloModeUnavailableError(ValueError):
    """Raised when solo-mode is requested but cannot run (e.g. full rigor)."""


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_global_config() -> Dict[str, Any]:
    """Load ``~/.wicked-brain/config/crew-defaults.json``.

    Returns an empty dict on any error (file absent, malformed JSON,
    permission denied).  Never raises.
    """
    try:
        raw = _GLOBAL_CONFIG_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return {}


def is_solo_mode(state: Any) -> bool:
    """Return True when the project has solo_mode: true in state.extras."""
    extras = getattr(state, "extras", None) or {}
    return bool(extras.get("solo_mode"))


def resolve_solo_mode(state: Any, flag: Optional[str]) -> bool:
    """Resolve effective solo-mode.

    Precedence (highest → lowest):
      1. Explicit ``--hitl=inline`` / ``--solo-mode`` flag  (flag == "inline")
      2. Project-state extras ``solo_mode: true``
      3. Global config ``default_hitl_mode: inline``
      4. Default: False

    Args:
        state:  ProjectState (may be None).
        flag:   Parsed ``--hitl`` value (e.g. ``"inline"``) or None.

    Returns:
        True when any precedence level requests inline HITL.
    """
    # 1. Explicit flag
    if flag and flag.lower() == "inline":
        return True

    # 2. Project state extras
    extras = getattr(state, "extras", None) or {}
    if extras.get("solo_mode"):
        return True

    # 3. Global config
    cfg = load_global_config()
    if cfg.get("default_hitl_mode", "").lower() == "inline":
        return True

    return False


def reject_full_rigor_solo(state: Any) -> None:
    """Raise SoloModeUnavailableError when state is at full rigor.

    Solo-mode is not permitted at full rigor — the council pattern is mandatory
    there.  Callers should check before setting solo_mode: true in extras.
    """
    extras = getattr(state, "extras", None) or {}
    rigor = (extras.get("rigor_tier") or "standard").lower()
    if rigor == "full":
        raise SoloModeUnavailableError(
            "Solo-mode is not available at full rigor. "
            "Use `/wicked-garden:crew:gate` to dispatch council review."
        )


# ---------------------------------------------------------------------------
# Headless detection
# ---------------------------------------------------------------------------


def _is_interactive() -> bool:
    """Return True when the session appears interactive (stdin is a TTY).

    Checks ``WG_HEADLESS=true`` first, then falls back to ``sys.stdin.isatty()``.
    Fail-open: if stdin check raises, assume non-interactive.
    """
    if os.environ.get(_ENV_HEADLESS, "").strip().lower() in ("1", "true", "yes"):
        return False
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Evidence summary builder
# ---------------------------------------------------------------------------


def _build_evidence_summary(
    gate_name: str,
    phase: str,
    gate_policy_entry: Dict[str, Any],
    state: Any,
) -> List[str]:
    """Return a 3-5 bullet evidence summary for the inline gate UI.

    Derives bullets from available project context — gate name, phase,
    min_score, evidence_required.  Does not read files (fast path).
    """
    bullets: List[str] = []

    # Bullet 1: gate identity
    bullets.append(f"Gate '{gate_name}' at phase '{phase}'")

    # Bullet 2: score threshold
    min_score = gate_policy_entry.get("min_score")
    if min_score is not None:
        bullets.append(f"Minimum passing score: {min_score}")

    # Bullet 3: evidence_required keys (if present)
    evidence_required = gate_policy_entry.get("evidence_required") or []
    if isinstance(evidence_required, list) and evidence_required:
        bullets.append(
            "Evidence required: " + ", ".join(str(e) for e in evidence_required[:5])
        )

    # Bullet 4: reviewers that would normally run
    reviewers = list(gate_policy_entry.get("reviewers") or [])
    if reviewers:
        bullets.append(
            "Normal reviewers (replaced by inline): " + ", ".join(reviewers[:3])
            + (" ..." if len(reviewers) > 3 else "")
        )

    # Bullet 5: rigor tier from state
    extras = getattr(state, "extras", None) or {}
    rigor = extras.get("rigor_tier")
    if rigor:
        bullets.append(f"Rigor tier: {rigor}")

    return bullets[:5]  # cap at 5


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_human_response(raw: str) -> Optional[Dict[str, Any]]:
    """Parse a raw user response into a verdict dict.

    Accepted forms:
      - ``APPROVE``                            → score 1.0, no conditions
      - ``CONDITIONAL: <text>``                → score 0.7, conditions text
      - ``REJECT: <reason>``                   → score 0.0, reason set

    Case-insensitive on the keyword prefix.  Returns None on unrecognised
    input so the caller can re-prompt.
    """
    stripped = raw.strip()
    upper = stripped.upper()

    if upper.startswith("APPROVE"):
        return {
            "verdict": "APPROVE",
            "score": _APPROVE_SCORE,
            "reason": "Human reviewer: APPROVE",
            "conditions": [],
        }

    if upper.startswith("CONDITIONAL"):
        # Extract text after the colon (may be empty)
        colon_idx = stripped.find(":")
        text = stripped[colon_idx + 1:].strip() if colon_idx >= 0 else ""
        return {
            "verdict": "CONDITIONAL",
            "score": _CONDITIONAL_SCORE,
            "reason": f"Human reviewer: CONDITIONAL — {text}" if text else
                      "Human reviewer: CONDITIONAL",
            "conditions_text": text,
            "conditions": [],
        }

    if upper.startswith("REJECT"):
        colon_idx = stripped.find(":")
        reason_text = stripped[colon_idx + 1:].strip() if colon_idx >= 0 else ""
        return {
            "verdict": "REJECT",
            "score": _REJECT_SCORE,
            "reason": f"Human reviewer: REJECT — {reason_text}" if reason_text else
                      "Human reviewer: REJECT",
            "conditions": [],
        }

    return None


# ---------------------------------------------------------------------------
# Conditions-manifest writer
# ---------------------------------------------------------------------------


def _write_conditions_manifest(
    project_dir: Path,
    phase: str,
    conditions_text: str,
    gate_name: str,
) -> Optional[Path]:
    """Write a conditions-manifest.json for a CONDITIONAL inline verdict.

    The user's raw text is written as a single unstructured condition
    (id=C-inline-1).  AC-4.4 auto-resolution in the next phase will
    surface and structure it.

    Returns the manifest path on success, None on failure.
    """
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = phase_dir / "conditions-manifest.json"

    manifest = {
        "phase": phase,
        "gate": gate_name,
        "source": DISPATCH_MODE,
        "created_at": _utc_now(),
        "conditions": [
            {
                "id": "C-inline-1",
                "description": conditions_text or "(no conditions text provided)",
                "status": "pending",
                "source": "human-inline-review",
            }
        ],
    }

    try:
        # Atomic write: write to .tmp then rename
        tmp_path = manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        tmp_path.replace(manifest_path)
        return manifest_path
    except OSError as exc:
        sys.stderr.write(
            f"[solo-mode] conditions-manifest write failed "
            f"(phase={phase}, gate={gate_name}): {exc}\n"
        )
        return None


# ---------------------------------------------------------------------------
# Inline-review-context writer
# ---------------------------------------------------------------------------


def _write_inline_review_context(
    project_dir: Path,
    phase: str,
    gate_name: str,
    bullets: List[str],
    raw_response: str,
    gate_result_ref: str,
) -> Optional[Path]:
    """Write ``inline-review-context.md`` alongside gate-result.json.

    Contains: evidence summary, user's raw response, timestamp, gate-result ref.
    """
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    ctx_path = phase_dir / "inline-review-context.md"

    lines = [
        f"# Inline Gate Review: {gate_name} ({phase})",
        "",
        f"**Timestamp**: {_utc_now()}",
        f"**Gate**: {gate_name}",
        f"**Phase**: {phase}",
        "",
        "## Evidence Summary",
        "",
    ]
    for b in bullets:
        lines.append(f"- {b}")
    lines += [
        "",
        "## User Response",
        "",
        f"> {raw_response.strip()}",
        "",
        "## Artifact Reference",
        "",
        f"Gate result: `{gate_result_ref}`",
        "",
    ]

    try:
        ctx_path.write_text("\n".join(lines), encoding="utf-8")
        return ctx_path
    except OSError as exc:
        sys.stderr.write(
            f"[solo-mode] inline-review-context write failed "
            f"(phase={phase}, gate={gate_name}): {exc}\n"
        )
        return None


# ---------------------------------------------------------------------------
# Gate-result writer
# ---------------------------------------------------------------------------


def _write_gate_result(
    project_dir: Path,
    phase: str,
    gate_name: str,
    verdict_dict: Dict[str, Any],
    context_ref: Optional[str],
) -> Optional[Path]:
    """Write gate-result.json to phases/{phase}/.

    Returns the path on success, None on failure (fail-open).
    """
    phase_dir = project_dir / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    gr_path = phase_dir / "gate-result.json"

    payload: Dict[str, Any] = {
        "verdict": verdict_dict["verdict"],
        "result": verdict_dict["verdict"],
        "reviewer": REVIEWER_NAME,
        "recorded_at": _utc_now(),
        "score": verdict_dict["score"],
        "reason": verdict_dict.get("reason", ""),
        "phase": phase,
        "gate": gate_name,
        "conditions": verdict_dict.get("conditions") or [],
        "dispatch_mode": DISPATCH_MODE,
        "mode": DISPATCH_MODE,
    }
    if context_ref:
        payload["context_ref"] = context_ref

    try:
        tmp_path = gr_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        tmp_path.replace(gr_path)
        return gr_path
    except OSError as exc:
        sys.stderr.write(
            f"[solo-mode] gate-result write failed "
            f"(phase={phase}, gate={gate_name}): {exc}\n"
        )
        return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Main dispatch function
# ---------------------------------------------------------------------------


def dispatch_human_inline(
    state: Any,
    phase: str,
    gate_name: str,
    gate_policy_entry: Dict[str, Any],
    *,
    _input_fn=None,
    _print_fn=None,
) -> Dict[str, Any]:
    """Inline HITL gate dispatch (#651).

    Presents a formatted gate review prompt to the user, parses the response,
    writes gate artifacts, and returns a merged gate_result dict with the same
    shape as other ``_dispatch_*`` helpers.

    Args:
        state:              ProjectState for context (may be None).
        phase:              Phase being reviewed.
        gate_name:          Gate being reviewed.
        gate_policy_entry:  The rigor-tier block from gate-policy.json.
        _input_fn:          Callable() -> str for reading input (injectable
                            for tests; default: ``builtins.input``).
        _print_fn:          Callable(str) -> None for output (injectable for
                            tests; default: ``builtins.print``).

    Headless fallback:
        When ``_is_interactive()`` returns False, returns a CONDITIONAL stub
        with ``mode_fallback_reason: "no-interactive-session"`` and does NOT
        write any artifacts.

    Returns:
        Gate result dict with keys: verdict, score, reason, conditions,
        per_reviewer_verdicts, dispatch_mode, reviewer.
    """
    _print = _print_fn if _print_fn is not None else print
    _input = _input_fn if _input_fn is not None else input

    # -----------------------------------------------------------------------
    # Headless fallback (R2: no silent failures)
    # -----------------------------------------------------------------------
    if not _is_interactive():
        sys.stderr.write(
            f"[solo-mode] non-interactive session detected — falling back to "
            f"council for gate={gate_name!r} phase={phase!r}. "
            "Set WG_HEADLESS=false or run in an interactive terminal to use "
            "inline HITL.\n"
        )
        return _headless_fallback_stub(gate_name, phase)

    # -----------------------------------------------------------------------
    # Resolve project_dir for artifact writes
    # -----------------------------------------------------------------------
    project_dir: Optional[Path] = None
    if state is not None and getattr(state, "name", None):
        try:
            # Lazy import to avoid circular dependencies
            from phase_manager import get_project_dir  # type: ignore
            project_dir = get_project_dir(state.name)
        except Exception as exc:
            sys.stderr.write(
                f"[solo-mode] project_dir unresolvable (name={getattr(state, 'name', '?')!r}): {exc}\n"
            )

    # -----------------------------------------------------------------------
    # Pre-register dispatch-log entry BEFORE presenting the UI (#AC-7)
    # -----------------------------------------------------------------------
    if project_dir is not None:
        try:
            from dispatch_log import append as _dl_append  # type: ignore
            from phase_manager import get_utc_timestamp  # type: ignore
            _dl_append(
                project_dir, phase,
                reviewer=REVIEWER_NAME,
                gate=gate_name,
                dispatch_id=f"{phase}:{gate_name}:{REVIEWER_NAME}:{get_utc_timestamp()}",
                dispatcher_agent="wicked-garden:crew:phase-manager:human-inline",
                expected_result_path="gate-result.json",
            )
        except Exception as exc:
            sys.stderr.write(
                f"[solo-mode] dispatch-log pre-register failed "
                f"(phase={phase}, gate={gate_name}): {exc}\n"
            )

    # -----------------------------------------------------------------------
    # Build evidence summary + present UI
    # -----------------------------------------------------------------------
    bullets = _build_evidence_summary(gate_name, phase, gate_policy_entry, state)

    _print("\n╔══════════════════════════════════════════════╗")
    _print(f"║ INLINE GATE REVIEW — phase: {phase:<16}║")
    _print("╚══════════════════════════════════════════════╝")
    _print("")
    _print("Evidence summary:")
    for b in bullets:
        _print(f"  • {b}")
    _print("")
    _print("Verdict? [APPROVE / CONDITIONAL: <conditions> / REJECT: <reason>]")

    # -----------------------------------------------------------------------
    # Read + parse user response (re-prompt once on ambiguous input)
    # -----------------------------------------------------------------------
    parsed: Optional[Dict[str, Any]] = None
    raw_response: str = ""

    for attempt in range(_MAX_REPROMPTS + 1):  # R5: bounded
        try:
            raw_response = _input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Non-interactive fallback
            sys.stderr.write(
                "[solo-mode] input interrupted — headless fallback engaged.\n"
            )
            return _headless_fallback_stub(gate_name, phase)

        parsed = _parse_human_response(raw_response)
        if parsed is not None:
            break

        # Ambiguous — re-prompt once
        if attempt < _MAX_REPROMPTS:
            _print(
                'Please respond with APPROVE, CONDITIONAL: <text>, or REJECT: <text>.'
            )
        else:
            # After max reprompts, fall back to CONDITIONAL to avoid blocking
            sys.stderr.write(
                "[solo-mode] ambiguous response after reprompt — defaulting to "
                f"CONDITIONAL for gate={gate_name!r} phase={phase!r}.\n"
            )
            parsed = {
                "verdict": "CONDITIONAL",
                "score": _CONDITIONAL_SCORE,
                "reason": "Human reviewer: ambiguous response — defaulted to CONDITIONAL",
                "conditions_text": f"Clarify gate verdict for {gate_name}",
                "conditions": [],
            }

    if parsed is None:
        # Should not be reachable, but satisfy type checker (R2)
        parsed = {
            "verdict": "CONDITIONAL",
            "score": _CONDITIONAL_SCORE,
            "reason": "Human reviewer: no response",
            "conditions": [],
        }

    # -----------------------------------------------------------------------
    # Write gate-result.json
    # -----------------------------------------------------------------------
    gate_result_ref = (
        str(project_dir / "phases" / phase / "gate-result.json")
        if project_dir else "gate-result.json"
    )
    if project_dir is not None:
        _write_gate_result(project_dir, phase, gate_name, parsed, context_ref=None)

    # -----------------------------------------------------------------------
    # Write inline-review-context.md
    # -----------------------------------------------------------------------
    if project_dir is not None:
        ctx_path = _write_inline_review_context(
            project_dir, phase, gate_name, bullets, raw_response, gate_result_ref
        )
        if ctx_path:
            # Back-patch context_ref into gate-result.json (best-effort)
            _write_gate_result(
                project_dir, phase, gate_name, parsed,
                context_ref=str(ctx_path),
            )

    # -----------------------------------------------------------------------
    # Write conditions-manifest.json for CONDITIONAL verdict
    # -----------------------------------------------------------------------
    conditions_manifest_path: Optional[Path] = None
    if parsed["verdict"] == "CONDITIONAL" and project_dir is not None:
        conditions_text = parsed.get("conditions_text", "")
        conditions_manifest_path = _write_conditions_manifest(
            project_dir, phase, conditions_text, gate_name
        )

    # -----------------------------------------------------------------------
    # Build merged result in the canonical gate_result shape
    # -----------------------------------------------------------------------
    per_reviewer = [
        {
            "reviewer": REVIEWER_NAME,
            "verdict": parsed["verdict"],
            "score": parsed["score"],
            "reason": parsed.get("reason", ""),
            "conditions": parsed.get("conditions") or [],
        }
    ]

    merged: Dict[str, Any] = {
        "verdict": parsed["verdict"],
        "result": parsed["verdict"],
        "score": parsed["score"],
        "min_score": gate_policy_entry.get("min_score", 0.0) or 0.0,
        "reviewer": REVIEWER_NAME,
        "reason": parsed.get("reason", ""),
        "conditions": parsed.get("conditions") or [],
        "phase": phase,
        "gate_name": gate_name,
        "per_reviewer_verdicts": per_reviewer,
        "reviewers_dispatched": [REVIEWER_NAME],
        "dispatch_mode": DISPATCH_MODE,
        "mode": DISPATCH_MODE,
        "external_review": False,
        "recorded_at": _utc_now(),
    }

    if conditions_manifest_path is not None:
        merged["conditions_manifest_path"] = str(conditions_manifest_path)

    return merged


# ---------------------------------------------------------------------------
# Headless fallback stub
# ---------------------------------------------------------------------------


def _headless_fallback_stub(gate_name: str, phase: str) -> Dict[str, Any]:
    """Return a CONDITIONAL stub with fallback metadata.

    The caller (phase_manager) should fall back to council dispatch when it
    sees ``mode_fallback_reason`` set.
    """
    return {
        "verdict": "CONDITIONAL",
        "result": "CONDITIONAL",
        "score": 0.0,
        "min_score": 0.0,
        "reviewer": REVIEWER_NAME,
        "reason": "solo-mode-headless-fallback: council dispatch required",
        "conditions": [],
        "phase": phase,
        "gate_name": gate_name,
        "per_reviewer_verdicts": [],
        "reviewers_dispatched": [],
        "dispatch_mode": DISPATCH_MODE,
        "mode": DISPATCH_MODE,
        "external_review": False,
        "mode_fallback_reason": "no-interactive-session",
    }


__all__ = [
    "DISPATCH_MODE",
    "REVIEWER_NAME",
    "SoloModeUnavailableError",
    "dispatch_human_inline",
    "is_solo_mode",
    "load_global_config",
    "reject_full_rigor_solo",
    "resolve_solo_mode",
]
