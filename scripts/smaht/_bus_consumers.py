#!/usr/bin/env python3
"""
smaht/_bus_consumers.py — Bus event consumers for the smaht domain.

Reacts to wicked-brain events to keep smaht caches fresh.
Poll-on-invoke pattern: called at prompt_submit hook startup.
"""

import logging
import os
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("wicked-smaht.bus-consumers")


def process_brain_events() -> List[str]:
    """Poll for brain events and invalidate caches as needed.

    Returns list of actions taken. Empty if bus unavailable.
    """
    actions = []
    try:
        from _bus import poll_pending, ack_events, is_processed, mark_processed

        events = poll_pending(event_type_prefix="wicked.brain.")
        if not events:
            return actions

        max_event_id = 0
        for event in events:
            event_id = event.get("event_id", 0)
            event_type = event.get("event_type", "")
            metadata = event.get("metadata", {})
            chain_id = metadata.get("chain_id", event_type)

            if event_id > max_event_id:
                max_event_id = event_id

            if is_processed(event_type, chain_id):
                continue

            if event_type == "wicked.brain.consolidated":
                _invalidate_brain_adapter_cache()
                mark_processed(event_type, chain_id)
                actions.append("Invalidated smaht brain adapter cache (brain consolidated)")

            elif event_type == "wicked.config.updated":
                _clear_brain_port_cache()
                mark_processed(event_type, chain_id)
                actions.append("Cleared brain port cache (config updated)")

            elif event_type == "wicked.brain.initialized":
                _auto_configure_brain_adapter()
                mark_processed(event_type, chain_id)
                actions.append("Auto-configured smaht brain adapter (brain initialized)")

        if max_event_id > 0:
            ack_events(max_event_id)

    except Exception as e:
        logger.debug(f"Brain event consumer error (non-blocking): {e}")

    return actions


def _invalidate_brain_adapter_cache():
    """Clear any cached brain query results so next prompt gets fresh data."""
    try:
        cache_dir = Path(os.path.expanduser("~")) / ".something-wicked" / "wicked-garden" / "local" / "wicked-smaht" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("brain_*.json"):
                f.unlink(missing_ok=True)
    except Exception:
        pass  # fail open


def _clear_brain_port_cache():
    """Clear the WICKED_BRAIN_PORT resolution cache."""
    try:
        from _brain_port import _port_cache
        _port_cache.clear()
    except Exception:
        pass  # fail open — _brain_port may not have a cache dict


def _auto_configure_brain_adapter():
    """Auto-detect brain and configure smaht adapter without manual setup."""
    try:
        from _brain_port import resolve_brain_port
        port = resolve_brain_port()
        if port:
            logger.info(f"Brain auto-detected on port {port}")
    except Exception:
        pass  # fail open
