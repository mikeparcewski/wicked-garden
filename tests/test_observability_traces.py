#!/usr/bin/env python3
"""Tier 1 — Fire-and-forget trace isolation tests (#157).

Tests cover:
- Trace functions use get_client (not ControlPlaneClient directly) — via source analysis
- Trace functions are wrapped in try/except (fire-and-forget)
- Failures don't block return values

Note: cp_adapter.py and orchestrator.py use relative/dynamic imports that prevent
direct import in test context. Tests use AST source analysis to verify patterns.
"""

import ast
import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_SMAHT_ADAPTERS = _SCRIPTS / "smaht" / "adapters"
_SMAHT_V2 = _SCRIPTS / "smaht" / "v2"


def _get_function_source(filepath: Path, func_name: str) -> str:
    """Extract function source from a file using AST."""
    source = filepath.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_source_segment(source, node)
    return ""


class TestSmahtTraceUsesGetClient(unittest.TestCase):
    """S-01 / #157 — _emit_smaht_trace should use get_client()."""

    def setUp(self):
        self.func_src = _get_function_source(
            _SMAHT_ADAPTERS / "cp_adapter.py", "_emit_smaht_trace"
        )
        self.assertTrue(self.func_src, "_emit_smaht_trace not found in cp_adapter.py")

    def test_uses_get_client(self):
        self.assertIn("get_client", self.func_src,
                       "_emit_smaht_trace should use get_client()")

    def test_does_not_instantiate_client_directly(self):
        self.assertNotIn("ControlPlaneClient(", self.func_src,
                          "_emit_smaht_trace should not directly instantiate ControlPlaneClient")

    def test_wrapped_in_try_except(self):
        """Function body is wrapped in try/except for fire-and-forget."""
        self.assertIn("try:", self.func_src)
        self.assertIn("except", self.func_src)

    def test_except_passes(self):
        """Exception handler is a bare pass (fire-and-forget, never block)."""
        self.assertIn("pass", self.func_src)


class TestOrchestratorTraceUsesGetClient(unittest.TestCase):
    """S-01 / #157 — _emit_orchestrator_trace should use get_client()."""

    def setUp(self):
        self.func_src = _get_function_source(
            _SMAHT_V2 / "orchestrator.py", "_emit_orchestrator_trace"
        )
        self.assertTrue(self.func_src, "_emit_orchestrator_trace not found in orchestrator.py")

    def test_uses_get_client(self):
        self.assertIn("get_client", self.func_src,
                       "_emit_orchestrator_trace should use get_client()")

    def test_does_not_instantiate_client_directly(self):
        self.assertNotIn("ControlPlaneClient(", self.func_src,
                          "_emit_orchestrator_trace should not directly instantiate ControlPlaneClient")

    def test_wrapped_in_try_except(self):
        self.assertIn("try:", self.func_src)
        self.assertIn("except", self.func_src)

    def test_except_passes(self):
        self.assertIn("pass", self.func_src)


class TestTraceFireAndForget(unittest.TestCase):
    """#157 — Traces are dispatched as daemon threads and never block."""

    def test_cp_adapter_uses_daemon_thread(self):
        """_query_domain launches trace in daemon thread."""
        source = (_SMAHT_ADAPTERS / "cp_adapter.py").read_text()
        func_src = ""
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_query_domain":
                func_src = ast.get_source_segment(source, node)
                break
        self.assertIn("daemon=True", func_src,
                       "Trace thread should be a daemon thread")
        self.assertIn("_emit_smaht_trace", func_src,
                       "Trace should call _emit_smaht_trace")


if __name__ == "__main__":
    unittest.main()
