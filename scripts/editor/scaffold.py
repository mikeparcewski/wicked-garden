#!/usr/bin/env python3
"""Scaffold an artifact editor plugin as a wicked-pack.json spec-2 pack.

    wicked-garden run scripts/editor/scaffold.py --vendor <vendor> --id <vendor>-<name> --title <words>
        --kinds <kind[,kind]> [--permissions <id[,id]>] [--surfaces <file.json>] [--version 0.1.0] --out <dir>

Writes into ``<dir>`` (a repo root or a subdirectory; it may exist, but every file it would write
must be absent — it refuses naming the first collision and writes nothing):

- ``wicked-pack.json``: spec 2 with one ``editors[]`` entry (id, title, version, protocol [1, 2], the
  kinds, sizes inline/pane/full, the protocol-2 ``surfaces`` declaration, each permission with its
  plain-words ``why``, the entry, and the entry's sha256 pinned);
- ``editors/<id>/index.html``: the one self-contained editor file, from the skill's template — the
  wicked.editor/2 plumbing (handshake, port, ping, size, theme, keys, typing; the card, options and
  full-screen surfaces, Simple/Advanced, card actions and host-drawn controls) that also speaks /1 to
  an older host, with a read-only viewer to replace. The same ``surfaces`` JSON is written into the
  manifest and the entry's ``plugin.ready`` (DES-EDITOR-PLUGIN-CONTRACT-001 §5.1: they must agree);
- ``README.md``.

The default permissions are the least an editor that reads and points needs: ``artifact.read``,
``selection.chip`` and ``ui.fullscreen``. Prints one JSON object: the pack path, the files, the
editor's id, version and sha256, and the commands that check it. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pack import (  # noqa: E402
    ID_RE, KIND_RE, MANIFEST_NAME, PERMISSIONS, RESERVED_RE, SEMVER_RE, SIZES, sha256_file,
    valid_topic_pattern, write_manifest,
)
from _surfaces import SurfacesError, parse_surfaces  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "skills" / "editor-scaffold" / "assets" / "pack"
RUN_PLUGIN_ASSETS = ROOT / "skills" / "editor-scaffold" / "assets" / "run-plugin"
DEFAULT_PERMISSIONS = "artifact.read,selection.chip,ui.fullscreen"
DEFAULT_RUN_OBSERVE = [
    {"topic": "wicked.run.session.*", "why": "to track when the run starts and finishes"},
    {"topic": "wicked.run.unit.*", "why": "to list the units that ran in each phase"},
]
TOPIC_REASONS = {
    "wicked.run.phase.*": "to show each phase as it starts and finishes",
    "wicked.run.unit.*": "to list the units that ran in each phase",
    "wicked.run.usage.reported": "to total token and cost usage across the run",
    "wicked.run.gate.*": "to show gate decisions and their outcomes",
    "wicked.run.session.*": "to track when the run starts and finishes",
    "wicked.run.**": "to observe all run lifecycle events for this section",
}
# The default protocol-2 declaration (DES-EDITOR-PLUGIN-CONTRACT-001 §5.2): an interactive card that reports
# its height with a plugin action and the host's "ask about it"; one plugin-rendered options tab and one
# host-drawn controls tab; full screen with Simple/Advanced. The template implements every part of it.
DEFAULT_SURFACES = {
    "card": {
        "interactive": True,
        "aspect": "auto",
        "actions": [
            {"id": "next", "label": "Next part", "verb": "plugin"},
            {"id": "ask", "label": "Ask about it", "verb": "host:ask"},
        ],
    },
    "options": {
        "tabs": [
            {"id": "parts", "label": "Parts", "render": "plugin"},
            {"id": "view", "label": "View", "render": "controls", "controls": [
                {"id": "density", "label": "Density", "type": "segmented",
                 "options": [{"id": "roomy", "label": "Roomy"}, {"id": "compact", "label": "Compact"}]},
                {"id": "numbers", "label": "Show numbers", "type": "toggle"},
            ]},
        ],
    },
    "full": {"modes": ["simple", "advanced"], "default": "simple"},
}


def _fail(message: str) -> int:
    sys.stderr.write(f"editor scaffold: {message}\n")
    return 2


def _stamp(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def _scaffold_run_plugin(args, vendor: str, plugin_id: str, title: str) -> int:
    if len(title) > 40 or any(c in title for c in ("<", ">", "\r", "\n")):
        return _fail("--title for a run plugin must be 1-40 characters with no '<', '>', CR or LF")
    if args.observe is None:
        observe = [dict(x) for x in DEFAULT_RUN_OBSERVE]
    else:
        topics = [t.strip() for t in args.observe.split(",") if t.strip()]
        if not (1 <= len(topics) <= 16):
            return _fail("--observe must list 1-16 topic patterns")
        bad = [t for t in topics if not valid_topic_pattern(t)]
        if bad:
            return _fail(f"invalid observe topic patterns {bad}: each must match wicked.run.* (§C2)")
        if len(set(topics)) != len(topics):
            return _fail(f"duplicate observe topic patterns in {topics}")
        observe = [{"topic": t, "why": TOPIC_REASONS.get(t, f"to observe {t} events for this section")} for t in topics]

    out: Path = args.out
    if out.exists() and not out.is_dir():
        return _fail(f"{out} exists and is not a directory")
    entry_rel = Path("plugins") / plugin_id / "index.html"
    samples_rel = Path("samples") / "events.ndjson"
    files = [
        (RUN_PLUGIN_ASSETS / "plugins" / "__PLUGIN_ID__" / "index.html", entry_rel),
        (RUN_PLUGIN_ASSETS / "samples" / "events.ndjson", samples_rel),
        (RUN_PLUGIN_ASSETS / "README.md", Path("README.md")),
    ]
    targets = [Path(MANIFEST_NAME), *(rel for _, rel in files)]
    for rel in targets:
        if (out / rel).exists() or (out / rel).is_symlink():
            return _fail(f"{out / rel} exists; refusing to overwrite — pick another --out")
    for src, _ in files:
        if not src.is_file():
            return _fail(f"template missing: {src}")

    panel_id = plugin_id[:32].rstrip("-")
    if not panel_id or not panel_id[0].isalpha():
        panel_id = ("p-" + panel_id)[:32].rstrip("-") or "details"
    panels = [{
        "slot": "run.details",
        "id": panel_id,
        "title": title,
        "instances": "single",
        "order": 50,
        "defaultOpen": "while-live",
        "summary": "plugin",
    }]
    values = {
        "__PLUGIN_ID__": plugin_id,
        "__PLUGIN_VERSION__": args.version,
        "__PLUGIN_TITLE__": title,
        "__PANEL_ID__": panel_id,
        "__PLUGIN_TOPICS__": ", ".join(o["topic"] for o in observe),
    }
    for src, rel in files:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(_stamp(src.read_text(encoding="utf-8"), values))
    sha = sha256_file(out / entry_rel)
    plugin_entry = {
        "id": plugin_id,
        "title": title,
        "version": args.version,
        "protocol": [3],
        "inline": "run-thread",
        "entry": entry_rel.as_posix(),
        "sha256": sha,
        "description": f"{title}: a run plugin for wicked-studio."[:160],
        "observe": observe,
        "panels": panels,
        "samples": samples_rel.as_posix(),
    }
    manifest = {
        "spec": 2,
        "name": plugin_id,
        "vendor": vendor,
        "version": args.version,
        "description": f"{title}: a run plugin for wicked-studio."[:160],
        "plugins": [plugin_entry],
    }
    write_manifest(out, manifest)
    print(json.dumps({
        "ok": True,
        "pack": str(out),
        "files": [p.as_posix() for p in targets],
        "plugin": {
            "id": plugin_id,
            "version": args.version,
            "sha256": sha,
            "protocol": [3],
            "inline": "run-thread",
            "observe": observe,
            "panels": panels,
            "samples": samples_rel.as_posix(),
        },
        "pin": f'wicked-garden run scripts/editor/pin.py "{out}"',
        "check": f'npx wicked-garden pack check "{out}"',
        "conformance": f'wicked-garden run scripts/editor/conformance.py --pack "{out}" --json',
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", choices=("editor", "run-plugin"), default="editor",
                        help="pack kind: editor (default) or run-plugin")
    parser.add_argument("--vendor", required=True, help="your vendor name (not wicked*)")
    parser.add_argument("--id", required=True, help="editor or plugin id, '<vendor>-<name>'")
    parser.add_argument("--title", required=True, help="the editor's or plugin's name in plain words")
    parser.add_argument("--kinds", default=None, help="artifact kinds it opens, comma-separated (for --kind editor)")
    parser.add_argument("--observe", default=None,
                        help="comma-separated wicked.run.* topic patterns (for --kind run-plugin)")
    parser.add_argument("--permissions", default=DEFAULT_PERMISSIONS, help=f"default {DEFAULT_PERMISSIONS}")
    parser.add_argument("--surfaces", type=Path, default=None,
                        help="a JSON file with the protocol-2 surfaces declaration (default: card, options, full)")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    vendor, editor_id, title = args.vendor.strip(), args.id.strip(), args.title.strip()
    if not ID_RE.match(vendor) or RESERVED_RE.match(vendor):
        return _fail(f"invalid vendor {vendor!r}: kebab-case, and 'wicked' is reserved for first-party editors")
    if not ID_RE.match(editor_id) or len(editor_id) > 64 or not editor_id.startswith(f"{vendor}-"):
        return _fail(f"invalid id {editor_id!r}: kebab-case, at most 64 characters, starting with '{vendor}-'")
    if not title:
        return _fail("--title is empty")
    if not SEMVER_RE.match(args.version):
        return _fail(f"invalid version {args.version!r}: use semver, e.g. 0.1.0")

    if args.kind == "run-plugin":
        return _scaffold_run_plugin(args, vendor, editor_id, title)

    if args.kinds is None:
        return _fail("--kinds is required for an artifact editor")
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    bad_kinds = [k for k in kinds if not KIND_RE.match(k)]
    if not kinds or bad_kinds:
        return _fail(f"invalid kinds {bad_kinds or args.kinds!r}: each matches ^[a-z][a-z0-9-]{{1,40}}$")
    perms = [p.strip() for p in args.permissions.split(",") if p.strip()]
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        return _fail(f"unknown permissions {unknown}: choose from {', '.join(PERMISSIONS)}")
    if "network.media" in perms:
        return _fail("network.media is not offered to a pack editor: its frame has no network (img/font from data: and blob: only)")

    surfaces = DEFAULT_SURFACES
    if args.surfaces is not None:
        try:
            surfaces = json.loads(args.surfaces.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _fail(f"--surfaces {args.surfaces}: not readable JSON ({exc})")
    try:
        parse_surfaces(surfaces)
    except SurfacesError as exc:
        return _fail(f"--surfaces refused: {exc}")
    if any(a.get("verb") == "host:export" for a in surfaces["card"].get("actions", [])) and "artifact.export" not in perms:
        return _fail("a host:export card action needs the artifact.export permission")

    out: Path = args.out
    if out.exists() and not out.is_dir():
        return _fail(f"{out} exists and is not a directory")
    entry_rel = Path("editors") / editor_id / "index.html"
    files = [(ASSETS / "editors" / "__EDITOR_ID__" / "index.html", entry_rel), (ASSETS / "README.md", Path("README.md"))]
    targets = [Path(MANIFEST_NAME), *(rel for _, rel in files)]
    for rel in targets:  # refuse before writing anything
        if (out / rel).exists() or (out / rel).is_symlink():
            return _fail(f"{out / rel} exists; refusing to overwrite — pick another --out")
    for src, _ in files:
        if not src.is_file():
            return _fail(f"template missing: {src}")

    values = {"__EDITOR_ID__": editor_id, "__EDITOR_VERSION__": args.version, "__EDITOR_TITLE__": title,
              "__EDITOR_KINDS__": ", ".join(kinds),
              # The same JSON as the manifest's `surfaces`; JSON is a JS expression, and `</` is escaped so the
              # declaration can never close the inline <script>.
              "__EDITOR_SURFACES__": json.dumps(surfaces, indent=2).replace("</", "<\\/")}
    for src, rel in files:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(_stamp(src.read_text(encoding="utf-8"), values))
    sha = sha256_file(out / entry_rel)
    manifest = {
        "spec": 2,
        "name": editor_id,
        "vendor": vendor,
        "version": args.version,
        "description": f"{title}: an artifact editor plugin for wicked-studio.",
        "editors": [{
            "id": editor_id,
            "title": title,
            "version": args.version,
            "protocol": [1, 2],
            "kinds": kinds,
            "entry": entry_rel.as_posix(),
            "sha256": sha,
            "sizes": list(SIZES),
            "surfaces": surfaces,
            "permissions": [{"id": p, "why": PERMISSIONS[p]} for p in perms],
        }],
    }
    write_manifest(out, manifest)
    print(json.dumps({
        "ok": True,
        "pack": str(out),
        "files": [p.as_posix() for p in targets],
        "editor": {"id": editor_id, "version": args.version, "sha256": sha, "kinds": kinds, "permissions": perms,
                   "protocol": [1, 2], "surfaces": sorted(k for k in ("card", "options", "full") if k in surfaces)},
        "pin": f'wicked-garden run scripts/editor/pin.py "{out}"',
        "check": f'npx wicked-garden pack check "{out}"',
        "conformance": f'wicked-garden run scripts/editor/conformance.py --pack "{out}" --json',
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
