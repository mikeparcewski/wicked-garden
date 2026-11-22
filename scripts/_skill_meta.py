#!/usr/bin/env python3
"""_skill_meta.py — the ONE reader of a skill's identity: its cross-CLI role.

A skill's role used to be inferred from Claude-only frontmatter (``context: fork`` = a
dispatchable worker) by 25 independent line-scanners across scripts/, hooks/ and tests/. The
cross-CLI skill format (docs/cross-cli-skill-format.md) declares it instead::

    metadata:
      role: worker | router | module | floor

* ``worker`` — a dispatchable specialist (the former agents/, now ``skills/<domain>-<role>/``);
  the only role loaders register as an AgentProfile / crew phase worker.
* ``router`` — an operator-facing entry point (``skills/<domain>/SKILL.md``); listed in help.
* ``module`` — NOT an entry point: a nested reference module a router/worker pulls in, or a
  retired redirect stub (the same meaning wicked-crew's ``skillKindOf`` gives ``module``).
* ``floor`` — a discipline every governed unit is handed (``wicked-garden-governed-worker``);
  never dispatchable, never an AgentProfile, exempt from the router line cap like a worker.

Transition: until the qe batches add ``metadata.role`` everywhere, the legacy keys are
INFERRED with crew's exact fallback order — ``context: fork`` → worker, ``user-invocable: true``
→ router, else module. A declared ``metadata.role`` always wins; an unknown declared value is
``module`` (never a silent worker). Every consumer that keyed on ``context: fork`` calls
:func:`skill_role` — one helper, one answer.

stdlib-only (hooks import it); the parser is the same line-scan subset the repo's other
frontmatter readers use, plus the nested ``metadata:`` mapping.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: The closed role set. Order is documentation, not precedence.
ROLES: tuple[str, ...] = ("worker", "router", "module", "floor")

#: The closed cross-CLI frontmatter key set (top level). Anything else is a Claude Code
#: plugin hint (``context``, ``subagent_type``, ``allowed-tools``, ``model``, ``effort``,
#: ``max-turns``, ``color``, ``user-invocable``, ``phase_relevance``, …) no other CLI reads.
CLOSED_KEYS: frozenset[str] = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "mandates"}
)

#: ``metadata`` is string → string. Documented keys (others are allowed, all strings).
METADATA_KEYS: tuple[str, ...] = ("role", "phases", "archetypes", "roles")

#: ``metadata`` key ← legacy top-level key it replaces (transition fallback).
METADATA_LEGACY: dict[str, str] = {
    "phases": "phase_relevance",
    "archetypes": "archetype_relevance",
}

_FENCE = "---"
_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$")
_NESTED_KEY_RE = re.compile(r"^[ \t]+([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """``(frontmatter block without fences, body)``; ``(None, text)`` when there is none
    (no leading fence, or no closing fence — a half-open block is not frontmatter)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != _FENCE:
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _FENCE:
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


#: A block scalar header: ``|`` or ``>``, then an optional indentation indicator and chomping
#: indicator in either order (YAML 1.2 §8.1.1), then an optional comment.
_BLOCK_HEADER_RE = re.compile(r"^([|>])(?:([1-9])([+-])?|([+-])([1-9])?)?(?:\s+#.*)?$")


def _block_scalar(header: str, lines: list[str]) -> str:
    """The value of a ``|`` / ``>`` block scalar as YAML 1.2 (§8.1) reads it, from its content lines.

    The content indentation is the indicator's, else the first non-blank line's; it is stripped from
    every line and any extra indentation is kept. Blank lines are kept. ``>`` folds a single line
    break between two plain lines into a space, keeps N blank lines as N breaks, and keeps the breaks
    around a more-indented line. Chomping: clip (default) ends with one newline, ``-`` with none,
    ``+`` keeps every trailing one. Lines are already confined to the scalar by the caller."""
    m = _BLOCK_HEADER_RE.match(header)
    style = m.group(1)
    digit = m.group(2) or m.group(5)
    chomp = m.group(3) or m.group(4) or ""
    if digit:
        indent = int(digit)
    else:
        first = next((ln for ln in lines if ln.strip()), "")
        indent = len(first) - len(first.lstrip(" "))
    body = [ln[indent:] if ln.strip() else "" for ln in lines]
    trailing = 0
    while body and body[-1] == "":
        body.pop()
        trailing += 1
    if style == "|":
        text = "\n".join(body)
    else:
        text, prev, empties = "", None, 0
        for ln in body:
            if ln == "":
                empties += 1
                continue
            if prev is None:
                text = "\n" * empties + ln
            elif prev[:1] in (" ", "\t") or ln[:1] in (" ", "\t"):
                text += "\n" * (empties + 1) + ln
            else:
                text += ("\n" * empties if empties else " ") + ln
            prev, empties = ln, 0
    if not body:
        return "\n" * trailing if chomp == "+" else ""
    if chomp == "-":
        return text
    if chomp == "+":
        return text + "\n" * (trailing + 1)
    return text + "\n"


def _fold_flow(lines: list[str]) -> str:
    """A plain or quoted scalar continued on indented lines, folded as YAML folds flow lines: one line
    break between text lines is a space, N blank lines are N breaks, and each line is trimmed. Escapes
    inside a double-quoted value are not decoded (a length check then over-counts, never under-counts)."""
    out, empties = "", 0
    for i, ln in enumerate(lines):
        t = ln.strip()
        if not t:
            empties += 1
            continue
        out = t if i == 0 else out + ("\n" * empties if empties else " ") + t
        empties = 0
    return out


def parse_frontmatter(block: str | None) -> dict[str, Any]:
    """Parse the YAML subset skill frontmatter uses.

    Top-level ``key: value`` → ``str`` (quotes stripped; first occurrence wins); a value continued on
    indented lines is folded as YAML folds it; ``key: |`` / ``key: >`` block scalars → the text YAML
    reads (:func:`_block_scalar`: blank lines, extra indentation and the final newline kept, as the
    skills publish's ``yaml.safe_load`` keeps them, so a length check measures what ships);
    ``key:`` followed by ``- item`` lines → ``list``;
    ``metadata:`` followed by indented ``k: v`` lines → ``dict[str, str]`` under ``"metadata"``.
    Anything else indented is continuation of the key above it and is not a key of its own.
    """
    out: dict[str, Any] = {}
    if not block:
        return out
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t", "-")):
            i += 1
            continue
        m = _KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2)
        j = i + 1
        sub: list[str] = []
        while j < len(lines) and (
            not lines[j].strip()
            or lines[j].startswith((" ", "\t"))
            or (val == "" and lines[j].startswith("- "))
        ):
            sub.append(lines[j])
            j += 1
        if key == "metadata":
            meta: dict[str, str] = {}
            if val == "":
                for s in sub:
                    mm = _NESTED_KEY_RE.match(s)
                    if mm:
                        meta.setdefault(mm.group(1), _unquote(mm.group(2)))
            out.setdefault("metadata", meta)
        elif _BLOCK_HEADER_RE.match(val):
            out.setdefault(key, _block_scalar(val, sub))
        elif val == "" and sub:
            items = [s.strip()[2:].strip() for s in sub if s.strip().startswith("- ")]
            out.setdefault(key, [_unquote(x) for x in items] if items else "\n".join(sub).strip())
        elif any(s.strip() for s in sub):
            out.setdefault(key, _unquote(_fold_flow([val, *sub])))
        else:
            out.setdefault(key, _unquote(val))
        i = j
    return out


def read_frontmatter(path: Path | str) -> dict[str, Any]:
    """Frontmatter of the file at ``path``; ``{}`` when unreadable or absent."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    block, _ = split_frontmatter(text)
    return parse_frontmatter(block) if block is not None else {}


def declared_role(fm: dict[str, Any] | None) -> str | None:
    """``metadata.role`` as written (stripped), or None when the skill declares none."""
    if not fm:
        return None
    meta = fm.get("metadata")
    if not isinstance(meta, dict):
        return None
    role = meta.get("role")
    if role is None:
        return None
    role = _unquote(str(role).strip())
    return role or None


def skill_role(fm: dict[str, Any] | str | None) -> str:
    """The skill's role: ``worker`` | ``router`` | ``module`` | ``floor``.

    ``fm`` is a parsed frontmatter dict (:func:`parse_frontmatter`) or the raw frontmatter
    block. Precedence: a declared ``metadata.role`` (an unknown value reads ``module`` — never a
    silent worker); else the legacy inference ``context: fork`` → worker, ``user-invocable:
    true`` → router, else module (wicked-crew's ``skillKindOf`` fallback order).
    """
    if fm is None:
        return "module"
    if isinstance(fm, str):
        fm = parse_frontmatter(fm)
    declared = declared_role(fm)
    if declared is not None:
        return declared if declared in ROLES else "module"
    if str(fm.get("context", "")).strip() == "fork":
        return "worker"
    if str(fm.get("user-invocable", "")).strip().lower() == "true":
        return "router"
    return "module"


def skill_role_of(path: Path | str) -> str:
    """:func:`skill_role` of the SKILL.md at ``path`` (``module`` when unreadable)."""
    return skill_role(read_frontmatter(path))


def is_worker(fm: dict[str, Any] | str | None) -> bool:
    """True only for the dispatchable role — the one loaders and registries admit."""
    return skill_role(fm) == "worker"


def metadata_value(fm: dict[str, Any] | None, key: str) -> str | None:
    """``metadata.<key>`` (string), falling back to the legacy top-level key it replaces
    (``phases`` ← ``phase_relevance``, ``archetypes`` ← ``archetype_relevance``) while the
    catalog transitions. A legacy list is joined with ``,``."""
    if not fm:
        return None
    meta = fm.get("metadata")
    if isinstance(meta, dict) and meta.get(key) not in (None, ""):
        return str(meta[key])
    legacy = METADATA_LEGACY.get(key)
    if legacy and fm.get(legacy) not in (None, ""):
        val = fm[legacy]
        if isinstance(val, list):
            return ",".join(str(v) for v in val)
        return str(val).strip("[]")
    return None


def claude_only_keys(fm: dict[str, Any] | None) -> list[str]:
    """Top-level frontmatter keys outside the closed cross-CLI set — Claude Code plugin hints
    no other CLI reads (the ``claude-frontmatter-key`` lint token)."""
    if not fm:
        return []
    return sorted(k for k in fm if k not in CLOSED_KEYS)
