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
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

from _skill_meta import CLOSED_KEYS as META_CLOSED_KEYS  # noqa: E402
from _skill_meta import claude_only_keys, parse_frontmatter, split_frontmatter  # noqa: E402
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
NOT_A_SKILL = GARDEN["skill_names"]["exemption_marker"]
# The eight cross-CLI tokens (L6 B0, D-21 — docs/cross-cli-skill-format.md; `claude-tool-call` from the B7 fold). The Claude-only shapes a
# skill still carries at HEAD are BASELINED per (token, file) in tests/cross_cli_baseline.json:
# tolerated there ONLY; the qe batches (B3–B17) translate skills and delete their entries in the same
# change; an entry that no longer trips is STALE and fails; B18 deletes the file (strict).
CROSS_CLI = GARDEN["cross_cli"]
CROSS_CLI_TOKENS = tuple(CROSS_CLI["tokens"])
CLOSED_KEYS = frozenset(CROSS_CLI["closed_frontmatter_keys"])
DISPATCH_CALL_RE = re.compile(CROSS_CLI["dispatch_regex"])
TOOL_CALL_RE = re.compile(CROSS_CLI["tool_call_regex"])
PROSE_RE = re.compile(CROSS_CLI["prose_regex"])
RETIRED_RE = re.compile(CROSS_CLI["retired_product_regex"])
HANDOFF_RE = re.compile(CROSS_CLI["handoff_regex"])
HISTORICAL = CROSS_CLI["historical_marker"]
BASELINE_PATH = REPO / CROSS_CLI["baseline"]
BASELINE = (json.loads(BASELINE_PATH.read_text(encoding="utf-8")) if BASELINE_PATH.exists()
            else {"entries": {}})
BASELINE_PAIRS = {(t, f) for t, files in BASELINE.get("entries", {}).items() for f in files}
# `verdict-spelling` (FIX-IT-ALL L6-0, the D-9 text half): the engine reads an evaluator unit's
# LAST `^VERDICT[:=]` line and passes ONLY on the token `PASS` — so garden text may ask for
# nothing but `VERDICT: PASS` / `VERDICT: FAIL` on such a line. The legacy `VERDICT=… REVIEWER=…
# RUN_ID=…` footers still parse (token PASS/FAIL) and are tolerated ONLY in the files listed —
# the qe batches (B14–B17) rewrite them and shrink the list; a stale entry fails the build.
VERDICT_SPELLING = GARDEN["verdict_spelling"]
VERDICT_ALLOWED = set(VERDICT_SPELLING["allowed"])
VERDICT_LEGACY_FILES = set(VERDICT_SPELLING["legacy_footer_files"])
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


def verdict_spelling_hit(rel_file: str, line: str) -> str | None:
    """`verdict-spelling`: judge ONLY a line-leading `VERDICT[:=]` line (fenced blocks included —
    the contract templates live in fences); return the violation detail or None.

    Conformant: exactly `VERDICT: PASS`, `VERDICT: FAIL`, or the template `VERDICT: PASS|FAIL`.
    Tolerated: the legacy qe footer `VERDICT=PASS|FAIL|{PASS|FAIL} REVIEWER=… RUN_ID=…` in a file
    listed in `verdict_spelling.legacy_footer_files` (it parses as PASS/FAIL; the batches delete it).
    Not judged: `**VERDICT: …**`, a backticked mention, `### Verdict:`, `verdict:` (lowercase record
    lines), a mid-line mention (`4. RENDER THE VERDICT: …`, a JS regex) — none is line-leading.
    """
    if not GRX["verdict_line"].match(line):
        return None
    if line.strip() in VERDICT_ALLOWED:
        return None
    if rel_file in VERDICT_LEGACY_FILES and GRX["verdict_legacy_footer"].match(line):
        return None
    return (f"`{line.strip()}` — an evaluator's verdict line is exactly `VERDICT: PASS` or `VERDICT: FAIL` "
            "(template `VERDICT: PASS|FAIL`): CONDITIONAL / APPROVE / REJECT / SKIP are not verdicts, and a "
            "`VERDICT=… REVIEWER=… RUN_ID=…` footer is legacy (tolerated only in verdict_spelling.legacy_footer_files "
            "until the qe batches normalise it)")


# ---------------------------------------------------------------------------
# The cross-CLI scan (L6 B0): the Claude-only shapes, one violation per (token, file)
# ---------------------------------------------------------------------------

def scan_cross_cli(rel_file: str, text: str, fm_end: int) -> list[Violation]:
    """The eight cross-CLI tokens for one .md file. Frontmatter tokens judge SKILL.md only;
    body tokens skip the frontmatter, skip `<!-- historical -->` lines, and exempt prose inside a
    Hand-off paragraph. Prose is matched over the PARAGRAPH (intra-paragraph newlines normalised to
    spaces), so a token cannot hide in a line wrap. One violation per (token, file) — the baseline is
    keyed the same way."""
    out: list[Violation] = []
    lines = text.split("\n")
    if rel_file.endswith("/SKILL.md") or rel_file == "SKILL.md":
        block, _ = split_frontmatter(text)
        if block is not None:
            fm = parse_frontmatter(block)
            extra = claude_only_keys(fm)
            if extra:
                first = 2
                for i, l in enumerate(block.split("\n")):
                    km = re.match(r"^([A-Za-z_][\w-]*)\s*:", l)
                    if km and km.group(1) in extra:
                        first = i + 2
                        break
                out.append(Violation("claude-frontmatter-key", rel_file, first,
                                     f"top-level frontmatter key(s) {extra} outside the cross-CLI closed set "
                                     f"{sorted(CLOSED_KEYS)} — Claude Code plugin hints no other CLI reads; role/phases/"
                                     "archetypes move under `metadata:`, the rest are dropped"))
            desc = fm.get("description", "")
            if isinstance(desc, str) and len(desc) > CROSS_CLI["description_max_chars"]:
                out.append(Violation("description-too-long", rel_file, 2,
                                     f"description is {len(desc)} chars (max {CROSS_CLI['description_max_chars']})"))
        nbytes = len(text.encode("utf-8"))
        if nbytes > CROSS_CLI["skill_max_bytes"] or len(lines) > CROSS_CLI["skill_max_lines"]:
            out.append(Violation("skill-too-large", rel_file, 1,
                                 f"{len(lines)} lines / {nbytes} bytes (max {CROSS_CLI['skill_max_lines']} lines / "
                                 f"{CROSS_CLI['skill_max_bytes']} bytes) — move detail into refs/"))
    dispatch: list[int] = []
    toolcalls: list[int] = []
    prose: list[int] = []
    retired: dict[str, int] = {}
    has_handoff = False
    in_handoff = False
    para: list[tuple[int, str]] = []

    def close_paragraph() -> None:
        """Match prose over the whole paragraph (review-garden-1158 M1). A tool noun can straddle a
        line break — `multiple Bash` / `tool calls in a single message` — and a line-based search
        never sees it. Join the lines with spaces, then map each match back to the line it starts on.
        Joining only ever ADDS matches (one inside a single line still matches), so no baselined pair
        can go stale from this."""
        if para:
            joined = " ".join(text for _, text in para)
            starts: list[tuple[int, int]] = []
            pos = 0
            for lineno, text in para:
                starts.append((pos, lineno))
                pos += len(text) + 1
            for m in PROSE_RE.finditer(joined):
                line_at = starts[0][1]
                for off, lineno in starts:
                    if off > m.start():
                        break
                    line_at = lineno
                prose.append(line_at)
        para.clear()

    for lineno, line in enumerate(lines, start=1):
        if lineno <= fm_end:
            continue
        if not line.strip():
            close_paragraph()  # a blank line ends the paragraph — and the Hand-off exemption
            in_handoff = False
            continue
        if HANDOFF_RE.match(line):
            in_handoff = True
            has_handoff = True
        if HISTORICAL in line:
            close_paragraph()  # the line is exempt, and never joins to its neighbours
            continue
        if DISPATCH_CALL_RE.search(line):
            dispatch.append(lineno)
        if TOOL_CALL_RE.search(line):
            toolcalls.append(lineno)
        if not in_handoff:
            para.append((lineno, line))
        for m in RETIRED_RE.finditer(line):
            retired.setdefault(m.group(0), lineno)
    close_paragraph()
    if dispatch:
        out.append(Violation("claude-dispatch", rel_file, dispatch[0],
                             f"{len(dispatch)} line(s) call a Claude Code dispatch primitive (Task( / Skill( / Agent( / "
                             "TaskCreate( / TaskUpdate( / TodoWrite( / subagent_type / AskUserQuestion) no other seat has — "
                             "name the skill in a Hand-off paragraph instead"))
        if not has_handoff:
            out.append(Violation("handoff-missing", rel_file, dispatch[0],
                                 "dispatches but carries no `Hand-off` paragraph — the only cross-CLI dispatch shape"))
    if toolcalls:
        out.append(Violation("claude-tool-call", rel_file, toolcalls[0],
                             f"{len(toolcalls)} line(s) call a Claude Code tool (Read( / Write( / Edit( / Bash( / Glob( / Grep( / …) "
                             "no other seat has — say what to do with your harness's file reader / shell / search instead"))
    if prose:
        out.append(Violation("claude-only-prose", rel_file, min(prose),
                             f"{len(prose)} match(es) of Claude-only prose (a tool noun, a .claude/ path or `Claude Code`) "
                             "outside a Hand-off paragraph and not marked <!-- historical --> — matched over the "
                             "paragraph, so a token split across a line break still counts"))
    if retired:
        out.append(Violation("retired-product-ref", rel_file, min(retired.values()),
                             f"names retired product(s) {sorted(retired)} without <!-- historical -->"))
    return out


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
    if is_md:
        out.extend(scan_cross_cli(rel_file, text, fm_end))

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
            verdict_detail = verdict_spelling_hit(rel_file, line)
            if verdict_detail is not None:
                add("verdict-spelling", lineno, verdict_detail)
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
    """Per-skill structural rule (garden): the `## Runtime` preamble. (The Claude-first fallback
    sentences — fork / dispatch / ask — were retired by L6 B0: the Claude shape itself is now the
    `claude-dispatch` finding, translated into a Hand-off paragraph by the batches.)"""
    out: list[Violation] = []
    for skill, files in files_by_skill.items():
        skill_md = skill / "SKILL.md"
        skill_text = skill_md.read_text(encoding="utf-8")
        rel_skill_md = skill_md.relative_to(repo).as_posix()
        uses_launcher = any(RX["launcher_call"].search(f.read_text(encoding="utf-8")) for f in files)
        if uses_launcher and RUNTIME_BLOCK not in skill_text:
            out.append(Violation("missing-runtime-preamble", rel_skill_md, 1,
                                 "skill uses `wicked-garden run|python|path` but its SKILL.md lacks the exact `## Runtime` block"))
    return out


def files_by_skill(files: list[Path]) -> dict[Path, list[Path]]:
    grouped: dict[Path, list[Path]] = {d: [] for d in skill_dirs()}
    for f in files:
        s = skill_of(f)
        if s is not None:
            grouped[s].append(f)
    return grouped


def apply_baseline(violations: list[Violation]) -> tuple[list[Violation], list[tuple[str, str]]]:
    """Drop the cross-CLI violations the baseline tolerates; return (residual, stale entries) — a
    stale entry is a baselined (token, file) that no longer trips and must be deleted."""
    residual: list[Violation] = []
    hit: set[tuple[str, str]] = set()
    for v in violations:
        if v.token in CROSS_CLI_TOKENS:
            hit.add((v.token, v.file))
            if (v.token, v.file) in BASELINE_PAIRS:
                continue
        residual.append(v)
    return residual, sorted(BASELINE_PAIRS - hit)


def scan_repo(repo: Path = REPO, baseline: bool = True) -> tuple[list[Violation], dict[str, int], list[tuple[str, str]]]:
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
    stale: list[tuple[str, str]] = []
    raw_cross_cli = Counter(v.token for v in violations if v.token in CROSS_CLI_TOKENS)
    if baseline:
        violations, stale = apply_baseline(violations)
    counts = {
        "files_scanned": len(files),
        "baseline_entries": len(BASELINE_PAIRS),
        "baseline_stale": len(stale),
        **{f"cross_cli.{t}": c for t, c in sorted(raw_cross_cli.items())},
        "bundle_files": len(bundle.files),
        "skills": len(names),
        "plugin_root_refs": identifier_hits["plugin-root"],
        "skill_dir_var_refs": identifier_hits["skill-dir-var"],
        "launcher_calls": launcher_calls,
        "skill_name_tokens": name_tokens,
        "violations": len(violations),
        **{f"violations.{t}": c for t, c in sorted(Counter(v.token for v in violations).items())},
    }
    return violations, counts, stale


def write_baseline(repo: Path = REPO) -> dict:
    """Regenerate tests/cross_cli_baseline.json from the RAW cross-CLI hits at HEAD (dev tooling:
    `python3 tests/test_skill_portability.py --write-baseline`). Never run it to silence a new
    finding — fix the skill; the file only ever shrinks after B0."""
    raw, _, _ = scan_repo(repo, baseline=False)
    entries: dict[str, list[str]] = {t: [] for t in CROSS_CLI_TOKENS}
    for v in raw:
        if v.token in CROSS_CLI_TOKENS and v.file not in entries[v.token]:
            entries[v.token].append(v.file)
    for t in entries:
        entries[t].sort()
    head = ""
    try:
        import subprocess
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True,
                              text=True, check=False).stdout.strip()
    except OSError:
        pass
    data = {
        "$comment": "L6 B0 cross-CLI baseline — the (token, file) pairs that still carry a Claude-only shape at the "
                    "generating HEAD (tests/test_skill_portability.py scan_cross_cli). A listed pair is tolerated; an "
                    "unlisted hit fails; a listed pair that no longer trips is STALE and fails — the qe batches (B3–B17) "
                    "translate skills and delete their entries in the same change, and B18 deletes this file. Never add an "
                    "entry to silence the lint; regenerate only with --write-baseline at B0.",
        "generated_from": head,
        "entries": entries,
    }
    (repo / CROSS_CLI["baseline"]).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def _report(violations: list[Violation], counts: dict[str, int]) -> str:
    lines = [str(v) for v in sorted(violations, key=lambda v: (v.file, v.line, v.token))]
    lines.append("")
    lines.append("counts: " + json.dumps(counts, indent=None, sort_keys=True))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_VIOLATIONS, _COUNTS, _STALE = scan_repo()
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
    # L6 B0 (+ B7 fold): the eight cross-CLI tokens + verdict-spelling are declared; the three Claude-first fallback
    # tokens are gone; the closed key set is the helper's (one source of truth)
    declared = {t["token"] for t in GARDEN["tokens"]}
    assert set(CROSS_CLI_TOKENS) == {"claude-frontmatter-key", "claude-dispatch", "claude-only-prose", "handoff-missing",
                                     "retired-product-ref", "description-too-long", "skill-too-large", "claude-tool-call"}
    assert set(CROSS_CLI_TOKENS) | {"verdict-spelling"} <= declared, declared
    assert not ({"fork-no-fallback", "dispatch-no-fallback", "ask-no-fallback"} & declared), declared
    assert CLOSED_KEYS == META_CLOSED_KEYS
    assert set(BASELINE.get("entries", {})) <= set(CROSS_CLI_TOKENS)


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
    assert _COUNTS["skills"] >= 137, _COUNTS  # B18 retired the crew-* trio stubs (was 140)
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


# ---------------------------------------------------------------------------
# cross-CLI tokens (L6 B0): one trip + one quiet case per token, and the baseline discipline
# ---------------------------------------------------------------------------

_FM_OK = "---\nname: wicked-garden-x\ndescription: d\nmetadata:\n  role: worker\n---\n"


def _cross(file: str, text: str) -> set[str]:
    return {v.token for v in scan_text(file, text, _NAMES, _BUNDLE) if v.token in CROSS_CLI_TOKENS}


@pytest.mark.parametrize(("file", "text", "expect"), [
    # claude-frontmatter-key: any top-level key outside the closed set; the closed set alone is quiet
    ("skills/x/SKILL.md", "---\nname: wicked-garden-x\ndescription: d\ncontext: fork\nmodel: opus\n---\n# x\n", {"claude-frontmatter-key"}),
    ("skills/x/SKILL.md", "---\nname: wicked-garden-x\ndescription: d\nlicense: MIT\ncompatibility: any\nmandates:\n  - wicked-garden-core\nmetadata:\n  role: router\n  phases: \"*\"\n---\n# x\n", set()),
    ("skills/x/refs/a.md", "---\ncontext: fork\n---\nprose\n", set()),  # frontmatter tokens judge SKILL.md only
    # claude-dispatch (+ handoff-missing when no Hand-off paragraph); a Hand-off paragraph satisfies the pair's second half
    ("skills/x/SKILL.md", _FM_OK + "Run `Task(subagent_type=\"x\", prompt=\"y\")` first.\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "```\nSkill(\n  skill=\"wicked-garden-qe\",\n  args=\"x\"\n)\n```\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "TaskCreate the follow-ups; TodoWrite(...) is fine\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "Hand-off: open the `wicked-garden-qe` skill and run its `review` action.\n\nThen `Skill(skill=\"wicked-garden-qe\")` was the old shape.\n", {"claude-dispatch"}),
    ("skills/x/refs/a.md", "the retired trio used `Task(subagent_type=…)` <!-- historical -->\n", set()),
    ("skills/x/refs/a.md", "a subtask is planned; the agent (a person) skips it\n", set()),
    # review-L6-B N3: the prose plurals are NOT calls; a placeholder-argument call still is
    ("skills/x/refs/a.md", "Task(s) and Agent(s) are queued by the router; a Task(s) list follows.\n", set()),
    ("skills/x/refs/a.md", "then `Skill(...)` hands over\n", {"claude-dispatch", "handoff-missing"}),
    # B8: framework code in a sample is not a dispatch — for the framework-ambiguous nouns Task( / Agent( ONLY, an assignment,
    # constructor or lambda context is quiet (the accepted trade: a Claude `report = Agent(prompt=…)` is masked too); a bare call still trips
    ("skills/x/refs/a.md", "```python\nresearcher = Agent(role='Researcher', tools=[search])\nsearch_task = Task(description='Research topic')\n```\n", set()),
    ("skills/x/refs/a.md", "```typescript\nconst agent = new Agent({ model: 'x' });\n```\n", set()),
    ("skills/x/refs/a.md", "factory=lambda: Agent(tools=[code_review])\n", set()),
    ("skills/x/refs/a.md", "report = Agent(prompt=\"Recon the estate\")\n", set()),
    # #1157 (B18): a bare CAPITALISED first positional arg FOLLOWED BY MORE ARGS is a real Claude-only
    # dispatch/tool-call the lookahead used to miss; a lone `X(Cap)` prose noun and plurals stay quiet.
    ("skills/x/refs/a.md", "Agent(Explore, prompt=\"find the callers\")\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "Read(FilePath, encoding)\n", {"claude-tool-call"}),
    ("skills/x/refs/a.md", "recall replaces Grep/Glob/Agent(Explore) here\n", set()),
    ("skills/x/refs/a.md", "Task(s) and Agent(s) are queued; a Read(s) list follows\n", set()),
    ("skills/x/refs/a.md", "```python\nAgent(prompt=\"summarise\")\n```\n", {"claude-dispatch", "handoff-missing"}),
    # review-garden-1154 H1: the Claude-only nouns are unconditional — assignment and label forms still trip (BC-38)
    ("skills/x/refs/a.md", "plan = Skill(skill=\"wicked-garden-qe\", args=\"plan\")\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "Dispatch: Skill(skill=\"wicked-garden-qe\", args=\"plan\")\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "t = TaskCreate(subject=\"X\", description=\"Y\")\n", {"claude-dispatch", "handoff-missing"}),
    ("skills/x/refs/a.md", "Then: TodoWrite(todos=[...])\n", {"claude-dispatch", "handoff-missing"}),
    # claude-only-prose: tool nouns, .claude/ paths, `Claude Code` — exempt inside a Hand-off paragraph / historical lines
    ("skills/x/refs/a.md", "Use the Read tool on the file.\n", {"claude-only-prose"}),
    ("skills/x/refs/a.md", "Dispatch uses the Skill tool on Claude Code (a fresh forked context).\n", {"claude-only-prose"}),
    ("skills/x/refs/a.md", "settings live in `.claude/settings.json`\n", {"claude-only-prose"}),
    ("skills/x/refs/a.md", "**Hand-off** — on Claude Code use the Skill tool; on any other seat open the named skill.\nSecond line of the paragraph still mentions Claude Code.\n", set()),
    ("skills/x/refs/a.md", "Claude Code loaded it via the plugin root <!-- historical -->\n", set()),
    ("skills/x/refs/a.md", "read the file with your file-edit tool; wicked-crew hands the seat the skills\n", set()),
    # review-garden-1158 M1: a prose token split across a line break is STILL Claude-only prose — the
    # line-based scan could not see it (`multiple Bash\ntool calls` shipped in jam-council for a year).
    # A token spanning a PARAGRAPH break is not one, a `<!-- historical -->` line never joins to its
    # neighbour, and the Hand-off exemption still covers the whole paragraph.
    ("skills/x/refs/a.md", "Run them in parallel using multiple Bash\ntool calls in one message.\n", {"claude-only-prose"}),
    ("skills/x/refs/a.md", "Open it with the Read\ntool before judging.\n", {"claude-only-prose"}),
    ("skills/x/refs/a.md", "the seat runs Bash\n\ntool calls are the harness's business\n", set()),
    ("skills/x/refs/a.md", "**Hand-off** — open the `wicked-garden-qe` skill; on Claude\nCode this is the Skill tool.\n", set()),
    ("skills/x/refs/a.md", "the old shape used the Read\ntool <!-- historical -->\n", set()),
    # claude-tool-call (review-garden-1153 M1): a tool call with an argument shape, in prose or a fence; the harness-neutral instruction is quiet
    ("skills/x/refs/a.md", "```\nRead(file_path=\"/path/to/screenshot.png\")\n```\n", {"claude-tool-call"}),
    ("skills/x/refs/a.md", "then `Glob(pattern=\"**/*.md\", path=\"x/\")` and `Bash(\"ls\")`\n", {"claude-tool-call"}),
    ("skills/x/refs/a.md", "Read(...) the file first\n", {"claude-tool-call"}),
    ("skills/x/refs/a.md", "the old shape was `Read(file_path=…)` <!-- historical -->\n", set()),
    ("skills/x/refs/a.md", "Read(s) and Write(s) are queued; open the file with your harness's file reader\n", set()),
    ("skills/x/refs/a.md", "the `read_text(path)` helper and `grep(pattern)` in code are not tool calls\n", set()),
    # retired-product-ref
    ("skills/x/refs/a.md", "run `wicked-testing accept` first\n", {"retired-product-ref"}),
    ("skills/x/refs/a.md", "the loom peer (`wicked-loom`) re-derives the gate\n", {"retired-product-ref"}),
    ("skills/x/refs/a.md", "ported from the retired wicked-testing package <!-- historical -->\n", set()),
    ("skills/x/refs/a.md", "wicked-vault and wicked-estate are live peers\n", set()),
    # description-too-long / skill-too-large (SKILL.md only)
    ("skills/x/SKILL.md", "---\nname: wicked-garden-x\ndescription: " + "d" * 1025 + "\nmetadata:\n  role: worker\n---\n# x\n", {"description-too-long"}),
    ("skills/x/SKILL.md", _FM_OK + "line\n" * 496, {"skill-too-large"}),
    ("skills/x/SKILL.md", _FM_OK + ("x" * 100 + "\n") * 250, {"skill-too-large"}),
    ("skills/x/refs/a.md", "line\n" * 600, set()),
], ids=lambda v: v if isinstance(v, str) and len(v) < 40 and "/" in v else None)
def test_cross_cli_token_table(file, text, expect):
    assert _cross(file, text) == expect


def test_cross_cli_baseline_has_no_stale_entries():
    """A baselined (token, file) that no longer trips is stale — the batch that translated the skill
    must delete the entry in the same change (the baseline only ever shrinks after B0)."""
    assert not _STALE, f"stale entries in {CROSS_CLI['baseline']} (delete them): {_STALE}"


def test_cross_cli_baseline_is_well_formed():
    """The baseline is SHRINK-ONLY after B0 (a batch deletes the entries it translated), so its size is
    never asserted here — a numeric floor would turn CI red on a batch that did exactly what the design
    asks (review-L6-B H1). What holds for the file's whole life: it names the HEAD it was generated
    from, carries every token (an empty list is a token with nothing left to translate), and every
    listed file still exists (a gone file = delete the entry). B18 deletes the file and this test."""
    generated_from = BASELINE.get("generated_from")
    assert isinstance(generated_from, str) and re.fullmatch(r"[0-9a-f]{7,40}", generated_from), generated_from
    entries = BASELINE.get("entries", {})
    assert set(entries) == set(CROSS_CLI_TOKENS), sorted(entries)
    assert all(isinstance(v, list) for v in entries.values())
    for t in CROSS_CLI_TOKENS:
        for f in entries[t]:
            assert (REPO / f).exists(), f"{t}: baselined file is gone — delete the entry: {f}"


# ---------------------------------------------------------------------------
# fenced-block pairing (L6-B6, review-garden-1148 H1 class): CommonMark treats EVERY line that starts
# with three or more backticks as a fence; an opener may carry an info string, a closer never does and
# must be at least as long. A template that wraps ```-blocks in a ```-wrapper therefore closes early
# and every heading after it renders as code — an even fence COUNT does not catch it, the walk does.
# ---------------------------------------------------------------------------

# Files whose fences do not pair at HEAD (all pre-existing). SHRINK-ONLY: the batch that translates a
# file fixes its fences and deletes its entry; an entry whose file pairs again is STALE and fails.
FENCE_PAIRING_BASELINE = {
    "skills/engineering/architecture/refs/examples-saas-trading.md",  # swallowed-sections class (review-garden-1154 M1)
    "skills/engineering/integration/refs/event-schemas-best-practices.md",
    "skills/qe/refs/scenario-format.md",
    "skills/qe-incident-to-scenario-synthesizer/SKILL.md",  # swallowed-sections class (review-garden-1154 M1)
}
_FENCE_RE = re.compile(r"^(`{3,})(.*)$")
_HEADING_RE = re.compile(r"^#{2,6} \S")


def fence_pairing_problem(text: str) -> str | None:
    """The CommonMark pairing walk: `None` when every fenced block closes AND no block opened by a bare ```
    swallows real sections; else the line of the block left open (or the first stray closer), or the block
    that holds both a `##` heading and a language-tagged fence — the signature of a wrapper that closed early
    (review-garden-1154 M1): a bare code fence never legitimately nests another fenced code block, while a
    bare fence holding only a heading is a fenced markdown template (a legitimate authoring choice)."""
    open_len = 0
    open_at = 0
    open_info = ""
    heads: list[int] = []
    inner: list[int] = []
    swallowed: str | None = None
    for lineno, line in enumerate(text.split("\n"), start=1):
        m = _FENCE_RE.match(line)
        if not m:
            if open_len and open_info == "" and _HEADING_RE.match(line):
                heads.append(lineno)
            continue
        n, info = len(m.group(1)), m.group(2).strip()
        if open_len == 0:
            open_len, open_at, open_info, heads, inner = n, lineno, info, [], []  # a bare ``` with nothing open OPENS a block — a "doubled closer" is never a stray
        elif info == "" and n >= open_len:
            if open_info == "" and heads and inner and swallowed is None:
                swallowed = f"the bare fence opened at :{open_at} holds a heading (:{heads[0]}) and a tagged fence (:{inner[0]}) — a wrapper closed early and swallowed real sections (promote the wrapper to ````)"
            open_len = 0
        elif info:
            inner.append(lineno)  # a tagged opener-looking line inside an open block
        # else: a shorter bare fence inside the open block — content
    if open_len:
        return f"fence opened at :{open_at} never closes (every heading after it renders as code)"
    return swallowed


def test_fenced_blocks_pair_in_every_skill_file():
    broken = {}
    for f in text_files():
        if f.suffix != ".md":
            continue
        rel = f.relative_to(REPO).as_posix()
        problem = fence_pairing_problem(f.read_text(encoding="utf-8"))
        if problem is not None and rel not in FENCE_PAIRING_BASELINE:
            broken[rel] = problem
    assert not broken, "unpaired fenced blocks (promote a wrapper that holds ```-blocks to ```` or close the block): " + json.dumps(broken, indent=1)


def test_fence_pairing_baseline_is_live():
    """Every baselined file still fails the walk — a file that pairs again must leave the list."""
    stale = [rel for rel in sorted(FENCE_PAIRING_BASELINE) if not (REPO / rel).exists() or fence_pairing_problem((REPO / rel).read_text(encoding="utf-8")) is None]
    assert not stale, f"stale FENCE_PAIRING_BASELINE entries (the file pairs now, or is gone): {stale}"


@pytest.mark.parametrize(("text", "ok"), [
    ("```bash\necho hi\n```\n", True),
    ("```markdown\n# T\n```python\nx = 1\n```\n## After\n```\n", False),          # the debug.md / component-template class: the inner closer ends the wrapper, the last ``` re-opens
    ("````markdown\n# T\n```python\nx = 1\n```\n## After\n````\n", True),        # the fix: a 4-backtick wrapper
    ("```json fence for paste) · more prose\n", False),                                # wrapped prose that starts a line with ``` IS an opener to a renderer
    ("text\n```\nblock\n```\n```\n", False),                                       # a doubled closer opens a new block
    ("```{language}\ncode\n```\n", True),                                            # an info string may be anything without backticks
    # review-garden-1154 M1: the flipped wrapper — paired by count, but the bare second half swallows real sections
    ("```markdown\n# Report\n```mermaid\ngraph TB\n```\ntext\n```\n\n## Integration\n\n```bash\nls\n```\n", False),
    ("````markdown\n# Report\n```mermaid\ngraph TB\n```\ntext\n````\n\n## Integration\n\n```bash\nls\n```\n", True),
    ("```\n## Grounding: {question}\n**Answer**: …\n```\n", True),                       # a bare fenced TEMPLATE with a heading is legitimate
])
def test_fence_pairing_walk_table(text, ok):
    assert (fence_pairing_problem(text) is None) is ok


# ---------------------------------------------------------------------------
# verdict-spelling (L6-0): the table the DES asks for — the three F4 sites + the grammar's edges
# ---------------------------------------------------------------------------

# a legacy-footer-SHAPED line; verdict_spelling.legacy_footer_files is EMPTY after B17 (all 40 qe workers
# converted), so this shape is now a verdict-spelling hit in EVERY file (row below). Kept as a generic
# example, not tied to a real skill.
_LEGACY_FOOTER = "VERDICT={PASS|FAIL} REVIEWER=wicked-garden-qe-example RUN_ID={RUN_ID}"


@pytest.mark.parametrize(("file", "line", "hit"), [
    # the three F4 sites (DES-L6 §5): two non-hits (not line-leading), one hit (a template `VERDICT:` line)
    ("skills/swarm/refs/independent-verification.md", "4. RENDER THE VERDICT: PASS / FAIL / PARTIAL.", False),
    ("skills/qe-flaky-test-hunter/SKILL.md", "  const pass=lines.filter(l=>/VERDICT=PASS/.test(l)).length;", False),
    ("skills/wickedizer/refs/patterns.md", "VERDICT: [Which wins and why]", True),
    # the grammar
    ("skills/x/SKILL.md", "VERDICT: PASS", False),
    ("skills/x/SKILL.md", "VERDICT: FAIL", False),
    ("skills/x/SKILL.md", "VERDICT: PASS|FAIL", False),
    ("skills/x/SKILL.md", "  VERDICT: PASS", False),  # indented inside a fence is still the contract line
    ("skills/x/SKILL.md", "VERDICT: PASS ", False),  # trailing whitespace is stripped, like the parser's trim
    # not verdicts (D-9): every other token, either separator, extra fields
    ("skills/x/SKILL.md", "VERDICT: CONDITIONAL", True),
    ("skills/x/SKILL.md", "VERDICT: APPROVE", True),
    ("skills/x/SKILL.md", "VERDICT: REJECT", True),
    ("skills/x/SKILL.md", "VERDICT: SKIP", True),
    ("skills/x/SKILL.md", "VERDICT=FAIL", True),
    ("skills/x/SKILL.md", "VERDICT: PASS REVIEWER: x", True),
    ("skills/x/SKILL.md", "VERDICT={PASS|CONDITIONAL|FAIL|SKIP} REVIEWER=wicked-garden-qe-security-test-engineer RUN_ID={RUN_ID}", True),
    ("skills/x/SKILL.md", "VERDICT={PASS|CONDITIONAL|FAIL} MODE=produced-test REVIEWER=wicked-garden-qe-test-code-quality-auditor RUN_ID={RUN_ID}", True),
    # B17 converted qe-visual-regression-engineer (the last legacy footer); legacy_footer_files is now EMPTY,
    # so a legacy-footer-shaped line is a verdict-spelling violation in EVERY file:
    ("skills/x/SKILL.md", _LEGACY_FOOTER, True),
    ("skills/qe-visual-regression-engineer/SKILL.md", _LEGACY_FOOTER, True),
    # not line-leading → not judged (the parser strips decoration; the TEXT rule forbids it in prose)
    ("skills/x/SKILL.md", "**VERDICT: PASS**", False),
    ("skills/x/SKILL.md", "`VERDICT: PASS`", False),
    ("skills/x/SKILL.md", "### Verdict: {PASS | FAIL}", False),
    ("skills/x/SKILL.md", "record: CONDITIONAL (axe+pa11y clean, manual review required)", False),
    ("skills/x/SKILL.md", "verdict: {PASS|CONDITIONAL|FAIL}  reason: {short}", False),
], ids=lambda v: v if isinstance(v, str) and len(v) < 60 else None)
def test_verdict_spelling_table(file, line, hit):
    assert (verdict_spelling_hit(file, line) is not None) is hit, (file, line)
    got = {v.token for v in scan_text(file, line + "\n", _NAMES, _BUNDLE)}
    assert ("verdict-spelling" in got) is hit, got


def test_verdict_spelling_judges_fenced_lines_too():
    fenced = "```\nMODE: produced-test\nVERDICT: CONDITIONAL\n```\n"
    got = [v for v in scan_text("skills/x/SKILL.md", fenced, _NAMES, _BUNDLE) if v.token == "verdict-spelling"]
    assert [v.line for v in got] == [3], got


def test_verdict_spelling_is_md_only():
    assert not [v for v in scan_text("skills/x/scripts/x.py", "VERDICT: CONDITIONAL\n", _NAMES, _BUNDLE)
                if v.token == "verdict-spelling"]


def test_verdict_legacy_footer_baseline_is_live():
    """Every listed file still carries a legacy footer — the qe batches (B14–B17) rewrite the footer
    to the grammar AND delete the entry in the same change; a stale entry is a failure, not a no-op."""
    stale = []
    for rel in sorted(VERDICT_LEGACY_FILES):
        p = REPO / rel
        lines = p.read_text(encoding="utf-8").split("\n") if p.exists() else []
        if not any(GRX["verdict_legacy_footer"].match(l) for l in lines):
            stale.append(rel)
    assert not stale, f"stale verdict_spelling.legacy_footer_files entries (no legacy footer left): {stale}"


def test_verdict_lines_in_repo_are_conformant_or_listed_legacy():
    """Non-vacuity for the token: the repo carries line-leading VERDICT lines (the contract templates
    and the not-yet-normalised footers); each is conformant or a listed legacy footer — the whole-repo
    scan (`test_skills_are_portable`) already fails on anything else."""
    seen = conformant = legacy = 0
    for f in text_files():
        if f.suffix != ".md":
            continue
        rel = f.relative_to(REPO).as_posix()
        for line in f.read_text(encoding="utf-8").split("\n"):
            if not GRX["verdict_line"].match(line):
                continue
            seen += 1
            if line.strip() in VERDICT_ALLOWED:
                conformant += 1
            elif rel in VERDICT_LEGACY_FILES and GRX["verdict_legacy_footer"].match(line):
                legacy += 1
    assert seen == conformant + legacy, (seen, conformant, legacy)
    assert conformant >= 5, conformant  # governed-worker's contract is mirrored by ≥ 5 evaluator templates
    assert legacy == len(VERDICT_LEGACY_FILES), (legacy, sorted(VERDICT_LEGACY_FILES))


def test_fence_walk_sees_non_shell_fences_in_the_repo():
    """The JS/TS-import false positives are killed by the fence skip — make sure it is exercised."""
    non_shell = 0
    for f in text_files():
        if f.suffix != ".md":
            continue
        if any(in_fence and not shell for _, _, in_fence, shell in fence_walk(f.read_text(encoding="utf-8").split("\n"))):
            non_shell += 1
    assert non_shell > 50, non_shell


# ── L4-⑨b (#1155, D1 / D2): search + mem ground through the read-only shim ONLY ──────────────────
ONE_RUNG_SKILLS = ("skills/search", "skills/mem")
MCP_RESIDUE_RE = re.compile(r"MCP|mcp__|wicked-estate-mcp|when connected")
SHIM_CALL_RE = re.compile(r"_estate_client\.py --readonly call")


def test_search_and_mem_have_one_rung_and_no_mcp_residue():
    """The #1146 leftover class must not return: an MCP-first "human session" branch, a tool named as
    something to "connect", the estate binary spelled as a rung. 0 residue tokens under
    skills/search/** + skills/mem/** (refs included — they are delivered with the skill), and each
    SKILL.md spells the one way — `_estate_client.py --readonly call` — at least once."""
    residue: list[str] = []
    for root in ONE_RUNG_SKILLS:
        for p in sorted((REPO / root).rglob("*.md")):
            for n, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
                if MCP_RESIDUE_RE.search(line):
                    residue.append(f"{p.relative_to(REPO).as_posix()}:{n}: {line.strip()[:90]}")
    assert residue == [], "MCP-first residue in the one-rung skills:\n" + "\n".join(residue)
    for root in ONE_RUNG_SKILLS:
        text = (REPO / root / "SKILL.md").read_text(encoding="utf-8")
        assert SHIM_CALL_RE.search(text), f"{root}/SKILL.md never spells `_estate_client.py --readonly call`"


if __name__ == "__main__":  # pragma: no cover - CLI report for the codemod loop
    if "--write-baseline" in sys.argv[1:]:
        data = write_baseline()
        print(json.dumps({t: len(fs) for t, fs in data["entries"].items()}, indent=2))
        sys.exit(0)
    print(_report(_VIOLATIONS, _COUNTS))
    if _STALE:
        print(f"STALE baseline entries: {_STALE}")
    sys.exit(1 if (_VIOLATIONS or _STALE) else 0)
