#!/usr/bin/env python3
"""
Session-fact extractor over native Claude tasks.

Replaces the smaht/v2 FactExtractor + HistoryCondenser turn-log pipeline
that was deleted in Gate 4 Phase 2 of the v6 rebuild (#428). Reads native
tasks written by TaskCreate/TaskUpdate to
${CLAUDE_CONFIG_DIR:-~/.claude}/tasks/{session_id}/*.json and extracts
session-level facts using the same heuristic patterns as the old
FactExtractor.

Source of truth shift:
- v5: wicked-smaht session directory turn log (user/assistant messages)
- v6: native task records (subject + description, filtered to completed)

The emission shape on wicked-bus stays the same — `wicked.garden.fact.extracted`
events with {type, content, entities, source, session_id} — so the brain
auto-memorize subscriber is unaffected.

Fact types (mirrors brain auto-memorize policy):
- decision    — "decided on X", "chose Y", "let's use Z"
- discovery   — "found that X", "turns out Y"
- artifact    — "created X", "wrote Y"
- problem_solved — "fixed X", "resolved Y"
- context     — "the system uses X", "currently running Y"

Only `decision` and `discovery` are emittable (brain re-filters).

stdlib-only. Fails open — returns [] on any I/O or parse error.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


FACT_TYPES = ("decision", "discovery", "artifact", "problem_solved", "context")
EMITTABLE_FACT_TYPES = frozenset({"decision", "discovery"})


@dataclass
class SessionFact:
    """A structured fact extracted from a native task record."""

    id: str
    type: str
    content: str
    entities: list = field(default_factory=list)
    source: str = "task"  # always "task" in v6 — native task origin
    timestamp: str = ""
    task_id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


# --- Extraction patterns (ported verbatim from smaht/v2/fact_extractor.py) ---

_DECISION_PATTERNS = [
    (r"let's (?:go with|use|do) ([^.!?\n]{10,100})", "decision"),
    (r"decided (?:on|to) ([^.!?\n]{10,100})", "decision"),
    (r"chose ([^.!?\n]{10,100})", "decision"),
    (r"we(?:'ll| will) use ([^.!?\n]{10,100})", "decision"),
    (r"going (?:to|with) ([^.!?\n]{10,100})", "decision"),
    (r"switched to ([^.!?\n]{10,100})", "decision"),
]

_DISCOVERY_PATTERNS = [
    (r"(?:found|discovered) (?:that |out )([^.!?\n]{10,100})", "discovery"),
    (r"turns out ([^.!?\n]{10,100})", "discovery"),
    (r"(?:realized|noticed) (?:that )?([^.!?\n]{10,100})", "discovery"),
    (r"the (?:issue|problem|root cause) (?:is|was) ([^.!?\n]{10,100})", "discovery"),
]

_ARTIFACT_PATTERNS = [
    (r"(?:created|wrote|generated|built) ([^.!?\n]{5,80})", "artifact"),
    (r"(?:added|implemented) ([^.!?\n]{5,80})", "artifact"),
]

_PROBLEM_SOLVED_PATTERNS = [
    (r"(?:fixed|resolved|solved) ([^.!?\n]{10,100})", "problem_solved"),
    (r"(?:the fix|solution) (?:is|was) ([^.!?\n]{10,100})", "problem_solved"),
]

_CONTEXT_PATTERNS = [
    (r"the system (?:uses|has|runs) ([^.!?\n]{10,80})", "context"),
    (r"currently (?:using|running|on) ([^.!?\n]{10,80})", "context"),
    (r"our (?:stack|setup|architecture) (?:is|includes) ([^.!?\n]{10,80})", "context"),
]

_ALL_PATTERNS = (
    _DECISION_PATTERNS
    + _DISCOVERY_PATTERNS
    + _ARTIFACT_PATTERNS
    + _PROBLEM_SOLVED_PATTERNS
    + _CONTEXT_PATTERNS
)


_TECH_NAMES = (
    "Redis", "Postgres", "PostgreSQL", "MySQL", "MongoDB", "SQLite",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    "React", "Vue", "Angular", "FastAPI", "Django", "Flask", "Express",
    "JWT", "OAuth", "GraphQL", "REST", "gRPC",
    "Stripe", "Kafka", "RabbitMQ", "Elasticsearch",
)

_FILE_PATH_RE = re.compile(
    r"([a-zA-Z_][a-zA-Z0-9_/.-]*\."
    r"(?:py|ts|js|tsx|jsx|json|yaml|yml|md|sql|java|go|rs|sh))\b"
)


def _extract_entities(text: str) -> list:
    """Extract entity references (files, technologies, services) from text."""
    entities: list = []

    files = _FILE_PATH_RE.findall(text)
    entities.extend(files[:5])

    for tech in _TECH_NAMES:
        if re.search(rf"\b{re.escape(tech)}\b", text, re.IGNORECASE) and tech not in entities:
            entities.append(tech)

    return entities[:8]


def _tasks_dir(session_id: str) -> Path:
    """Resolve the native tasks directory for a session.

    Honors CLAUDE_CONFIG_DIR; defaults to ~/.claude.
    """
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    if base:
        root = Path(base).expanduser()
    else:
        root = Path.home() / ".claude"
    # Sanitize session_id the same way hooks/scripts/stop.py does.
    safe = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return root / "tasks" / safe


def _iter_task_records_direct(session_id: str) -> Iterable[dict]:
    """Yield completed task records via direct file read (pre-PR-2 behaviour)."""
    tdir = _tasks_dir(session_id)
    if not tdir.exists() or not tdir.is_dir():
        return

    # Native task filenames are the numeric task id + .json. Sort numerically
    # so earlier tasks produce earlier facts (stable order for dedup).
    def _sort_key(p: Path) -> tuple:
        stem = p.stem
        try:
            return (0, int(stem))
        except ValueError:
            return (1, stem)

    for path in sorted(tdir.glob("*.json"), key=_sort_key):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("status") != "completed":
            continue
        yield data


def _iter_task_records(session_id: str) -> Iterable[dict]:
    """Yield native task JSON records for the session, oldest-first by numeric id.

    Only yields tasks whose status == 'completed'.

    Routing: WG_DAEMON_ENABLED=false → direct file read (unchanged);
             WG_DAEMON_ENABLED=true  → daemon HTTP with fallback (#596 v8-PR-2).
    """
    try:
        # _SCRIPTS_ROOT is the parent of this file's directory.
        _scripts = str(Path(__file__).resolve().parents[1])
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
        from crew._task_reader import read_session_tasks  # type: ignore[import]
        tasks = read_session_tasks(session_id, limit=500)
        for t in tasks:
            if isinstance(t, dict) and t.get("status") == "completed":
                yield t
        return
    except Exception:
        pass  # fail open — _task_reader unavailable; fall through to direct file read
    # Fallback to direct file read if import fails.
    yield from _iter_task_records_direct(session_id)


# --- Transcript source (starvation fix, task #76) ---------------------------
#
# Native task records turned out to be a starved source: TaskCreate/TaskUpdate
# files exist for almost no session, so `wicked.garden.fact.extracted` was
# never emitted (zero events in a 54MB live bus DB). The transcript the Stop
# hook already receives on stdin is the real conversation record — run the
# same patterns over its recent turns.

_TRANSCRIPT_TAIL_LINES = 400   # per-turn Stop scans the recent window; earlier
                               # turns were scanned by earlier Stops.
_TRANSCRIPT_MAX_TEXT = 8000    # cap a single message's text (defensive)


def _message_text(entry: dict) -> str:
    """Text of one transcript JSONL entry (user/assistant), '' otherwise."""
    if not isinstance(entry, dict) or entry.get("type") not in ("user", "assistant"):
        return ""
    message = entry.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content[:_TRANSCRIPT_MAX_TEXT]
    if isinstance(content, list):
        parts = [
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)[:_TRANSCRIPT_MAX_TEXT]
    return ""


def _iter_transcript_texts(transcript_path: str) -> Iterable[str]:
    """Yield user/assistant text blocks from the transcript JSONL tail."""
    try:
        path = Path(transcript_path)
        if not path.is_file():
            return
        with path.open(encoding="utf-8", errors="replace") as fh:
            tail = deque(fh, maxlen=_TRANSCRIPT_TAIL_LINES)
    except OSError:
        return
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = _message_text(entry)
        if text:
            yield text


def extract_transcript_facts(transcript_path: str, limit: int = 10) -> list:
    """Extract facts from the session transcript's recent turns.

    Same patterns and dedup as the task source; `source` is marked
    "transcript" so consumers can tell the two apart. Fails open.
    """
    if not transcript_path or limit <= 0:
        return []
    facts: list = []
    seen: set = set()
    try:
        for text in _iter_transcript_texts(transcript_path):
            for fact in _extract_from_text(text, task_id="transcript"):
                fact.source = "transcript"
                key = fact.content.lower()
                if key in seen:
                    continue
                seen.add(key)
                facts.append(fact)
                if len(facts) >= limit:
                    return facts
    except Exception as exc:  # pragma: no cover - defensive fail-open
        print(f"[wicked-mem] transcript fact extraction error: {exc}", file=sys.stderr)
    return facts


# --- Per-session emitted ledger ----------------------------------------------
#
# Stop fires every turn and the transcript is cumulative, so without a ledger
# the same fact would be re-emitted each turn. One small JSON file per session
# records the content hashes already emitted; the consumer's global
# content-hash dedup remains the cross-session guard.

def _emitted_ledger_path(session_id: str) -> Path:
    override = os.environ.get("WICKED_MEM_LEDGER_DIR")
    base = Path(override) if override else (
        Path.home() / ".something-wicked" / "wicked-garden" / "local" / "wicked-mem"
    )
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "default")[:80]
    return base / "emitted" / f"{safe}.json"


def _fact_hash(content: str) -> str:
    """Same normalization as scripts/mem/auto_memorize.content_hash."""
    normalized = re.sub(r"\s+", " ", str(content or "").strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def filter_unemitted(facts: list, session_id: str) -> list:
    """Facts whose content this session has not emitted yet. Fails open (all)."""
    try:
        raw = _emitted_ledger_path(session_id).read_text(encoding="utf-8")
        emitted = set(json.loads(raw))
    except (OSError, ValueError):
        emitted = set()
    return [f for f in facts if _fact_hash(f.content) not in emitted]


def mark_emitted(facts: list, session_id: str) -> None:
    """Record facts as emitted for this session. Fails open."""
    if not facts:
        return
    path = _emitted_ledger_path(session_id)
    try:
        emitted = set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        emitted = set()
    emitted.update(_fact_hash(f.content) for f in facts)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(emitted)), encoding="utf-8")
    except OSError:
        pass


def _extract_from_text(text: str, task_id: str) -> list:
    """Extract facts from a text block (task subject + description)."""
    if not text:
        return []

    facts: list = []
    text_lower = text.lower()
    entities = _extract_entities(text)

    for pattern, fact_type in _ALL_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches[:2]:
            if isinstance(match, tuple):
                match = " ".join(match)
            match = match.strip()
            if not match or len(match) < 5:
                continue
            facts.append(
                SessionFact(
                    id=str(uuid.uuid4())[:8],
                    type=fact_type,
                    content=match,
                    entities=entities,
                    source="task",
                    task_id=task_id,
                )
            )
    # Match the old FactExtractor cap of 5 per text block.
    return facts[:5]


def extract_session_facts(
    session_id: str,
    limit: int = 10,
    transcript_path: Optional[str] = None,
) -> list:
    """Extract session-level facts from native task records + the transcript.

    Task records come first (structured, higher precision); the transcript
    tail (when a path is provided) fills the remaining budget — that source
    is what actually feeds the pipeline in practice, since native task files
    exist for almost no session (the auto-memorize starvation, task #76).

    Returns a list of SessionFact objects (up to `limit`), deduplicated by
    lowercased content. Fails open — returns [] on any error.

    The returned shape matches what hooks/scripts/stop.py::_run_memory_promotion
    consumes: objects with `.type`, `.content`, `.entities`, `.source`.
    """
    if not session_id or limit <= 0:
        return []

    facts: list = []
    seen: set = set()

    try:
        for record in _iter_task_records(session_id):
            task_id = str(record.get("id", ""))
            subject = str(record.get("subject", "") or "")
            description = str(record.get("description", "") or "")
            # Concatenate so patterns can match across subject+description;
            # keeps entity extraction coherent within a single task.
            text = f"{subject}. {description}".strip()

            for fact in _extract_from_text(text, task_id):
                key = fact.content.lower()
                if key in seen:
                    continue
                seen.add(key)
                facts.append(fact)
                if len(facts) >= limit:
                    return facts
    except Exception as exc:  # pragma: no cover - defensive fail-open
        print(f"[wicked-mem] session fact extraction error: {exc}", file=sys.stderr)
        return facts

    if transcript_path and len(facts) < limit:
        for fact in extract_transcript_facts(transcript_path, limit - len(facts)):
            key = fact.content.lower()
            if key in seen:
                continue
            seen.add(key)
            facts.append(fact)

    return facts


def _self_test() -> int:
    """Inline self-test with a synthetic task directory."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="wg-sfe-"))
    try:
        session_id = "selftest"
        sdir = tmp / "tasks" / session_id
        sdir.mkdir(parents=True)

        # Task 1: contains a decision + an artifact
        (sdir / "1.json").write_text(json.dumps({
            "id": "1",
            "subject": "Wire facilitator",
            "description": "We decided to use the rubric approach and created facilitator.md",
            "status": "completed",
        }))
        # Task 2: pending — should be ignored
        (sdir / "2.json").write_text(json.dumps({
            "id": "2",
            "subject": "Write docs",
            "description": "Not done yet",
            "status": "pending",
        }))
        # Task 3: a discovery
        (sdir / "3.json").write_text(json.dumps({
            "id": "3",
            "subject": "Root cause",
            "description": "The issue was a race condition in the event loop",
            "status": "completed",
        }))

        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp)
        facts = extract_session_facts(session_id, limit=10)

        types = [f.type for f in facts]
        contents = [f.content for f in facts]

        assert facts, f"expected at least one fact, got {facts}"
        assert "decision" in types, f"expected a decision fact, got types={types}"
        assert "discovery" in types, f"expected a discovery fact, got types={types}"
        # pending task must not leak into facts
        assert not any("not done" in c for c in contents), (
            f"pending task leaked into facts: {contents}"
        )
        # Every fact must have a task_id linking it to its source
        assert all(f.task_id for f in facts), (
            f"facts missing task_id: {[f.to_dict() for f in facts]}"
        )

        emittable = [f for f in facts if f.type in EMITTABLE_FACT_TYPES]
        assert emittable, "expected at least one emittable (decision/discovery) fact"

        print(f"session_fact_extractor self-test: PASS ({len(facts)} facts, {len(emittable)} emittable)")
        return 0
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)


if __name__ == "__main__":
    sys.exit(_self_test())
