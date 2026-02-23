#!/usr/bin/env python3
"""
UserPromptSubmit hook - Three jobs:
1. Capture session goal on first substantive prompt (goal tracking)
2. Inject relevant memories when the user asks about past context (recall)
3. Periodically nudge Claude to store learnings from recent work (storage)
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Add scripts to path
plugin_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(plugin_root / "scripts"))
sys.path.insert(0, str(plugin_root / "hooks" / "scripts"))

from memory import MemoryStore, MemoryStatus

# How often to nudge for storage (every N real user messages)
STORAGE_NUDGE_INTERVAL = 10


# Patterns that signal need for historical context
CONTEXT_SIGNALS = [
    # Past decisions
    r"why did (we|you|i)",
    r"what did (we|you) decide",
    r"what was the (decision|rationale|reason)",
    r"remind me (why|what|how)",

    # Previous work
    r"last time",
    r"before when",
    r"previously",
    r"earlier (we|you|i)",
    r"we already",
    r"we had",

    # Patterns/approaches
    r"how do we (usually|normally|typically)",
    r"what('s| is) (our|the) (approach|pattern|convention)",
    r"standard (way|approach|pattern)",

    # Explicit memory
    r"(do you )?remember",
    r"recall",
    r"what do you know about",
    r"any (context|history|background) on",

    # Continuity
    r"where (were|did) we",
    r"what were we",
    r"picking up from",
    r"continuing from",
]


def strip_system_tags(text: str) -> tuple[str, bool]:
    """Remove system-generated content before processing."""
    if not text:
        return "", True

    patterns = [
        r'<task-notification>[\s\S]*?</task-notification>',
        r'<system-reminder>[\s\S]*?</system-reminder>',
        r'<command-message>[\s\S]*?</command-message>',
        r'<command-name>[\s\S]*?</command-name>',
        r'<command-args>[\s\S]*?</command-args>',
    ]

    result = text
    for p in patterns:
        result = re.sub(p, '', result, flags=re.DOTALL | re.IGNORECASE)
    result = result.strip()

    return result, len(result) == 0


def needs_context(prompt: str) -> bool:
    """Check if prompt signals need for historical context."""
    prompt_lower = prompt.lower()
    return any(re.search(p, prompt_lower) for p in CONTEXT_SIGNALS)


def extract_keywords(text: str) -> list:
    """Extract meaningful keywords from text."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "can", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
        "who", "whom", "how", "why", "when", "where", "and", "or", "but", "if",
        "then", "else", "for", "of", "to", "from", "in", "on", "at", "by",
        "with", "about", "into", "through", "during", "before", "after",
        "above", "below", "between", "under", "again", "further", "once",
        "here", "there", "all", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
        "very", "just", "also", "now", "please", "help", "me", "my", "want",
        "need", "like", "get", "make", "let", "show", "tell", "give",
        "remember", "recall", "know", "did", "were", "last", "time"
    }

    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', text.lower())
    keywords = []
    seen = set()
    for word in words:
        if word not in stop_words and len(word) > 2 and word not in seen:
            keywords.append(word)
            seen.add(word)

    return keywords[:8]


def get_turn_counter_path() -> Path:
    """Get path to turn counter file (per-session, in temp dir)."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-mem-turns-{session_id}"


def increment_turn_counter() -> int:
    """Increment and return the turn count for this session."""
    counter_file = get_turn_counter_path()
    try:
        count = int(counter_file.read_text().strip()) + 1
    except (FileNotFoundError, ValueError):
        count = 1
    counter_file.write_text(str(count))
    return count


def get_goal_path() -> Path:
    """Get path to session goal file."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    return Path(tempfile.gettempdir()) / f"wicked-mem-goal-{session_id}"


def capture_session_goal(prompt: str, turn_count: int):
    """On early turns, capture the session goal as working memory.

    The first substantive user prompt typically states the session
    objective. Storing it as working memory (1-day TTL) with a 'goal'
    tag lets wicked-smaht surface it throughout the session, preventing
    Claude from drifting away from the original intent.
    """
    goal_path = get_goal_path()

    # Only capture on turns 1-2, and only once per session
    if turn_count > 2 or goal_path.exists():
        return

    # Skip very short prompts — not substantive goals
    if len(prompt) < 20:
        return

    # Extract a goal summary (first 200 chars of the cleaned prompt)
    goal_summary = prompt[:200].strip()
    if len(prompt) > 200:
        goal_summary += "..."

    # Store as working memory with goal tag
    try:
        from memory import MemoryType, Importance
        project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
        store = MemoryStore(project)
        store.store(
            title="Session Goal",
            content=goal_summary,
            type=MemoryType.WORKING,
            tags=["goal", "session-intent"],
            importance=Importance.MEDIUM,
        )
        # Mark that we captured the goal for this session
        goal_path.write_text(goal_summary)
    except Exception:
        pass  # Never fail on goal capture


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        prompt = input_data.get("prompt", "")

        if not prompt or len(prompt) < 10:
            print(json.dumps({"continue": True}))
            return

        # Strip system tags before processing
        cleaned_prompt, was_fully_system = strip_system_tags(prompt)

        if was_fully_system:
            print(json.dumps({"continue": True}))
            return

        # Track turns for periodic storage nudge
        turn_count = increment_turn_counter()

        # Capture session goal on early turns
        capture_session_goal(cleaned_prompt, turn_count)
        storage_nudge = ""
        if turn_count > 0 and turn_count % STORAGE_NUDGE_INTERVAL == 0:
            storage_nudge = (
                "[Memory] Checkpoint: If recent work produced any decisions, gotchas, "
                "or reusable patterns, store them now with /wicked-mem:store."
            )

        # --- Memory injection ---
        # Two triggers:
        #   1. Explicit context signals ("remember", "last time", …)
        #   2. Topical relevance — prompt keywords match stored memories
        #      even when the user doesn't ask for recall explicitly.
        keywords = extract_keywords(cleaned_prompt)
        explicit_recall = needs_context(cleaned_prompt)

        if keywords:
            pattern = "|".join(keywords[:5])
            project = os.environ.get("CLAUDE_PROJECT_NAME") or Path.cwd().name
            store = MemoryStore(project)
            memories = store.search(pattern)
            memories = [m for m in memories if m.status == MemoryStatus.ACTIVE.value]

            if not explicit_recall:
                # For implicit (topical) injection, require at least one
                # keyword to appear in a memory's tags (or title) so we
                # stay precise.  Allow substring matches so e.g. keyword
                # "auth" hits tag "authentication".
                def _topically_relevant(m):
                    lowered_tags = [t.lower() for t in m.tags]
                    title_lower = m.title.lower()
                    for kw in keywords:
                        if any(kw in tag for tag in lowered_tags):
                            return True
                        if kw in title_lower:
                            return True
                    return False

                memories = [m for m in memories if _topically_relevant(m)]

            memories = memories[:2]

            if memories:
                lines = ["[Memory] Relevant:"]
                for m in memories:
                    lines.append(f"  [{m.type}] {m.title}: {m.summary[:100]}...")
                if storage_nudge:
                    lines.append(storage_nudge)
                print(json.dumps({
                    "continue": True,
                    "systemMessage": "\n".join(lines)
                }))
                return

        # No recall needed — emit storage nudge if it's time, otherwise pass through
        if storage_nudge:
            print(json.dumps({
                "continue": True,
                "systemMessage": storage_nudge
            }))
        else:
            print(json.dumps({"continue": True}))

    except Exception:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
