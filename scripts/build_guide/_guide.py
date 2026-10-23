"""Shared reading of a build/test guide (`.wicked/build-guide.json`, DES-BUILD-GUIDE contract v1).

Three things live here, used by check.py and rehearse.py:

* ``schema_errors`` — the guide against the contract schema, ``schemas/build-guide.v1.json``,
  vendored byte for byte from wicked-core (the interpreter's owner). The schema layer is the
  repo's own stdlib draft subset validator (``domain.validate_domain_model._validate``); a schema
  that uses a keyword that validator does not implement is refused rather than half-checked.
* ``lint`` — what the schema does not say: regexes compile and stay inside RE2 (a rule that is
  not anchored ``^...$`` is a warning), the named groups exist, the templates carry their
  placeholders, paths are repo-relative, a draft carries no ``verified`` (only
  ``wicked-core floor probe`` writes it; the skill only fills its blank ``runnerVersion``), and
  what the FLOOR requires is present — a non-empty ``failedExit``, ``alone``, ``deselect``, a
  ``text`` or ``junit`` results kind, a ``list`` — plus what the skill always writes
  (``derivedFrom``, two distinct mutation probes). The schema makes these optional; the floor
  will not use a check without them.
* ``parse_text`` / ``parse_junit`` / ``parse_list`` / ``deselect_tokens`` — a REHEARSAL of the
  core interpreter, following the semantics the schema's descriptions state (blocks, JUnit
  ``id``/``idJoin``, deselect composition, ``merge``). wicked-core's interpreter is authoritative;
  what this reading decides that the schema leaves open is listed in the build-guide skill's
  ``refs/contract-notes.md``.

Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from domain.validate_domain_model import _validate  # noqa: E402

SCHEMA = _REPO_ROOT / "schemas" / "build-guide.v1.json"
# Where the vendored schema came from: wicked-core#1066's branch, not yet merged.
SCHEMA_SOURCE = "wicked-core feat/floor-v2-exit-codes@f88a639 schemas/build-guide.v1.json (unmerged, #1066)"
# The probes the floor requires to have passed before it relies on a check (core REQUIRED_PROBES),
# plus `affected` when the check has that piece.
REQUIRED_PROBES = ("list", "run", "ids", "alone", "deselect", "mutation", "multi")
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
UNAVAILABLE = "probe unavailable: the guide is unverified, so the floor will not use it for exclusion"
PLACEHOLDERS = ("{id}", "{q}")

# Keywords the subset validator implements, plus annotation-only keywords it may ignore.
_VALIDATED = {"$ref", "type", "const", "enum", "minLength", "pattern", "minimum", "maximum",
              "minItems", "items", "required", "properties", "additionalProperties", "if", "then"}
_ANNOTATIONS = {"$schema", "$id", "$comment", "$defs", "title", "description", "examples", "default"}

# RE2 rejects these Python-regex constructs (lookaround, backreferences, atomic and possessive
# forms, conditionals). A parser must stay inside RE2 because the core interpreter is Rust.
_NOT_RE2 = [
    (re.compile(r"\(\?<?[=!]"), "lookaround"),
    (re.compile(r"\\[1-9]"), "backreference"),
    (re.compile(r"\(\?P="), "named backreference"),
    (re.compile(r"\(\?>"), "atomic group"),
    (re.compile(r"[*+?}][+]"), "possessive quantifier"),
    (re.compile(r"\(\?\("), "conditional"),
]


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def unsupported_schema_keywords(node: Any, path: str = "") -> list[str]:
    """Every schema keyword the subset validator would silently ignore."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, val in node.items():
            here = f"{path}/{key}"
            if key in ("properties", "$defs"):
                for name, sub in (val or {}).items():
                    found += unsupported_schema_keywords(sub, f"{here}/{name}")
                continue
            if key not in _VALIDATED and key not in _ANNOTATIONS:
                found.append(here)
            if isinstance(val, (dict, list)) and key not in ("enum", "const", "required", "examples", "default"):
                found += unsupported_schema_keywords(val, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found += unsupported_schema_keywords(item, f"{path}/{i}")
    return found


def schema_errors(guide: Any, schema: dict[str, Any]) -> list[str]:
    unsupported = unsupported_schema_keywords(schema)
    if unsupported:
        return [f"schema uses keywords this validator does not implement: {', '.join(unsupported)}"]
    errors: list[str] = []
    _validate(guide, schema, "", schema, errors)
    return errors


ANCHOR_NOTE = "not anchored ^...$"


def _regex_problems(where: str, pattern: str, groups: Iterable[str]) -> list[str]:
    """Problems with one rule. One whose text contains ``ANCHOR_NOTE`` is a warning, not an error."""
    out: list[str] = []
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return [f"{where}: does not compile ({exc})"]
    for rx, what in _NOT_RE2:
        if rx.search(pattern):
            out.append(f"{where}: uses a {what}, which RE2 does not support")
    if not (pattern.startswith("^") and pattern.endswith("$")):
        out.append(f"{where}: not anchored ^...$; the interpreter searches each line, so it also matches "
                   "inside longer lines")
    for group in groups:
        if group not in compiled.groupindex:
            out.append(f"{where}: needs a (?P<{group}>...) group")
    return out


def _repo_relative(where: str, value: str) -> list[str]:
    p = PurePosixPath(value)
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value) or ".." in p.parts:
        return [f"{where}: {value!r} must be repo-relative, with no '..'"]
    return []


def _has_placeholder(argv: list[str]) -> bool:
    return any(p in a for a in argv for p in PLACEHOLDERS)


def _lint_parser(at: str, parser: dict) -> list[str]:
    errors: list[str] = []
    if not parser.get("failed") and not parser.get("blocks"):
        errors.append(f"{at}.parser: needs failed rules or blocks, or it can never name a failure")
    if "section" in parser:
        errors += _regex_problems(f"{at}.parser.section", parser["section"], ["q"])
    for r, rx in enumerate(parser.get("failed", [])):
        errors += _regex_problems(f"{at}.parser.failed[{r}]", rx, ["id"])
    for b, block in enumerate(parser.get("blocks", [])):
        for key in ("start", "end"):
            errors += _regex_problems(f"{at}.parser.blocks[{b}].{key}", block.get(key, ""), [])
        errors += _regex_problems(f"{at}.parser.blocks[{b}].item", block.get("item", ""), ["id"])
    return errors


def _lint_check(at: str, check: dict, repo: Path | None, draft: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    cwd = check.get("cwd", ".")
    errors += _repo_relative(f"{at}.cwd", cwd)
    if repo is not None and not (repo / cwd).is_dir():
        errors.append(f"{at}.cwd: {cwd!r} is not a directory in the repo")
    for key in ("failedExit", "list", "alone", "deselect"):
        if not check.get(key):
            errors.append(f"{at}.{key}: missing or empty; the floor will not use this check without it")
    run = check.get("run", [])
    if len(run) == 1 and " " in run[0]:
        warnings.append(f"{at}.run: one token with spaces looks like a shell string; run is an exact argv")
    for where, argv in (("run", run), ("list.run", check.get("list", {}).get("run", [])),
                        ("alone.run", check.get("alone", {}).get("run", []))):
        if argv and PurePosixPath(argv[0]).name in SHELLS:
            warnings.append(f"{at}.{where}: runs through a shell ({argv[0]}); argv never passes through a "
                            "shell, so name the runner itself")
    results = check.get("results", {})
    kind = results.get("kind")
    parser = check.get("parser")
    if kind == "text" and parser is None:
        errors.append(f"{at}.parser: results.kind=text needs a parser")
    if kind != "text" and parser is not None:
        errors.append(f"{at}.parser: a parser is only for results.kind=text (kind is {kind!r})")
    if kind != "junit" and ("id" in results or "idJoin" in results):
        errors.append(f"{at}.results: id/idJoin are only for results.kind=junit")
    if kind in ("json-lines", "tap"):
        errors.append(f"{at}.results.kind: {kind} is reserved in v1; the floor reads only text and junit")
    path = results.get("how", {}).get("path")
    if path:
        errors += _repo_relative(f"{at}.results.how.path", path)
    if isinstance(parser, dict):
        errors += _lint_parser(at, parser)
    lst = check.get("list", {})
    if "item" in lst:
        errors += _regex_problems(f"{at}.list.item", lst["item"], ["id"])
    if "section" in lst:
        errors += _regex_problems(f"{at}.list.section", lst["section"], ["q"])
    if "alone" in check and not _has_placeholder(check["alone"].get("run", [])):
        errors.append(f"{at}.alone.run: needs an {{id}} (or {{q}}) placeholder")
    if "deselect" in check and not _has_placeholder(check["deselect"].get("append", [])):
        errors.append(f"{at}.deselect.append: needs an {{id}} (or {{q}}) placeholder")
    if "affected" in check and not any("{files}" in a for a in check["affected"].get("run", [])):
        errors.append(f"{at}.affected.run: needs a {{files}} placeholder")
    probes = check.get("probes", {})
    for key, probe in (("mutation", "mutation"), ("mutation2", "multi")):
        mutation = probes.get(key)
        if not mutation:
            errors.append(f"{at}.probes.{key}: missing; the `{probe}` probe the floor requires cannot pass without it")
            continue
        errors += _repo_relative(f"{at}.probes.{key}.file", mutation.get("file", ""))
        if repo is not None and mutation.get("file") and (repo / cwd / mutation["file"]).exists():
            warnings.append(f"{at}.probes.{key}.file: {mutation['file']!r} exists; "
                            "the probe would overwrite a real file — inject a new one")
    m1, m2 = probes.get("mutation") or {}, probes.get("mutation2") or {}
    if m1 and m2 and (m1.get("file") == m2.get("file") or
                      (m1.get("expectId"), m1.get("expectQ")) == (m2.get("expectId"), m2.get("expectQ"))):
        errors.append(f"{at}.probes.mutation2: must be a second, distinct failing test (another file, another id)")
    verified = check.get("verified")
    if draft and verified is not None:
        errors.append(f"{at}.verified: a draft carries no verified; only `wicked-core floor probe` writes it")
    elif verified is not None:
        needed = list(REQUIRED_PROBES) + (["affected"] if "affected" in check else [])
        results = verified.get("results", {})
        unpassed = [f"{p}: {results.get(p, 'never ran')}" for p in needed if results.get(p) != "pass"]
        if unpassed:
            warnings.append(f"{at}.verified: the floor will not rely on this check ({'; '.join(unpassed)})")
        if not verified.get("runnerVersion"):
            warnings.append(f"{at}.verified.runnerVersion: blank; fill it from `<runner> --version` before proposing")
    return errors, warnings


def lint(guide: dict[str, Any], repo: Path | None = None, draft: bool = False) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) the schema does not express."""
    errors: list[str] = []
    warnings: list[str] = []
    if not guide.get("derivedFrom"):
        errors.append("derivedFrom: missing or empty; record the CI files and manifests the guide came from")
    for i, rel in enumerate(guide.get("derivedFrom", [])):
        errors += _repo_relative(f"derivedFrom[{i}]", rel)
        if repo is not None and not (repo / rel).exists():
            errors.append(f"derivedFrom[{i}]: {rel!r} does not exist in the repo")
    names: set[str] = set()
    for c, check in enumerate(guide.get("checks", [])):
        at = f"checks[{c}]({check.get('name', '?')})"
        if check.get("name") in names:
            errors.append(f"{at}: duplicate check name")
        names.add(check.get("name"))
        e, w = _lint_check(at, check, repo, draft)
        errors += [x for x in e if ANCHOR_NOTE not in x]
        warnings += w + [x for x in e if ANCHOR_NOTE in x]
    if not guide.get("checks"):
        errors.append("checks: empty; with no check there is no guide (say so instead)")
    return errors, warnings


# --- results reading (rehearsal of the core interpreter) ------------------------------------

Failure = tuple[str, str]  # (q, id); q is "" when the guide has no qualifier


def _lines(text: str) -> list[str]:
    return [ln.rstrip("\r") for ln in text.split("\n")]


def _match(pattern: str | None, line: str) -> re.Match | None:
    # The core interpreter searches each line (Regex::is_match / captures), so does this.
    return re.search(pattern, line) if pattern else None


class _BlockState:
    """One ``blocks`` rule. A block is the contiguous item lines (blank lines allowed) after a
    start; any other line ends it. At an end, the last block since the previous end
    (``last-before-end``, the default) or every one (``all``) is taken."""

    def __init__(self, rule: dict):
        self.rule = rule
        self.since_end: list[list[Failure]] = []
        self.current: list[Failure] | None = None

    def _close(self) -> None:
        if self.current is not None:
            self.since_end.append(self.current)
            self.current = None

    def feed(self, line: str, q: str) -> list[Failure]:
        if _match(self.rule["end"], line):
            self._close()
            taken = self.since_end if self.rule.get("use", "last-before-end") == "all" else self.since_end[-1:]
            self.since_end = []
            return [f for block in taken for f in block]
        if _match(self.rule["start"], line):
            self._close()
            self.current = []
            return []
        if self.current is not None:
            if not line.strip():
                return []
            item = _match(self.rule["item"], line)
            if item:
                self.current.append((q, item.group("id")))
            else:
                self._close()
        return []


def parse_text(parser: dict[str, Any], text: str) -> set[Failure]:
    """Failures named by a text parser: per-line ``failed`` rules plus ``blocks``. ``section``
    sets the qualifier ``q`` for every id until the next section line."""
    found: set[Failure] = set()
    q = ""
    blocks = [_BlockState(rule) for rule in parser.get("blocks", [])]
    for line in _lines(text):
        m = _match(parser.get("section"), line)
        if m:
            q = m.group("q") or ""
        for rx in parser.get("failed", []):
            fm = _match(rx, line)
            if fm:
                found.add((q, fm.group("id")))
        for state in blocks:
            found.update(state.feed(line, q))
    return {f for f in found if f[1]}


def parse_junit(xml_text: str, id_attrs: list[str] | None = None, join: str = "::") -> tuple[list[Failure], set[Failure]]:
    """(every testcase that ran, failed testcases), as the core reader takes them: the id is the
    ``results.id`` attributes (default classname, name) joined by ``results.idJoin`` (default
    ``::``), q is the enclosing testsuite's ``name``; a testcase with a ``<skipped/>`` child neither
    passed nor failed (a filter left it out); one with ``<failure>`` or ``<error>`` failed."""
    attrs = id_attrs or ["classname", "name"]
    root = ET.fromstring(xml_text)
    every: list[Failure] = []
    failed: set[Failure] = set()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    for suite in suites:
        for case in suite.iter("testcase"):
            key = (suite.get("name", ""), join.join(case.get(a, "") for a in attrs))
            if not key[1]:
                continue
            if case.find("failure") is not None or case.find("error") is not None:
                failed.add(key)
            if case.find("skipped") is None:
                every.append(key)
    return every, failed


def parse_list(spec: dict[str, Any], text: str) -> list[Failure]:
    """Ids the suite's own TOC names, in its order (``list.item``; ``q`` from ``list.section``)."""
    ids: list[Failure] = []
    q = ""
    for line in _lines(text):
        sm = _match(spec.get("section"), line)
        if sm:
            q = sm.group("q") or ""
            continue
        im = _match(spec["item"], line)
        if im:
            ids.append((q, im.group("id")))
    return ids


def substitute(argv: list[str], **values: str) -> list[str]:
    out = []
    for token in argv:
        for key, val in values.items():
            token = token.replace("{" + key + "}", val)
        out.append(token)
    return out


def deselect_tokens(append: list[str], failures: list[Failure], argv: list[str]) -> list[str]:
    """The schema's composition: tokens before the first one with ``{id}``/``{q}`` once (a leading
    ``--`` only when ``argv`` has none), the tokens through the last such one once per id, the rest once."""
    marked = [i for i, tok in enumerate(append) if any(p in tok for p in PLACEHOLDERS)]
    if not marked:
        return list(append)
    first, last = marked[0], marked[-1]
    prefix = list(append[:first])
    if prefix and prefix[0] == "--" and "--" in argv:
        prefix = prefix[1:]
    middle: list[str] = []
    for q, ident in failures:
        middle += substitute(append[first:last + 1], id=ident, q=q)
    return prefix + middle + list(append[last + 1:])


def expand_files(argv: list[str], files: list[str]) -> list[str]:
    """A token that is exactly ``{files}`` becomes one token per file; elsewhere they join with spaces."""
    out: list[str] = []
    for token in argv:
        if token == "{files}":
            out += files
        else:
            out.append(token.replace("{files}", " ".join(files)))
    return out
