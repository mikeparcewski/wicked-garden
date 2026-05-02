#!/usr/bin/env python3
"""resolve.py — classify-don't-retry path for CONDITIONAL findings (#717).

Implements the reframed mechanism for issue #717: instead of bounded retries
that mutate gate verdicts, this module classifies each finding in
``conditions-manifest.json`` as ``mechanical | judgment | escalation`` and
exposes a ``resolve_phase`` API the ``crew:resolve`` skill calls.

The verdict on ``gate-result.json`` is NEVER mutated by this module. The
honest CONDITIONAL signal is preserved end-to-end. Resolution sidecars are
written via :func:`conditions_manifest.mark_resolved` which deliberately
does not flip ``verified=True`` — only ``crew:approve`` advances the phase.

Per-resolution audit: each accepted resolution emits
``wicked.gate.condition.resolved`` to wicked-bus. Bus emit failure is
fail-open (matches the file-wide convention) — never raises.

Stdlib-only.

Public API
----------
    load_rules(path=None)                              -> list[dict]
    classify_finding(finding, rules)                   -> dict
    resolve_phase(project_dir, phase, *, accept=False) -> dict

CLI
---
    python -m crew.resolve <project_dir> <phase> [--accept] [--cluster-id ID]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Make sibling modules importable when invoked as a script.
_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from crew import conditions_manifest as cm  # noqa: E402

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Default rules file. Project-overridable via .wicked-garden/finding-classification.json.
_DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude-plugin"
    / "finding-classification.json"
)

#: Project-local override path (relative to project_dir).
_PROJECT_RULES_RELPATH = ".wicked-garden/finding-classification.json"

#: Valid classification labels — order is significant, used as default.
VALID_CLASSIFICATIONS = ("mechanical", "judgment", "escalation")

#: When no rule matches, default to the most conservative bucket.
#: ``judgment`` requires a human read; never auto-classify as ``mechanical``.
DEFAULT_CLASSIFICATION = "judgment"

#: Rule applied when nothing matched — distinct sentinel for audit clarity.
NO_MATCH_RULE_ID = "no-rule-matched"


# ---------------------------------------------------------------------------
# Rule loading + classification
# ---------------------------------------------------------------------------

def load_rules(path: "str | Path | None" = None) -> list[dict]:
    """Load classification rules from disk and pre-compile their regexes.

    When ``path`` is given, that file is read verbatim. When ``path`` is
    ``None``, the default ``.claude-plugin/finding-classification.json``
    in the plugin root is used. The project-local override layering
    (``.wicked-garden/finding-classification.json`` taking precedence by
    rule id over plugin defaults) is applied separately by
    :func:`_load_rules_with_overrides`, which calls this function twice
    and merges.

    Each returned rule has an extra ``_compiled`` field — a list of
    pre-compiled ``re.Pattern`` objects (with ``re.IGNORECASE``).
    Patterns that fail to compile are dropped at load time with a
    stderr note, so :func:`classify_finding` can use them directly
    without per-classification try/except. Pre-compilation moves regex
    parsing out of the classification hot path AND surfaces malformed
    rules early; it also limits ReDoS exposure to load time, where a
    project-local override could otherwise inject untrusted regexes
    silently.

    Returns ``[]`` on missing file or malformed JSON. Callers MUST handle
    the empty case — falling back to ``DEFAULT_CLASSIFICATION`` for every
    finding is the safe behaviour.
    """
    target = Path(path) if path else _DEFAULT_RULES_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(raw, dict):
        return []
    rules = raw.get("rules") or []
    if not isinstance(rules, list):
        return []
    out: list[dict] = []
    for rule in rules:
        if not _is_well_formed_rule(rule):
            continue
        compiled: list[re.Pattern] = []
        for pat in rule["matches"]:
            try:
                compiled.append(re.compile(pat, re.IGNORECASE))
            except re.error as exc:
                sys.stderr.write(
                    f"[crew:resolve] dropped malformed regex in rule "
                    f"{rule.get('id')!r}: {pat!r} ({exc})\n"
                )
        if not compiled:
            # Every pattern in the rule was malformed — drop the rule.
            continue
        prepared = dict(rule)  # shallow copy; don't mutate caller-owned dicts
        prepared["_compiled"] = compiled
        out.append(prepared)
    return out


def _is_well_formed_rule(rule: Any) -> bool:
    if not isinstance(rule, dict):
        return False
    if not isinstance(rule.get("id"), str):
        return False
    if rule.get("classification") not in VALID_CLASSIFICATIONS:
        return False
    matches = rule.get("matches")
    if not isinstance(matches, list) or not matches:
        return False
    return all(isinstance(m, str) for m in matches)


def _load_rules_with_overrides(project_dir: Path) -> list[dict]:
    """Layer project-local rules on top of the plugin defaults.

    Project-local rules take precedence by ``id`` — a project rule with
    the same ``id`` as a default rule replaces the default. New project
    rule ids are appended.
    """
    defaults = load_rules()
    override_path = Path(project_dir) / _PROJECT_RULES_RELPATH
    overrides = load_rules(override_path) if override_path.is_file() else []
    if not overrides:
        return defaults
    by_id: dict[str, dict] = {r["id"]: r for r in defaults}
    for r in overrides:
        by_id[r["id"]] = r
    return list(by_id.values())


def classify_finding(finding: Any, rules: Iterable[dict]) -> dict:
    """Classify one finding by matching its descriptive text against ``rules``.

    Args:
        finding: A condition entry from ``conditions-manifest.json``. Reads
            the ``message``, ``description``, ``title``, and ``id`` fields
            (whichever are present) for matching. Strings are joined for the
            scan so a rule pattern can hit any of them.
        rules: Iterable of rule dicts from :func:`load_rules`.

    Returns:
        Dict with keys ``classification`` (one of
        :data:`VALID_CLASSIFICATIONS`) and ``applied_rule`` (rule id or
        :data:`NO_MATCH_RULE_ID`).

    Falls back to :data:`DEFAULT_CLASSIFICATION` (``judgment``) on no match
    so unknown findings always require a human read — never auto-classify
    as ``mechanical``.
    """
    haystack = _extract_match_text(finding)
    for rule in rules:
        # Prefer pre-compiled patterns from load_rules. Fall back to a
        # one-shot compile when callers hand-build rules (test fixtures,
        # ad-hoc programmatic use). Malformed patterns are skipped in
        # the fallback path to preserve the never-raise contract.
        compiled = rule.get("_compiled")
        if compiled is None:
            compiled = []
            for pat in rule.get("matches", []):
                try:
                    compiled.append(re.compile(pat, re.IGNORECASE))
                except re.error:
                    continue
        for pattern in compiled:
            if pattern.search(haystack):
                return {
                    "classification": rule["classification"],
                    "applied_rule": rule["id"],
                }
    return {
        "classification": DEFAULT_CLASSIFICATION,
        "applied_rule": NO_MATCH_RULE_ID,
    }


def _extract_match_text(finding: Any) -> str:
    if not isinstance(finding, dict):
        return str(finding)
    parts = []
    for key in ("message", "description", "title", "summary", "id"):
        value = finding.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# resolve_phase — the public API the crew:resolve skill calls
# ---------------------------------------------------------------------------

def resolve_phase(
    project_dir: "str | Path",
    phase: str,
    *,
    accept: bool = False,
    cluster_id: "str | None" = None,
) -> dict:
    """Drive a resolution pass over the conditions manifest for one phase.

    This function NEVER modifies ``gate-result.json``. It only:
      * Reads ``conditions-manifest.json``
      * Classifies each unverified condition
      * For ``mechanical`` clusters: surfaces the condition's classified
        details (id, applied rule, message). This module does NOT itself
        dispatch a specialist or generate a diff in this PR — that's the
        caller's job (the slash command can render the message and prompt
        the user). When ``accept=True``, the module ALSO writes a
        proposed-resolution sidecar via
        :func:`conditions_manifest.mark_resolved` and emits
        ``wicked.gate.condition.resolved`` so downstream consumers (the
        resume projector, telemetry) can record the resolution intent.
        Specialist re-dispatch is a follow-up; tracked in #717's reframe
        comment as the next step after this skill ships.
      * For ``escalation`` clusters: refuses with a structured pointer to
        the appropriate higher-rigor surface.
      * For ``judgment`` clusters: surfaces them in the result without
        attempting to dispatch. Human must decide.

    Args:
        project_dir: Project root (parent of ``phases/``).
        phase: Phase name (e.g. ``"design"``).
        accept: When False (default), produces a preview only — no
            sidecars written, no events emitted. When True, the user
            has explicitly opted in for THIS invocation; sidecars are
            written for every ``mechanical`` cluster we touch.
        cluster_id: When provided, restrict resolution to a single
            condition by id. Useful for ``--accept`` per-cluster review.

    Returns:
        Dict with shape::

            {
                "phase": str,
                "manifest_loaded": bool,
                "mechanical": [ {condition_id, applied_rule, message, ...} ],
                "judgment":   [ {condition_id, applied_rule, message, ...} ],
                "escalation": [ {condition_id, applied_rule, message,
                                  refused_with: str} ],
                "resolved":   [ {condition_id, sidecar_path, emit_status} ],
                "verdict_unchanged": True,  # explicit auditor assertion
            }
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / "phases" / phase / "conditions-manifest.json"
    result: dict[str, Any] = {
        "phase": phase,
        "manifest_loaded": False,
        "mechanical": [],
        "judgment": [],
        "escalation": [],
        "resolved": [],
        "verdict_unchanged": True,  # never flipped by this module
    }

    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return result
    result["manifest_loaded"] = True

    rules = _load_rules_with_overrides(project_dir)
    conditions = manifest.get("conditions") or []

    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        if condition.get("verified") is True:
            continue
        # Use ``id`` only — matches the conditions_manifest.py convention
        # (mark_cleared / _find_condition_index both look up by ``id``).
        # Falling back to ``condition_id`` would diverge from manifest
        # tooling and write sidecars no other helper can find.
        cid = condition.get("id")
        if not cid:
            continue
        if cluster_id and cid != cluster_id:
            continue

        classification_info = classify_finding(condition, rules)
        bucket = classification_info["classification"]
        applied_rule = classification_info["applied_rule"]

        entry = {
            "condition_id": cid,
            "applied_rule": applied_rule,
            "message": condition.get("message") or condition.get("description") or "",
        }

        if bucket == "escalation":
            entry["refused_with"] = (
                f"escalation finding (rule={applied_rule}); resolve refuses "
                f"to dispatch — surface to user via crew:swarm or council mode"
            )
            result["escalation"].append(entry)
            continue

        if bucket == "judgment":
            result["judgment"].append(entry)
            continue

        # mechanical — prepare for resolution
        result["mechanical"].append(entry)

        if accept:
            # Prefer the manifest's existing ``resolution`` key (the
            # convention used by mark_cleared/recover in conditions_manifest.py)
            # so a specialist-proposed resolution is captured first;
            # fall back to ``resolution_ref`` for any caller that still
            # uses that name; finally synthesize a placeholder.
            resolution_ref = (
                condition.get("resolution")
                or condition.get("resolution_ref")
                or f"crew:resolve/{cid}"
            )
            sidecar_path = cm.mark_resolved(
                project_dir,
                phase,
                cid,
                applied_rule=applied_rule,
                resolution_ref=resolution_ref,
                note=f"Resolved via crew:resolve (--accept) on rule {applied_rule}",
            )
            emit_status = _emit_resolved_event(
                project_id=project_dir.name,
                phase=phase,
                condition_id=cid,
                applied_rule=applied_rule,
            )
            result["resolved"].append({
                "condition_id": cid,
                "sidecar_path": str(sidecar_path),
                "emit_status": emit_status,
            })

    return result


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _read_manifest(manifest_path: Path) -> "dict | None":
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _emit_resolved_event(
    *,
    project_id: str,
    phase: str,
    condition_id: str,
    applied_rule: str,
) -> str:
    """Emit ``wicked.gate.condition.resolved`` — fail-open, never raises.

    Returns ``"emitted"`` on apparent success, ``"skipped:bus-unavailable"``
    when the bus integration is missing, or ``"failed:<reason>"`` on any
    other error. The caller records this string in the audit trail so the
    eventual reconciler can spot resolutions that didn't make it onto
    the bus.
    """
    try:
        from _bus import emit_event  # type: ignore[import]
        # Per-condition chain_id — `_bus.is_processed` keys idempotency
        # off chain_id, so a phase-level chain would let consumers
        # silently skip every resolution after the first in the same
        # phase. Including condition_id makes each resolution event
        # uniquely identifiable downstream.
        chain_id = f"{project_id}.{phase}.{condition_id}"
        emit_event(
            "wicked.gate.condition.resolved",
            {
                "project_id": project_id,
                "phase": phase,
                "condition_id": condition_id,
                "applied_rule": applied_rule,
                "verdict_unchanged": True,
            },
            chain_id=chain_id,
        )
        return "emitted"
    except ImportError:
        return "skipped:bus-unavailable"
    except Exception as exc:  # pragma: no cover — defensive
        return f"failed:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_preview(result: dict) -> None:
    print(f"# crew:resolve preview — phase={result['phase']}")
    print()
    if not result["manifest_loaded"]:
        print("(no conditions-manifest.json — nothing to resolve)")
        return
    print(f"mechanical: {len(result['mechanical'])}")
    for e in result["mechanical"]:
        print(f"  - {e['condition_id']} [{e['applied_rule']}] {e['message'][:80]}")
    print(f"judgment:   {len(result['judgment'])}")
    for e in result["judgment"]:
        print(f"  - {e['condition_id']} [{e['applied_rule']}] {e['message'][:80]}")
    print(f"escalation: {len(result['escalation'])}")
    for e in result["escalation"]:
        print(f"  - {e['condition_id']} [{e['applied_rule']}] REFUSED: {e['refused_with'][:60]}")
    if result["resolved"]:
        print(f"resolved:   {len(result['resolved'])}")
        for r in result["resolved"]:
            print(f"  - {r['condition_id']} → {r['sidecar_path']} (emit={r['emit_status']})")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve mechanical CONDITIONAL findings (#717). Verdict NEVER mutated.",
    )
    parser.add_argument("project_dir")
    parser.add_argument("phase")
    parser.add_argument(
        "--accept",
        action="store_true",
        help="Write resolution sidecars + emit events for mechanical clusters. "
             "Without --accept the run is a preview.",
    )
    parser.add_argument(
        "--cluster-id",
        default=None,
        help="Restrict resolution to a single condition id.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the result as JSON instead of the human-readable preview.",
    )
    args = parser.parse_args(argv)

    result = resolve_phase(
        args.project_dir,
        args.phase,
        accept=args.accept,
        cluster_id=args.cluster_id,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        _print_preview(result)

    if not result["manifest_loaded"]:
        return 1
    if result["escalation"] and not (result["mechanical"] or result["judgment"]):
        # All-escalation phases: the user must take action elsewhere.
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
