#!/usr/bin/env python3
"""Rehearse a draft guide's probes in a scratch copy, before `wicked-core floor probe` runs.

    wicked-garden run scripts/build_guide/rehearse.py --repo <dir> --guide <file> [--check <name>]
        [--schema <file>] [--timeout 900] [--exclude <dir>]... [--link <dir>]...

A REHEARSAL, not the probe: it never writes ``verified`` and its verdict is not evidence the
floor reads. It exists so the parser, the ids and the templates can be iterated on quickly (and
reported honestly when the probe is unavailable). It mirrors wicked-core's ``floor probe``
(wicked-core main's ``src/floor_probe.rs``) piece by piece, with exit codes as the referee:

* ``list``     — the list run exits 0 and names tests.
* ``run``      — the clean run is GREEN (exit 0, no parsed failure). Every later probe needs a
  green base; on a red one they all fail "needs a green base".
* ``mutation`` — with ``probes.mutation`` written, the run fails with a failedExit naming EXACTLY
  the expected test, and the run deselecting it is green.
* ``multi``    — with ``probes.mutation2`` written too, the run names exactly both; deselecting
  both is green, and the list deselecting both lists exactly the rest.
* ``ids``      — every id the results report is in the list.
* ``alone``    — the mutated test alone fails naming exactly it (JUnit: exactly one testcase
  ran), and a passing test under its qualifier alone is green (JUnit: exactly it ran). A runner
  whose qualifier is the test file (cargo: one binary per file) therefore needs a passing test
  beside the mutation, in the mutation's own file.
* ``deselect`` — the list deselecting that passing test lists exactly the rest.
* ``affected`` — when declared: run on the mutation file, its failures include the mutated test.
* ``version``  — when declared: the command passes and prints a line (stdout and stderr merged),
  reported as ``runnerVersion``. The probe records it; this never writes it.

When any probe fails (other than for a missing piece), the WHOLE rehearsal re-runs once on a
fresh copy and that retry's results are the result, each marked `` (retried)``, as core does.
A check with no ``list`` piece is a gate (exit code only) and is skipped, as core skips it.
Argvs are composed as core composes them: ``argvAppend`` and ``deselect.append`` tokens go
around the argv's ``--`` (see ``_guide.compose``).

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
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _guide import (SCHEMA, Failure, compose, deselected, expand_files, lint, load_json,  # noqa: E402
                    parse_junit, parse_list, parse_text, passed, schema_errors, substitute)

NOTE = ("rehearsal only: verified is not written and this is not probe evidence; "
        "the floor uses a guide only after `wicked-core floor probe` passes it")


class Outcome:
    def __init__(self, exit_code: int | None, failures: list, every: list | None, error: str = ""):
        self.exit = exit_code
        self.failures = failures
        self.every = every
        self.error = error

    def green(self) -> bool:
        return not self.error and self.exit == 0 and not self.failures


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


def _unique(check: dict, ids) -> list:
    """Unique, first-seen order; without a keyed list the qualifier is dropped (core ``dedup``)."""
    out: list = []
    for q, i in ids:
        key = (q if _keyed(check) else "", i)
        if i and key not in out:
            out.append(key)
    return out


def _results_env(check: dict) -> dict:
    """``results.how.env`` applies only to runs whose results are read (core ``results_exec``);
    the list and version runs get the plain environment."""
    return {**os.environ, **check.get("results", {}).get("how", {}).get("env", {})}


def execute(check: dict, workdir: Path, argv: list[str], timeout: int) -> Outcome:
    """A results run, as the interpreter makes it: ``argv`` composed with ``results.how.argvAppend``."""
    results = check["results"]
    how = results.get("how", {})
    full = compose(list(argv), list(how.get("argvAppend", [])))
    result_file = (workdir / how["path"]) if how.get("path") else None
    if result_file is not None and result_file.exists():
        result_file.unlink()
    try:
        proc = _capture(full, workdir, _results_env(check), bool(how.get("merge")), timeout)
    except FileNotFoundError:
        return Outcome(None, [], None, f"{full[0]!r} is not on PATH")
    except subprocess.TimeoutExpired:
        return Outcome(None, [], None, f"did not finish within {timeout}s")
    if result_file is not None:
        if not result_file.exists():
            return Outcome(proc.returncode, [], None, f"`{how['path']}` could not be opened")
        text = result_file.read_text(encoding="utf-8", errors="replace")
    else:
        text = proc.stdout
    if results["kind"] == "text":
        return Outcome(proc.returncode, _unique(check, sorted(parse_text(check["parser"], text))), None)
    try:
        every, failed = parse_junit(text, results.get("id"), results.get("idJoin", "::"))
    except ValueError as exc:  # no <testsuite>
        return Outcome(proc.returncode, [], None, str(exc))
    except Exception as exc:  # noqa: BLE001 - any unreadable report is a probe failure, named
        return Outcome(proc.returncode, [], None, f"the results do not parse as JUnit ({exc.__class__.__name__})")
    every = [(q if _keyed(check) else "", i) for q, i in every]  # each testcase on its own, no de-dup
    return Outcome(proc.returncode, _unique(check, sorted(failed)), every)


def _inject(workdir: Path, mutation: dict) -> str | None:
    """Write a mutation file inside the scratch copy, never through a link (as core writes through
    its held directory): ``None`` when written, else why not."""
    rel = PurePosixPath(mutation["file"])
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return f"the mutation file `{rel}` is not inside the check's directory"
    cur = workdir
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            return f"the mutation file `{rel}` would be written through the link `{part}`"
        cur.mkdir(exist_ok=True)
    target = cur / rel.name
    if target.is_symlink():
        return f"the mutation file `{rel}` is a link"
    target.write_text(mutation["content"], encoding="utf-8")
    return None


def inventory(check: dict, workdir: Path, timeout: int, deselect: list[Failure] | None = None) -> list | str:
    """The list run (with ``deselect`` ids deselected, when given): its ids, or why it is incomplete."""
    spec = check["list"]
    argv = deselected(check["deselect"]["append"], spec["run"], deselect) if deselect else list(spec["run"])
    try:
        proc = _capture(argv, workdir, dict(os.environ), bool(spec.get("merge")), timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"its list could not run ({exc.__class__.__name__})"
    if proc.returncode != 0:
        return f"its list did not exit 0 (exit {proc.returncode})"
    ids = parse_list(spec, proc.stdout)
    if not ids and not deselect:
        return "its list names no test"
    return ids


def _failed_exit(check: dict, code: int | None) -> bool:
    """A NONZERO exit the guide calls a test failure (core ``failed_exit``)."""
    return code is not None and code != 0 and code in check["failedExit"]


def _verdict(ok: bool, why: str) -> str:
    return "pass" if ok else f"fail: {why}"


def _is(t: Failure, m: dict) -> bool:
    return t[1] == m["expectId"] and m.get("expectQ") in (None, t[0])


AFTER_RUN = ("ids", "alone", "deselect", "mutation", "multi")


def _deselects_exactly(check: dict, workdir: Path, listed, ids: list, timeout: int) -> bool:
    """Each of ``ids`` is listed exactly once (else deselecting it proves nothing), and the list
    deselecting them lists exactly the rest."""
    if not isinstance(listed, list) or any(listed.count(i) != 1 for i in ids):
        return False
    rest = inventory(check, workdir, timeout, deselect=ids)
    return isinstance(listed, list) and isinstance(rest, list) and \
        sorted(rest) == sorted(t for t in listed if t not in ids)


def _probes(check: dict, workdir: Path, timeout: int) -> dict:
    """One attempt of the core probes, in its order, on ``workdir`` (a fresh copy)."""
    out: dict[str, str] = {}

    def fail_rest(why: str) -> dict:
        # Every probe not yet decided fails with `why` (`affected` too, when the check has it).
        for p in AFTER_RUN + (("affected",) if "affected" in check else ()):
            out.setdefault(p, f"fail: {why}")
        return out

    run_argv = list(check["run"])
    # core's alone_argv: {id}, {q}, {id:re} and {ids:re|} (this one id, escaped) in one pass
    alone = lambda t: substitute(check["alone"]["run"], id=t[1], q=t[0])  # noqa: E731
    desel = lambda ids: deselected(check["deselect"]["append"], run_argv, ids)  # noqa: E731
    listed0 = inventory(check, workdir, timeout)
    out["list"] = _verdict(isinstance(listed0, list), str(listed0))
    clean = execute(check, workdir, run_argv, timeout)
    out["run"] = _verdict(clean.green(), clean.error or f"needs a green base: the clean run exited {clean.exit} "
                                                       f"with {len(clean.failures)} parsed failure(s)")
    probes = check.get("probes", {})
    for piece, present in (("alone", "alone" in check), ("deselect", "deselect" in check),
                           ("probes.mutation", "mutation" in probes), ("probes.mutation2", "mutation2" in probes)):
        if not present:
            return fail_rest(f"no `{piece}`")
    if not clean.green():
        return fail_rest("needs a green base")
    m, m2 = probes["mutation"], probes["mutation2"]
    refused = _inject(workdir, m)
    if refused:
        return fail_rest(refused)
    mutated = execute(check, workdir, run_argv, timeout)
    if mutated.error or not _failed_exit(check, mutated.exit) or len(mutated.failures) != 1 \
            or not _is(mutated.failures[0], m):
        return fail_rest(f"the mutated run (exit {mutated.exit}) named {mutated.failures[:5]}, "
                         f"not exactly `{m['expectId']}`")
    t = mutated.failures[0]
    out["mutation"] = _verdict(execute(check, workdir, desel([t]), timeout).green(),
                               f"deselecting `{t[1]}` did not run green")
    refused = _inject(workdir, m2)
    if refused:
        out["multi"] = f"fail: {refused}"
    listed = inventory(check, workdir, timeout)
    both = execute(check, workdir, run_argv, timeout)
    pair = both.failures if (not both.error and _failed_exit(check, both.exit) and len(both.failures) == 2
                             and t in both.failures and any(x != t and _is(x, m2) for x in both.failures)) else []
    out.setdefault("multi", "")
    out["multi"] = out["multi"] or _verdict(bool(pair) and execute(check, workdir, desel(pair), timeout).green()
                            and _deselects_exactly(check, workdir, listed, pair, timeout),
                            f"with both mutations: {both.failures[:5]} (exit {both.exit}); both must be named, and "
                            "deselecting both must run green and list exactly the rest")
    reported = list(clean.every or []) + list(both.every or []) + list(both.failures)
    if not isinstance(listed, list):
        out["ids"] = f"fail: {listed}"
    else:
        stray = next((x for x in reported if x not in listed), None)
        out["ids"] = _verdict(bool(reported) and stray is None,
                              f"the results name `{stray[1]}` (q `{stray[0]}`), which the list does not" if stray
                              else "the results named no test")
    junit = check["results"]["kind"] == "junit"

    def exactly(o: Outcome, want: Failure, failing: bool) -> bool:
        return (o.failures == [want] if failing else not o.failures) and (not junit or o.every == [want])

    alone_t = execute(check, workdir, alone(t), timeout)
    passing = next((x for x in listed if x[0] == t[0] and x != t and not _is(x, m2)), None) \
        if isinstance(listed, list) else None
    if alone_t.error:
        out["alone"] = f"fail: `{t[1]}` alone: {alone_t.error}"
    elif not (_failed_exit(check, alone_t.exit) and exactly(alone_t, t, True)):
        out["alone"] = f"fail: `{t[1]}` alone (exit {alone_t.exit}) did not fail naming exactly it"
    elif passing is None:
        out["alone"] = f"fail: no passing test beside `{t[1]}` under its qualifier"
    else:
        alone_p = execute(check, workdir, alone(passing), timeout)
        out["alone"] = _verdict(alone_p.exit == 0 and not alone_p.error and exactly(alone_p, passing, False),
                                f"`{passing[1]}` alone (exit {alone_p.exit}) did not run exactly it, green")
    out["deselect"] = (f"fail: no passing test beside `{t[1]}` under its qualifier" if passing is None else
                       _verdict(_deselects_exactly(check, workdir, listed, [passing], timeout),
                                f"the list deselecting `{passing[1]}` does not list exactly the rest"))
    if "affected" in check:
        aff = execute(check, workdir, expand_files(list(check["affected"]["run"]), [m["file"]]), timeout)
        out["affected"] = _verdict(_failed_exit(check, aff.exit) and t in aff.failures,
                                   f"the affected run did not fail with a `failedExit` naming `{t[1]}`")
    return out


def _version(check: dict, workdir: Path, timeout: int) -> tuple[str, str]:
    """(verdict, first output line) of the `version` piece, stdout and stderr merged, as core."""
    try:
        proc = _capture(check["version"]["run"], workdir, dict(os.environ), True, min(timeout, 120))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"fail: the version command did not pass ({exc.__class__.__name__})", ""
    line = next((ln.strip() for ln in proc.stdout.splitlines() if ln.strip()), "")
    if proc.returncode != 0:
        return f"fail: the version command did not pass (exit {proc.returncode})", ""
    if not line:
        return "fail: the version command printed nothing", ""
    return "pass", line


INSTALL_TIMEOUT = 2700


def _install_failed(install: dict, scratch: Path) -> str | None:
    """Run the guide's install step for the check's directory in this fresh copy, as core does
    before every probe: ``None`` when it passed, else why not."""
    try:
        proc = _capture(list(install["run"]), scratch / install.get("cwd", "."), dict(os.environ), True,
                        INSTALL_TIMEOUT)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"install failed ({exc.__class__.__name__})"
    return None if proc.returncode == 0 else f"install failed (exit {proc.returncode})"


def _all_failed(check: dict, why: str) -> dict:
    keys = ("list", "run") + AFTER_RUN + (("affected",) if "affected" in check else ()) + \
        (("version",) if "version" in check else ())
    return {p: f"fail: {why}" for p in keys}


def _attempt(check: dict, repo: Path, timeout: int, exclude: list[str], link: list[str],
             install: dict | None = None) -> tuple[dict, str]:
    # With an install step, nothing is linked to the host repo: the install writes into the copy,
    # never into the operator's node_modules or .venv.
    scratch = make_scratch(repo, exclude, [] if install else link)
    try:
        workdir = scratch / check.get("cwd", ".")
        why = _install_failed(install, scratch) if install else None
        if why:
            return _all_failed(check, why), ""
        results = _probes(check, workdir, timeout)
        version = ""
        if "version" in check:
            results["version"], version = _version(check, workdir, timeout)
        return results, version
    finally:
        shutil.rmtree(scratch.parent, ignore_errors=True)


def rehearse_check(check: dict, repo: Path, timeout: int, exclude: list[str], link: list[str],
                   install: dict | None = None) -> dict:
    """The core probe's pieces; when any fails (other than for a missing piece), the whole attempt
    re-runs once on a fresh copy and its results are the result, each marked `` (retried)``. The
    guide's ``install`` step for the same ``cwd`` runs first in every copy (core: an install that
    fails fails every probe)."""
    if "list" not in check:
        return {"name": check["name"], "skipped": "no `list` piece: a gate (exit code only), not probed",
                "ok": True}
    results, version = _attempt(check, repo, timeout, exclude, link, install)
    if any(not passed(r) and not r.startswith("fail: no `") for r in results.values()):
        second, version = _attempt(check, repo, timeout, exclude, link, install)
        results = {p: f"{r} (retried)" for p, r in second.items()}
    return {"name": check["name"], "results": results, "runnerVersion": version,
            "ok": all(passed(v) for v in results.values())}


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
    if not args.repo.is_dir():
        print(json.dumps({"rehearsal": True, "ok": False, "errors": [f"--repo {args.repo} is not a directory"]}))
        return 2
    repo = args.repo.resolve()
    try:
        guide = load_json(args.guide)
    except (OSError, ValueError) as exc:
        print(json.dumps({"rehearsal": True, "ok": False, "errors": [f"cannot read the guide: {exc}"]}))
        return 2
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
    def install_for(check: dict) -> dict | None:
        where = PurePosixPath(str(check.get("cwd", ".")))
        return next((c for c in guide["checks"] if c.get("name") == "install" and c is not check
                     and PurePosixPath(str(c.get("cwd", "."))) == where), None)

    reports = [rehearse_check(c, repo, args.timeout, exclude, link, install_for(c)) for c in checks]
    ok = all(r["ok"] for r in reports)
    print(json.dumps({"rehearsal": True, "note": NOTE, "ok": ok, "checks": reports}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
