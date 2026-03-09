#!/usr/bin/env python3
"""
tests/smaht/test_assembler_registry.py

Unit and structural tests for the FastPath/SlowPath assembler refactor (Task 4.3).

AC coverage: AC-3.1, AC-3.2, AC-3.3, AC-2.1
Scenario coverage: S-ASM-1..7

Structural tests read source text directly — robust against dynamic attribute tricks.
Unit tests mock AdapterRegistry and timed_query to avoid DomainStore / MCP calls.
"""

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_V2_DIR = _REPO_ROOT / "scripts" / "smaht" / "v2"
_ADAPTERS_DIR = _REPO_ROOT / "scripts" / "smaht"

sys.path.insert(0, str(_V2_DIR))
sys.path.insert(0, str(_ADAPTERS_DIR))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# TestAssemblerStructural — source inspection tests (AC-3.1, AC-3.5)
# ---------------------------------------------------------------------------

class TestAssemblerStructural(unittest.TestCase):
    """S-ASM-1, S-ASM-2: Source inspection verifies _load_adapters is absent."""

    def test_fast_path_no_load_adapters_method(self):
        """AC-3.1 / S-ASM-1: FastPathAssembler must not define _load_adapters after refactor."""
        src = (_V2_DIR / "fast_path.py").read_text()
        self.assertNotIn(
            "def _load_adapters",
            src,
            "FastPathAssembler._load_adapters must be deleted after registry refactor",
        )

    def test_slow_path_no_load_adapters_method(self):
        """AC-3.1 / S-ASM-2: SlowPathAssembler must not define _load_adapters after refactor."""
        src = (_V2_DIR / "slow_path.py").read_text()
        self.assertNotIn(
            "def _load_adapters",
            src,
            "SlowPathAssembler._load_adapters must be deleted after registry refactor",
        )

    def test_fast_path_uses_adapter_registry(self):
        """AC-3.1: fast_path.py imports AdapterRegistry (single load point)."""
        src = (_V2_DIR / "fast_path.py").read_text()
        self.assertIn("AdapterRegistry", src)

    def test_slow_path_uses_adapter_registry(self):
        """AC-3.1: slow_path.py imports AdapterRegistry (single load point)."""
        src = (_V2_DIR / "slow_path.py").read_text()
        self.assertIn("AdapterRegistry", src)

    def test_no_import_cycle(self):
        """AC-3.5 / S-ASM-3 (structural): Import chain is cycle-free."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, '.'); "
                "from fast_path import FastPathAssembler; "
                "from slow_path import SlowPathAssembler; "
                "print('OK')",
            ],
            capture_output=True,
            text=True,
            cwd=str(_V2_DIR),
            timeout=15,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Import cycle detected:\n{result.stderr}",
        )
        self.assertIn("OK", result.stdout)

    def test_fast_path_result_has_adapter_timings_field(self):
        """AC-2.1 / S-ASM-6: FastPathResult dataclass declares adapter_timings field."""
        from fast_path import FastPathResult
        result = FastPathResult(
            briefing="b",
            sources_queried=[],
            sources_failed=[],
            latency_ms=0,
        )
        self.assertIsInstance(result.adapter_timings, dict)

    def test_slow_path_result_has_adapter_timings_field(self):
        """AC-2.1 / S-ASM-7: SlowPathResult dataclass declares adapter_timings field."""
        from slow_path import SlowPathResult
        result = SlowPathResult(
            briefing="b",
            sources_queried=[],
            sources_failed=[],
            latency_ms=0,
        )
        self.assertIsInstance(result.adapter_timings, dict)

    def test_fast_path_hasattr_no_load_adapters(self):
        """AC-3.1 (runtime): FastPathAssembler instance has no _load_adapters attribute."""
        from fast_path import FastPathAssembler
        mock_registry = MagicMock()
        mock_registry.available.return_value = []

        with patch("fast_path.AdapterRegistry", return_value=mock_registry):
            assembler = FastPathAssembler()

        self.assertFalse(
            hasattr(assembler, "_load_adapters"),
            "FastPathAssembler must not have _load_adapters after refactor",
        )

    def test_slow_path_hasattr_no_load_adapters(self):
        """AC-3.1 (runtime): SlowPathAssembler instance has no _load_adapters attribute."""
        from slow_path import SlowPathAssembler
        mock_registry = MagicMock()
        mock_registry.available.return_value = []

        with patch("slow_path.AdapterRegistry", return_value=mock_registry):
            assembler = SlowPathAssembler()

        self.assertFalse(
            hasattr(assembler, "_load_adapters"),
            "SlowPathAssembler must not have _load_adapters after refactor",
        )


# ---------------------------------------------------------------------------
# TestFastPathAdapterSet — adapter selection (AC-3.2)
# ---------------------------------------------------------------------------

class TestFastPathAdapterSet(unittest.TestCase):
    """AC-3.2 / S-ASM-3: FastPath adapter set is unchanged — no mem, correct names."""

    def _make_analysis(self, intent_type_value="implementation"):
        """Build a minimal PromptAnalysis for the given intent."""
        from router import IntentType, PromptAnalysis
        intent_map = {
            "implementation": IntentType.IMPLEMENTATION,
            "debugging": IntentType.DEBUGGING,
            "planning": IntentType.PLANNING,
            "research": IntentType.RESEARCH,
            "review": IntentType.REVIEW,
            "general": IntentType.GENERAL,
        }
        return PromptAnalysis(
            prompt="test prompt",
            word_count=5,
            intent_type=intent_map[intent_type_value],
            confidence=0.9,
            competing_intents=0,
            entities=[],
            entity_count=0,
            is_compound=False,
            requires_history=False,
            is_continuation=False,
        )

    def test_fast_path_implementation_excludes_mem(self):
        """AC-3.2: IMPLEMENTATION intent — mem NOT in adapters requested from registry."""
        from fast_path import FastPathAssembler, ADAPTER_RULES
        from router import IntentType

        # Verify statically that the ADAPTER_RULES don't include mem for IMPLEMENTATION
        implementation_adapters = ADAPTER_RULES.get(IntentType.IMPLEMENTATION, [])
        self.assertNotIn("mem", implementation_adapters)

    def test_fast_path_implementation_includes_required_adapters(self):
        """AC-3.2: IMPLEMENTATION intent includes domain, context7, tools, delegation."""
        from fast_path import ADAPTER_RULES
        from router import IntentType

        adapters = ADAPTER_RULES.get(IntentType.IMPLEMENTATION, [])
        for name in ("domain", "context7", "tools", "delegation"):
            self.assertIn(name, adapters, f"IMPLEMENTATION must include '{name}'")

    def test_fast_path_no_intent_includes_mem(self):
        """AC-3.2: No intent in ADAPTER_RULES includes mem (fast path never queries mem)."""
        from fast_path import ADAPTER_RULES

        for intent, adapters in ADAPTER_RULES.items():
            self.assertNotIn(
                "mem",
                adapters,
                f"Intent '{intent}' must not include 'mem' in fast path adapter rules",
            )

    def test_fast_path_assemble_requests_correct_names_from_registry(self):
        """AC-3.2 / S-ASM-3: assemble() passes expected names to registry.get(), excluding mem."""
        from fast_path import FastPathAssembler

        mock_registry = MagicMock()
        mock_registry.get.return_value = {}  # No adapters available — returns empty result

        analysis = self._make_analysis("implementation")

        with patch("fast_path.AdapterRegistry", return_value=mock_registry):
            assembler = FastPathAssembler()
            asyncio.run(assembler.assemble("implement the cache", analysis))

        # Collect all name lists passed to registry.get()
        all_requested = []
        for call_args in mock_registry.get.call_args_list:
            names = call_args[0][0]  # positional arg
            all_requested.extend(names)

        self.assertNotIn("mem", all_requested, "mem must not be requested by fast path")
        for name in ("domain", "context7", "tools", "delegation"):
            self.assertIn(name, all_requested, f"'{name}' must be requested by fast path")

    def test_fast_path_result_adapter_timings_is_dict(self):
        """S-ASM-6: FastPathResult.adapter_timings is a dict (even with no adapters)."""
        from fast_path import FastPathAssembler

        mock_registry = MagicMock()
        mock_registry.get.return_value = {}

        analysis = self._make_analysis("implementation")

        with patch("fast_path.AdapterRegistry", return_value=mock_registry):
            assembler = FastPathAssembler()
            result = asyncio.run(assembler.assemble("prompt", analysis))

        self.assertIsInstance(result.adapter_timings, dict)


# ---------------------------------------------------------------------------
# TestSlowPathAdapterSet — adapter selection (AC-3.3)
# ---------------------------------------------------------------------------

class TestSlowPathAdapterSet(unittest.TestCase):
    """AC-3.3 / S-ASM-5: SlowPath adapter set is unchanged — all 5 adapters."""

    def _make_analysis(self):
        """Build a minimal PromptAnalysis for slow path."""
        from router import IntentType, PromptAnalysis
        return PromptAnalysis(
            prompt="complex planning prompt",
            word_count=50,
            intent_type=IntentType.PLANNING,
            confidence=0.9,
            competing_intents=0,
            entities=[],
            entity_count=0,
            is_compound=True,
            requires_history=True,
            is_continuation=False,
        )

    def test_slow_path_requests_all_five_adapter_names(self):
        """AC-3.3 / S-ASM-5: SlowPath calls registry.get() with all 5 known adapter names."""
        from slow_path import SlowPathAssembler
        from adapter_registry import AdapterRegistry

        mock_registry = MagicMock()
        mock_registry.get.return_value = {}

        mock_condenser = MagicMock()
        mock_condenser.get_condensed_history.return_value = ""
        mock_condenser.get_last_turn.return_value = None

        analysis = self._make_analysis()

        # slow_path.py accesses AdapterRegistry.KNOWN_ADAPTERS as a class attribute.
        # Patch the class but preserve KNOWN_ADAPTERS so the key list is correct.
        mock_registry_class = MagicMock()
        mock_registry_class.return_value = mock_registry
        mock_registry_class.KNOWN_ADAPTERS = AdapterRegistry.KNOWN_ADAPTERS

        with patch("slow_path.AdapterRegistry", mock_registry_class):
            assembler = SlowPathAssembler()
            asyncio.run(assembler.assemble("complex planning prompt", analysis, mock_condenser))

        # Collect all names passed to registry.get()
        all_requested = []
        for call_args in mock_registry.get.call_args_list:
            names = call_args[0][0]
            all_requested.extend(names)

        for name in AdapterRegistry.KNOWN_ADAPTERS.keys():
            self.assertIn(
                name,
                all_requested,
                f"SlowPath must request '{name}' from registry",
            )

    def test_slow_path_result_adapter_timings_is_dict(self):
        """S-ASM-7: SlowPathResult.adapter_timings is a dict (even with no adapters)."""
        from slow_path import SlowPathAssembler

        mock_registry = MagicMock()
        mock_registry.get.return_value = {}

        mock_condenser = MagicMock()
        mock_condenser.get_condensed_history.return_value = ""
        mock_condenser.get_last_turn.return_value = None

        analysis = self._make_analysis()

        with patch("slow_path.AdapterRegistry", return_value=mock_registry):
            assembler = SlowPathAssembler()
            result = asyncio.run(assembler.assemble("prompt", analysis, mock_condenser))

        self.assertIsInstance(result.adapter_timings, dict)

    def test_slow_path_uses_known_adapters_class_attr(self):
        """Gap G-4: slow_path uses AdapterRegistry.KNOWN_ADAPTERS as class attribute."""
        src = (_V2_DIR / "slow_path.py").read_text()
        self.assertIn(
            "AdapterRegistry.KNOWN_ADAPTERS",
            src,
            "slow_path must reference AdapterRegistry.KNOWN_ADAPTERS (class attribute, not instance)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
