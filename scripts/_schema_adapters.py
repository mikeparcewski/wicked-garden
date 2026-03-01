#!/usr/bin/env python3
"""
_schema_adapters.py — Bidirectional schema translation at the CP boundary.

Domain scripts write in their native field names ("script format").
The control plane expects a different schema for some sources.
This module sits between StorageManager and ControlPlaneClient to
translate outbound (script → CP) and inbound (CP → script) payloads.

Two adapter tiers:
    1. Static adapters: hand-tuned per (domain, source) in _REGISTRY.
       Handle semantic renames (category→signal_type) and complex transforms.
    2. Dynamic adapters: auto-generated from manifest_detail() schemas.
       Handle required-field defaults and overflow packing into metadata.

Priority: static adapter > dynamic adapter > passthrough.

Fail-open: if any adapter crashes, the original record is returned
unchanged.  The untransformed payload may still be rejected by CP,
but callers handle None returns gracefully.
"""

import json
import sys
import time
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
# Dynamic schema adaptation (manifest_detail-based)
# ---------------------------------------------------------------------------

# CP system fields that scripts typically don't send or expect back.
_CP_SYSTEM_FIELDS = frozenset({
    "id", "created_at", "updated_at", "deleted_at",
})

# Fields eligible as overflow containers (checked in priority order).
_OVERFLOW_CANDIDATES = ("metadata", "payload", "extra", "extras")

# TTL for cached schemas (seconds).
_SCHEMA_CACHE_TTL = 300  # 5 minutes

# Sentinel value cached for manifest_detail misses to avoid repeated lookups.
_NEGATIVE_SENTINEL: dict = {"_negative": True}

# CP client reference, injected by StorageManager at init time.
_cp_client: Any = None


def set_cp_client(client: Any) -> None:
    """Inject the ControlPlaneClient used for manifest_detail lookups.

    Called by StorageManager.__init__ so the adapter module reuses the
    same client (and timeout settings) as the caller.
    """
    global _cp_client
    _cp_client = client


class _SchemaCache:
    """In-process TTL cache for parsed manifest_detail schemas.

    Short-lived hook processes do at most one fetch per (domain, source).
    Long-lived command scripts benefit from TTL-based reuse.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], tuple[float, dict]] = {}

    def get(self, domain: str, source: str, verb: str) -> dict | None:
        key = (domain, source, verb)
        entry = self._entries.get(key)
        if entry is None:
            return None
        ts, schema = entry
        if time.monotonic() - ts > _SCHEMA_CACHE_TTL:
            del self._entries[key]
            return None
        return schema

    def put(self, domain: str, source: str, verb: str, schema: dict) -> None:
        self._entries[(domain, source, verb)] = (time.monotonic(), schema)


_schema_cache = _SchemaCache()


def _parse_schema(detail: dict) -> dict | None:
    """Extract structured schema info from a manifest_detail response.

    Returns a dict with:
        known_fields:   set of field names the CP accepts
        required:       set of required field names
        defaults:       dict of field_name → default_value
        overflow_field: name of the dict/object field for packing extras, or None

    Returns None if the schema cannot be parsed.
    """
    body = detail.get("request_body")
    if not body or not isinstance(body, dict):
        return None

    props = body.get("properties")
    if not props or not isinstance(props, dict):
        return None

    known_fields: set[str] = set(props.keys())
    required: set[str] = set()
    defaults: dict[str, Any] = {}
    overflow_field: str | None = None

    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue

        if spec.get("required"):
            required.add(name)

        if "default" in spec:
            defaults[name] = spec["default"]

        # Identify overflow candidate (first match wins)
        ftype = spec.get("type", "")
        if overflow_field is None and ftype == "object" and name in _OVERFLOW_CANDIDATES:
            overflow_field = name

    # Infer type-appropriate defaults for required fields without one
    _TYPE_DEFAULTS = {"string": "", "integer": 0, "number": 0.0,
                      "boolean": False, "array": [], "object": {}}
    for name in required:
        if name not in defaults:
            spec = props.get(name, {})
            ftype = spec.get("type", "string")
            if ftype in _TYPE_DEFAULTS:
                defaults[name] = _TYPE_DEFAULTS[ftype]

    return {
        "known_fields": known_fields,
        "required": required,
        "defaults": defaults,
        "overflow_field": overflow_field,
    }


def _get_or_fetch_schema(domain: str, source: str, verb: str) -> dict | None:
    """Fetch, parse, and cache a schema from manifest_detail.

    For read verbs (list, get), looks up the 'create' schema since it
    defines the full field set.  Returns None if unavailable.
    """
    lookup_verb = verb if verb in ("create", "update") else "create"

    cached = _schema_cache.get(domain, source, lookup_verb)
    if cached is not None:
        return None if cached.get("_negative") else cached

    if _cp_client is None:
        return None

    try:
        detail = _cp_client.manifest_detail(domain, source, lookup_verb)
    except Exception:
        _schema_cache.put(domain, source, lookup_verb, _NEGATIVE_SENTINEL)
        return None

    if detail is None:
        _schema_cache.put(domain, source, lookup_verb, _NEGATIVE_SENTINEL)
        return None

    schema = _parse_schema(detail)
    if schema is None:
        _schema_cache.put(domain, source, lookup_verb, _NEGATIVE_SENTINEL)
        return None

    _schema_cache.put(domain, source, lookup_verb, schema)
    return schema


def _dynamic_to_cp(record: dict, schema: dict, verb: str = "create") -> dict:
    """Generic outbound adapter: inject required defaults, pack overflow."""
    out = dict(record)

    known = schema["known_fields"]
    overflow_field = schema["overflow_field"]

    # 1. Inject missing required/default fields (create only — updates are partial)
    if verb == "create":
        for field_name, default_val in schema["defaults"].items():
            if field_name not in out:
                # Copy mutable defaults to avoid shared-state bugs
                out[field_name] = list(default_val) if isinstance(default_val, list) \
                    else dict(default_val) if isinstance(default_val, dict) \
                    else default_val

    # 2. Pack overflow: fields not in schema → overflow_field
    if overflow_field:
        extras = {}
        for k in list(out):
            if k not in known and k not in _CP_SYSTEM_FIELDS:
                extras[k] = out.pop(k)
        if extras:
            existing = out.get(overflow_field)
            if isinstance(existing, dict):
                existing.update(extras)
            else:
                out[overflow_field] = extras

    return out


def _dynamic_from_cp(record: dict, schema: dict) -> dict:
    """Generic inbound adapter: unpack overflow fields back to top-level."""
    out = dict(record)

    overflow_field = schema.get("overflow_field")
    known = schema.get("known_fields", set())

    # Unpack overflow field: keys that aren't part of the CP schema
    # were likely packed by _dynamic_to_cp
    if overflow_field and overflow_field in out:
        packed = out.get(overflow_field)
        if isinstance(packed, dict):
            unpacked = {k: v for k, v in packed.items() if k not in known}
            if unpacked:
                out.update(unpacked)
                remaining = {k: v for k, v in packed.items() if k in known}
                if remaining:
                    out[overflow_field] = remaining
                else:
                    del out[overflow_field]

    return out


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

    Priority: static adapter → dynamic adapter (manifest_detail) → passthrough.

    Args:
        domain: Plugin domain (e.g. "wicked-crew").
        source: Resource collection (e.g. "decisions").
        verb:   CRUD verb ("create", "update", "list", etc.).
        record: Script-format record dict.

    Returns:
        CP-format record dict.
    """
    # Priority 1: static adapter
    entry = _REGISTRY.get((domain, source))
    if entry is not None:
        try:
            return entry[0](record)
        except Exception as exc:
            print(
                f"[wicked-garden] Schema adapter to_cp failed for "
                f"{domain}/{source}: {exc}",
                file=sys.stderr,
            )
            return record

    # Priority 2: dynamic adapter from manifest_detail
    schema = _get_or_fetch_schema(domain, source, verb)
    if schema is not None:
        try:
            return _dynamic_to_cp(record, schema, verb=verb)
        except Exception as exc:
            print(
                f"[wicked-garden] Dynamic adapter to_cp failed for "
                f"{domain}/{source}: {exc}",
                file=sys.stderr,
            )
            return record

    # Priority 3: passthrough
    return record


def from_cp(domain: str, source: str, verb: str, record: dict) -> dict:
    """Transform a CP-format record to script-format for inbound responses.

    Priority: static adapter → dynamic adapter (manifest_detail) → passthrough.

    Args:
        domain: Plugin domain (e.g. "wicked-crew").
        source: Resource collection (e.g. "decisions").
        verb:   CRUD verb ("list", "get", "create", etc.).
        record: CP-format record dict.

    Returns:
        Script-format record dict.
    """
    # Priority 1: static adapter
    entry = _REGISTRY.get((domain, source))
    if entry is not None:
        try:
            return entry[1](record)
        except Exception as exc:
            print(
                f"[wicked-garden] Schema adapter from_cp failed for "
                f"{domain}/{source}: {exc}",
                file=sys.stderr,
            )
            return record

    # Priority 2: dynamic adapter from manifest_detail
    schema = _get_or_fetch_schema(domain, source, verb)
    if schema is not None:
        try:
            return _dynamic_from_cp(record, schema)
        except Exception as exc:
            print(
                f"[wicked-garden] Dynamic adapter from_cp failed for "
                f"{domain}/{source}: {exc}",
                file=sys.stderr,
            )
            return record

    # Priority 3: passthrough
    return record
