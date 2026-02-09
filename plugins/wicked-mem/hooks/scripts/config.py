#!/usr/bin/env python3
"""
Configuration for wicked-mem hooks.

Feature flags for independent enable/disable of components.
"""

import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Feature flags - override via environment variables
FEATURES = {
    # Context injection: inject relevant memories into prompts
    "CONTEXT_INJECTION": os.environ.get("WICKED_MEM_CONTEXT", "1") == "1",

    # Decay: run memory decay/archival
    "DECAY_ENABLED": os.environ.get("WICKED_MEM_DECAY", "1") == "1",

    # Debug mode: verbose logging
    "DEBUG": os.environ.get("WICKED_MEM_DEBUG", "0") == "1",
}


def is_enabled(feature: str) -> bool:
    """Check if a feature is enabled."""
    return FEATURES.get(feature, False)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with consistent naming."""
    logger = logging.getLogger(f"wicked-mem.{name}")
    if FEATURES["DEBUG"]:
        logger.setLevel(logging.DEBUG)
    return logger
