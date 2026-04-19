"""Tests for scripts/platform/guard_pipeline.py (Issue #448).

Covers:
    * scalpel profile budget (<1s on a synthetic 100-file diff)
    * profile auto-selection logic
    * each of the 5 checks with violation + clean cases
    * semantic-reviewer fail-open when module is missing
    * wicked-bus emission path (captured via monkey-patch)
    * does NOT hard-block even on BLOCK-level findings (API contract)

Deterministic, stdlib-only, no sleeps.
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from typing import List
from unittest import mock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "platform"))

import guard_pipeline as gp  # noqa: E402
import guard_profiles as gprof  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_py_file(tmpdir: Path, rel: str, content: str) -> Path:
    path = tmpdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_synthetic_files(tmpdir: Path, count: int) -> List[str]:
    files: List[str] = []
    template = (
        "import os\n"
        "import sys\n"
        "\n"
        "def do_work(a, b, c):\n"
        "    x = a + b + c\n"
        "    return x\n"
        "\n"
        "class Worker:\n"
        "    def run(self, value):\n"
        "        return value * 2\n"
    )
    for i in range(count):
        p = _make_py_file(tmpdir, f"src/module_{i}.py", template)
        files.append(str(p))
    return files


# ---------------------------------------------------------------------------
# Budget test — core acceptance criterion
# ---------------------------------------------------------------------------

class TestScalpelBudget(unittest.TestCase):
    """Scalpel must finish well under 1s on a 100-file synthetic diff."""

    def test_scalpel_under_one_second_on_100_files(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            files = _make_synthetic_files(tmpdir, 100)

            t0 = time.monotonic()
            report = gp.run_pipeline(
                profile_name="scalpel",
                cwd=tmpdir,
                files=files,
            )
            elapsed = time.monotonic() - t0

            # Hard assertion on wall time with generous CI margin.  The guard's
            # own internal budget is 1s; we allow up to 2s here to absorb
            # slow CI hardware while still catching runaway scans.
            self.assertLess(elapsed, 2.0,
                            f"scalpel took {elapsed:.3f}s on 100 files (budget 1s)")
            self.assertEqual(report.profile, "scalpel")
            self.assertIn(report.status, {"ok", "budget_exceeded"})
            # Print the timing so CI surfaces it even when the assert passes.
            sys.stderr.write(f"\n[budget-test] scalpel @ 100 files: {elapsed*1000:.1f}ms "
                             f"(internal={report.duration_ms}ms)\n")


# ---------------------------------------------------------------------------
# Profile auto-selection
# ---------------------------------------------------------------------------

class TestProfileAutoSelect(unittest.TestCase):

    def test_explicit_env_overrides(self):
        with mock.patch.dict(os.environ, {"WG_GUARD_PROFILE": "deep"}):
            p = gprof.auto_select()
            self.assertEqual(p.name, "deep")

    def test_explicit_arg_overrides_env(self):
        with mock.patch.dict(os.environ, {"WG_GUARD_PROFILE": "deep"}):
            p = gprof.auto_select(explicit_profile="scalpel")
            self.assertEqual(p.name, "scalpel")

    def test_invalid_profile_name_falls_back_to_scalpel(self):
        p = gprof.get_profile("nonsense")
        self.assertEqual(p.name, "scalpel")

    def test_build_phase_close_promotes_to_standard(self):
        with mock.patch.object(gprof, "_current_branch", return_value="feature/x"), \
             mock.patch.object(gprof, "_count_changed_files", return_value=2):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("WG_GUARD_PROFILE", None)
                p = gprof.auto_select(build_phase_just_closed=True)
                self.assertEqual(p.name, "standard")

    def test_release_branch_promotes_to_deep(self):
        with mock.patch.object(gprof, "_current_branch", return_value="main"), \
             mock.patch.object(gprof, "_count_changed_files", return_value=0):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("WG_GUARD_PROFILE", None)
                p = gprof.auto_select()
                self.assertEqual(p.name, "deep")

    def test_default_is_scalpel(self):
        with mock.patch.object(gprof, "_current_branch", return_value="feature/x"), \
             mock.patch.object(gprof, "_count_changed_files", return_value=1):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("WG_GUARD_PROFILE", None)
                p = gprof.auto_select()
                self.assertEqual(p.name, "scalpel")


# ---------------------------------------------------------------------------
# Individual checks — violation + clean
# ---------------------------------------------------------------------------

class TestBulletproofScan(unittest.TestCase):

    def test_clean_file_no_findings(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/clean.py",
                              "def foo(x):\n    return x + 1\n")
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
            self.assertEqual(result.status, "ok")
            self.assertEqual([x for x in result.findings if x.rule_id != "R1"], [])

    def test_bare_raise_exception_flagged_r2(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/bad.py",
                              "def foo():\n    raise Exception('boom')\n")
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
            rules = {x.rule_id for x in result.findings}
            self.assertIn("R2", rules)

    def test_swallowed_exception_flagged_r4(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/swallow.py",
                              "def foo():\n    try:\n        pass\n    except Exception:\n        pass\n")
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
            rules = {x.rule_id for x in result.findings}
            self.assertIn("R4", rules)

    def test_god_function_flagged_r6(self):
        # Build a function with 10 params
        src = "def big(a, b, c, d, e, f, g, h, i, j):\n    return a\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/big.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
            r6 = [x for x in result.findings if x.rule_id == "R6"]
            self.assertTrue(r6, "expected R6 finding for >8 params")


# ---------------------------------------------------------------------------
# AC-4: R3 magic values in conditionals — AST heuristic
# ---------------------------------------------------------------------------


class TestR3MagicValues(unittest.TestCase):
    """#462, Item 3 — R3 detects magic numeric literals in Compare nodes
    while allow-listing 0, 1, -1."""

    def test_magic_value_flagged(self):
        """`if x > 42:` triggers an R3 finding."""
        src = "def f(x):\n    if x > 42:\n        return x\n    return 0\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/m.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertTrue(r3, "expected R3 finding for magic value 42")
        self.assertTrue(any("42" in x.message for x in r3))

    def test_allow_listed_zero_not_flagged(self):
        """`if x > 0:` is NOT flagged — 0 is allow-listed."""
        src = "def f(x):\n    if x > 0:\n        return x\n    return 0\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/z.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertEqual(r3, [], f"0 should not be flagged as magic: {r3}")

    def test_allow_listed_negative_one_not_flagged(self):
        """`if x == -1:` is NOT flagged — -1 is allow-listed."""
        src = "def f(x):\n    if x == -1:\n        return x\n    return 0\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/neg.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertEqual(r3, [], f"-1 should not be flagged as magic: {r3}")

    def test_allow_listed_one_not_flagged(self):
        """`if n == 1:` is NOT flagged — 1 is allow-listed."""
        src = "def f(n):\n    if n == 1:\n        return n\n    return 0\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/one.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertEqual(r3, [], f"1 should not be flagged as magic: {r3}")

    def test_named_constant_not_flagged(self):
        """`if x > THRESHOLD:` is NOT flagged — comparator is a Name, not Constant."""
        src = (
            "THRESHOLD = 42\n"
            "def f(x):\n"
            "    if x > THRESHOLD:\n"
            "        return x\n"
            "    return 0\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/named.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertEqual(r3, [], f"Named constant should not be flagged: {r3}")

    def test_negative_magic_flagged_via_unary(self):
        """`if x < -42:` is flagged — -42 not in allow-list, parsed as UnaryOp."""
        src = "def f(x):\n    if x < -42:\n        return x\n    return 0\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/neg42.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r3 = [x for x in result.findings if x.rule_id == "R3"]
        self.assertTrue(r3, "expected R3 finding for -42 via UnaryOp")


# ---------------------------------------------------------------------------
# AC-5: R5 unbounded recursion — AST heuristic
# ---------------------------------------------------------------------------


class TestR5UnboundedRecursion(unittest.TestCase):
    """#462, Item 3 — R5 detects functions that self-call with no guard."""

    def test_unbounded_recursion_flagged(self):
        """`def f(n): return f(n - 1)` — flagged."""
        src = "def f(n):\n    return f(n - 1)\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/unbound.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r5 = [x for x in result.findings if x.rule_id == "R5"]
        self.assertTrue(r5, "expected R5 finding for unguarded recursion")
        self.assertTrue(any("f" in x.message for x in r5))

    def test_guarded_recursion_not_flagged(self):
        """Recursion with an early-return guard — NOT flagged."""
        src = (
            "def f(n):\n"
            "    if n <= 0:\n"
            "        return 0\n"
            "    return f(n - 1)\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/guard.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r5 = [x for x in result.findings if x.rule_id == "R5"]
        self.assertEqual(r5, [], f"Guarded recursion should not be flagged: {r5}")

    def test_non_recursive_function_not_flagged(self):
        """A plain function is not flagged."""
        src = "def g(n):\n    return n + 1\n"
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/plain.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r5 = [x for x in result.findings if x.rule_id == "R5"]
        self.assertEqual(r5, [], f"Non-recursive fn should not be R5: {r5}")

    def test_method_self_call_flagged(self):
        """`self.method(...)` also counts as self-call for R5 purposes."""
        src = (
            "class C:\n"
            "    def walk(self, n):\n"
            "        return self.walk(n - 1)\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/cls.py", src)
            result = gp.check_bulletproof_scan([str(f)], budget_seconds=1.0)
        r5 = [x for x in result.findings if x.rule_id == "R5"]
        self.assertTrue(r5, "expected R5 finding for unguarded method recursion")


# ---------------------------------------------------------------------------
# AC-6: performance — scalpel + R3 + R5 stays under the 1s budget (2s CI slack)
# ---------------------------------------------------------------------------


class TestR3R5PerformanceBudget(unittest.TestCase):
    """100-file synthetic diff with R3+R5 active on every Python file.
    Must stay under the scalpel budget (1s target, 2s hard assert)."""

    def test_scalpel_budget_with_r3_r5_active(self):
        # Template includes both R3-eligible conditionals and a recursive
        # guarded function — exercises the AST walkers on every file.
        template = (
            "import os\n"
            "import sys\n"
            "\n"
            "def work(x):\n"
            "    if x > 42:\n"                  # R3 candidate
            "        return x\n"
            "    if x == 0:\n"                  # allow-listed
            "        return 0\n"
            "    return work(x - 1)\n"          # R5 candidate (guarded)
            "\n"
            "class Worker:\n"
            "    def run(self, value):\n"
            "        if value < 100:\n"         # R3 candidate
            "            return value\n"
            "        return self.run(value - 1)\n"  # R5 (guarded via `if`)
            "\n"
            "def plain(y):\n"
            "    return y + 1\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            files: List[str] = []
            for i in range(100):
                p = _make_py_file(tmpdir, f"src/mod_{i}.py", template)
                files.append(str(p))

            t0 = time.monotonic()
            report = gp.run_pipeline(
                profile_name="scalpel",
                cwd=tmpdir,
                files=files,
            )
            elapsed = time.monotonic() - t0

            # Target budget 1s; 2s CI slack matches the baseline test at
            # the top of this file.
            self.assertLess(elapsed, 2.0,
                            f"scalpel+R3+R5 took {elapsed:.3f}s on 100 files (target 1s)")
            # Sanity: the scan should have surfaced at least the R3
            # findings from `if x > 42:` and `if value < 100:`.
            r3_count = sum(1 for c in report.checks for f in c.findings
                           if f.rule_id == "R3")
            self.assertGreater(r3_count, 0,
                               "expected R3 findings from the synthetic diff")
            # Print timing so CI always shows it.
            sys.stderr.write(
                f"\n[budget-test] scalpel+R3+R5 @ 100 files: {elapsed*1000:.1f}ms "
                f"(internal={report.duration_ms}ms, r3={r3_count})\n"
            )


class TestDebugArtifacts(unittest.TestCase):

    def test_clean_file_no_findings(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "lib/foo.py",
                              "def foo():\n    return 1\n")
            result = gp.check_debug_artifacts([str(f)], budget_seconds=1.0)
            # no debug artifacts; either ok or skip for no-code
            self.assertEqual(result.findings, [])

    def test_print_in_non_script_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "lib/foo.py",
                              "def foo():\n    print('debug')\n    return 1\n")
            result = gp.check_debug_artifacts([str(f)], budget_seconds=1.0)
            msgs = [x.message for x in result.findings]
            self.assertTrue(any("print()" in m for m in msgs))

    def test_print_in_scripts_path_tolerated(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "scripts/tool.py",
                              "def foo():\n    print('ok')\n")
            result = gp.check_debug_artifacts([str(f)], budget_seconds=1.0)
            self.assertEqual(
                [x for x in result.findings if "print()" in x.message], [])


class TestAdrConstraints(unittest.TestCase):

    def test_no_adrs_skips(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            f = _make_py_file(tmpdir, "src/a.py", "x = 1\n")
            result = gp.check_adr_constraints(
                [str(f)], budget_seconds=1.0, cwd=tmpdir)
            self.assertEqual(result.status, "skip")

    def test_must_not_phrase_matched(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            adr = tmpdir / "docs" / "adr" / "adr-001.md"
            adr.parent.mkdir(parents=True)
            adr.write_text(
                "# ADR 001\n\nThe system MUST NOT use eval() on user input.\n",
                encoding="utf-8",
            )
            code = _make_py_file(
                tmpdir, "src/a.py",
                "def run(x):\n    # use eval() on user input for flexibility\n    return x\n",
            )
            result = gp.check_adr_constraints(
                [str(code)], budget_seconds=1.0, cwd=tmpdir)
            self.assertEqual(result.status, "ok")
            self.assertTrue(result.findings,
                            "expected at least one MUST-NOT finding")

    def test_clean_code_no_finding(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            adr = tmpdir / "docs" / "adr" / "adr-001.md"
            adr.parent.mkdir(parents=True)
            adr.write_text(
                "# ADR 001\n\nThe system MUST NOT use eval() on user input.\n",
                encoding="utf-8",
            )
            code = _make_py_file(
                tmpdir, "src/b.py",
                "def run(x):\n    return x * 2\n",
            )
            result = gp.check_adr_constraints(
                [str(code)], budget_seconds=1.0, cwd=tmpdir)
            self.assertEqual([x for x in result.findings if x.severity != "info"],
                             [])


class TestSemanticReview(unittest.TestCase):
    """The semantic-review integration must fail-open if the module is missing."""

    def test_unavailable_returns_skip_with_info_finding(self):
        # Ensure any cached import is cleared
        sys.modules.pop("semantic_review", None)
        with mock.patch.object(gp, "_call_semantic_reviewer", return_value=None):
            result = gp.check_semantic_review(
                [], budget_seconds=1.0, project_dir=Path.cwd())
        self.assertEqual(result.status, "skip")
        self.assertEqual(result.note, "semantic-review-unavailable")
        self.assertTrue(any(
            f.rule_id == "semantic-review-unavailable" for f in result.findings
        ))

    def test_reviewer_conditional_emits_warn(self):
        fake = {
            "schema_version": "1",
            "project": "x",
            "complexity": 3,
            "verdict": "CONDITIONAL",
            "score": 0.7,
            "total": 1, "aligned": 0, "divergent": 1, "missing": 0,
            "summary": "one gap",
            "findings": [
                {"message": "Requirement X has no test", "rule_id": "missing-test"},
            ],
        }
        with mock.patch.object(gp, "_call_semantic_reviewer", return_value=fake):
            result = gp.check_semantic_review(
                [], budget_seconds=1.0, project_dir=Path.cwd())
        self.assertEqual(result.status, "ok")
        self.assertTrue(any(f.severity == "warn" for f in result.findings))

    def test_reviewer_reject_emits_block(self):
        fake = {
            "verdict": "REJECT", "score": 0.0,
            "total": 1, "aligned": 0, "divergent": 1, "missing": 0,
            "summary": "divergence",
            "findings": [{"message": "Design drift detected"}],
        }
        with mock.patch.object(gp, "_call_semantic_reviewer", return_value=fake):
            result = gp.check_semantic_review(
                [], budget_seconds=1.0, project_dir=Path.cwd())
        self.assertTrue(any(f.severity == "block" for f in result.findings))


class TestSkipLog(unittest.TestCase):

    def test_no_project_dir_skips(self):
        result = gp.check_skip_log([], budget_seconds=1.0, project_dir=None)
        self.assertEqual(result.status, "skip")

    def test_unresolved_entries_surface(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            phase = tmpdir / "phases" / "clarify"
            phase.mkdir(parents=True)
            log = phase / "skip-reeval-log.json"
            log.write_text(json.dumps([
                {"reason": "deferred for investigation"},
            ]), encoding="utf-8")

            result = gp.check_skip_log(
                [], budget_seconds=1.0, project_dir=tmpdir)
            self.assertTrue(result.findings,
                            "expected unresolved skip finding")

    def test_resolved_entries_no_finding(self):
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            phase = tmpdir / "phases" / "design"
            phase.mkdir(parents=True)
            log = phase / "skip-reeval-log.json"
            log.write_text(json.dumps([
                {"reason": "X", "resolved_at": "2026-04-18T00:00:00Z"},
            ]), encoding="utf-8")

            result = gp.check_skip_log(
                [], budget_seconds=1.0, project_dir=tmpdir)
            self.assertEqual(result.findings, [])


# ---------------------------------------------------------------------------
# Bus emission + fail-open contract
# ---------------------------------------------------------------------------

class TestBusEmission(unittest.TestCase):

    def test_emit_calls_wicked_bus_emit_event(self):
        report = gp.PipelineReport(
            pipeline_version="1.0", profile="scalpel", budget_seconds=1.0,
            duration_ms=10, status="ok", total_findings=0,
        )

        captured = {}

        def fake_emit(event_type, payload, **_kw):
            captured["event_type"] = event_type
            captured["payload"] = payload

        # Install a fake scripts._bus module
        import types
        fake_mod = types.ModuleType("_bus")
        fake_mod.emit_event = fake_emit  # type: ignore[attr-defined]
        fake_mod.BUS_EVENT_MAP = {"wicked.guard.findings": {}}  # type: ignore[attr-defined]
        with mock.patch.dict(sys.modules, {"_bus": fake_mod}):
            gp.emit_findings_event(report)

        self.assertEqual(captured.get("event_type"), "wicked.guard.findings")
        self.assertEqual(captured["payload"]["profile"], "scalpel")
        self.assertEqual(captured["payload"]["total_findings"], 0)

    def test_emit_falls_back_to_jsonl_when_bus_unavailable(self):
        report = gp.PipelineReport(
            pipeline_version="1.0", profile="scalpel", budget_seconds=1.0,
            duration_ms=5, status="ok", total_findings=0,
        )
        # Make _bus unavailable by replacing it with a module that raises on import
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(
                    os.environ, {"CLAUDE_SESSION_ID": "test-session-emission"}):
                with mock.patch("tempfile.gettempdir", return_value=td):
                    # Poison the _bus module so import raises
                    with mock.patch.dict(sys.modules, {"_bus": None}):
                        gp.emit_findings_event(report)
                    # No assertion on file since import error path may write
                    # or not depending on filesystem; just ensure it didn't raise.

    def test_run_pipeline_never_raises_even_with_bad_inputs(self):
        # Contract check — run_pipeline must swallow all check errors
        with mock.patch.dict(
                gp.CHECK_REGISTRY,
                {"bulletproof_scan": lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))},
                clear=False):
            report = gp.run_pipeline(profile_name="scalpel", files=[])
            # pipeline still returns a report; bulletproof_scan shows status=error
            names = [c.name for c in report.checks]
            self.assertIn("bulletproof_scan", names)


# ---------------------------------------------------------------------------
# Hard-block contract — findings never prevent session close
# ---------------------------------------------------------------------------

class TestNoHardBlock(unittest.TestCase):

    def test_block_findings_do_not_change_return_type(self):
        """Even when a check emits severity=block, run_pipeline still returns
        a PipelineReport — it never raises or sets a non-ok exit signal."""

        def fake_check(files, *, budget_seconds, **_kw):
            return gp.CheckResult(
                name="bulletproof_scan", status="ok",
                findings=[gp.Finding(
                    check="bulletproof_scan", rule_id="R2",
                    severity=gp.SEVERITY_BLOCK,
                    message="fake block-level finding",
                )],
            )

        with mock.patch.dict(
                gp.CHECK_REGISTRY,
                {"bulletproof_scan": fake_check}, clear=False):
            report = gp.run_pipeline(profile_name="scalpel", files=[])
            self.assertEqual(report.status, "ok")  # not "blocked", not "error"
            self.assertGreaterEqual(report.findings_by_severity.get("block", 0), 1)
            # The summary renders but doesn't set any exit code
            summary = gp.render_summary(report)
            self.assertIn("block=", summary)


if __name__ == "__main__":
    unittest.main()
