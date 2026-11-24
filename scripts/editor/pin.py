#!/usr/bin/env python3
"""Re-pin every editor entry's sha256 in a pack's wicked-pack.json after the entry changed.

    wicked-garden run scripts/editor/pin.py <pack dir>

The manifest pins the full sha256 of each editor's one entry file; the host refuses a bundle whose
bytes no longer match, and a grant is keyed by that hash, so every edit of an entry needs a re-pin.
Rewrites only the ``sha256`` fields; prints one JSON object ``{ok, pack, editors: [{id, sha256,
changed}]}``. Exit 0 pinned, 2 when the pack cannot be read. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pack import PackError, entry_path, pack_entries_of, read_manifest, sha256_file, write_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pack", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = read_manifest(args.pack)
        editors, plugins = pack_entries_of(manifest)
        out_ed = []
        for editor in editors:
            sha = sha256_file(entry_path(args.pack, editor, kind="editor"))
            out_ed.append({"id": editor.get("id"), "sha256": sha, "changed": editor.get("sha256") != sha})
            editor["sha256"] = sha
        out_pl = []
        for plugin in plugins:
            sha = sha256_file(entry_path(args.pack, plugin, kind="plugin"))
            out_pl.append({"id": plugin.get("id"), "sha256": sha, "changed": plugin.get("sha256") != sha})
            plugin["sha256"] = sha
    except PackError as exc:
        sys.stderr.write(f"editor pin: {exc}\n")
        return 2
    if any(e["changed"] for e in out_ed + out_pl):
        write_manifest(args.pack, manifest)
    res: dict = {"ok": True, "pack": str(args.pack), "editors": out_ed}
    if out_pl:
        res["plugins"] = out_pl
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
