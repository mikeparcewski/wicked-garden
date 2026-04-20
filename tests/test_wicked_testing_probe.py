"""
tests/test_wicked_testing_probe.py

Unit tests for scripts/_wicked_testing_probe.py.

Coverage:
  - probe success (installed, in-range)
  - probe missing (subprocess not found / non-zero exit)
  - probe timeout — CH-02 actionable log: asserts log contains subprocess stderr,
    command string, and timeout context
  - probe out-of-range
  - escape hatch (WG_SKIP_WICKED_TESTING_CHECK=1)
  - cache hit — subprocess called only once when probe key already present
  - is_version_in_range: caret semantics, prerelease rejection, malformed input
  - read_pin_from_plugin_json: happy path, missing file, missing field
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/ is on path (conftest.py handles this globally, but explicit is safe)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from _wicked_testing_probe import (
    _PROBE_CMD,
    _PROBE_TIMEOUT_S,
    is_version_in_range,
    probe,
    read_pin_from_plugin_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_state(extras=None, wicked_testing_missing=None):
    state = MagicMock()
    state.extras = extras
    state.wicked_testing_missing = wicked_testing_missing
    return state


def _completed_process(stdout="0.1.3\n", stderr="", returncode=0):
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


# ---------------------------------------------------------------------------
# is_version_in_range
# ---------------------------------------------------------------------------

class TestIsVersionInRange:
    def test_exact_match(self):
        assert is_version_in_range("0.1.0", "^0.1.0") is True

    def test_higher_patch_in_range(self):
        assert is_version_in_range("0.1.3", "^0.1.0") is True

    def test_lower_patch_out_of_range(self):
        assert is_version_in_range("0.0.9", "^0.1.0") is False

    def test_higher_minor_out_of_range_when_major_zero(self):
        # ^0.1.0 → <0.2.0
        assert is_version_in_range("0.2.0", "^0.1.0") is False

    def test_major_nonzero_pin_upper_bound(self):
        # ^1.0.0 → <2.0.0
        assert is_version_in_range("1.9.99", "^1.0.0") is True
        assert is_version_in_range("2.0.0", "^1.0.0") is False

    def test_prerelease_rejected(self):
        assert is_version_in_range("0.1.1-beta.1", "^0.1.0") is False

    def test_malformed_installed(self):
        assert is_version_in_range("not-a-version", "^0.1.0") is False

    def test_malformed_pin(self):
        assert is_version_in_range("0.1.0", "0.1.0") is False  # no caret

    def test_malformed_pin_tilde(self):
        assert is_version_in_range("0.1.0", "~0.1.0") is False

    def test_too_few_parts(self):
        assert is_version_in_range("0.1", "^0.1.0") is False

    def test_non_numeric_parts(self):
        assert is_version_in_range("0.x.0", "^0.1.0") is False


# ---------------------------------------------------------------------------
# read_pin_from_plugin_json
# ---------------------------------------------------------------------------

class TestReadPinFromPluginJson:
    def test_happy_path(self, tmp_path):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        assert read_pin_from_plugin_json(str(plugin_json)) == "^0.1.0"

    def test_file_missing(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            read_pin_from_plugin_json(str(tmp_path / "nonexistent.json"))

    def test_field_absent(self, tmp_path):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"name": "wicked-garden"}))
        with pytest.raises(ValueError, match="missing wicked_testing_version"):
            read_pin_from_plugin_json(str(plugin_json))

    def test_field_wrong_type(self, tmp_path):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": 1}))
        with pytest.raises(ValueError, match="must be a string"):
            read_pin_from_plugin_json(str(plugin_json))

    def test_malformed_json(self, tmp_path):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text("{bad json}")
        with pytest.raises(ValueError, match="unreadable"):
            read_pin_from_plugin_json(str(plugin_json))


# ---------------------------------------------------------------------------
# probe — happy path (success)
# ---------------------------------------------------------------------------

class TestProbeSuccess:
    def test_probe_ok(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch("subprocess.run", return_value=_completed_process("0.1.3\n")) as mock_run:
            result = probe()

        assert result["status"] == "ok"
        assert result["version"] == "0.1.3"
        assert result["pin"] == "^0.1.0"
        assert result["error"] is None
        mock_run.assert_called_once()

    def test_probe_strips_v_prefix(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch("subprocess.run", return_value=_completed_process("v0.1.5\n")):
            result = probe()

        assert result["status"] == "ok"
        assert result["version"] == "0.1.5"


# ---------------------------------------------------------------------------
# probe — missing (subprocess not found, non-zero exit)
# ---------------------------------------------------------------------------

class TestProbeMissing:
    def test_npx_not_found(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch("subprocess.run", side_effect=FileNotFoundError("npx")):
            result = probe()

        assert result["status"] == "missing"
        assert result["version"] is None
        assert "npx not found" in result["error"]
        assert "Node.js" in result["error"]

    def test_nonzero_exit(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch(
            "subprocess.run",
            return_value=_completed_process("", "npm ERR! 404 Not Found", 1),
        ):
            result = probe()

        assert result["status"] == "missing"
        assert "npm ERR!" in result["error"]


# ---------------------------------------------------------------------------
# probe — timeout (CH-02 actionable log)
# ---------------------------------------------------------------------------

class TestProbeTimeout:
    def test_timeout_returns_error_status(self, tmp_path, monkeypatch, capsys):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        exc = subprocess.TimeoutExpired(cmd=_PROBE_CMD, timeout=_PROBE_TIMEOUT_S, stderr=b"connection error")
        with patch("subprocess.run", side_effect=exc):
            result = probe()

        assert result["status"] == "error"
        assert "probe timeout" in result["error"]
        assert str(_PROBE_TIMEOUT_S) in result["error"]

    def test_timeout_log_contains_subprocess_stderr(self, tmp_path, monkeypatch, capsys):
        """CH-02 hardening: log line MUST contain subprocess stderr."""
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        exc = subprocess.TimeoutExpired(
            cmd=_PROBE_CMD, timeout=_PROBE_TIMEOUT_S, stderr=b"ECONNREFUSED: connection refused"
        )
        with patch("subprocess.run", side_effect=exc):
            probe()

        captured = capsys.readouterr()
        assert "ECONNREFUSED" in captured.err, "log line must contain subprocess stderr"

    def test_timeout_log_contains_command(self, tmp_path, monkeypatch, capsys):
        """CH-02 hardening: log line MUST contain the command that was run."""
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        exc = subprocess.TimeoutExpired(cmd=_PROBE_CMD, timeout=_PROBE_TIMEOUT_S, stderr=b"some stderr")
        with patch("subprocess.run", side_effect=exc):
            probe()

        captured = capsys.readouterr()
        cmd_str = " ".join(_PROBE_CMD)
        assert cmd_str in captured.err, "log line must contain the command string"

    def test_timeout_log_contains_timeout_context(self, tmp_path, monkeypatch, capsys):
        """CH-02 hardening: log line MUST contain timeout context (duration)."""
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        exc = subprocess.TimeoutExpired(cmd=_PROBE_CMD, timeout=_PROBE_TIMEOUT_S, stderr=b"some stderr")
        with patch("subprocess.run", side_effect=exc):
            probe()

        captured = capsys.readouterr()
        assert str(_PROBE_TIMEOUT_S) in captured.err, "log line must contain timeout duration"


# ---------------------------------------------------------------------------
# probe — out-of-range
# ---------------------------------------------------------------------------

class TestProbeOutOfRange:
    def test_version_below_range(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch("subprocess.run", return_value=_completed_process("0.0.9\n")):
            result = probe()

        assert result["status"] == "out-of-range"
        assert result["version"] == "0.0.9"
        assert result["pin"] == "^0.1.0"
        assert result["error"] is None

    def test_version_above_minor_range(self, tmp_path, monkeypatch):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)

        with patch("subprocess.run", return_value=_completed_process("0.2.0\n")):
            result = probe()

        assert result["status"] == "out-of-range"
        assert result["version"] == "0.2.0"


# ---------------------------------------------------------------------------
# probe — escape hatch
# ---------------------------------------------------------------------------

class TestEscapeHatch:
    def test_skip_env_var_set(self, monkeypatch, capsys):
        monkeypatch.setenv("WG_SKIP_WICKED_TESTING_CHECK", "1")

        with patch("subprocess.run") as mock_run:
            result = probe()

        # Subprocess must NOT be called when escape hatch is active.
        mock_run.assert_not_called()

        assert result["status"] == "ok"
        assert result["version"] == "skipped"
        assert result["pin"] == "skipped"
        assert result["error"] is None

        # Warning must be emitted to stderr.
        captured = capsys.readouterr()
        assert "WG_SKIP_WICKED_TESTING_CHECK" in captured.err
        assert "offline dev mode" in captured.err
        assert "Do not use in production" in captured.err

    def test_skip_env_var_not_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WG_SKIP_WICKED_TESTING_CHECK", raising=False)
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))

        with patch("subprocess.run", return_value=_completed_process("0.1.0\n")) as mock_run:
            result = probe()

        mock_run.assert_called_once()
        assert result["status"] == "ok"

    def test_skip_env_var_value_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WG_SKIP_WICKED_TESTING_CHECK", "0")
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(json.dumps({"wicked_testing_version": "^0.1.0"}))
        monkeypatch.setattr("_wicked_testing_probe._PLUGIN_JSON_PATH", str(plugin_json))

        with patch("subprocess.run", return_value=_completed_process("0.1.0\n")) as mock_run:
            result = probe()

        # "0" must NOT trigger the escape hatch.
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# probe — cache hit (subprocess called only once)
# ---------------------------------------------------------------------------

class TestProbeCache:
    def test_cache_hit_bypasses_subprocess(self, tmp_path, monkeypatch):
        """When extras already has wicked_testing_probe, subprocess is not called again.

        The caching is enforced by _probe_wicked_testing in bootstrap.py
        (re-entrant guard). The probe() function itself does not cache —
        it's stateless. This test verifies the bootstrap guard behavior
        by calling _probe_wicked_testing() with a pre-populated extras dict.
        """
        import importlib
        import hooks.scripts  # noqa: ensure hooks scripts are importable

        # We test the guard in _probe_wicked_testing from bootstrap.py.
        sys.path.insert(0, str(_REPO_ROOT / "hooks" / "scripts"))
        try:
            import bootstrap
            importlib.reload(bootstrap)
        except Exception:
            pytest.skip("bootstrap module not importable in this test environment")
            return

        # Pre-populate extras with a cached probe result.
        cached_result = {"status": "ok", "version": "0.1.1", "pin": "^0.1.0", "error": None}
        state = MagicMock()
        state.extras = {"wicked_testing_probe": cached_result}
        state.update = MagicMock()

        with patch("subprocess.run") as mock_run:
            bootstrap._probe_wicked_testing(state)

        # Re-entrant guard: subprocess must NOT be called.
        mock_run.assert_not_called()
        # state.update must NOT be called (no changes).
        state.update.assert_not_called()
