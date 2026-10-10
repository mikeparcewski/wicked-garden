"""The editor-plugin scripts (scripts/editor/): scaffold, pin, install, and conformance's argument
and fail-closed paths. The browser cases run only when Chromium and a studio dist are present
(``WICKED_STUDIO_DIST``); CI without them still pins every refusal.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "mcp"))
sys.path.insert(0, str(REPO / "scripts"))

from daemon_fixture import FakeDaemon, closed_origin  # noqa: E402
from pack.check import check_pack  # noqa: E402

SCRIPTS = REPO / "scripts" / "editor"
FIXTURE_ENTRY = "editors/acme-json/index.html"


def run(script: str, *args: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    full_env = {k: v for k, v in os.environ.items() if k != "WICKED_CREW_URL"}
    full_env.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                          env=full_env, cwd=cwd, timeout=240)


def scaffold(out: Path, *extra: str) -> subprocess.CompletedProcess:
    return run("scaffold.py", "--vendor", "acme", "--id", "acme-json", "--title", "JSON viewer",
               "--kinds", "page,document", "--out", str(out), *extra)


# ── scaffold + pin ─────────────────────────────────────────────────────────────────────────

def test_scaffold_writes_a_spec2_pack_that_passes_pack_check(tmp_path):
    out = tmp_path / "pack"
    done = scaffold(out)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    manifest = json.loads((out / "wicked-pack.json").read_text())
    editor = manifest["editors"][0]
    assert manifest["spec"] == 2 and manifest["vendor"] == "acme" and editor["id"] == "acme-json"
    assert editor["entry"] == FIXTURE_ENTRY and editor["sizes"] == ["inline", "pane", "full"]
    assert [p["id"] for p in editor["permissions"]] == ["artifact.read", "selection.chip", "ui.fullscreen"]
    assert all(p["why"] for p in editor["permissions"])
    html = (out / FIXTURE_ENTRY).read_text()
    assert "__EDITOR" not in html and "const EDITOR = 'acme-json', VERSION = '0.1.0'" in html
    assert report["editor"]["sha256"] == editor["sha256"]
    assert [f.render() for f in check_pack(out, garden_root=REPO) if f.level == "error"] == []


@pytest.mark.parametrize("args, needle", [
    (["--vendor", "wicked", "--id", "wicked-x"], "reserved"),
    (["--vendor", "acme", "--id", "other-x"], "starting with 'acme-'"),
    (["--vendor", "acme", "--id", "acme-x", "--kinds", "Page"], "invalid kinds"),
    (["--vendor", "acme", "--id", "acme-x", "--permissions", "artifact.read,run.agents"], "unknown permissions"),
    (["--vendor", "acme", "--id", "acme-x", "--permissions", "network.media"], "no network"),
])
def test_scaffold_refuses_bad_names_kinds_and_permissions(tmp_path, args, needle):
    base = {"--title": "X", "--kinds": "page", "--out": str(tmp_path / "p")}
    for i in range(0, len(args), 2):
        base[args[i]] = args[i + 1]
    flat = [x for kv in base.items() for x in kv]
    done = run("scaffold.py", *flat)
    assert done.returncode == 2 and needle in done.stderr
    assert not (tmp_path / "p").exists()


def test_scaffold_never_overwrites(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    (out / "README.md").write_text("mine\n")
    done = scaffold(out)
    assert done.returncode == 2 and "refusing to overwrite" in done.stderr
    assert (out / "README.md").read_text() == "mine\n" and not (out / "wicked-pack.json").exists()


def test_pin_re_pins_an_edited_entry_and_pack_check_follows(tmp_path):
    out = tmp_path / "pack"
    assert scaffold(out).returncode == 0
    entry = out / FIXTURE_ENTRY
    entry.write_text(entry.read_text().replace("Loading…", "Loading the JSON…"))
    assert any(f.code == "PK064" for f in check_pack(out, garden_root=REPO))
    done = run("pin.py", str(out))
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["editors"][0]["changed"] is True
    assert [f.render() for f in check_pack(out, garden_root=REPO) if f.level == "error"] == []


# ── install ────────────────────────────────────────────────────────────────────────────────

def _install_env(daemon_origin: str, root: Path) -> dict:
    return {"WICKED_CREW_URL": daemon_origin, "WICKED_EDITOR_INSTALL_ROOT": str(root)}


def test_dry_run_plans_two_choices_with_their_program_owned_writes(tmp_path):
    pack = tmp_path / "tree" / "editor"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "home" / ".wicked" / "editors"
    with FakeDaemon() as d:
        done = run("install.py", "--from-run", "--dry-run", "--json",
                   env={**_install_env(d.origin, root), "WICKED_TREE": str(tmp_path / "tree")})
        assert d.requests == []  # the plan asks the daemon nothing and writes nothing
    assert done.returncode == 0, done.stderr
    plan = json.loads(done.stdout.strip().splitlines()[-1])
    assert plan["dry_run"] is True and plan["key"] == "acme-json"
    assert [c["id"] for c in plan["choices"]] == ["daemon", "daemon-off"] and plan["choices"][0]["default"] is True
    paths = [w["path"] for w in plan["choices"][0]["writes"]]
    assert paths[0] == str(root.resolve() / "acme-json" / "current") or paths[0].endswith("acme-json/current")
    assert any(p.endswith("/api/v1/editors") for p in paths)
    assert all(w["operator_owned"] is False for c in plan["choices"] for w in c["writes"])
    assert not root.exists()


def test_install_stages_registers_and_records(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-json"}],
                                                        "conformance": {"ok": True}})
        done = run("install.py", "--dir", str(pack), "--target", "daemon-off", "--json", env=_install_env(d.origin, root))
        body = d.requests[0]["body"]
    assert done.returncode == 0, done.stdout + done.stderr
    current = root / "acme-json" / "current"
    assert body == {"packRoot": str(current.resolve()), "enabled": False}
    assert (current / FIXTURE_ENTRY).read_bytes() == (pack / FIXTURE_ENTRY).read_bytes()
    assert sorted(p.name for p in current.iterdir()) == ["README.md", "editors", "wicked-pack.json"]
    record = json.loads((root / "acme-json" / "installed.json").read_text())
    assert record["key"] == "acme-json" and record["enabled"] is False


def test_a_refused_install_rolls_the_staged_copy_back(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    (root / "acme-json" / "current").mkdir(parents=True)
    (root / "acme-json" / "current" / "marker").write_text("the install before")
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (422, {"error": "conformance failed", "code": "editor_not_conformant",
                                                        "conformance": {"ok": False}})
        done = run("install.py", "--dir", str(pack), "--json", env=_install_env(d.origin, root))
    assert done.returncode == 1
    out = json.loads(done.stdout)
    assert out["ok"] is False and "conformance failed" in out["error"]
    assert (root / "acme-json" / "current" / "marker").read_text() == "the install before"
    assert not (root / "acme-json" / "installed.json").exists()


def test_install_with_no_daemon_installs_nothing(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    done = run("install.py", "--dir", str(pack), "--json", env=_install_env(closed_origin(), root))
    assert done.returncode == 1 and "no daemon" in json.loads(done.stdout)["error"]
    assert not (root / "acme-json" / "current").exists()


def test_install_needs_an_origin_and_never_guesses_a_port(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    env = {k: v for k, v in os.environ.items() if k != "WICKED_CREW_URL"}
    done = subprocess.run([sys.executable, str(SCRIPTS / "install.py"), "--dir", str(pack), "--json"],
                          capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 2 and "never assume a port" in done.stdout


def test_uninstall_removes_every_editor_of_the_pack_then_the_copy(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    shutil.copytree(pack, root / "acme-json" / "current")
    with FakeDaemon() as d:
        d.routes[("DELETE", "/api/v1/editors/acme-json")] = (200, {"removed": True})
        done = run("install.py", "--uninstall", "acme-json", "--json", env=_install_env(d.origin, root))
        assert [(r["method"], r["path"]) for r in d.requests] == [("DELETE", "/api/v1/editors/acme-json")]
    assert done.returncode == 0, done.stdout
    assert json.loads(done.stdout)["registry"] == {"acme-json": "removed"} and not (root / "acme-json").exists()


# ── conformance ────────────────────────────────────────────────────────────────────────────

def test_conformance_needs_a_host_and_never_guesses_a_port(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    env = {k: v for k, v in os.environ.items() if k != "WICKED_CREW_URL"}
    done = subprocess.run([sys.executable, str(SCRIPTS / "conformance.py"), "--pack", str(pack)],
                          capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 2 and "never a guessed port" in json.loads(done.stdout)["error"]


def test_conformance_refuses_a_pack_with_no_editors(tmp_path):
    (tmp_path / "wicked-pack.json").write_text(json.dumps({"spec": 1, "name": "acme-x", "vendor": "acme", "version": "0.1.0"}))
    done = run("conformance.py", "--pack", str(tmp_path), "--studio-dist", str(tmp_path))
    assert done.returncode == 2 and "declares no editors" in json.loads(done.stdout)["error"]


def _browser_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return False
    dist = os.environ.get("WICKED_STUDIO_DIST")
    return bool(dist) and (Path(dist) / "index.html").is_file() and sync_playwright is not None


@pytest.mark.skipif(not _browser_ready(), reason="needs playwright + chromium and WICKED_STUDIO_DIST (a studio dist)")
def test_the_scaffolded_editor_passes_and_a_silent_one_fails_the_handshake(tmp_path):
    good, silent = tmp_path / "good", tmp_path / "silent"
    assert scaffold(good).returncode == 0 and scaffold(silent).returncode == 0
    entry = silent / FIXTURE_ENTRY
    entry.write_text(entry.read_text().replace("parent.postMessage(env('plugin.ready'", "void (env('plugin.ready'"))
    assert run("pin.py", str(silent)).returncode == 0
    dist = os.environ["WICKED_STUDIO_DIST"]
    ok = run("conformance.py", "--pack", str(good), "--studio-dist", dist)
    assert ok.returncode == 0, ok.stdout[-2000:]
    bad = run("conformance.py", "--pack", str(silent), "--studio-dist", dist)
    report = json.loads(bad.stdout)
    assert bad.returncode == 1 and report["editors"][0]["cases"]["1-handshake"]["ok"] is False
