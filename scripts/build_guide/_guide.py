"""Shared reading of a build/test guide (`.wicked/build-guide.json`, DES-BUILD-GUIDE contract v1).

Three things live here, used by check.py and rehearse.py:

* ``schema_errors`` — the guide against the contract schema, ``schemas/build-guide.v1.json``,
  vendored byte for byte from wicked-core (the interpreter's owner). The schema layer is the
  repo's own stdlib draft subset validator (``domain.validate_domain_model._validate``); a schema
  that uses a keyword that validator does not implement is refused rather than half-checked.
* ``lint`` — what the schema does not say: regexes compile and stay inside RE2 (a rule that is
  not anchored ``^...$`` is a warning), the named groups exist, the templates carry their
  placeholders, paths are repo-relative, a draft carries no ``verified`` (only
  ``wicked-core floor probe`` writes it, including ``runnerVersion`` from the ``version`` piece), and
  what the FLOOR requires of a test check (one with ``list``) is present — a non-empty
  ``failedExit``, ``alone``, ``deselect``, a ``text`` or ``junit`` results kind — plus what the
  skill always writes (``derivedFrom``, ``version``, two distinct mutation probes). A check with
  no ``list`` is a gate (install, build, format, lint, typecheck): exit code only, never probed.
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
# Where the vendored schema came from: wicked-core main (the file last changed in #1066).
SCHEMA_SOURCE = "wicked-core main@72da31b schemas/build-guide.v1.json (landed in #1066 as e88ea6a)"
# The probes the floor requires to have passed before it relies on a check (core REQUIRED_PROBES),
# plus `affected` when the check has that piece.
REQUIRED_PROBES = ("list", "run", "ids", "alone", "deselect", "mutation", "multi")
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
UNAVAILABLE = "probe unavailable: the guide is unverified, so the floor will not use it for exclusion"
# Per-id placeholders (their token repeats once per id) and the all-ids one (its token is added once).
PLACEHOLDERS = ("{id}", "{q}", "{id:re}")
ALL_IDS = "{ids:re|}"
# The characters Rust's regex::escape escapes (the core interpreter's escape).
_RE_META = set("\\.+*?()|[]{}^$#&-~")

# Keywords the subset validator implements, plus annotation-only keywords it may ignore.
_VALIDATED = {"$ref", "type", "const", "enum", "minLength", "pattern", "minimum", "maximum",
              "minItems", "items", "required", "dependentRequired", "not", "properties", "additionalProperties",
              "propertyNames", "if", "then"}
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
            if isinstance(val, (dict, list)) and key not in ("enum", "const", "required", "examples", "default",
                                                                    "dependentRequired"):
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
    # An escaped character is a literal (`C\++` is a literal `+` then a quantifier): judge the
    # constructs on the pattern with every `\x` pair masked, except a backreference, which IS one.
    masked = re.sub(r"\\[^1-9]", "__", pattern)
    for rx, what in _NOT_RE2:
        if rx.search(masked):
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


def cwd_ok(cwd: str) -> bool:
    """core's ``cwd_ok``: ``.``, or relative ``/``-separated segments, none empty, ``.`` or ``..``,
    and no ``\\`` or ``:`` (no Windows drive, ``C:x`` included). ``""`` is refused."""
    return cwd == "." or not (cwd.startswith("/") or "\\" in cwd or ":" in cwd
                              or any(seg in ("", ".", "..") for seg in cwd.split("/")))


def name_ok(name: Any) -> bool:
    """core's ``name_ok``: 1-64 of ``A-Z a-z 0-9 . _ -``, never ``.`` or ``..`` (it keys files)."""
    return (isinstance(name, str) and 1 <= len(name) <= 64 and name not in (".", "..")
            and re.fullmatch(r"[A-Za-z0-9._-]+", name) is not None)


# core's ``env_name_ok``: the shape, and never a loader or shell hook.
_ENV_HOOKS = {"BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "IFS", "GCONV_PATH", "LOCPATH"}


def env_name_ok(name: str) -> bool:
    return (re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) is not None and not name.startswith(("LD_", "DYLD_"))
            and name not in _ENV_HOOKS)


def _pathspec_matches(repo: Path, spec: str) -> bool:
    """Does a ``derivedFrom`` entry (a git pathspec; globs such as ``crates/*/Cargo.toml``) match?"""
    if not any(c in spec for c in "*?["):
        return (repo / spec).exists()
    return any(True for _ in repo.glob(spec))


def _has_placeholder(argv: list[str]) -> bool:
    return any(p in a for a in argv for p in PLACEHOLDERS + (ALL_IDS,))


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


def passed(result: str) -> bool:
    """A probe result the floor counts as passed (core: `pass`, or `pass (retried)`)."""
    return result in ("pass", "pass (retried)")


def _lint_common(at: str, check: dict, repo: Path | None) -> tuple[list[str], list[str]]:
    """What every check needs, a gate (no `list`) or a test check."""
    errors: list[str] = []
    warnings: list[str] = []
    # The load-time checks the floor and the probe both make (core ``floor_guide::parse``): a guide
    # failing one does not load at all, and detection is the whole floor.
    load = "the floor would not load this guide: the check has "
    tokens = check.get("deselect", {}).get("append", [])
    first, last = per_id_range(tokens)
    if not check.get("run"):
        errors.append(f"{at}.run: {load}an empty `run`")
    if any(s not in ("creator", "verify") for s in check.get("stage", [])):
        errors.append(f"{at}.stage: {load}a `stage` other than `creator` / `verify`")
    if "list" in check and not check.get("failedExit"):
        errors.append(f"{at}.failedExit: {load}a `list` and no `failedExit`")
    if 0 in check.get("failedExit", []):
        errors.append(f"{at}.failedExit: {load}`0` in `failedExit` (a failure exits nonzero)")
    if not name_ok(check.get("name")):
        errors.append(f"{at}.name: {load}a name that is not 1-64 of `A-Z a-z 0-9 . _ -` (or is `.` or `..`)")
    bad_env = [k for k in check.get("results", {}).get("how", {}).get("env", {}) if not env_name_ok(k)]
    if bad_env:
        errors.append(f"{at}.results.how.env: {load}env {bad_env[0]!r}: names are `[A-Z_][A-Z0-9_]*`, and never "
                      "a loader or shell hook (`LD_*`, `DYLD_*`, `BASH_ENV`, `ENV`, …)")
    if not cwd_ok(check.get("cwd", ".")):
        errors.append(f"{at}.cwd: {load}a `cwd` that is absolute, climbs (`..`) or has an empty segment")
    if any(ALL_IDS in t for t in tokens[first:last]):
        errors.append(f"{at}.deselect.append: {load}`{{ids:re|}}` among the per-id tokens of `deselect.append` "
                      "(it is once-only)")
    elif any(ALL_IDS in t for t in tokens) and any("{q}" in t for t in tokens):
        errors.append(f"{at}.deselect.append: {load}`{{ids:re|}}` and `{{q}}` in one `deselect.append` (the "
                      "pattern cannot bind ids to qualifiers)")
    cwd = check.get("cwd", ".")
    errors += _repo_relative(f"{at}.cwd", cwd)
    if repo is not None and not (repo / cwd).is_dir():
        errors.append(f"{at}.cwd: {cwd!r} is not a directory in the repo")
    run = check.get("run", [])
    if len(run) == 1 and " " in run[0]:
        warnings.append(f"{at}.run: one token with spaces looks like a shell string; run is an exact argv")
    for where, argv in (("run", run), ("list.run", check.get("list", {}).get("run", [])),
                        ("alone.run", check.get("alone", {}).get("run", [])),
                        ("version.run", check.get("version", {}).get("run", []))):
        if argv and PurePosixPath(argv[0]).name in SHELLS:
            warnings.append(f"{at}.{where}: runs through a shell ({argv[0]}); fine for a compound CI step, "
                            "but a test check's pieces never pass through a shell, so name the runner when you can")
    results = check.get("results", {})
    kind = results.get("kind")
    parser = check.get("parser")
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
    return errors, warnings


def _lint_gate(at: str, check: dict) -> tuple[list[str], list[str]]:
    """A check with no `list` piece (install, build, format, lint, typecheck): it gates on its exit
    code only and is not probed."""
    warnings: list[str] = []
    extra = [k for k in ("alone", "deselect", "probes", "affected") if k in check]
    if extra:
        warnings.append(f"{at}: has {', '.join(extra)} but no `list`, so it is a gate (exit code only) and "
                        "none of them is probed or used")
    return [], warnings


def _lint_test(at: str, check: dict, repo: Path | None, draft: bool) -> tuple[list[str], list[str]]:
    """A test check (it has `list`): everything the floor needs to exclude base failures."""
    errors: list[str] = []
    warnings: list[str] = []
    cwd = check.get("cwd", ".")
    for key in ("alone", "deselect"):
        if not check.get(key):
            errors.append(f"{at}.{key}: missing or empty; the floor will not use this check without it")
    if check.get("results", {}).get("kind") == "text" and check.get("parser") is None:
        errors.append(f"{at}.parser: results.kind=text needs a parser")
    lst = check.get("list", {})
    if "item" in lst:
        errors += _regex_problems(f"{at}.list.item", lst["item"], ["id"])
    if "section" in lst:
        errors += _regex_problems(f"{at}.list.section", lst["section"], ["q"])
    if "alone" in check and not _has_placeholder(check["alone"].get("run", [])):
        errors.append(f"{at}.alone.run: needs an {{id}} (or {{q}}, {{id:re}}) placeholder")
    if "deselect" in check and not _has_placeholder(check["deselect"].get("append", [])):
        errors.append(f"{at}.deselect.append: needs an {{id}} (or {{q}}, {{id:re}}, {{ids:re|}}) placeholder")
    if not check.get("version", {}).get("run"):
        warnings.append(f"{at}.version: missing; the skill writes the runner's own version command, so a "
                        "runner change marks the guide stale")
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
        needed = list(REQUIRED_PROBES) + [p for p in ("affected", "version") if p in check]
        results = verified.get("results", {})
        unpassed = [f"{p}: {results.get(p, 'never ran')}" for p in needed if not passed(results.get(p, ""))]
        if unpassed:
            warnings.append(f"{at}.verified: the floor will not rely on this check ({'; '.join(unpassed)})")
    return errors, warnings


def _lint_check(at: str, check: dict, repo: Path | None, draft: bool) -> tuple[list[str], list[str]]:
    errors, warnings = _lint_common(at, check, repo)
    e, w = _lint_test(at, check, repo, draft) if "list" in check else _lint_gate(at, check)
    if "list" not in check and draft and "verified" in check:
        e.append(f"{at}.verified: a draft carries no verified; only `wicked-core floor probe` writes it")
    return errors + e, warnings + w


def lint(guide: dict[str, Any], repo: Path | None = None, draft: bool = False) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) the schema does not express."""
    errors: list[str] = []
    warnings: list[str] = []
    if not guide.get("derivedFrom"):
        errors.append("derivedFrom: missing or empty; record the CI files and manifests the guide came from")
    for i, rel in enumerate(guide.get("derivedFrom", [])):
        relative = _repo_relative(f"derivedFrom[{i}]", rel)
        errors += relative
        if repo is not None and not relative and not _pathspec_matches(repo, rel):
            errors.append(f"derivedFrom[{i}]: {rel!r} matches nothing in the repo")
    # Unique per directory, as core keys them (one `install` per `cwd` is how a monorepo installs
    # each package it tests).
    names: set[tuple[str, Any]] = set()
    for c, check in enumerate(guide.get("checks", [])):
        at = f"checks[{c}]({check.get('name', '?')})"
        key = (str(PurePosixPath(str(check.get("cwd", ".")))), check.get("name"))
        if key in names:
            errors.append(f"{at}: duplicate check name in `{key[0]}`")
        names.add(key)
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
    """(every testcase that ran, failed testcases), as core's roxmltree reader takes them, with a
    real XML parser (CDATA, ``<system-out>`` and entities are text, never markup):

    * the id is the ``results.id`` attributes (default classname, name) joined by
      ``results.idJoin`` (default ``::``); a testcase whose id attributes are ALL empty is dropped;
    * q is the NEAREST enclosing ``<testsuite>``'s ``name`` (suites may nest);
    * each ``<testcase>`` is judged on its own: one with a ``<skipped/>`` child is dropped (it
      neither passed nor failed), one with a ``<failure>`` or ``<error>`` child failed, and two
      that share an id and both ran are both counted.

    Raises ``ValueError`` when the text holds no ``<testsuite>`` ("the results hold no testsuite").
    """
    attrs = id_attrs or ["classname", "name"]
    root = ET.fromstring(xml_text)
    if root.tag != "testsuite" and root.find(".//testsuite") is None:
        raise ValueError("the results hold no testsuite")
    every: list[Failure] = []
    failed: set[Failure] = set()

    def walk(node: ET.Element, suite: str) -> None:
        for child in node:
            if child.tag == "testsuite":
                walk(child, child.get("name", ""))
            elif child.tag == "testcase":
                values = [child.get(a, "") for a in attrs]
                if all(not v for v in values) or child.find("skipped") is not None:
                    continue
                key = (suite, join.join(values))
                every.append(key)
                if child.find("failure") is not None or child.find("error") is not None:
                    failed.add(key)
            else:
                walk(child, suite)

    top = root
    if root.tag == "testsuite":  # a bare <testsuite> document: walk it as a child, so it is a suite
        top = ET.Element("results")
        top.append(root)
    walk(top, "")
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


def re_escape(text: str) -> str:
    """``text`` with every regex metacharacter backslash-escaped, as Rust's ``regex::escape``."""
    return "".join("\\" + c if c in _RE_META else c for c in text)


_SLOT = re.compile(r"\{(?:id|id:re|ids:re\||q)\}")


def substitute(argv: list[str], **values: str) -> list[str]:
    """Fill ``{id}``, ``{q}`` and ``{id:re}`` (the id regex-escaped) in every token, in ONE pass
    (as core's ``fill``): a value that itself contains ``{q}`` is not filled again."""
    escaped = re_escape(values["id"]) if "id" in values else None
    slots = {"{id}": values.get("id", "{id}"), "{q}": values.get("q", "{q}"),
             "{id:re}": escaped or "{id:re}", "{ids:re|}": escaped or "{ids:re|}"}
    return [_SLOT.sub(lambda m: slots[m.group(0)], token) for token in argv]


def compose(argv: list[str], extra: list[str]) -> list[str]:
    """``argv`` with ``extra`` added around its end of options, as core's ``compose``: ``extra``'s
    tokens before its own ``--`` (all of them when it has none) are the runner's options and go
    just before ``argv``'s ``--`` (at the end when it has none); the tokens after that ``--`` go
    last, behind ONE ``--``. A second ``--`` is never emitted."""
    i = extra.index("--") if "--" in extra else None
    opts, tail = (extra, None) if i is None else (extra[:i], extra[i + 1:])
    out = list(argv)
    at = out.index("--") if "--" in out else len(out)
    out[at:at] = opts
    if tail is not None:
        if "--" not in out:
            out.append("--")
        out += [t for t in tail if t != "--"]
    return out


def per_id_range(tokens: list[str]) -> tuple[int, int]:
    """From the first token with ``{id}``, ``{id:re}`` or ``{q}`` through the last one."""
    marked = [i for i, tok in enumerate(tokens) if any(p in tok for p in PLACEHOLDERS)]
    return (marked[0], marked[-1] + 1) if marked else (len(tokens), len(tokens))


def deselect_tokens(append: list[str], failures: list[Failure]) -> list[str]:
    """``deselect.append`` filled for ``failures``: tokens before the first per-id token once, the
    per-id tokens once per id, the rest once; ``{ids:re|}`` (every id regex-escaped, joined by
    ``|``) fills a once-token. Compose the result onto an argv with ``compose``."""
    joined = "|".join(re_escape(ident) for _q, ident in failures)
    fill_all = lambda tokens: [t.replace(ALL_IDS, joined) for t in tokens]  # noqa: E731
    first, last = per_id_range(append)
    middle: list[str] = []
    for q, ident in failures:
        middle += substitute(append[first:last], id=ident, q=q)
    return fill_all(append[:first]) + middle + fill_all(append[last:])


def deselected(append: list[str], argv: list[str], failures: list[Failure]) -> list[str]:
    """``argv`` with ``failures`` deselected (core's ``deselected``)."""
    return compose(argv, deselect_tokens(append, failures))


def expand_files(argv: list[str], files: list[str]) -> list[str]:
    """A token that is exactly ``{files}`` becomes one token per file; elsewhere they join with spaces."""
    out: list[str] = []
    for token in argv:
        if token == "{files}":
            out += files
        else:
            out.append(token.replace("{files}", " ".join(files)))
    return out
