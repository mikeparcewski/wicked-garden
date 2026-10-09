#!/usr/bin/env python3
"""The ``install`` action: install or update a built MCP server for running, idempotent by key.

    wicked-garden run scripts/mcp/install.py (--from-run | --dir <server dir>) [--key <key>]
        [--from-npm <pkg>@<version>] [--cli all|claude,codex,opencode,antigravity,pi|none]
        [--crew-url <origin>] [--install-root <dir>] [--json]
    wicked-garden run scripts/mcp/install.py --uninstall <key> [--cli ...] [--crew-url ...]

1. **Locate** the server: ``--from-run`` finds the one ``mcp-server.config.json`` under
   ``$WICKED_TREE`` (else the cwd), outside node_modules/dist; ``--dir`` names it. The key and
   version come from that config.
2. **Stage** into ``<root>/<key>/next/`` (root: ``--install-root``, ``$WICKED_MCP_INSTALL_ROOT``,
   else ``~/.wicked/mcp-servers``): ``npm ci --ignore-scripts && npm run build`` in the server
   dir, copy dist/ + package.json + package-lock.json + tools.json + mcp-server.config.json,
   ``npm ci --omit=dev --ignore-scripts`` there. ``--from-npm`` installs the package instead.
3. **Smoke** with ``probe.py``. A failure naming ``<SERVER>_TOKEN`` is a pending credential
   (disclosed, not failed); any other failure exits 1 with ``next/`` removed and nothing else
   touched.
4. **Swap** ``current/`` → ``previous/``, ``next/`` → ``current/``. The registered command
   ``node <root>/<key>/current/dist/server.js`` is stable across updates.
5. **Register** with wicked-crew (``POST /api/v1/mcp/servers/preview`` with
   ``auth: {ref: "env:<SERVER>_TOKEN"}`` — a reference, never a value — then
   ``POST /api/v1/mcp/servers {previewHash}``); saving over the same key is the update — but
   only of THIS install: before anything is staged, a registry entry under the key that is a
   different server (another ``kind``, command or args — e.g. a REST server named the same)
   refuses the install (exit 1) naming it, and nothing is written; the check runs again right
   before the save, so a key claimed while staging is never overwritten either.
6. **CLI configs** through ``wicked-installer mcp upsert`` (never written here); an installer
   without the verb is reported, not failed.
7. **Record** ``<root>/<key>/installed.json`` and print one JSON record.

Exit 0 staged (a pending credential or an absent daemon are disclosed in the record), 1 a
staging, smoke or registry failure, 2 bad arguments. Never reads, prints or sends a secret
value; never writes ``.env``. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE / "probe.py"
DEFAULT_ORIGIN = "http://127.0.0.1:7701"
CONFIG_NAME = "mcp-server.config.json"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
NPM_SPEC_RE = re.compile(r"^(?P<pkg>(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*)@(?P<version>[^@\s]+)$")
SKIP_DIRS = {"node_modules", "dist", ".git"}
STAGE_FILES = ("package.json", "package-lock.json", "tools.json", CONFIG_NAME)
CLIS = ("claude", "codex", "opencode", "antigravity", "pi")
NO_VERB = "skipped: wicked-installer lacks the mcp verb (needs >= the release that adds it)"
NPM_TIMEOUT_S = 600
PROBE_TIMEOUT_S = 30
HTTP_TIMEOUT_S = 60


class Failure(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# ── small helpers ──────────────────────────────────────────────────────────────────────────

def env_prefix(key: str) -> str:
    return key.upper().replace("-", "_")


def env_name_for(key: str) -> str:
    """The ONE variable the server reads its credential from (a NAME, never a value)."""
    return f"{env_prefix(key)}_TOKEN"


def crew_origin(flag: str | None) -> str:
    return (flag or os.environ.get("WICKED_CREW_URL") or DEFAULT_ORIGIN).rstrip("/")


def install_root(flag: Path | None) -> Path:
    if flag is not None:
        return flag
    env = os.environ.get("WICKED_MCP_INSTALL_ROOT")
    return Path(env) if env else Path.home() / ".wicked" / "mcp-servers"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _run(argv: list[str], cwd: Path, what: str, timeout: float = NPM_TIMEOUT_S) -> None:
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise Failure(1, f"{what} failed: {err}") from err
    if done.returncode != 0:
        tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
        raise Failure(1, f"{what} exited {done.returncode}: {tail[0][:300]}")


def _npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        raise Failure(1, "npm is not on PATH (Node >= 22 is required to build the server)")
    return npm


def _strip_userinfo(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        return urllib.parse.urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
    return url


def _git(dir_: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(dir_), *args], capture_output=True, text=True,
                              timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def http_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    """(status, parsed body). ``urllib.error.URLError`` propagates when nothing answers."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"content-type": "application/json",
                                          "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as res:  # noqa: S310
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        parsed = json.loads(raw or b"{}")
    except ValueError:
        parsed = {"message": raw.decode("utf-8", "replace")[:300]}
    return status, parsed if isinstance(parsed, dict) else {"value": parsed}


def _message(body: dict) -> str:
    return str(body.get("message") or body.get("error") or body.get("code") or "refused")


# ── 1. locate ──────────────────────────────────────────────────────────────────────────────

def find_configs(tree: Path) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if CONFIG_NAME in filenames:
            found.append(Path(dirpath) / CONFIG_NAME)
    return found


def locate(args) -> tuple[Path | None, dict]:
    if args.dir is not None:
        config_path = args.dir / CONFIG_NAME
        if not config_path.is_file():
            if args.from_npm:
                return None, {}
            raise Failure(2, f"{args.dir} has no {CONFIG_NAME}; scaffold the server first")
    elif args.from_run:
        tree = Path(os.environ.get("WICKED_TREE") or os.getcwd())
        found = find_configs(tree)
        if len(found) != 1:
            names = ", ".join(str(p) for p in found) or "none"
            raise Failure(2, f"--from-run needs exactly one {CONFIG_NAME} under {tree}; found "
                             f"{len(found)} ({names}) — pass --dir <server dir>")
        config_path = found[0]
    else:
        return None, {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise Failure(2, f"cannot read {config_path}: {err}") from err
    if not isinstance(config, dict) or not isinstance(config.get("key"), str):
        raise Failure(2, f"{config_path} has no string 'key'")
    return config_path.parent, config


# ── 3. smoke ───────────────────────────────────────────────────────────────────────────────

def smoke(server_js: Path, var: str) -> tuple[str, dict]:
    argv = [sys.executable, str(PROBE), "--timeout", str(PROBE_TIMEOUT_S), "--env", var, "--",
            "node", str(server_js)]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S + 30)
        report = json.loads(done.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as err:
        return "failed", {"ok": False, "error": f"probe did not run: {err}"}
    if report.get("ok") is True:
        return "ok", report
    if var in (report.get("stderrNames") or []):
        return "pending_credential", report
    return "failed", report


# ── 0. key collision ───────────────────────────────────────────────────────────────────────

def installed_rel(npm_spec: str | None) -> Path:
    """server.js relative to ``current/`` — known before staging, so the registry check runs first."""
    if npm_spec:
        pkg = NPM_SPEC_RE.match(npm_spec).group("pkg")
        return Path("node_modules", *pkg.split("/"), "dist", "server.js")
    return Path("dist", "server.js")


def check_key(origin: str, key: str, server_js: Path) -> dict | None:
    """Refuse when the registry holds a DIFFERENT server under ``key`` (garden#1250).

    The same key is the update only when the entry is this install (``mcp-stdio``, ``node``,
    the same staged path). No daemon: nothing to collide with here (registration reports it).
    Answers the existing entry's identity when it is this install, else None."""
    try:
        status, body = http_json("GET", f"{origin}/api/v1/mcp/servers")
    except (urllib.error.URLError, OSError):
        return None
    if status == 404:  # a daemon without the registry list route: registration will say so
        return None
    if status >= 400:
        raise Failure(1, f"cannot read the registry to check the key {key!r} (HTTP {status}): "
                         f"{_message(body)}; nothing was installed")
    servers = body.get("servers") if isinstance(body.get("servers"), list) else []
    existing = next((s for s in servers if isinstance(s, dict) and s.get("name") == key), None)
    if existing is None:
        return None
    ours = {"kind": "mcp-stdio", "command": "node", "args": [str(server_js)]}
    theirs = {k: existing.get(k) for k in ours}
    if theirs == ours:
        return theirs
    what = existing.get("kind") or "unknown-kind"
    where = existing.get("url") or " ".join([str(existing.get("command") or ""),
                                             *map(str, existing.get("args") or [])]).strip()
    raise Failure(1, f"the registry already holds a different server under the key {key!r} "
                     f"({what}{': ' + where if where else ''}); refusing to replace it. Pick "
                     f"another key in {CONFIG_NAME}, or remove the existing server first "
                     f"(studio MCP tools, or install.py --uninstall {key}); nothing was installed")


# ── 5. register ────────────────────────────────────────────────────────────────────────────

def register(origin: str, key: str, server_js: Path, var: str) -> dict:
    body = {"name": key, "kind": "mcp-stdio", "command": "node", "args": [str(server_js)],
            "auth": {"ref": f"env:{var}", "env": var}}
    try:
        status, preview = http_json("POST", f"{origin}/api/v1/mcp/servers/preview", body)
    except (urllib.error.URLError, OSError):
        return {"registered": False, "reason": f"no daemon at {origin}"}
    if status == 409 and preview.get("code") == "secret_missing":
        return {"registered": False, "missing": [var], "remedy": [
            f"export {var} in the wicked-crew daemon's environment and re-run install",
            "or add the server in studio MCP tools -> Add existing with the secret, which stores "
            f"it in the OS keychain (keychain:wicked-mcp/{key})",
        ]}
    if status >= 400:
        raise Failure(1, f"the registry refused the preview (HTTP {status}): {_message(preview)}")
    preview_hash = preview.get("previewHash")
    if not isinstance(preview_hash, str):
        raise Failure(1, "the registry's preview carried no previewHash")
    try:
        status, saved = http_json("POST", f"{origin}/api/v1/mcp/servers", {"previewHash": preview_hash})
    except (urllib.error.URLError, OSError):
        return {"registered": False, "reason": f"no daemon at {origin} (lost after the preview)"}
    if status >= 400:
        raise Failure(1, f"the registry refused the save (HTTP {status}): {_message(saved)}")
    tools = preview.get("tools") if isinstance(preview.get("tools"), list) else []
    return {
        "registered": "updated" if preview.get("diff") is not None else True,
        "registry": {"server": key, "tools": len(tools), "policies": preview.get("policies")},
    }


# ── 6. CLI configs ─────────────────────────────────────────────────────────────────────────

def installer(argv: list[str]):
    """Run ``wicked-installer <argv> --json``: its envelope, or the reportable condition."""
    exe = shutil.which("wicked-installer")
    cmd = [exe, *argv] if exe else [shutil.which("npx") or "npx", "-y", "wicked-installer", *argv]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as err:
        return f"skipped: wicked-installer did not run ({err.__class__.__name__})"
    text = f"{done.stdout}\n{done.stderr}".lower()
    if done.returncode == 2 or "unknown command" in text or "unknown verb" in text:
        try:
            envelope = json.loads(done.stdout)
        except ValueError:
            return NO_VERB
        if not isinstance(envelope, dict) or "clis" not in envelope:
            return NO_VERB
    try:
        envelope = json.loads(done.stdout)
    except ValueError:
        return f"failed: wicked-installer exited {done.returncode} without a JSON envelope"
    if isinstance(envelope, dict) and "clis" in envelope:
        return envelope["clis"]
    return envelope


def cli_list(raw: str) -> str:
    if raw in ("all", "none"):
        return raw
    names = [n.strip() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in CLIS]
    if unknown or not names:
        raise Failure(2, f"--cli: unknown {', '.join(unknown) or '(empty)'}; use all, none or a "
                         f"comma list of {', '.join(CLIS)}")
    return ",".join(names)


# ── the flows ──────────────────────────────────────────────────────────────────────────────

def _source(server_dir: Path | None, npm_spec: str | None) -> dict:
    if npm_spec:
        return {"npm": npm_spec}
    assert server_dir is not None
    repo = os.environ.get("WICKED_REPO") or _git(server_dir, "remote", "get-url", "origin")
    return {"repo": _strip_userinfo(repo) if repo else None,
            "branch": _git(server_dir, "rev-parse", "--abbrev-ref", "HEAD"),
            "commit": _git(server_dir, "rev-parse", "HEAD"),
            "dir": str(server_dir)}


def stage(server_dir: Path | None, npm_spec: str | None, next_dir: Path) -> Path:
    """Build + copy into next/; the server.js path inside next/."""
    npm = _npm()
    if npm_spec:
        pkg = NPM_SPEC_RE.match(npm_spec).group("pkg")  # validated by the caller
        next_dir.mkdir(parents=True)
        _run([npm, "install", "--prefix", str(next_dir), "--ignore-scripts", "--no-audit",
              "--no-fund", npm_spec], next_dir, f"npm install {npm_spec}")
        server_js = next_dir / "node_modules" / Path(*pkg.split("/")) / "dist" / "server.js"
    else:
        assert server_dir is not None
        _run([npm, "ci", "--ignore-scripts"], server_dir, "npm ci (server dir)")
        _run([npm, "run", "build"], server_dir, "npm run build")
        if not (server_dir / "dist").is_dir():
            raise Failure(1, f"npm run build left no dist/ in {server_dir}")
        next_dir.mkdir(parents=True)
        shutil.copytree(server_dir / "dist", next_dir / "dist")
        for name in STAGE_FILES:
            if (server_dir / name).is_file():
                shutil.copy2(server_dir / name, next_dir / name)
        if not (next_dir / "package-lock.json").is_file():
            raise Failure(1, f"{server_dir} has no package-lock.json (npm ci needs it)")
        _run([npm, "ci", "--omit=dev", "--ignore-scripts"], next_dir, "npm ci --omit=dev (staged copy)")
        server_js = next_dir / "dist" / "server.js"
    if not server_js.is_file():
        raise Failure(1, f"the staged server has no {server_js.relative_to(next_dir)}")
    return server_js


def swap(key_root: Path) -> None:
    current, previous, nxt = key_root / "current", key_root / "previous", key_root / "next"
    if current.exists():
        if previous.exists():
            shutil.rmtree(previous)
        current.rename(previous)
    nxt.rename(current)


def do_install(args) -> tuple[int, dict]:
    if args.from_npm and not NPM_SPEC_RE.match(args.from_npm):
        raise Failure(2, f"--from-npm {args.from_npm!r}: use <pkg>@<version>")
    server_dir, config = locate(args)
    key = config.get("key") or args.key
    if not key:
        raise Failure(2, "no server key: pass --dir/--from-run (the config's key) or --key with --from-npm")
    if args.key and args.key != key:
        raise Failure(2, f"--key {args.key} does not match the config's key {key}")
    if not NAME_RE.match(key):
        raise Failure(2, f"invalid server key {key!r}")
    if server_dir is None and not args.from_npm:
        raise Failure(2, "pass --from-run or --dir <server dir> (or --from-npm with --key)")
    clis = cli_list(args.cli)
    version = config.get("version")
    if args.from_npm:
        version = NPM_SPEC_RE.match(args.from_npm).group("version")
    var = env_name_for(key)
    root = install_root(args.install_root)
    key_root = root / key
    next_dir = key_root / "next"
    origin = crew_origin(args.crew_url)
    check_key(origin, key, key_root / "current" / installed_rel(args.from_npm))
    if next_dir.is_symlink():
        next_dir.unlink()
    elif next_dir.exists():
        shutil.rmtree(next_dir)  # a stale half-staged copy from an interrupted run
    key_root.mkdir(parents=True, exist_ok=True)

    try:
        staged_js = stage(server_dir if not args.from_npm else None, args.from_npm, next_dir)
        smoke_state, probe_report = smoke(staged_js, var)
        if smoke_state == "failed":
            raise Failure(1, f"the staged server failed its smoke: {probe_report.get('error')}")
    except Failure:
        shutil.rmtree(next_dir, ignore_errors=True)
        raise
    swap(key_root)
    current_js = key_root / "current" / staged_js.relative_to(next_dir)

    record = {"key": key, "version": version, "source": _source(server_dir, args.from_npm),
              "command": "node", "args": [str(current_js)], "envNames": [var],
              "installedAt": _now()}
    code = 0
    try:
        # Again right before the save: the key may have been claimed while this staged, or the
        # first check found no daemon to ask (the registry has no conditional save to lean on).
        check_key(origin, key, current_js)
        reg = register(origin, key, current_js, var)
    except Failure as err:
        reg = {"registered": False, "error": str(err)}
        code = 1
    record["registered"] = reg.pop("registered")
    record["smoke"] = smoke_state
    (key_root / "installed.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    out = {**record, **reg, "probe": probe_report}
    out.setdefault("registry", None)
    out["clis"] = "skipped: --cli none" if clis == "none" else installer(
        ["mcp", "upsert", key, "--command", "node", "--arg", str(current_js), "--cli", clis, "--json"])
    return code, out


def do_uninstall(args) -> tuple[int, dict]:
    key = args.uninstall
    if not NAME_RE.match(key):
        raise Failure(2, f"invalid server key {key!r}")
    clis = cli_list(args.cli)
    origin = crew_origin(args.crew_url)
    out: dict = {"key": key, "uninstalled": True}
    try:
        status, body = http_json("DELETE", f"{origin}/api/v1/mcp/servers/{urllib.parse.quote(key)}")
        if status == 404:
            out["registered"] = "absent"
        elif status >= 400:
            # Keep everything local so a re-run can finish the job once the daemon agrees.
            raise Failure(1, f"the registry refused the delete (HTTP {status}): {_message(body)}; "
                             "nothing was removed")
        else:
            out["registered"] = "removed"
    except (urllib.error.URLError, OSError):
        out["registered"] = False
        out["reason"] = f"no daemon at {origin}"
    out["clis"] = "skipped: --cli none" if clis == "none" else installer(["mcp", "remove", key, "--json"])
    key_root = install_root(args.install_root) / key
    out["removed"] = str(key_root) if key_root.exists() else None
    if key_root.exists():
        shutil.rmtree(key_root)
    return 0, out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--from-run", action="store_true",
                       help=f"find the one {CONFIG_NAME} under $WICKED_TREE (else the cwd)")
    where.add_argument("--dir", type=Path, help="the server directory")
    where.add_argument("--uninstall", metavar="KEY", help="unregister and remove an installed server")
    parser.add_argument("--key", help="the server key (must equal the config's key)")
    parser.add_argument("--from-npm", metavar="PKG@VERSION", help="install a published package instead")
    parser.add_argument("--cli", default="all", help="all | none | " + ",".join(CLIS))
    parser.add_argument("--crew-url", help=f"the wicked-crew origin (default $WICKED_CREW_URL, else {DEFAULT_ORIGIN})")
    parser.add_argument("--install-root", type=Path, help="default $WICKED_MCP_INSTALL_ROOT, else ~/.wicked/mcp-servers")
    parser.add_argument("--json", action="store_true", help="print the record as one compact JSON line")
    args = parser.parse_args(argv)
    try:
        code, out = do_uninstall(args) if args.uninstall else do_install(args)
    except Failure as err:
        code, out = err.code, {"ok": False, "error": str(err)}
    else:
        out = {"ok": code == 0, **out}
    print(json.dumps(out) if args.json else json.dumps(out, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
