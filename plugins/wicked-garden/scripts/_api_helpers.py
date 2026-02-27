#!/usr/bin/env python3
"""
_api_helpers.py — Shared utilities replacing 48 duplicated helper functions.

Provides the canonical implementations of meta(), error(), read_input(),
validate(), paginate(), parse_envelope(), success(), and validate_safe_name().

Domain scripts import from here instead of defining their own _meta()/_error():

    from _api_helpers import meta, error, read_input, validate, paginate, success

Standard output envelope:
    {
        "data": <list or dict>,
        "meta": {
            "total": N,
            "limit": N,
            "offset": N,
            "source": "memories",
            "timestamp": "2026-01-01T00:00:00+00:00"
        }
    }

Standard error (written to stderr, then sys.exit(1)):
    { "error": "...", "code": "VALIDATION_ERROR", "details": {...} }
"""

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Output envelope helpers
# ---------------------------------------------------------------------------


def meta(source: str, total: int, limit: int = 100, offset: int = 0) -> dict:
    """Build the standard meta block included in every API response.

    Args:
        source: Name of the data source / collection (e.g. "memories").
        total:  Total number of records available (before pagination).
        limit:  Page size applied to the response.
        offset: Number of records skipped.

    Returns:
        Meta dict ready to be embedded in the response envelope.
    """
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def success(data: Any, source: str, total: int | None = None) -> None:
    """Print the standard {data, meta} envelope to stdout and return.

    Args:
        data:   List of records or a single record dict.
        source: Data source name for the meta block.
        total:  Total count override. Defaults to len(data) for lists, 1 for dicts.

    Prints JSON to stdout. Does NOT call sys.exit — callers can continue after.
    """
    if total is None:
        total = len(data) if isinstance(data, list) else 1

    limit = len(data) if isinstance(data, list) else 1
    envelope = {"data": data, "meta": meta(source, total, limit=limit)}
    print(json.dumps(envelope, indent=2))


def parse_envelope(response: dict) -> tuple[Any, dict]:
    """Split a control plane response into (data, meta).

    Args:
        response: The raw dict returned by ControlPlaneClient.request().

    Returns:
        (data, meta_dict). data may be a list or dict. meta_dict may be empty
        if the response did not include a meta block.
    """
    return response.get("data"), response.get("meta", {})


# ---------------------------------------------------------------------------
# Error output
# ---------------------------------------------------------------------------


def error(message: str, code: str, **details: Any) -> None:
    """Print a structured error to stderr and exit with status 1.

    This function does NOT return. It is the canonical error exit for all
    domain scripts.

    Args:
        message: Human-readable error description.
        code:    Machine-readable error code (e.g. "NOT_FOUND", "VALIDATION_ERROR").
        **details: Optional structured context merged into "details" key.
    """
    err: dict[str, Any] = {"error": message, "code": code}
    if details:
        err["details"] = details
    print(json.dumps(err), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------


def read_input() -> dict:
    """Read JSON from stdin for write operations.

    Returns an empty dict when stdin is a TTY (interactive) or empty.
    Calls error() and exits if stdin contains invalid JSON.

    Returns:
        Parsed dict from stdin, or {} when no input is present.
    """
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        error("Invalid JSON input", "INVALID_INPUT", detail=str(exc))
        return {}  # unreachable, satisfies type checkers


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(payload: dict, required_fields: list[str] | tuple[str, ...]) -> None:
    """Assert that all required_fields are present and non-None in payload.

    Calls error() (exits) on the first missing field group.

    Args:
        payload:         Input dict to validate.
        required_fields: Field names that must be present and non-None.
    """
    missing = [f for f in required_fields if f not in payload or payload[f] is None]
    if not missing:
        return
    error(
        "Validation failed",
        "VALIDATION_ERROR",
        fields={f: "required field missing" for f in missing},
    )


def validate_safe_name(name: str, field: str = "name") -> None:
    """Assert that name is a safe kebab-case identifier.

    Allowed characters: lowercase letters, digits, hyphens. No spaces, no
    path separators, max 64 chars.

    Calls error() (exits) on violation.

    Args:
        name:  The value to validate.
        field: Field name used in error output.
    """
    if not name:
        error(f"'{field}' must not be empty", "VALIDATION_ERROR", field=field)

    if len(name) > 64:
        error(
            f"'{field}' exceeds maximum length of 64 characters",
            "VALIDATION_ERROR",
            field=field,
            length=len(name),
        )

    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", name):
        error(
            f"'{field}' must be lowercase letters, digits, and hyphens only",
            "VALIDATION_ERROR",
            field=field,
            value=name,
        )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def paginate(items: list, limit: int, offset: int) -> tuple[list, int]:
    """Apply limit/offset pagination to a list.

    Args:
        items:  Full list of records.
        limit:  Maximum number of records to return.
        offset: Number of records to skip from the start.

    Returns:
        (page: list, total: int) — the sliced page and the pre-pagination total.

    Example:
        page, total = paginate(all_items, limit=10, offset=20)
        print(json.dumps({"data": page, "meta": meta("tasks", total, limit, offset)}))
    """
    total = len(items)
    page = items[offset : offset + limit]
    return page, total
