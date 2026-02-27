"""
Source adapters for wicked-smaht.

Each adapter queries a wicked-garden plugin and returns ContextItems.

IMPORTANT: All adapters must be truly async to enable parallel execution.
Use run_subprocess() for subprocess calls and run_in_thread() for blocking I/O.

All scripts are co-located under plugins/wicked-garden/scripts/{domain}/.
Use _SCRIPTS_ROOT to build direct paths instead of discover_script().
"""

import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# All domain scripts live under plugins/wicked-garden/scripts/
# adapters/ is at scripts/smaht/adapters/, so parents[2] = scripts/
_SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


async def run_subprocess(
    cmd: List[str],
    timeout: float = 5.0,
    cwd: Optional[str] = None
) -> tuple[int, str, str]:
    """Run subprocess asynchronously without blocking the event loop.

    Returns: (returncode, stdout, stderr)
    """
    def _run():
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (-1, "", "timeout")
        except Exception as e:
            return (-1, "", str(e))

    return await asyncio.to_thread(_run)


async def run_in_thread(func, *args, **kwargs):
    """Run a blocking function in a thread pool."""
    import functools
    return await asyncio.to_thread(functools.partial(func, *args, **kwargs))


@dataclass
class ContextItem:
    """A single item of context from a source."""
    id: str
    source: str           # mem, jam, kanban, search, crew, context7
    title: str
    summary: str
    excerpt: str = ""
    relevance: float = 0.0
    age_days: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def token_estimate(self) -> int:
        """Estimate token count for this item."""
        text = f"{self.title} {self.summary} {self.excerpt}"
        return len(text) // 4  # Rough estimate


from . import cp_adapter
from . import context7_adapter

__all__ = [
    'ContextItem',
    'cp_adapter',
    'context7_adapter',
]
