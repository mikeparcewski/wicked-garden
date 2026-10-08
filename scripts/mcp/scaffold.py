#!/usr/bin/env python3
"""Scaffold an MCP server from a wicked-garden-mcp-scaffold template.

    wicked-garden run scripts/mcp/scaffold.py --name <server-name> [--lang typescript|node|python] --out <dir>

Copies the chosen template (``skills/mcp-scaffold/assets/<lang>/``) into ``<dir>``, stamping
the server name. ``typescript`` (the default) is a whole project directory — fastmcp,
OpenTelemetry, loglayer — stamped with the name, its env prefix and the SPDX year; ``node``
and ``python`` are dependency-free one-file servers. ``<dir>`` may already exist (a repo
root or a subdirectory) but every file the scaffold would write must be absent: it never
overwrites, and refuses naming the first collision before writing anything. Prints one JSON
object on stdout: the written path, the command that runs the server, and the probe command
that proves it answers ``initialize`` and ``tools/list``. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "skills" / "mcp-scaffold" / "assets"
PLACEHOLDER = "__SERVER_NAME__"
ENV_PLACEHOLDER = "__SERVER_ENV__"
YEAR_PLACEHOLDER = "__YEAR__"
# Template files stored without their leading dot (npm pack drops a nested .gitignore).
RENAMES = {"gitignore": ".gitignore", "env.example": ".env.example"}
SKIP_DIRS = {"node_modules", "dist", "__pycache__"}
# The registry key and the `mcp:<server>/<tool>` subject segment: lowercase, no separators
# that the subject grammar uses, at most 64 characters.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TEMPLATES = {
    "node": ("server.mjs", "node"),
    "python": ("server.py", "python3"),
}
DIRECTORY_TEMPLATES = ("typescript",)
DEFAULT_LANG = "typescript"


def _fail(message: str) -> int:
    sys.stderr.write(f"mcp scaffold: {message}\n")
    return 2


def env_prefix(name: str) -> str:
    """``acme-notes`` → ``ACME_NOTES``: the prefix of the server's environment variables."""
    return name.upper().replace("-", "_")


def _stamp(text: str, name: str) -> str:
    return (text.replace(PLACEHOLDER, name)
            .replace(ENV_PLACEHOLDER, env_prefix(name))
            .replace(YEAR_PLACEHOLDER, str(datetime.date.today().year)))


def _template_files(source: Path) -> list[tuple[Path, Path]]:
    """(source file, path relative to the output dir) for every file of a directory template."""
    out = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if not path.is_file() or SKIP_DIRS.intersection(rel.parts[:-1]):
            continue
        out.append((path, rel.with_name(RENAMES.get(rel.name, rel.name))))
    return out


def _scaffold_directory(name: str, lang: str, out: Path) -> int:
    source = ASSETS / lang
    if not source.is_dir():
        return _fail(f"template missing: {source}")
    if out.exists() and not out.is_dir():
        return _fail(f"{out} exists and is not a directory")
    files = _template_files(source)
    for _, rel in files:  # refuse before writing anything
        if (out / rel).exists() or (out / rel).is_symlink():
            return _fail(f"{out / rel} exists; refusing to overwrite — pick another --out")
    for src, rel in files:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(_stamp(src.read_text(encoding="utf-8"), name))
    env_name = f"{env_prefix(name)}_TOKEN"  # a variable NAME; the value is never read here
    server = out / "dist" / "server.js"
    print(json.dumps({
        "ok": True,
        "name": name,
        "lang": lang,
        "path": str(out),
        "files": [rel.as_posix() for _, rel in files],
        "envNames": [env_name],
        "run": "npm install && npm run build && node dist/server.js",
        "probe": f'wicked-garden run scripts/mcp/probe.py --env {env_name} -- node "{server}"',
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="server name: lowercase, digits, '-'; <= 64")
    parser.add_argument("--lang", default=DEFAULT_LANG,
                        choices=sorted([*TEMPLATES, *DIRECTORY_TEMPLATES]),
                        help=f"template (default {DEFAULT_LANG})")
    parser.add_argument("--out", required=True, type=Path, help="directory to write into")
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        return _fail(f"invalid name {args.name!r}: use lowercase letters, digits and '-', "
                     "starting with a letter, at most 64 characters")
    if args.lang in DIRECTORY_TEMPLATES:
        return _scaffold_directory(args.name, args.lang, args.out)
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
