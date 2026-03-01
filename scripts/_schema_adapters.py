#!/usr/bin/env python3
"""
_schema_adapters.py — Bidirectional schema translation at the CP boundary.

Domain scripts write in their native field names ("script format").
The control plane expects a different schema for 12 newer sources.
This module sits between StorageManager and ControlPlaneClient to
translate outbound (script → CP) and inbound (CP → script) payloads.

Fail-open: if any adapter crashes, the original record is returned
unchanged.  The untransformed payload may still be rejected by CP,
but callers handle None returns gracefully.

Sources without a registered adapter pass through untouched.
"""

import json
import sys
from typing import Any, Callable

# Type alias for adapter functions
AdapterFn = Callable[[dict], dict]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pop_remaining(src: dict, *exclude: str) -> dict:
    """Return a copy of *src* without the named keys."""
    return {k: v for k, v in src.items() if k not in exclude}


def _json_str(obj: Any) -> str:
    """Serialize to JSON string if not already a string."""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj)


def _json_load(val: Any) -> Any:
    """Parse JSON string back to object; pass through non-strings."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


# ---------------------------------------------------------------------------
# crew / decisions
# ---------------------------------------------------------------------------

def _crew_decisions_to_cp(r: dict) -> dict:
    out = dict(r)
    # analysis fields → content JSON blob
    analysis = {}
    for k in ("complexity_score", "complexity_breakdown",
              "specialists_selected", "overrides_applied", "confidence"):
        if k in out:
            analysis[k] = out.pop(k)
    if analysis:
        out["content"] = _json_str(analysis)
    # signals dict → tags list
    signals = out.pop("signals", None)
    if signals and isinstance(signals, dict):
        out["tags"] = list(signals.keys())
        # preserve full signals in metadata for round-trip
        out.setdefault("metadata", {})
        out["metadata"]["signals"] = signals
    out["decision_type"] = "analysis"
    out.setdefault("project_name", "unknown")
    return out


def _crew_decisions_from_cp(r: dict) -> dict:
    out = dict(r)
    # content JSON → analysis fields
    content = out.pop("content", None)
    if content:
        parsed = _json_load(content)
        if isinstance(parsed, dict):
            for k in ("complexity_score", "complexity_breakdown",
                      "specialists_selected", "overrides_applied", "confidence"):
                if k in parsed:
                    out[k] = parsed[k]
    # recover signals from metadata
    meta = out.get("metadata", {})
    if isinstance(meta, dict) and "signals" in meta:
        out["signals"] = meta.pop("signals")
    # tags → signals keys (fallback if metadata didn't have it)
    if "signals" not in out:
        tags = out.pop("tags", None)
        if tags and isinstance(tags, list):
            out["signals"] = {t: 1.0 for t in tags}
    else:
        out.pop("tags", None)
    out.pop("decision_type", None)
    return out


# ---------------------------------------------------------------------------
# crew / feedback
# ---------------------------------------------------------------------------

def _crew_feedback_to_cp(r: dict) -> dict:
    out = dict(r)
    if "outcome" in out:
        out["category"] = out.pop("outcome")
    if "satisfaction" in out:
        out["rating"] = out.pop("satisfaction")
    # remaining detail fields → content JSON
    detail_keys = ("details", "context", "improvements")
    details = {}
    for k in detail_keys:
        if k in out:
            details[k] = out.pop(k)
    if details:
        out["content"] = _json_str(details)
    out["source"] = "auto"
    out.setdefault("project_name", "unknown")
    return out


def _crew_feedback_from_cp(r: dict) -> dict:
    out = dict(r)
    if "category" in out:
        out["outcome"] = out.pop("category")
    if "rating" in out:
        out["satisfaction"] = out.pop("rating")
    content = out.pop("content", None)
    if content:
        parsed = _json_load(content)
        if isinstance(parsed, dict):
            out.update(parsed)
    if out.get("source") == "auto":
        out.pop("source", None)
    return out


# ---------------------------------------------------------------------------
# crew / metrics
# ---------------------------------------------------------------------------

def _crew_metrics_to_cp(r: dict) -> dict:
    out = dict(r)
    # wrap all non-standard fields into metadata
    standard = {"id", "created_at", "updated_at", "project_name",
                "category", "metadata", "name", "value", "timestamp"}
    extras = {k: out.pop(k) for k in list(out) if k not in standard}
    if "categories" in extras:
        out.setdefault("metadata", {})
        out["metadata"]["categories"] = extras.pop("categories")
    if extras:
        out.setdefault("metadata", {})
        out["metadata"].update(extras)
    out["category"] = "signal-accuracy"
    out.setdefault("project_name", "global")
    return out


def _crew_metrics_from_cp(r: dict) -> dict:
    out = dict(r)
    meta = out.get("metadata", {})
    if isinstance(meta, dict):
        if "categories" in meta:
            out["categories"] = meta.pop("categories")
        # restore extras
        for k, v in list(meta.items()):
            if k not in ("categories",):
                out[k] = v
                del meta[k]
        if not meta:
            out.pop("metadata", None)
    out.pop("category", None)
    return out


# ---------------------------------------------------------------------------
# crew / signals
# ---------------------------------------------------------------------------

def _crew_signals_to_cp(r: dict) -> dict:
    out = dict(r)
    if "category" in out:
        out["signal_type"] = out.pop("category")
    if "text" in out:
        out["content"] = out.pop("text")
    if "weight" in out:
        out["confidence"] = out.pop("weight")
    if "library" in out:
        out["source"] = out.pop("library")
    out.setdefault("project_name", "global")
    return out


def _crew_signals_from_cp(r: dict) -> dict:
    out = dict(r)
    if "signal_type" in out:
        out["category"] = out.pop("signal_type")
    if "content" in out:
        out["text"] = out.pop("content")
    if "confidence" in out:
        out["weight"] = out.pop("confidence")
    if "source" in out:
        out["library"] = out.pop("source")
    return out


# ---------------------------------------------------------------------------
# crew / tool-usage
# ---------------------------------------------------------------------------

def _crew_tool_usage_to_cp(r: dict) -> dict:
    out = dict(r)
    if "tool" in out:
        out["tool_name"] = out.pop("tool")
    agent = out.pop("agent", None)
    if agent:
        out.setdefault("metadata", {})
        out["metadata"]["agent"] = agent
    out.setdefault("invocation_count", 1)
    out.setdefault("project_name", "global")
    return out


def _crew_tool_usage_from_cp(r: dict) -> dict:
    out = dict(r)
    if "tool_name" in out:
        out["tool"] = out.pop("tool_name")
    meta = out.get("metadata", {})
    if isinstance(meta, dict) and "agent" in meta:
        out["agent"] = meta.pop("agent")
        if not meta:
            out.pop("metadata", None)
    out.pop("invocation_count", None)
    return out


# ---------------------------------------------------------------------------
# kanban / activity
# ---------------------------------------------------------------------------

def _kanban_activity_to_cp(r: dict) -> dict:
    out = dict(r)
    if "type" in out:
        out["event_type"] = out.pop("type")
    # pack remaining non-standard fields into payload
    standard = {"id", "created_at", "updated_at", "event_type",
                "payload", "actor", "timestamp", "task_id", "initiative_id"}
    extras = {k: out.pop(k) for k in list(out) if k not in standard}
    if extras:
        out.setdefault("payload", {})
        if isinstance(out["payload"], dict):
            out["payload"].update(extras)
        else:
            out["payload"] = extras
    out["actor"] = "claude"
    return out


def _kanban_activity_from_cp(r: dict) -> dict:
    out = dict(r)
    if "event_type" in out:
        out["type"] = out.pop("event_type")
    # unpack payload
    payload = out.pop("payload", None)
    if payload and isinstance(payload, dict):
        out.update(payload)
    if out.get("actor") == "claude":
        out.pop("actor", None)
    return out


# ---------------------------------------------------------------------------
# kanban / config
# ---------------------------------------------------------------------------

def _kanban_config_to_cp(r: dict) -> dict:
    out = dict(r)
    if "id" in out:
        out["key"] = out.pop("id")
    # everything else becomes the value object
    standard = {"key", "created_at", "updated_at", "value"}
    value_fields = {k: out.pop(k) for k in list(out) if k not in standard}
    if value_fields:
        out["value"] = value_fields
    return out


def _kanban_config_from_cp(r: dict) -> dict:
    out = dict(r)
    if "key" in out:
        out["id"] = out.pop("key")
    value = out.pop("value", None)
    if value and isinstance(value, dict):
        out.update(value)
    return out


# ---------------------------------------------------------------------------
# kanban / indexes
# ---------------------------------------------------------------------------

def _kanban_indexes_to_cp(r: dict) -> dict:
    out = dict(r)
    if "id" in out:
        out["project_id"] = out.pop("id")
    # flatten structured index data into task_ids list
    standard = {"project_id", "created_at", "updated_at", "task_ids"}
    remaining = {k: out.pop(k) for k in list(out) if k not in standard}
    if "all" in remaining:
        out["task_ids"] = remaining.pop("all")
    elif remaining:
        # fallback: collect any list values as task_ids
        for v in remaining.values():
            if isinstance(v, list):
                out.setdefault("task_ids", []).extend(v)
    return out


def _kanban_indexes_from_cp(r: dict) -> dict:
    out = dict(r)
    if "project_id" in out:
        out["id"] = out.pop("project_id")
    if "task_ids" in out:
        out["all"] = out.pop("task_ids")
    return out


# ---------------------------------------------------------------------------
# kanban / swimlanes
# ---------------------------------------------------------------------------

def _kanban_swimlanes_to_cp(r: dict) -> dict:
    out = dict(r)
    if "id" in out:
        out["project_id"] = out.pop("id")
    # lane objects → name strings
    standard = {"project_id", "created_at", "updated_at", "lanes"}
    remaining = {k: out.pop(k) for k in list(out) if k not in standard}
    lanes = out.get("lanes", remaining.get("lanes", []))
    if lanes and isinstance(lanes, list):
        out["lanes"] = [
            ln.get("name", ln) if isinstance(ln, dict) else ln
            for ln in lanes
        ]
    return out


def _kanban_swimlanes_from_cp(r: dict) -> dict:
    out = dict(r)
    if "project_id" in out:
        out["id"] = out.pop("project_id")
    # name strings → minimal lane objects
    lanes = out.get("lanes", [])
    if lanes and isinstance(lanes, list):
        out["lanes"] = [
            {"name": ln} if isinstance(ln, str) else ln
            for ln in lanes
        ]
    return out


# ---------------------------------------------------------------------------
# observability / assertions
# ---------------------------------------------------------------------------

_ASSERTION_STATUS_MAP = {"pass": "passed", "fail": "failed", "skip": "skipped"}
_ASSERTION_STATUS_REV = {v: k for k, v in _ASSERTION_STATUS_MAP.items()}


def _obs_assertions_to_cp(r: dict) -> dict:
    out = dict(r)
    # plugin:script → assertion_name
    plugin = out.pop("plugin", None)
    script = out.pop("script", None)
    if plugin or script:
        out["assertion_name"] = f"{plugin or ''}:{script or ''}"
    # result → status enum
    result = out.pop("result", None)
    if result:
        out["status"] = _ASSERTION_STATUS_MAP.get(result, result)
    # violations → error
    violations = out.pop("violations", None)
    if violations:
        if isinstance(violations, list):
            out["error"] = "; ".join(str(v) for v in violations)
        else:
            out["error"] = str(violations)
    return out


def _obs_assertions_from_cp(r: dict) -> dict:
    out = dict(r)
    # assertion_name → plugin:script
    name = out.pop("assertion_name", None)
    if name and ":" in name:
        parts = name.split(":", 1)
        out["plugin"] = parts[0]
        out["script"] = parts[1]
    # status → result
    status = out.pop("status", None)
    if status:
        out["result"] = _ASSERTION_STATUS_REV.get(status, status)
    # error → violations
    error = out.pop("error", None)
    if error:
        out["violations"] = error.split("; ") if "; " in error else [error]
    return out


# ---------------------------------------------------------------------------
# observability / health
# ---------------------------------------------------------------------------

def _obs_health_to_cp(r: dict) -> dict:
    out = dict(r)
    if "status" in out:
        out["overall_status"] = out.pop("status")
    # violations list → probes structured array
    violations = out.pop("violations", None)
    if violations and isinstance(violations, list):
        probes = []
        for v in violations:
            if isinstance(v, dict):
                probes.append(v)
            else:
                probes.append({"name": str(v), "status": "failed"})
        out["probes"] = probes
    return out


def _obs_health_from_cp(r: dict) -> dict:
    out = dict(r)
    if "overall_status" in out:
        out["status"] = out.pop("overall_status")
    probes = out.pop("probes", None)
    if probes and isinstance(probes, list):
        out["violations"] = probes
    return out


# ---------------------------------------------------------------------------
# observability / traces — passthrough
# ---------------------------------------------------------------------------

def _passthrough(r: dict) -> dict:
    return r


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

# (domain, source) → (to_cp, from_cp)
_REGISTRY: dict[tuple[str, str], tuple[AdapterFn, AdapterFn]] = {
    ("wicked-crew", "decisions"):    (_crew_decisions_to_cp, _crew_decisions_from_cp),
    ("wicked-crew", "feedback"):     (_crew_feedback_to_cp, _crew_feedback_from_cp),
    ("wicked-crew", "metrics"):      (_crew_metrics_to_cp, _crew_metrics_from_cp),
    ("wicked-crew", "signals"):      (_crew_signals_to_cp, _crew_signals_from_cp),
    ("wicked-crew", "tool-usage"):   (_crew_tool_usage_to_cp, _crew_tool_usage_from_cp),
    ("wicked-kanban", "activity"):   (_kanban_activity_to_cp, _kanban_activity_from_cp),
    ("wicked-kanban", "config"):     (_kanban_config_to_cp, _kanban_config_from_cp),
    ("wicked-kanban", "indexes"):    (_kanban_indexes_to_cp, _kanban_indexes_from_cp),
    ("wicked-kanban", "swimlanes"):  (_kanban_swimlanes_to_cp, _kanban_swimlanes_from_cp),
    ("wicked-observability", "assertions"): (_obs_assertions_to_cp, _obs_assertions_from_cp),
    ("wicked-observability", "health"):     (_obs_health_to_cp, _obs_health_from_cp),
    ("wicked-observability", "traces"):     (_passthrough, _passthrough),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def to_cp(domain: str, source: str, verb: str, record: dict) -> dict:
    """Transform a script-format record to CP-format for outbound requests.

    Returns the original record unchanged if no adapter is registered
    or if the adapter raises an exception (fail-open).

    Args:
        domain: Plugin domain (e.g. "wicked-crew").
        source: Resource collection (e.g. "decisions").
        verb:   CRUD verb (unused currently, reserved for verb-specific transforms).
        record: Script-format record dict.

    Returns:
        CP-format record dict.
    """
    entry = _REGISTRY.get((domain, source))
    if entry is None:
        return record
    try:
        return entry[0](record)
    except Exception as exc:
        print(
            f"[wicked-garden] Schema adapter to_cp failed for "
            f"{domain}/{source}: {exc}",
            file=sys.stderr,
        )
        return record


def from_cp(domain: str, source: str, verb: str, record: dict) -> dict:
    """Transform a CP-format record to script-format for inbound responses.

    Returns the original record unchanged if no adapter is registered
    or if the adapter raises an exception (fail-open).

    Args:
        domain: Plugin domain (e.g. "wicked-crew").
        source: Resource collection (e.g. "decisions").
        verb:   CRUD verb (unused currently, reserved for verb-specific transforms).
        record: CP-format record dict.

    Returns:
        Script-format record dict.
    """
    entry = _REGISTRY.get((domain, source))
    if entry is None:
        return record
    try:
        return entry[1](record)
    except Exception as exc:
        print(
            f"[wicked-garden] Schema adapter from_cp failed for "
            f"{domain}/{source}: {exc}",
            file=sys.stderr,
        )
        return record
