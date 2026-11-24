#!/usr/bin/env python3
"""Scaffold an MCP server from a wicked-garden-mcp-scaffold template.

    wicked-garden run scripts/mcp/scaffold.py --name <server-name> [--lang typescript|node|python] [--rest] --out <dir>

Copies the chosen template (``skills/mcp-scaffold/assets/<lang>/``) into ``<dir>``, stamping
the server name. ``typescript`` (the default) is a whole project directory — fastmcp,
OpenTelemetry, loglayer — stamped with the name, its env prefix and the SPDX year; ``node``
and ``python`` are dependency-free one-file servers. ``<dir>`` may already exist (a repo
root or a subdirectory) but every file the scaffold would write must be absent: it never
overwrites, and refuses naming the first collision before writing anything. Prints one JSON
object on stdout: the written path, the command that runs the server, and the probe command
that proves it answers ``initialize`` and ``tools/list``. ``--rest`` (TypeScript only, garden#1339)
also exposes every tool as a REST API with an OpenAPI 3.1 document, from the same tool definitions:
it sets ``rest.enabled`` in ``mcp-server.config.json`` and prints the HTTP run and REST smoke
commands. The committed transport stays ``stdio`` (an MCP client spawns the server, so it stays
installable); the REST routes ride fastmcp's HTTP server, served under ``MCP_TRANSPORT=httpStream``.
Standard library only.
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


CONFIG_FILE = "mcp-server.config.json"


def _rest_config(text: str) -> str:
    """The stamped config with ``rest.enabled`` on. Every other committed field, the stdio
    transport included, is kept as the template has it."""
    config = json.loads(text)
    config["rest"] = {**config.get("rest", {}), "enabled": True}
    return json.dumps(config, indent=2) + "\n"


def _scaffold_directory(name: str, lang: str, out: Path, rest: bool = False) -> int:
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
        text = _stamp(src.read_text(encoding="utf-8"), name)
        if rest and rel.as_posix() == CONFIG_FILE:
            text = _rest_config(text)
        with target.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    env_name = f"{env_prefix(name)}_TOKEN"  # a variable NAME; the value is never read here
    server = out / "dist" / "server.js"
    report = {
        "ok": True,
        "name": name,
        "lang": lang,
        "path": str(out),
        "files": [rel.as_posix() for _, rel in files],
        "envNames": [env_name],
        "run": "npm install && npm run build && node dist/server.js",
        "probe": f'wicked-garden run scripts/mcp/probe.py --env {env_name} -- node "{server}"',
    }
    if rest:
        config = json.loads((out / CONFIG_FILE).read_text(encoding="utf-8"))
        base = f"http://127.0.0.1:{config.get('port', 8080)}{config['rest']['basePath']}"
        report["rest"] = {
            "enabled": True,
            "envNames": ["MCP_SERVER_BEARER"],  # the bearer every HTTP request carries (REST and MCP)
            "run": f'MCP_TRANSPORT=httpStream node "{server}"',  # with {env_name} and MCP_SERVER_BEARER set
            "openapi": f"{base}/openapi.json",
            # A fresh-scaffold smoke of the REST surface: the document, then the example `echo`
            # (generated tools replace it: then POST one of yours), both with the bearer.
            "smoke": [
                f'curl -fsS -H "Authorization: Bearer $MCP_SERVER_BEARER" {base}/openapi.json',
                f'curl -fsS -H "Authorization: Bearer $MCP_SERVER_BEARER" -H "content-type: application/json"'
                f' -d \'{{"text":"hi"}}\' {base}/tools/echo',
            ],
        }
    print(json.dumps(report, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="server name: lowercase, digits, '-'; <= 64")
    parser.add_argument("--lang", default=DEFAULT_LANG,
                        choices=sorted([*TEMPLATES, *DIRECTORY_TEMPLATES]),
                        help=f"template (default {DEFAULT_LANG})")
    parser.add_argument("--out", required=True, type=Path, help="directory to write into")
    parser.add_argument("--rest", action="store_true",
                        help="also expose every tool as a REST API + OpenAPI 3.1 (typescript only)")
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        return _fail(f"invalid name {args.name!r}: use lowercase letters, digits and '-', "
                     "starting with a letter, at most 64 characters")
    if args.rest and args.lang not in DIRECTORY_TEMPLATES:
        return _fail("--rest needs --lang typescript: the REST surface is part of the TypeScript template")
    if args.lang in DIRECTORY_TEMPLATES:
        return _scaffold_directory(args.name, args.lang, args.out, rest=args.rest)
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
