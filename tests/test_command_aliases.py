"""
tests/test_command_aliases.py

Regression suite for command aliases introduced in v6.3.3 hygiene bundle (#533).

Asserts:
- The canonical auto-approve command exists with full content.
- The phase_manager.py 'yolo' action subcommand name is preserved (no runtime rename).

Historical note (v9.2.10): the `TestCrewYoloAliasStub` class was removed
because `commands/crew/yolo.md` was deleted in PR #603 (v9-PR-2 surface
cuts). The CLI compatibility shim now lives in `scripts/crew/autonomy.py`
— `--yolo` resolves to `--autonomy=full` via `get_mode()` and emits a
one-shot deprecation warning. There is no markdown alias file anymore;
the contract `TestCrewYoloAliasStub` asserted has not held since #603.
"""

from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
COMMANDS_CREW = REPO / "commands" / "crew"
SCRIPTS_CREW = REPO / "scripts" / "crew"


class TestCrewAutoApproveCanonical:
    """crew:auto-approve must exist as the full canonical command."""

    def test_auto_approve_md_exists(self):
        """commands/crew/auto-approve.md must exist as the canonical command."""
        assert (COMMANDS_CREW / "auto-approve.md").exists(), (
            "commands/crew/auto-approve.md is missing. "
            "This is the canonical command that replaced crew:yolo."
        )

    def test_auto_approve_has_when_to_use_section(self):
        """auto-approve.md must have a 'When to use' disambiguation table."""
        content = (COMMANDS_CREW / "auto-approve.md").read_text(encoding="utf-8")
        assert "When to use" in content, (
            "commands/crew/auto-approve.md must contain a 'When to use this vs the others' "
            "section to distinguish execute / just-finish / auto-approve."
        )

    def test_auto_approve_documents_guardrails(self):
        """auto-approve.md must document the three safety guardrails."""
        content = (COMMANDS_CREW / "auto-approve.md").read_text(encoding="utf-8")
        assert "Justification" in content, (
            "auto-approve.md must document the Justification guardrail."
        )
        assert "Cooldown" in content, (
            "auto-approve.md must document the Cooldown guardrail."
        )


class TestPhaseManagerYoloSubcommandPreserved:
    """phase_manager.py must still have the 'yolo' action — only the command renames."""

    def test_phase_manager_yolo_action_exists(self):
        """scripts/crew/phase_manager.py must still expose the 'yolo' action subcommand."""
        phase_manager = SCRIPTS_CREW / "phase_manager.py"
        assert phase_manager.exists(), "scripts/crew/phase_manager.py not found"
        content = phase_manager.read_text(encoding="utf-8")
        assert '"yolo"' in content or "'yolo'" in content, (
            "scripts/crew/phase_manager.py must still have the 'yolo' action choice. "
            "Only the COMMAND was renamed — the script subcommand stays 'yolo' for "
            "backward compatibility with existing audit logs and automation."
        )

    def test_scripts_do_not_reference_crew_yolo_command(self):
        """scripts/ must not reference 'crew:yolo' as an invocation (namespace coupling)."""
        scripts_dir = REPO / "scripts"
        matches = []
        for py_file in sorted(scripts_dir.rglob("*.py")):
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "crew:yolo" in text:
                matches.append(str(py_file.relative_to(REPO)))
        assert matches == [], (
            f"scripts/ should not hard-code 'crew:yolo' command references "
            f"(use 'crew:auto-approve' or the phase_manager 'yolo' action instead):\n"
            + "\n".join(f"  {m}" for m in matches)
        )
