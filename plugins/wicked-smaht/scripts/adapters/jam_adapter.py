"""
wicked-jam adapter for wicked-smaht.

Queries brainstorming session summaries and insights.
"""

import json
import sys
from datetime import datetime, timezone
from typing import List

from . import ContextItem, discover_script, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-jam sessions for relevant brainstorms."""
    items = []

    jam_script = discover_script("wicked-jam", "jam.py")
    if not jam_script:
        return items

    cmd = [sys.executable, str(jam_script), "list-sessions",
           "--query", prompt[:500], "--limit", "10", "--json"]
    if project:
        cmd.extend(["--project", project])

    returncode, stdout, stderr = await run_subprocess(cmd, timeout=5.0)

    if returncode == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            sessions = data.get("sessions", [])

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
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-jam JSON parse failed: {e}", file=sys.stderr)
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-jam query failed: {stderr}", file=sys.stderr)

    return items
