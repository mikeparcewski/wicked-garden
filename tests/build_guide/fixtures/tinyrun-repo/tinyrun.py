#!/usr/bin/env python3
"""tinyrun: a tiny test runner with NO structured output (no JUnit, JSON or TAP).

A test file is checks/<suite>.tc; each line is a test:

    <name> <int> == <int>      passes when the two integers are equal
    <name> say <text>          prints <text> (test output, interleaved) and passes

A test's id is <suite>/<name>. Usage:

    tinyrun.py                 run every test
    tinyrun.py --list          print every id, one per line (after --only / --skip)
    tinyrun.py --only ID       run one test (also --only=ID)
    tinyrun.py --skip ID       skip a test, repeatable (also --skip=ID)
    tinyrun.py --version | --help

Exit 0 when every test passed, 3 when any failed, 2 on bad usage or an unreadable test.
"""
import sys
from pathlib import Path

VERSION = "tinyrun 0.3.1"


def load():
    tests = []
    for path in sorted(Path("checks").glob("*.tc")):
        for raw in path.read_text().splitlines():
            if not raw.strip():
                continue
            name, rest = raw.split(" ", 1)
            tests.append((f"{path.stem}/{name}", path.stem, name, rest))
    return tests


def main(argv):
    only, skip, listing = None, [], False
    it = iter(argv)
    for arg in it:
        if arg == "--version":
            print(VERSION)
            return 0
        if arg == "--help":
            print(__doc__)
            return 0
        if arg == "--list":
            listing = True
        elif arg == "--only":
            only = next(it, None)
        elif arg.startswith("--only="):
            only = arg.split("=", 1)[1]
        elif arg == "--skip":
            skip.append(next(it, None))
        elif arg.startswith("--skip="):
            skip.append(arg.split("=", 1)[1])
        else:
            print(f"tinyrun: unknown argument {arg!r}", file=sys.stderr)
            return 2
    tests = [t for t in load() if (only is None or t[0] == only) and t[0] not in skip]
    if listing:
        for ident, *_ in tests:
            print(ident)
        return 0
    print(VERSION)
    failed, passed = [], 0
    for ident, suite, name, rest in tests:
        if rest.startswith("say "):
            print(rest[4:])
            ok = True
        else:
            lhs, _, rhs = rest.partition(" == ")
            ok = int(lhs) == int(rhs)
        print(f"[{suite}] {name} ... {'ok' if ok else 'FAIL'}")
        if ok:
            passed += 1
        else:
            failed.append(ident)
    print("--- tinyrun summary ---")
    for ident in failed:
        print(f"FAIL {ident}")
    print(f"--- {len(failed)} failed, {passed} passed ---")
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
