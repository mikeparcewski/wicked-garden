#!/usr/bin/env python3
"""Check a build/test guide against contract v1, before and after the probe.

    wicked-garden run scripts/build_guide/check.py --guide <file> [--repo <dir>] [--schema <file>] [--draft]

* ``--schema``: the contract schema. The default is ``schemas/build-guide.v1.json``, vendored byte
  for byte from wicked-core main (the report's ``schema`` names that source); pass core's current
  file to check against a newer one.
* ``--repo``: also check that ``derivedFrom`` files and each ``cwd`` exist there, and warn for
  every command the repo's CI runs that no check declares in that step's working directory
  (``working-directory``). In the directories a usable guide's checks cover (their ``cwd``s), its
  checks replace the floor's own detection, so an undeclared install, build, format, lint,
  typecheck or test step there would stop gating. A step counts as declared when a check's ``run`` equals its argv,
  or when EVERY command of the ``make``/``just`` recipe or npm script it runs is declared (an npm
  script's also with ``npx`` in front: npm runs scripts with ``node_modules/.bin`` on PATH).
* ``--draft``: the guide has not been probed — it must carry no ``verified`` (only
  ``wicked-core floor probe`` writes it).

Prints one JSON object and exits 0 when there are no errors, 1 otherwise, 2 on bad usage.
Warnings never fail the check. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guide import SCHEMA, SCHEMA_SOURCE, lint, load_json, schema_errors  # noqa: E402
from discover import discover, is_trivial  # noqa: E402


def _argv(command: str) -> list[str] | None:
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _dir(path: str) -> str:
    path = path.strip().removeprefix("./").rstrip("/")
    return path or "."


def undeclared_ci_steps(guide: dict, repo: Path) -> list[str]:
    """A warning for every CI step no check declares in the step's working directory."""
    runs = [(c.get("run"), _dir(c.get("cwd", "."))) for c in guide.get("checks", []) if isinstance(c, dict)]
    out = []
    for step in discover(repo)["ciSteps"]:
        where = _dir(step.get("cwd", "."))

        def declared(argv: list[str] | None, npm: bool = False) -> bool:
            return bool(argv) and ((argv, where) in runs or (npm and (["npx", *argv], where) in runs))

        # The step itself, or every real command of the recipe / script it runs: a guide that
        # declares `cargo test` alone does not cover a `make ci` that also builds.
        resolved = [r for r in step.get("resolves", []) if not is_trivial(r["command"])]
        covered = declared(_argv(step["command"])) or (bool(resolved) and all(
            declared(_argv(r["command"]), "package.json#scripts." in r["source"]) for r in resolved))
        if not covered:
            at = "" if where == "." else f" in `{where}`"
            out.append(f"CI runs `{step['command']}`{at} ({step['source']}) but no check declares it there; in the "
                       "directories its checks cover, a guide's checks replace the floor's detection, so this step "
                       "would not gate. Declare it as a check with that `cwd` (a gate with no `list` when it is not "
                       "the test run).")
    return out


def run_check(guide_path: Path, repo: Path | None, schema_path: Path | None, draft: bool) -> dict:
    report: dict = {"guide": str(guide_path), "schema": SCHEMA_SOURCE if schema_path is None else str(schema_path),
                    "draft": draft}
    try:
        guide = load_json(guide_path)
    except (OSError, ValueError) as exc:
        report.update(ok=False, errors=[f"cannot read the guide: {exc}"], warnings=[])
        return report
    schema = load_json(schema_path or SCHEMA)
    errors = schema_errors(guide, schema)
    warnings: list[str] = []
    if isinstance(guide, dict):
        try:
            lint_errors, warnings = lint(guide, repo, draft)
        except (AttributeError, TypeError, KeyError) as exc:
            # A guide the schema already refuses can be shaped so the deeper checks cannot read it.
            if not errors:
                raise
            lint_errors, warnings = [f"the deeper checks were skipped: the guide's shape is invalid "
                                     f"({exc.__class__.__name__}); fix the schema errors first"], []
        errors += lint_errors
        if repo is not None:
            warnings += undeclared_ci_steps(guide, repo)
    report.update(ok=not errors, errors=errors, warnings=warnings)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--guide", required=True, type=Path)
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--schema", type=Path)
    ap.add_argument("--draft", action="store_true")
    args = ap.parse_args(argv)
    if args.repo is not None and not args.repo.is_dir():
        print(json.dumps({"ok": False, "errors": [f"--repo {args.repo} is not a directory"]}))
        return 2
    report = run_check(args.guide, args.repo, args.schema, args.draft)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
