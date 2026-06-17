"""tests/crew/test_stack_registry.py — modernize stack-registry dispatch reader.

Covers the §B11/G2 fail-closed contract: a `wired` stack returns a runnable
dispatch; an unknown or `planned`/`none` stack returns a capability-gap task
and NO dispatch (the reader never fabricates a migration). Bus emit is patched
out so the unit test stays hermetic.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import stack_registry as sr  # noqa: E402


class TestRegistryLoads(unittest.TestCase):
    def test_registry_has_status_levels_and_stacks(self):
        reg = sr.load_registry()
        self.assertIn("stacks", reg)
        self.assertIn("$status_levels", reg)
        # Every stack carries an explicit status (no silent default in data).
        for sid, entry in reg["stacks"].items():
            self.assertIn("status", entry, f"{sid} missing status")
            self.assertIn(entry["status"], ("wired", "planned", "none"))


class TestWiredDispatch(unittest.TestCase):
    """A wired stack returns a runnable dispatch, no gap-task."""

    def test_known_wired_stack_returns_dispatch(self):
        r = sr.resolve_dispatch("node-legacy-to-modern", emit=False)
        self.assertEqual(r["status"], "wired")
        self.assertIsNone(r["gap_task"])
        self.assertIsNotNone(r["dispatch"])
        # Dispatch names the blueprint + transform the modernize phases run.
        self.assertTrue(r["dispatch"]["blueprint"])
        self.assertIn("skills", r["dispatch"]["transform"])
        self.assertEqual(r["dispatch"]["validate"], {"gate": "produces:parity-proof"})

    def test_generic_cross_stack_is_wired(self):
        r = sr.resolve_dispatch("generic-cross-stack", emit=False)
        self.assertEqual(r["status"], "wired")
        self.assertIsNotNone(r["dispatch"])


class TestWiredOnlyContract(unittest.TestCase):
    """Dispatch is strictly wired-only: any non-`wired` status fails closed.

    Guards the §B11/G2 honesty contract — a typo'd or novel status must NOT
    leak a runnable dispatch (regression test for the resolve_dispatch fix).
    """

    def _reg(self, status):
        return {
            "stacks": {
                "x-stack": {
                    "id": "x-stack", "label": "X", "status": status,
                    "blueprint": "bp",
                    "fixes": ["f"],
                    "transform": {"skills": ["t"]},
                    "validate": {"gate": "g"},
                }
            }
        }

    def test_typo_status_fails_closed_to_gap(self):
        # A misspelled "wierd" status must NOT be treated as runnable.
        with patch.object(sr, "_emit_gap"):
            r = sr.resolve_dispatch("x-stack", registry=self._reg("wierd"), emit=False)
        self.assertEqual(r["status"], "wierd")
        self.assertIsNone(r["dispatch"])
        self.assertIsNotNone(r["gap_task"])
        self.assertEqual(r["gap_task"]["kind"], "capability-gap")

    def test_novel_status_fails_closed_to_gap(self):
        # An unrecognised-but-plausible status (e.g. "experimental") also gaps.
        with patch.object(sr, "_emit_gap"):
            r = sr.resolve_dispatch("x-stack", registry=self._reg("experimental"), emit=False)
        self.assertIsNone(r["dispatch"])
        self.assertIsNotNone(r["gap_task"])

    def test_wired_status_still_dispatches(self):
        r = sr.resolve_dispatch("x-stack", registry=self._reg("wired"), emit=False)
        self.assertIsNotNone(r["dispatch"])
        self.assertIsNone(r["gap_task"])
        self.assertEqual(r["dispatch"]["fixes"], ["f"])


class TestExplicitNullFields(unittest.TestCase):
    """Explicit JSON null on a wired stack coalesces to the empty container.

    `dict.get(k, default)` returns None (not default) when the key is present
    but null; the reader uses `... or default` so list(None)/None-downstream
    can't happen (regression test for the explicit-null fix)."""

    def _reg_with_nulls(self):
        return {
            "stacks": {
                "null-stack": {
                    "id": "null-stack", "label": "Null", "status": "wired",
                    "blueprint": None,
                    "fixes": None,
                    "transform": None,
                    "validate": None,
                }
            }
        }

    def test_explicit_nulls_do_not_crash_and_coalesce(self):
        # Must not raise TypeError: 'NoneType' object is not iterable.
        r = sr.resolve_dispatch("null-stack", registry=self._reg_with_nulls(), emit=False)
        self.assertEqual(r["status"], "wired")
        d = r["dispatch"]
        self.assertIsNotNone(d)
        self.assertEqual(d["fixes"], [])        # list(None or []) -> []
        self.assertEqual(d["transform"], {})    # None or {} -> {}
        self.assertEqual(d["validate"], {})     # None or {} -> {}
        self.assertIsNone(d["blueprint"])       # blueprint may legitimately be None

    def test_missing_fixes_key_still_defaults(self):
        reg = {"stacks": {"s": {"status": "wired", "transform": {}, "validate": {}}}}
        r = sr.resolve_dispatch("s", registry=reg, emit=False)
        self.assertEqual(r["dispatch"]["fixes"], [])


class TestGapEmission(unittest.TestCase):
    """Unknown / planned / none -> a gap-task, NO dispatch, bus event fired."""

    def test_unknown_stack_emits_gap_task_not_dispatch(self):
        with patch.object(sr, "_emit_gap") as mock_emit:
            r = sr.resolve_dispatch("perl-cgi-to-rails")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["dispatch"])
        self.assertIsNotNone(r["gap_task"])
        self.assertEqual(r["gap_task"]["kind"], "capability-gap")
        self.assertEqual(r["gap_task"]["stack"], "perl-cgi-to-rails")
        mock_emit.assert_called_once()

    def test_planned_stack_emits_gap_task_not_dispatch(self):
        # cobol-to-java ships as status: planned (on the roadmap, not wired).
        with patch.object(sr, "_emit_gap") as mock_emit:
            r = sr.resolve_dispatch("cobol-to-java")
        self.assertEqual(r["status"], "planned")
        self.assertIsNone(r["dispatch"])
        self.assertIsNotNone(r["gap_task"])
        self.assertIn("planned", r["gap_task"]["body"])
        mock_emit.assert_called_once()

    def test_gap_task_carries_actionable_body(self):
        with patch.object(sr, "_emit_gap"):
            r = sr.resolve_dispatch("angularjs-to-angular")
        # The gap body must point the operator at how to close the gap.
        self.assertIn("stack-registry.json", r["gap_task"]["body"])
        self.assertIn("wired", r["gap_task"]["body"])


class TestListStacks(unittest.TestCase):
    def test_list_includes_wired_and_planned(self):
        rows = sr.list_stacks()
        statuses = {row["status"] for row in rows}
        self.assertIn("wired", statuses)
        self.assertIn("planned", statuses)
        ids = {row["id"] for row in rows}
        self.assertIn("generic-cross-stack", ids)


class TestCLI(unittest.TestCase):
    """The CLI shim: exit 0 on a wired dispatch, exit 3 on a gap (fail-closed)."""

    def _run(self, *args):
        script = _REPO_ROOT / "scripts" / "crew" / "stack_registry.py"
        return subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True,
        )

    def test_cli_resolve_wired_exits_zero(self):
        res = self._run("resolve", "--stack", "node-legacy-to-modern", "--no-emit")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["status"], "wired")
        self.assertIsNotNone(out["dispatch"])

    def test_cli_resolve_gap_exits_three(self):
        res = self._run("resolve", "--stack", "cobol-to-java", "--no-emit")
        self.assertEqual(res.returncode, 3, res.stderr)
        out = json.loads(res.stdout)
        self.assertIsNone(out["dispatch"])
        self.assertIsNotNone(out["gap_task"])

    def test_cli_resolve_unknown_exits_three(self):
        res = self._run("resolve", "--stack", "not-a-real-stack", "--no-emit")
        self.assertEqual(res.returncode, 3, res.stderr)


if __name__ == "__main__":
    unittest.main()
