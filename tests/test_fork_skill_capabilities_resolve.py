"""Every fork skill's declared ``tool-capabilities`` must exist in the registry.

The capability resolver (``_capability_resolver.resolve_agent``) only *warns*
to stderr when a worker declares an unknown capability, then silently skips it —
so the worker gets no tools for that capability and a warning is printed on
every SessionStart bootstrap. That is too quiet: a typo'd or unregistered
capability should fail loudly in CI, not rot as runtime noise. This test turns
that warning into a hard failure and pins capability declarations to the
registry (`scripts/_capability_registry.py`).

History: workers used to live in agents/{domain}/*.md; the v12.25 skills-only
conversion moved them to context-fork skills under skills/, loaded by
``AgentLoader.load_fork_skills``. Same invariant, new home.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from _agents import AgentLoader  # noqa: E402
from _capability_registry import CAPABILITY_REGISTRY  # noqa: E402


def test_all_fork_skill_tool_capabilities_are_registered():
    loader = AgentLoader()
    agents = loader.load_fork_skills(_REPO_ROOT / "skills")
    assert agents, "no fork skills loaded — loader or skills/ path is broken"
    assert "wicked-garden-crew-implementer" in agents, (
        "the crew implementer worker did not load — the fork-skill scan is "
        "not seeing the converted workers"
    )

    registry = set(CAPABILITY_REGISTRY.keys())
    offenders: dict[str, list[str]] = {}
    for name, profile in agents.items():
        caps = (profile.metadata or {}).get("tool_capabilities") or []
        unknown = [c for c in caps if c not in registry]
        if unknown:
            offenders[name] = unknown

    assert not offenders, (
        "fork skills declare tool-capabilities absent from CAPABILITY_REGISTRY "
        f"(add them to scripts/_capability_registry.py): {offenders}"
    )
