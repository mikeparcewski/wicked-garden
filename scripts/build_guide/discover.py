#!/usr/bin/env python3
"""Collect what a repo already declares about how it tests — the evidence a guide is drafted from.

    wicked-garden run scripts/build_guide/discover.py --repo <dir>

Reads, in this order, and never runs anything:

1. CI config — ``.github/workflows/*.yml|yaml`` (``run:`` steps, including ``run: |`` blocks),
   ``.gitlab-ci.yml`` (``script:`` items), ``Makefile`` / ``justfile`` recipes.
2. Manifests — ``Cargo.toml``, ``package.json`` (its ``scripts``), ``pyproject.toml``,
   ``setup.cfg``, ``tox.ini``, ``go.mod``, ``build.gradle(.kts)``, ``pom.xml``.

It holds no table of runners. A command is a test candidate when its text says ``test`` (which
covers ``cargo test``, ``pytest``, ``vitest``, ``go test``, ``make test``, ``npm test`` …); a
``make <target>``, ``just <recipe>`` or ``npm|pnpm|yarn run <script>`` / ``npm test`` candidate
is followed one level into the recipe or script it names, so the guide can be derived from the
command that really runs. Which candidate is the check, and what its runner can emit, is the
agent's call after running the runner's ``--version`` and ``--help``.

Prints one JSON object: ``files`` (repo-relative CI and manifest paths found — the
``derivedFrom`` candidates), ``commands`` (every test candidate with its source ``file:line`` and
any resolved recipe), ``ciSteps`` (EVERY command CI runs — install, build, format, lint,
typecheck, test — each of which the guide must declare as a check, because a guide's checks
replace the floor's own detection), and ``verdict``: ``candidates`` or ``no-test-command``. Exit 0; 2 on bad usage.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

CI_GLOBS = [".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml"]
RECIPE_FILES = ["Makefile", "makefile", "GNUmakefile", "justfile", "Justfile"]
MANIFESTS = ["Cargo.toml", "package.json", "pyproject.toml", "setup.cfg", "tox.ini", "go.mod",
             "build.gradle", "build.gradle.kts", "pom.xml"]
# npm init writes this as the default test script; it declares that there are no tests.
NPM_PLACEHOLDER = "no test specified"

_RUN_KEY = re.compile(r"^(\s*)(?:-\s+)?run:\s*(.*)$")
_SCRIPT_KEY = re.compile(r"^(\s*)script:\s*(.*)$")
_LIST_ITEM = re.compile(r"^\s*-\s+(.*)$")
_RECIPE_HEAD = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:(?!=)")
_INDIRECT = re.compile(r"(?:^|[\s;&|(])(make|just|npm|pnpm|yarn)\s+(?:(?:-\S+\s+)*)(run\s+)?([A-Za-z0-9_:.\-]+)")


def is_test(cmd: str) -> bool:
    return "test" in cmd.lower()


# Shell builtins that set up a step rather than gate it.
_TRIVIAL = {"echo", "cd", "export", "set", "true", ":", "printf", "pushd", "popd"}


def is_trivial(cmd: str) -> bool:
    first = cmd.strip().split(" ", 1)[0] if cmd.strip() else ""
    return not first or first.startswith("#") or first in _TRIVIAL


def _block_lines(lines: list[str], start: int, indent: int) -> list[tuple[int, str]]:
    out = []
    for j in range(start, len(lines)):
        text = lines[j]
        if text.strip() and (len(text) - len(text.lstrip())) <= indent:
            break
        if text.strip():
            out.append((j + 1, text.strip()))
    return out


def ci_commands(rel: str, text: str) -> list[dict]:
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        m = _RUN_KEY.match(line) or _SCRIPT_KEY.match(line)
        if not m:
            continue
        indent, rest = len(m.group(1)), m.group(2).strip()
        if rest in ("|", ">", "|-", ">-", ""):
            for lineno, cmd in _block_lines(lines, i + 1, indent):
                item = _LIST_ITEM.match(cmd) if rest == "" else None
                found.append({"source": f"{rel}:{lineno}", "command": item.group(1) if item else cmd})
        else:
            found.append({"source": f"{rel}:{i + 1}", "command": rest.strip("'\"")})
    return found


def recipes(text: str) -> dict[str, list[tuple[int, str]]]:
    """Makefile / justfile recipe bodies by target name."""
    out: dict[str, list[tuple[int, str]]] = {}
    current = None
    for i, line in enumerate(text.splitlines()):
        head = _RECIPE_HEAD.match(line)
        if head and not line.startswith((" ", "\t")):
            current = head.group(1)
            out.setdefault(current, [])
        elif current and line.startswith(("\t", "    ")) and line.strip():
            out[current].append((i + 1, line.strip().lstrip("@-")))
        elif line.strip() and not line.startswith(("\t", " ")):
            current = None
    return out


def resolve(cmd: str, repo: Path, recipe_map: dict, scripts: dict) -> list[dict]:
    m = _INDIRECT.search(cmd)
    if not m:
        return []
    tool, run_word, name = m.group(1), m.group(2), m.group(3)
    if tool in ("make", "just"):
        for rel, table in recipe_map.items():
            if name in table and table[name]:
                return [{"source": f"{rel}:{n}", "command": c} for n, c in table[name]]
        return []
    if name == "test" or run_word:
        if name in scripts:
            return [{"source": f"package.json#scripts.{name}", "command": scripts[name]}]
    return []


def discover(repo: Path) -> dict:
    # Exact names from the directory listing: on a case-insensitive filesystem `makefile` would
    # otherwise also "exist" next to `Makefile`.
    present = set(os.listdir(repo))
    files: list[str] = []
    steps: list[dict] = []
    for pattern in CI_GLOBS:
        for path in sorted(repo.glob(pattern)):
            rel = path.relative_to(repo).as_posix()
            files.append(rel)
            steps += [c for c in ci_commands(rel, path.read_text(encoding="utf-8", errors="replace"))
                      if not is_trivial(c["command"])]
    commands: list[dict] = [dict(c) for c in steps if is_test(c["command"])]
    recipe_map: dict[str, dict] = {}
    for name in RECIPE_FILES:
        path = repo / name
        if name in present and path.is_file():
            files.append(name)
            recipe_map[name] = recipes(path.read_text(encoding="utf-8", errors="replace"))
    scripts: dict[str, str] = {}
    manifests = []
    for name in MANIFESTS:
        path = repo / name
        if name not in present or not path.is_file():
            continue
        files.append(name)
        entry: dict = {"file": name}
        if name == "package.json":
            try:
                scripts = json.loads(path.read_text(encoding="utf-8")).get("scripts", {}) or {}
            except ValueError:
                entry["error"] = "package.json is not valid JSON"
            entry["scripts"] = scripts
        manifests.append(entry)
    for rel, table in recipe_map.items():
        for target, body in table.items():
            if is_test(target):
                commands += [{"source": f"{rel}:{n}", "command": c, "target": target} for n, c in body]
    for key, value in scripts.items():
        if is_test(key):
            commands.append({"source": f"package.json#scripts.{key}", "command": value})
    for cmd in commands + steps:
        resolved = resolve(cmd["command"], repo, recipe_map, scripts)
        if resolved:
            cmd["resolves"] = resolved
        if NPM_PLACEHOLDER in cmd["command"]:
            cmd["placeholder"] = True
    real = [c for c in commands if not c.get("placeholder")]
    return {"repo": str(repo), "files": files, "manifests": manifests, "commands": commands,
            "ciSteps": steps, "verdict": "candidates" if real else "no-test-command"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, type=Path)
    args = ap.parse_args(argv)
    if not args.repo.is_dir():
        print(json.dumps({"error": f"--repo {args.repo} is not a directory"}))
        return 2
    report = discover(args.repo.resolve())
    report["repo"] = "."
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
