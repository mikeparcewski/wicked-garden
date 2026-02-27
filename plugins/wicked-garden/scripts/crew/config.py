#!/usr/bin/env python3
"""
Configuration and feature flags for wicked-crew.

Feature flags allow independent enable/disable of components for:
- Gradual rollout
- Debugging
- A/B testing
- Emergency rollback
"""

import os
import logging
from pathlib import Path

# Configure logging for all wicked-crew components
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Feature flags - can be overridden via environment variables
FEATURES = {
    # Dynamic specialist discovery: use specialist_discovery.py instead of hardcoded mapping
    "DYNAMIC_SPECIALISTS": os.environ.get("WICKED_CREW_DYNAMIC_SPECIALISTS", "1") == "1",

    # Task-driven phases: create tasks for phase deliverables
    "TASK_PHASES": os.environ.get("WICKED_CREW_TASK_PHASES", "1") == "1",

    # Adaptive workflow: skip/add phases based on complexity
    "ADAPTIVE_WORKFLOW": os.environ.get("WICKED_CREW_ADAPTIVE", "1") == "1",

    # Smart decisioning: analyze input for signals and complexity
    "SMART_DECISIONING": os.environ.get("WICKED_CREW_SMART", "1") == "1",

    # Specialist fallbacks: use built-in agents when specialists unavailable
    "FALLBACK_AGENTS": os.environ.get("WICKED_CREW_FALLBACKS", "1") == "1",

    # Debug mode: verbose logging
    "DEBUG": os.environ.get("WICKED_CREW_DEBUG", "0") == "1",
}

# Phase complexity thresholds for adaptive workflow
PHASE_THRESHOLDS = {
    "design": 2,    # Skip design if complexity < 2
    "qe": 1,        # Always do at least minimal QE
    "review": 0,    # Always review
}

# Task staleness threshold (minutes)
TASK_STALENESS_MINUTES = int(os.environ.get("WICKED_CREW_TASK_STALENESS", "30"))


def is_enabled(feature: str) -> bool:
    """Check if a feature is enabled."""
    return FEATURES.get(feature, False)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with consistent naming."""
    logger = logging.getLogger(f"wicked-crew.{name}")
    if FEATURES["DEBUG"]:
        logger.setLevel(logging.DEBUG)
    return logger


# Data flow tracing for debugging cross-component issues
_TRACE_LOG = []


def trace(component: str, event: str, data: dict = None):
    """
    Trace data flow through components for debugging.

    Usage:
        trace("smart_decisioning", "signals_detected", {"signals": ["security"]})
        trace("specialist_discovery", "specialists_found", {"count": 3})
    """
    if not FEATURES["DEBUG"]:
        return

    entry = {
        "component": component,
        "event": event,
        "data": data or {},
    }
    _TRACE_LOG.append(entry)

    logger = get_logger("trace")
    logger.debug(f"[{component}] {event}: {data}")


def get_trace_log() -> list:
    """Get the trace log for debugging."""
    return _TRACE_LOG.copy()


def clear_trace_log():
    """Clear the trace log."""
    global _TRACE_LOG
    _TRACE_LOG = []


def should_skip_phase(phase: str, complexity: int, user_override: bool = False) -> bool:
    """
    Determine if a phase should be skipped based on complexity.

    Priority order: user_override > signals > complexity

    Args:
        phase: Phase name (design, qe, review)
        complexity: Complexity score 0-7
        user_override: If True, never skip this phase

    Returns:
        True if phase should be skipped
    """
    if user_override:
        return False

    threshold = PHASE_THRESHOLDS.get(phase, 0)
    should_skip = complexity < threshold

    if should_skip:
        logger = get_logger("workflow")
        logger.info(f"Skipping phase '{phase}': complexity {complexity} < threshold {threshold}")

    return should_skip
