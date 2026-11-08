"""The editor-plugin scripts (scripts/editor/): scaffold, pin, install, and conformance's argument
and fail-closed paths. The browser cases run only when Chromium and a studio dist are present
(``WICKED_STUDIO_DIST``); CI without them still pins every refusal.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
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
    digest = base64.urlsafe_b64encode(hashlib.sha256((pack / "wicked-pack.json").read_bytes()).digest()).decode()[:21]
    assert [c["id"] for c in plan["choices"]] == [f"daemon_{digest}", f"daemon-off_{digest}"]
    # core's consent_plan.rs: a choice id is [A-Za-z0-9_-], at most 32 (it rides a token and an env var)
    assert all(len(c["id"]) <= 32 and re.fullmatch(r"[A-Za-z0-9_-]+", c["id"]) for c in plan["choices"])
    assert plan["choices"][0]["default"] is True
    paths = [w["path"] for w in plan["choices"][0]["writes"]]
    assert paths[0] == str(root.resolve() / "acme-json" / "current") or paths[0].endswith("acme-json/current")
    assert any(p.endswith("/api/v1/editors") for p in paths)
    assert all(w["operator_owned"] is False for c in plan["choices"] for w in c["writes"])
    assert not any(w["path"] == "EDITOR-GRANTS" for c in plan["choices"] for w in c["writes"])  # grants nothing
    assert not root.exists()


def test_from_run_finds_the_pack_in_the_worktree_when_wicked_tree_is_a_tree_id(tmp_path):
    # The engine runs the install Tool phase IN the run's worktree and sets WICKED_TREE to that worktree's git tree
    # id (wicked-core#776), never a path. Read as a path, the id found no pack, so every real run's install-plan
    # failed with "found 0 (none)" (j6-cert, run 910e3e0b, 2026-10-26).
    tree = tmp_path / "worktree"
    pack = tree / "changelog-editor"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "home" / ".wicked" / "editors"
    with FakeDaemon() as d:
        done = run("install.py", "--from-run", "--dry-run", "--json", cwd=tree,
                   env={**_install_env(d.origin, root), "WICKED_TREE": "e7f75f7c794795ef010e7d25dc7070b9e98338c3"})
    assert done.returncode == 0, done.stdout + done.stderr
    plan = json.loads(done.stdout.strip().splitlines()[-1])
    assert plan["dry_run"] is True and plan["key"] == "acme-json"
    assert not root.exists()


def test_an_mcp_session_editor_scaffolds_with_its_plain_words_and_passes_pack_check(tmp_path):
    out = tmp_path / "pack"
    done = scaffold(out, "--kinds", "mcp-server", "--permissions", "artifact.read,mcp.session,ui.fullscreen")
    assert done.returncode == 0, done.stderr
    editor = json.loads((out / "wicked-pack.json").read_text())["editors"][0]
    assert editor["kinds"] == ["mcp-server"]
    assert {"id": "mcp.session", "why": "to start and talk to the MCP servers you connect it to"} in editor["permissions"]
    assert [f.render() for f in check_pack(out, garden_root=REPO) if f.level == "error"] == []


def test_the_plan_of_an_mcp_session_editor_lists_its_per_build_grant_on_both_choices(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack, "--kinds", "mcp-server", "--permissions", "artifact.read,mcp.session").returncode == 0
    editor = json.loads((pack / "wicked-pack.json").read_text())["editors"][0]
    with FakeDaemon() as d:
        done = run("install.py", "--dir", str(pack), "--dry-run", "--json", env=_install_env(d.origin, tmp_path / "editors"))
        assert d.requests == []
    assert done.returncode == 0, done.stderr
    plan = json.loads(done.stdout.strip().splitlines()[-1])
    token = f"editor:acme-json@{editor['version']}#{editor['sha256']}/mcp.session"
    for choice in plan["choices"]:
        grants = [w for w in choice["writes"] if w["path"] == "EDITOR-GRANTS"]
        assert len(grants) == 1 and grants[0]["operator_owned"] is False
        assert grants[0]["what"].startswith("This plugin can start and talk to MCP servers") and token in grants[0]["what"]


def _plan_ids(pack: Path, env: dict) -> list[str]:
    done = run("install.py", "--dir", str(pack), "--dry-run", "--json", env=env)
    assert done.returncode == 0, done.stderr
    return [c["id"] for c in json.loads(done.stdout.strip().splitlines()[-1])["choices"]]


@pytest.mark.parametrize("choice, enabled", [(0, True), (1, False)])
def test_an_approved_choice_installs_the_pack_it_planned(tmp_path, choice, enabled):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    with FakeDaemon() as d:
        env = _install_env(d.origin, tmp_path / "editors")
        ids = _plan_ids(pack, env)
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-json"}]})
        done = run("install.py", "--dir", str(pack), "--target", ids[choice], "--json", env=env)
        assert [r["body"]["enabled"] for r in d.requests] == [enabled]
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["target"] == ("daemon" if enabled else "daemon-off")


def test_a_pack_changed_after_the_approved_plan_is_never_installed(tmp_path):
    # Planned without mcp.session, then the permission is added while consent is pending: the approved
    # choice no longer matches, so crew is never asked (and so never writes a grant nobody saw).
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    (root / "acme-json" / "current").mkdir(parents=True)
    (root / "acme-json" / "current" / "marker").write_text("the install before")
    with FakeDaemon() as d:
        env = _install_env(d.origin, root)
        approved = _plan_ids(pack, env)[0]
        manifest = json.loads((pack / "wicked-pack.json").read_text())
        manifest["editors"][0]["permissions"].append({"id": "mcp.session", "why": "x"})
        (pack / "wicked-pack.json").write_text(json.dumps(manifest))
        done = run("install.py", "--dir", str(pack), "--target", approved, "--json", env=env)
        assert d.requests == []
    assert done.returncode == 1 and "changed after the plan" in json.loads(done.stdout)["error"]
    assert (root / "acme-json" / "current" / "marker").read_text() == "the install before"
    assert not (root / "acme-json" / "next").exists()


def test_a_manifest_swapped_between_locate_and_staging_never_lands(tmp_path, monkeypatch):
    # The located manifest picked the install directory; a staged copy that differs from it (even one
    # matching the approved digest) must not be swapped in over another pack's install.
    sys.path.insert(0, str(SCRIPTS))
    import install  # noqa: PLC0415
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    real_stage = install.stage

    def racing_stage(src, manifest, next_dir):
        copied = real_stage(src, manifest, next_dir)
        other = dict(manifest, name="acme-other")
        (next_dir / "wicked-pack.json").write_text(json.dumps(other))
        return copied

    monkeypatch.setattr(install, "stage", racing_stage)
    monkeypatch.delenv("WICKED_RUN_ID", raising=False)
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-json"}]})
        monkeypatch.setenv("WICKED_CREW_URL", d.origin)
        code = install.main(["--dir", str(pack), "--install-root", str(root), "--json"])
        assert d.requests == []
    assert code == 1
    assert not (root / "acme-json" / "current").exists() and not (root / "acme-json" / "next").exists()


@pytest.mark.parametrize("target", ["daemon_", "daemon-0123456789abcdef01234", "daemon_short", "workers",
                                    "daemon-off-on", "daemon_" + "a" * 22])
def test_a_malformed_target_is_refused(tmp_path, target):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    done = run("install.py", "--dir", str(pack), "--target", target, "--json", env=_install_env(closed_origin(), tmp_path / "e"))
    assert done.returncode == 2 and "invalid target" in done.stderr


@pytest.mark.parametrize("reply, expected", [
    ({"granted": ["editor:acme-json@0.1.0#ab/mcp.session"]}, {"granted": ["editor:acme-json@0.1.0#ab/mcp.session"]}),
    ({"grantError": "the EDITOR-GRANTS ledger is not in the policy store"},
     {"grantError": "the EDITOR-GRANTS ledger is not in the policy store"}),
    ({}, {}),  # a crew without the MCP inspector bridge says nothing about grants
])
def test_install_reports_the_grants_crew_wrote_or_why_not(tmp_path, reply, expected):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-json"}], **reply})
        done = run("install.py", "--dir", str(pack), "--json", env=_install_env(d.origin, tmp_path / "editors"))
    assert done.returncode == 0, done.stdout + done.stderr
    out = json.loads(done.stdout)
    assert {k: out[k] for k in ("granted", "grantError") if k in out} == expected


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


def test_an_entry_that_climbs_out_of_the_pack_is_never_staged(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    manifest = json.loads((pack / "wicked-pack.json").read_text())
    # `../pack/...` resolves INSIDE the source pack, but joined under next/ it would land outside it.
    manifest["editors"][0]["entry"] = "../pack/" + FIXTURE_ENTRY
    (pack / "wicked-pack.json").write_text(json.dumps(manifest))
    root = tmp_path / "editors"
    with FakeDaemon() as d:
        done = run("install.py", "--dir", str(pack), "--json", env=_install_env(d.origin, root))
        assert d.requests == []
    assert done.returncode == 2 and "plain relative path" in json.loads(done.stdout)["error"]
    assert not (root / "acme-json").exists() and not (tmp_path / "pack" / "pack").exists()


def test_inside_a_governed_run_only_the_consent_gated_step_installs(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    with FakeDaemon() as d:
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": []})
        refused = run("install.py", "--dir", str(pack), "--json", env={**_install_env(d.origin, root), "WICKED_RUN_ID": "r1"})
        assert d.requests == [] and not (root / "acme-json").exists()
        planned = run("install.py", "--dir", str(pack), "--dry-run", "--json", env={**_install_env(d.origin, root), "WICKED_RUN_ID": "r1"})
        choice = json.loads(planned.stdout.strip().splitlines()[-1])["choices"][0]["id"]
        # core's preset: --target "$WICKED_CONSENT_CHOICE"
        gated = run("install.py", "--dir", str(pack), "--target", choice, "--json",
                    env={**_install_env(d.origin, root), "WICKED_RUN_ID": "r1", "WICKED_CONSENT_CHOICE": choice})
    assert refused.returncode == 2 and "consent-gated install step" in json.loads(refused.stdout)["error"]
    assert planned.returncode == 0 and json.loads(planned.stdout.strip().splitlines()[-1])["dry_run"] is True
    assert gated.returncode == 0, gated.stdout


def test_inside_a_governed_run_a_choice_not_bound_to_its_plan_never_installs(tmp_path):
    # A plan from before the binding (bare "daemon"), approved after a garden upgrade, names no manifest.
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    root = tmp_path / "editors"
    with FakeDaemon() as d:
        done = run("install.py", "--dir", str(pack), "--target", "daemon", "--json",
                   env={**_install_env(d.origin, root), "WICKED_RUN_ID": "r1", "WICKED_CONSENT_CHOICE": "daemon"})
        assert d.requests == []
    assert done.returncode == 2 and "not bound to its plan" in json.loads(done.stdout)["error"]
    assert not (root / "acme-json").exists()


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


# ── conformance: ENGINE MODE (the engine's host step, DES-EDITOR-CONFORMANCE-HOST / F18) ─────────

def _conformance_module():
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location("wg_editor_conformance", SCRIPTS / "conformance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _engine_env(tree: Path, tmp_path: Path, **over: str) -> dict:
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><title>studio</title>")
    env = {"WICKED_EDITOR_CONFORMANCE_JAIL": "sandbox-exec", "WICKED_EDITOR_PACK_ROOT": str(tree),
           "WG_EDITOR_CONFORMANCE_PORT": "18799", "WG_EDITOR_CONFORMANCE_STUDIO_DIST": str(dist),
           "WG_EDITOR_CONFORMANCE_OUT": str(tmp_path / "out" / "report.json")}
    (tmp_path / "out").mkdir(exist_ok=True)
    env.update(over)
    return env


def test_engine_mode_refuses_to_run_unjailed_and_writes_nothing(tmp_path):
    tree = tmp_path / "tree"
    assert scaffold(tree / "acme-json").returncode == 0
    env = _engine_env(tree, tmp_path, WICKED_EDITOR_CONFORMANCE_JAIL="")
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads(done.stdout)
    assert done.returncode == 2 and report["cause"] == "no_jail" and report["ok"] is False
    assert not (tmp_path / "out" / "report.json").exists()


def test_engine_mode_takes_no_pack_or_host_from_its_arguments(tmp_path):
    tree = tmp_path / "tree"
    assert scaffold(tree / "acme-json").returncode == 0
    done = run("conformance.py", "--engine", "--pack", str(tree / "acme-json"), env=_engine_env(tree, tmp_path))
    assert done.returncode == 2 and "every input from the environment" in done.stderr


def test_engine_mode_finds_the_one_pack_and_refuses_two(tmp_path):
    mod = _conformance_module()
    tree = tmp_path / "tree"
    assert scaffold(tree / "plugins" / "acme-json").returncode == 0
    (tree / "node_modules" / "x").mkdir(parents=True)
    shutil.copytree(tree / "plugins" / "acme-json", tree / "node_modules" / "x" / "acme-json")  # never searched
    got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
    assert refusal == {} and got["pack"] == tree / "plugins" / "acme-json" and got["port"] == 18799
    shutil.copytree(tree / "plugins" / "acme-json", tree / "second")
    got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
    assert got is None and refusal["cause"] == "pack_invalid" and "found 2" in refusal["error"]


@pytest.mark.parametrize("over, cause", [
    ({"WG_EDITOR_CONFORMANCE_PORT": "80"}, "bad_arguments"),
    ({"WG_EDITOR_CONFORMANCE_PORT": "７７２１"}, "bad_arguments"),
    ({"WG_EDITOR_CONFORMANCE_OUT": "report.json"}, "bad_arguments"),
    ({"WG_EDITOR_CONFORMANCE_STUDIO_DIST": "/nonexistent-studio-dist"}, "no_studio"),
    ({"WICKED_EDITOR_PACK_ROOT": "relative/tree"}, "bad_arguments"),
])
def test_engine_mode_refuses_inputs_it_cannot_vouch_for(tmp_path, over, cause):
    mod = _conformance_module()
    tree = tmp_path / "tree"
    assert scaffold(tree / "acme-json").returncode == 0
    got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path, **over))
    assert got is None and refusal["cause"] == cause, refusal


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
@pytest.mark.parametrize("what", ["entry", "manifest", "dir"])
def test_engine_mode_refuses_a_linked_pack_before_any_browser(tmp_path, what):
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    secret = tmp_path / "secret.html"
    if what == "entry":
        secret.write_text((pack / FIXTURE_ENTRY).read_text())
        (pack / FIXTURE_ENTRY).unlink()
        (pack / FIXTURE_ENTRY).symlink_to(secret)
    elif what == "manifest":
        real = tmp_path / "manifest.json"
        real.write_text((pack / "wicked-pack.json").read_text())
        (pack / "wicked-pack.json").unlink()
        (pack / "wicked-pack.json").symlink_to(real)
    else:
        real = tmp_path / "editors-real"
        shutil.move(str(pack / "editors"), real)
        (pack / "editors").symlink_to(real, target_is_directory=True)
    done = run("conformance.py", "--engine", "--json", env=_engine_env(tree, tmp_path))
    report = json.loads(done.stdout)
    assert done.returncode == 2 and report["cause"] == "pack_invalid" and "link" in report["error"], report
    assert json.loads((tmp_path / "out" / "report.json").read_text())["cause"] == "pack_invalid"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks")
def test_engine_mode_refuses_a_link_anywhere_in_the_pack_and_a_linked_manifest_before_reading_it(tmp_path):
    mod = _conformance_module()
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    (pack / "skills").mkdir()
    (pack / "skills" / "SKILL.md").symlink_to(tmp_path / "host-secret.md")  # case 0 would read it
    done = run("conformance.py", "--engine", "--json", env=_engine_env(tree, tmp_path))
    report = json.loads(done.stdout)
    assert report["cause"] == "pack_invalid" and "skills/SKILL.md is a link" in report["error"], report
    # A linked manifest is refused at discovery, before it is opened (its target here cannot be read at all).
    tree2 = tmp_path / "tree2"
    (tree2 / "p").mkdir(parents=True)
    (tree2 / "p" / "wicked-pack.json").symlink_to(tmp_path / "missing-target.json")
    got, refusal = mod.engine_inputs(_engine_env(tree2, tmp_path))
    assert got is None and refusal["cause"] == "pack_invalid" and "is a link" in refusal["error"], refusal


def test_engine_mode_calls_an_entry_no_filesystem_accepts_an_invalid_pack(tmp_path):
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    m = json.loads((pack / "wicked-pack.json").read_text())
    m["editors"][0]["entry"] = "editors/acme-json/in\u0000dex.html"
    (pack / "wicked-pack.json").write_text(json.dumps(m))
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_REEXEC="1")
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads(done.stdout)
    assert done.returncode == 2 and report["cause"] == "pack_invalid", report


def test_engine_discovery_never_lets_an_unreadable_manifest_drop_out_and_install_keeps_its_rule(tmp_path):
    mod = _conformance_module()
    sys.path.insert(0, str(SCRIPTS))
    import _pack  # noqa: PLC0415
    tree = tmp_path / "tree"
    assert scaffold(tree / "good").returncode == 0
    assert scaffold(tree / "big").returncode == 0
    big = json.loads((tree / "big" / "wicked-pack.json").read_text())
    big["padding"] = "x" * (_pack.MANIFEST_CAP + 1)
    (tree / "big" / "wicked-pack.json").write_text(json.dumps(big))
    got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
    assert got is None and refusal["cause"] == "pack_invalid" and "over" in refusal["error"], refusal
    # install.py --from-run's discovery is unchanged: no cap, both packs found (so it refuses two).
    assert len(_pack.find_editor_packs(tree)) == 2
    (tree / "deep").mkdir()
    (tree / "deep" / "wicked-pack.json").write_text("[" * 100000 + "]" * 100000)
    (tree / "big" / "wicked-pack.json").unlink()
    got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
    assert got is None and refusal["cause"] == "pack_invalid", refusal
    assert _pack.find_editor_packs(tree) == [tree / "good"]  # install skips it, as before


def test_a_pack_the_checker_cannot_decode_fails_case_0_and_a_stop_is_classified(tmp_path):
    mod = _conformance_module()
    pack = tmp_path / "acme-json"
    assert scaffold(pack).returncode == 0
    (pack / "skills" / "x").mkdir(parents=True)
    (pack / "skills" / "x" / "SKILL.md").write_bytes(b"---\nname: x\n---\n\xff\xfe bad utf-8")
    m0 = mod.manifest_case(pack)
    assert m0["ok"] is False and "host_failure" not in m0, m0  # a verdict on the pack, not the host
    # By the exception's TYPE, never its words: a Playwright timeout is the editor's ("stopped", charged to no
    # case that did not run); the browser going away, or anything else, is the harness's.
    pw_timeout = type("TimeoutError", (Exception,), {"__module__": "playwright._impl._errors"})
    er = {"cases": {"0-manifest": {"ok": True}, "1-handshake": {"ok": True}, "2-sizes": {"ok": True}}}
    mod.record_stop(er, pw_timeout("Timeout 5000ms exceeded waiting for body"), mod.CASES_V1)
    assert er["cases"]["stopped"]["ok"] is False and er["cases"]["stopped"]["after"] == "2-sizes"
    assert "3-no-network" not in er["cases"] and "host_failure" not in er
    closed = type("TargetClosedError", (Exception,), {"__module__": "playwright._impl._errors"})
    for exc in (closed("Target page, context or browser has been closed"),
                AttributeError("window.__wickedEditor.setSize is not a function"),
                Exception("has been closed")):  # an editor's error text never decides
        er2 = {"cases": {}}
        mod.record_stop(er2, exc, mod.CASES_V1)
        assert "host_failure" in er2 and er2["cases"] == {}, exc
    # A field of the wrong type the checker trips on is the pack's (case 0), not the harness's.
    m = json.loads((pack / "wicked-pack.json").read_text())
    m["domains"] = [{"name": 7}]
    (pack / "wicked-pack.json").write_text(json.dumps(m))
    m0 = mod.manifest_case(pack)
    assert m0["ok"] is False and "host_failure" not in m0, m0


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permissions")
def test_engine_discovery_refuses_a_subtree_it_cannot_read_and_install_reads_as_before(tmp_path):
    mod = _conformance_module()
    sys.path.insert(0, str(SCRIPTS))
    import _pack  # noqa: PLC0415
    tree = tmp_path / "tree"
    assert scaffold(tree / "good").returncode == 0
    assert scaffold(tree / "hidden" / "second").returncode == 0
    (tree / "hidden").chmod(0o000)
    try:
        got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
        assert got is None and refusal["cause"] == "pack_invalid" and "cannot be read" in refusal["error"], refusal
        assert _pack.find_editor_packs(tree) == [tree / "good"]  # install's walk is unchanged
    finally:
        (tree / "hidden").chmod(0o755)
    # A non-finite number is refused only by the engine's reader; install reads the manifest as before.
    m = (tree / "good" / "wicked-pack.json").read_text()
    (tree / "good" / "wicked-pack.json").write_text(m.replace("{", '{"x-provenance": 1e999, ', 1))
    assert _pack.read_manifest(tree / "good")["x-provenance"] == float("inf")
    with pytest.raises(_pack.PackError):
        _pack.read_manifest(tree / "good", finite=True)


def test_an_engine_report_is_bounded_whatever_the_pack_puts_in_it(tmp_path):
    mod = _conformance_module()
    nested: object = "x"
    for _ in range(200):
        nested = {"n": nested}
    big = {"ok": False, "error": "x" * 1_000_000, "pack": "/p", "editors": [
        {"id": nested, "version": ["v"] * 10_000, "sha256": "ab", "protocol": [1] * 60 + [2], "ok": False,
         "cases": {"14-card": {"ok": False, "error": "e" * 50_000, "reply": {f"k{i}": "v" * 1000 for i in range(5000)}},
                   "0-manifest": {"ok": True}}}]}
    small = mod.engine_report(big)
    text = json.dumps(small)
    assert len(text) < 20_000, len(text)
    # Every verdict-bearing field kept whole: the protocol-2 requirement past item 50 survives, each case's ok too.
    e = small["editors"][0]
    assert e["protocol"] == [1, 2] and e["cases"]["14-card"]["ok"] is False and e["cases"]["0-manifest"]["ok"] is True
    assert "reply" not in e["cases"]["14-card"] and isinstance(e["id"], str)
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    m = json.loads((pack / "wicked-pack.json").read_text())
    m["editors"][0]["entry"] = "editors/" + "a" * 600_000 + ".html"
    (pack / "wicked-pack.json").write_text(json.dumps(m))
    done = run("conformance.py", "--engine", "--json", env=_engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_REEXEC="1"))
    out = (tmp_path / "out" / "report.json").read_text()
    assert len(out) < 20_000 and json.loads(out)["cause"] == "pack_invalid", out[:300]
    # Discovery refusals go through the same writer: many candidate packs name a few, bounded.
    many = tmp_path / "many"
    for i in range(8):
        assert scaffold(many / (f"p{i}-" + "d" * 200)).returncode == 0
    done = run("conformance.py", "--engine", "--json", env=_engine_env(many, tmp_path))
    out = (tmp_path / "out" / "report.json").read_text()
    assert done.returncode == 2 and json.loads(out)["cause"] == "pack_invalid" and "found 8" in out and len(out) < 5_000


@pytest.mark.parametrize("field, value", [("title", "t" * 70_000), ("protocol", [1, 2, 10 ** 400]),
                                          ("permissions", [{"id": "artifact.read", "why": "to read it"}] * 40),
                                          ("permissions", 1), ("permissions", True)])
def test_a_pack_value_no_host_page_or_reader_can_carry_is_the_pack_s(tmp_path, field, value):
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    m = json.loads((pack / "wicked-pack.json").read_text())
    m["editors"][0][field] = value
    (pack / "wicked-pack.json").write_text(json.dumps(m))
    done = run("conformance.py", "--engine", "--json", env=_engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_REEXEC="1"))
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert done.returncode == 2 and report["cause"] == "pack_invalid", report


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permissions")
def test_a_readable_but_unsearchable_directory_is_the_pack_s(tmp_path):
    mod = _conformance_module()
    tree = tmp_path / "tree"
    assert scaffold(tree / "good").returncode == 0
    assert scaffold(tree / "odd" / "second").returncode == 0
    (tree / "odd" / "second").chmod(0o400)
    try:
        got, refusal = mod.engine_inputs(_engine_env(tree, tmp_path))
    finally:
        (tree / "odd" / "second").chmod(0o755)
    assert got is None and refusal["cause"] == "pack_invalid", refusal


def test_the_host_running_out_of_resources_in_pack_check_is_the_harness_s(tmp_path, monkeypatch):
    import errno  # noqa: PLC0415
    mod = _conformance_module()
    import pack.check  # noqa: PLC0415

    def emfile(*_a, **_k):
        raise OSError(errno.EMFILE, "Too many open files")
    monkeypatch.setattr(pack.check, "check_pack", emfile)
    m0 = mod.manifest_case(tmp_path)
    assert m0["ok"] is False and "host_failure" in m0, m0


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permissions")
def test_engine_mode_calls_an_unreadable_entry_or_a_non_finite_number_an_invalid_pack(tmp_path):
    tree = tmp_path / "tree"
    pack = tree / "acme-json"
    assert scaffold(pack).returncode == 0
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_REEXEC="1")
    (pack / FIXTURE_ENTRY).chmod(0o000)
    try:
        done = run("conformance.py", "--engine", "--json", env=env)
    finally:
        (pack / FIXTURE_ENTRY).chmod(0o644)
    report = json.loads(done.stdout)
    assert done.returncode == 2 and report["cause"] == "pack_invalid", report
    m = (pack / "wicked-pack.json").read_text()
    (pack / "wicked-pack.json").write_text(m.replace('"protocol": [', '"protocol": [1e999, ', 1))
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads(done.stdout, parse_constant=lambda c: pytest.fail(f"{c} in the report"))
    out = json.loads((tmp_path / "out" / "report.json").read_text(), parse_constant=lambda c: pytest.fail(c))
    assert report["cause"] == out["cause"] == "pack_invalid", report


@pytest.mark.skipif(sys.platform == "win32", reason="a shell-script interpreter")
def test_engine_mode_reexecutes_under_the_engines_interpreter_first(tmp_path):
    tree = tmp_path / "tree"
    assert scaffold(tree / "acme-json").returncode == 0
    seen = tmp_path / "seen.txt"
    fake = tmp_path / "venv-python"
    # Answers the probe ("-I -c import playwright…") yes; any other call records its argv and env, writes a report.
    fake.write_text("#!/bin/sh\n"
                    'if [ "$2" = "-c" ]; then exit 0; fi\n'
                    f'printf "%s\\n" "$@" > {seen}\n'
                    f'printf "REEXEC=%s\\n" "$WG_EDITOR_CONFORMANCE_REEXEC" >> {seen}\n'
                    'echo \'{"ok": true, "editors": []}\'\n'
                    "exit 7\n")
    fake.chmod(0o755)
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_PYTHON=str(fake))
    done = run("conformance.py", "--engine", "--json", env=env)
    assert done.returncode == 7, done.stdout + done.stderr  # the child's status is the run's
    lines = seen.read_text().splitlines()
    assert lines[0] == "-I" and lines[1].endswith("scripts/editor/conformance.py"), lines
    assert lines[2:4] == ["--engine", "--json"] and "REEXEC=1" in lines, lines
    # No interpreter named: a no_browser refusal, never PATH's playwright.
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_PYTHON="")  # unset even when the parent has one
    done = run("conformance.py", "--engine", "--json", env=env)
    assert done.returncode == 3 and json.loads(done.stdout)["cause"] == "no_browser"


def _engine_browser_ready() -> bool:
    py, dist = os.environ.get("WG_EDITOR_CONFORMANCE_PYTHON", ""), os.environ.get("WICKED_STUDIO_DIST", "")
    return bool(py) and os.path.isfile(py) and bool(dist) and (Path(dist) / "index.html").is_file()


@pytest.mark.skipif(not _engine_browser_ready(), reason="needs WG_EDITOR_CONFORMANCE_PYTHON (playwright + chromium) "
                    "and WICKED_STUDIO_DIST (a protocol-2 studio dist)")
def test_engine_mode_runs_every_case_and_writes_the_report_the_engine_reads(tmp_path):
    import socket  # noqa: PLC0415
    tree = tmp_path / "tree"
    assert scaffold(tree / "acme-json").returncode == 0
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_PORT=str(port),
                      WG_EDITOR_CONFORMANCE_STUDIO_DIST=os.environ["WICKED_STUDIO_DIST"])
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert done.returncode == 0 and report["ok"] is True and "cause" not in report, done.stdout[-2000:]
    editor = report["editors"][0]
    assert editor["protocol"] == [1, 2] and editor["negotiated"] == 2
    required = ["0-manifest", "1-handshake", "2-sizes", "3-no-network", "4-permissions", "5-typing", "6-forwarding",
                "7-edit", "8-strict-input", "9-liveness", "10-keyboard", "11-theme", "12-hash-pinned", "18-shows",
                "13-surfaces", "14-card", "15-options", "16-full"]  # crew's requiredCases for a protocol-2 editor
    assert {c: editor["cases"].get(c, {}).get("ok") for c in required} == {c: True for c in required}
    # A silent editor: a verdict on the pack, never a host refusal.
    entry = tree / "acme-json" / FIXTURE_ENTRY
    entry.write_text(entry.read_text().replace("parent.postMessage(env('plugin.ready'", "void (env('plugin.ready'"))
    assert run("pin.py", str(tree / "acme-json")).returncode == 0
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert done.returncode == 1 and report["cause"] == "case_failed", report.get("error")
    # A studio dist that never renders the host page: the host's failure, a refusal, never a send-back.
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_PORT=str(port), WG_EDITOR_CONFORMANCE_TIMEOUT="5")
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["ok"] is False and report["cause"] == "host_page_failed", report.get("error")
    # An editor that handshakes but keeps its body hidden: the editor's failure, never a crashed run.
    entry.write_text(entry.read_text()
                     .replace("void (env('plugin.ready'", "parent.postMessage(env('plugin.ready'")
                     .replace("<head>", "<head><style>body{display:none!important}</style>", 1))
    assert run("pin.py", str(tree / "acme-json")).returncode == 0
    env = _engine_env(tree, tmp_path, WG_EDITOR_CONFORMANCE_PORT=str(port),
                      WG_EDITOR_CONFORMANCE_STUDIO_DIST=os.environ["WICKED_STUDIO_DIST"])
    done = run("conformance.py", "--engine", "--json", env=env)
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["cause"] == "case_failed", report.get("error") or report["editors"][0]["cases"]


def test_engine_mode_never_probes_path_for_an_interpreter(tmp_path, monkeypatch):
    mod = _conformance_module()
    fake = tmp_path / "bin"
    fake.mkdir()
    py = fake / "python3"
    py.write_text("#!/bin/sh\nexit 0\n")  # "imports playwright" for anyone who asks
    py.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake))
    monkeypatch.delenv("WG_EDITOR_CONFORMANCE_PYTHON", raising=False)
    assert mod.python_with_playwright(engine=True) is None
    if sys.platform != "win32":
        assert mod.python_with_playwright(engine=False) == str(py)
        monkeypatch.setenv("WG_EDITOR_CONFORMANCE_PYTHON", str(py))
        assert mod.python_with_playwright(engine=True) == str(py)


def test_the_conformance_origin_listens_on_the_port_it_is_handed(tmp_path):
    import socket  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    mod = _conformance_module()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    (tmp_path / "index.html").write_text("<!doctype html><title>studio</title>")
    server = mod.make_server({}, None, tmp_path, 5.0, port)
    try:
        assert server.server_address[1] == port
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/editors/conformance", timeout=5) as r:  # noqa: S310
            assert r.status == 200
        with pytest.raises(OSError):
            mod.make_server({}, None, tmp_path, 5.0, port)  # taken: the engine's cause is port_unavailable
    finally:
        server.shutdown()
        server.server_close()


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


# ── G9b: the behaviour an editor owes the artifact it opens (cases 7 and 18) ──────────────────────

# wicked-crew `editors/pack-install.ts` CONFORMANCE_CASES and wicked-core `src/editor_conformance.rs` CASES require these
# same ids of every editor: a report that omits one never installs and never passes the engine's step.
EVERY_EDITOR = ["0-manifest", "1-handshake", "2-sizes", "3-no-network", "4-permissions", "5-typing", "6-forwarding",
                "7-edit", "8-strict-input", "9-liveness", "10-keyboard", "11-theme", "12-hash-pinned", "18-shows"]


def test_every_editor_runs_the_edit_and_shows_cases():
    mod = _conformance_module()
    assert list(mod.CASES_V1) == EVERY_EDITOR
    assert list(mod.CASES_V2) == ["13-surfaces", "14-card", "15-options", "16-full"]
    assert mod.expected_cases({"protocol": [1, 2]}) == 18 and mod.expected_cases({"protocol": [1]}) == 15
    assert mod.BEHAVIOUR_CASES == ("7-edit", "18-shows") and set(mod.BEHAVIOUR_CASES) <= set(mod.CASES_V1)


def test_shown_runs_matches_the_handed_text_whatever_the_whitespace():
    mod = _conformance_module()
    runs = ["Book a study room in under a minute", "One fixed fee", "Support is included"]
    assert mod.shown_runs("1 Book a study\n room in   under a minute\n2 nothing", runs) == [runs[0]]
    assert mod.shown_runs("Fill in the form to build an entry.", runs) == []
    assert mod.shown_runs("", runs) == [] and mod.shown_runs("One fixed fee", [None, "", "One fixed fee"]) == ["One fixed fee"]


def test_a_refused_read_never_counts_toward_the_first_read_deadline():
    mod = _conformance_module()
    # Handshake at 0: a read refused at once (1 ms), then the real read at 3.1 s: nothing answered within 3 s.
    r = {"hs": 0.0, "at": [1.0, 3100.0], "refused": [1.2]}
    assert mod.answered_reads_by(r, 3000.0) == 0 and mod.answered_reads_by(r, 3200.0) == 1
    assert mod.answered_reads_by({"hs": 0.0, "at": [20.0], "refused": []}, 3000.0) == 1


def test_the_sample_an_editor_is_shown_on_is_its_kind():
    mod = _conformance_module()
    assert mod.sample_kind({"kinds": ["page", "deck"]}) == "page"
    assert mod.sample_kind({"kinds": ["deck"]}) == "deck"
    assert mod.sample_kind({"kinds": ["demo-video"]}) is None and mod.sample_kind({}) is None


# An editor that may write: one control marked data-wicked-save writes a text edit of the first part it shows.
SAVE_BUTTON = '<button type="button" id="save" data-wicked-save>Save</button>'
SAVE_SCRIPT = """
  document.getElementById('save').addEventListener('click', async () => {
    const p = parts[0]; if (!p) return;
    const before = p.lastChild.textContent;
    await req('version.write', { base: head, ops: [{ op: 'text', anchor: p.dataset.part, value: before + ' (edited)', before }], summary: 'An edit' });
  });
  async function load() {"""


def _edit_entry(pack: Path, *, mark: bool = True, reread: bool = True, button: bool = True) -> None:
    entry = pack / FIXTURE_ENTRY
    text = entry.read_text()
    if button:
        btn = SAVE_BUTTON if mark else SAVE_BUTTON.replace(" data-wicked-save", "")
        text = text.replace('<button type="button" id="full">', btn + ' <button type="button" id="full">', 1)
        text = text.replace("\n  async function load() {", SAVE_SCRIPT, 1)
    if not reread:
        text = text.replace("case 'artifact.changed': if (p.by !== 'this-editor') load(); break;", "case 'artifact.changed': break;", 1)
    entry.write_text(text)
    assert run("pin.py", str(pack)).returncode == 0


def _cases(pack: Path) -> dict:
    done = run("conformance.py", "--pack", str(pack), "--studio-dist", os.environ["WICKED_STUDIO_DIST"])
    return json.loads(done.stdout)["editors"][0]["cases"]


@pytest.mark.skipif(not _browser_ready(), reason="needs playwright + chromium and WICKED_STUDIO_DIST (a studio dist)")
def test_case_18_an_editor_must_read_show_and_follow_what_it_is_handed(tmp_path):
    good, blind, stale = tmp_path / "good", tmp_path / "blind", tmp_path / "stale"
    assert scaffold(good).returncode == 0
    cases = _cases(good)
    assert cases["18-shows"]["ok"] is True and cases["18-shows"]["reread"] is True, cases["18-shows"]
    assert cases["7-edit"] == {"ok": True, "viewer": True, "note": cases["7-edit"]["note"]}
    # The J6 Changelog entry pack's shape: it never asks to read the page (G9).
    assert scaffold(blind, "--permissions", "selection.chip,ui.fullscreen").returncode == 0
    cases = _cases(blind)
    assert cases["18-shows"]["ok"] is False and "artifact.read" in cases["18-shows"]["error"]
    assert cases["9-liveness"]["ok"] is True  # recorded without stopping the run: every other case still reports
    # It reads once and never again: a new version never reaches what it shows.
    assert scaffold(stale).returncode == 0
    _edit_entry(stale, button=False, reread=False)
    cases = _cases(stale)
    assert cases["18-shows"]["ok"] is False and cases["18-shows"]["reread"] is False, cases["18-shows"]
    # A deck editor whose change handler asks for a version that does not exist: the refused read is no re-read
    # (on the deck sample the re-read is all case 18 can judge after a change).
    deck = tmp_path / "deck"
    assert run("scaffold.py", "--vendor", "acme", "--id", "acme-json", "--title", "Deck viewer", "--kinds", "deck",
               "--out", str(deck)).returncode == 0
    entry = deck / FIXTURE_ENTRY
    entry.write_text(entry.read_text().replace("case 'artifact.changed': if (p.by !== 'this-editor') load(); break;",
                                               "case 'artifact.changed': req('artifact.read', { version: 999 }); break;", 1))
    assert run("pin.py", str(deck)).returncode == 0
    cases = _cases(deck)
    assert cases["18-shows"]["ok"] is False and cases["18-shows"]["reread"] is False, cases["18-shows"]


@pytest.mark.skipif(not _browser_ready(), reason="needs playwright + chromium and WICKED_STUDIO_DIST (a studio dist)")
def test_case_7_an_editor_that_may_write_saves_through_its_own_marked_control(tmp_path):
    perms = ("--permissions", "artifact.read,artifact.write,ui.fullscreen")
    writer, unmarked, silent = tmp_path / "writer", tmp_path / "unmarked", tmp_path / "silent"
    for pack in (writer, unmarked, silent):
        assert scaffold(pack, *perms).returncode == 0
    _edit_entry(writer)
    cases = _cases(writer)
    assert cases["7-edit"]["ok"] is True and cases["7-edit"]["writes"] == 1 and cases["7-edit"]["head_moved"] == 1, cases["7-edit"]
    _edit_entry(unmarked, mark=False)
    cases = _cases(unmarked)
    assert cases["7-edit"]["ok"] is False and "data-wicked-save" in cases["7-edit"]["error"], cases["7-edit"]
    # A validating form: Save stays disabled until a valid email and a note are in (a 300 ms debounce); what was
    # typed reaches the version.
    form = tmp_path / "form"
    assert scaffold(form, *perms).returncode == 0
    entry = form / FIXTURE_ENTRY
    entry.write_text(entry.read_text()
        .replace('<button type="button" id="full">', '<input type="email" id="who" required aria-label="Who"> '
                 '<input type="number" id="n" required max="5" step="2" aria-label="Count"> '
                 '<input type="number" id="m" required value="1" max="5" step="2" aria-label="Odd"> '
                 '<input type="number" id="d" required min="0.3" max="0.9" step="0.2" aria-label="Share"> '
                 '<input type="text" id="note" aria-label="Note"> ' + SAVE_BUTTON.replace(">Save", " disabled>Save")
                 + ' <button type="button" id="full">', 1)
        .replace("\n  async function load() {", """
  let wait = null;
  document.getElementById('m').value = '';  // emptied at start: its value attribute (1) stays the step base
  const valid = () => document.getElementById('who').checkValidity() && document.getElementById('who').value
    && ['n', 'm', 'd'].every((id) => document.getElementById(id).value && document.getElementById(id).checkValidity())
    && document.getElementById('note').value;
  for (const id of ['who', 'n', 'm', 'd', 'note']) document.getElementById(id).addEventListener('input', () => {
    clearTimeout(wait); wait = setTimeout(() => { document.getElementById('save').disabled = !valid(); }, 300); });
  document.getElementById('save').addEventListener('click', async () => {
    const p = parts[0]; if (!p || !valid()) return;
    const before = p.lastChild.textContent;
    await req('version.write', { base: head, ops: [{ op: 'text', anchor: p.dataset.part, value: before + ' ' + document.getElementById('note').value, before }], summary: 'A note' });
  });
  async function load() {""", 1))
    assert run("pin.py", str(form)).returncode == 0
    cases = _cases(form)
    assert cases["7-edit"]["ok"] is True and cases["7-edit"]["filled"] == 5 and cases["7-edit"]["typed_in_version"] is True, cases["7-edit"]
    # A field already at its maxlength, Save waiting for a change: the field is changed within its limit.
    full = tmp_path / "full"
    assert scaffold(full, *perms).returncode == 0
    entry = full / FIXTURE_ENTRY
    entry.write_text(entry.read_text()
        .replace('<button type="button" id="full">', '<input type="text" id="t" maxlength="5" value="hello" aria-label="T"> '
                 + SAVE_BUTTON.replace(">Save", " disabled>Save") + ' <button type="button" id="full">', 1)
        .replace("\n  async function load() {", """
  document.getElementById('t').addEventListener('input', () => { document.getElementById('save').disabled = document.getElementById('t').value === 'hello'; });
  document.getElementById('save').addEventListener('click', async () => {
    const p = parts[0]; if (!p) return;
    const before = p.lastChild.textContent;
    await req('version.write', { base: head, ops: [{ op: 'text', anchor: p.dataset.part, value: before + ' ' + document.getElementById('t').value, before }], summary: 'T' });
  });
  async function load() {""", 1))
    assert run("pin.py", str(full)).returncode == 0
    cases = _cases(full)
    assert cases["7-edit"]["ok"] is True and cases["7-edit"]["filled"] == 0, cases["7-edit"]
    # A marked control that writes nothing: no version lands.
    entry = silent / FIXTURE_ENTRY
    entry.write_text(entry.read_text().replace('<button type="button" id="full">', SAVE_BUTTON + ' <button type="button" id="full">', 1))
    assert run("pin.py", str(silent)).returncode == 0
    cases = _cases(silent)
    assert cases["7-edit"]["ok"] is False and cases["7-edit"]["writes"] == 0, cases["7-edit"]
    # A failed behaviour case never keeps the protocol-2 cases from reporting (the scaffold speaks protocol 2).
    assert {c: cases[c]["ok"] for c in ("13-surfaces", "14-card", "15-options", "16-full")} == dict.fromkeys(
        ("13-surfaces", "14-card", "15-options", "16-full"), True), cases


# ── CS7: third-party run plugins (protocol 3, plugins[], r0-r5) ────────────────────────────

def scaffold_run_plugin(out: Path, *extra: str) -> subprocess.CompletedProcess:
    return run("scaffold.py", "--kind", "run-plugin", "--vendor", "acme", "--id", "acme-spend",
               "--title", "Phase spend", "--out", str(out), *extra)


def test_scaffold_run_plugin_writes_a_spec2_pack_that_passes_pack_check_and_pins(tmp_path):
    out = tmp_path / "run-pack"
    done = scaffold_run_plugin(out)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    manifest = json.loads((out / "wicked-pack.json").read_text())
    plugin = manifest["plugins"][0]
    assert manifest["spec"] == 2 and "editors" not in manifest and plugin["id"] == "acme-spend"
    assert plugin["protocol"] == [3] and plugin["inline"] == "run-thread"
    assert plugin["entry"] == "plugins/acme-spend/index.html"
    assert plugin["samples"] == "samples/events.ndjson" and (out / "samples" / "events.ndjson").is_file()
    assert len(plugin["observe"]) == 2 and all(o["topic"].startswith("wicked.run.") and o["why"] for o in plugin["observe"])
    assert plugin["panels"][0]["slot"] == "run.details"
    html = (out / plugin["entry"]).read_text()
    assert "__PLUGIN" not in html and "const PLUGIN = 'acme-spend', VERSION = '0.1.0'" in html
    assert report["plugin"]["sha256"] == plugin["sha256"]
    assert [f.render() for f in check_pack(out, garden_root=REPO) if f.level == "error"] == []

    # Editing the plugin entry triggers PK084 until pin.py re-pins it.
    entry = out / plugin["entry"]
    entry.write_text(html.replace("Waiting for run events…", "Waiting for phase events…"))
    assert any(f.code == "PK084" for f in check_pack(out, garden_root=REPO))
    pinned = run("pin.py", str(out))
    assert pinned.returncode == 0 and json.loads(pinned.stdout)["plugins"][0]["changed"] is True
    assert [f.render() for f in check_pack(out, garden_root=REPO) if f.level == "error"] == []


def test_install_plan_lists_plugin_observe_topics_and_installs_plugin_only_pack(tmp_path):
    pack = tmp_path / "run-pack"
    assert scaffold_run_plugin(
        pack, "--observe", "wicked.run.phase.*,wicked.run.usage.reported"
    ).returncode == 0
    root = tmp_path / "editors"
    with FakeDaemon() as d:
        planned = run("install.py", "--dir", str(pack), "--plan", "--json", env=_install_env(d.origin, root))
        assert d.requests == []
        assert planned.returncode == 0, planned.stderr
        plan = json.loads(planned.stdout.strip().splitlines()[-1])
        assert plan["dry_run"] is True and plan["key"] == "acme-spend"
        assert len(plan["plugins"]) == 1
        p_plan = plan["plugins"][0]
        assert p_plan["id"] == "acme-spend" and p_plan["version"] == "0.1.0"
        assert [o["topic"] for o in p_plan["observe"]] == ["wicked.run.phase.*", "wicked.run.usage.reported"]
        assert all(o["why"] for o in p_plan["observe"])
        grants = [w for w in plan["choices"][0]["writes"] if w["path"] == "EDITOR-GRANTS"]
        assert len(grants) == 2 and all("observe:" in g["what"] for g in grants)

        # Install the plugin-only pack through the same path.
        choice = plan["choices"][0]["id"]
        d.routes[("POST", "/api/v1/editors")] = (200, {"installed": True, "editors": [{"id": "acme-spend"}]})
        installed = run("install.py", "--dir", str(pack), "--target", choice, "--json", env=_install_env(d.origin, root))
    assert installed.returncode == 0, installed.stdout + installed.stderr
    current = root / "acme-spend" / "current"
    assert (current / "plugins" / "acme-spend" / "index.html").is_file()
    assert (current / "samples" / "events.ndjson").is_file()


def test_run_plugin_verdict_functions_r1_to_r5():
    mod = _conformance_module()
    assert list(mod.RUN_PLUGIN_CASES) == [
        "r0-manifest", "r1-handshake", "r2-no-network", "r3-topics", "r4-replay", "r5-hash-pinned"
    ]

    # r1-handshake: requires exactly 1 handshake, 0 ignored window messages, protocol 3.
    assert mod.r1_handshake_verdict([{"kind": "handshake"}], 3)["ok"] is True
    assert mod.r1_handshake_verdict([], 3)["ok"] is False
    assert mod.r1_handshake_verdict([{"kind": "handshake"}, {"kind": "handshake"}], 3)["ok"] is False
    assert mod.r1_handshake_verdict([{"kind": "handshake"}], 2)["ok"] is False

    # r2-no-network: 0 external frame requests.
    assert mod.r2_no_network_verdict([])["ok"] is True
    assert mod.r2_no_network_verdict(["https://evil.example/exfil"])["ok"] is False

    # r3-topics: reject ungranted rows and an empty delivery. Integration below exercises the actual host guard.
    granted = ["wicked.run.phase.*"]
    withheld = ["wicked.run.unit.*"]
    clean_batches = [
        {"mount": 1, "replay": True, "rows": [{"id": "e1", "topic": "wicked.run.phase.started"}]},
        {"mount": 1, "replay": False, "rows": [{"id": "e2", "topic": "wicked.run.phase.completed"}]},
    ]
    assert mod.r3_topics_verdict(clean_batches, granted, withheld)["ok"] is True
    leaked_batches = [
        {"mount": 1, "replay": True, "rows": [{"id": "e1", "topic": "wicked.run.phase.started"}]},
        {"mount": 1, "replay": False, "rows": [{"id": "e2", "topic": "wicked.run.unit.started"}]},
    ]
    r3_leaked = mod.r3_topics_verdict(leaked_batches, granted, withheld)
    assert r3_leaked["ok"] is False and "wicked.run.unit.started" in r3_leaked["leaked"]
    assert mod.r3_topics_verdict([], granted, withheld)["ok"] is False
    assert mod.r3_topics_verdict(clean_batches, granted, withheld, alive=False)["ok"] is False

    # r4-replay: fails on a duplicate id, on a missing id, and on a gap; passes on a clean sequence.
    clean_replay = [
        {"mount": 1, "replay": True, "rows": [{"id": "e1", "topic": "wicked.run.phase.started"}]},
        {"mount": 1, "replay": False, "rows": [{"id": "e2", "topic": "wicked.run.phase.completed"}]},
        {"mount": 2, "replay": True, "rows": [
            {"id": "e1", "topic": "wicked.run.phase.started"},
            {"id": "e2", "topic": "wicked.run.phase.completed"},
        ]},
        {"mount": 2, "replay": False, "rows": [{"id": "e3", "topic": "wicked.run.phase.started"}]},
    ]
    assert mod.r4_replay_verdict(clean_replay, ["e1", "e2"], ["e3"])["ok"] is True

    dup_replay = [
        {"mount": 2, "replay": True, "rows": [{"id": "e1", "topic": "wicked.run.phase.started"}]},
        {"mount": 2, "replay": False, "rows": [
            {"id": "e1", "topic": "wicked.run.phase.started"},
            {"id": "e2", "topic": "wicked.run.phase.completed"},
        ]},
    ]
    r4_dup = mod.r4_replay_verdict(dup_replay, ["e1"], ["e2"])
    assert r4_dup["ok"] is False and "e1" in r4_dup["duplicates"]

    missing_replay = [
        {"mount": 2, "replay": True, "rows": [{"id": "e1", "topic": "wicked.run.phase.started"}]},
        {"mount": 2, "replay": False, "rows": [{"id": "e3", "topic": "wicked.run.phase.started"}]},
    ]
    r4_missing = mod.r4_replay_verdict(missing_replay, ["e1", "e2"], ["e3"])
    assert r4_missing["ok"] is False and "e2" in r4_missing["missing"]

    gap_replay = [
        {"mount": 2, "replay": True, "gap": "dropped_before_seq_4", "rows": [
            {"id": "e1", "topic": "wicked.run.phase.started"},
            {"id": "e2", "topic": "wicked.run.phase.completed"},
        ]},
        {"mount": 2, "replay": False, "rows": [{"id": "e3", "topic": "wicked.run.phase.started"}]},
    ]
    r4_gap = mod.r4_replay_verdict(gap_replay, ["e1", "e2"], ["e3"])
    assert r4_gap["ok"] is False and r4_gap["gaps"] == ["dropped_before_seq_4"]

    # r5-hash-pinned: torn down and 0 handshakes.
    assert mod.r5_hash_pinned_verdict([], "bundle_hash_mismatch")["ok"] is True
    assert mod.r5_hash_pinned_verdict([{"kind": "handshake"}], "bundle_hash_mismatch")["ok"] is False
    assert mod.r5_hash_pinned_verdict([], None)["ok"] is False


def test_conformance_samples_server_and_engine_report_carry_plugins(tmp_path):
    import socket  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    mod = _conformance_module()
    pack = tmp_path / "run-pack"
    assert scaffold_run_plugin(pack).returncode == 0
    manifest = json.loads((pack / "wicked-pack.json").read_text())
    plugin = manifest["plugins"][0]
    samples_bytes = mod.build_plugin_samples(pack, plugin)
    rows = [json.loads(line) for line in samples_bytes.decode("utf-8").splitlines() if line.strip()]
    seen_types = {r["type"] for r in rows}
    assert {typ for types in mod.RUN_TOPICS.values() for typ in types} <= seen_types
    assert all(r["session"] == "conformance-run" and isinstance(r["seq"], int) and isinstance(r["ts"], (int, float)) for r in rows)
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))

    # The local origin serves the generated samples file on /api/v1/editors/<id>/<version>/samples.ndjson.
    (tmp_path / "index.html").write_text("<!doctype html><title>studio</title>")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = mod.make_server({}, None, tmp_path, 5.0, port, samples={("acme-spend", "0.1.0"): samples_bytes})
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/v1/editors/acme-spend/0.1.0/samples.ndjson", timeout=5
        ) as resp:  # noqa: S310
            assert resp.status == 200 and resp.read() == samples_bytes
    finally:
        server.shutdown()
        server.server_close()

    # The report and engine_report carry the top-level plugins array.
    rep = mod.engine_report({
        "ok": True,
        "pack": str(pack),
        "editors": [],
        "plugins": [{
            "id": "acme-spend",
            "version": "0.1.0",
            "sha256": plugin["sha256"],
            "protocol": [3],
            "negotiated": 3,
            "ok": True,
            "cases": {c: {"ok": True} for c in mod.RUN_PLUGIN_CASES},
        }],
    })
    assert rep["ok"] is True and rep["editors"] == [] and len(rep["plugins"]) == 1
    assert rep["plugins"][0]["id"] == "acme-spend" and rep["plugins"][0]["protocol"] == [3]
    assert set(rep["plugins"][0]["cases"]) == set(mod.RUN_PLUGIN_CASES)



@pytest.mark.parametrize("patterns", [
    ["wicked.run.**", "wicked.run.phase.*"],
    ["wicked.run.unit.*", "wicked.run.**"],
    ["wicked.run.unit.*", "wicked.run.unit.started"],
    ["wicked.run.*.started", "wicked.run.unit.*"],
])
def test_overlapping_plugin_patterns_do_not_make_granted_rows_leaks(patterns):
    mod = _conformance_module()
    grants, withheld = mod.split_plugin_topics({"observe": [{"topic": p} for p in patterns]})
    assert grants
    for w in withheld:
        assert not any(mod._pattern_covers(g, w) for g in grants)
    rows = [{"id": str(i), "topic": t} for i, t in enumerate(mod.RUN_TOPICS)
            if any(mod.topic_matches(g, t) for g in grants)]
    assert mod.r3_topics_verdict([{"rows": rows}], grants, withheld)["ok"]
    # A withheld broad pattern may overlap a granted narrower one: those rows remain authorized.
    assert mod.r3_topics_verdict([{"rows": [{"id": "s1", "topic": "wicked.run.unit.started"}]}],
                                 ["wicked.run.unit.*"], ["wicked.run.**"])["ok"]


def test_r4_requires_mount2_and_exact_independent_replay_and_live_ids(tmp_path):
    mod = _conformance_module()
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    plugin = json.loads((pack / "wicked-pack.json").read_text())["plugins"][0]
    samples = mod.build_plugin_samples(pack, plugin)
    grants, _ = mod.split_plugin_topics(plugin)
    first = len(samples.splitlines()) // 4
    replay, live = mod.expected_plugin_ids(samples, grants, first)
    assert replay and live and all(i.startswith("s") for i in replay) and live[0] == "l1"
    batches = [{"mount": 2, "replay": True, "rows": [{"id": i} for i in replay]},
               {"mount": 2, "replay": False, "rows": [{"id": i} for i in live]}]
    assert mod.r4_replay_verdict(batches, replay, live)["ok"]
    assert not mod.r4_replay_verdict([{**b, "mount": 1} for b in batches], replay, live)["ok"]
    assert not mod.r4_replay_verdict(batches[1:], replay, live)["ok"]
    assert not mod.r4_replay_verdict(batches[:1], replay, live)["ok"]
    dropped = [{**batches[0], "rows": batches[0]["rows"][1:]}, batches[1]]
    assert not mod.r4_replay_verdict(dropped, replay, live)["ok"]
    extra = [*batches, {"mount": 2, "replay": False, "rows": [{"id": "l999"}]}]
    assert mod.r4_replay_verdict(extra, replay, live)["unexpected"] == ["l999"]


def test_generated_samples_cover_every_source_in_both_halves_and_reject_malformed_extras(tmp_path):
    mod = _conformance_module()
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    plugin = json.loads((pack / "wicked-pack.json").read_text())["plugins"][0]
    path = pack / plugin["samples"]
    # Many extras must not push catalog coverage out of either half.
    path.write_text(path.read_text() * 30)
    rows = [json.loads(line) for line in mod.build_plugin_samples(pack, plugin).splitlines()]
    half = (len(rows) + 1) // 2
    types = {typ for source in mod.RUN_TOPICS.values() for typ in source}
    assert types <= {e["type"] for e in rows[:half]}
    assert types <= {e["type"] for e in rows[half:]}
    path.write_text('{}\n')
    with pytest.raises(mod.PackError, match="samples line 1.*CoreEvent"):
        mod.build_plugin_samples(pack, plugin)


# The browser runs a ResizeObserver's first callback as soon as it observes, before the host's hello: the scaffold
# must not remember a height it could not send, or the report right after hello looks unchanged and is lost (CJ9).
_RUN_PLUGIN_HELLO_HARNESS = r"""
const vm = require('vm');
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const src = html.slice(html.lastIndexOf('<script>') + 8, html.lastIndexOf('</script>'));
const node = () => ({ textContent: '', dataset: {}, style: { setProperty() {} }, setAttribute() {}, appendChild() {} });
const byId = {};
const main = { getBoundingClientRect: () => ({ height: 123.2 }) };
const observers = [];
const listeners = [];
const document = {
  querySelector: (sel) => (sel === 'main' ? main : null),
  getElementById: (id) => (byId[id] = byId[id] || node()),
  createElement: () => node(),
  body: { dataset: {} },
  documentElement: { style: { setProperty() {} } },
};
class ResizeObserver { constructor(cb) { this.cb = cb; } observe() { observers.push(this.cb); } }
vm.runInNewContext(src, {
  document, ResizeObserver, window: { addEventListener: (type, fn) => listeners.push([type, fn]) },
  parent: { postMessage() {} },
});
for (const cb of observers) cb([]);
const sent = [];
const port = { onmessage: null, postMessage: (m) => sent.push(m) };
const hello = { data: { p: 'wicked.editor', v: 1, type: 'host.hello', payload: { protocol: 3, observe: { topics: [] } } },
                ports: [port] };
for (const [type, fn] of listeners) if (type === 'message') fn(hello);
process.stdout.write(JSON.stringify(sent));
"""


def test_run_plugin_reports_its_first_height_right_after_hello(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to run the scaffold's script")
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    entry = pack / json.loads((pack / "wicked-pack.json").read_text())["plugins"][0]["entry"]
    harness = tmp_path / "hello-harness.cjs"
    harness.write_text(_RUN_PLUGIN_HELLO_HARNESS)
    done = subprocess.run([node, str(harness), str(entry)], capture_output=True, text=True, timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    sent = json.loads(done.stdout)
    heights = [m["payload"] for m in sent if m.get("type") == "ui.height"]
    assert heights == [{"px": 124}], sent


@pytest.fixture
def run_plugin_studio_dist():
    """Opt in to the real protocol-3 host, with no artifact-page DOM dependencies."""
    dist = os.environ.get("CS7_RUN_PLUGIN_DIST")
    if not dist:
        pytest.skip("set CS7_RUN_PLUGIN_DIST to a built studio dist for real run-plugin coverage")
    pytest.importorskip("playwright.sync_api")
    assert (Path(dist) / "index.html").is_file()
    return Path(dist)


def _plugin_conformance(pack, dist):
    done = run("conformance.py", "--pack", str(pack), "--studio-dist", str(dist), "--json", "--timeout", "30")
    report = json.loads(done.stdout)
    return done, report


def test_scaffold_run_plugin_real_host_conformance(tmp_path, run_plugin_studio_dist):
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    done, report = _plugin_conformance(pack, run_plugin_studio_dist)
    assert done.returncode == 0, json.dumps(report, indent=2) + done.stderr
    row = report["plugins"][0]
    assert report["ok"] and row["ok"]
    assert set(row["cases"]) == set(_conformance_module().RUN_PLUGIN_CASES)
    assert row["cases"]["r4-replay"]["live"] > 0
    assert row["cases"]["r4-replay"]["mount2"]


def test_run_plugin_real_host_detects_removed_topic_guard(tmp_path, run_plugin_studio_dist):
    # Mutate only a COPY of the built host page: feed it the declared observe list rather than the harness's grant.
    # A verdict-only fixture cannot catch this regression; the real host and RunEventFeed must deliver the leak.
    mutant = tmp_path / "studio-unfiltered"
    shutil.copytree(run_plugin_studio_dist, mutant)
    patched = 0
    for js in mutant.rglob("*.js"):
        text = js.read_text()
        text, n = re.subn(r'\b\w+\.get\("observe"\)',
                          '"wicked.run.session.*,wicked.run.unit.*"', text)
        if n:
            js.write_text(text)
            patched += n
    assert patched == 1, "the real host's observe query reader must be the only mutation"
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    done, report = _plugin_conformance(pack, mutant)
    assert done.returncode == 1, report
    verdict = report["plugins"][0]["cases"]["r3-topics"]
    assert not verdict["ok"] and verdict["ungranted"] and verdict["alive"], report


def test_run_plugin_real_host_rejects_computed_network_load(tmp_path, run_plugin_studio_dist):
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    manifest = json.loads((pack / "wicked-pack.json").read_text())
    entry = pack / manifest["plugins"][0]["entry"]
    entry.write_text(entry.read_text().replace('</body>',
        "<script>new Image().src = ['https:', '', 'evil.example', 'image.png'].join('/');</script></body>"))
    assert run("pin.py", str(pack)).returncode == 0
    # Computed loads pass the static scan, so the browser's CSP/request observation has to catch this one.
    assert not [f for f in check_pack(pack, garden_root=REPO) if f.level == "error"]
    done, report = _plugin_conformance(pack, run_plugin_studio_dist)
    assert done.returncode == 1, report
    verdict = report["plugins"][0]["cases"]["r2-no-network"]
    assert not verdict["ok"] and any("evil.example" in url for url in verdict["requests"]), report


@pytest.mark.parametrize("patterns", ["wicked.run.**,wicked.run.phase.*", "wicked.run.**,wicked.run.unit.*"])
def test_run_plugin_real_host_accepts_overlapping_grants(tmp_path, run_plugin_studio_dist, patterns):
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack, "--observe", patterns).returncode == 0
    done, report = _plugin_conformance(pack, run_plugin_studio_dist)
    assert done.returncode == 0 and report["ok"], report


def test_run_plugin_real_host_hello_topics_and_summary_payload(tmp_path, run_plugin_studio_dist):
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright

    mod = _conformance_module()
    pack = tmp_path / "plugin"
    assert scaffold_run_plugin(pack).returncode == 0
    plugin = json.loads((pack / "wicked-pack.json").read_text())["plugins"][0]
    body = (pack / plugin["entry"]).read_bytes()
    key = (plugin["id"], plugin["version"])
    server = mod.make_server({key: (body, plugin["sha256"])}, None, run_plugin_studio_dist, 30, 0,
                             samples={key: mod.build_plugin_samples(pack, plugin)})
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                query = urlencode({"plugin": plugin["id"], "version": plugin["version"], "sha": plugin["sha256"],
                                   "observe": "wicked.run.unit.*", "samples": f"/api/v1/editors/{key[0]}/{key[1]}/samples.ndjson"})
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/editors/conformance?{query}")
                page.wait_for_function("() => window.__wickedRunPlugin?.log.some(e => "
                                       "e.kind === 'in' && e.type === 'panel.summary' && e.ok)")
                text = page.frame_locator("iframe").locator("#status").inner_text()
                assert "wicked.run.unit.*" in text and "No topics granted" not in text
                assert page.frame_locator("iframe").locator('[role="listitem"]').count() > 0
                assert not page.evaluate("() => window.__wickedRunPlugin.log.some(e => "
                                         "e.type === 'panel.summary' && (e.ok === false || e.kind === 'dropped'))")
                # The section sizes to its rows: the scaffold reports its height, and the host takes it.
                page.wait_for_function("() => window.__wickedRunPlugin.log.some(e => e.kind === 'in' && e.type === 'ui.height' && e.ok)")
                assert not page.evaluate("() => window.__wickedRunPlugin.log.some(e => "
                                         "e.type === 'ui.height' && (e.ok === false || e.kind === 'dropped'))")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
