#!/usr/bin/env python3
"""The ``install`` action: install or update a built editor plugin into a wicked-crew daemon's editors.

    wicked-garden run scripts/editor/install.py (--from-run | --dir <pack dir>) [--target daemon|daemon-off]
        [--dry-run] [--crew-url <origin>] [--install-root <dir>] [--json]
    wicked-garden run scripts/editor/install.py --uninstall <pack name> [--crew-url <origin>] [--install-root <dir>]

An editor plugin is a ``wicked-pack.json`` spec-2 pack with ``editors[]`` (scaffold it with
``scripts/editor/scaffold.py``). Install, idempotent by the pack's ``name``:

1. **Locate**: ``--from-run`` finds the one spec-2 ``wicked-pack.json`` with editors under
   ``$WICKED_TREE`` (else the cwd), outside node_modules/.git/dist; ``--dir`` names it.
2. **Stage** into ``<root>/<name>/next/`` (root: ``--install-root``, ``$WICKED_EDITOR_INSTALL_ROOT``,
   else ``~/.wicked/editors``, a program-owned place): ``wicked-pack.json``, every editor's entry
   file at its manifest path, and the README. Nothing else of the tree is copied (an editor is ONE
   self-contained file; a pack with skills or blocks is refused by the daemon until their approval
   step exists).
3. **Swap** ``current/`` → ``previous/``, ``next/`` → ``current/``.
4. **Register** with wicked-crew: ``POST /api/v1/editors {packRoot: <root>/<name>/current, enabled}``.
   The daemon re-runs garden's ``pack check`` and this skill's **conformance run** against the staged
   copy itself, refuses on any failure (fail closed: no headless browser is a refusal), pins each
   entry's sha256 and records it in its editor registry. A refusal swaps ``previous/`` back (or
   removes ``current/`` on a first install) and exits 1.
5. **Record** ``<root>/<name>/installed.json`` and print it.

**Targets** (the consent gate's choices): ``daemon`` (the default) installs it turned on — it opens
the artifact kinds it claims; ``daemon-off`` installs it turned off, to switch on in studio Settings
→ Developer → Editor plugins. Both write the same places, all program-owned. ``--dry-run`` writes
nothing and prints ONE JSON line, the plan: ``{"dry_run": true, "key", "choices": [{"id", "label",
"default"?, "writes": [{"path", "what", "operator_owned"}]}], "skipped": []}``. An editor that
declares ``mcp.session`` adds one more write to both choices, on the ``EDITOR-GRANTS`` steering rule:
"This plugin can start and talk to MCP servers", with the exact per-build token the install writes
(``editor:<id>@<version>#<sha256>/mcp.session``). The install consent is that grant; no rule allows it.

**The approval is bound to the plan.** Each choice id carries a digest of the planned
``wicked-pack.json`` bytes, the same bytes the plan's lines were read from (``daemon_<d>``,
``daemon-off_<d>``; ``<d>`` = 21 base64url characters of its sha256, 126 bits), and the gated step passes it
back as ``--target``. If the staged copy differs (another permission, version or entry hash), the install
refuses and writes nothing, so the operator is asked again. Inside a governed run only a bound choice
installs; a bare ``daemon``/``daemon-off`` is for installs by hand.

**Daemon origin**: ``--crew-url``, else ``$WICKED_CREW_URL`` (crew sets it for every governed unit).
There is no port default. Exit 0 installed, 1 a staging or registry failure, 2 bad arguments.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pack import (  # noqa: E402
    INSTALL_GRANTED, ID_RE, MANIFEST_NAME, PackError, editors_of, entry_path, read_manifest,
)

SKIP_DIRS = {"node_modules", "dist", ".git"}
# A choice id: the target, optionally bound to the plan by the digest of the manifest it showed. The id
# rides the consent gate's answer token and an env var: [A-Za-z0-9_-], at most 32 (core consent_plan.rs).
DIGEST_CHARS = 21
TARGET_RE = re.compile(r"^(daemon|daemon-off)(?:_([A-Za-z0-9_-]{%d}))?$" % DIGEST_CHARS)
CHOICE_LABELS = {"daemon": "Install for this daemon", "daemon-off": "Install, turned off"}
# The daemon re-runs the conformance cases (a headless browser, one ping period per editor) before it answers.
HTTP_TIMEOUT_S = 300


class Failure(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def crew_origin(flag: str | None) -> str:
    origin = flag or os.environ.get("WICKED_CREW_URL")
    if not origin:
        raise Failure(2, "no wicked-crew origin: $WICKED_CREW_URL is unset (crew sets it for every governed unit) "
                         "and no --crew-url was given; pass --crew-url <the daemon's URL> — never assume a port")
    return origin.rstrip("/")


def install_root(flag: Path | None) -> Path:
    if flag is not None:
        return flag
    env = os.environ.get("WICKED_EDITOR_INSTALL_ROOT")
    return Path(env) if env else Path.home() / ".wicked" / "editors"


def http_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"content-type": "application/json", "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as res:  # noqa: S310 (the run's own daemon)
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        parsed = json.loads(raw or b"{}")
    except ValueError:
        parsed = {"error": raw.decode("utf-8", "replace")[:300]}
    return status, parsed if isinstance(parsed, dict) else {"value": parsed}


def _message(body: dict) -> str:
    return str(body.get("error") or body.get("message") or body.get("code") or "refused")


# ── 1. locate ──────────────────────────────────────────────────────────────────────────────

def _is_editor_pack(manifest_path: Path) -> bool:
    try:
        editors_of(read_manifest(manifest_path.parent))
        return True
    except PackError:
        return False


def locate(args) -> tuple[Path, dict]:
    if args.dir is not None:
        pack = args.dir
    elif args.from_run:
        tree = Path(os.environ.get("WICKED_TREE") or os.getcwd())
        found = []
        for dirpath, dirnames, filenames in os.walk(tree):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            if MANIFEST_NAME in filenames and _is_editor_pack(Path(dirpath) / MANIFEST_NAME):
                found.append(Path(dirpath))
        if len(found) != 1:
            names = ", ".join(str(p) for p in found) or "none"
            raise Failure(2, f"--from-run needs exactly one editor pack ({MANIFEST_NAME} spec 2 with editors) under "
                             f"{tree}; found {len(found)} ({names}) — pass --dir <pack dir>")
        pack = found[0]
    else:
        raise Failure(2, "pass --from-run or --dir <pack dir>")
    try:
        manifest = read_manifest(pack)
        editors = editors_of(manifest)
        for e in editors:
            entry_path(pack, e)
    except PackError as err:
        raise Failure(2, str(err)) from err
    name = manifest.get("name")
    if not isinstance(name, str) or not ID_RE.match(name) or len(name) > 64:
        raise Failure(2, f"{pack / MANIFEST_NAME}: invalid pack name {name!r}")
    return pack, manifest


# ── 2-3. stage and swap ────────────────────────────────────────────────────────────────────

def stage(pack: Path, manifest: dict, next_dir: Path) -> list[str]:
    if next_dir.is_symlink():
        next_dir.unlink()
    elif next_dir.exists():
        shutil.rmtree(next_dir)  # a stale half-staged copy from an interrupted run
    next_dir.mkdir(parents=True)
    copied = [MANIFEST_NAME]
    shutil.copy2(pack / MANIFEST_NAME, next_dir / MANIFEST_NAME)
    root = next_dir.resolve()
    for e in editors_of(manifest):
        source = entry_path(pack, e)  # refuses an entry that is not a plain relative path inside the pack
        dest = (next_dir / Path(*e["entry"].split("/"))).resolve()
        if root not in dest.parents:
            raise PackError(f"editor {e.get('id')!r}: entry {e['entry']!r} would stage outside {next_dir}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(e["entry"])
    if (pack / "README.md").is_file():
        shutil.copy2(pack / "README.md", next_dir / "README.md")
        copied.append("README.md")
    return copied


def swap(key_root: Path) -> None:
    """``current/`` → ``previous/``, ``next/`` → ``current/``; a failed promotion puts ``current/`` back."""
    current, previous, nxt = key_root / "current", key_root / "previous", key_root / "next"
    moved = False
    if current.exists():
        if previous.exists():
            shutil.rmtree(previous)
        current.rename(previous)
        moved = True
    try:
        nxt.rename(current)
    except OSError as err:
        if moved and not current.exists():
            previous.rename(current)
        raise Failure(1, f"could not put the staged copy in place ({err}); the installed copy is unchanged") from err


def unswap(key_root: Path, had_previous_install: bool) -> None:
    current, previous = key_root / "current", key_root / "previous"
    if current.exists():
        shutil.rmtree(current)
    if had_previous_install and previous.exists():
        previous.rename(current)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ── the flows ──────────────────────────────────────────────────────────────────────────────

def install_grants(manifest: dict) -> list[dict]:
    """One write per editor permission the install consent grants: crew writes that build's token
    into the ``EDITOR-GRANTS`` steering rule when the operator approves (DES-MCP-INSPECTOR-001 §6)."""
    rows = []
    for e in editors_of(manifest):
        declared = {p.get("id") for p in e.get("permissions", []) if isinstance(p, dict)}
        for perm, line in INSTALL_GRANTED.items():
            if perm in declared:
                token = f"editor:{e.get('id')}@{e.get('version')}#{e.get('sha256')}/{perm}"
                rows.append({"path": "EDITOR-GRANTS", "operator_owned": False,
                             "what": f"{line}: {e.get('id')} is granted {token} (steering; revoke it there)"})
    return rows


def plan_digest(raw: bytes) -> str:
    """The manifest bytes' sha256 as base64url, cut to fit a choice id: what the plan showed (permissions,
    version, entry hashes)."""
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode("ascii")[:DIGEST_CHARS]


def parse_target(value: str) -> tuple[str, str | None]:
    m = TARGET_RE.match(value)
    if m is None:
        raise argparse.ArgumentTypeError(f"invalid target {value!r}: daemon or daemon-off (a plan's choice id may "
                                         "carry its _<digest>)")
    return m.group(1), m.group(2)


def do_plan(args) -> dict:
    pack, located = locate(args)
    # One read: the lines shown and the digest that binds the approval come from the same bytes.
    raw = (pack / MANIFEST_NAME).read_bytes()
    try:
        manifest = json.loads(raw)
    except ValueError:
        manifest = None
    if manifest != located:
        raise Failure(2, f"{pack / MANIFEST_NAME} changed while it was planned; plan it again")
    key = manifest["name"]
    root = install_root(args.install_root)
    origin = crew_origin(args.crew_url)
    key_root = Path(os.path.abspath(root / key))
    writes = [{"path": str(key_root / "current"), "what": "the staged copy of the editor pack (program-owned)",
               "operator_owned": False}]
    if (key_root / "current").exists():
        writes.append({"path": str(key_root / "previous"), "what": "the copy installed now, kept for a roll-back",
                       "operator_owned": False})
    writes += [{"path": str(key_root / "installed.json"), "what": "the install record", "operator_owned": False},
               {"path": f"{origin}/api/v1/editors", "what": "wicked-crew editor registry entry "
                f"({', '.join(str(e.get('id')) for e in editors_of(manifest))}; daemon-editors.json in its state home)",
                "operator_owned": False}]
    writes += install_grants(manifest)
    digest = plan_digest(raw)
    return {"dry_run": True, "key": key, "choices": [
        {"id": f"daemon_{digest}", "label": CHOICE_LABELS["daemon"], "default": True, "writes": writes},
        {"id": f"daemon-off_{digest}", "label": CHOICE_LABELS["daemon-off"], "writes": list(writes)}],
        "skipped": []}


def do_install(args) -> tuple[int, dict]:
    pack, manifest = locate(args)
    target, approved = args.target
    key = manifest["name"]
    origin = crew_origin(args.crew_url)
    key_root = install_root(args.install_root) / key
    key_root.mkdir(parents=True, exist_ok=True)
    had_previous = (key_root / "current").exists()
    try:
        copied = stage(pack, manifest, key_root / "next")
    except (OSError, PackError) as err:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"staging failed: {err}") from err
    # Checked on the staged copy, the bytes crew reads: it is the manifest that chose this install
    # directory and these entries, and (for a plan's choice) the one the plan showed.
    staged = (key_root / "next" / MANIFEST_NAME).read_bytes()
    try:
        same = json.loads(staged) == manifest
    except ValueError:
        same = False
    if not same:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"{pack / MANIFEST_NAME} changed while it was being installed; nothing was installed")
    if approved is not None and plan_digest(staged) != approved:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"{pack / MANIFEST_NAME} changed after the plan the operator approved (its permissions, "
                         "version or entry hash may differ); nothing was installed: plan and approve it again")
    swap(key_root)
    current = key_root / "current"
    try:
        status, body = http_json("POST", f"{origin}/api/v1/editors",
                                 {"packRoot": str(current.resolve()), "enabled": target == "daemon"})
    except (urllib.error.URLError, OSError) as err:
        unswap(key_root, had_previous)
        raise Failure(1, f"no daemon at {origin} ({err}); nothing was installed") from err
    if status >= 400:
        unswap(key_root, had_previous)
        detail = {k: body[k] for k in ("code", "check", "conformance") if k in body}
        raise Failure(1, f"the daemon refused the install (HTTP {status}): {_message(body)}"
                         + (f" — {json.dumps(detail)[:1500]}" if detail else ""))
    record = {"key": key, "version": manifest.get("version"), "source": {"dir": str(pack)}, "files": copied,
              "editors": body.get("editors", []), "enabled": target == "daemon",
              "updated": bool(body.get("updated")), "installedAt": _now()}
    (key_root / "installed.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # crew >= the MCP inspector bridge reports the install-consent grants it wrote (or why it could not).
    grants = {k: body[k] for k in ("granted", "grantError") if k in body}
    return 0, {**record, **grants, "target": target, "path": str(current),
               "conformance": body.get("conformance")}


def do_uninstall(args) -> tuple[int, dict]:
    key = args.uninstall
    if not ID_RE.match(key):
        raise Failure(2, f"invalid pack name {key!r}")
    origin = crew_origin(args.crew_url)
    key_root = install_root(args.install_root) / key
    editors: list[str] = []
    try:
        editors = [str(e.get("id")) for e in editors_of(read_manifest(key_root / "current"))]
    except PackError:
        editors = []
    out: dict = {"key": key, "uninstalled": True, "registry": {}}
    for eid in editors:
        try:
            status, body = http_json("DELETE", f"{origin}/api/v1/editors/{urllib.parse.quote(eid)}")
        except (urllib.error.URLError, OSError) as err:
            raise Failure(1, f"no daemon at {origin} ({err}); nothing was removed") from err
        if status == 404:
            out["registry"][eid] = "absent"
        elif status >= 400:
            raise Failure(1, f"the daemon refused to remove {eid} (HTTP {status}): {_message(body)}; nothing was removed")
        else:
            out["registry"][eid] = "removed"
    out["removed"] = str(key_root) if key_root.exists() else None
    if key_root.exists():
        shutil.rmtree(key_root)
    return 0, out


def consent_refusal(args, env) -> str | None:
    """Inside a governed run (``WICKED_RUN_ID`` set) a live install happens only in the consent-gated
    Tool unit, the one unit the engine hands ``WICKED_CONSENT_CHOICE`` (the operator's approved
    choice). Any other unit (a creator in build, a reviewer) may plan with ``--dry-run`` but never
    installs or uninstalls (E2E finding F-EDIT-1: a creator installed before the gate asked)."""
    if not env.get("WICKED_RUN_ID"):
        return None
    if env.get("WICKED_CONSENT_CHOICE"):
        if args.uninstall or args.target[1] is not None:
            return None
        # A choice with no digest (a plan from before the binding, approved after an upgrade) names no
        # manifest, so it could install permissions nobody was shown.
        return ("refusing to install a consent choice that is not bound to its plan (no _<digest>): the plan "
                "it came from predates this installer. Plan it again so the operator approves what installs.")
    return ("refusing to install inside a governed run outside its consent-gated install step: the operator "
            "approves the install at that gate. Plan it with --dry-run; the install step runs it.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--from-run", action="store_true", help="find the one editor pack under $WICKED_TREE (else the cwd)")
    where.add_argument("--dir", type=Path, help="the pack directory")
    where.add_argument("--uninstall", metavar="NAME", help="unregister and remove an installed editor pack")
    parser.add_argument("--target", type=parse_target, default=("daemon", None),
                        help="daemon (default): installed and on; daemon-off: installed, turned off; "
                             "a plan's choice id (-<digest>) also refuses a pack changed since the plan")
    parser.add_argument("--crew-url", help="the wicked-crew origin (default $WICKED_CREW_URL; no port is assumed)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; print the plan as one JSON line")
    parser.add_argument("--install-root", type=Path, help="default $WICKED_EDITOR_INSTALL_ROOT, else ~/.wicked/editors")
    parser.add_argument("--json", action="store_true", help="print the record as one compact JSON line")
    args = parser.parse_args(argv)
    if args.dry_run:
        if args.uninstall:
            print(json.dumps({"ok": False, "error": "--dry-run plans an install, not --uninstall"}))
            return 2
        try:
            print(json.dumps(do_plan(args)))
            return 0
        except Failure as err:
            sys.stderr.write(f"editor install --dry-run: {err}\n")
            return err.code
    refusal = consent_refusal(args, os.environ)
    if refusal is not None:
        print(json.dumps({"ok": False, "error": refusal}))
        return 2
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
