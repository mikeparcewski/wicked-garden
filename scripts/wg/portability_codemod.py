#!/usr/bin/env python3
"""portability_codemod.py — mechanical rewrite of skills/ to the cross-CLI convention (F-079).

Dev tooling (scripts/wg/ is excluded from the npm package and from crew's bundle closure).
It applies design W4 §6.1 to every text file under skills/ and reports every rewrite and
every target it could not resolve, so the ~10 % that needs a human is a list, not a hunt.
The lint that judges the result is tests/test_skill_portability.py; both read the same data —
the CANONICAL parity fixture tests/portability_rules.json (vendored from wicked-crew: shared
regexes + fence semantics) and garden's additions in tests/portability_rules.garden.json
(runtime block, fallback sentences, bare-span regexes, codemod knobs).

Usage:
  python3 scripts/wg/portability_codemod.py --dry-run [--report FILE]   report, write nothing
  python3 scripts/wg/portability_codemod.py --write   [--report FILE]   apply + report

Rewrites (in this order, per line, fence-aware where it matters):
  1. `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/<p>" …`,
     `python3|node "${CLAUDE_PLUGIN_ROOT}/<p>" …`, `cd "${CLAUDE_PLUGIN_ROOT}" && uv run python <p>`
        → `wicked-garden run <p> …`  (a script INSIDE the referencing skill's own dir becomes the
          base-dir-relative `python3 scripts/<x>.py` — the four skill-local scripts/ dirs are stdlib-only)
     `sh "…/_python.sh" -c|-` → `wicked-garden python -c|-`;  `X="${CLAUDE_PLUGIN_ROOT}/<dir>"` →
     `X="$(wicked-garden path <dir>)"`;  `cd "${CLAUDE_PLUGIN_ROOT}[/<dir>]"` → `cd "$(wicked-garden root|path <dir>)"`;
     a quoted `"${CLAUDE_PLUGIN_ROOT}/<p>"` continuing a launcher command → `<p>`, elsewhere →
     `"$(wicked-garden path <p>)"`.
  2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/<self>/<rest>")` → read `<rest>` (first occurrence per file
     adds "(relative to this skill's base directory)"); `…/skills/<other>/<rest>` → read the
     `wicked-garden-<other>` skill's `<rest>`; a nested module of the same skill keeps its relative
     path and names the module.
  3. Any other `${CLAUDE_PLUGIN_ROOT}/skills/<x>` → the same self/other/nested forms; any other
     `${CLAUDE_PLUGIN_ROOT}/<shared>` → `<shared>` (first occurrence per file adds
     "(under the plugin root: `wicked-garden path <shared>`)").
  4. `../<x>` that resolves into ANOTHER skill → "the `wicked-garden-<x>` skill's `<rest>`" /
     "`wicked-garden-<x>`" / "the parent skill `wicked-garden-<parent>`"; into a shared file →
     "`<rel>` (plugin root: `wicked-garden path <rel>`)". Unresolvable `../` tokens are left alone.
  5. cwd-relative `python3|node|uv run python scripts/<p>` and `cd scripts/<p>` that exist at the
     plugin root → `wicked-garden run|path …` (skills/qe/refs/campaign-ci.md, a template for the
     TARGET repo's CI, uses `npx wicked-garden@12 …`).
  6. `/wicked-garden:<a>[:<b>]` in skill BODIES → `wicked-garden-<a>-<b>` when that skill exists,
     else `wicked-garden-<a> <b>` (skill + action); frontmatter trigger phrases are left alone.
  7. Inserts (once, exact text from the rules fixture): the `## Runtime` block into every SKILL.md
     whose skill uses the launcher; the fork-worker sentence into every `context: fork` SKILL.md;
     the dispatch-fallback sentence before the first `Skill(skill=` in a file.

Left for a human (reported under "Unresolvable / needs review"): inline-Python heredocs that build
sys.path from the variable, bare `${CLAUDE_PLUGIN_ROOT}` mentions, Python-string forms, slash forms
whose skill/action cannot be mapped, and `../` tokens that look like skill paths but resolve nowhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"
# Two rule files, both data: the CANONICAL parity fixture (vendored byte-for-byte from wicked-crew —
# shared regexes + fence semantics) and garden's own additions (runtime block, fallback sentences,
# bare-span regexes, codemod knobs). See tests/test_skill_portability.py.
CANON = json.loads((REPO / "tests" / "portability_rules.json").read_text(encoding="utf-8"))
RULES = json.loads((REPO / "tests" / "portability_rules.garden.json").read_text(encoding="utf-8"))
RUNTIME_BLOCK = RULES["launcher"]["runtime_block"]
FORK_SENTENCE = RULES["fallbacks"]["fork_worker_sentence"]
DISPATCH_SENTENCE = RULES["fallbacks"]["dispatch_sentence"]
DISPATCH_RE = re.compile(RULES["fallbacks"]["dispatch_trigger_regex"])  # single- AND multi-line `Skill(` … `skill=`
LAUNCHER_RE = re.compile(CANON["regex"]["launcher_call"])
BARE_SPAN_RE = re.compile(RULES["regex"]["bare_script_span"])
BARE_LINE_RE = re.compile(RULES["regex"]["bare_script_line"])
FENCE_RE = re.compile(CANON["regex"]["fence_line"])
# the codemod rewrites MORE than the lint judges: yaml/yml fences too (CI templates carry shell
# `run:` lines) — rewriting toward the launcher is always safe
SHELL_FENCES = {lang.lower() for lang in CANON["fences"]["shell_langs"]} | {l.lower() for l in RULES["codemod"]["shell_langs_extra"]}

VAR = r"\$\{CLAUDE_PLUGIN_ROOT\}"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
NAME_DECL_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
CONTEXT_FORK_RE = re.compile(r"^context:\s*fork\s*$", re.MULTILINE)
SKIP_NAMES = {"__pycache__", ".DS_Store"}
BASE_DIR_NOTE = " (relative to this skill's base directory)"
LAUNCHER_PREFIX_BY_FILE = RULES["codemod"]["launcher_prefix_by_file"]


@dataclass
class Change:
    file: str
    line: int
    kind: str
    old: str
    new: str


@dataclass
class Unresolved:
    file: str
    line: int
    kind: str
    target: str
    note: str


@dataclass
class Report:
    changes: list[Change] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    files_changed: set[str] = field(default_factory=set)


class Catalog:
    def __init__(self, root: Path = SKILLS):
        self.root = root
        self.dirs = sorted((p.parent for p in root.rglob("SKILL.md")), key=lambda d: (-len(d.parts), str(d)))
        self.names: dict[Path, str] = {}
        for d in self.dirs:
            m = FRONTMATTER_RE.match((d / "SKILL.md").read_text(encoding="utf-8"))
            decl = NAME_DECL_RE.search(m.group(1)) if m else None
            self.names[d] = decl.group(1).strip().strip("\"'") if decl else "wicked-garden-" + "-".join(d.relative_to(root).parts)
        self.by_name = {n: d for d, n in self.names.items()}

    def skill_of(self, path: Path) -> Path | None:
        candidates = ([path] if path.is_dir() else []) + list(path.parents)
        for d in candidates:
            if d == self.root or self.root not in d.parents and d != self.root:
                if d == self.root:
                    return None
            try:
                d.relative_to(self.root)
            except ValueError:
                return None
            if d == self.root:
                return None
            if (d / "SKILL.md").exists():
                return d
        return None

    def name_of(self, d: Path) -> str:
        return self.names[d]


CAT = Catalog()


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


def text_files() -> list[Path]:
    return [p for p in sorted(SKILLS.rglob("*"))
            if p.is_file() and p.name not in SKIP_NAMES and not any(x in SKIP_NAMES for x in p.parts) and is_text(p)]


def verb_case(prefix: str) -> str:
    """'Read' at the start of a list item / line, 'read' mid-sentence."""
    return "Read" if re.fullmatch(r"\s*(?:[-*+]|\d+[.)])?\s*(?:\*\*[^*]+\*\*[:.]?\s*)?", prefix) else "read"


class FileRewriter:
    def __init__(self, path: Path, report: Report):
        self.path = path
        self.rel = str(path.relative_to(REPO))
        self.skill = CAT.skill_of(path)
        self.report = report
        self.first_read_done = False
        self.first_shared_done = False
        self.launcher_prefix = LAUNCHER_PREFIX_BY_FILE.get(self.rel, "wicked-garden")
        self.is_md = path.suffix == ".md"
        self.lineno = 0

    # -- helpers -----------------------------------------------------------

    def change(self, kind: str, old: str, new: str) -> None:
        if old != new:
            self.report.changes.append(Change(self.rel, self.lineno, kind, old.strip(), new.strip()))

    def unresolved(self, kind: str, target: str, note: str) -> None:
        self.report.unresolved.append(Unresolved(self.rel, self.lineno, kind, target, note))

    def classify(self, root_rel: str) -> tuple[str, Path | None, str]:
        """('self'|'nested'|'other'|'shared'|'missing', skill dir, skill-relative rest)."""
        target = REPO / root_rel
        exists = target.exists()
        if not root_rel.startswith("skills/"):
            return ("shared" if exists or "{" in root_rel else "missing"), None, root_rel
        owner = CAT.skill_of(target) if exists else None
        if owner is None:
            # tolerate template braces / not-yet-existing files: attribute by path prefix
            for d in CAT.dirs:
                if root_rel.startswith(str(d.relative_to(REPO)) + "/") or root_rel == str(d.relative_to(REPO)):
                    owner = d
                    break
        if owner is None:
            return "missing", None, root_rel
        rest = str(Path(root_rel).relative_to(owner.relative_to(REPO))) if root_rel != str(owner.relative_to(REPO)) else "SKILL.md"
        if self.skill is not None and owner == self.skill:
            return "self", owner, rest
        if self.skill is not None and self.skill in owner.parents:
            return "nested", owner, str(Path(root_rel).relative_to(self.skill.relative_to(REPO)))
        return "other", owner, rest

    def launcher_or_local(self, interp: str, root_rel: str) -> str:
        kind, _, rest = self.classify(root_rel)
        if kind == "missing" and "{" not in root_rel:
            self.unresolved("plugin-root", root_rel, "no such file under the plugin root")
        if kind == "self":
            return f"{interp if interp in ('python3', 'node') else 'python3'} {rest}"
        return f"{self.launcher_prefix} run {root_rel}"

    def prose_ref(self, root_rel: str, *, verb: str | None = None, inline_code: bool = False) -> str:
        """Name-based or base-dir-relative rendering of a plugin path in prose.

        `inline_code=True` means the token already sits inside a backtick span (a command
        with arguments): render the bare path only — self → skill-relative, anything else →
        root-relative (the surrounding command is a launcher call) — no backticks, no note.
        """
        kind, owner, rest = self.classify(root_rel)
        if kind == "missing" and "{" not in root_rel:
            self.unresolved("plugin-root", root_rel, "no such file under the plugin root")
        if inline_code:
            return rest if kind == "self" else root_rel
        lead = f"{verb} " if verb else ""
        if kind == "self":
            note = "" if self.first_read_done else BASE_DIR_NOTE
            self.first_read_done = True
            return f"{lead}`{rest}`{note}"
        if kind == "nested":
            return f"{lead}`{rest}` (the `{CAT.name_of(owner)}` module)"
        if kind == "other":
            name = CAT.name_of(owner)
            v = (verb.lower() if verb else "")
            if rest == "SKILL.md":
                return f"{v + ' ' if v else ''}the `{name}` skill (its `SKILL.md`)"
            return f"{v + ' ' if v else ''}the `{name}` skill's `{rest}`"
        # shared
        note = "" if self.first_shared_done else f" (under the plugin root: `wicked-garden path {root_rel}`)"
        self.first_shared_done = True
        return f"{lead}`{root_rel}`{note}"

    # -- per-line passes ----------------------------------------------------

    def pass_commands(self, line: str, cont_launcher: bool) -> tuple[str, bool]:
        old = line
        # 1a. _python.sh + explicit script
        line = re.sub(rf'sh "{VAR}/scripts/_python\.sh"\s+"{VAR}/([^"]+)"',
                      lambda m: self.launcher_or_local("python3", m.group(1)), line)
        # 1b. _python.sh -c / - (inline python)
        line = re.sub(rf'sh "{VAR}/scripts/_python\.sh"(?=\s+-)', "wicked-garden python", line)
        # 1c. _python.sh with the script on a continuation line
        line = re.sub(rf'sh "{VAR}/scripts/_python\.sh"(?=\s*\\\s*$)', f"{self.launcher_prefix} run", line)
        # 1d. python3|node + quoted root path
        line = re.sub(rf'\b(python3|python|node)\s+"{VAR}/([^"]+)"',
                      lambda m: self.launcher_or_local(m.group(1), m.group(2)), line)
        # 1e. cd root && uv run python <p>
        line = re.sub(rf'cd "{VAR}" && uv run python (\S+)', rf"{self.launcher_prefix} run \1", line)
        # 1f. cd "${ROOT}/<dir>" / cd "${ROOT}"
        line = re.sub(rf'cd "{VAR}/([^"]+)"', r'cd "$(wicked-garden path \1)"', line)
        line = re.sub(rf'cd "{VAR}"', 'cd "$(wicked-garden root)"', line)
        # 1g. assignments
        line = re.sub(rf'\b([A-Za-z_][A-Za-z0-9_]*=)"{VAR}/([^"]+)"', r'\1"$(wicked-garden path \2)"', line)
        # 1h. continuation argument of a launcher command → bare root-relative path
        if cont_launcher:
            line = re.sub(rf'"{VAR}/([^"]+)"', r"\1", line)
        line = self.pass_pystrings(line)
        self.change("command", old, line)
        starts_launcher = bool(re.search(r"(?:^|[\s$(])(?:npx wicked-garden@\S+|wicked-garden) (?:run|python)\b", line))
        continues = line.rstrip().endswith("\\")
        return line, continues and (starts_launcher or cont_launcher)

    def pass_pystrings(self, line: str) -> str:
        """Python-string forms inside inline python: the launcher exports WICKED_GARDEN_ROOT."""
        def pypath(m: re.Match[str]) -> str:
            parts = ", ".join(f'"{seg}"' for seg in m.group(1).split("/"))
            return f'sys.path.insert(0, os.path.join(os.environ["WICKED_GARDEN_ROOT"], {parts}))'

        line = re.sub(rf"sys\.path\.insert\(0, '{VAR}/([^']+)'\)", pypath, line)
        line = re.sub(r"sys\.path\.insert\(0, os\.path\.join\(os\.environ\.get\(['\"]CLAUDE_PLUGIN_ROOT['\"], ['\"]\.['\"]\), ([^)]+)\)\)",
                      r'sys.path.insert(0, os.path.join(os.environ["WICKED_GARDEN_ROOT"], \1))', line)
        line = re.sub(r"Path\(os\.environ\.get\(['\"]CLAUDE_PLUGIN_ROOT['\"], ['\"]\.['\"]\)\)\.resolve\(\)",
                      'Path(os.environ["WICKED_GARDEN_ROOT"])', line)
        if 'os.environ["WICKED_GARDEN_ROOT"]' in line and line.lstrip().startswith("import sys;"):
            line = line.replace("import sys;", "import os, sys;", 1)
        return line

    @staticmethod
    def retarget_inline_python_openers(lines: list[str]) -> list[int]:
        """`python3 -c "` blocks that build sys.path from the plugin root must run through the
        launcher (`wicked-garden python -c "`) so WICKED_GARDEN_ROOT is set. Returns the
        opener line indexes that were retargeted (mutates `lines`)."""
        hits = []
        for i, l in enumerate(lines):
            if l.strip() not in ('python3 -c "', 'python -c "'):
                continue
            j = i + 1
            uses_root = False
            while j < len(lines) and j - i < 80 and lines[j].strip() != '"':
                if "CLAUDE_PLUGIN_ROOT" in lines[j] or 'os.environ["WICKED_GARDEN_ROOT"]' in lines[j]:
                    uses_root = True
                j += 1
            if uses_root:
                lines[i] = re.sub(r"\bpython3? -c", "wicked-garden python -c", lines[i], count=1)
                hits.append(i)
        return hits

    def pass_read(self, line: str) -> str:
        old = line
        pat = re.compile(rf'`?Read\("{VAR}/skills/([^"]+)"\)`?')

        def repl(m: re.Match[str]) -> str:
            return self.prose_ref("skills/" + m.group(1), verb=verb_case(line[: m.start()]))

        line = pat.sub(repl, line)
        self.change("read", old, line)
        return line

    def pass_generic(self, line: str) -> str:
        old = line
        # quoted shared paths in shell context that survived the command pass
        line = re.sub(rf'"{VAR}/((?:scripts|schemas|docs|hooks)/[^"]+)"', r'"$(wicked-garden path \1)"', line)
        # backticked
        line = re.sub(rf"`{VAR}/([^`\s]+)`", lambda m: self.prose_ref(m.group(1)), line)
        # bare (not followed by a quote/backtick opener); inside an open code span → path only,
        # and when that span goes on with ARGUMENTS it is a command: emit the launcher form (a
        # cwd-relative `scripts/x.py <args>` is an instruction no host can execute)
        def bare_repl(m: re.Match[str]) -> str:
            inside_span = line[: m.start()].count("`") % 2 == 1
            target = m.group(1).rstrip(".")
            trailer = "." if m.group(1).endswith(".") else ""
            if inside_span:
                rest_of_span = line[m.end():].split("`", 1)[0]
                if rest_of_span.strip() and re.search(r"\.(?:py|mjs|js|cjs|sh)$", target):
                    return self.launcher_or_local("python3", target) + trailer
            return self.prose_ref(target, inline_code=inside_span) + trailer

        line = re.sub(rf"{VAR}/([^\s`\"')\],]+)", bare_repl, line)
        self.change("generic", old, line)
        if "${CLAUDE_PLUGIN_ROOT}" in line or "CLAUDE_PLUGIN_ROOT" in line:
            self.unresolved("plugin-root", line.strip()[:120], "bare / Python-string / heredoc form — rewrite by hand (WICKED_GARDEN_ROOT is exported by the launcher)")
        return line

    def pass_relative(self, line: str) -> str:
        if not self.is_md:
            return line
        old = line
        # markdown links first
        def link_repl(m: re.Match[str]) -> str:
            label, target = m.group(1), m.group(2)
            rendered = self.render_relative(target, label=label)
            return rendered if rendered is not None else m.group(0)

        line = re.sub(r"\[([^\]]*)\]\(((?:\.\./)+[A-Za-z0-9_][A-Za-z0-9_./-]*)\)", link_repl, line)

        def token_repl(m: re.Match[str]) -> str:
            lead, open_tick, target, close_tick = m.group(1), m.group(2), m.group(3), m.group(4)
            rendered = self.render_relative(target)
            if rendered is None:
                return m.group(0)
            # a token that already sat in backticks is replaced span-and-all (the rendering
            # carries its own code spans); a bare token keeps its leading character
            return lead + rendered if (open_tick or not close_tick) else lead + rendered + close_tick

        # backticked or bare tokens (leading char kept)
        line = re.sub(r"(^|[^A-Za-z0-9_./`-])(`?)((?:\.\./)+[A-Za-z0-9_][A-Za-z0-9_./-]*)(`?)", token_repl, line)
        self.change("relative", old, line)
        return line

    def render_relative(self, target: str, label: str | None = None) -> str | None:
        clean = target.rstrip(".,;:")
        resolved = (self.path.parent / clean).resolve()
        if not resolved.exists():
            if re.match(r"(?:\.\./)+[a-z][a-z0-9-]+/", clean) and (SKILLS / clean.lstrip("./").split("/")[0]).exists():
                self.unresolved("relative-link", target, "looks like a skill path but resolves nowhere")
            return None
        try:
            rel_to_repo = str(resolved.relative_to(REPO.resolve()))
        except ValueError:
            return None
        owner = CAT.skill_of(REPO / rel_to_repo)
        if owner is None:
            return f"`{rel_to_repo}` (plugin root: `wicked-garden path {rel_to_repo}`)"
        if self.skill is not None and owner.resolve() == self.skill.resolve():
            return None  # own tree — fine as is
        name = CAT.name_of(owner)
        rest = str(Path(rel_to_repo).relative_to(owner.relative_to(REPO))) if rel_to_repo != str(owner.relative_to(REPO)) else "SKILL.md"
        if rest == "SKILL.md":
            if self.skill is not None and owner in self.skill.parents:
                return f"the parent skill `{name}`"
            plain = (label or "").strip("` ")
            if label and plain and not plain.endswith("SKILL.md") and plain != name and "/" not in plain:
                return f"{plain} (`{name}`)"
            return f"`{name}`"
        return f"the `{name}` skill's `{rest}`"

    def pass_bare_spans(self, line: str, shell_ctx: bool, in_fence: bool, prev_nonblank: str) -> str:
        """A bare `scripts/<x>.py <args>` code span, or a shell-fence line that starts with such a
        path (and is not the continuation of a `\\` command), has no interpreter at all — no host
        can run it. Skill-local scripts get `python3 <rel>`; plugin scripts the launcher form."""
        old = line

        def form(p: str) -> str | None:
            if self.skill and (self.skill / p).exists():
                return f"python3 {p}"
            if (REPO / p).exists():
                return f"{self.launcher_prefix} run {p}"
            return None

        if not in_fence:
            def span_repl(m: re.Match[str]) -> str:
                f = form(m.group(1))
                return f"`{f}{m.group(2)}`" if f else m.group(0)

            line = BARE_SPAN_RE.sub(span_repl, line)
        elif shell_ctx and not prev_nonblank.rstrip().endswith("\\"):
            m = BARE_LINE_RE.match(line)
            if m:
                f = form(m.group(2))
                if f:
                    line = f"{m.group(1)}{f}{m.group(3) or ''}"
        self.change("cwd-script", old, line)
        return line

    def pass_cwd(self, line: str, shell_ctx: bool) -> str:
        if not shell_ctx:
            return line
        old = line

        def run_repl(m: re.Match[str]) -> str:
            interp, p = m.group(1), m.group(2)
            if (REPO / p).exists() and not (self.skill and (self.skill / p).exists()):
                return f"{m.group(0)[: m.start(1) - m.start(0)]}{self.launcher_prefix} run {p}"
            return m.group(0)

        line = re.sub(r"(?<![\w/.$\"'-])(python3|node|uv run python)\s+(scripts/[A-Za-z0-9_./-]+)", run_repl, line)

        def cd_repl(m: re.Match[str]) -> str:
            p = m.group(1)
            if (REPO / p).is_dir():
                return f'cd "$({self.launcher_prefix} path {p})"'
            return m.group(0)

        line = re.sub(r"(?<![\w/.$\"'-])cd (scripts/[A-Za-z0-9_./-]+)", cd_repl, line)

        # skill-local scripts documented as a bare file name (`python3 gh_ops.py …`) — the
        # file lives in the skill's own scripts/, so spell the base-dir-relative path
        def local_repl(m: re.Match[str]) -> str:
            interp, name = m.group(1), m.group(2)
            if self.skill and (self.skill / "scripts" / name).exists() and not (self.skill / name).exists():
                return f"{interp} scripts/{name}"
            return m.group(0)

        line = re.sub(r"(?<![\w/.$\"'-])(python3|python)\s+([A-Za-z0-9_-]+\.py)\b", local_repl, line)
        self.change("cwd-script", old, line)
        return line

    def pass_slash(self, line: str) -> str:
        old = line

        def repl(m: re.Match[str]) -> str:
            parts = m.group(1).split(":")
            full = "wicked-garden-" + "-".join(parts)
            if full in CAT.by_name:
                return full
            head = "wicked-garden-" + parts[0]
            if len(parts) >= 2 and head in CAT.by_name:
                return f"{head} {':'.join(parts[1:])}"
            self.unresolved("slash-form", m.group(0), "no skill or skill+action mapping — rewrite by hand")
            return m.group(0)

        line = re.sub(r"(?<![A-Za-z0-9_})/])/wicked-garden:([a-z0-9:-]+)", repl, line)
        self.change("slash-form", old, line)
        return line

    # -- driver -------------------------------------------------------------

    def rewrite(self, text: str) -> str:
        fm_end = 0
        if self.is_md:
            m = FRONTMATTER_RE.match(text)
            fm_end = text[: m.end()].count("\n") if m else 0
        out: list[str] = []
        cont_launcher = False
        fence_marker: str | None = None
        fence_is_shell = True
        lines = text.split("\n")
        for idx in self.retarget_inline_python_openers(lines):
            self.lineno = idx + 1
            self.change("command", 'python3 -c "', lines[idx])
        prev_nonblank = ""
        for i, line in enumerate(lines, 1):
            self.lineno = i
            fm = FENCE_RE.match(line)
            if fm and fence_marker is None and (fm.group(1) or fm.group(2)):
                run = fm.group(1) or fm.group(2)
                fence_marker, fence_is_shell = run, (fm.group(3) or "").lower() in SHELL_FENCES
                in_fence = False
            elif fence_marker is not None and re.match(r"^\s*" + re.escape(fence_marker[0]) + "{" + str(len(fence_marker)) + r",}\s*$", line):
                fence_marker = None
                in_fence = False
            else:
                in_fence = fence_marker is not None
            shell_ctx = self.path.suffix == ".sh" or (self.is_md and (not in_fence or fence_is_shell))
            if "${CLAUDE_PLUGIN_ROOT}" in line:
                line, cont_launcher = self.pass_commands(line, cont_launcher)
                if "${CLAUDE_PLUGIN_ROOT}" in line:
                    line = self.pass_read(line)
                if "${CLAUDE_PLUGIN_ROOT}" in line:
                    line = self.pass_generic(line)
            else:
                cont_launcher = cont_launcher and line.rstrip().endswith("\\")
                if "CLAUDE_PLUGIN_ROOT" in line:
                    before = line
                    line = self.pass_pystrings(line)
                    self.change("command", before, line)
                    if "CLAUDE_PLUGIN_ROOT" in line:
                        self.unresolved("plugin-root", line.strip()[:120], "bare identifier in prose/code — rewrite by hand")
            if "../" in line:
                line = self.pass_relative(line)
            line = self.pass_cwd(line, shell_ctx)
            if self.is_md and ("scripts/" in line or "hooks/" in line):
                line = self.pass_bare_spans(line, shell_ctx, in_fence, prev_nonblank)
            if self.is_md and i > fm_end and "/wicked-garden:" in line:
                line = self.pass_slash(line)
            out.append(line)
            if line.strip():
                prev_nonblank = line
        self.ensure_import_os(out)
        return "\n".join(out)

    def ensure_import_os(self, lines: list[str]) -> None:
        """An inline-python block that now reads os.environ needs `os` imported: widen the
        nearest preceding `import sys[, …]` line (within the same block) when no `import os`
        is in sight."""
        for i, line in enumerate(lines):
            if 'os.environ["WICKED_GARDEN_ROOT"]' not in line or line.lstrip().startswith("import "):
                continue
            window = range(max(0, i - 8), i)
            if any(re.match(r"\s*import (?:.*\b)?os\b", lines[j]) or re.match(r"\s*import\b.*\bos\b", lines[j]) for j in window):
                continue
            for j in reversed(window):
                m = re.match(r"^(\s*)import ([A-Za-z_][\w, ]*)$", lines[j])
                if m and "sys" in [n.strip() for n in m.group(2).split(",")]:
                    before = lines[j]
                    lines[j] = f"{m.group(1)}import os, {m.group(2)}"
                    self.lineno = j + 1
                    self.change("command", before, lines[j])
                    break


# ---------------------------------------------------------------------------
# Inserts
# ---------------------------------------------------------------------------

def insert_runtime_block(text: str) -> str:
    if RUNTIME_BLOCK in text:
        return text
    lines = text.split("\n")
    m = FRONTMATTER_RE.match(text)
    start = text[: m.end()].count("\n") if m else 0
    idx = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), None)
    block = RUNTIME_BLOCK.split("\n")
    # A router that also dispatches workers gets the dispatch-fallback sentence as the
    # block's last line (one paragraph of "how this skill reaches things off-Claude")
    # instead of a separate paragraph — the non-fork SKILL.md line cap is tight.
    if DISPATCH_RE.search(text) and DISPATCH_SENTENCE not in text:
        block = block + [DISPATCH_SENTENCE]
    if idx is None:
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines + [""] + block) + "\n"
    before = lines[:idx]
    while before and before[-1] == "":
        before.pop()
    return "\n".join(before + [""] + block + [""] + lines[idx:])


def insert_fork_sentence(text: str) -> str:
    if FORK_SENTENCE in text:
        return text
    lines = text.split("\n")
    m = FRONTMATTER_RE.match(text)
    start = text[: m.end()].count("\n") if m else 0
    idx = next((i for i in range(start, len(lines)) if lines[i].startswith("# ")), None)
    at = (idx + 1) if idx is not None else start
    insert = ["", FORK_SENTENCE] if idx is not None else [FORK_SENTENCE, ""]
    return "\n".join(lines[:at] + insert + lines[at:])


def first_dispatch_line(lines: list[str]) -> int | None:
    """Index of the first `Skill(skill=` line, or of a `Skill(` opener whose next non-blank
    line starts with `skill=` (the multi-line dispatch block)."""
    for i, l in enumerate(lines):
        if re.search(r"Skill\(\s*skill=", l):
            return i
        if re.search(r"Skill\(\s*$", l):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("skill="):
                return i
    return None


def insert_dispatch_sentence(text: str) -> str:
    if not DISPATCH_RE.search(text) or DISPATCH_SENTENCE in text:
        return text
    lines = text.split("\n")
    first = first_dispatch_line(lines)
    if first is None:
        return text
    # if inside a fence, back up to its opener
    fence_marker = None
    opener = None
    for i in range(first + 1):
        fm = FENCE_RE.match(lines[i])
        if fm and fence_marker is None and (fm.group(1) or fm.group(2)):
            fence_marker, opener = (fm.group(1) or fm.group(2)), i
        elif fence_marker is not None and re.match(r"^\s*" + re.escape(fence_marker[0]) + "{" + str(len(fence_marker)) + r",}\s*$", lines[i]):
            fence_marker, opener = None, None
    at = opener if fence_marker is not None and opener is not None else first
    indent = re.match(r"\s*", lines[at]).group(0)
    insert = [indent + DISPATCH_SENTENCE, ""]
    if at > 0 and lines[at - 1].strip() != "":
        insert = [""] + insert
    return "\n".join(lines[:at] + insert + lines[at:])


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(write: bool) -> Report:
    report = Report()
    files = text_files()
    rewritten: dict[Path, str] = {}
    for f in files:
        original = f.read_text(encoding="utf-8")
        new = FileRewriter(f, report).rewrite(original)
        rewritten[f] = new
    # inserts need the post-rewrite view of every skill's files
    by_skill: dict[Path, list[Path]] = {d: [] for d in CAT.dirs}
    for f in files:
        s = CAT.skill_of(f)
        if s is not None:
            by_skill[s].append(f)
    for skill, own in by_skill.items():
        skill_md = skill / "SKILL.md"
        text = rewritten[skill_md]
        if any(LAUNCHER_RE.search(rewritten[f]) for f in own):
            new = insert_runtime_block(text)
            if new != text:
                report.changes.append(Change(str(skill_md.relative_to(REPO)), 0, "insert-runtime", "", "## Runtime block"))
                text = new
        fm = FRONTMATTER_RE.match(text)
        if fm and CONTEXT_FORK_RE.search(fm.group(1)):
            new = insert_fork_sentence(text)
            if new != text:
                report.changes.append(Change(str(skill_md.relative_to(REPO)), 0, "insert-fork", "", "fork-worker sentence"))
                text = new
        rewritten[skill_md] = text
    for f in files:
        if f.suffix == ".md":
            new = insert_dispatch_sentence(rewritten[f])
            if new != rewritten[f]:
                report.changes.append(Change(str(f.relative_to(REPO)), 0, "insert-dispatch", "", "dispatch-fallback sentence"))
                rewritten[f] = new
    for f in files:
        if rewritten[f] != f.read_text(encoding="utf-8"):
            report.files_changed.add(str(f.relative_to(REPO)))
            if write:
                f.write_text(rewritten[f], encoding="utf-8")
    return report


def render(report: Report, write: bool) -> str:
    out = []
    for c in report.changes:
        if c.kind.startswith("insert"):
            out.append(f"{c.file}: [{c.kind}] {c.new}")
        else:
            out.append(f"{c.file}:{c.line}: [{c.kind}]\n    - {c.old}\n    + {c.new}")
    out.append("")
    out.append("Unresolvable / needs review:")
    if not report.unresolved:
        out.append("  (none)")
    for u in report.unresolved:
        out.append(f"  {u.file}:{u.line}: [{u.kind}] {u.target} — {u.note}")
    out.append("")
    kinds = Counter(c.kind for c in report.changes)
    out.append(f"{'APPLIED' if write else 'DRY-RUN'}: {len(report.changes)} changes in {len(report.files_changed)} files "
               f"({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))}); {len(report.unresolved)} unresolvable")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--report", type=Path, help="also write the report to this file")
    args = ap.parse_args(argv)
    report = run(write=args.write)
    text = render(report, args.write)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
        print(text.splitlines()[-1])
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
