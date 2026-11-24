#!/usr/bin/env python3
"""The ``install`` action: install or update a built editor plugin into a wicked-crew daemon's editors.

    wicked-garden run scripts/editor/install.py (--from-run | --dir <pack dir>) [--target daemon|daemon-off]
        [--dry-run] [--crew-url <origin>] [--install-root <dir>] [--json]
    wicked-garden run scripts/editor/install.py --uninstall <pack name> [--crew-url <origin>] [--install-root <dir>]

An editor plugin is a ``wicked-pack.json`` spec-2 pack with ``editors[]`` (scaffold it with
``scripts/editor/scaffold.py``). Install, idempotent by the pack's ``name``:

1. **Locate**: ``--from-run`` finds the one spec-2 ``wicked-pack.json`` with editors under
   the run's worktree (the cwd; ``$WICKED_TREE`` when it names a directory), outside node_modules/.git/dist; ``--dir`` names it.
2. **Stage** into ``<root>/<name>/next/`` (root: ``--install-root``, ``$WICKED_EDITOR_INSTALL_ROOT``,
   else ``$WICKED_HOME/editors``, else ``~/.wicked/editors``, a program-owned place; an empty variable counts
   as unset): ``wicked-pack.json``, every editor's entry
   file and its accepted declared card images at their manifest paths, the README, and (a pack that
   also ships skills or blocks, wicked-crew#1703) every entry under its ``skills_dir`` and each
   block's ``preset`` file, at their manifest paths. Malformed cosmetic images are skipped, as in pack
   check (PK089); they never refuse an install. A link anywhere in the skills tree, or a preset outside
   the pack, refuses it. Nothing else of the tree is copied (an editor is ONE self-contained file).
3. **Swap** ``current/`` → ``previous/``, ``next/`` → ``current/``.
4. **Register** with wicked-crew: ``POST /api/v1/editors {packRoot: <root>/<name>/current, enabled}``,
   plus ``approve: {skills: [<skill dir>…], blocks: [<block id>…]}`` for a pack with skills or blocks:
   the lists the operator approved, which crew adds (each skill as ``wicked-garden-<dir>``, each block's
   preset as a workflow preset) in the same install, or refuses with nothing installed.
   The daemon re-runs garden's ``pack check`` and this skill's **conformance run** against the staged
   copy itself, refuses on any failure (fail closed: no headless browser is a refusal), pins each
   entry's sha256 and records it in its editor registry. A refusal swaps ``previous/`` back (or
   removes ``current/`` on a first install) and exits 1.
5. **Record** ``<root>/<name>/installed.json`` and print it.

**Targets** (the consent gate's choices): ``daemon`` (the default) installs it turned on — it opens
the artifact kinds it claims; ``daemon-off`` installs it turned off, to switch on in studio Settings
→ Developer → Editor plugins. Both write the same places, all program-owned. ``--dry-run`` writes
nothing and prints ONE JSON line, the plan: ``{"dry_run": true, "key", "choices": [{"id", "label",
"default"?, "writes": [{"path", "what", "operator_owned"}]}], "skipped": [],
"asks"?: [{"editor", "permission", "why"}], "skills"?: [{"dir", "name", "installs_as"}],
"blocks"?: [{"id", "label", "produces_kind", "phases", "skills"}]}``; each skill and block is also a
write row on both choices. An editor that
declares ``mcp.session`` adds one more write to both choices, on the ``EDITOR-GRANTS`` steering rule:
"This plugin can start and talk to MCP servers", with the exact per-build token the install writes
(``editor:<id>@<version>#<sha256>/mcp.session``). The install consent is that grant; no rule allows it.
``asks`` lists the other declared permissions, the ones a person allows later in Plugins; a permission the
install itself grants (``INSTALL_GRANTED``) is a write row above and never an ask.

**The approval is bound to the plan.** Each choice id carries a digest of the planned
``wicked-pack.json`` bytes (and, for a pack with skills or blocks, of every skill and preset file it
stages), the same bytes the plan's lines were read from (``daemon_<d>``,
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
    INSTALL_GRANTED, ID_RE, MANIFEST_NAME, PackError, editor_card_fields, entry_path, find_editor_packs,
    pack_entries_of, plugin_extra_paths, read_manifest,
)

# A choice id: the target, optionally bound to the plan by the digest of the manifest it showed. The id
# rides the consent gate's answer token and an env var: [A-Za-z0-9_-], at most 32 (core consent_plan.rs).
DIGEST_CHARS = 21
TARGET_RE = re.compile(r"^(daemon|daemon-off)(?:_([A-Za-z0-9_-]{%d}))?$" % DIGEST_CHARS)
CHOICE_LABELS = {"daemon": "Install for this daemon", "daemon-off": "Install, turned off"}
# The daemon re-runs the conformance cases (a headless browser, one ping period per editor) before it answers.
HTTP_TIMEOUT_S = 300
PLAN_ASKS_CAP = 64
PLAN_ID_CHARS = 200
PLAN_WHY_CHARS = 300


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
    """``--install-root``, else ``$WICKED_EDITOR_INSTALL_ROOT``, else the daemon's state home: ``$WICKED_HOME/editors``,
    else ``~/.wicked/editors``. An empty variable counts as unset (garden#1532: a daemon on a scratch home staged
    editors in the live ``~/.wicked``)."""
    if flag is not None:
        return flag
    env = os.environ.get("WICKED_EDITOR_INSTALL_ROOT")
    if env:
        return Path(env)
    home = os.environ.get("WICKED_HOME")
    return Path(os.path.abspath((Path(home) if home else Path.home() / ".wicked") / "editors"))


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

def run_tree() -> Path:
    """The run's worktree for ``--from-run``. The engine runs an install Tool phase IN the worktree and hands
    ``$WICKED_TREE`` as that worktree's git tree id (wicked-core#776), never a path; reading the id as a path found
    no pack in any real run. A ``$WICKED_TREE`` that names a directory is still honoured, else the cwd."""
    named = os.environ.get("WICKED_TREE")
    return Path(named) if named and Path(named).is_dir() else Path.cwd()


def locate(args) -> tuple[Path, dict]:
    if args.dir is not None:
        pack = args.dir
    elif args.from_run:
        tree = run_tree()
        found = find_editor_packs(tree)
        if len(found) != 1:
            names = ", ".join(str(p) for p in found) or "none"
            raise Failure(2, f"--from-run needs exactly one editor pack ({MANIFEST_NAME} spec 2 with editors) under "
                             f"{tree}; found {len(found)} ({names}) — pass --dir <pack dir>")
        pack = found[0]
    else:
        raise Failure(2, "pass --from-run or --dir <pack dir>")
    try:
        manifest = read_manifest(pack)
        editors, plugins = pack_entries_of(manifest)
        for e in editors:
            entry_path(pack, e, kind="editor")
        for p in plugins:
            entry_path(pack, p, kind="plugin")
            plugin_extra_paths(pack, p)
        pack_extra_files(pack, manifest)
    except PackError as err:
        raise Failure(2, str(err)) from err
    name = manifest.get("name")
    if not isinstance(name, str) or not ID_RE.match(name) or len(name) > 64:
        raise Failure(2, f"{pack / MANIFEST_NAME}: invalid pack name {name!r}")
    return pack, manifest


# ── the pack's skills and block presets (wicked-crew#1703) ────────────────────────────────

SKILL_NAME_RE = re.compile(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE)


def _inside(pack: Path, rel: object, what: str) -> Path:
    """``rel`` as a plain relative path inside ``pack`` (POSIX separators, no drive, no ``..`` escape)."""
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) \
            or "\\" in rel:
        raise PackError(f"{what} must be a relative path inside the pack (got {rel!r})")
    path = (pack / Path(*rel.split("/"))).resolve()
    if path != pack.resolve() and pack.resolve() not in path.parents:
        raise PackError(f"{what} must be a relative path inside the pack (got {rel!r})")
    return path


def pack_skills(pack: Path, manifest: dict) -> tuple[str, list[str]]:
    """The skills dir and its entries as crew lists them: every non-hidden name under it, sorted."""
    skills_dir = manifest.get("skills_dir", "skills")
    base = _inside(pack, skills_dir, "skills_dir")
    if not base.is_dir():
        return skills_dir, []
    return skills_dir, sorted(n for n in os.listdir(base) if not n.startswith("."))


def pack_blocks(manifest: dict) -> list[dict]:
    blocks = manifest.get("blocks")
    return [b for b in blocks if isinstance(b, dict)] if isinstance(blocks, list) else []


def pack_extra_files(pack: Path, manifest: dict) -> list[tuple[str, Path]]:
    """Every skill file and block preset an install stages, as ``(manifest-relative path, source)``, sorted.
    A link in the skills tree or a preset outside the pack refuses (a link could stage a file from anywhere)."""
    files: dict[str, Path] = {}
    skills_dir, names = pack_skills(pack, manifest)
    for name in names:
        top = pack / Path(*skills_dir.split("/")) / name
        if top.is_symlink():
            raise PackError(f"{skills_dir}/{name} is a link; a pack's skills are staged as plain files only")
        if top.is_file():
            files[f"{skills_dir}/{name}"] = top
            continue
        for here, dirs, leaves in os.walk(top):
            for entry in sorted(dirs + leaves):
                path = Path(here) / entry
                rel = path.relative_to(pack).as_posix()
                if path.is_symlink():
                    raise PackError(f"{rel} is a link; a pack's skills are staged as plain files only")
                if path.is_file():
                    files[rel] = path
    for block in pack_blocks(manifest):
        preset = block.get("preset")
        path = _inside(pack, preset, f"block {block.get('id')!r} preset")
        if path.is_symlink() or not path.is_file():
            raise PackError(f"block {block.get('id')!r} preset {preset!r} is not a plain file in the pack")
        files[preset] = path
    return sorted(files.items())


def _skill_name(path: Path) -> str:
    """A SKILL.md's frontmatter ``name`` ('' when it has none)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    head = text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else ""
    m = SKILL_NAME_RE.search(head)
    return m.group(1).strip() if m else ""


def _preset_phases(path: Path) -> list[str]:
    try:
        preset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    phases = preset.get("phases") if isinstance(preset, dict) else None
    return [p for p in phases if isinstance(p, str)] if isinstance(phases, list) else []


def approve_lists(pack: Path, manifest: dict) -> dict | None:
    """``approve`` for the register call: the skill dirs and block ids the plan listed (None: none)."""
    _, skills = pack_skills(pack, manifest)
    blocks = [str(b.get("id")) for b in pack_blocks(manifest)]
    return {"skills": skills, "blocks": blocks} if skills or blocks else None


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
    editors, plugins = pack_entries_of(manifest)
    for e in editors:
        source = entry_path(pack, e, kind="editor")  # refuses an entry that is not a plain relative path inside the pack
        dest = (next_dir / Path(*e["entry"].split("/"))).resolve()
        if root not in dest.parents:
            raise PackError(f"editor {e.get('id')!r}: entry {e['entry']!r} would stage outside {next_dir}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(e["entry"])
        images, _ = editor_card_fields(pack, e)
        for rel_str, body in images:
            extra_dest = next_dir / Path(*rel_str.split("/"))
            extra_dest.parent.mkdir(parents=True, exist_ok=True)
            extra_dest.write_bytes(body)
            if rel_str not in copied:
                copied.append(rel_str)
    for p in plugins:
        source = entry_path(pack, p, kind="plugin")
        dest = (next_dir / Path(*p["entry"].split("/"))).resolve()
        if root not in dest.parents:
            raise PackError(f"plugin {p.get('id')!r}: entry {p['entry']!r} would stage outside {next_dir}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(p["entry"])
        for rel_str, extra_src in plugin_extra_paths(pack, p):
            extra_dest = (next_dir / Path(*rel_str.split("/"))).resolve()
            if root not in extra_dest.parents:
                raise PackError(f"plugin {p.get('id')!r}: {rel_str!r} would stage outside {next_dir}")
            extra_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(extra_src, extra_dest)
            if rel_str not in copied:
                copied.append(rel_str)
    for rel_str, source in pack_extra_files(pack, manifest):
        dest = (next_dir / Path(*rel_str.split("/"))).resolve()
        if root not in dest.parents:
            raise PackError(f"{rel_str!r} would stage outside {next_dir}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if rel_str not in copied:
            copied.append(rel_str)
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
    """One write per editor permission or run-plugin observe topic the install consent grants: crew writes
    that build's token into the ``EDITOR-GRANTS`` steering rule when the operator approves
    (DES-MCP-INSPECTOR-001 §6; CONTRACT-CS7 §C3)."""
    rows = []
    editors, plugins = pack_entries_of(manifest)
    for e in editors:
        declared = {p.get("id") for p in e.get("permissions", []) if isinstance(p, dict)}
        for perm, line in INSTALL_GRANTED.items():
            if perm in declared:
                token = f"editor:{e.get('id')}@{e.get('version')}#{e.get('sha256')}/{perm}"
                rows.append({"path": "EDITOR-GRANTS", "operator_owned": False,
                             "what": f"{line}: {e.get('id')} is granted {token} (steering; revoke it there)"})
    for p in plugins:
        pid, pver, psha = p.get("id"), p.get("version"), p.get("sha256")
        for obs in p.get("observe", []) if isinstance(p.get("observe"), list) else []:
            if not isinstance(obs, dict):
                continue
            topic, why = obs.get("topic"), obs.get("why")
            token = f"plugin:{pid}@{pver}#{psha}/observe:{topic}"
            rows.append({"path": "EDITOR-GRANTS", "operator_owned": False,
                         "what": f"Observe {topic} ({why}): {pid} is granted {token}"})
    return rows


def permission_asks(entries: list[dict]) -> list[dict]:
    """Bounded, informational permission rows in manifest order; these grant nothing. A permission the install
    consent itself grants (``INSTALL_GRANTED``, e.g. ``mcp.session``) is left out: it has no Plugins switch, and
    the plan already shows it as an ``EDITOR-GRANTS`` write row (``install_grants``)."""
    rows = []
    for entry in entries:
        permissions = entry.get("permissions") if isinstance(entry, dict) else None
        for permission in permissions if isinstance(permissions, list) else []:
            if not isinstance(permission, dict) or not isinstance(permission.get("id"), str):
                continue
            if permission["id"] in INSTALL_GRANTED:
                continue
            why = permission.get("why", permission.get("reason", ""))
            rows.append({"editor": str(entry.get("id", ""))[:PLAN_ID_CHARS],
                         "permission": permission["id"][:PLAN_ID_CHARS],
                         "why": why[:PLAN_WHY_CHARS] if isinstance(why, str) else ""})
            if len(rows) == PLAN_ASKS_CAP:
                return rows
    return rows


def plan_digest(raw: bytes, extras: list[tuple[str, bytes]] = ()) -> str:
    """The manifest bytes' sha256 as base64url, cut to fit a choice id: what the plan showed (permissions,
    version, entry hashes). A pack with skills or blocks also binds each staged skill and preset file
    (its manifest path and bytes, sorted), so a file changed after the plan refuses the bound install.
    An editor-only pack has no extras and keeps the manifest-only digest."""
    h = hashlib.sha256(raw)
    for rel, body in sorted(extras):
        h.update(b"\0" + rel.encode("utf-8") + b"\0" + str(len(body)).encode("ascii") + b"\0" + body)
    return base64.urlsafe_b64encode(h.digest()).decode("ascii")[:DIGEST_CHARS]


def _extras(base: Path, manifest: dict) -> list[tuple[str, bytes]]:
    return [(rel, path.read_bytes()) for rel, path in pack_extra_files(base, manifest)]


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
    editors, plugins = pack_entries_of(manifest)
    writes = [{"path": str(key_root / "current"), "what": "the staged copy of the editor pack, including accepted declared card images (program-owned)",
               "operator_owned": False}]
    if (key_root / "current").exists():
        writes.append({"path": str(key_root / "previous"), "what": "the copy installed now, kept for a roll-back",
                       "operator_owned": False})
    writes += [{"path": str(key_root / "installed.json"), "what": "the install record", "operator_owned": False},
               {"path": f"{origin}/api/v1/editors", "what": "wicked-crew editor registry entry "
                f"({', '.join(str(x.get('id')) for x in editors + plugins)}; daemon-editors.json in its state home)",
                "operator_owned": False}]
    writes += install_grants(manifest)
    try:
        extras = _extras(pack, manifest)
    except (OSError, PackError) as err:
        raise Failure(2, f"{pack}: {err}") from err
    skills_dir, skill_dirs = pack_skills(pack, manifest)
    skills = [{"dir": d, "name": _skill_name(pack / Path(*skills_dir.split("/")) / d / "SKILL.md"),
               "installs_as": f"wicked-garden-{d}"} for d in skill_dirs]
    blocks = [{"id": b.get("id"), "label": b.get("label"), "produces_kind": b.get("produces_kind"),
               "phases": _preset_phases(_inside(pack, b.get("preset"), "preset")),
               "skills": [s for s in b.get("skills", []) if isinstance(s, str)] if isinstance(b.get("skills"), list) else []}
              for b in pack_blocks(manifest)]
    for s in skills:
        writes.append({"path": f"{origin}/api/v1/editors", "operator_owned": False,
                       "what": f"skill {s['dir']} into the daemon's skills root as {s['installs_as']} "
                               f"(from pack {key}; every seat gets it)"})
    for b in blocks:
        writes.append({"path": f"{origin}/api/v1/editors", "operator_owned": False,
                       "what": f"workflow preset {b['id']} ({b['label']}): phases {', '.join(b['phases'])} "
                               f"(from pack {key})"})
    digest = plan_digest(raw, extras)
    plan: dict = {"dry_run": True, "key": key, "choices": [
        {"id": f"daemon_{digest}", "label": CHOICE_LABELS["daemon"], "default": True, "writes": writes},
        {"id": f"daemon-off_{digest}", "label": CHOICE_LABELS["daemon-off"], "writes": list(writes)}],
        "skipped": []}
    asks = permission_asks(editors + plugins)
    if asks:
        plan["asks"] = asks
    if skills:
        plan["skills"] = skills
    if blocks:
        plan["blocks"] = blocks
    if plugins:
        plan["plugins"] = [
            {
                "id": p.get("id"),
                "version": p.get("version"),
                "observe": [
                    {"topic": o.get("topic"), "why": o.get("why")}
                    for o in (p.get("observe") if isinstance(p.get("observe"), list) else [])
                    if isinstance(o, dict)
                ],
            }
            for p in plugins
        ]
    return plan


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
    try:
        staged_extras = _extras(key_root / "next", manifest)
    except (OSError, PackError) as err:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"the staged copy could not be read back ({err}); nothing was installed") from err
    if approved is not None and plan_digest(staged, staged_extras) != approved:
        shutil.rmtree(key_root / "next", ignore_errors=True)
        raise Failure(1, f"{pack / MANIFEST_NAME} changed after the plan the operator approved (its permissions, "
                         "version, entry hash, skills or block presets may differ); nothing was installed: plan "
                         "and approve it again")
    swap(key_root)
    current = key_root / "current"
    try:
        request = {"packRoot": str(current.resolve()), "enabled": target == "daemon"}
        approve = approve_lists(current, manifest)
        if approve is not None:
            request["approve"] = approve  # the skills and blocks the plan listed (wicked-crew#1703)
        status, body = http_json("POST", f"{origin}/api/v1/editors", request)
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
        ed, pl = pack_entries_of(read_manifest(key_root / "current"))
        editors = [str(e.get("id")) for e in ed + pl]
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
    where.add_argument("--from-run", action="store_true", help="find the one editor pack in the run's worktree (the cwd, or $WICKED_TREE when it names a directory)")
    where.add_argument("--dir", type=Path, help="the pack directory")
    where.add_argument("--uninstall", metavar="NAME", help="unregister and remove an installed editor pack")
    parser.add_argument("--target", type=parse_target, default=("daemon", None),
                        help="daemon (default): installed and on; daemon-off: installed, turned off; "
                             "a plan's choice id (-<digest>) also refuses a pack changed since the plan")
    parser.add_argument("--crew-url", help="the wicked-crew origin (default $WICKED_CREW_URL; no port is assumed)")
    parser.add_argument("--dry-run", "--plan", dest="dry_run", action="store_true",
                        help="write nothing; print the plan as one JSON line")
    parser.add_argument("--install-root", type=Path, help="default $WICKED_EDITOR_INSTALL_ROOT, else $WICKED_HOME/editors, else ~/.wicked/editors")
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
