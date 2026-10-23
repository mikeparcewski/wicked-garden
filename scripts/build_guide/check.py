#!/usr/bin/env python3
"""Check a build/test guide against contract v1, before and after the probe.

    wicked-garden run scripts/build_guide/check.py --guide <file> [--repo <dir>] [--schema <file>] [--draft]

* ``--schema``: the contract schema. The default is ``schemas/build-guide.v1.json``, vendored byte
  for byte from wicked-core's #1066 branch (the report's ``schema`` names that source); pass
  core's current file to check against a newer one.
* ``--repo``: also check that ``derivedFrom`` files and each ``cwd`` exist there.
* ``--draft``: the guide has not been probed — it must carry no ``verified`` (only
  ``wicked-core floor probe`` writes it).

Prints one JSON object and exits 0 when there are no errors, 1 otherwise, 2 on bad usage.
Warnings never fail the check. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guide import SCHEMA, SCHEMA_SOURCE, lint, load_json, schema_errors  # noqa: E402


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
        lint_errors, warnings = lint(guide, repo, draft)
        errors += lint_errors
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
