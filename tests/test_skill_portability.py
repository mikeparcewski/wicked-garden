"""Cross-CLI skill portability lint (F-079, design W4 §5.1) — fails the build on any violation.

Skill text is installed into very different layouts: the whole plugin under Claude Code,
a FLAT skills-only copy under Codex / Pi / OpenCode / Antigravity (no ``scripts/``, no venv,
siblings laid out by NAME, nested modules riding inside their parent), and wicked-crew's
read-only snapshot (+ its flat-by-name copilot view). Only Claude Code substitutes
``${CLAUDE_PLUGIN_ROOT}`` / ``${CLAUDE_SKILL_DIR}``; every other host passes them through
literally. So a skill's text must (1) refer to its OWN files by a base-directory-relative
path, (2) refer to OTHER skills by NAME (``wicked-garden-qe``) + skill-relative file, never
by a filesystem path, (3) reach the shared runtime only through the launcher
(``wicked-garden run scripts/<x> …``) and carry the standard ``## Runtime`` block, and
(4) write harness mechanics (Skill tool, forks, AskUserQuestion) with an inline fallback.

Two rule files, both DATA:

* ``tests/portability_rules.json`` — the CANONICAL parity fixture, vendored byte-for-byte
  from wicked-crew (``packages/crew/tests/fixtures/portability_rules.json``). Every regex,
  the fence walk, option skipping, bundle existence, ``../`` resolution and the six shared
  tokens come from it; ``derive()`` below is the Python port of that engine and every one
  of its ``cases[]`` is re-derived here (``test_canonical_case``). Nothing about the shared
  tokens is hand-coded in this file. ``tests/test_portability_fixture_parity.py`` pins the
  vendored bytes and re-computes the fixture's ``sha256_of_rules``.
* ``tests/portability_rules.garden.json`` — garden's extras on top: the exact ``## Runtime``
  block, the fallback sentences, the name resolver, the slash-form ban, the bare
  ``scripts/x.py <args>`` span extension of ``cwd-script``, the stricter bare-identifier
  check, and their own regression corpus.

Files under ``skills/`` are attributed to the DEEPEST skill directory that contains them
(nested modules are their own skills), exactly as crew's catalog does; the bundle universe
is crew's (support files outside ``skills/`` in the bundle closure + skills' own files). The
allowlist is EMPTY on purpose: a violation is fixed in the skill body
(``python3 scripts/wg/portability_codemod.py --dry-run`` shows the fix), never tolerated here.

Non-vacuity is inverted from the pre-12.33 suite: ZERO plugin-root / skill-dir-var refs under
``skills/``, MORE THAN 200 launcher calls, ZERO unresolved ``wicked-garden-*`` names.

Run it directly for the full report + counts: ``python3 tests/test_skill_portability.py``.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
CANON_PATH = Path(__file__).resolve().parent / "portability_rules.json"
GARDEN_PATH = Path(__file__).resolve().parent / "portability_rules.garden.json"
CANON = json.loads(CANON_PATH.read_text(encoding="utf-8"))
GARDEN = json.loads(GARDEN_PATH.read_text(encoding="utf-8"))

# --- canonical (shared with wicked-crew) — everything below is read from the fixture ------
MARKERS = CANON["markers"]
RX = {name: re.compile(src) for name, src in CANON["regex"].items()}
FENCE_OPEN = RX["fence_line"]
SHELL_LANGS = {lang.lower() for lang in CANON["fences"]["shell_langs"]}
RH_KEY = CANON["frontmatter"]["requires_harness_key"]          # "metadata.requires-harness"
RH_VALUE = CANON["frontmatter"]["requires_harness_value"]      # "claude"
SHARED_TOKENS = {rule["token"] for rule in CANON["rules"]}
TRAILING_PUNCT = ".,:"

# --- garden-only ----------------------------------------------------------------------
IDENTIFIERS = GARDEN["identifiers"]
GRX = {name: re.compile(src) for name, src in GARDEN["regex"].items()}
RUNTIME_BLOCK = GARDEN["launcher"]["runtime_block"]
FORK_SENTENCE = GARDEN["fallbacks"]["fork_worker_sentence"]
DISPATCH_SENTENCE = GARDEN["fallbacks"]["dispatch_sentence"]
DISPATCH_RE = re.compile(GARDEN["fallbacks"]["dispatch_trigger_regex"])
NOT_A_SKILL = GARDEN["fallbacks"]["skill_name_exemption_marker"]
SKIP_NAMES = {"__pycache__", ".DS_Store", "node_modules", ".venv"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
CONTEXT_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)
NAME_DECL_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Hit:
    token: str
    line: int
    detail: str


@dataclass(frozen=True)
class Violation:
    token: str
    file: str
    line: int
    detail: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.file}:{self.line}: [{self.token}] {self.detail}"


# ---------------------------------------------------------------------------
# The bundle: what exists, and who owns what (canonical `existence` semantics)
# ---------------------------------------------------------------------------

class Bundle:
    """The files the next publish carries. `exists` = a carried file, or a directory some
    carried file sits under, or the bare root. `owner` = the DEEPEST skill dir prefixing a path."""

    def __init__(self, files: Iterable[str], skill_dirs: Iterable[str]):
        self.files = set(files)
        self.dirs: set[str] = set()
        for f in self.files:
            parts = f.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))
        self.skill_dirs = sorted(set(skill_dirs), key=lambda d: (-d.count("/"), d))

    def exists(self, path: str) -> bool:
        return path == "" or path in self.files or path in self.dirs

    def owner(self, path: str) -> str | None:
        for d in self.skill_dirs:
            if path == d or path.startswith(d + "/"):
                return d
        return None

    @classmethod
    def from_case(cls, case: dict) -> "Bundle":
        files = case.get("exists") or CANON["bundle"]["files"]
        skill_dirs = {f[: -len("/SKILL.md")] for f in files if f.endswith("/SKILL.md")} | {case["skill_dir"]}
        return cls(files, skill_dirs)

    @classmethod
    def from_repo(cls, repo: Path = REPO) -> "Bundle":
        skill_dirs = {p.parent.relative_to(repo).as_posix() for p in (repo / "skills").rglob("SKILL.md")
                      if not any(part in SKIP_NAMES for part in p.parts)}
        deepest = sorted(skill_dirs, key=lambda d: -d.count("/"))
        files: set[str] = set()
        for p in repo.rglob("*"):
            if not p.is_file() or any(part in SKIP_NAMES for part in p.relative_to(repo).parts):
                continue
            rel = p.relative_to(repo).as_posix()
            if rel.startswith("skills/"):
                if any(rel.startswith(d + "/") for d in deepest):  # owner-less files under skills/ are never carried
                    files.add(rel)
            elif rel.startswith((".claude-plugin/", "schemas/", "docs/examples/")) or rel in ("pyproject.toml", "uv.lock"):
                files.add(rel)
            elif rel.startswith("scripts/") and not rel.startswith(("scripts/ci/", "scripts/wg/")):
                files.add(rel)
        return cls(files, skill_dirs)


# ---------------------------------------------------------------------------
# Path resolution (canonical `relative_resolution` + `existence.cwd_script_target`)
# ---------------------------------------------------------------------------

def _normalize(path: str) -> str | None:
    """Posix-normalize a plugin-relative path; None when it climbs out of the root."""
    if path in ("", "."):
        return ""
    n = posixpath.normpath(path)
    if n == ".":
        return ""
    if n == ".." or n.startswith("../"):
        return None
    return n.rstrip("/")


def plugin_root_target(after_marker: str | None) -> str | None:
    if not after_marker:
        return ""                                # the bare marker is the root
    return _normalize(after_marker.lstrip("/").rstrip(TRAILING_PUNCT))


def relative_target(token: str, file: str) -> str | None:
    joined = posixpath.join(posixpath.dirname(file), token.rstrip(TRAILING_PUNCT))
    return _normalize(joined)


def cwd_target(token: str) -> str | None:
    return _normalize(token)


# ---------------------------------------------------------------------------
# The fence walk (canonical `fences`)
# ---------------------------------------------------------------------------

def fence_walk(lines: list[str]) -> Iterator[tuple[int, str, bool, bool]]:
    """Yield (lineno, line, in_fence, fence_is_shell). Boundary lines are scanned as prose;
    a shorter run or a run followed by text does not close; an unclosed fence runs to EOF."""
    open_char: str | None = None
    open_len = 0
    shell = True
    for lineno, line in enumerate(lines, 1):
        if open_char is None:
            m = FENCE_OPEN.match(line)
            if m and (m.group(1) or m.group(2)):
                run = m.group(1) or m.group(2)
                open_char, open_len = run[0], len(run)
                shell = (m.group(3) or "").lower() in SHELL_LANGS
                yield lineno, line, False, True
                continue
            yield lineno, line, False, True
        else:
            if re.match(r"^\s*" + re.escape(open_char) + "{" + str(open_len) + r",}\s*$", line):
                open_char = None
                yield lineno, line, False, True
                continue
            yield lineno, line, True, shell


def requires_harness_line(text: str) -> int | None:
    """1-based line of `requires-harness: claude` under a `metadata:` mapping in YAML frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    top, sub = RH_KEY.split(".", 1)
    in_mapping = False
    for i, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return None
        if re.match(rf"^{re.escape(top)}:\s*$", line):
            in_mapping = True
            continue
        if in_mapping:
            if line[:1] not in (" ", "\t"):
                in_mapping = False
                continue
            m = re.match(rf"^\s+{re.escape(sub)}:\s*(.*)$", line)
            if m and m.group(1).strip().lower() == RH_VALUE:
                return i
    return None


# ---------------------------------------------------------------------------
# The canonical engine — derive the shared reasons for one file
# ---------------------------------------------------------------------------

def derive(text: str, file: str, skill_dir: str, bundle: Bundle) -> list[Hit]:
    hits: list[Hit] = []
    lines = text.split("\n")
    for lineno, line in enumerate(lines, 1):
        for m in RX["plugin_root_ref"].finditer(line):
            hits.append(Hit("plugin-root", lineno, f"`{MARKERS['plugin-root']}` is substituted by Claude Code only"))
            target = plugin_root_target(m.group(1))
            if target is not None and bundle.exists(target):
                owner = bundle.owner(target)
                if owner is not None and owner != skill_dir:
                    hits.append(Hit("cross-skill-path", lineno, f"`{m.group(0)}` reaches skill dir `{owner}` by path — refer to that skill by NAME"))
        if MARKERS["skill-dir-var"] in line:
            hits.append(Hit("skill-dir-var", lineno, f"`{MARKERS['skill-dir-var']}` is a Claude-only substitution"))
        for m in RX["relative_ref"].finditer(line):
            target = relative_target(m.group(1), file)
            if target is None or not bundle.exists(target):
                continue
            owner = bundle.owner(target)
            if owner == skill_dir:
                continue
            hits.append(Hit("relative-link", lineno, f"`{m.group(1)}` → {target} leaves the skill's own tree — the flat install breaks it"))
            if owner is not None:
                hits.append(Hit("cross-skill-path", lineno, f"`{m.group(1)}` → {target} lives in skill dir `{owner}`; refer to that skill by NAME"))
    for lineno, line, in_fence, fence_is_shell in fence_walk(lines):
        if in_fence and not fence_is_shell:
            continue
        masked = RX["launcher_call"].sub(lambda m: " " * len(m.group(0)), line)
        for m in RX["cwd_script"].finditer(masked):
            target = cwd_target(m.group(1))
            if target is not None and bundle.exists(target):
                hits.append(Hit("cwd-script", lineno, f"`{m.group(0).strip()}` reaches a plugin file cwd-relatively; write `wicked-garden run {target}`"))
    if file == skill_dir + "/SKILL.md":
        ln = requires_harness_line(text)
        if ln is not None:
            hits.append(Hit("requires-harness:claude", ln, "declared by the author"))
    return hits


def reasons(hits: Iterable[Hit]) -> list[str]:
    return sorted({h.token for h in hits})


def first_lines(hits: Iterable[Hit]) -> dict[str, int]:
    out: dict[str, int] = {}
    for h in hits:
        out[h.token] = min(out.get(h.token, h.line), h.line)
    return out


# ---------------------------------------------------------------------------
# Catalog helpers (garden)
# ---------------------------------------------------------------------------

def skill_dirs(root: Path = SKILLS) -> list[Path]:
    return sorted((p.parent for p in root.rglob("SKILL.md") if not any(x in SKIP_NAMES for x in p.parts)),
                  key=lambda d: (-len(d.parts), str(d)))


def skill_of(path: Path, root: Path = SKILLS) -> Path | None:
    candidates = ([path] if path.is_dir() else []) + list(path.parents)
    for d in candidates:
        try:
            d.relative_to(root)
        except ValueError:
            return None
        if d == root:
            return None
        if (d / "SKILL.md").exists():
            return d
    return None


def declared_names(root: Path = SKILLS) -> dict[str, Path]:
    names: dict[str, Path] = {}
    for d in skill_dirs(root):
        m = FRONTMATTER_RE.match((d / "SKILL.md").read_text(encoding="utf-8"))
        decl = NAME_DECL_RE.search(m.group(1)) if m else None
        if decl:
            names[decl.group(1).strip().strip("\"'")] = d
    return names


def is_text(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in data[:8000]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def text_files(root: Path = SKILLS) -> list[Path]:
    return [p for p in sorted(root.rglob("*"))
            if p.is_file() and not any(part in SKIP_NAMES for part in p.parts) and is_text(p)]


def frontmatter_lines(text: str) -> int:
    m = FRONTMATTER_RE.match(text)
    return text[: m.end()].count("\n") if m else 0


def body_of(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


# ---------------------------------------------------------------------------
# The garden scan: canonical engine + garden's extras, for one file
# ---------------------------------------------------------------------------

def scan_text(rel_file: str, text: str, names: dict[str, Path], bundle: Bundle, repo: Path = REPO) -> list[Violation]:
    file_path = repo / rel_file
    skill = skill_of(file_path, repo / "skills")
    skill_rel = skill.relative_to(repo).as_posix() if skill else ""
    is_md = rel_file.endswith(".md")
    fm_end = frontmatter_lines(text) if is_md else 0
    out: list[Violation] = []

    def add(token: str, lineno: int, detail: str) -> None:
        out.append(Violation(token, rel_file, lineno, detail))

    for h in derive(text, rel_file, skill_rel, bundle):
        add(h.token, h.line, h.detail)

    def own_file(p: str) -> bool:
        return skill is not None and (skill / p).exists()

    prev_nonblank = ""
    for lineno, line, in_fence, fence_is_shell in fence_walk(text.split("\n")):
        # stricter than crew: the bare identifier, not only the `${…}` marker
        for token, ident in IDENTIFIERS.items():
            if ident in line and MARKERS[token] not in line:
                add(token, lineno, f"`{ident}` is substituted by Claude Code only — use a skill-relative path or the launcher")
        if is_md:
            for m in GRX["skill_name"].finditer(line):
                name = m.group(1)
                # the exemption marker is TOKEN-scoped: it must follow this very token
                # (`wicked-garden-x` <!-- not-a-skill -->), not merely sit somewhere on the line
                exempt = re.match(r"[`'\"]?\s*" + re.escape(NOT_A_SKILL), line[m.end():]) is not None
                if "{" in name or name in names or exempt:
                    continue
                add("unresolved-skill-name", lineno,
                    f"`{name}` is not declared by any SKILL.md (an identifier that is not a skill gets `{NOT_A_SKILL}` right after the token)")
            if lineno > fm_end and GRX["slash_form"].search(line):
                add("slash-form", lineno, "skills are not slash commands on any CLI — name the skill (`wicked-garden-<x>`) instead")
            # bare `scripts/<x>.py <args>` span (prose) / bare shell-fence command line: no interpreter at all
            if not in_fence:
                for m in GRX["bare_script_span"].finditer(line):
                    if not own_file(m.group(1)) and bundle.exists(m.group(1)):
                        add("cwd-script", lineno, f"bare `{m.group(1)} …` span has no interpreter and is cwd-relative; write `wicked-garden run {m.group(1)} …`")
            elif fence_is_shell and not prev_nonblank.rstrip().endswith("\\"):
                m = GRX["bare_script_line"].match(line)
                if m and not own_file(m.group(2)) and bundle.exists(m.group(2)):
                    add("cwd-script", lineno, f"bare `{m.group(2)}` command line is cwd-relative; write `wicked-garden run {m.group(2)}`")
        if line.strip():
            prev_nonblank = line
    return out


def scan_structure(files_by_skill: dict[Path, list[Path]], repo: Path = REPO) -> list[Violation]:
    """Per-skill and per-file structural rules (garden): preamble, fork/dispatch/ask fallbacks."""
    out: list[Violation] = []
    for skill, files in files_by_skill.items():
        skill_md = skill / "SKILL.md"
        skill_text = skill_md.read_text(encoding="utf-8")
        rel_skill_md = skill_md.relative_to(repo).as_posix()
        uses_launcher = any(RX["launcher_call"].search(f.read_text(encoding="utf-8")) for f in files)
        if uses_launcher and RUNTIME_BLOCK not in skill_text:
            out.append(Violation("missing-runtime-preamble", rel_skill_md, 1,
                                 "skill uses `wicked-garden run|python|path` but its SKILL.md lacks the exact `## Runtime` block"))
        fm = FRONTMATTER_RE.match(skill_text)
        if fm and CONTEXT_FORK_RE.search(fm.group(1)) and FORK_SENTENCE not in skill_text:
            out.append(Violation("fork-no-fallback", rel_skill_md, 1,
                                 "context: fork worker without the 'when your harness cannot fork' sentence"))
        for f in files:
            if f.suffix != ".md":
                continue
            text = f.read_text(encoding="utf-8")
            rel = f.relative_to(repo).as_posix()
            if DISPATCH_RE.search(text) and DISPATCH_SENTENCE not in text:
                out.append(Violation("dispatch-no-fallback", rel, 1,
                                     "dispatches with Skill(skill=…) (single- or multi-line) but lacks the harness-fallback sentence"))
            if "AskUserQuestion" in body_of(text) and not GRX["ask_fallback"].search(text):
                out.append(Violation("ask-no-fallback", rel, 1,
                                     "mentions AskUserQuestion without spelling the plain-text fallback"))
    return out


def files_by_skill(files: list[Path]) -> dict[Path, list[Path]]:
    grouped: dict[Path, list[Path]] = {d: [] for d in skill_dirs()}
    for f in files:
        s = skill_of(f)
        if s is not None:
            grouped[s].append(f)
    return grouped


def scan_repo(repo: Path = REPO) -> tuple[list[Violation], dict[str, int]]:
    names = declared_names(repo / "skills")
    bundle = Bundle.from_repo(repo)
    files = text_files(repo / "skills")
    violations: list[Violation] = []
    launcher_calls = 0
    identifier_hits: Counter[str] = Counter()
    name_tokens = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(repo).as_posix()
        violations.extend(scan_text(rel, text, names, bundle, repo))
        # the ## Runtime block MENTIONS the launcher twice; count only real call sites
        launcher_calls += len(RX["launcher_call"].findall(text.replace(RUNTIME_BLOCK, "")))
        for token, ident in IDENTIFIERS.items():
            identifier_hits[token] += text.count(ident)
        if f.suffix == ".md":
            name_tokens += sum(1 for m in GRX["skill_name"].finditer(text) if "{" not in m.group(1))
    violations.extend(scan_structure(files_by_skill(files), repo))
    counts = {
        "files_scanned": len(files),
        "bundle_files": len(bundle.files),
        "skills": len(names),
        "plugin_root_refs": identifier_hits["plugin-root"],
        "skill_dir_var_refs": identifier_hits["skill-dir-var"],
        "launcher_calls": launcher_calls,
        "skill_name_tokens": name_tokens,
        "violations": len(violations),
        **{f"violations.{t}": c for t, c in sorted(Counter(v.token for v in violations).items())},
    }
    return violations, counts


def _report(violations: list[Violation], counts: dict[str, int]) -> str:
    lines = [str(v) for v in sorted(violations, key=lambda v: (v.file, v.line, v.token))]
    lines.append("")
    lines.append("counts: " + json.dumps(counts, indent=None, sort_keys=True))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_VIOLATIONS, _COUNTS = scan_repo()
_NAMES = declared_names()
_BUNDLE = Bundle.from_repo()


def test_fixtures_are_well_formed():
    assert CANON["version"] == 2
    assert SHARED_TOKENS == {"plugin-root", "skill-dir-var", "cwd-script", "relative-link", "cross-skill-path", "requires-harness:claude"}
    for name, src in {**CANON["regex"], **GARDEN["regex"]}.items():
        re.compile(src)  # raises on a Python-incompatible spelling
    assert GARDEN["canonical_fixture"] == "tests/portability_rules.json"
    assert RUNTIME_BLOCK.startswith(GARDEN["launcher"]["runtime_heading"] + "\n")
    assert "Relative paths in this skill are relative to the directory that contains this SKILL.md." in RUNTIME_BLOCK


@pytest.mark.parametrize("case", CANON["cases"], ids=lambda c: c["name"])
def test_canonical_case(case):
    """Parity with wicked-crew: every canonical case derives EXACTLY its expected reasons
    (and the first hit line where the case pins one)."""
    hits = derive(case["text"], case["file"], case["skill_dir"], Bundle.from_case(case))
    assert reasons(hits) == case["expected"], [str(h) for h in hits]
    if "first_line" in case:
        got = first_lines(hits)
        for token, line in case["first_line"].items():
            assert got.get(token) == line, (token, got)


def test_canonical_corpus_is_not_vacuous():
    assert len(CANON["cases"]) >= 80
    expected = Counter(t for c in CANON["cases"] for t in c["expected"])
    assert set(expected) == SHARED_TOKENS, expected


def test_skills_are_portable():
    """Every text file under skills/ is free of the non-portable patterns. Allowlist: none."""
    assert not _VIOLATIONS, (
        f"{len(_VIOLATIONS)} portability violation(s) under skills/ — fix the skill text "
        "(python3 scripts/wg/portability_codemod.py --dry-run shows the mechanical rewrite):\n"
        + _report(_VIOLATIONS, _COUNTS)
    )


def test_non_vacuity_inverted():
    """The pre-12.33 guard asserted > 20 plugin-root refs; the portable tree asserts the inverse."""
    assert _COUNTS["files_scanned"] > 300, _COUNTS
    assert _COUNTS["bundle_files"] > 500, _COUNTS
    assert _COUNTS["skills"] >= 140, _COUNTS
    assert _COUNTS["plugin_root_refs"] == 0, f"plugin-root refs under skills/: {_COUNTS['plugin_root_refs']}"
    assert _COUNTS["skill_dir_var_refs"] == 0, f"skill-dir-var refs under skills/: {_COUNTS['skill_dir_var_refs']}"
    assert _COUNTS["launcher_calls"] > 200, (
        f"only {_COUNTS['launcher_calls']} launcher calls found — the launcher regex drifted or the "
        "shared-runtime call sites were lost"
    )
    assert _COUNTS["skill_name_tokens"] > 300, f"name resolver saw only {_COUNTS['skill_name_tokens']} tokens"
    assert _COUNTS.get("violations.unresolved-skill-name", 0) == 0


@pytest.mark.parametrize("entry", GARDEN["corpus"]["quiet"], ids=lambda e: e["text"][:50])
def test_garden_corpus_is_quiet(entry):
    got = scan_text(entry["file"], entry["text"], _NAMES, _BUNDLE)
    assert not got, [str(v) for v in got]


@pytest.mark.parametrize("entry", GARDEN["corpus"]["trips"], ids=lambda e: f"{e['token']}::{e['text'][:40]}")
def test_garden_corpus_trips_exactly_its_tokens(entry):
    got = {v.token for v in scan_text(entry["file"], entry["text"], _NAMES, _BUNDLE)}
    assert got == set(entry["token"].split("+")), f"expected {entry['token']}, got {got}"


@pytest.mark.parametrize("text", [
    'Skill(skill="wicked-garden-mem", args="recall x")',
    'Skill(\n  skill="wicked-garden-qe-test-oracle",\n  args="""…"""\n)',
    'Skill(   skill="x")',
])
def test_dispatch_trigger_matches_single_and_multi_line_forms(text):
    assert DISPATCH_RE.search(text), text


def test_dispatch_trigger_ignores_non_dispatch_mentions():
    for text in ["invoke it with the Skill tool", "`Skill(wicked-bus:query, query=…)`", "Skill(\"superpowers:x\")"]:
        assert not DISPATCH_RE.search(text), text


def test_fence_walk_sees_non_shell_fences_in_the_repo():
    """The JS/TS-import false positives are killed by the fence skip — make sure it is exercised."""
    non_shell = 0
    for f in text_files():
        if f.suffix != ".md":
            continue
        if any(in_fence and not shell for _, _, in_fence, shell in fence_walk(f.read_text(encoding="utf-8").split("\n"))):
            non_shell += 1
    assert non_shell > 50, non_shell


if __name__ == "__main__":  # pragma: no cover - CLI report for the codemod loop
    print(_report(_VIOLATIONS, _COUNTS))
    sys.exit(1 if _VIOLATIONS else 0)
