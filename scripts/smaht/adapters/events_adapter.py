"""
Event log adapter for wicked-smaht context assembly.

Queries the unified event log (events.db) for recent cross-domain activity
relevant to the current prompt. Surfaces crew phase transitions, jam decisions,
kanban task changes, and other domain events alongside traditional context sources.

This adapter complements brain_adapter (which queries memories) by providing
the broader activity timeline that memories alone don't capture.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))


_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "can",
    "may", "might", "must", "i", "you", "we", "they", "me", "my", "your",
    "this", "that", "these", "those", "what", "which", "who", "how", "why",
    "when", "where", "and", "or", "but", "if", "for", "of", "to", "from",
    "in", "on", "at", "by", "with", "about", "not", "so", "just", "also",
})

# Action patterns that indicate high-value events for context
_HIGH_VALUE_ACTIONS = {
    "phases.": 0.3,       # Crew phase transitions
    "projects.created": 0.25,
    "sessions.created": 0.2,  # Jam sessions
    "memories.created": 0.15,
    "tasks.": 0.1,        # Kanban changes (base; event_type may boost further)
}

# Event type boosts (for kanban events carrying event_type in payload)
_EVENT_TYPE_BOOSTS = {
    "gate-finding": 0.4,
    "phase-transition": 0.35,
    "procedure-trigger": 0.3,
    "coding-task": 0.2,
    "subtask": 0.15,
    "task": 0.0,  # regular tasks get no extra boost
}


def _extract_keywords(prompt: str) -> str:
    words = prompt.lower().split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords[:6]) if keywords else ""


def _query_events(prompt: str) -> list:
    """Query EventStore for relevant events. Runs in thread pool."""
    try:
        from _event_store import EventStore
        EventStore.ensure_schema()

        results = []

        # Strategy 1: FTS search with prompt keywords
        keywords = _extract_keywords(prompt)
        if keywords:
            fts_results = EventStore.query(fts=keywords, since="30d", limit=10)
            results.extend(fts_results)

        # Strategy 2: Recent high-value events (last 7 days)
        recent = EventStore.query(since="7d", limit=20)
        seen_ids = {r.get("event_id") for r in results}
        for event in recent:
            if event.get("event_id") not in seen_ids:
                results.append(event)

        return results[:15]  # Cap total

    except Exception:
        return []


def _action_boost(action: str) -> float:
    """Score boost based on action type."""
    for prefix, boost in _HIGH_VALUE_ACTIONS.items():
        if action.startswith(prefix):
            return boost
    return 0.0


def _chain_boost(payload_dict: dict, active_chain_id: "str | None") -> float:
    """Score boost when event belongs to the active chain.

    Chain-matched events score 0.65 base boost (combined with 0.15 base → 0.8 total).
    Partial chain prefix match (parent chain) scores 0.45.
    No chain match: 0.0.
    """
    if not active_chain_id:
        return 0.0
    event_chain = payload_dict.get("chain_id", "")
    if not event_chain:
        return 0.0
    if event_chain == active_chain_id:
        return 0.65
    # Parent chain match: active is a.b.c, event is a.b → partial match
    if active_chain_id.startswith(event_chain + "."):
        return 0.45
    # Child chain match: active is a.b, event is a.b.c → also relevant
    if event_chain.startswith(active_chain_id + "."):
        return 0.50
    return 0.0


def _get_active_chain_id() -> "str | None":
    """Read active chain_id from session state."""
    try:
        from _session import SessionState
        state = SessionState.load()
        return getattr(state, "active_chain_id", None)
    except Exception:
        return None


def _age_days(ts_str: str) -> float:
    """Calculate age in days from ISO timestamp."""
    try:
        event_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - event_time
        return max(delta.total_seconds() / 86400, 0.0)
    except Exception:
        return 30.0  # Default to old if unparseable


async def query(prompt: str) -> List[ContextItem]:
    """Query unified event log for cross-domain activity relevant to prompt.

    Returns ContextItems tagged with source="events" so the context assembler
    can distinguish event-sourced context from memory or domain-sourced context.
    """
    events = await run_in_thread(_query_events, prompt)
    if not events:
        return []

    active_chain_id = await run_in_thread(_get_active_chain_id)

    items: list[ContextItem] = []
    prompt_lower = prompt.lower()

    for event in events:
        domain = event.get("domain", "unknown")
        action = event.get("action", "unknown")
        record_id = event.get("record_id", "")
        ts = event.get("ts", "")
        payload = event.get("payload", "")
        project_id = event.get("project_id", "")

        # Parse payload if it's a JSON string
        payload_dict: dict = {}
        if payload and isinstance(payload, str):
            try:
                payload_dict = json.loads(payload)
            except Exception:
                pass

        # Build title and summary
        title = f"{domain}.{action}"
        summary_parts = []

        if action == "tasks.created":
            task_name = payload_dict.get("name", "").strip()
            if not task_name:
                continue  # skip bare UUID entries — no meaningful name
            title = f"{domain}.{action}: {task_name}"
            summary_parts.append(task_name)
        else:
            if record_id:
                summary_parts.append(record_id)
            if project_id:
                summary_parts.append(f"project: {project_id}")
            if payload and isinstance(payload, str) and len(payload) < 200:
                summary_parts.append(payload)

        summary = " | ".join(summary_parts) if summary_parts else action

        # Score: base + action boost + event_type boost + keyword match + recency + chain
        base = 0.15
        action_score = _action_boost(action)
        event_type_val = payload_dict.get("event_type", "task")
        event_type_score = _EVENT_TYPE_BOOSTS.get(event_type_val, 0.0)
        keyword_score = 0.0
        search_text = f"{title} {summary} {record_id} {project_id}".lower()
        for word in prompt_lower.split():
            if len(word) > 2 and word in search_text:
                keyword_score += 0.1

        age = _age_days(ts)
        recency_boost = max(0.0, 0.15 - (age / 30) * 0.15)  # 0.15 for today, 0 for 30d ago

        chain_score = _chain_boost(payload_dict, active_chain_id)
        relevance = min(
            base + action_score + event_type_score + keyword_score + recency_boost + chain_score,
            1.0,
        )

        items.append(ContextItem(
            id=event.get("event_id", ""),
            source="events",
            title=title,
            summary=summary,
            excerpt=(
                f"[{ts[:10]}] {title}"
                if action == "tasks.created"
                else (f"[{ts[:10]}] {title}: {record_id}" if record_id else f"[{ts[:10]}] {title}")
            ),
            relevance=relevance,
            age_days=age,
            metadata={
                "domain": domain,
                "action": action,
                "project_id": project_id,
                "event_ts": ts,
                "chain_id": payload_dict.get("chain_id", ""),
            },
        ))

    # Sort by relevance descending
    items.sort(key=lambda x: x.relevance, reverse=True)
    return items[:10]
