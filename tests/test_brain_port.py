"""tests/test_brain_port.py — port resolution + auto-start contract.

Covers the regression where per-project brain configs without a source_path
field fell through to the 4242 default while the server listened on another
port (the server probes upward from 4242 and writes the bound port back to
config) — making every hook probe a false negative: "server is not running"
against a healthy server. Also pins the ensure_server() contract: hooks fix
a stopped server deterministically instead of directing the model to.
"""

import json

import _brain_port


def _write_cfg(path, **fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fields))


def test_resolve_port_by_directory_name_convention(tmp_path, monkeypatch):
    """Configs without source_path resolve via projects/{cwd basename}."""
    monkeypatch.delenv("WICKED_BRAIN_PORT", raising=False)
    home = tmp_path / "home"
    proj = tmp_path / "workspaces" / "myproj"
    proj.mkdir(parents=True)
    _write_cfg(
        home / ".wicked-brain" / "projects" / "myproj" / "_meta" / "config.json",
        server_port=4777,
    )
    monkeypatch.setattr(_brain_port.Path, "home", lambda: home)
    monkeypatch.chdir(proj)
    assert _brain_port.resolve_port() == 4777


def test_resolve_port_source_path_match_wins_over_name(tmp_path, monkeypatch):
    """A config whose source_path matches cwd beats the name-convention dir."""
    monkeypatch.delenv("WICKED_BRAIN_PORT", raising=False)
    home = tmp_path / "home"
    proj = tmp_path / "workspaces" / "myproj"
    proj.mkdir(parents=True)
    _write_cfg(
        home / ".wicked-brain" / "projects" / "myproj" / "_meta" / "config.json",
        server_port=4777,
    )
    _write_cfg(
        home / ".wicked-brain" / "projects" / "renamed-brain" / "_meta" / "config.json",
        server_port=4888,
        source_path=str(proj),
    )
    monkeypatch.setattr(_brain_port.Path, "home", lambda: home)
    monkeypatch.chdir(proj)
    assert _brain_port.resolve_port() == 4888


def test_resolve_port_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.delenv("WICKED_BRAIN_PORT", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    proj = tmp_path / "elsewhere"
    proj.mkdir()
    monkeypatch.setattr(_brain_port.Path, "home", lambda: home)
    monkeypatch.chdir(proj)
    assert _brain_port.resolve_port() == 4242


def test_ensure_server_short_circuits_when_healthy(monkeypatch):
    monkeypatch.setattr(_brain_port, "_AUTOSTART_ATTEMPTED", False)
    monkeypatch.setattr(_brain_port, "_health_ok", lambda timeout=1.0: True)
    assert _brain_port.ensure_server() is True


def test_ensure_server_single_attempt_without_cli(monkeypatch):
    """No wicked-brain-call on PATH → one failed attempt, then memoized."""
    import shutil

    monkeypatch.setattr(_brain_port, "_AUTOSTART_ATTEMPTED", False)
    monkeypatch.setattr(_brain_port, "_health_ok", lambda timeout=1.0: False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert _brain_port.ensure_server(wait_secs=0.1) is False
    assert _brain_port._AUTOSTART_ATTEMPTED is True
    # Second call must not re-attempt the spawn (memoized, still False).
    assert _brain_port.ensure_server(wait_secs=0.1) is False
