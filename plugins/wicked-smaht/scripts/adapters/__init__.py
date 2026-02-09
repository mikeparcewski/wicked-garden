"""
Source adapters for wicked-smaht.

Each adapter queries a wicked-garden plugin and returns ContextItems.

IMPORTANT: All adapters must be truly async to enable parallel execution.
Use run_subprocess() for subprocess calls and run_in_thread() for blocking I/O.
"""

import asyncio
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _parse_version(v: str) -> tuple:
    """Parse semver string to comparable tuple."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def discover_script(plugin_name: str, script_name: str) -> Optional[Path]:
    """Find a plugin's script via cache (highest version) or local repo.

    Discovery order:
    1. Cache path (~/.claude/plugins/cache/wicked-garden/{plugin}/{version}/scripts/{script})
       - Selects highest semver version deterministically
    2. Local repo sibling path (../../../{plugin}/scripts/{script})
    """
    # 1. Cache path (highest semver)
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden" / plugin_name
    if cache_base.exists():
        versions = []
        for d in cache_base.iterdir():
            if d.is_dir():
                versions.append((_parse_version(d.name), d))
        if versions:
            versions.sort(key=lambda x: x[0], reverse=True)
            script = versions[0][1] / "scripts" / script_name
            if script.exists():
                return script

    # 2. Local repo sibling path
    local = Path(__file__).parent.parent.parent.parent / plugin_name / "scripts" / script_name
    if local.exists():
        return local

    return None


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


from . import mem_adapter
from . import jam_adapter
from . import kanban_adapter
from . import search_adapter
from . import crew_adapter
from . import context7_adapter

__all__ = [
    'ContextItem',
    'mem_adapter',
    'jam_adapter',
    'kanban_adapter',
    'search_adapter',
    'crew_adapter',
    'context7_adapter',
]
