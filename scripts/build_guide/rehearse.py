#!/usr/bin/env python3
"""Rehearse a draft guide's probes in a scratch copy, before `wicked-core floor probe` runs.

    wicked-garden run scripts/build_guide/rehearse.py --repo <dir> --guide <file> [--check <name>]
        [--schema <file>] [--timeout 900] [--exclude <dir>]... [--link <dir>]...

A REHEARSAL, not the probe: it never writes ``verified`` and its verdict is not evidence the
floor reads. It exists so the parser, the ids and the templates can be iterated on quickly (and
reported honestly when the probe is unavailable). It mirrors wicked-core's ``floor probe``
(#1066's ``src/floor_probe.rs`` at f88a639) piece by piece, with exit codes as the referee:

* ``list``     — the list run exits 0 and names tests.
* ``run``      — the run's exit code agrees with its parsed failures (0 iff none; else a failedExit).
* ``mutation`` — with ``probes.mutation`` written, the run fails with a failedExit and its new
  failures (that still fail alone) are exactly the expected id; deselecting it leaves the clean
  run's failures; run alone, it fails.
* ``ids``      — every id the clean run reports (JUnit: all; text: its failures), and the mutated
  id, is one the list names.
* ``alone``    — a listed passing id run alone exits 0 with no failure (JUnit: every testcase that
  ran is that id).
* ``deselect`` — the list, deselecting that passing id, lists exactly the rest.
* ``multi``    — with ``probes.mutation2`` written too, the new failures are exactly the two
  expected ids, and deselecting both leaves the clean run's failures.
* ``affected`` — when declared: run on the mutation file, its failures include the mutated id.

A probe that fails is retried once, as core does; failing twice means unverified (``retried``
names the probes that needed the retry).

The copy omits ``.git`` and ``--exclude`` dirs (default ``target``) and symlinks ``--link`` dirs
(default ``node_modules``, ``.venv``) instead of copying them. Prints one JSON report; exit 0
when no probe failed, 1 when one did, 2 when the guide does not check. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guide import (SCHEMA, Failure, deselect_tokens, expand_files, lint, load_json,  # noqa: E402
                    parse_junit, parse_list, parse_text, schema_errors, substitute)

NOTE = ("rehearsal only: verified is not written and this is not probe evidence; "
        "the floor uses a guide only after `wicked-core floor probe` passes it")


class Outcome:
    def __init__(self, exit_code: int | None, failures: set, every: set | None, error: str = ""):
        self.exit = exit_code
        self.failures = failures
        self.every = every
        self.error = error


def make_scratch(repo: Path, exclude: list[str], link: list[str]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="wg-build-guide-"))
    dest = root / "repo"
    skip = {".git", *exclude, *link}

    def ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in skip and Path(_dir) == repo]

    shutil.copytree(repo, dest, ignore=ignore, symlinks=True)
    for name in link:
        if (repo / name).exists():
            os.symlink(repo / name, dest / name, target_is_directory=True)
    return dest


def _capture(argv: list[str], workdir: Path, env: dict, merge: bool, timeout: int):
    return subprocess.run(argv, cwd=workdir, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT if merge else subprocess.PIPE,
                          text=True, errors="replace", timeout=timeout)


def _keyed(check: dict) -> bool:
    """As the interpreter: ids carry their qualifier only when the list has a section."""
    return bool(check.get("list", {}).get("section"))


def _unkey(check: dict, ids):
    return ids if _keyed(check) else type(ids)(("", i) for _q, i in ids)


def execute(check: dict, workdir: Path, argv: list[str], timeout: int) -> Outcome:
    """A results run, as the interpreter makes it: ``argv`` + ``results.how.argvAppend``."""
    results = check["results"]
    how = results.get("how", {})
    full = list(argv) + list(how.get("argvAppend", []))
    env = {**os.environ, **how.get("env", {})}
    result_file = (workdir / how["path"]) if how.get("path") else None
    if result_file is not None and result_file.exists():
        result_file.unlink()
    try:
        proc = _capture(full, workdir, env, bool(how.get("merge")), timeout)
    except FileNotFoundError:
        return Outcome(None, set(), None, f"{full[0]!r} is not on PATH")
    except subprocess.TimeoutExpired:
        return Outcome(None, set(), None, f"did not finish within {timeout}s")
    if result_file is not None:
        if not result_file.exists():
            return Outcome(proc.returncode, set(), None, f"`{how['path']}` could not be opened")
        text = result_file.read_text(encoding="utf-8", errors="replace")
    else:
        text = proc.stdout
    if results["kind"] == "text":
        return Outcome(proc.returncode, _unkey(check, parse_text(check["parser"], text)), None)
    try:
        every, failed = parse_junit(text, results.get("id"), results.get("idJoin", "::"))
    except Exception as exc:  # noqa: BLE001 - any unreadable report is a probe failure, named
        return Outcome(proc.returncode, set(), None, f"the results do not parse as JUnit ({exc.__class__.__name__})")
    return Outcome(proc.returncode, _unkey(check, failed), _unkey(check, every))


def exit_of(check: dict, workdir: Path, argv: list[str], timeout: int) -> int | None:
    """A bare run (no argvAppend, no results read), as the interpreter's exit-only runs."""
    env = {**os.environ, **check["results"].get("how", {}).get("env", {})}
    try:
        return _capture(argv, workdir, env, False, timeout).returncode
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _ids(keys) -> set:
    return {i for _q, i in keys}


def _inject(workdir: Path, mutation: dict) -> None:
    target = workdir / mutation["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(mutation["content"], encoding="utf-8")


def inventory(check: dict, workdir: Path, timeout: int, deselect: list[Failure] | None = None) -> list | str:
    """The list run (with ``deselect`` ids deselected, when given): its ids, or why it is incomplete."""
    spec = check["list"]
    argv = _deselected(check, deselect, spec["run"]) if deselect else list(spec["run"])
    env = {**os.environ, **check["results"].get("how", {}).get("env", {})}
    try:
        proc = _capture(argv, workdir, env, bool(spec.get("merge")), timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"its list could not run ({exc.__class__.__name__})"
    if proc.returncode != 0:
        return f"its list did not exit 0 (exit {proc.returncode})"
    ids = parse_list(spec, proc.stdout)
    if not ids and not deselect:
        return "its list names no test"
    return ids


def _deselected(check: dict, ids: list[Failure], argv: list[str] | None = None) -> list[str]:
    """``argv`` (default ``run``) with ``ids`` deselected, composed as the schema states."""
    base = list(check["run"] if argv is None else argv)
    return base + deselect_tokens(check["deselect"]["append"], ids, base)


def _verdict(ok: bool, why: str) -> str:
    return "pass" if ok else f"fail: {why}"


def _steady(check: dict, workdir: Path, failed, before, timeout: int) -> set:
    """``failed``'s ids beyond ``before`` that still fail run alone; a new failure that passes
    alone is the suite's flake, not the parser's mistake, and is set aside (as core does)."""
    return {t for t in failed if t not in before and
            exit_of(check, workdir, substitute(check["alone"]["run"], id=t[1], q=t[0]), timeout) in check["failedExit"]}


def _matches(t: Failure, m: dict) -> bool:
    return t[1] == m["expectId"] and m.get("expectQ") in (None, t[0])


def _deselect_clean(check: dict, workdir: Path, ids: list, clean_failed: set, timeout: int) -> tuple[bool, Outcome]:
    """Deselecting ``ids`` leaves the clean run's failures (and exits 0 when it had none)."""
    d = execute(check, workdir, _deselected(check, ids), timeout)
    ok = (not d.error and not any(t in d.failures for t in ids)
          and not _steady(check, workdir, d.failures, clean_failed, timeout)
          and (bool(clean_failed) or d.exit == 0))
    return ok, d


def _probe_mutation(check: dict, workdir: Path, clean_failed: set, mutated: Outcome, timeout: int):
    """The mutated run fails with a failedExit and exactly one new (steady) failure, the expected
    one; deselecting it leaves the clean run's failures; run alone it fails. Returns (verdict, id)."""
    m = check["probes"]["mutation"]
    if mutated.error:
        return f"fail: the mutated run's results: {mutated.error}", None
    new = sorted(_steady(check, workdir, mutated.failures, clean_failed, timeout))
    hit = new[0] if len(new) == 1 and _matches(new[0], m) else None
    if hit is None:
        return f"fail: the mutated run's new failures are {new[:5]}, not `{m['expectId']}`", None
    if mutated.exit not in check["failedExit"]:
        return f"fail: the mutated run exited {mutated.exit}", hit
    ok, d = _deselect_clean(check, workdir, [hit], clean_failed, timeout)
    if not ok:
        return f"fail: deselecting `{hit[1]}` did not leave the clean run's failures (exit {d.exit})", hit
    if exit_of(check, workdir, substitute(check["alone"]["run"], id=hit[1], q=hit[0]), timeout) not in check["failedExit"]:
        return f"fail: `{hit[1]}` run alone does not fail", hit
    return "pass", hit


def _probe_ids(clean: Outcome, hit, listed) -> str:
    """Every id the clean run reports (junit: all; text: the failures), and the mutated id, is listed."""
    if clean.error or hit is None or not isinstance(listed, list):
        return "fail: the clean or mutated run's ids could not be established"
    reported = list(clean.every or []) + sorted(clean.failures) + [hit]
    stray = next((t for t in reported if t not in listed), None)
    return _verdict(stray is None, f"the results name `{stray[1] if stray else ''}` (q `{stray[0] if stray else ''}`), "
                                   "which the list does not")


def _probe_alone_and_deselect(check: dict, workdir: Path, listed, mutated: Outcome, timeout: int) -> tuple[str, str]:
    failing = _ids(mutated.failures)
    passing = next((t for t in listed if t[1] not in failing), None) if isinstance(listed, list) else None
    if passing is None:
        return ("fail: the list names no passing test",) * 2
    one = execute(check, workdir, substitute(check["alone"]["run"], id=passing[1], q=passing[0]), timeout)
    ran = one.every if one.every is not None else []
    alone_ok = not one.error and one.exit == 0 and not one.failures and (
        check["results"]["kind"] != "junit" or (bool(ran) and all(t[1] == passing[1] for t in ran)))
    alone = _verdict(alone_ok, one.error or f"`{passing[1]}` alone exited {one.exit}, ran {len(ran)} test(s), "
                                         f"{len(one.failures)} failure(s)")
    rest = inventory(check, workdir, timeout, deselect=[passing])
    want = sorted(t for t in listed if t != passing)
    got = sorted(rest) if isinstance(rest, list) else []
    deselect = _verdict(isinstance(rest, list) and got == want,
                        f"the list deselecting `{passing[1]}` lists {len(got)} test(s), not the {len(want)} others"
                        + (f" ({rest})" if isinstance(rest, str) else ""))
    return alone, deselect


def _probe_multi(check: dict, workdir: Path, clean_failed: set, timeout: int) -> str:
    """With ``probes.mutation2`` written too, the new failures are exactly the two expected ids,
    and deselecting both leaves the clean run's failures."""
    m, m2 = check["probes"]["mutation"], check["probes"].get("mutation2")
    if not m2:
        return "fail: no `probes.mutation2`"
    _inject(workdir, m2)
    run = execute(check, workdir, list(check["run"]), timeout)
    if run.error:
        return f"fail: the run's results: {run.error}"
    new = sorted(_steady(check, workdir, run.failures, clean_failed, timeout))
    both = len(new) == 2 and any(_matches(t, m) for t in new) and any(_matches(t, m2) for t in new)
    if not both or run.exit not in check["failedExit"]:
        return (f"fail: with both mutations the new failures are {new[:5]} (exit {run.exit}), "
                f"not `{m['expectId']}` and `{m2['expectId']}`")
    ok, d = _deselect_clean(check, workdir, new, clean_failed, timeout)
    return _verdict(ok, f"deselecting both did not leave the clean run's failures (exit {d.exit})")


def rehearse_check(check: dict, repo: Path, timeout: int, exclude: list[str], link: list[str]) -> dict:
    """The core probe's pieces, retried once as core does: a probe that failed is run again (a
    fresh scratch copy, every piece in order) and passes if the retry passes; failing twice
    leaves the guide unverified."""
    first = _rehearse_once(check, repo, timeout, exclude, link)
    failed = [p for p, v in first.items() if v.startswith("fail")]
    if not failed:
        return {"name": check["name"], "results": first, "retried": [], "ok": True}
    second = _rehearse_once(check, repo, timeout, exclude, link)
    results = {p: (second.get(p, v) if p in failed else v) for p, v in first.items()}
    return {"name": check["name"], "results": results, "retried": failed,
            "ok": not any(v.startswith("fail") for v in results.values())}


def _rehearse_once(check: dict, repo: Path, timeout: int, exclude: list[str], link: list[str]) -> dict:
    """The core probe's pieces, in its order."""
    results: dict[str, str] = {}
    scratch = make_scratch(repo, exclude, link)
    try:
        workdir = scratch / check.get("cwd", ".")
        listed = inventory(check, workdir, timeout)
        results["list"] = _verdict(isinstance(listed, list), str(listed))
        clean = execute(check, workdir, list(check["run"]), timeout)
        if clean.error:
            results["run"] = f"fail: {clean.error}"
        else:
            ok = not clean.failures if clean.exit == 0 else bool(clean.failures) and clean.exit in check["failedExit"]
            results["run"] = _verdict(ok, f"exit {clean.exit} with {len(clean.failures)} parsed failure(s)")
        _inject(workdir, check["probes"]["mutation"])
        mutated = execute(check, workdir, list(check["run"]), timeout)
        results["mutation"], hit = _probe_mutation(check, workdir, clean.failures, mutated, timeout)
        listed_now = inventory(check, workdir, timeout)
        results["ids"] = _probe_ids(clean, hit, listed_now)
        results["alone"], results["deselect"] = _probe_alone_and_deselect(check, workdir, listed_now, mutated, timeout)
        results["multi"] = _probe_multi(check, workdir, clean.failures, timeout)
        if "affected" in check:
            aff = execute(check, workdir, expand_files(list(check["affected"]["run"]), [check["probes"]["mutation"]["file"]]),
                          timeout)
            results["affected"] = ("fail: the mutation probe did not establish the id" if hit is None else
                                   _verdict(hit in aff.failures, f"the affected run's failures do not include `{hit[1]}`"))
    finally:
        shutil.rmtree(scratch.parent, ignore_errors=True)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--guide", required=True, type=Path)
    ap.add_argument("--check", dest="check_name")
    ap.add_argument("--schema", type=Path)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--exclude", action="append", default=None)
    ap.add_argument("--link", action="append", default=None)
    args = ap.parse_args(argv)
    repo = args.repo.resolve()
    guide = load_json(args.guide)
    errors = schema_errors(guide, load_json(args.schema or SCHEMA))
    if not errors:
        errors, _warnings = lint(guide, repo, draft=False)
    if errors:
        print(json.dumps({"rehearsal": True, "ok": False, "errors": errors}, indent=2))
        return 2
    checks = [c for c in guide["checks"] if args.check_name in (None, c["name"])]
    if not checks:
        print(json.dumps({"rehearsal": True, "ok": False, "errors": [f"no check named {args.check_name!r}"]}))
        return 2
    exclude = args.exclude if args.exclude is not None else ["target"]
    link = args.link if args.link is not None else ["node_modules", ".venv"]
    reports = [rehearse_check(c, repo, args.timeout, exclude, link) for c in checks]
    ok = all(r["ok"] for r in reports)
    print(json.dumps({"rehearsal": True, "note": NOTE, "ok": ok, "checks": reports}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
