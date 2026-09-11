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

The rules live as DATA in ``tests/portability_rules.json`` — the same spelling wicked-crew's
publisher validator imports as a parity fixture — so drift between the two lints is a
failing test, not a surprise at publish. Files under ``skills/`` are attributed to the
DEEPEST skill directory that contains them (nested modules are their own skills), exactly
as crew's catalog does. The allowlist is EMPTY on purpose: a violation is fixed in the
skill body (``python3 scripts/wg/portability_codemod.py --dry-run`` shows the fix), never
tolerated here.

Non-vacuity is inverted from the pre-12.33 suite: this lint asserts ZERO plugin-root /
skill-dir-var references under ``skills/``, MORE THAN 200 launcher calls (a regex drift
cannot pass vacuously), ZERO unresolved ``wicked-garden-*`` names, and that the shared
false-positive corpus stays quiet while the positive corpus trips.

Run it directly for the full report + counts: ``python3 tests/test_skill_portability.py``.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
RULES_PATH = Path(__file__).resolve().parent / "portability_rules.json"
RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))

# Where a cwd-relative path may resolve into and still be "a plugin file" (crew's bundle
# closure + hooks). Anything else that happens to exist (README.md, tests/…) is not a
# runtime dependency the mirror could break.
BUNDLE_DIRS = ("scripts", "skills", "schemas", "docs", "hooks")
SKIP_NAMES = {"__pycache__", ".DS_Store"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
CONTEXT_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)
NAME_DECL_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


def _rx(name: str) -> re.Pattern[str]:
    return re.compile(RULES["regex"][name])


FENCE_RE = _rx("fence")
CWD_RE = _rx("cwd_script")
RELLINK_RE = _rx("relative_link")
NAME_RE = _rx("skill_name")
LAUNCHER_RE = _rx("launcher_call")
SLASH_RE = _rx("slash_form")
ASK_RE = _rx("ask_fallback")
SHELL_FENCES = {lang.lower() for lang in RULES["shell_fence_languages"]}
SCRIPT_EXTS = tuple(RULES["script_extensions"])
IDENTIFIERS = RULES["identifiers"]
RUNTIME_BLOCK = RULES["launcher"]["runtime_block"]
FORK_SENTENCE = RULES["fallbacks"]["fork_worker_sentence"]
DISPATCH_SENTENCE = RULES["fallbacks"]["dispatch_sentence"]
DISPATCH_TRIGGER = RULES["fallbacks"]["dispatch_trigger"]


@dataclass(frozen=True)
class Violation:
    token: str
    file: str
    line: int
    detail: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.file}:{self.line}: [{self.token}] {self.detail}"


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def skill_dirs(root: Path = SKILLS) -> list[Path]:
    return sorted((p.parent for p in root.rglob("SKILL.md")), key=lambda d: (-len(d.parts), str(d)))


def skill_of(path: Path, root: Path = SKILLS) -> Path | None:
    """Deepest ancestor (or self, for a directory) that declares a SKILL.md — crew's attribution."""
    candidates = [path] if path.is_dir() else []
    candidates += list(path.parents)
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
        if not m:
            continue
        decl = NAME_DECL_RE.search(m.group(1))
        if decl:
            names[decl.group(1).strip().strip("\"'")] = d
    return names


def name_of(skill_dir: Path, names: dict[str, Path]) -> str:
    for name, d in names.items():
        if d == skill_dir:
            return name
    return "wicked-garden-" + "-".join(skill_dir.relative_to(SKILLS).parts)


def is_text(path: Path) -> bool:
    try:
        head = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in head[:8000]:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def text_files(root: Path = SKILLS) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in SKIP_NAMES or any(part in SKIP_NAMES for part in p.parts):
            continue
        if is_text(p):
            out.append(p)
    return out


def frontmatter_lines(text: str) -> int:
    m = FRONTMATTER_RE.match(text)
    return text[: m.end()].count("\n") if m else 0


def body_of(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


def _is_within(target: Path, ancestor: Path) -> bool:
    try:
        target.relative_to(ancestor)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Line scanner with fence awareness
# ---------------------------------------------------------------------------

def iter_lines(text: str):
    """Yield (lineno, line, in_fence, fence_is_shell)."""
    fence_marker: str | None = None
    fence_is_shell = True
    for lineno, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m and fence_marker is None:
            fence_marker = m.group(1)
            fence_is_shell = m.group(2).lower() in SHELL_FENCES
            yield lineno, line, True, fence_is_shell
            continue
        if m and fence_marker is not None and m.group(1) == fence_marker and m.group(2) == "":
            fence_marker = None
            yield lineno, line, False, True
            continue
        yield lineno, line, fence_marker is not None, fence_is_shell


def classify_cwd(interp: str, rel: str, file_path: Path, skill: Path | None, repo: Path) -> Violation | None:
    if not ("/" in rel or rel.endswith(SCRIPT_EXTS)):
        return None
    bare = rel[2:] if rel.startswith("./") else rel
    if skill is not None:
        own = (skill / bare).resolve()
        if own.exists() and _is_within(own, skill.resolve()):
            return None  # base-dir-relative path to the skill's OWN file: portable
    first = bare.split("/", 1)[0]
    root_target = repo / bare
    if first in BUNDLE_DIRS and root_target.exists():
        return Violation(
            "cwd-script",
            str(file_path.relative_to(repo)),
            0,
            f"`{interp} {rel}` reaches a plugin file cwd-relatively; write `wicked-garden run {bare}`"
            + (" (or `wicked-garden path …`)" if interp == "cd" else ""),
        )
    return None


def classify_rel(rel: str, file_path: Path, skill: Path | None, names: dict[str, Path], repo: Path) -> Violation | None:
    target = (file_path.parent / rel).resolve()
    if not target.exists():
        return None
    try:
        rel_to_repo = target.relative_to(repo.resolve())
    except ValueError:
        return None
    other = skill_of(target.relative_to(repo.resolve()) and (repo / rel_to_repo))
    where = str(file_path.relative_to(repo))
    if other is not None and (skill is None or other.resolve() != skill.resolve()):
        return Violation(
            "cross-skill-path",
            where,
            0,
            f"`{rel}` → {rel_to_repo} lives in skill `{name_of(other, names)}`; refer to that skill by NAME "
            "(+ its skill-relative file) — the installer lays skills out flat by name",
        )
    if other is not None:
        return None  # inside the referencing skill's own tree
    return Violation(
        "relative-link",
        where,
        0,
        f"`{rel}` → {rel_to_repo} is a shared plugin file; use `wicked-garden path {rel_to_repo}` or a URL",
    )


def scan_text(rel_file: str, text: str, names: dict[str, Path], repo: Path = REPO) -> list[Violation]:
    """The per-line token rules over one file's text (the corpus runs exactly these)."""
    file_path = repo / rel_file
    skill = skill_of(file_path, repo / "skills")
    is_md = rel_file.endswith(".md")
    is_shell_file = rel_file.endswith(".sh")
    fm_end = frontmatter_lines(text) if is_md else 0
    out: list[Violation] = []

    def add(token: str, lineno: int, detail: str) -> None:
        out.append(Violation(token, rel_file, lineno, detail))

    for lineno, line, in_fence, fence_is_shell in iter_lines(text):
        for token, ident in IDENTIFIERS.items():
            if ident in line:
                add(token, lineno, f"`{ident}` is substituted by Claude Code only — use a skill-relative path or the launcher")
        if is_md:
            for m in NAME_RE.finditer(line):
                name = m.group(1)
                if "{" in name or name in names:
                    continue
                add("unresolved-skill-name", lineno, f"`{name}` is not declared by any SKILL.md")
            if lineno > fm_end and SLASH_RE.search(line):
                add("slash-form", lineno, "skills are not slash commands on any CLI — name the skill (`wicked-garden-<x>`) instead")
        shell_ctx = is_shell_file or (is_md and (not in_fence or fence_is_shell))
        if shell_ctx:
            for m in CWD_RE.finditer(line):
                v = classify_cwd(m.group(1), m.group(2).rstrip(".,;:"), file_path, skill, repo)
                if v:
                    add(v.token, lineno, v.detail)
        if is_md:
            for m in RELLINK_RE.finditer(line):
                v = classify_rel(m.group(1).rstrip(".,;:"), file_path, skill, names, repo)
                if v:
                    add(v.token, lineno, v.detail)
    return out


def scan_structure(files_by_skill: dict[Path, list[Path]], names: dict[str, Path], repo: Path = REPO) -> list[Violation]:
    """Per-skill and per-file structural rules (preamble, fork/dispatch/ask fallbacks)."""
    out: list[Violation] = []
    for skill, files in files_by_skill.items():
        skill_md = skill / "SKILL.md"
        skill_text = skill_md.read_text(encoding="utf-8")
        rel_skill_md = str(skill_md.relative_to(repo))
        uses_launcher = any(LAUNCHER_RE.search(f.read_text(encoding="utf-8")) for f in files)
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
            rel = str(f.relative_to(repo))
            if DISPATCH_TRIGGER in text and DISPATCH_SENTENCE not in text:
                out.append(Violation("dispatch-no-fallback", rel, 1,
                                     "dispatches with Skill(skill=…) but lacks the harness-fallback sentence"))
            if "AskUserQuestion" in body_of(text) and not ASK_RE.search(text):
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
    files = text_files(repo / "skills")
    violations: list[Violation] = []
    launcher_calls = 0
    identifier_hits: Counter[str] = Counter()
    name_tokens = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        rel = str(f.relative_to(repo))
        violations.extend(scan_text(rel, text, names, repo))
        # the ## Runtime block MENTIONS the launcher twice; count only real call sites
        launcher_calls += len(LAUNCHER_RE.findall(text.replace(RUNTIME_BLOCK, "")))
        for token, ident in IDENTIFIERS.items():
            identifier_hits[token] += text.count(ident)
        if f.suffix == ".md":
            name_tokens += sum(1 for m in NAME_RE.finditer(text) if "{" not in m.group(1))
    violations.extend(scan_structure(files_by_skill(files), names, repo))
    counts = {
        "files_scanned": len(files),
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


def test_rules_fixture_is_well_formed():
    tokens = {t["token"] for t in RULES["tokens"]}
    assert tokens >= {
        "plugin-root", "skill-dir-var", "cwd-script", "relative-link", "cross-skill-path",
        "unresolved-skill-name", "missing-runtime-preamble", "requires-harness",
    }
    for name in RULES["regex"]:
        re.compile(RULES["regex"][name])  # raises on a Python-incompatible spelling
    assert RUNTIME_BLOCK.startswith(RULES["launcher"]["runtime_heading"] + "\n")
    assert "Relative paths in this skill are relative to the directory that contains this SKILL.md." in RUNTIME_BLOCK


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
    assert _COUNTS["skills"] >= 140, _COUNTS
    assert _COUNTS["plugin_root_refs"] == 0, f"plugin-root refs under skills/: {_COUNTS['plugin_root_refs']}"
    assert _COUNTS["skill_dir_var_refs"] == 0, f"skill-dir-var refs under skills/: {_COUNTS['skill_dir_var_refs']}"
    assert _COUNTS["launcher_calls"] > 200, (
        f"only {_COUNTS['launcher_calls']} launcher calls found — the launcher regex drifted or the "
        "shared-runtime call sites were lost"
    )
    assert _COUNTS["skill_name_tokens"] > 300, f"name resolver saw only {_COUNTS['skill_name_tokens']} tokens"
    assert _COUNTS.get("violations.unresolved-skill-name", 0) == 0


@pytest.mark.parametrize("entry", RULES["corpus"]["quiet"], ids=lambda e: e["text"][:50])
def test_false_positive_corpus_is_quiet(entry):
    got = scan_text(entry["file"], entry["text"], _NAMES)
    assert not got, [str(v) for v in got]


@pytest.mark.parametrize("entry", RULES["corpus"]["trips"], ids=lambda e: f"{e['token']}::{e['text'][:40]}")
def test_positive_corpus_trips_exactly_its_token(entry):
    got = {v.token for v in scan_text(entry["file"], entry["text"], _NAMES)}
    assert got == {entry["token"]}, f"expected {{{entry['token']!r}}}, got {got}"


def test_fence_parser_sees_non_shell_fences():
    """The JS/TS-import false positives are killed by the fence skip — make sure it is exercised."""
    non_shell = 0
    for f in text_files():
        if f.suffix != ".md":
            continue
        for _, _, in_fence, fence_is_shell in iter_lines(f.read_text(encoding="utf-8")):
            if in_fence and not fence_is_shell:
                non_shell += 1
                break
    assert non_shell > 50, non_shell


if __name__ == "__main__":  # pragma: no cover - CLI report for the codemod loop
    print(_report(_VIOLATIONS, _COUNTS))
    sys.exit(1 if _VIOLATIONS else 0)
