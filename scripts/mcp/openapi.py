#!/usr/bin/env python3
"""The ``openapi`` action: turn an OpenAPI 3 document into an MCP server's ``tools.json``.

    wicked-garden run scripts/mcp/openapi.py --name <key> --base-url <url> \\
        (--spec <file> | --spec-url <url>) [--operations a,b] --out <dir> [--crew-url <origin>]

The conversion is wicked-crew's: this posts ``{name, kind: "rest", url, openapiUrl | openapi,
operations?}`` to ``POST <origin>/api/v1/mcp/servers/preview`` (the origin is ``--crew-url``,
else ``$WICKED_CREW_URL``, else http://127.0.0.1:7701), and writes the answer's ``tools`` and
``skipped`` into ``<dir>/tools.json`` as ``{"source": {...}, "tools": [...], "skipped": [...]}``
— one tool per operation, each with its ``class`` and ``rest`` request mapping — then sets
``baseUrl`` in ``<dir>/mcp-server.config.json``. It refuses to overwrite a ``tools.json``
that is not the empty template. It never reads or sends a secret (no ``secret``/``auth``
key is ever in the body) and never invents tools: with no daemon answering it exits 2.

Prints one JSON summary: tool count, classes, skipped. Exit 0 written, 1 the daemon
refused (its message is carried), 2 bad arguments or no daemon. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_ORIGIN = "http://127.0.0.1:7701"
PREVIEW = "/api/v1/mcp/servers/preview"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TIMEOUT_S = 60
TOOL_KEYS = ("name", "description", "inputSchema", "annotations", "class", "rest")


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: int, message: str) -> int:
    sys.stderr.write(f"mcp openapi: {message}\n")
    return code


def crew_origin(flag: str | None) -> str:
    return (flag or os.environ.get("WICKED_CREW_URL") or DEFAULT_ORIGIN).rstrip("/")


def _http_url(raw: str, what: str, bare: bool) -> str:
    u = urllib.parse.urlsplit(raw)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise Refused(2, f"{what} must be an http(s) URL")
    if bare and (u.username or u.password or u.query or u.fragment):
        raise Refused(2, f"{what} must carry no credentials, query or fragment")
    return raw


def _read_spec(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        raise Refused(2, f"cannot read --spec {path}: {err}") from err
    try:
        doc = json.loads(text)
    except ValueError:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise Refused(2, f"{path} is not JSON and PyYAML is not installed: pass --spec-url "
                             "(the conversion service reads YAML itself)") from None
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as err:
            raise Refused(2, f"{path} is neither JSON nor YAML: {err}") from err
    if not isinstance(doc, dict):
        raise Refused(2, f"{path} is not an OpenAPI document (not an object)")
    return doc


def _is_empty_template(path: Path) -> bool:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and set(doc) <= {"tools"} and doc.get("tools") == []


def post_json(url: str, body: dict, timeout: float = TIMEOUT_S, method: str = "POST") -> dict:
    """POST JSON; the parsed reply. ``Refused`` carries the daemon's message on an HTTP error;
    ``urllib.error.URLError`` propagates when nothing answers."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"content-type": "application/json",
                                          "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 — operator origin
            raw = res.read()
    except urllib.error.HTTPError as err:
        payload = err.read()
        try:
            parsed = json.loads(payload or b"{}")
        except ValueError:
            parsed = {}
        message = (parsed.get("message") or parsed.get("error") or payload.decode("utf-8", "replace")
                   or err.reason) if isinstance(parsed, dict) else str(err.reason)
        refused = Refused(1, f"HTTP {err.code}: {message}")
        refused.status = err.code  # type: ignore[attr-defined]
        refused.body = parsed if isinstance(parsed, dict) else {}  # type: ignore[attr-defined]
        raise refused from None
    return json.loads(raw or b"{}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="the server key")
    parser.add_argument("--base-url", required=True, help="the API base URL the tools are pinned to")
    spec = parser.add_mutually_exclusive_group(required=True)
    spec.add_argument("--spec", type=Path, help="a local OpenAPI 3 document (JSON; YAML with PyYAML)")
    spec.add_argument("--spec-url", help="an http(s) URL the daemon fetches the document from")
    parser.add_argument("--operations", help="comma-separated operationIds to keep (default all)")
    parser.add_argument("--out", required=True, type=Path, help="the server directory")
    parser.add_argument("--crew-url", help=f"the wicked-crew daemon origin (default $WICKED_CREW_URL, else {DEFAULT_ORIGIN})")
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        return _fail(2, f"invalid --name {args.name!r}: lowercase letters, digits and '-', at most 64")
    tools_path = args.out / "tools.json"
    config_path = args.out / "mcp-server.config.json"
    try:
        _http_url(args.base_url, "--base-url", bare=True)
        if args.spec_url:
            _http_url(args.spec_url, "--spec-url", bare=False)
        if tools_path.exists() and not _is_empty_template(tools_path):
            raise Refused(2, f"{tools_path} already holds tools; refusing to overwrite — "
                             "restore the empty template ({\"tools\": []}) to regenerate")
        body: dict = {"name": args.name, "kind": "rest", "url": args.base_url}
        if args.spec_url:
            body["openapiUrl"] = args.spec_url
        else:
            body["openapi"] = _read_spec(args.spec)
        if args.operations is not None:
            body["operations"] = [op.strip() for op in args.operations.split(",") if op.strip()]
            if not body["operations"]:
                raise Refused(2, "--operations names no operationId")
        config = None
        if config_path.is_file():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except ValueError as err:
                raise Refused(2, f"{config_path} is not valid JSON: {err}") from err
            if not isinstance(config, dict):
                raise Refused(2, f"{config_path} is not a JSON object")
    except Refused as err:
        return _fail(err.code, str(err))

    origin = crew_origin(args.crew_url)
    try:
        answer = post_json(origin + PREVIEW, body)
    except Refused as err:
        return _fail(1, f"the conversion service refused: {err}")
    except (urllib.error.URLError, OSError):
        return _fail(2, f"the conversion service is the wicked-crew daemon; none answered at {origin} "
                        "— write the tools by hand (branch B)")
    except ValueError:
        return _fail(1, f"the daemon at {origin} answered something that is not JSON")

    tools = [{k: t[k] for k in TOOL_KEYS if k in t}
             for t in answer.get("tools") or [] if isinstance(t, dict)]
    skipped = answer.get("skipped") or []
    source = {"specUrl": args.spec_url} if args.spec_url else {"specFile": str(args.spec)}
    source.update({"baseUrl": args.base_url,
                   "convertedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})
    args.out.mkdir(parents=True, exist_ok=True)
    tools_path.write_text(json.dumps({"source": source, "tools": tools, "skipped": skipped},
                                     indent=2) + "\n", encoding="utf-8")
    config_note = None
    if config is not None:
        config["baseUrl"] = args.base_url
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    else:
        config_note = f"{config_path} not found: set baseUrl there after scaffolding"
    classes: dict[str, int] = {}
    for t in tools:
        classes[str(t.get("class"))] = classes.get(str(t.get("class")), 0) + 1
    summary = {"ok": True, "tools": len(tools), "classes": classes, "skipped": skipped,
               "toolsJson": str(tools_path), "previewHash": answer.get("previewHash")}
    if config_note:
        summary["note"] = config_note
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
