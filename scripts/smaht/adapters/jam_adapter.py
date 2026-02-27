"""
wicked-jam adapter for wicked-smaht.

Queries brainstorming session summaries and insights.
Uses direct import of jam.jam since all scripts are co-located.
"""

import sys
from datetime import datetime, timezone
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

# Direct import of the jam module (co-located under scripts/jam/)
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from jam.jam import list_sessions


def _get_sessions(query: str, project: str = None) -> list:
    """Synchronous jam session list — called via run_in_thread for async."""
    try:
        data = list_sessions(query=query[:500], limit=10, project=project)
        return data.get("sessions", [])
    except Exception:
        return []


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-jam sessions for relevant brainstorms."""
    items = []

    sessions = await run_in_thread(_get_sessions, prompt, project)

    now = datetime.now(timezone.utc)
    prompt_lower = prompt.lower()

    for session in sessions:
        topic = session.get("topic", "")
        summary = session.get("summary", "")
        created = session.get("created", "")

        # Calculate age
        age_days = 0
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_days = (now - created_dt).days
            except Exception:
                pass

        # Relevance scoring
        topic_lower = topic.lower()
        summary_lower = summary.lower()
        semantic_score = 0.3
        for word in prompt_lower.split():
            if len(word) > 3:
                if word in topic_lower:
                    semantic_score += 0.3
                if word in summary_lower:
                    semantic_score += 0.1
        semantic_score = min(semantic_score, 1.0)

        if semantic_score > 0.3:
            items.append(ContextItem(
                id=session.get("id", ""),
                source="jam",
                title=f"Brainstorm: {topic}",
                summary=summary[:200] if summary else f"Session with {session.get('perspectives_count', 0)} perspectives",
                excerpt=summary,
                age_days=age_days,
                metadata={
                    "topic": topic,
                    "perspectives_count": session.get("perspectives_count", 0),
                    "semantic_score": semantic_score,
                }
            ))

    return items
