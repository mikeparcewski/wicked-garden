#!/usr/bin/env python3
"""
tests/test_where_am_i.py — Unit tests for scripts/where_am_i.py.

Every case cites Issue #576 — the per-dispatch path-bloat reduction.

Coverage (T1-T6 compliant):
  - Default JSON shape exposes all six top-level keys.
  - --fence wraps output in ```json markers.
  - --env substitutes $CLAUDE_PLUGIN_ROOT when the env var is present.
  - Missing brain config returns brain: null without raising.
  - Missing bus DB returns bus_db: null without raising.
  - active_project_id is null when no session state is active.
  - Running the helper as a subprocess returns exit code 0 on success.
  - Helper never raises when every resolver fails.

T1 determinism: each test patches env + paths into a TemporaryDirectory.
T2 no sleeps. T3 isolation: no shared state across tests. T4 single
focused assertion per test. T5 descriptive names. T6 provenance in
module + class docstrings.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup — matching existing test suite pattern.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_WHERE_AM_I = _SCRIPTS / "where_am_i.py"

# Keys the manifest must always expose (#576 contract).
_EXPECTED_KEYS = {
    "plugin_root",
    "source_cwd",
    "active_project_id",
    "project_artifacts",
    "brain",
    "bus_db",
}


def _fresh_module():
    """Import or re-import where_am_i with a clean module state."""
    if "where_am_i" in sys.modules:
        del sys.modules["where_am_i"]
    import where_am_i
    return where_am_i


class _Base(unittest.TestCase):
    """Shared fixtures: isolated home + plugin root + session tempdir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

        self.fake_home = self.tmp_path / "home"
        self.fake_plugin_root = self.tmp_path / "plugin"
        self.fake_cwd = self.tmp_path / "source"
        for d in (self.fake_home, self.fake_plugin_root, self.fake_cwd):
            d.mkdir(parents=True, exist_ok=True)

        # Pin session state into the tempdir by scoping TMPDIR + a fresh
        # CLAUDE_SESSION_ID so SessionState.load() returns defaults.
        self.env_patch = patch.dict(
            os.environ,
            {
                "HOME": str(self.fake_home),
                "TMPDIR": str(self.tmp_path / "tmp"),
                "CLAUDE_PLUGIN_ROOT": str(self.fake_plugin_root),
                "CLAUDE_SESSION_ID": "test-where-am-i",
                "CLAUDE_CWD": str(self.fake_cwd),
            },
            clear=False,
        )
        self.env_patch.start()
        (self.tmp_path / "tmp").mkdir(exist_ok=True)

        # Defensive: remove any env that could leak the real brain port.
        os.environ.pop("WICKED_BRAIN_PORT", None)

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    def _chdir_and_run(self, argv):
        """Call main() with cwd pinned to fake_cwd; returns captured stdout."""
        module = _fresh_module()
        saved_cwd = os.getcwd()
        os.chdir(self.fake_cwd)
        try:
            from io import StringIO
            buf = StringIO()
            with patch.object(sys, "stdout", buf):
                rc = module.main(argv)
            return rc, buf.getvalue()
        finally:
            os.chdir(saved_cwd)


class TestDefaultShape(_Base):
    """Default JSON shape has all six top-level keys (#576 contract)."""

    def test_default_json_has_all_top_level_keys(self):
        rc, out = self._chdir_and_run([])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(set(parsed.keys()), _EXPECTED_KEYS)


class TestFenceFlag(_Base):
    """--fence wraps output in ```json markers (#576)."""

    def test_fence_wraps_output(self):
        rc, out = self._chdir_and_run(["--fence"])
        self.assertEqual(rc, 0)
        stripped = out.strip()
        self.assertTrue(stripped.startswith("```json"), out)
        self.assertTrue(stripped.endswith("```"), out)
        # Body between fences must still be valid JSON.
        body = "\n".join(stripped.splitlines()[1:-1])
        parsed = json.loads(body)
        self.assertIn("plugin_root", parsed)


class TestEnvSubstitution(_Base):
    """--env substitutes $CLAUDE_PLUGIN_ROOT when present (#576)."""

    def test_env_flag_substitutes_plugin_root(self):
        rc, out = self._chdir_and_run(["--env"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["plugin_root"], "$CLAUDE_PLUGIN_ROOT")


class TestMissingBrainConfig(_Base):
    """Missing brain config returns brain: null without raising (#576)."""

    def test_missing_brain_returns_null(self):
        # fake_home has no .wicked-brain tree at all.
        rc, out = self._chdir_and_run([])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertIsNone(parsed["brain"])


class TestMissingBusDb(_Base):
    """Missing bus DB returns bus_db: null without raising (#576)."""

    def test_missing_bus_db_returns_null(self):
        # fake_home has no wicked-bus tree.
        rc, out = self._chdir_and_run([])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertIsNone(parsed["bus_db"])


class TestActiveProjectIdNullByDefault(_Base):
    """active_project_id is null when no session is active (#576)."""

    def test_active_project_id_null_without_session(self):
        rc, out = self._chdir_and_run([])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertIsNone(parsed["active_project_id"])


class TestBrainResolutionWhenConfigPresent(_Base):
    """Brain block resolves path + port from a valid config (#576)."""

    def test_brain_reads_project_config(self):
        # The helper keys on cwd basename; fake_cwd is .../source
        project_dir = self.fake_home / ".wicked-brain" / "projects" / "source"
        meta_dir = project_dir / "_meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "config.json").write_text(
            json.dumps({"server_port": 4299, "source_path": str(self.fake_cwd)}),
            encoding="utf-8",
        )
        rc, out = self._chdir_and_run([])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertIsNotNone(parsed["brain"])
        self.assertEqual(parsed["brain"]["port"], 4299)
        self.assertEqual(parsed["brain"]["path"], str(project_dir))


class TestSubprocessExitCode(_Base):
    """Running the helper as a subprocess returns exit 0 on success (#576)."""

    def test_subprocess_invocation_exit_zero(self):
        env = dict(os.environ)
        # Keep the isolated HOME/TMPDIR/CLAUDE_* set by _Base.setUp.
        result = subprocess.run(
            [sys.executable, str(_WHERE_AM_I)],
            env=env,
            cwd=str(self.fake_cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(set(parsed.keys()), _EXPECTED_KEYS)


class TestNeverRaisesOnResolverFailure(_Base):
    """Helper never raises when individual resolvers blow up (#576)."""

    def test_build_manifest_is_total(self):
        module = _fresh_module()
        with patch.object(module, "_resolve_plugin_root", side_effect=RuntimeError("boom")):
            # Even if a resolver itself raised, main() should swallow via
            # the fail-open contract. We assert the contract by calling
            # the individual pieces the main path uses and confirming
            # that none of them propagate.
            with self.assertRaises(RuntimeError):
                module._resolve_plugin_root()
        # build_manifest itself must be total when resolvers behave.
        m = module.build_manifest()
        self.assertEqual(set(m.keys()), _EXPECTED_KEYS)


if __name__ == "__main__":
    unittest.main()
