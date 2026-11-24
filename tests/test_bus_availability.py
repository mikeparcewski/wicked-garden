"""Bus availability stays hermetic, including explicitly enabled fallback probes."""

from unittest.mock import Mock

import _bus


def test_bus_is_disabled_without_probing_by_default(monkeypatch):
    resolve = Mock(side_effect=AssertionError("disabled bus must not probe binaries"))
    monkeypatch.setattr(_bus, "_resolve_binary", resolve)

    assert _bus._check_available() is False
    resolve.assert_not_called()


def test_enabled_bus_uses_direct_binary(monkeypatch):
    monkeypatch.delenv("WICKED_BUS_DISABLED")
    monkeypatch.setattr(_bus.shutil, "which", lambda name: "/fake/wicked-bus")
    run = Mock(side_effect=AssertionError("direct binary needs no npx probe"))
    monkeypatch.setattr(_bus.subprocess, "run", run)

    assert _bus._check_available() is True
    assert _bus._build_cmd("status") == ["/fake/wicked-bus", "status"]
    run.assert_not_called()


def test_enabled_bus_npx_fallback_is_stubbed_and_cached(monkeypatch):
    monkeypatch.delenv("WICKED_BUS_DISABLED")
    monkeypatch.setattr(_bus.shutil, "which", lambda name: None)
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(_bus.subprocess, "run", run)

    assert _bus._check_available() is True
    assert _bus._check_available() is True
    assert _bus._build_cmd("status") == ["npx", "wicked-bus", "status"]
    run.assert_called_once_with(
        ["npx", "wicked-bus", "status", "--json"],
        capture_output=True, text=True, timeout=_bus._EMIT_TIMEOUT_SECONDS,
    )


def test_enabled_bus_missing_binary_fails_open_without_real_npx(monkeypatch):
    monkeypatch.delenv("WICKED_BUS_DISABLED")
    monkeypatch.setattr(_bus.shutil, "which", lambda name: None)
    run = Mock(side_effect=FileNotFoundError("npx"))
    monkeypatch.setattr(_bus.subprocess, "run", run)

    assert _bus._check_available() is False
    run.assert_called_once()
