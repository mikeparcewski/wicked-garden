#!/usr/bin/env python3
"""Run `wicked-core floor probe` on a guide, or say plainly that it cannot run.

    wicked-garden run scripts/build_guide/probe.py --repo <dir> --guide <file> [--check <name>]
        [--bin <wicked-core>] [--timeout 3600] [--version-argv '["cargo","--version"]']

The probe is wicked-core's (``wicked-core floor probe --repo <dir> --guide <file> [--check
<name>]``, DES-BUILD-GUIDE): it runs every probe in a scratch copy of the base and writes
``verified``. This wrapper only finds the binary (``--bin``, else ``$WICKED_CORE_BIN``, else
``wicked-core`` on PATH), asks it whether it has the command (``floor probe --help``), runs it,
and summarizes the ``verified`` block it wrote. It never writes a probe result, ``baseSha`` or
``at``. The probe leaves ``verified.runnerVersion`` blank; with ``--version-argv`` (a JSON argv,
run in ``--repo`` with no shell) this fills each probed check's blank ``runnerVersion`` with the
first line that command prints — the runner's own ``--version``.

Prints one JSON object with ``probe`` = ``ran`` | ``unavailable`` and, when it ran, the per-check
``verified.results`` plus a Markdown table for the proposal. Exit codes: the probe's own exit
code when it ran; 3 when it is unavailable (the message says the guide is unverified, so the
floor will not use it for exclusion); 2 on bad usage. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guide import UNAVAILABLE, load_json  # noqa: E402

HELP_TIMEOUT = 30
USAGE = "floor probe --repo"


def find_core(explicit: str | None) -> str | None:
    for candidate in (explicit, os.environ.get("WICKED_CORE_BIN"), "wicked-core"):
        if candidate:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def has_probe(binary: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run([binary, "floor", "probe", "--help"], capture_output=True, text=True,
                              errors="replace", timeout=HELP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"`{Path(binary).name} floor probe --help` could not run ({exc.__class__.__name__})"
    # wicked-core answers an incomplete `floor probe` with its usage line (exit 2), so the usage
    # text, not the exit code, says the command exists.
    if proc.returncode == 0 or USAGE in proc.stdout + proc.stderr:
        return True, ""
    return False, f"`{Path(binary).name} floor probe --help` exited {proc.returncode}: this wicked-core has no floor probe"


def runner_version(argv: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace", timeout=HELP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return next((ln.strip() for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()), "")


def fill_runner_version(guide_path: Path, wanted: str | None, version: str) -> list[str]:
    """Write ``version`` into each probed check's blank ``verified.runnerVersion``; names the checks."""
    guide = load_json(guide_path)
    filled = []
    for check in guide.get("checks", []):
        v = check.get("verified")
        if (wanted and check.get("name") != wanted) or not isinstance(v, dict) or v.get("runnerVersion"):
            continue
        v["runnerVersion"] = version
        filled.append(check.get("name"))
    if filled:
        guide_path.write_text(json.dumps(guide, indent=2) + "\n", encoding="utf-8")
    return filled


def summarize(guide_path: Path, wanted: str | None) -> tuple[list[dict], str]:
    guide = load_json(guide_path)
    rows: list[dict] = []
    for check in guide.get("checks", []):
        if wanted and check.get("name") != wanted:
            continue
        verified = check.get("verified")
        rows.append({"check": check.get("name"), "verified": verified})
    lines = ["| check | probe | result |", "|---|---|---|"]
    for row in rows:
        results = (row["verified"] or {}).get("results") or {}
        if not results:
            lines.append(f"| {row['check']} | - | no verified written |")
        for probe, outcome in sorted(results.items()):
            lines.append(f"| {row['check']} | {probe} | {outcome} |")
    return rows, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--guide", required=True, type=Path)
    ap.add_argument("--check", dest="check_name")
    ap.add_argument("--bin")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--version-argv", help="JSON argv printing the runner's version, e.g. '[\"cargo\",\"--version\"]'")
    args = ap.parse_args(argv)
    version_argv = None
    if args.version_argv:
        try:
            version_argv = json.loads(args.version_argv)
        except ValueError:
            version_argv = None
        if not (isinstance(version_argv, list) and version_argv and all(isinstance(a, str) for a in version_argv)):
            print(json.dumps({"error": "--version-argv must be a JSON array of strings"}))
            return 2
    if not args.repo.is_dir() or not args.guide.is_file():
        print(json.dumps({"error": "--repo must be a directory and --guide a file"}))
        return 2
    binary = find_core(args.bin)
    reason = "wicked-core is not installed (set WICKED_CORE_BIN or put it on PATH)" if binary is None else ""
    if binary is not None:
        ok, reason = has_probe(binary)
        if not ok:
            binary = None
    if binary is None:
        print(json.dumps({"probe": "unavailable", "guide": "unverified", "message": UNAVAILABLE,
                          "reason": reason}, indent=2))
        return 3
    cmd = [binary, "floor", "probe", "--repo", str(args.repo), "--guide", str(args.guide)]
    if args.check_name:
        cmd += ["--check", args.check_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(json.dumps({"probe": "ran", "exit": None, "error": f"timed out after {args.timeout}s"}))
        return 1
    filled: list[str] = []
    version = ""
    if version_argv:
        version = runner_version(version_argv, args.repo)
        if version:
            filled = fill_runner_version(args.guide, args.check_name, version)
    rows, table = summarize(args.guide, args.check_name)
    print(json.dumps({"probe": "ran", "exit": proc.returncode, "checks": rows, "markdown": table,
                      "runnerVersion": version, "runnerVersionFilled": filled,
                      "stderrTail": proc.stderr[-2000:]}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
