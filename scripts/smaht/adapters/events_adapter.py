"""
Event log adapter for wicked-smaht context assembly.

Queries the unified event log (events.db) for recent cross-domain activity
relevant to the current prompt. Surfaces crew phase transitions, jam decisions,
kanban task changes, and other domain events alongside traditional context sources.

This adapter complements brain_adapter (which queries memories) by providing
the broader activity timeline that memories alone don't capture.
"""

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
    "tasks.": 0.1,        # Kanban changes
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
                import json as _json
                payload_dict = _json.loads(payload)
            except Exception:
                pass

        # Filter: skip tasks.created events that have no meaningful name.
        # Bare UUID record_id entries without a name add noise to briefings.
        if action == "tasks.created":
            task_name = payload_dict.get("name", "") if payload_dict else ""
            if not task_name or not task_name.strip():
                continue

        # Build title and summary
        title = f"{domain}.{action}"
        summary_parts = []

        # For tasks.created, surface the task name instead of the raw UUID
        if action == "tasks.created" and payload_dict.get("name"):
            task_name = payload_dict["name"].strip()
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

        # Score: base + action boost + keyword match + recency
        base = 0.15
        action_score = _action_boost(action)
        keyword_score = 0.0
        search_text = f"{title} {summary} {record_id} {project_id}".lower()
        for word in prompt_lower.split():
            if len(word) > 2 and word in search_text:
                keyword_score += 0.1

        age = _age_days(ts)
        recency_boost = max(0.0, 0.15 - (age / 30) * 0.15)  # 0.15 for today, 0 for 30d ago

        relevance = min(base + action_score + keyword_score + recency_boost, 1.0)

        items.append(ContextItem(
            id=event.get("event_id", ""),
            source="events",
            title=title,
            summary=summary,
            excerpt=(
                f"[{ts[:10]}] {title}"
                if (action == "tasks.created" and payload_dict.get("name"))
                else (f"[{ts[:10]}] {title}: {record_id}" if record_id else f"[{ts[:10]}] {title}")
            ),
            relevance=relevance,
            age_days=age,
            metadata={
                "domain": domain,
                "action": action,
                "project_id": project_id,
                "event_ts": ts,
            },
        ))

    # Sort by relevance descending
    items.sort(key=lambda x: x.relevance, reverse=True)
    return items[:10]
