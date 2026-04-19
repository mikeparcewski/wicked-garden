"""
Regression suite: every Task(subagent_type="wicked-garden:*:*") ref in commands/
must resolve to an existing agent file.

Audit finding: #533 — 15 command files referenced agents that did not exist on disk.
Fix: consolidation map applied in build phase (2026-04-19). This suite prevents
future command additions from referencing non-existent agents.

Extraction: regex over Task( ... subagent_type="wicked-garden:{domain}:{name}" ... )
Resolution: agents/{domain}/{name}.md must exist.
"""
import re
from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
COMMANDS_DIR = REPO / "commands"
AGENTS_DIR = REPO / "agents"

# Match subagent_type="wicked-garden:{domain}:{name}" (quoted, in Task() calls)
SUBAGENT_REF_RE = re.compile(
    r'subagent_type\s*=\s*"(wicked-garden:[a-z][a-z0-9-]*:[a-z][a-z0-9-]*)"'
)


def _command_ref_params():
    """
    Collect (command_file, ref_string, expected_agent_path) for every
    subagent_type ref found in commands/**/*.md files.
    """
    params = []
    for md_file in sorted(COMMANDS_DIR.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for match in SUBAGENT_REF_RE.finditer(text):
            ref = match.group(1)
            parts = ref.split(":")
            if len(parts) != 3:
                continue
            _, domain, name = parts
            agent_path = AGENTS_DIR / domain / f"{name}.md"
            params.append(
                pytest.param(
                    md_file,
                    ref,
                    agent_path,
                    id=f"{md_file.relative_to(REPO)}::{ref}",
                )
            )
    return params


@pytest.mark.parametrize("command_file,ref,agent_path", _command_ref_params())
def test_command_subagent_ref_resolves(
    command_file: Path, ref: str, agent_path: Path
):
    """Every Task(subagent_type=...) in commands/ must have a corresponding agent file."""
    assert agent_path.exists(), (
        f"{command_file.relative_to(REPO)}: references '{ref}' but "
        f"agents/{agent_path.parent.name}/{agent_path.name} does not exist"
    )
