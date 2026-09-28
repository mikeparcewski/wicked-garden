#!/usr/bin/env python3
"""Scaffold an MCP server from a wicked-garden-mcp-scaffold template.

    wicked-garden run scripts/mcp/scaffold.py --name <server-name> --lang node|python --out <dir>

Copies the chosen template (``skills/mcp-scaffold/assets/<lang>/``) into ``<dir>``, stamping
the server name. It never overwrites: an existing target file is an error. Prints one JSON
object on stdout: the written path, the command that runs the server, and the probe command
that proves it answers ``initialize`` and ``tools/list``. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "skills" / "mcp-scaffold" / "assets"
PLACEHOLDER = "__SERVER_NAME__"
# The registry key and the `mcp:<server>/<tool>` subject segment: lowercase, no separators
# that the subject grammar uses, at most 64 characters.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TEMPLATES = {
    "node": ("server.mjs", "node"),
    "python": ("server.py", "python3"),
}


def _fail(message: str) -> int:
    sys.stderr.write(f"mcp scaffold: {message}\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="server name: lowercase, digits, '-'; <= 64")
    parser.add_argument("--lang", required=True, choices=sorted(TEMPLATES))
    parser.add_argument("--out", required=True, type=Path, help="directory to write into")
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        return _fail(f"invalid name {args.name!r}: use lowercase letters, digits and '-', "
                     "starting with a letter, at most 64 characters")
    filename, interpreter = TEMPLATES[args.lang]
    source = ASSETS / args.lang / filename
    if not source.is_file():
        return _fail(f"template missing: {source}")
    target = args.out / filename
    if target.exists():
        return _fail(f"{target} exists; refusing to overwrite — pick another --out")

    text = source.read_text(encoding="utf-8").replace(PLACEHOLDER, args.name)
    args.out.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    target.chmod(0o755)

    run = f'{interpreter} "{target}"'
    print(json.dumps({
        "ok": True,
        "name": args.name,
        "lang": args.lang,
        "path": str(target),
        "run": run,
        "probe": f"wicked-garden run scripts/mcp/probe.py -- {run}",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
