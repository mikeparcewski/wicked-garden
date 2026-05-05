#!/usr/bin/env python3
"""
_validate_registry.py — startup-time validator for wicked-garden in-code allowlists.

Catches the "invisible gap" failure mode: hardcoded lists of registered assets
(phases, reviewer subagent_types, bus event handlers) silently drift from the
files / catalogs they reference. Probes pass, unrelated traffic is fine, then
the first request that hits the missing asset blows up with a cryptic error.

This validator walks each allowlist source, checks that every target exists
on disk / in the relevant catalog, and aggregates findings into structured
categories: ``missing`` / ``malformed`` / ``invalid_id``.

Stdlib-only, cross-platform. Two consumers:

1. ``hooks/scripts/bootstrap.py`` calls ``run_all_checks()`` once per
   SessionStart and surfaces findings as a session-briefing warning.
   Fail-OPEN: the validator never blocks session start.
2. The CLI entrypoint runs the same checks and exits non-zero on any
   ``missing`` / ``malformed`` / ``invalid_id`` finding for CI use.

Allowlists covered (when the source-of-truth file exists):

- Phase IDs in ``.claude-plugin/phases.json`` ↔ phase agents in ``agents/``
  (each phase that declares ``fallback_agent`` should have a matching agent
  file or specialist alias).
- Reviewer ``subagent_type`` strings in ``.claude-plugin/gate-policy.json``
  ↔ agent files in ``agents/**/*.md`` (frontmatter ``subagent_type``).
  External plugin reviewers (``wicked-testing:*``) are recognised via a
  configurable allow-prefix list and reported as ``external`` (advisory),
  not ``missing``.
- Bus event types in ``scripts/_bus.py::BUS_EVENT_MAP`` ↔ projector handlers
  in ``daemon/projector.py::_HANDLERS``. Audit-marker events are explicitly
  excluded from the handler check via ``_AUDIT_MARKER_EVENTS``.
- Skills referenced from agent frontmatter ``skills:`` lists ↔ ``SKILL.md``
  files present on disk under ``skills/``.

Categories:

- ``missing``      — a referenced asset exists in an allowlist but the
                     target file / handler / row is absent.
- ``malformed``    — the source-of-truth file is unreadable, invalid JSON,
                     or has a structurally broken entry.
- ``invalid_id``   — the referenced asset has a syntactic problem
                     (e.g. empty string, non-string in a string field,
                     unexpected colon-form).

Out-of-scope (informational only, never elevated to ``missing``):

- ``external``     — drop-in plugin reviewers (``wicked-testing:*``,
                     ``wicked-brain:*``) that legitimately live in another
                     plugin. Surfaced for visibility but never failing.
- ``skipped``      — a check skipped because its source-of-truth file is
                     missing on this checkout (e.g. ``daemon/projector.py``
                     not present in a slim install). Bootstrap surfaces
                     ``skipped`` checks as INFO, not WARN.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Categories. Keep these literal — the bootstrap consumer matches on them.
CAT_MISSING = "missing"
CAT_MALFORMED = "malformed"
CAT_INVALID_ID = "invalid_id"
CAT_EXTERNAL = "external"
CAT_SKIPPED = "skipped"

# Severity → categories. Bootstrap-warning + CI-failing categories.
_BLOCKING_CATEGORIES = frozenset({CAT_MISSING, CAT_MALFORMED, CAT_INVALID_ID})

# Reviewer subagent_type prefixes that are EXPECTED to live outside this plugin.
# Anything starting with one of these is downgraded from `missing` to `external`.
_EXTERNAL_REVIEWER_PREFIXES: Tuple[str, ...] = (
    "wicked-testing:",
    "wicked-brain:",
    "wicked-bus:",
)

# Bus event types that are AUDIT MARKERS — by design they have no projector
# handler. Source: scripts/_bus.py inline comments around the migration events.
# Keep this in sync with daemon/projector.py.ARCHITECTURE.md if it changes.
_AUDIT_MARKER_EVENTS: Tuple[str, ...] = (
    "wicked.crew.legacy_adopted",
    "wicked.crew.qe_evaluator_migrated",
    "wicked.log.rotated",
    # jam events do not project to wicked-garden's projector — their
    # consumers live in jam scripts and the brain auto-memorize subscriber.
    "wicked.session.started",
    "wicked.session.synthesized",
    "wicked.session.synthesis_ready",
    "wicked.council.voted",
    "wicked.persona.contributed",
    # qe / platform / delivery events are observability-only — no projector.
    "wicked.scenario.run",
    "wicked.coverage.changed",
    "wicked.security.finding_raised",
    "wicked.guard.findings",
    "wicked.compliance.passed",
    "wicked.compliance.failed",
    "wicked.rollout.decided",
    "wicked.experiment.concluded",
    "wicked.fact.extracted",
    "wicked.verdict.recorded",
    "wicked.quality.drift_detected",
    # crew condition resolution — observability only, verdict not mutated.
    "wicked.gate.condition.resolved",
)

# Reviewer values in gate-policy.json that are NOT subagent identifiers — they
# are mode markers / role placeholders consumed by gate_dispatch.py directly.
_NON_AGENT_REVIEWERS: Tuple[str, ...] = (
    "human",
    "user",
    "self",
    "skip",
)

# Frontmatter regex — minimal YAML reader for ``subagent_type:`` and ``name:``.
# Stdlib-only constraint precludes a real YAML dependency, and the agent
# frontmatter is mechanically generated so a regex is sufficient.
_FRONTMATTER_RE = re.compile(r"^---\s*$(.*?)^---\s*$", re.DOTALL | re.MULTILINE)
_KEY_LINE_RE = re.compile(r"^\s*([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$")


def _plugin_root() -> Path:
    """Resolve plugin root from CLAUDE_PLUGIN_ROOT, else this file's parent."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        p = Path(env)
        if p.exists():
            return p
    # scripts/_validate_registry.py → parent.parent
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """Read JSON and return (data, error_message). Either the data or an error
    string — never both."""
    if not path.is_file():
        return None, f"file not found: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _parse_agent_frontmatter(path: Path) -> Tuple[Dict[str, str], Optional[str]]:
    """Extract YAML-style frontmatter keys from an agent .md file.

    Returns ({key: value, ...}, error_or_None). Only flat string keys are
    parsed — list / nested values are returned as the raw line tail.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {}, f"read error: {exc}"
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return {}, "no frontmatter block"
    out: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = _KEY_LINE_RE.match(line)
        if km:
            out[km.group(1)] = km.group(2)
    return out, None


def _scan_agents(plugin_root: Path) -> Tuple[Dict[str, Path], List[Dict[str, Any]]]:
    """Walk agents/**/*.md and return (subagent_type → path map, malformed findings)."""
    findings: List[Dict[str, Any]] = []
    by_subagent: Dict[str, Path] = {}
    by_name: Dict[str, Path] = {}

    agents_dir = plugin_root / "agents"
    if not agents_dir.is_dir():
        return {}, [
            {
                "category": CAT_SKIPPED,
                "check": "agents.scan",
                "target": str(agents_dir),
                "detail": "agents/ directory not found — slim install?",
            }
        ]

    for md_path in agents_dir.rglob("*.md"):
        if md_path.name.upper() == "README.MD":
            continue
        fm, err = _parse_agent_frontmatter(md_path)
        if err:
            findings.append(
                {
                    "category": CAT_MALFORMED,
                    "check": "agents.frontmatter",
                    "target": str(md_path.relative_to(plugin_root)),
                    "detail": err,
                }
            )
            continue
        sub = fm.get("subagent_type", "").strip()
        name = fm.get("name", "").strip()
        if name:
            by_name.setdefault(name, md_path)
        if not sub:
            # Not every agent is required to declare subagent_type
            # (e.g. README-style agents). Skip silently.
            continue
        if ":" in sub and not sub.startswith("wicked-garden:"):
            # Mis-namespaced (e.g. typo'd colon) — flag as invalid_id.
            findings.append(
                {
                    "category": CAT_INVALID_ID,
                    "check": "agents.frontmatter",
                    "target": str(md_path.relative_to(plugin_root)),
                    "detail": f"subagent_type does not start with 'wicked-garden:': {sub!r}",
                }
            )
            continue
        if sub in by_subagent:
            findings.append(
                {
                    "category": CAT_INVALID_ID,
                    "check": "agents.duplicate",
                    "target": sub,
                    "detail": f"duplicate subagent_type in {md_path.relative_to(plugin_root)} (also {by_subagent[sub].relative_to(plugin_root)})",
                }
            )
            continue
        by_subagent[sub] = md_path

    # Expose name-keyed entries under bare-name keys so gate-policy
    # references like "senior-engineer" resolve. We register under the
    # name AND under the colon-namespaced subagent_type so both forms work.
    for nm, p in by_name.items():
        # Only register if no colon-form already claims that bare name.
        # The gate-policy "fallback" / shorthand reviewers use bare names.
        by_subagent.setdefault(nm, p)

    return by_subagent, findings


def check_phases(plugin_root: Path) -> List[Dict[str, Any]]:
    """Validate phase fallback_agent references against agent files."""
    findings: List[Dict[str, Any]] = []
    phases_path = plugin_root / ".claude-plugin" / "phases.json"
    data, err = _read_json(phases_path)
    if err:
        findings.append(
            {
                "category": CAT_SKIPPED if "not found" in err else CAT_MALFORMED,
                "check": "phases.json",
                "target": str(phases_path),
                "detail": err,
            }
        )
        return findings
    if not isinstance(data, dict):
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "phases.json",
                "target": str(phases_path),
                "detail": "top-level value is not an object",
            }
        )
        return findings

    phases = data.get("phases")
    if not isinstance(phases, dict):
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "phases.json",
                "target": str(phases_path),
                "detail": "missing or non-object 'phases' key",
            }
        )
        return findings

    agents_index, agent_findings = _scan_agents(plugin_root)
    findings.extend(agent_findings)

    # Slim-install short-circuit: if agents/ was missing, _scan_agents
    # already emitted a single `skipped` finding. Don't cascade into N
    # `missing` findings for every fallback_agent — one slim-install
    # signal is enough.
    if not agents_index and any(
        f.get("category") == CAT_SKIPPED and f.get("check") == "agents.scan"
        for f in agent_findings
    ):
        return findings

    for phase_id, body in phases.items():
        if not isinstance(phase_id, str) or not phase_id:
            findings.append(
                {
                    "category": CAT_INVALID_ID,
                    "check": "phases.id",
                    "target": repr(phase_id),
                    "detail": "phase id must be a non-empty string",
                }
            )
            continue
        if not isinstance(body, dict):
            findings.append(
                {
                    "category": CAT_MALFORMED,
                    "check": "phases.body",
                    "target": phase_id,
                    "detail": "phase body is not an object",
                }
            )
            continue
        fb = body.get("fallback_agent")
        if fb in (None, ""):
            continue  # fallback_agent is optional
        if not isinstance(fb, str):
            findings.append(
                {
                    "category": CAT_INVALID_ID,
                    "check": "phases.fallback_agent",
                    "target": phase_id,
                    "detail": f"fallback_agent is not a string: {fb!r}",
                }
            )
            continue
        if fb in _NON_AGENT_REVIEWERS:
            continue
        if fb in agents_index:
            continue
        # Bare names without colon — already merged into agents_index by name.
        findings.append(
            {
                "category": CAT_MISSING,
                "check": "phases.fallback_agent",
                "target": f"{phase_id} → {fb}",
                "detail": f"phase '{phase_id}' references fallback_agent '{fb}' but no agent .md file declares it",
            }
        )

    return findings


def check_gate_policy(plugin_root: Path) -> List[Dict[str, Any]]:
    """Validate gate-policy reviewer + fallback references against agent files."""
    findings: List[Dict[str, Any]] = []
    gp_path = plugin_root / ".claude-plugin" / "gate-policy.json"
    data, err = _read_json(gp_path)
    if err:
        findings.append(
            {
                "category": CAT_SKIPPED if "not found" in err else CAT_MALFORMED,
                "check": "gate-policy.json",
                "target": str(gp_path),
                "detail": err,
            }
        )
        return findings
    if not isinstance(data, dict):
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "gate-policy.json",
                "target": str(gp_path),
                "detail": "top-level value is not an object",
            }
        )
        return findings

    gates = data.get("gates")
    if not isinstance(gates, dict):
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "gate-policy.gates",
                "target": str(gp_path),
                "detail": "missing or non-object 'gates' key",
            }
        )
        return findings

    agents_index, agent_findings = _scan_agents(plugin_root)
    findings.extend(agent_findings)

    # Slim-install short-circuit (mirrors check_phases): if agents/ was
    # missing, return after surfacing the single `skipped` finding rather
    # than cascading into per-reviewer `missing` findings.
    if not agents_index and any(
        f.get("category") == CAT_SKIPPED and f.get("check") == "agents.scan"
        for f in agent_findings
    ):
        return findings

    def _resolve(reviewer: str) -> str:
        if not isinstance(reviewer, str) or not reviewer.strip():
            return CAT_INVALID_ID
        if reviewer in _NON_AGENT_REVIEWERS:
            return "ok"
        if any(reviewer.startswith(p) for p in _EXTERNAL_REVIEWER_PREFIXES):
            return CAT_EXTERNAL
        if reviewer in agents_index:
            return "ok"
        return CAT_MISSING

    for gate_id, tiers in gates.items():
        if not isinstance(tiers, dict):
            findings.append(
                {
                    "category": CAT_MALFORMED,
                    "check": "gate-policy.gate",
                    "target": gate_id,
                    "detail": "gate body is not an object",
                }
            )
            continue
        for tier_name, tier_body in tiers.items():
            if not isinstance(tier_body, dict):
                continue  # description / non-tier keys
            # Read raw values without falsy-coercion (`or []`) — falsy
            # non-list values like `""`, `0`, `{}` previously slipped through
            # as "no reviewers" instead of being flagged as malformed.
            raw_reviewers = tier_body.get("reviewers")
            if raw_reviewers is None:
                reviewers: List[Any] = []
            elif isinstance(raw_reviewers, list):
                reviewers = raw_reviewers
            else:
                findings.append(
                    {
                        "category": CAT_MALFORMED,
                        "check": "gate-policy.reviewers",
                        "target": f"{gate_id}.{tier_name}",
                        "detail": (
                            "reviewers is not a list "
                            f"(got {type(raw_reviewers).__name__}: {raw_reviewers!r})"
                        ),
                    }
                )
                continue
            raw_fallback = tier_body.get("fallback")
            # `fallback` is a single string (or absent). Reject any other
            # non-string type — the previous `is not None and != ""` check
            # silently accepted dicts / numbers / booleans.
            if raw_fallback is None or raw_fallback == "":
                fallback: Optional[str] = None
            elif isinstance(raw_fallback, str):
                fallback = raw_fallback
            else:
                findings.append(
                    {
                        "category": CAT_MALFORMED,
                        "check": "gate-policy.fallback",
                        "target": f"{gate_id}.{tier_name}",
                        "detail": (
                            "fallback is not a string "
                            f"(got {type(raw_fallback).__name__}: {raw_fallback!r})"
                        ),
                    }
                )
                fallback = None
            for rv in reviewers:
                outcome = _resolve(rv)
                if outcome == "ok":
                    continue
                findings.append(
                    {
                        "category": outcome,
                        "check": "gate-policy.reviewer",
                        "target": f"{gate_id}.{tier_name} → {rv}",
                        "detail": (
                            "external plugin reviewer (advisory only)"
                            if outcome == CAT_EXTERNAL
                            else f"reviewer '{rv}' has no matching agent .md file"
                            if outcome == CAT_MISSING
                            else f"reviewer is not a non-empty string: {rv!r}"
                        ),
                    }
                )
            if fallback is not None:
                outcome = _resolve(fallback)
                if outcome == "ok":
                    continue
                findings.append(
                    {
                        "category": outcome,
                        "check": "gate-policy.fallback",
                        "target": f"{gate_id}.{tier_name} → {fallback}",
                        "detail": (
                            "external plugin fallback (advisory only)"
                            if outcome == CAT_EXTERNAL
                            else f"fallback '{fallback}' has no matching agent .md file"
                            if outcome == CAT_MISSING
                            else f"fallback is not a non-empty string: {fallback!r}"
                        ),
                    }
                )

    return findings


def _extract_string_keys_from_dict_literal(text: str, var_name: str) -> Optional[Set[str]]:
    """Best-effort string-key extraction from a Python dict literal.

    Stdlib-only — we cannot import the bus module at validation time without
    pulling its deps, so we parse the source text. Looks for:

        VAR_NAME ... = {
            "key1": ...,
            "key2": ...,
        }

    Returns the set of keys, or None if the variable cannot be located.
    """
    # Match the assignment up to the opening brace
    pat = re.compile(
        r"^\s*" + re.escape(var_name) + r"\s*(?::[^=]+)?=\s*\{",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        return None
    start = m.end() - 1  # position of '{'
    depth = 0
    end = -1
    in_string: Optional[str] = None
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        # Skip Python line comments ('#' to end of line) — but ONLY when
        # we are NOT inside a string. A '}' inside a comment must not
        # decrement depth or we terminate parsing prematurely.
        if ch == "#":
            nl = text.find("\n", i)
            if nl < 0:
                # Comment runs to EOF — no closer can follow.
                break
            i = nl + 1
            continue
        if ch in ("'", '"'):
            in_string = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
        i += 1
    if end < 0:
        return None
    # Walk the dict body character-by-character, tracking brace/bracket depth
    # AND string state, so we can collect ONLY the top-level (depth-0) keys.
    # The regex-per-line approach picks up inner dict keys like "description"
    # from each event record, which is wrong.
    body = text[start + 1 : end]
    keys: Set[str] = set()
    depth_b = 0  # braces
    depth_s = 0  # square brackets
    depth_p = 0  # parens
    in_str: Optional[str] = None
    str_buf: List[str] = []
    str_start_at_zero = False
    j = 0
    n = len(body)
    while j < n:
        ch = body[j]
        if in_str:
            if ch == "\\":
                str_buf.append(body[j : j + 2])
                j += 2
                continue
            if ch == in_str:
                # Closing quote — peek ahead for ':'
                literal = "".join(str_buf)
                in_str = None
                str_buf = []
                # Skip whitespace and check for ':' — Python permits a
                # newline between the closing quote and the colon, so accept
                # CR/LF here in addition to space/tab.
                k = j + 1
                while k < n and body[k] in " \t\n\r":
                    k += 1
                if (
                    str_start_at_zero
                    and k < n
                    and body[k] == ":"
                    and re.fullmatch(r"[A-Za-z0-9_.\-]+", literal)
                ):
                    keys.add(literal)
                str_start_at_zero = False
                j += 1
                continue
            str_buf.append(ch)
            j += 1
            continue
        if ch == "#":
            # Skip line comment
            nl = body.find("\n", j)
            if nl < 0:
                break
            j = nl + 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            str_buf = []
            str_start_at_zero = depth_b == 0 and depth_s == 0 and depth_p == 0
            j += 1
            continue
        if ch == "{":
            depth_b += 1
        elif ch == "}":
            depth_b -= 1
        elif ch == "[":
            depth_s += 1
        elif ch == "]":
            depth_s -= 1
        elif ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p -= 1
        j += 1
    return keys


def check_bus_handlers(plugin_root: Path) -> List[Dict[str, Any]]:
    """Validate every BUS_EVENT_MAP entry that needs a projector has a handler."""
    findings: List[Dict[str, Any]] = []
    bus_path = plugin_root / "scripts" / "_bus.py"
    proj_path = plugin_root / "daemon" / "projector.py"

    if not bus_path.is_file():
        findings.append(
            {
                "category": CAT_SKIPPED,
                "check": "bus.event_map",
                "target": str(bus_path),
                "detail": "_bus.py not found — bus catalog check skipped",
            }
        )
        return findings

    if not proj_path.is_file():
        findings.append(
            {
                "category": CAT_SKIPPED,
                "check": "bus.handlers",
                "target": str(proj_path),
                "detail": "daemon/projector.py not found — handler check skipped",
            }
        )
        return findings

    try:
        bus_text = bus_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "bus.event_map",
                "target": str(bus_path),
                "detail": f"read error: {exc}",
            }
        )
        return findings
    try:
        proj_text = proj_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "bus.handlers",
                "target": str(proj_path),
                "detail": f"read error: {exc}",
            }
        )
        return findings

    event_keys = _extract_string_keys_from_dict_literal(bus_text, "BUS_EVENT_MAP")
    handler_keys = _extract_string_keys_from_dict_literal(proj_text, "_HANDLERS")

    if event_keys is None:
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "bus.event_map",
                "target": str(bus_path),
                "detail": "could not locate BUS_EVENT_MAP literal",
            }
        )
        return findings
    if handler_keys is None:
        findings.append(
            {
                "category": CAT_MALFORMED,
                "check": "bus.handlers",
                "target": str(proj_path),
                "detail": "could not locate _HANDLERS literal",
            }
        )
        return findings

    audit_marker = set(_AUDIT_MARKER_EVENTS)
    for evt in sorted(event_keys):
        if evt in audit_marker:
            continue
        if evt in handler_keys:
            continue
        findings.append(
            {
                "category": CAT_MISSING,
                "check": "bus.handlers",
                "target": evt,
                "detail": (
                    "event in BUS_EVENT_MAP has no projector handler in "
                    "daemon/projector.py::_HANDLERS and is not in the "
                    "audit-marker exclusion list"
                ),
            }
        )

    # Reverse direction: handler defined for an unknown event.
    # This is informational — events may be emitted via callsites that bypass
    # BUS_EVENT_MAP (e.g. legacy direct-emit paths kept for bus-as-truth
    # cutover compat). Surface as `external` so it shows up in audit but does
    # not fail the gate.
    for h in sorted(handler_keys):
        if h in event_keys:
            continue
        findings.append(
            {
                "category": CAT_EXTERNAL,
                "check": "bus.handlers.orphan",
                "target": h,
                "detail": (
                    "_HANDLERS dispatches an event_type that is not "
                    "registered in BUS_EVENT_MAP — likely emitted via a "
                    "legacy or direct-emit callsite (advisory only)"
                ),
            }
        )

    return findings


def check_skill_refs(plugin_root: Path) -> List[Dict[str, Any]]:
    """Validate that any agent frontmatter ``skills:`` reference resolves
    to a SKILL.md on disk under ``skills/``.

    Frontmatter shape varies:

        skills: foo, bar
        skills: [foo, bar]
        skills:
          - foo
          - bar

    We accept all three forms by stripping brackets / dashes and splitting
    on commas / newlines.
    """
    findings: List[Dict[str, Any]] = []
    agents_dir = plugin_root / "agents"
    skills_dir = plugin_root / "skills"
    if not agents_dir.is_dir() or not skills_dir.is_dir():
        findings.append(
            {
                "category": CAT_SKIPPED,
                "check": "skills.refs",
                "target": str(agents_dir if not agents_dir.is_dir() else skills_dir),
                "detail": "agents/ or skills/ directory missing — skill-ref check skipped",
            }
        )
        return findings

    # Build the set of skill identifiers present on disk.
    # A skill is any directory containing SKILL.md, OR a domain dir with
    # SKILL.md at its root (single-skill domains). We index by:
    #   - bare name (last path segment of the dir holding SKILL.md)
    #   - "wicked-garden:{domain}:{skill-name}" colon-form
    available: Set[str] = set()
    for skill_md in skills_dir.rglob("SKILL.md"):
        try:
            rel = skill_md.relative_to(skills_dir)
        except ValueError:
            continue
        parts = rel.parts[:-1]  # drop SKILL.md
        if not parts:
            continue
        # Bare leaf-name form
        available.add(parts[-1])
        # Colon-namespaced form for multi-skill domains
        if len(parts) == 1:
            available.add(f"wicked-garden:{parts[0]}")
        elif len(parts) >= 2:
            available.add(f"wicked-garden:{parts[0]}:{parts[-1]}")

    # Walk agents
    for md_path in agents_dir.rglob("*.md"):
        if md_path.name.upper() == "README.MD":
            continue
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _FRONTMATTER_RE.search(text)
        if not m:
            continue
        # Find the ``skills:`` block
        block = m.group(1)
        sk_match = re.search(
            r"^\s*skills\s*:\s*(.*?)(?=^\s*[A-Za-z_][\w-]*\s*:|\Z)",
            block,
            re.DOTALL | re.MULTILINE,
        )
        if not sk_match:
            continue
        raw = sk_match.group(1)
        # Normalise inline / list / multiline forms
        cleaned = raw.replace("[", " ").replace("]", " ")
        cleaned = re.sub(r"^\s*-\s*", "", cleaned, flags=re.MULTILINE)
        tokens = [
            t.strip().strip("'\"")
            for piece in cleaned.split(",")
            for t in piece.splitlines()
        ]
        for tok in tokens:
            if not tok:
                continue
            if tok in available:
                continue
            # Only flag if it LOOKS like a skill ref (no spaces, plausible chars)
            if " " in tok or len(tok) > 80:
                continue
            findings.append(
                {
                    "category": CAT_MISSING,
                    "check": "skills.refs",
                    "target": f"{md_path.relative_to(plugin_root)} → {tok}",
                    "detail": (
                        f"agent declares skills include '{tok}' but no "
                        "SKILL.md under skills/ matches that id"
                    ),
                }
            )

    return findings


def run_all_checks(plugin_root: Optional[Path] = None) -> Dict[str, Any]:
    """Run every check and return a structured report.

    Returns:
        {
            "ok": bool,                  # False if any blocking finding
            "checks_run": [name, ...],
            "findings": [ {category, check, target, detail}, ... ],
            "summary": {category: count, ...},
        }
    """
    root = plugin_root or _plugin_root()
    findings: List[Dict[str, Any]] = []
    checks_run: List[str] = []

    for name, fn in (
        ("phases", check_phases),
        ("gate_policy", check_gate_policy),
        ("bus_handlers", check_bus_handlers),
        ("skill_refs", check_skill_refs),
    ):
        try:
            results = fn(root)
        except Exception as exc:  # fail-open per individual check
            results = [
                {
                    "category": CAT_MALFORMED,
                    "check": f"{name}.exception",
                    "target": name,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ]
        checks_run.append(name)
        findings.extend(results)

    summary: Dict[str, int] = {}
    for f in findings:
        summary[f["category"]] = summary.get(f["category"], 0) + 1

    blocking = sum(summary.get(c, 0) for c in _BLOCKING_CATEGORIES)
    return {
        "ok": blocking == 0,
        "checks_run": checks_run,
        "findings": findings,
        "summary": summary,
    }


def format_briefing(
    report: Dict[str, Any],
    max_lines: int = 8,
    include_advisory: bool = False,
) -> Optional[str]:
    """Format a session-briefing string for bootstrap.py.

    Returns:
        - None when there is nothing worth surfacing in the SessionStart
          briefing (no blocking findings AND advisory-only findings are
          either absent or suppressed by `include_advisory=False`).
        - A short multi-line block otherwise.

    The default ``include_advisory=False`` keeps the briefing quiet during
    normal operation: drop-in plugin references (`wicked-testing:*`,
    `wicked-brain:*`) and known orphan handlers populate the advisory
    bucket and would otherwise add 10-15 lines to every SessionStart.
    The CLI runner shows ALL findings unconditionally — this filter only
    affects the bootstrap surface.
    """
    findings = report.get("findings", []) or []
    if not findings:
        return None
    summary = report.get("summary") or {}
    blocking = {
        c: n for c, n in summary.items() if c in _BLOCKING_CATEGORIES and n > 0
    }
    advisory = {
        c: n
        for c, n in summary.items()
        if c not in _BLOCKING_CATEGORIES and n > 0
    }
    # Bootstrap default: quiet unless something is broken.  CI runs the
    # CLI which always shows everything.
    if not blocking and not include_advisory:
        return None
    if not blocking and not advisory:
        return None
    head_parts = []
    if blocking:
        head_parts.append(
            ", ".join(f"{c}={n}" for c, n in sorted(blocking.items()))
        )
    if advisory and include_advisory:
        head_parts.append(
            "advisory: "
            + ", ".join(f"{c}={n}" for c, n in sorted(advisory.items()))
        )
    head = "[Registry] startup-time validation surfaced findings — " + "; ".join(
        head_parts
    )
    lines = [head]
    # Show blocking findings first, capped, then advisory.
    blocking_list = [f for f in findings if f["category"] in _BLOCKING_CATEGORIES]
    if include_advisory:
        advisory_list = [
            f for f in findings if f["category"] not in _BLOCKING_CATEGORIES
        ]
    else:
        advisory_list = []
    shown = 0
    for f in blocking_list + advisory_list:
        if shown >= max_lines:
            break
        lines.append(
            f"  - [{f['category']}] {f['check']}: {f['target']} — {f['detail']}"
        )
        shown += 1
    surfaced_total = len(blocking_list) + len(advisory_list)
    leftover = surfaced_total - shown
    if leftover > 0:
        lines.append(
            f"  ... and {leftover} more (run scripts/_validate_registry.py for full list)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _emit(report: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        # Use sys.stdout.write + json.dumps to honour the cross-platform
        # rule (no `printf` ambiguity); print() in Python is line-buffered
        # and adds a single newline which is fine on every platform.
        sys.stdout.write(json.dumps(report, indent=2))
        sys.stdout.write("\n")
        return
    summary = report.get("summary") or {}
    summary_str = ", ".join(f"{c}={n}" for c, n in sorted(summary.items())) or "clean"
    sys.stdout.write(
        f"wicked-garden registry validator — checks: "
        f"{', '.join(report.get('checks_run', []))}\n"
    )
    sys.stdout.write(f"  summary: {summary_str}\n")
    for f in report.get("findings", []):
        sys.stdout.write(
            f"  [{f['category']}] {f['check']}: {f['target']} — {f['detail']}\n"
        )
    if report.get("ok"):
        sys.stdout.write("OK\n")
    else:
        sys.stdout.write("FAIL\n")


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(
            "Usage: _validate_registry.py [--json]\n\n"
            "Validate that wicked-garden in-code allowlists "
            "(phases, reviewers, bus handlers, skill refs) point to "
            "assets that actually exist on disk / in catalog.\n\n"
            "Exit code: 0 = clean, 1 = blocking findings, 2 = unexpected error.\n"
        )
        return 0
    try:
        report = run_all_checks()
    except Exception as exc:  # pragma: no cover — defensive
        sys.stderr.write(
            f"_validate_registry: unexpected error: {type(exc).__name__}: {exc}\n"
        )
        return 2
    _emit(report, as_json=as_json)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
