"""test_loom_internals.py — unit tests for the absorbed scripts/loom/ package.

Ported from archived/wicked-loom/tests/ (Phase B — ECOSYSTEM-RATIONALIZATION.md
§5a). The full wicked-loom test suite covered flow/flowstate/busemit which are
RETIRED — those are NOT ported. What IS ported:

  - compose._meets_pin and _parse_version (the version-pin gate logic — critical,
    untested path until now; SIG-5 from the Phase B adversarial review)
  - compose.check_peer (resolve→probe→parse→compare)
  - compose.install_peer (headless install command dispatch)
  - compose.check_all (one row per registered peer)
  - resolve.resolve and resolve.resolve_version_bin (peer resolution ladder)
  - manifest peer registry (spot checks — vault install_cmd post-absorption)

Key differences from the archived tests:
  - vault install_cmd is now ["npx", "wicked-testing", "install"] (vault absorbed
    into wicked-testing; archived tests expected ["npx", "wicked-vault-install"])
  - brain is STATUS_EXPERIMENTAL (bridge/deprecation period), so capability_ok=False
    for brain rows; archived tests expected all peers capability_ok=True
  - imports are prefixed `loom.` (in-process package, not a top-level CLI module)

sys.path setup: the root conftest.py inserts scripts/ at sys.path[0] before any
test module is collected (pytest_configure hook), so `from loom import ...` resolves
to scripts/loom/ without any per-test path manipulation.
"""

from __future__ import annotations

import shutil
import unittest
from unittest.mock import patch

from loom import compose, manifest
from loom import resolve as resolve_mod
from loom.compose import RunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _runner(stdout: str = "", code: int = 0):
    """Return a fake runner that always yields the given stdout + exit code."""
    def run(cmd, timeout=None):
        return RunResult(returncode=code, stdout=stdout, stderr="")
    return run


def _capturing_runner(stdout: str = "9.9.9", code: int = 0):
    """A runner that records every argv it was handed."""
    calls = []

    def run(cmd, timeout=None):
        calls.append(cmd)
        return RunResult(returncode=code, stdout=stdout, stderr="")

    return run, calls


# ---------------------------------------------------------------------------
# _parse_version and _meets_pin  (SIG-5 — the critical untested path)
# ---------------------------------------------------------------------------

class MeetsPinTests(unittest.TestCase):
    """_meets_pin is the version-gate logic on the critical peer-check path.
    A wrong comparison means a peer on a too-old version silently passes as ok.
    Every edge case here is a potential silent regression."""

    def test_meets_pin_exact_match(self):
        self.assertTrue(compose._meets_pin("0.3.0", "0.3"))

    def test_meets_pin_patch_above(self):
        self.assertTrue(compose._meets_pin("0.3.5", "0.3"))

    def test_meets_pin_minor_above(self):
        self.assertTrue(compose._meets_pin("0.4.0", "0.3"))

    def test_meets_pin_major_above(self):
        self.assertTrue(compose._meets_pin("1.0.0", "0.3"))

    def test_meets_pin_below_is_false(self):
        self.assertFalse(compose._meets_pin("0.2.9", "0.3"))

    def test_meets_pin_same_major_minor_below_is_false(self):
        self.assertFalse(compose._meets_pin("0.2.99", "0.3"))

    def test_meets_pin_zero_zero_always_true(self):
        # Pin 0.0 — any installed version >= 0.0
        self.assertTrue(compose._meets_pin("0.0.1", "0.0"))

    def test_meets_pin_unparseable_installed_is_false(self):
        self.assertFalse(compose._meets_pin("not-a-version", "0.3"))

    def test_meets_pin_unparseable_pin_is_false(self):
        self.assertFalse(compose._meets_pin("0.3.0", "bad"))

    def test_meets_pin_both_unparseable_is_false(self):
        self.assertFalse(compose._meets_pin("nope", "nope"))

    def test_parse_version_extracts_semver(self):
        self.assertEqual(compose._parse_version("wicked-vault 0.3.2\n"), "0.3.2")

    def test_parse_version_bare_version(self):
        self.assertEqual(compose._parse_version("0.14.1"), "0.14.1")

    def test_parse_version_v_prefix(self):
        self.assertEqual(compose._parse_version("v2.1.0"), "2.1.0")

    def test_parse_version_no_patch_defaults_to_zero(self):
        self.assertEqual(compose._parse_version("0.3"), "0.3.0")

    def test_parse_version_no_version_is_none(self):
        self.assertIsNone(compose._parse_version("no version here"))

    def test_parse_version_empty_is_none(self):
        self.assertIsNone(compose._parse_version(""))


# ---------------------------------------------------------------------------
# compose.check_peer — reachability + version probe
# ---------------------------------------------------------------------------

class CheckPeerTests(unittest.TestCase):

    def test_ok_when_version_meets_pin(self):
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-vault"]):
            r = compose.check_peer("vault", run=_runner(stdout="wicked-vault 0.3.2\n"))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["installed"], "0.3.2")
        self.assertEqual(r["pin"], "0.3")
        self.assertTrue(r["ok"])

    def test_drift_when_below_pin(self):
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-vault"]):
            r = compose.check_peer("vault", run=_runner(stdout="0.2.9"))
        self.assertEqual(r["status"], "drift")
        self.assertFalse(r["ok"])

    def test_missing_when_unresolvable(self):
        with patch.object(compose, "resolve_version_bin", return_value=None):
            r = compose.check_peer("vault", run=_runner())
        self.assertEqual(r["status"], "missing")
        self.assertFalse(r["ok"])

    def test_nonzero_exit_but_resolved_is_present_not_error(self):
        """A responding binary that exits non-zero (old help-style CLIs) is
        PRESENT, not a hard error.  Cry-wolf finding: was reported as error."""
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-vault"]):
            r = compose.check_peer("vault", run=_runner(code=1))
        self.assertEqual(r["status"], "present")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["status"], "error")

    def test_probe_raise_is_error(self):
        """The ONLY path to 'error' after resolution: the probe RAISED."""
        def boom(cmd, timeout=None):
            raise OSError("binary vanished")
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-vault"]):
            r = compose.check_peer("vault", run=boom)
        self.assertEqual(r["status"], "error")
        self.assertFalse(r["ok"])

    def test_unknown_peer_is_error(self):
        r = compose.check_peer("frobnicate")
        self.assertEqual(r["status"], "error")

    # --- capability is surfaced on every row, orthogonal to reachability ---

    def test_capability_carried_on_ok_row(self):
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-vault"]):
            r = compose.check_peer("vault", run=_runner(stdout="wicked-vault 0.3.2\n"))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["capability"], "wired")
        self.assertTrue(r["capability_ok"])

    def test_capability_carried_on_missing_row(self):
        with patch.object(compose, "resolve_version_bin", return_value=None):
            r = compose.check_peer("vault", run=_runner())
        self.assertEqual(r["capability"], "wired")
        self.assertTrue(r["capability_ok"])

    def test_unknown_peer_has_null_capability(self):
        r = compose.check_peer("frobnicate")
        self.assertIsNone(r["capability"])
        self.assertFalse(r["capability_ok"])

    def test_brain_capability_is_experimental_not_wired(self):
        """brain is STATUS_EXPERIMENTAL in the post-absorption manifest
        (bridge/deprecation period).  Its capability_ok must be False —
        the never-fake contract: a capability-gap is reported, not a silent wired."""
        with patch.object(compose, "resolve_version_bin",
                          return_value=["wicked-brain-server"]):
            r = compose.check_peer("brain",
                                   run=_runner(stdout="wicked-brain-server 0.14.0\n"))
        self.assertEqual(r["capability"], "experimental")
        self.assertFalse(r["capability_ok"])
        # Reachability is separate: resolved + good version = ok
        self.assertEqual(r["status"], "ok")

    # --- cry-wolf: a healthy bus must never be reported error ----------------

    _BUS_HELP_JSON = (
        '{\n'
        '  "usage": "wicked-bus <command> [options]",\n'
        '  "commands": ["init", "emit", "subscribe", "status"],\n'
        '  "global_flags": ["--db-path <path>", "--json"]\n'
        '}\n'
    )

    def test_healthy_bus_help_style_is_not_error(self):
        run, calls = _capturing_runner(stdout=self._BUS_HELP_JSON, code=1)
        with patch.object(compose, "resolve_version_bin", return_value=["wicked-bus"]):
            r = compose.check_peer("bus", run=run)
        self.assertNotEqual(r["status"], "error")
        self.assertEqual(r["status"], "present")
        self.assertTrue(r["ok"])

    def test_genuinely_absent_bus_is_missing(self):
        with patch.object(compose, "resolve_version_bin", return_value=None):
            r = compose.check_peer("bus", run=_runner())
        self.assertEqual(r["status"], "missing")
        self.assertFalse(r["ok"])


# ---------------------------------------------------------------------------
# compose.check_all
# ---------------------------------------------------------------------------

class CheckAllTests(unittest.TestCase):

    def test_returns_one_row_per_registered_peer(self):
        with patch.object(compose, "resolve_version_bin", return_value=["x"]):
            rows = compose.check_all(run=_runner(stdout="9.9.9"))
        peer_names = {r["peer"] for r in rows}
        self.assertEqual(peer_names, {"vault", "testing", "brain", "bus"})

    def test_all_rows_carry_capability(self):
        with patch.object(compose, "resolve_version_bin", return_value=["x"]):
            rows = compose.check_all(run=_runner(stdout="9.9.9"))
        for row in rows:
            self.assertIn("capability", row)
            self.assertIn("capability_ok", row)

    def test_brain_row_capability_ok_is_false(self):
        """brain is EXPERIMENTAL — capability_ok must be False in check_all output."""
        with patch.object(compose, "resolve_version_bin", return_value=["x"]):
            rows = compose.check_all(run=_runner(stdout="9.9.9"))
        brain_row = next(r for r in rows if r["peer"] == "brain")
        self.assertFalse(brain_row["capability_ok"])
        self.assertEqual(brain_row["capability"], "experimental")

    def test_wired_peers_capability_ok_is_true(self):
        """vault, testing, bus are STATUS_WIRED — capability_ok must be True."""
        with patch.object(compose, "resolve_version_bin", return_value=["x"]):
            rows = compose.check_all(run=_runner(stdout="9.9.9"))
        for row in rows:
            if row["peer"] in ("vault", "testing", "bus"):
                self.assertTrue(row["capability_ok"], f"{row['peer']} should be wired")
                self.assertEqual(row["capability"], "wired")


# ---------------------------------------------------------------------------
# compose.install_peer — headless install dispatch
# ---------------------------------------------------------------------------

class InstallPeerTests(unittest.TestCase):

    def test_install_vault_runs_wicked_testing_install(self):
        """Post-absorption: vault is now installed via wicked-testing.
        install_cmd = ["npx", "wicked-testing", "install"] (not the old
        ["npx", "wicked-vault-install"])."""
        calls = []

        def run(cmd, timeout=None):
            calls.append(cmd)
            return RunResult(returncode=0, stdout="ok", stderr="")

        r = compose.install_peer("vault", run=run)
        self.assertEqual(calls, [["npx", "wicked-testing", "install"]])
        self.assertEqual(r["status"], "installed")

    def test_install_unknown_peer_is_error(self):
        r = compose.install_peer("nope", run=_runner())
        self.assertEqual(r["status"], "error")

    def test_install_failure_nonzero_exit_is_install_failed(self):
        r = compose.install_peer("vault", run=_runner(code=1))
        self.assertEqual(r["status"], "install-failed")


# ---------------------------------------------------------------------------
# resolve.resolve — peer resolution ladder
# ---------------------------------------------------------------------------

class ResolvePeerTests(unittest.TestCase):

    def setUp(self):
        # Ensure env vars don't bleed between tests
        import os
        for var in ("WICKED_VAULT_BIN", "WICKED_BRAIN_BIN",
                    "WICKED_TESTING_BIN", "WICKED_BUS_BIN"):
            os.environ.pop(var, None)

    def tearDown(self):
        import os
        for var in ("WICKED_VAULT_BIN", "WICKED_BRAIN_BIN",
                    "WICKED_TESTING_BIN", "WICKED_BUS_BIN"):
            os.environ.pop(var, None)

    def test_env_var_override_wins(self):
        import os
        os.environ["WICKED_VAULT_BIN"] = "/opt/custom/vault"
        self.assertEqual(resolve_mod.resolve("vault"), ["/opt/custom/vault"])

    def test_empty_env_var_is_killswitch(self):
        import os
        os.environ["WICKED_VAULT_BIN"] = ""
        self.assertIsNone(resolve_mod.resolve("vault"))

    def test_path_lookup_when_no_env(self):
        with patch.object(shutil, "which", return_value="/usr/local/bin/wicked-vault"):
            self.assertEqual(resolve_mod.resolve("vault"), ["/usr/local/bin/wicked-vault"])

    def test_npx_fallback_when_not_on_path(self):
        with patch.object(shutil, "which", return_value=None):
            self.assertEqual(resolve_mod.resolve("vault"), ["npx", "wicked-vault"])

    def test_unknown_peer_returns_none(self):
        self.assertIsNone(resolve_mod.resolve("nope"))


# ---------------------------------------------------------------------------
# resolve.resolve_version_bin — probe binary may differ from run package
# ---------------------------------------------------------------------------

class ResolveVersionBinTests(unittest.TestCase):

    def setUp(self):
        import os
        for var in ("WICKED_VAULT_BIN", "WICKED_BRAIN_BIN"):
            os.environ.pop(var, None)

    def tearDown(self):
        import os
        for var in ("WICKED_VAULT_BIN", "WICKED_BRAIN_BIN"):
            os.environ.pop(var, None)

    def test_brain_resolves_server_via_path(self):
        with patch.object(shutil, "which",
                          return_value="/usr/local/bin/wicked-brain-server"):
            self.assertEqual(resolve_mod.resolve_version_bin("brain"),
                             ["/usr/local/bin/wicked-brain-server"])

    def test_brain_npx_fallback_uses_server_binary(self):
        with patch.object(shutil, "which", return_value=None):
            self.assertEqual(resolve_mod.resolve_version_bin("brain"),
                             ["npx", "wicked-brain-server"])

    def test_same_binary_peer_uses_npm_package(self):
        """vault/testing/bus: version_bin is empty → falls back to npm_package."""
        with patch.object(shutil, "which", return_value=None):
            self.assertEqual(resolve_mod.resolve_version_bin("vault"),
                             ["npx", "wicked-vault"])

    def test_killswitch_respected(self):
        import os
        os.environ["WICKED_BRAIN_BIN"] = ""
        self.assertIsNone(resolve_mod.resolve_version_bin("brain"))

    def test_env_override_respected(self):
        import os
        os.environ["WICKED_BRAIN_BIN"] = "/opt/custom/brain"
        self.assertEqual(resolve_mod.resolve_version_bin("brain"),
                         ["/opt/custom/brain"])

    def test_unknown_peer_returns_none(self):
        self.assertIsNone(resolve_mod.resolve_version_bin("nope"))


# ---------------------------------------------------------------------------
# manifest — spot checks post-absorption
# ---------------------------------------------------------------------------

class ManifestTests(unittest.TestCase):

    def test_vault_install_cmd_is_wicked_testing(self):
        """Post-absorption: vault comes via wicked-testing. install_cmd must
        NOT be the old wicked-vault-install."""
        vault = manifest.get("vault")
        self.assertIsNotNone(vault)
        self.assertEqual(vault.install_cmd, ["npx", "wicked-testing", "install"])
        self.assertNotIn("wicked-vault-install", " ".join(vault.install_cmd))

    def test_vault_is_wired(self):
        vault = manifest.get("vault")
        self.assertTrue(vault.is_wired)
        self.assertEqual(vault.status, "wired")

    def test_brain_is_experimental(self):
        """brain must be STATUS_EXPERIMENTAL — bridge/deprecation period."""
        brain = manifest.get("brain")
        self.assertIsNotNone(brain)
        self.assertEqual(brain.status, "experimental")
        self.assertFalse(brain.is_wired)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(manifest.get("does-not-exist"))

    def test_all_registered_peers_have_install_cmd(self):
        for name, peer in manifest.PEERS.items():
            self.assertTrue(peer.install_cmd, f"{name} missing install_cmd")

    def test_wired_statuses_only_contains_wired(self):
        """The never-fake contract: ONLY 'wired' satisfies a gate."""
        self.assertIn("wired", manifest.WIRED_STATUSES)
        self.assertNotIn("experimental", manifest.WIRED_STATUSES)
        self.assertNotIn("planned", manifest.WIRED_STATUSES)


if __name__ == "__main__":
    unittest.main()
