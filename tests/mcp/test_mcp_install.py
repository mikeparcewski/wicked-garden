"""The `install` action (scripts/mcp/install.py): install or update a built MCP server for
running, idempotent by key. DES-mcp-server-workflow rev 2 §4b.

No network: a stub `npm` on PATH "builds" by writing dist/server.js (the real zero-dependency
Node template, so the smoke probe is real), a stub `wicked-installer` records its argv and
prints the envelope, and a local http.server plays the daemon's registry routes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from daemon_fixture import FakeDaemon, closed_origin

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="stub executables are POSIX scripts"),
    pytest.mark.skipif(shutil.which("node") is None, reason="needs node for the smoke probe"),
]

REPO = Path(__file__).resolve().parent.parent.parent
INSTALL = REPO / "scripts" / "mcp" / "install.py"
NODE_TEMPLATE = REPO / "skills" / "mcp-scaffold" / "assets" / "node" / "server.mjs"
PREVIEW = "/api/v1/mcp/servers/preview"
SAVE = "/api/v1/mcp/servers"
VAR = "ACME_NOTES_TOKEN"

BROKEN_SERVER = "process.stderr.write('boom: cannot load the thing\\n'); process.exit(3);\n"
NEEDS_TOKEN = ("if (!process.env.ACME_NOTES_TOKEN) {\n"
               "  process.stderr.write('ACME_NOTES_TOKEN is not set\\n'); process.exit(1);\n}\n")

STUB_NPM = textwrap.dedent('''\
    #!PYTHON
    import json, os, shutil, sys
    with open(os.environ["STUB_LOG"], "a") as fh:
        fh.write(json.dumps({"tool": "npm", "argv": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
    if sys.argv[1:3] == ["run", "build"]:
        os.makedirs("dist", exist_ok=True)
        shutil.copyfile(os.environ["STUB_SERVER_SOURCE"], os.path.join("dist", "server.js"))
    ''')
STUB_INSTALLER = textwrap.dedent('''\
    #!PYTHON
    import json, os, sys
    with open(os.environ["STUB_LOG"], "a") as fh:
        fh.write(json.dumps({"tool": "wicked-installer", "argv": sys.argv[1:]}) + "\\n")
    if os.environ.get("STUB_INSTALLER_MODE") == "noverb":
        sys.stderr.write("wicked-installer: unknown command 'mcp'\\n")
        sys.exit(2)
    verb, key = sys.argv[2], sys.argv[3]
    argv = sys.argv[1:]
    def home(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else os.path.expanduser(default)
    result = "planned" if "--dry-run" in argv else "written"
    print(json.dumps({"verb": verb, "key": key, "clis": [
        {"cli": "claude", "result": result,
         "target": os.path.join(home("--claude-home", "~"), ".claude.json"), "detail": None},
        {"cli": "codex", "result": result,
         "target": os.path.join(home("--codex-home", "~/.codex"), "config.toml"), "detail": None},
        {"cli": "pi", "result": "unsupported", "target": home("--pi-home", "~/.pi/agent"),
         "detail": "unsupported: no MCP target"}]}))
    ''')


def _stub(path: Path, text: str) -> None:
    path.write_text(text.replace("PYTHON", sys.executable), encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def rig(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir / "npm", STUB_NPM)
    _stub(bin_dir / "wicked-installer", STUB_INSTALLER)
    tree = tmp_path / "tree"
    srv = tree / "servers" / "acme"
    srv.mkdir(parents=True)
    (srv / "mcp-server.config.json").write_text(json.dumps(
        {"key": "acme-notes", "version": "0.1.0", "transport": "stdio",
         "baseUrl": "https://api.example.com"}), encoding="utf-8")
    (srv / "package.json").write_text('{"name": "acme-notes", "version": "0.1.0"}', encoding="utf-8")
    (srv / "package-lock.json").write_text('{"lockfileVersion": 3}', encoding="utf-8")
    (srv / "tools.json").write_text('{"tools": []}', encoding="utf-8")
    source = tmp_path / "server-source.js"
    source.write_text(NODE_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    log = tmp_path / "stub.log"
    log.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if k not in ("WICKED_CREW_URL", "WICKED_REPO", "WICKED_WORKER_HOME", VAR)}
    # A temp HOME: the worker target must never name a path outside it (core#820).
    (tmp_path / "home").mkdir()
    env.update({"HOME": str(tmp_path / "home"), "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}", "STUB_LOG": str(log),
                "STUB_SERVER_SOURCE": str(source), "WICKED_TREE": str(tree),
                "WICKED_MCP_INSTALL_ROOT": str(tmp_path / "root")})

    class Rig:
        pass
    r = Rig()
    r.tmp, r.tree, r.srv, r.source, r.env = tmp_path, tree, srv, source, env
    r.home = tmp_path / "home"
    r.worker_args = ["--claude-home", str(r.home / ".wicked-worker" / "claude"),
                     "--codex-home", str(r.home / ".wicked-worker" / "codex"),
                     "--opencode-home", str(r.home / ".wicked-worker" / "opencode" / "config" / "opencode"),
                     "--pi-home", str(r.home / ".wicked-worker" / "pi"),
                     "--gemini-home", str(r.home / ".wicked-worker" / "agy")]
    r.root = tmp_path / "root" / "acme-notes"

    def run(*args: str, **extra_env: str):
        done = subprocess.run([sys.executable, str(INSTALL), *args], capture_output=True,
                              text=True, timeout=180, env={**env, **extra_env}, cwd=tree)
        try:
            out = json.loads(done.stdout)
        except ValueError:
            out = {"_stdout": done.stdout, "_stderr": done.stderr}
        return done.returncode, out

    def calls(tool: str):
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
                if json.loads(line)["tool"] == tool]
    r.run, r.calls = run, calls
    return r


def _registry(daemon: FakeDaemon, diff=None, servers=None):
    daemon.routes[("GET", SAVE)] = (200, {"servers": servers or [], "discovered": []})
    daemon.routes[("POST", PREVIEW)] = (200, {"previewHash": "ph-1", "diff": diff, "policies": {"read": "allow"},
                                              "tools": [{"name": "echo"}, {"name": "counter_increment"}]})
    daemon.routes[("POST", SAVE)] = (200, {"name": "acme-notes"})


def test_first_install_stages_registers_writes_clis_and_records(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 0, out
    current_js = rig.root / "current" / "dist" / "server.js"
    assert current_js.is_file() and not (rig.root / "next").exists()
    assert out["smoke"] == "ok" and out["probe"]["ok"] is True
    assert out["registered"] is True
    assert out["registry"] == {"server": "acme-notes", "tools": 2, "policies": {"read": "allow"}}
    assert out["command"] == "node" and out["args"] == [str(current_js)]
    assert out["envNames"] == [VAR]
    listed, relisted, preview, save = daemon.requests
    assert (listed["method"], listed["path"]) == ("GET", SAVE), "the key is checked before staging"
    assert (relisted["method"], relisted["path"]) == ("GET", SAVE), "and again before the save"
    assert preview["path"] == PREVIEW and preview["body"] == {
        "name": "acme-notes", "kind": "mcp-stdio", "command": "node", "args": [str(current_js)],
        "auth": {"ref": f"env:{VAR}", "env": VAR}}
    assert save["path"] == SAVE and save["body"] == {"previewHash": "ph-1"}
    (inst,) = rig.calls("wicked-installer")
    assert inst["argv"] == ["mcp", "upsert", "acme-notes", "--command", "node", "--arg",
                            str(current_js), "--cli", "all", "--json", *rig.worker_args], \
        "the default target registers in the worker homes only (core#820)"
    assert out["target"] == "worker" and "operatorClis" not in out
    assert out["clis"][0]["result"] == "written"
    npm = [c["argv"] for c in rig.calls("npm")]
    assert npm == [["ci", "--ignore-scripts"], ["run", "build"], ["ci", "--omit=dev", "--ignore-scripts"]]
    record = json.loads((rig.root / "installed.json").read_text(encoding="utf-8"))
    assert record["key"] == "acme-notes" and record["version"] == "0.1.0"
    assert record["source"]["dir"] == str(rig.srv)
    assert record["registered"] is True and record["smoke"] == "ok"
    for f in ("package.json", "package-lock.json", "tools.json", "mcp-server.config.json"):
        assert (rig.root / "current" / f).is_file()


def test_second_install_updates_in_place(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        assert rig.run("--from-run", "--crew-url", daemon.origin)[0] == 0
        (rig.srv / "tools.json").write_text('{"tools": [], "v": 2}', encoding="utf-8")
        _registry(daemon, diff={"registered": [], "gone": []})
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 0, out
    assert out["registered"] == "updated"
    assert json.loads((rig.root / "previous" / "tools.json").read_text(encoding="utf-8")) == {"tools": []}
    assert json.loads((rig.root / "current" / "tools.json").read_text(encoding="utf-8"))["v"] == 2
    first, second = rig.calls("wicked-installer")
    assert first["argv"] == second["argv"], "the CLI entry never changes on an update"
    posts = [r for r in daemon.requests if r["method"] == "POST"]
    assert posts[0]["body"]["args"] == posts[2]["body"]["args"]


def test_secret_missing_is_disclosed_not_failed(rig):
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (409, {"code": "secret_missing", "message": "env ref unresolved"})
        code, out = rig.run("--dir", str(rig.srv), "--crew-url", daemon.origin, "--json")

    assert code == 0, out
    assert out["registered"] is False and out["missing"] == [VAR]
    assert len(out["remedy"]) == 2
    assert VAR in out["remedy"][0] and "Add existing" in out["remedy"][1]
    assert [r["path"] for r in daemon.requests if r["method"] == "POST"] == [PREVIEW], "nothing is saved"
    assert (rig.root / "current" / "dist" / "server.js").is_file()


def test_no_daemon_is_disclosed_not_failed(rig):
    origin = closed_origin()
    code, out = rig.run("--from-run", "--crew-url", origin)

    assert code == 0, out
    assert out["registered"] is False and out["reason"] == f"no daemon at {origin}"
    assert json.loads((rig.root / "installed.json").read_text(encoding="utf-8"))["registered"] is False


def test_a_missing_credential_at_smoke_is_pending_not_failed(rig):
    body = NODE_TEMPLATE.read_text(encoding="utf-8")
    if body.startswith("#!"):
        body = body.split("\n", 1)[1]  # the guard goes first; a shebang may only be line 1
    rig.source.write_text(NEEDS_TOKEN + body, encoding="utf-8")
    code, out = rig.run("--from-run", "--crew-url", closed_origin())

    assert code == 0, out
    assert out["smoke"] == "pending_credential"
    assert (rig.root / "current" / "dist" / "server.js").is_file()


def test_a_probe_failure_exits_1_and_leaves_current_untouched(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        assert rig.run("--from-run", "--crew-url", daemon.origin)[0] == 0
        before = (rig.root / "current" / "dist" / "server.js").read_text(encoding="utf-8")
        rig.source.write_text(BROKEN_SERVER, encoding="utf-8")
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 1 and out["ok"] is False and "smoke" in out["error"]
    assert (rig.root / "current" / "dist" / "server.js").read_text(encoding="utf-8") == before
    assert not (rig.root / "next").exists() and not (rig.root / "previous").exists()
    assert len([r for r in daemon.requests if r["method"] == "POST"]) == 2, \
        "the failed install never reached the registry"


def test_an_installer_without_the_verb_is_skipped(rig):
    code, out = rig.run("--from-run", "--crew-url", closed_origin(), STUB_INSTALLER_MODE="noverb")

    assert code == 0, out
    assert out["clis"].startswith("skipped: wicked-installer lacks the mcp verb")


def test_registry_refusal_exits_1_with_the_daemons_message(rig):
    with FakeDaemon() as daemon:
        daemon.routes[("POST", PREVIEW)] = (400, {"error": "args[0] must be absolute"})
        code, out = rig.run("--from-run", "--crew-url", daemon.origin, "--cli", "none")

    assert code == 1
    assert "args[0] must be absolute" in out["error"]
    assert out["clis"] == "skipped: --cli none"


def test_uninstall_deletes_the_registration_clis_and_root(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        assert rig.run("--from-run", "--crew-url", daemon.origin)[0] == 0
        daemon.routes[("DELETE", "/api/v1/mcp/servers/acme-notes")] = (200, {"ok": True})
        code, out = rig.run("--uninstall", "acme-notes", "--crew-url", daemon.origin)

    assert code == 0, out
    assert out["registered"] == "removed" and out["uninstalled"] is True
    assert daemon.requests[-1]["method"] == "DELETE"
    assert rig.calls("wicked-installer")[-1]["argv"] == ["mcp", "remove", "acme-notes", "--json",
                                                         *rig.worker_args]
    assert not rig.root.exists()


def test_two_configs_in_the_tree_exit_2_naming_both(rig):
    other = rig.tree / "other"
    other.mkdir()
    (other / "mcp-server.config.json").write_text('{"key": "other"}', encoding="utf-8")
    (rig.tree / "node_modules" / "x").mkdir(parents=True)
    (rig.tree / "node_modules" / "x" / "mcp-server.config.json").write_text('{"key": "nm"}', encoding="utf-8")
    code, out = rig.run("--from-run", "--crew-url", closed_origin())

    assert code == 2
    assert str(rig.srv / "mcp-server.config.json") in out["error"]
    assert str(other / "mcp-server.config.json") in out["error"]
    assert "node_modules" not in out["error"] and "--dir" in out["error"]


def test_key_mismatch_and_bad_cli_are_argument_errors(rig):
    assert rig.run("--dir", str(rig.srv), "--key", "nope")[0] == 2
    assert rig.run("--dir", str(rig.srv), "--cli", "emacs")[0] == 2


def test_no_secret_value_is_ever_sent_or_recorded(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        code, out = rig.run("--from-run", "--crew-url", daemon.origin, **{VAR: "s3cr3t-value-xyz"})

    assert code == 0, out
    blob = json.dumps(out) + "".join(r["raw"] for r in daemon.requests) + \
        (rig.root / "installed.json").read_text(encoding="utf-8") + \
        (rig.tmp / "stub.log").read_text(encoding="utf-8")
    assert "s3cr3t-value-xyz" not in blob
    assert not any(p.name == ".env" for p in rig.tmp.rglob(".env"))


def test_uninstall_keeps_everything_when_the_registry_refuses(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        assert rig.run("--from-run", "--crew-url", daemon.origin)[0] == 0
        daemon.routes[("DELETE", "/api/v1/mcp/servers/acme-notes")] = (500, {"error": "store locked"})
        code, out = rig.run("--uninstall", "acme-notes", "--crew-url", daemon.origin)

    assert code == 1 and "store locked" in out["error"]
    assert (rig.root / "current" / "dist" / "server.js").is_file()


def _theirs(**over):
    return {"name": "acme-notes", "kind": "rest", "command": None, "args": [],
            "url": "https://petstore.example/v3", **over}


@pytest.mark.parametrize("existing", [
    _theirs(),                                                     # another kind (the dogfood case)
    _theirs(kind="mcp-stdio", command="node", args=["/elsewhere/server.js"], url=None),
])
def test_a_different_server_under_the_key_refuses_before_writing(rig, existing):
    """garden#1250: the same key is an update only of THIS install; another server under the
    key (a REST entry named the same, or a stdio server elsewhere) refuses, writing nothing."""
    with FakeDaemon() as daemon:
        _registry(daemon, servers=[existing])
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 1, out
    assert "different server under the key 'acme-notes'" in out["error"]
    assert existing["kind"] in out["error"] and "--uninstall acme-notes" in out["error"]
    assert [r["method"] for r in daemon.requests] == ["GET"], "nothing was previewed or saved"
    assert rig.calls("npm") == [] and rig.calls("wicked-installer") == []
    assert not rig.root.exists(), "nothing staged"


def test_the_same_install_under_the_key_is_the_update(rig):
    current_js = rig.root / "current" / "dist" / "server.js"
    with FakeDaemon() as daemon:
        _registry(daemon, diff={"registered": [], "gone": []}, servers=[
            _theirs(kind="mcp-stdio", command="node", args=[str(current_js)], url=None)])
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 0, out
    assert out["registered"] == "updated"


def test_an_unreadable_registry_refuses_before_writing(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        daemon.routes[("GET", SAVE)] = (503, {"error": "registry unavailable"})
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 1, out
    assert "cannot read the registry" in out["error"] and "registry unavailable" in out["error"]
    assert rig.calls("npm") == [] and not rig.root.exists()


def test_a_key_claimed_while_staging_is_never_overwritten(rig):
    """The check runs again right before the save (codex review): a different server that took
    the key while this one staged refuses the registration; nothing is previewed or saved."""
    lists = iter([[], [_theirs()]])
    with FakeDaemon() as daemon:
        _registry(daemon)
        daemon.routes[("GET", SAVE)] = lambda _req: (200, {"servers": next(lists), "discovered": []})
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)

    assert code == 1, out
    assert out["registered"] is False and "different server under the key" in out["error"]
    assert [r["method"] for r in daemon.requests] == ["GET", "GET"], "nothing previewed or saved"


# ── core#820: --target worker|operator and --dry-run; garden#1258: no port default ─────────

def _under(path: str, root: Path) -> bool:
    p = Path(path)
    return p == root or root in p.parents


def test_the_dry_run_plans_each_target_and_writes_nothing(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        done = subprocess.run([sys.executable, str(INSTALL), "--from-run", "--dry-run", "--json",
                               "--crew-url", daemon.origin], capture_output=True, text=True,
                              timeout=120, env=rig.env, cwd=rig.tree)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 1, "ONE JSON line on stdout"
    plan = json.loads(lines[0])
    assert plan["dry_run"] is True and plan["key"] == "acme-notes"
    worker, operator = plan["choices"]
    assert (worker["id"], worker["default"], operator["id"]) == ("worker", True, "operator")
    assert worker["label"] == "Install for workers" and operator["label"] == "Also install into my CLIs"
    # Worker: program-owned only — everything under the temp HOME's .wicked*, or the daemon.
    for w in worker["writes"]:
        assert w["operator_owned"] is False, w
        assert "://" in w["path"] or _under(w["path"], rig.tmp), w
    assert {w["what"] for w in worker["writes"]} >= {"install root", "wicked-crew MCP tools registry entry",
                                                      "claude MCP config", "codex MCP config (codex mcp add)"}
    claude = next(w for w in worker["writes"] if w.get("cli") == "claude")
    assert claude["path"] == str(rig.home / ".wicked-worker" / "claude" / ".claude.json")
    # Operator: every worker write, plus the operator's own configs, flagged.
    assert operator["writes"][:len(worker["writes"])] == worker["writes"]
    own = operator["writes"][len(worker["writes"]):]
    assert {w["path"] for w in own} == {str(rig.home / ".claude.json"), str(rig.home / ".codex" / "config.toml")}
    assert all(w["operator_owned"] is True for w in own)
    assert {"cli": "pi", "why": "unsupported"} in plan["skipped"]
    # Nothing was written: no npm, no staging, only dry-run installer calls, only a registry GET.
    assert rig.calls("npm") == [] and not (rig.tmp / "root").exists()
    assert all("--dry-run" in c["argv"] for c in rig.calls("wicked-installer"))
    assert {r["method"] for r in daemon.requests} == {"GET"}


def test_the_operator_target_also_writes_the_operators_clis(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        code, out = rig.run("--from-run", "--target", "operator", "--crew-url", daemon.origin)
    assert code == 0, out
    worker_call, operator_call = rig.calls("wicked-installer")
    assert worker_call["argv"][-len(rig.worker_args):] == rig.worker_args
    assert not any(a.startswith("--") and a.endswith("-home") for a in operator_call["argv"])
    assert out["target"] == "operator" and isinstance(out["operatorClis"], list)


def test_the_worker_target_never_names_an_operator_path(rig):
    with FakeDaemon() as daemon:
        _registry(daemon)
        code, out = rig.run("--from-run", "--crew-url", daemon.origin)
    assert code == 0, out
    (call,) = rig.calls("wicked-installer")
    paths = [a for a in call["argv"] if a.startswith("/")]
    assert paths and all(_under(p, rig.tmp) for p in paths), paths
    assert all(".wicked" in Path(p).relative_to(rig.home).parts[0] for p in paths
               if _under(p, rig.home)), paths
    for row in out["clis"]:
        assert _under(row["target"], rig.home / ".wicked-worker"), row


def test_no_origin_refuses_and_names_the_remedy_1258(rig):
    code, out = rig.run("--from-run")
    assert code == 2
    assert "WICKED_CREW_URL" in out["error"] and "--crew-url" in out["error"]
    assert rig.calls("npm") == [], "nothing is staged without the run's daemon"
    done = subprocess.run([sys.executable, str(INSTALL), "--from-run", "--dry-run", "--json"],
                          capture_output=True, text=True, timeout=60, env=rig.env, cwd=rig.tree)
    assert done.returncode == 2 and "WICKED_CREW_URL" in done.stderr and done.stdout == ""


def test_the_dry_run_never_downloads_the_installer(rig):
    (rig.tmp / "bin" / "wicked-installer").unlink()
    npx = rig.tmp / "bin" / "npx"
    _stub(npx, '#!PYTHON\nimport json, os, sys\nopen(os.environ["STUB_LOG"], "a").write(json.dumps({"tool": "npx", "argv": sys.argv[1:]}) + "\\n")\n')
    env = {**rig.env, "PATH": f"{rig.tmp / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin"}
    with FakeDaemon() as daemon:
        _registry(daemon)
        done = subprocess.run([sys.executable, str(INSTALL), "--from-run", "--dry-run", "--json",
                               "--crew-url", daemon.origin], capture_output=True, text=True,
                              timeout=60, env=env, cwd=rig.tree)
    assert done.returncode != 0 and "never downloads" in done.stderr, done.stderr
    assert rig.calls("npx") == []
