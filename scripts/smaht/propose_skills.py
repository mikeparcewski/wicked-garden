#!/usr/bin/env python3
"""scripts/smaht/propose_skills.py — session-mined skill builder (MVP for #677).

Read-only analyzer over Claude Code session transcripts.

Reads ``${CLAUDE_CONFIG_DIR:-~/.claude}/projects/{project-slug}/*.jsonl`` for the
current project (default: cwd basename → slug), detects repetitive patterns across
sessions, clusters overlapping detections, and writes a markdown report at
``tempfile.gettempdir()/wg-propose-skills-{timestamp}.md`` (on macOS this resolves
to a per-user dir under ``/var/folders/...``).

Hard constraints (per scope and CLAUDE.md):

* **stdlib-only** — no external deps.
* **read-only** — never writes outside ``tempfile.gettempdir()``.
* **local-only** — no network, no telemetry, no LLM calls.
* **cross-platform** — uses ``pathlib.Path`` and ``tempfile.gettempdir()``; honors
  ``CLAUDE_CONFIG_DIR`` for users running Claude Code with a non-default config.
* **privacy** — scrubs absolute paths to ``~/...`` form (matched at path-segment
  boundaries to avoid substring scrubbing), skips any session whose user prompt
  contains the literal token ``private`` or ``secret``. Privacy check runs on the
  full untruncated prompt before any 200-char trimming.

The MVP intentionally outputs a markdown report only. There is no interactive
UI and no scaffolding handoff in v1 — both are explicit v2 follow-ups
documented in the report's footer.

Usage::

    python3 scripts/smaht/propose_skills.py [--project SLUG] [--limit N]
                                            [--sessions-root PATH]
                                            [--output PATH] [--json]

Exit codes:

* ``0`` — graceful run (even when no candidates are found).
* ``1`` — failed to write the report (I/O error after analysis succeeded).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Constants — surfaced as module-level so tests can patch / inspect.
# ---------------------------------------------------------------------------

# Patterns whose first 5 normalized words are skipped as "too generic" — they
# inflate every report otherwise (e.g. continuations and approvals).
_GENERIC_PROMPT_PREFIXES: frozenset[str] = frozenset(
    {
        "yes",
        "ok",
        "okay",
        "continue",
        "go",
        "do it",
        "looks good",
        "thanks",
        "thank you",
        "sounds good",
        "lgtm",
    }
)

# Bash command first-tokens we ignore (file inspection, not workflow).
_GENERIC_BASH_TOKENS: frozenset[str] = frozenset(
    {"ls", "cat", "echo", "cd", "pwd", "true", "false", ":"}
)

# Min total occurrences (across all sessions, with intra-session repeats counted)
# before a candidate qualifies.
MIN_FREQUENCY = 3
# Min DISTINCT sessions a candidate must appear in. Frequency alone is not enough —
# a single chatty session shouldn't surface a workflow as a cross-cutting pattern.
MIN_SESSION_COUNT = 2

# Sequence detection bounds — short sequences are noisy, long sequences are rare.
SEQUENCE_MIN_LEN = 2
SEQUENCE_MAX_LEN = 5

# Privacy: skip whole sessions whose user prompts mention these tokens.
PRIVACY_SKIP_TOKENS: tuple[str, ...] = ("private", "secret")

# Cap report candidates so the markdown stays scannable.
TOP_CANDIDATES = 10

# Frontmatter description hard limit — matches Claude Code's surface convention.
DESCRIPTION_MAX_CHARS = 140

# Domain inference lookup — picks the scaffolding domain by string heuristic on
# the tool names + bash tokens that appear inside the pattern.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "platform": ("gh", "docker", "kubectl", "helm", "terraform", "aws", "gcloud"),
    "engineering": ("git", "pytest", "npm", "node", "uv", "ruff", "mypy"),
    "search": ("grep", "rg", "glob", "find"),
    "qe": ("test", "wg-test", "scenarios"),
    "data": ("psql", "sqlite", "duckdb", "jq"),
    "delivery": ("release", "changelog", "version"),
}


# ---------------------------------------------------------------------------
# Project + session discovery.
# ---------------------------------------------------------------------------


def project_slug(cwd: Path | None = None) -> str:
    """Return the Claude Code project slug for ``cwd`` (default: real cwd).

    Claude Code encodes project paths by replacing path separators with ``-``
    and prefixing with ``-``. Cross-platform: uses ``Path.as_posix()`` so
    Windows ``\\`` separators and drive letters (``C:``) are normalized before
    the substitution.

    Example (POSIX): ``/Users/x/Projects/wicked-garden`` →
    ``-Users-x-Projects-wicked-garden``.
    Example (Windows): ``C:\\Users\\x\\Projects\\wg`` → ``-C-Users-x-Projects-wg``.
    """
    base = (cwd or Path.cwd()).expanduser().resolve()
    posix = base.as_posix()
    # Strip the Windows drive colon (e.g. ``C:`` → ``C``) so the slug stays
    # filesystem-safe under Claude Code's project-dir naming convention.
    posix = posix.replace(":", "")
    return "-" + posix.strip("/").replace("/", "-")


def resolve_claude_config_dir() -> Path:
    """Return the active Claude config dir, honoring ``CLAUDE_CONFIG_DIR``.

    Falls back to ``~/.claude`` when the env var is unset or empty. Mirrors
    the convention documented in CLAUDE.md (``${CLAUDE_CONFIG_DIR:-~/.claude}``).
    """
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude"


def session_root() -> Path:
    """Return the default Claude Code session root for the active config dir."""
    return resolve_claude_config_dir() / "projects"


def default_sessions_root() -> Path:
    """Backward-compat alias for ``session_root()``. Honors ``CLAUDE_CONFIG_DIR``."""
    return session_root()


def find_session_files(
    *,
    sessions_root: Path,
    project: str,
    limit: int,
) -> list[Path]:
    """Return the ``limit`` most recently modified ``*.jsonl`` files for ``project``."""
    project_dir = sessions_root / project
    if not project_dir.is_dir():
        return []
    files = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(0, int(limit))]


# ---------------------------------------------------------------------------
# Privacy scrub.
# ---------------------------------------------------------------------------


_HOME_STR = str(Path.home())


def scrub_path(text: str, *, home: str = _HOME_STR) -> str:
    """Replace ``$HOME`` in ``text`` with ``~``, matched at path boundaries only.

    The naive ``str.replace`` approach corrupts neighbouring paths — e.g. with
    ``home='/Users/alice'`` an input ``/Users/alice2/`` would become ``~2/``.
    To avoid that, ``home`` only matches when followed by end-of-string, ``/``,
    or ``\\`` (the path-separator boundary). Idempotent — running twice on an
    already-scrubbed string is a no-op.
    """
    if not text or not home:
        return text
    pattern = re.escape(home) + r"(?=$|[/\\])"
    return re.sub(pattern, "~", text)


def _prompt_is_private(prompt: str) -> bool:
    """Return True when ``prompt`` (untruncated) contains a privacy-skip token."""
    low = (prompt or "").lower()
    for token in PRIVACY_SKIP_TOKENS:
        if token in low:
            return True
    return False


def session_is_private(user_prompts: Iterable[str]) -> bool:
    """Return ``True`` when any prompt contains a privacy-skip token (case-insensitive).

    Note: ``parse_session`` now sets a ``privacy_skip`` flag on the digest using
    the full untruncated prompt text. ``analyze`` prefers that flag, so this
    function is only consulted for tests and external callers that hand-build
    session digests.
    """
    return any(_prompt_is_private(p) for p in user_prompts)


# ---------------------------------------------------------------------------
# Session parsing.
# ---------------------------------------------------------------------------


def _extract_user_text(content: Any) -> str:
    """Return the leading text of a user message ``content`` field (str or list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                txt = item.get("text", "")
                if isinstance(txt, str) and txt.strip():
                    return txt
    return ""


def _extract_tool_uses(content: Any) -> list[dict[str, Any]]:
    """Return assistant ``tool_use`` items as ``{"name": str, "input": dict}`` records."""
    out: list[dict[str, Any]] = []
    if not isinstance(content, list):
        return out
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        name = item.get("name") or "?"
        inp = item.get("input") if isinstance(item.get("input"), dict) else {}
        out.append({"name": str(name), "input": inp})
    return out


def parse_session(path: Path) -> dict[str, Any]:
    """Parse one ``*.jsonl`` session file and return a structured digest.

    Returns ``{"path": str, "user_prompts": [...], "tool_calls": [...],
    "privacy_skip": bool}``. The privacy check inspects the FULL untruncated
    user-prompt text (so a ``private``/``secret`` token past the 200-char
    detector limit is still caught) — only after that do we trim each prompt
    to 200 chars for downstream detector economy. Robust against malformed
    lines: each bad line is skipped, never raised.
    """
    user_prompts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    privacy_skip = False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "path": str(path),
            "user_prompts": user_prompts,
            "tool_calls": tool_calls,
            "privacy_skip": privacy_skip,
        }
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        record_type = obj.get("type")
        message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        content = message.get("content") if message else None
        if record_type == "user":
            txt = _extract_user_text(content if content is not None else obj.get("message"))
            if txt:
                # Privacy gate runs on the FULL prompt — never on the truncated
                # detector view — so a trigger token past char 200 still flags.
                if not privacy_skip and _prompt_is_private(txt):
                    privacy_skip = True
                user_prompts.append(txt[:200])
        elif record_type == "assistant":
            tool_calls.extend(_extract_tool_uses(content))
    return {
        "path": str(path),
        "user_prompts": user_prompts,
        "tool_calls": tool_calls,
        "privacy_skip": privacy_skip,
    }


# ---------------------------------------------------------------------------
# Pattern detectors.
# ---------------------------------------------------------------------------


_PROMPT_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalize_prompt_prefix(prompt: str) -> str | None:
    """Return the first 5 normalized words of ``prompt`` (lowercase, no punct).

    Returns ``None`` for prompts shorter than 5 words, whose prefix is in the
    generic-prompt blocklist, or that look like a Claude Code system envelope
    rather than a user-authored prompt (e.g. ``<local-command-...>`` or
    ``<command-name>...</command-name>`` wrappers).

    The punctuation strip uses a Unicode-aware ``\\w``/``\\s`` character class
    so CJK ideographs, accented Latin characters, and other non-ASCII letters
    are preserved as part of the prefix instead of being collapsed to spaces.
    """
    if not prompt:
        return None
    stripped = prompt.lstrip()
    if stripped.startswith("<local-command") or stripped.startswith("<command-"):
        return None
    cleaned = _PROMPT_PUNCT_RE.sub(" ", prompt.lower()).strip()
    if not cleaned:
        return None
    words = cleaned.split()
    if len(words) < 5:
        return None
    prefix = " ".join(words[:5])
    if prefix in _GENERIC_PROMPT_PREFIXES:
        return None
    # Reject if first word alone is a generic single-token continuation.
    if words[0] in _GENERIC_PROMPT_PREFIXES:
        return None
    # Reject if any multi-word generic phrase ("do it", "looks good", "thank you",
    # "sounds good") appears as a substring of the normalized prefix. These never
    # match the equality check above because they're shorter than 5 words.
    for generic in _GENERIC_PROMPT_PREFIXES:
        if " " in generic and generic in prefix:
            return None
    return prefix


def _bash_first_tokens(input_dict: dict[str, Any]) -> tuple[str, ...] | None:
    """Return the first 2 tokens of a Bash command, or ``None`` for generic shapes."""
    cmd = input_dict.get("command")
    if not isinstance(cmd, str):
        return None
    tokens = cmd.strip().split()
    if len(tokens) < 2:
        return None
    head = tokens[0].lstrip("()`$\"'")
    if not head or head in _GENERIC_BASH_TOKENS:
        return None
    return (head, tokens[1])


def _is_homogeneous(tup: tuple[str, ...]) -> bool:
    """Return True when every element of ``tup`` is the same tool name.

    These are noise — e.g. ``Bash → Bash → Bash`` just means the agent ran
    several bash commands in a row, not a workflow worth automating.
    """
    return len(set(tup)) <= 1


def detect_repeated_sequences(
    sessions: list[dict[str, Any]],
    *,
    min_freq: int = MIN_FREQUENCY,
    min_len: int = SEQUENCE_MIN_LEN,
    max_len: int = SEQUENCE_MAX_LEN,
    min_sessions: int = MIN_SESSION_COUNT,
) -> list[dict[str, Any]]:
    """Detect ordered N-tuples of tool names appearing ``>= min_freq`` times.

    Tracks two independent counters per N-tuple:

    * ``frequency`` — TOTAL occurrences across all sessions (with intra-session
      repeats included). Reflects how often the agent runs the pattern overall.
    * ``sessions`` — number of DISTINCT sessions the N-tuple appears in.
      Reflects how broadly the pattern shows up across the project's history.

    A candidate must satisfy ``frequency >= min_freq`` AND
    ``sessions >= min_sessions``. Homogeneous sequences (all the same tool name)
    are filtered because they reflect run-of-the-mill repetition, not a procedure.
    """
    total_counter: Counter[tuple[str, ...]] = Counter()
    sessions_by_seq: dict[tuple[str, ...], set[str]] = defaultdict(set)
    examples: dict[tuple[str, ...], str] = {}
    for sess in sessions:
        names = [tc["name"] for tc in sess["tool_calls"]]
        sid = sess["path"]
        for n in range(min_len, max_len + 1):
            for i in range(0, max(0, len(names) - n + 1)):
                tup = tuple(names[i : i + n])
                if _is_homogeneous(tup):
                    continue
                # Count EVERY occurrence — repeats within a session count, so
                # frequency reflects true workload, not just session breadth.
                total_counter[tup] += 1
                sessions_by_seq[tup].add(sid)
                examples.setdefault(tup, " → ".join(tup))
    out: list[dict[str, Any]] = []
    for tup, freq in total_counter.items():
        sess_count = len(sessions_by_seq[tup])
        if freq < min_freq or sess_count < min_sessions:
            continue
        out.append(
            {
                "kind": "tool-sequence",
                "key": tup,
                "frequency": freq,
                "sessions": sess_count,
                "example": examples[tup],
                "names": list(tup),
            }
        )
    return out


def detect_repeated_prompt_templates(
    sessions: list[dict[str, Any]],
    *,
    min_freq: int = MIN_FREQUENCY,
    min_sessions: int = MIN_SESSION_COUNT,
) -> list[dict[str, Any]]:
    """Detect user prompts whose first 5 normalized words match across sessions.

    Tracks both total occurrences and distinct-session count (see
    ``detect_repeated_sequences`` for rationale). A candidate must satisfy
    both ``min_freq`` and ``min_sessions``.
    """
    total_counter: Counter[str] = Counter()
    sessions_by_prefix: dict[str, set[str]] = defaultdict(set)
    examples: dict[str, str] = {}
    for sess in sessions:
        sid = sess["path"]
        for prompt in sess["user_prompts"]:
            prefix = _normalize_prompt_prefix(prompt)
            if prefix is None:
                continue
            total_counter[prefix] += 1
            sessions_by_prefix[prefix].add(sid)
            examples.setdefault(prefix, prompt[:160])
    out: list[dict[str, Any]] = []
    for prefix, freq in total_counter.items():
        sess_count = len(sessions_by_prefix[prefix])
        if freq < min_freq or sess_count < min_sessions:
            continue
        out.append(
            {
                "kind": "prompt-template",
                "key": prefix,
                "frequency": freq,
                "sessions": sess_count,
                "example": examples[prefix],
            }
        )
    return out


def detect_repeated_bash_shapes(
    sessions: list[dict[str, Any]],
    *,
    min_freq: int = MIN_FREQUENCY,
    min_sessions: int = MIN_SESSION_COUNT,
) -> list[dict[str, Any]]:
    """Detect bash commands sharing the same first 2 tokens across sessions.

    Tracks both total occurrences and distinct-session count (see
    ``detect_repeated_sequences`` for rationale). A candidate must satisfy
    both ``min_freq`` and ``min_sessions``.
    """
    total_counter: Counter[tuple[str, str]] = Counter()
    sessions_by_shape: dict[tuple[str, str], set[str]] = defaultdict(set)
    examples: dict[tuple[str, str], str] = {}
    for sess in sessions:
        sid = sess["path"]
        for tc in sess["tool_calls"]:
            if tc["name"] != "Bash":
                continue
            shape = _bash_first_tokens(tc.get("input") or {})
            if shape is None:
                continue
            total_counter[shape] += 1
            sessions_by_shape[shape].add(sid)
            cmd = (tc.get("input") or {}).get("command", "")
            if isinstance(cmd, str):
                examples.setdefault(shape, cmd[:160])
    out: list[dict[str, Any]] = []
    for shape, freq in total_counter.items():
        sess_count = len(sessions_by_shape[shape])
        if freq < min_freq or sess_count < min_sessions:
            continue
        out.append(
            {
                "kind": "bash-shape",
                "key": shape,
                "frequency": freq,
                "sessions": sess_count,
                "example": examples.get(shape, " ".join(shape)),
                "names": list(shape),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Deduplication — drop sub-sequences subsumed by a more frequent super-sequence.
# ---------------------------------------------------------------------------


def _is_subsequence(short: tuple[str, ...], long: tuple[str, ...]) -> bool:
    """Return True if ``short`` appears as a contiguous subsequence of ``long``."""
    if len(short) >= len(long):
        return False
    for i in range(0, len(long) - len(short) + 1):
        if long[i : i + len(short)] == short:
            return True
    return False


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop tool-sequence candidates that are sub-sequences of a more frequent super-sequence.

    Non tool-sequence kinds pass through untouched. Among tool-sequence
    candidates, ``short`` is dropped only when a strictly longer ``long`` exists
    with frequency ``>=`` ``short.frequency`` AND ``short`` is contiguous in
    ``long`` — this preserves cases where the shorter pattern is genuinely more
    common in different contexts.
    """
    sequences = [c for c in candidates if c["kind"] == "tool-sequence"]
    others = [c for c in candidates if c["kind"] != "tool-sequence"]
    keep: list[dict[str, Any]] = []
    for short in sequences:
        short_key = tuple(short["key"])
        is_subsumed = False
        for long in sequences:
            if long is short:
                continue
            long_key = tuple(long["key"])
            if not _is_subsequence(short_key, long_key):
                continue
            if long["frequency"] >= short["frequency"]:
                is_subsumed = True
                break
        if not is_subsumed:
            keep.append(short)
    return keep + others


# ---------------------------------------------------------------------------
# Skill proposal builder — name + description + scaffolding command.
# ---------------------------------------------------------------------------


def _slugify(text: str, *, max_len: int = 48) -> str:
    """Return a kebab-case slug from ``text`` (alnum + hyphens only, no leading/trailing hyphens)."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    if not cleaned:
        cleaned = "candidate"
    return cleaned[:max_len].strip("-") or "candidate"


def infer_domain(candidate: dict[str, Any]) -> str:
    """Pick a scaffolding domain by keyword presence in the candidate's pattern."""
    haystack_parts: list[str] = []
    if candidate["kind"] == "tool-sequence":
        haystack_parts.extend(candidate.get("names", []))
    elif candidate["kind"] == "bash-shape":
        haystack_parts.extend(candidate.get("names", []))
    elif candidate["kind"] == "prompt-template":
        haystack_parts.append(str(candidate.get("key", "")))
    haystack = " ".join(haystack_parts).lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            return domain
    return "engineering"


def propose_skill(candidate: dict[str, Any]) -> dict[str, str]:
    """Return ``{"slug", "description", "scaffold_command"}`` for ``candidate``."""
    if candidate["kind"] == "tool-sequence":
        names = candidate["names"]
        slug = _slugify("auto " + "-".join(n.lower() for n in names))
        description = (
            f"Automate the recurring {' → '.join(names)} sequence "
            f"observed {candidate['frequency']}x across {candidate['sessions']} sessions."
        )
    elif candidate["kind"] == "prompt-template":
        slug = _slugify("answer " + candidate["key"])
        description = (
            f"Handle the recurring prompt template "
            f"\"{candidate['key']}…\" — observed {candidate['frequency']}x."
        )
    else:  # bash-shape
        head, second = candidate["names"]
        slug = _slugify(f"run {head} {second}")
        description = (
            f"Wrap the recurring `{head} {second} …` shell pattern — "
            f"observed {candidate['frequency']}x across {candidate['sessions']} sessions."
        )
    description = description[:DESCRIPTION_MAX_CHARS]
    domain = infer_domain(candidate)
    return {
        "slug": slug,
        "description": description,
        "domain": domain,
        "scaffold_command": f"/wg-scaffold skill {slug} --domain {domain}",
    }


# ---------------------------------------------------------------------------
# Report rendering.
# ---------------------------------------------------------------------------


def _candidate_score(c: dict[str, Any]) -> tuple[int, int, int]:
    """Sort key — frequency desc, sessions desc, length desc."""
    length = len(c.get("names", [])) if c["kind"] != "prompt-template" else 1
    return (-int(c["frequency"]), -int(c["sessions"]), -length)


def render_report(
    *,
    project: str,
    sessions_scanned: int,
    sessions_skipped: int,
    candidates: list[dict[str, Any]],
    timestamp: str,
) -> str:
    """Render the markdown report. Pure function — no I/O."""
    lines: list[str] = []
    lines.append("# Session-mined skill proposals")
    lines.append("")
    lines.append(f"_Generated: {timestamp}_")
    lines.append("")
    lines.append(
        f"**Project**: `{project}` · **Sessions scanned**: {sessions_scanned} · "
        f"**Skipped (privacy)**: {sessions_skipped} · "
        f"**Candidates**: {len(candidates)}"
    )
    lines.append("")
    if not candidates:
        lines.append("No repetitive patterns met the minimum-frequency threshold.")
        lines.append("")
        lines.append("This is normal for short or one-off projects — try `--limit 50`")
        lines.append("once you have more session history.")
        return "\n".join(lines) + "\n"
    candidates_sorted = sorted(candidates, key=_candidate_score)[:TOP_CANDIDATES]
    lines.append("## Candidates")
    lines.append("")
    for idx, c in enumerate(candidates_sorted, 1):
        proposal = propose_skill(c)
        lines.append(f"### {idx}. {proposal['slug']}")
        lines.append("")
        lines.append(f"- **Pattern kind**: `{c['kind']}`")
        # Show TOTAL occurrences and DISTINCT sessions independently — when a
        # pattern repeats inside a session, the two numbers genuinely differ.
        lines.append(
            f"- **Frequency**: {c['frequency']} total occurrences across "
            f"{c['sessions']} distinct sessions"
        )
        lines.append(f"- **Proposed description**: {proposal['description']}")
        lines.append(f"- **Suggested scaffold**: `{proposal['scaffold_command']}`")
        example = scrub_path(str(c.get("example", "")))
        lines.append("- **Example**:")
        lines.append("")
        lines.append("  ```")
        lines.append(f"  {example}")
        lines.append("  ```")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("This is the **MVP** of the session-mined skill builder (#677).")
    lines.append("")
    lines.append("- Detection is heuristic — false positives are expected. Treat each candidate as a prompt for")
    lines.append("  judgment, not a directive.")
    lines.append("- v1 is read-only and does not scaffold anything. Run the suggested `/wg-scaffold` command")
    lines.append("  yourself if a candidate looks worth building.")
    lines.append("- Interactive accept/reject UI and direct scaffolding handoff are explicit v2 / v3 follow-ups.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------


def analyze(
    *,
    sessions_root: Path,
    project: str,
    limit: int,
) -> dict[str, Any]:
    """Run end-to-end analysis and return a structured result.

    Pure orchestration — never writes to disk. ``run()`` writes the report.
    """
    files = find_session_files(sessions_root=sessions_root, project=project, limit=limit)
    parsed: list[dict[str, Any]] = []
    skipped = 0
    for f in files:
        sess = parse_session(f)
        # Prefer the per-session ``privacy_skip`` flag set by parse_session
        # (which inspects the FULL untruncated prompt). Fall back to the
        # truncated-prompt scan for digests built by external callers (tests).
        if sess.get("privacy_skip") or session_is_private(sess["user_prompts"]):
            skipped += 1
            continue
        parsed.append(sess)
    candidates = (
        detect_repeated_sequences(parsed)
        + detect_repeated_prompt_templates(parsed)
        + detect_repeated_bash_shapes(parsed)
    )
    candidates = dedupe_candidates(candidates)
    return {
        "project": project,
        "sessions_scanned": len(parsed),
        "sessions_skipped": skipped,
        "candidates": candidates,
    }


def _timestamp_slug() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _json_safe_candidate(c: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable copy of ``c`` (tuples → lists)."""
    safe: dict[str, Any] = {}
    for k, v in c.items():
        if isinstance(v, tuple):
            safe[k] = list(v)
        else:
            safe[k] = v
    return safe


def run(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code.

    * ``0`` on graceful runs (including when no candidates are found).
    * ``1`` when the report file could not be written after a successful analysis.
    """
    parser = argparse.ArgumentParser(
        prog="propose_skills",
        description="Mine recent Claude Code sessions for skill candidates (MVP, read-only).",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Claude Code project slug (default: derived from current working directory).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of most-recent sessions to scan (default: 10).",
    )
    parser.add_argument(
        "--sessions-root",
        default=None,
        help=(
            "Override the Claude session root "
            "(default: ${CLAUDE_CONFIG_DIR:-~/.claude}/projects)."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override the report output path (default: tempfile.gettempdir()/wg-propose-skills-{ts}.md).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Print the structured analysis result as JSON to stdout (in addition to "
            "the report). Includes the full candidates payload."
        ),
    )
    args = parser.parse_args(argv)

    sessions_root = (
        Path(args.sessions_root).expanduser() if args.sessions_root else default_sessions_root()
    )
    project = args.project or project_slug()
    timestamp = _timestamp_slug()

    try:
        result = analyze(sessions_root=sessions_root, project=project, limit=args.limit)
    except Exception as exc:  # pragma: no cover — last-resort safety net
        sys.stderr.write(f"propose_skills: analyze failed: {exc}\n")
        result = {
            "project": project,
            "sessions_scanned": 0,
            "sessions_skipped": 0,
            "candidates": [],
        }

    report = render_report(
        project=result["project"],
        sessions_scanned=result["sessions_scanned"],
        sessions_skipped=result["sessions_skipped"],
        candidates=result["candidates"],
        timestamp=timestamp,
    )

    if args.output:
        out_path = Path(args.output).expanduser()
    else:
        out_path = Path(tempfile.gettempdir()) / f"wg-propose-skills-{timestamp}.md"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"propose_skills: failed to write report: {exc}\n")
        return 1

    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "report_path": str(out_path),
                    "project": result["project"],
                    "sessions_root": str(sessions_root),
                    "sessions_scanned": result["sessions_scanned"],
                    "sessions_skipped": result["sessions_skipped"],
                    "candidate_count": len(result["candidates"]),
                    "candidates": [_json_safe_candidate(c) for c in result["candidates"]],
                },
                indent=2,
            )
            + "\n"
        )
    else:
        sys.stdout.write(str(out_path) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
