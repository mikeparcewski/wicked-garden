"""
wicked-jam adapter for wicked-smaht.

Queries brainstorming session summaries and insights via Control Plane.
"""

import sys
from datetime import datetime, timezone
from typing import List

from . import ContextItem, _SCRIPTS_ROOT, run_in_thread

if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from _control_plane import get_client


def _get_sessions(query: str, project: str = None) -> list:
    """Query CP for jam sessions."""
    try:
        cp = get_client()
        params = {}
        if query:
            params["q"] = query[:500]
        if project:
            params["project"] = project

        resp = cp.request("wicked-jam", "sessions", "list", params=params or None)
        if resp and isinstance(resp.get("data"), list):
            return resp["data"]
        return []
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
        summary = session.get("summary", "") or session.get("synthesis", {}).get("summary", "")
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
            perspectives_count = session.get("perspectives_count", 0)
            if not perspectives_count:
                perspectives = session.get("perspectives", [])
                perspectives_count = len(perspectives) if isinstance(perspectives, list) else 0

            items.append(ContextItem(
                id=session.get("id", ""),
                source="jam",
                title=f"Brainstorm: {topic}",
                summary=summary[:200] if summary else f"Session with {perspectives_count} perspectives",
                excerpt=summary,
                age_days=age_days,
                metadata={
                    "topic": topic,
                    "perspectives_count": perspectives_count,
                    "semantic_score": semantic_score,
                }
            ))

    return items
