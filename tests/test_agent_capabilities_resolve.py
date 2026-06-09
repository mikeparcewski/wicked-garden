"""Every agent's declared ``tool-capabilities`` must exist in the registry.

The capability resolver (``_capability_resolver.resolve_agent``) only *warns*
to stderr when an agent declares an unknown capability, then silently skips it —
so the agent gets no tools for that capability and a warning is printed on every
SessionStart bootstrap. That is too quiet: a typo'd or unregistered capability
should fail loudly in CI, not rot as runtime noise. This test turns that
warning into a hard failure and pins capability declarations to the registry
(`scripts/_capability_registry.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from _agents import AgentLoader  # noqa: E402
from _capability_registry import CAPABILITY_REGISTRY  # noqa: E402


def test_all_agent_tool_capabilities_are_registered():
    loader = AgentLoader()
    agents = loader.load_disk_agents(_REPO_ROOT / "agents")
    assert agents, "no agents loaded — loader or path is broken"

    registry = set(CAPABILITY_REGISTRY.keys())
    offenders: dict[str, list[str]] = {}
    for name, profile in agents.items():
        caps = (profile.metadata or {}).get("tool_capabilities") or []
        unknown = [c for c in caps if c not in registry]
        if unknown:
            offenders[name] = unknown

    assert not offenders, (
        "agents declare tool-capabilities absent from CAPABILITY_REGISTRY "
        f"(add them to scripts/_capability_registry.py): {offenders}"
    )
