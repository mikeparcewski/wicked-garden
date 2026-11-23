"""The editor install root follows the daemon's state home (garden#1532).

A daemon started on a scratch ``WICKED_HOME`` (a proof or test daemon) staged installed editor packs in the person's
live ``~/.wicked/editors``. The root is ``--install-root``, else ``$WICKED_EDITOR_INSTALL_ROOT``, else
``$WICKED_HOME/editors``, else ``~/.wicked/editors``; an empty variable counts as unset.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "mcp"))

from daemon_fixture import FakeDaemon  # noqa: E402

SCRIPTS = REPO / "scripts" / "editor"
ROOT_VARS = ("WICKED_CREW_URL", "WICKED_HOME", "WICKED_EDITOR_INSTALL_ROOT")


def _run(script: str, *args: str, env: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    full = {k: v for k, v in os.environ.items() if k not in ROOT_VARS}
    full.update(env)
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                          env=full, cwd=cwd, timeout=240)


@pytest.fixture
def pack(tmp_path):
    out = tmp_path / "tree" / "editor"
    done = _run("scaffold.py", "--vendor", "acme", "--id", "acme-json", "--title", "JSON viewer",
                "--kinds", "page,document", "--out", str(out), env={})
    assert done.returncode == 0, done.stderr
    return out


def _plan_paths(pack: Path, env: dict) -> list[str]:
    with FakeDaemon() as d:
        done = _run("install.py", "--dir", str(pack), "--dry-run", "--json",
                    env={"WICKED_CREW_URL": d.origin, **env})
    assert done.returncode == 0, done.stdout + done.stderr
    plan = json.loads(done.stdout.strip().splitlines()[-1])
    return [w["path"] for w in plan["choices"][0]["writes"]]


def test_the_plan_stages_under_wicked_home_when_no_install_root_is_set(tmp_path, pack):
    home = tmp_path / "scratch-home"
    paths = _plan_paths(pack, {"HOME": str(tmp_path / "person"), "WICKED_HOME": str(home)})
    assert paths[0] == str(home / "editors" / "acme-json" / "current")
    assert str(home / "editors" / "acme-json" / "installed.json") in paths
    assert not any(p.startswith(str(tmp_path / "person")) for p in paths), "nothing in the person's ~/.wicked"


def test_an_empty_wicked_home_counts_as_unset(tmp_path, pack):
    person = tmp_path / "person"
    paths = _plan_paths(pack, {"HOME": str(person), "WICKED_HOME": ""})
    assert paths[0] == str(person / ".wicked" / "editors" / "acme-json" / "current")


def test_the_install_root_variable_still_wins_over_wicked_home(tmp_path, pack):
    root = tmp_path / "explicit"
    paths = _plan_paths(pack, {"WICKED_HOME": str(tmp_path / "scratch-home"), "WICKED_EDITOR_INSTALL_ROOT": str(root)})
    assert paths[0] == str(root / "acme-json" / "current")


def test_the_install_writes_under_wicked_home(tmp_path, pack):
    home, person = tmp_path / "scratch-home", tmp_path / "person"
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-json"}],
                                                        "conformance": {"ok": True}})
        done = _run("install.py", "--dir", str(pack), "--target", "daemon", "--json",
                    env={"WICKED_CREW_URL": d.origin, "HOME": str(person), "WICKED_HOME": str(home)})
        body = d.requests[0]["body"]
    assert done.returncode == 0, done.stdout + done.stderr
    current = home / "editors" / "acme-json" / "current"
    assert body["packRoot"] == str(current.resolve())
    assert (current / "wicked-pack.json").is_file()
    assert (home / "editors" / "acme-json" / "installed.json").is_file()
    assert not (person / ".wicked").exists()
