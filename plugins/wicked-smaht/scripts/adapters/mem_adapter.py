"""
wicked-mem adapter for wicked-smaht.

Queries memories, decisions, and procedural knowledge.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from . import ContextItem, discover_script, run_subprocess


async def query(prompt: str, project: str = None) -> List[ContextItem]:
    """Query wicked-mem for relevant memories."""
    items = []

    mem_script = discover_script("wicked-mem", "memory.py")
    if not mem_script:
        return items

    # Query memories using async subprocess
    cmd = [sys.executable, str(mem_script), "recall", "--query", prompt[:500], "--limit", "5", "--json"]
    returncode, stdout, stderr = await run_subprocess(cmd, timeout=5.0)

    if returncode == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            memories = data.get("memories", [])

            now = datetime.now(timezone.utc)
            for mem in memories:
                created = mem.get("created", "")
                age_days = 0
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age_days = (now - created_dt).days
                    except Exception:
                        pass

                # Boost relevance based on memory type — decisions and
                # preferences contain project constraints that prevent
                # wrong-approach errors (e.g. "use GCP not local PostgreSQL")
                mem_type = mem.get("type", "episodic")
                tags = mem.get("tags", [])
                type_boost = {
                    "decision": 0.3,
                    "preference": 0.3,
                    "procedural": 0.1,
                    "working": 0.4 if "goal" in tags else 0.2,
                    "episodic": 0.0,
                }.get(mem_type, 0.0)
                relevance = min(0.5 + type_boost, 1.0)

                items.append(ContextItem(
                    id=mem.get("id", ""),
                    source="mem",
                    title=mem.get("title", mem.get("type", "Memory")),
                    summary=mem.get("content", "")[:200],
                    excerpt=mem.get("content", ""),
                    relevance=relevance,
                    age_days=age_days,
                    metadata={
                        "type": mem_type,
                        "tags": tags,
                        "semantic_score": relevance,
                    }
                ))
        except json.JSONDecodeError as e:
            print(f"Warning: wicked-mem JSON parse failed: {e}", file=sys.stderr)
    elif stderr and stderr != "timeout":
        print(f"Warning: wicked-mem query failed: {stderr}", file=sys.stderr)

    return items
