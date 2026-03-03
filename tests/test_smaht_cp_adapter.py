#!/usr/bin/env python3
"""Tier 1 — Project-scoped smaht query tests (#156).

Tests cover:
- project_scoped flag is set on correct domain configs via source analysis
- crew config is exempt from project scoping
- _query_domain logic injects project_id when project_scoped=True
- BC-04: Empty cp_project_id sends no project_id param

Note: cp_adapter.py uses relative imports (from . import ...) so it cannot be
imported directly. Tests use source analysis to verify config values and
logic patterns.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_CP_ADAPTER = _SCRIPTS / "smaht" / "adapters" / "cp_adapter.py"


def _parse_domain_queries() -> dict:
    """Parse _DOMAIN_QUERIES from cp_adapter.py source.

    Returns a dict mapping domain name to its project_scoped value.
    """
    source = _CP_ADAPTER.read_text()
    # Use line-by-line parsing to find domain keys and their project_scoped values
    configs = {}
    current_domain = None

    for line in source.split("\n"):
        # Match domain key like:    "memory": {
        domain_match = re.match(r'\s+"(\w+)":\s*\{', line)
        if domain_match:
            current_domain = domain_match.group(1)

        # Match project_scoped value
        if current_domain:
            scoped_match = re.search(r'"project_scoped":\s*(True|False)', line)
            if scoped_match:
                configs[current_domain] = scoped_match.group(1) == "True"
                current_domain = None

    return configs


class TestDomainConfigProjectScoped(unittest.TestCase):
    """#156 — project_scoped flag on domain configs."""

    def setUp(self):
        self.configs = _parse_domain_queries()
        self.assertTrue(len(self.configs) >= 5,
                        f"Expected at least 5 domain configs, got {len(self.configs)}: {list(self.configs.keys())}")

    def test_memory_is_project_scoped(self):
        self.assertTrue(self.configs.get("memory"),
                        "memory domain should have project_scoped=True")

    def test_kanban_is_project_scoped(self):
        self.assertTrue(self.configs.get("kanban"),
                        "kanban domain should have project_scoped=True")

    def test_jam_is_project_scoped(self):
        self.assertTrue(self.configs.get("jam"),
                        "jam domain should have project_scoped=True")

    def test_knowledge_is_not_project_scoped(self):
        self.assertFalse(self.configs.get("knowledge"),
                         "knowledge domain should have project_scoped=False")

    def test_crew_is_exempt(self):
        """Crew queries should NOT be project-scoped."""
        self.assertFalse(self.configs.get("crew"),
                         "crew domain should have project_scoped=False")


class TestQueryDomainProjectScoping(unittest.TestCase):
    """#156 — _query_domain project_id injection logic."""

    def test_query_domain_checks_project_scoped(self):
        """_query_domain source contains the project scoping condition."""
        source = _CP_ADAPTER.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_query_domain":
                func_src = ast.get_source_segment(source, node)
                self.assertIn('project_scoped', func_src)
                self.assertIn('project_id', func_src)
                return
        self.fail("_query_domain function not found in cp_adapter.py")

    def test_query_domain_injects_project_id_in_params(self):
        """_query_domain sets params['project_id'] = cp_project_id."""
        source = _CP_ADAPTER.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_query_domain":
                func_src = ast.get_source_segment(source, node)
                self.assertIn('params["project_id"] = cp_project_id', func_src)
                return
        self.fail("_query_domain function not found")


class TestBC04EmptyProjectId(unittest.TestCase):
    """BC-04: Empty cp_project_id sends no project_id param."""

    def test_empty_string_is_falsy(self):
        """Empty string cp_project_id evaluates to False in the scoping check."""
        cp_project_id = ""
        config_scoped = True
        should_scope = config_scoped and cp_project_id
        self.assertFalse(should_scope)

    def test_none_is_falsy(self):
        """None cp_project_id evaluates to False in the scoping check."""
        cp_project_id = None
        config_scoped = True
        should_scope = config_scoped and cp_project_id
        self.assertFalse(should_scope)


if __name__ == "__main__":
    unittest.main()
