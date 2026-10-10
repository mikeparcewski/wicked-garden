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
"default"?, "writes": [{"path", "what", "operator_owned"}]}], "skipped": []}``.

**Daemon origin**: ``--crew-url``, else ``$WICKED_CREW_URL`` (crew sets it for every governed unit).
There is no port default. Exit 0 installed, 1 a staging or registry failure, 2 bad arguments.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pack import ID_RE, MANIFEST_NAME, PackError, editors_of, entry_path, read_manifest  # noqa: E402

SKIP_DIRS = {"node_modules", "dist", ".git"}
TARGETS = ("daemon", "daemon-off")
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
    for e in editors_of(manifest):
        rel = Path(e["entry"])
        (next_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry_path(pack, e), next_dir / rel)
        copied.append(rel.as_posix())
    if (pack / "README.md").is_file():
        shutil.copy2(pack / "README.md", next_dir / "README.md")
        copied.append("README.md")
    return copied


def swap(key_root: Path) -> None:
    current, previous, nxt = key_root / "current", key_root / "previous", key_root / "next"
    if current.exists():
        if previous.exists():
            shutil.rmtree(previous)
        current.rename(previous)
    nxt.rename(current)


def unswap(key_root: Path, had_previous_install: bool) -> None:
    current, previous = key_root / "current", key_root / "previous"
    if current.exists():
        shutil.rmtree(current)
    if had_previous_install and previous.exists():
        previous.rename(current)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ── the flows ──────────────────────────────────────────────────────────────────────────────

def do_plan(args) -> dict:
    pack, manifest = locate(args)
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
    return {"dry_run": True, "key": key, "choices": [
        {"id": "daemon", "label": CHOICE_LABELS["daemon"], "default": True, "writes": writes},
        {"id": "daemon-off", "label": CHOICE_LABELS["daemon-off"], "writes": list(writes)}],
        "skipped": []}


def do_install(args) -> tuple[int, dict]:
    pack, manifest = locate(args)
    key = manifest["name"]
    origin = crew_origin(args.crew_url)
    key_root = install_root(args.install_root) / key
    key_root.mkdir(parents=True, exist_ok=True)
    had_previous = (key_root / "current").exists()
    try:
        copied = stage(pack, manifest, key_root / "next")
    except OSError as err:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"staging failed: {err}") from err
    swap(key_root)
    current = key_root / "current"
    try:
        status, body = http_json("POST", f"{origin}/api/v1/editors",
                                 {"packRoot": str(current.resolve()), "enabled": args.target == "daemon"})
    except (urllib.error.URLError, OSError) as err:
        unswap(key_root, had_previous)
        raise Failure(1, f"no daemon at {origin} ({err}); nothing was installed") from err
    if status >= 400:
        unswap(key_root, had_previous)
        detail = {k: body[k] for k in ("code", "check", "conformance") if k in body}
        raise Failure(1, f"the daemon refused the install (HTTP {status}): {_message(body)}"
                         + (f" — {json.dumps(detail)[:1500]}" if detail else ""))
    record = {"key": key, "version": manifest.get("version"), "source": {"dir": str(pack)}, "files": copied,
              "editors": body.get("editors", []), "enabled": args.target == "daemon",
              "updated": bool(body.get("updated")), "installedAt": _now()}
    (key_root / "installed.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0, {**record, "target": args.target, "path": str(current),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--from-run", action="store_true", help="find the one editor pack under $WICKED_TREE (else the cwd)")
    where.add_argument("--dir", type=Path, help="the pack directory")
    where.add_argument("--uninstall", metavar="NAME", help="unregister and remove an installed editor pack")
    parser.add_argument("--target", choices=TARGETS, default="daemon",
                        help="daemon (default): installed and on; daemon-off: installed, turned off")
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
