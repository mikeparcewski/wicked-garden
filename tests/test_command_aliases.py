"""
tests/test_command_aliases.py

Regression suite for command aliases introduced in v6.3.3 hygiene bundle (#533).

Asserts:
- The crew:yolo alias stub still exists (backward compat).
- The yolo stub redirects to crew:auto-approve (mentions auto-approve).
- The canonical auto-approve command exists with full content.
- The phase_manager.py 'yolo' action subcommand name is preserved (no runtime rename).
"""

from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
COMMANDS_CREW = REPO / "commands" / "crew"
SCRIPTS_CREW = REPO / "scripts" / "crew"


class TestCrewYoloAliasStub:
    """crew:yolo must remain as a stub that redirects to crew:auto-approve."""

    def test_yolo_md_exists(self):
        """commands/crew/yolo.md must still exist for backward compatibility."""
        assert (COMMANDS_CREW / "yolo.md").exists(), (
            "commands/crew/yolo.md was deleted. It must remain as an alias stub "
            "so that existing /wicked-garden:crew:yolo invocations continue to work."
        )

    def test_yolo_md_is_short_stub(self):
        """yolo.md must be short (stub-only, not full command spec)."""
        content = (COMMANDS_CREW / "yolo.md").read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) <= 20, (
            f"commands/crew/yolo.md has {len(lines)} non-empty lines — expected a short alias "
            f"stub (<=20 lines). It may have been reverted to the full command spec."
        )

    def test_yolo_stub_references_auto_approve(self):
        """yolo.md must reference crew:auto-approve so users know where the canonical command is."""
        content = (COMMANDS_CREW / "yolo.md").read_text(encoding="utf-8")
        assert "auto-approve" in content, (
            "commands/crew/yolo.md stub must reference 'auto-approve' to redirect users "
            "to the canonical command. Got:\n" + content[:300]
        )


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
