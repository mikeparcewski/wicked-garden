#!/usr/bin/env python3
"""
crew/detectors/sensitive_path.py — Sensitive-path touch detector.

PR-2 of the steering detector epic (#679). First real detector. Validates the
bus-first wiring landed in PR-1 (#681) by emitting ``wicked.steer.escalated``
events when a session touches sensitive code paths (auth, payments, schema
migrations, secrets/credentials).

Design constraints:

  * Pure stdlib. No external deps.
  * Detector and emitter are SEPARATE — ``detect_sensitive_path_touch`` returns
    a list of validated payloads; ``emit_sensitive_path_events`` pushes them
    onto the bus. Tests can validate payloads without touching the bus.
  * Every emitted payload MUST pass ``crew.steering_event_schema.validate_payload``.
    The emitter has a runtime assertion to enforce this — a payload that fails
    schema validation is dropped (with a stderr warning) and the count is not
    incremented, so a buggy detector cannot silently spam malformed events.
  * Fail-open if bus is unreachable — print to stderr, return 0 from the
    emitter, exit 0 from the CLI. Never crash the calling crew workflow.
  * Extension filter is the brainstorm-mandated guardrail: a README inside
    ``auth/`` does NOT trigger. Only code files do.
  * No call-site changes — wiring this into a hook or the crew workflow is a
    future PR. This module ships the detector + emitter only.

Usage (programmatic)::

    from crew.detectors.sensitive_path import (
        detect_sensitive_path_touch,
        emit_sensitive_path_events,
    )

    payloads = detect_sensitive_path_touch(
        ["src/auth/login.py", "README.md"],
        session_id="sess-001",
        project_slug="fix-auth-redirect",
    )
    # -> [{"detector": "sensitive-path", ...}]  (one event for login.py)

    emitted = emit_sensitive_path_events(payloads)
    # -> 1

Usage (CLI)::

    # explicit paths
    python3 scripts/crew/detectors/sensitive_path.py \\
        --paths src/auth/login.py db/migrations/001.sql \\
        --session-id sess-001 --project-slug demo --dry-run

    # paths from a git diff range
    python3 scripts/crew/detectors/sensitive_path.py \\
        --paths-from-git-diff origin/main..HEAD \\
        --session-id sess-001 --project-slug demo
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

# Allow running directly as a script (``python3 scripts/crew/detectors/sensitive_path.py``).
# When imported as a package (``crew.detectors.sensitive_path``) the package import
# already resolved sys.path, so this is a no-op in that case.
_REPO_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_REPO_SCRIPTS))

from crew.steering_event_schema import (  # noqa: E402  (sys.path tweak above)
    KNOWN_DETECTORS,
    validate_payload,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DETECTOR_NAME = "sensitive-path"
EVENT_TYPE = "wicked.steer.escalated"
EVENT_DOMAIN = "wicked-garden"
EVENT_SUBDOMAIN = f"crew.detector.{DETECTOR_NAME}"

# Schema-layer guardrail — make sure this detector is allowlisted in PR-1.
assert DETECTOR_NAME in KNOWN_DETECTORS, (
    f"detector {DETECTOR_NAME!r} not in KNOWN_DETECTORS — "
    "schema (steering_event_schema.py) and detector are out of sync"
)

#: Recommended rigor action per category. Loose set per PR-1; if you add a new
#: category here also confirm it's an entry in ``KNOWN_ACTIONS`` (or accept the
#: warning the validator will produce).
ACTION_MAP: dict = {
    "auth": "force-full-rigor",
    "payments": "force-full-rigor",
    "migration": "regen-test-strategy",
    "secrets": "require-council-review",
}

#: Common code extensions used as the auth/payments default extension filter.
_CODE_EXTS: List[str] = [
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".kt",
    ".rb", ".rs", ".cs", ".scala", ".php", ".swift", ".m", ".mm",
]

#: Migration-specific extensions — SQL + ORM migration files only.
_MIGRATION_EXTS: List[str] = [".sql", ".py", ".rb", ".prisma", ".js", ".ts"]

#: Secrets/credentials extensions — code AND config formats. ``.env`` is the
#: load-bearing one; YAML/JSON catch the common config-secret leak shapes.
_SECRET_EXTS: List[str] = [
    ".py", ".ts", ".js", ".go", ".java", ".rb", ".rs",
    ".env", ".yaml", ".yml", ".json", ".toml",
]

#: Default sensitive-path patterns. Each entry is matched in order; a path that
#: matches multiple patterns produces multiple events (the caller can dedupe).
SENSITIVE_PATH_PATTERNS: List[dict] = [
    # Auth / identity
    {"glob": "**/auth/**",            "extensions": _CODE_EXTS, "category": "auth"},
    {"glob": "**/authentication/**",  "extensions": _CODE_EXTS, "category": "auth"},
    {"glob": "**/authorization/**",   "extensions": _CODE_EXTS, "category": "auth"},
    {"glob": "**/login/**",           "extensions": _CODE_EXTS, "category": "auth"},
    {"glob": "**/identity/**",        "extensions": _CODE_EXTS, "category": "auth"},
    # Payments / billing
    {"glob": "**/payment*/**",        "extensions": _CODE_EXTS, "category": "payments"},
    {"glob": "**/billing/**",         "extensions": _CODE_EXTS, "category": "payments"},
    {"glob": "**/charge*/**",         "extensions": _CODE_EXTS, "category": "payments"},
    # Migrations / schema
    {"glob": "**/migrations/**",      "extensions": _MIGRATION_EXTS, "category": "migration"},
    {"glob": "**/schema/**",          "extensions": _MIGRATION_EXTS, "category": "migration"},
    # Secrets / credentials / tokens
    {"glob": "**/*secret*",           "extensions": _SECRET_EXTS, "category": "secrets"},
    {"glob": "**/*credential*",       "extensions": _SECRET_EXTS, "category": "secrets"},
    {"glob": "**/*token*",            "extensions": _SECRET_EXTS, "category": "secrets"},
]

#: Bus probe timeout — mirrors the 5s budget used elsewhere in the plugin.
_BUS_PROBE_TIMEOUT_SECONDS = 5.0
#: Emit timeout — give bus emit a little more headroom than a status probe.
_BUS_EMIT_TIMEOUT_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Glob -> regex
# ---------------------------------------------------------------------------

def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a ``**``-aware glob into an anchored regex.

    Rules:

      * ``**`` matches any number of path components (including zero), so
        ``**/auth/**`` matches ``auth/login.py``, ``src/auth/login.py``, and
        ``a/b/c/auth/x/y.py``.
      * ``*`` matches any character except ``/`` (one path segment chunk).
      * Other regex metacharacters are escaped.

    Path separators are normalized to ``/`` by the caller.
    """
    # Process character-by-character so we can collapse `**` patterns before
    # individual `*` characters get escaped.
    out: List[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            # Look for `**` (optionally with trailing `/`)
            if i + 1 < n and pattern[i + 1] == "*":
                # Handle `**/` and `/**` and bare `**`.
                if i + 2 < n and pattern[i + 2] == "/":
                    # `**/` — match zero or more "<segment>/" chunks
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                # Trailing or bare `**` — match anything (across separators).
                out.append(".*")
                i += 2
                continue
            # Single `*` — match any chars except path separator.
            out.append("[^/]*")
            i += 1
            continue
        if c == "?":
            out.append("[^/]")
            i += 1
            continue
        if c == "/":
            out.append("/")
            i += 1
            continue
        out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _normalize_path(path: str) -> str:
    """Normalize a path for matching: forward slashes, no leading ``./``."""
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def _has_extension(path: str, extensions: Sequence[str]) -> bool:
    """Return True if ``path`` ends with one of ``extensions`` (case-insensitive).

    Empty/None extension lists mean "any extension passes" — but the default
    patterns always supply a non-empty list, so this is the brainstorm-mandated
    guardrail: a README inside ``auth/`` will not match because ``.md`` is not
    in any of the default extension lists.
    """
    if not extensions:
        return True
    lowered = path.lower()
    return any(lowered.endswith(ext.lower()) for ext in extensions)


# ---------------------------------------------------------------------------
# Public API — detector
# ---------------------------------------------------------------------------

def detect_sensitive_path_touch(
    changed_paths: Iterable[str],
    *,
    session_id: str,
    project_slug: str,
    patterns: Optional[List[dict]] = None,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Inspect ``changed_paths`` and return one validated payload per match.

    Each payload conforms to ``crew.steering_event_schema`` and is ready to
    emit on wicked-bus as ``wicked.steer.escalated``.

    Args:
        changed_paths: Iterable of file paths (e.g. from ``git diff --name-only``).
            Empty/whitespace-only entries are skipped.
        session_id: Session that produced the change set. Required by schema.
        project_slug: Crew project slug. Required by schema.
        patterns: Override the default ``SENSITIVE_PATH_PATTERNS``. Each entry
            must have ``glob``, ``extensions``, and ``category``. Useful for
            tests and per-project tuning.
        now: Override the timestamp source — only used by tests for
            determinism. Production callers leave this as ``None``.

    Returns:
        A list of payload dicts — possibly empty. The detector does not
        deduplicate: a path matching two patterns produces two payloads, and
        the caller may choose to dedupe by ``(file, category)``.

    Raises:
        ValueError: if ``session_id`` or ``project_slug`` is empty/whitespace,
            or if a custom ``patterns`` entry is missing required keys. The
            detector validates inputs eagerly so a misconfigured caller
            doesn't silently emit invalid events.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")
    if not isinstance(project_slug, str) or not project_slug.strip():
        raise ValueError("project_slug must be a non-empty string")

    active_patterns = patterns if patterns is not None else SENSITIVE_PATH_PATTERNS
    compiled: List[tuple] = []
    for entry in active_patterns:
        for required in ("glob", "extensions", "category"):
            if required not in entry:
                raise ValueError(
                    f"pattern entry missing required key {required!r}: {entry!r}"
                )
        compiled.append((
            _glob_to_regex(entry["glob"]),
            tuple(entry["extensions"]),
            entry["category"],
            entry["glob"],
        ))

    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payloads: List[dict] = []
    for raw_path in changed_paths:
        if not raw_path or not str(raw_path).strip():
            continue
        path = _normalize_path(str(raw_path))

        for regex, exts, category, glob_pattern in compiled:
            if not regex.match(path):
                continue
            if not _has_extension(path, exts):
                # Extension filter rejected — README inside auth/ lands here.
                continue
            action = ACTION_MAP.get(category, "force-full-rigor")
            payload = {
                "detector": DETECTOR_NAME,
                "signal": f"sensitive {category} path touched: {path}",
                "threshold": {
                    "glob": glob_pattern,
                    "extensions": list(exts),
                    "category": category,
                },
                "recommended_action": action,
                "evidence": {
                    "file": path,
                    "category": category,
                    "matched_glob": glob_pattern,
                    "session_id": session_id,
                    "project_slug": project_slug,
                },
                "session_id": session_id,
                "project_slug": project_slug,
                "timestamp": timestamp,
            }
            # Defense-in-depth: the detector built this payload, so the schema
            # MUST accept it. If it doesn't, that's a bug in the detector — not
            # a runtime condition to swallow. Fail loudly during dev.
            errors, _warnings = validate_payload(EVENT_TYPE, payload)
            if errors:
                raise AssertionError(
                    f"detector built an invalid payload for {path!r}: {errors}"
                )
            payloads.append(payload)
    return payloads


# ---------------------------------------------------------------------------
# Public API — emitter
# ---------------------------------------------------------------------------

def _resolve_bus_command() -> Optional[List[str]]:
    """Return argv prefix for invoking wicked-bus, or None if unreachable.

    Mirrors ``scripts/_bus.py:_resolve_binary`` and ``steering_tail.py``: prefer
    direct binary; fall back to ``npx wicked-bus`` only after probing
    ``status --json`` (otherwise npx may hang downloading the package).
    """
    direct = shutil.which("wicked-bus")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx is None:
        return None
    try:
        result = subprocess.run(
            [npx, "wicked-bus", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=_BUS_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return [npx, "wicked-bus"]


def emit_sensitive_path_events(payloads: Sequence[dict]) -> int:
    """Emit each payload to wicked-bus as ``wicked.steer.escalated``.

    Subdomain is fixed at ``crew.detector.sensitive-path``.

    Every payload is re-validated immediately before emit. Payloads that fail
    schema validation are dropped with a stderr warning — they do NOT count
    toward the return value. This is the contract guarantee promised by the
    docstring: every event that lands on the bus passed validation.

    Fail-open: if wicked-bus is not installed/reachable, log to stderr and
    return 0 instead of raising. The crew workflow must never be blocked by
    a missing bus.

    Args:
        payloads: Sequence of payload dicts produced by
            ``detect_sensitive_path_touch``.

    Returns:
        Count of payloads that were successfully emitted (i.e. the bus
        subprocess exited 0). Bus unreachable, schema failure, and emit
        timeouts all count as 0.
    """
    if not payloads:
        return 0

    bus_cmd = _resolve_bus_command()
    if bus_cmd is None:
        sys.stderr.write(
            "warn: wicked-bus is not installed or unreachable; "
            f"dropping {len(payloads)} sensitive-path event(s). "
            "Install via 'npm install -g wicked-bus' to enable steering events.\n"
        )
        return 0

    emitted = 0
    for payload in payloads:
        # Re-validate at the bus boundary — defense in depth. The detector
        # also validates, but a misbehaving caller could pass hand-crafted
        # payloads directly. Schema failures are dropped, never blocked.
        errors, _warnings = validate_payload(EVENT_TYPE, payload)
        if errors:
            sys.stderr.write(
                f"warn: dropping invalid sensitive-path payload: {errors}\n"
            )
            continue

        cmd = list(bus_cmd) + [
            "emit",
            "--type", EVENT_TYPE,
            "--domain", EVENT_DOMAIN,
            "--subdomain", EVENT_SUBDOMAIN,
            "--payload", json.dumps(payload, default=str, separators=(",", ":")),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_BUS_EMIT_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            sys.stderr.write(
                f"warn: wicked-bus emit failed for sensitive-path event: {exc}\n"
            )
            continue
        if result.returncode != 0:
            sys.stderr.write(
                f"warn: wicked-bus emit returned {result.returncode}: "
                f"{result.stderr.strip() or '(no stderr)'}\n"
            )
            continue
        emitted += 1
    return emitted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sensitive_path",
        description=(
            "Detect sensitive-path touches and emit wicked.steer.escalated "
            "events. Reads paths either from --paths or from --paths-from-git-diff."
        ),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--paths",
        nargs="+",
        help="Explicit list of file paths to inspect.",
    )
    src.add_argument(
        "--paths-from-git-diff",
        metavar="DIFF_RANGE",
        help=(
            "Run 'git diff --name-only <DIFF_RANGE>' and inspect those paths. "
            "Example: --paths-from-git-diff origin/main..HEAD"
        ),
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Session that produced the change set (required by schema).",
    )
    parser.add_argument(
        "--project-slug",
        required=True,
        help="Crew project slug (required by schema).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and print payloads to stdout but do NOT emit to wicked-bus."
        ),
    )
    return parser.parse_args(argv)


def _git_diff_paths(diff_range: str) -> List[str]:
    """Run ``git diff --name-only`` and return the path list. Fail-open."""
    git = shutil.which("git")
    if git is None:
        sys.stderr.write("warn: git not found on PATH; cannot resolve diff range\n")
        return []
    try:
        result = subprocess.run(
            [git, "diff", "--name-only", diff_range],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        sys.stderr.write(f"warn: git diff failed: {exc}\n")
        return []
    if result.returncode != 0:
        sys.stderr.write(
            f"warn: git diff --name-only {diff_range!r} returned "
            f"{result.returncode}: {result.stderr.strip() or '(no stderr)'}\n"
        )
        return []
    return [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    if args.paths:
        paths = list(args.paths)
    else:
        paths = _git_diff_paths(args.paths_from_git_diff)

    try:
        payloads = detect_sensitive_path_touch(
            paths,
            session_id=args.session_id,
            project_slug=args.project_slug,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    # Always print the resolved payloads so the user can audit what would be
    # emitted (or what was emitted, when --dry-run is absent).
    for payload in payloads:
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()

    sys.stderr.write(
        f"detector: {len(payloads)} sensitive-path event(s) from {len(paths)} path(s)\n"
    )

    if args.dry_run:
        return 0

    emitted = emit_sensitive_path_events(payloads)
    sys.stderr.write(
        f"emitted: {emitted}/{len(payloads)} event(s) to wicked-bus\n"
    )
    # Fail-open: even if emit count is 0 (bus unreachable), exit 0 so we never
    # crash the calling crew workflow. Stderr already explained what happened.
    return 0


__all__ = [
    "DETECTOR_NAME",
    "EVENT_TYPE",
    "EVENT_DOMAIN",
    "EVENT_SUBDOMAIN",
    "ACTION_MAP",
    "SENSITIVE_PATH_PATTERNS",
    "detect_sensitive_path_touch",
    "emit_sensitive_path_events",
]


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
