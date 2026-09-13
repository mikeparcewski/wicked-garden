"""Governed-grounding lint (wicked-garden #1130, DES-GROUNDING-001 §7) — fails the build on a violation.

A governed worker (a unit of a wicked-crew run, ``WICKED_RUN_ID`` set) grounds through the
estate stdio shim (``scripts/_estate_client.py``) in ``--readonly`` with the store pinned
from the worker environment. The raw WRITE CLI — ``wicked-estate index | scip | tfstate |
import-telemetry | compact | watch`` and ``wicked-estate clusters --annotate`` — mutates the
shared project graph and is NEVER a rung of a governed ladder; wicked-core's gate hook
denies it (core #471), and a skill that coaches it would send every seat into a denial.

Two rules over every text file under ``skills/`` (refs included — they are delivered with
the skill on every CLI):

* ``governed-write-cli`` — inside a GOVERNED BLOCK, a line that spells a write-CLI
  invocation must also spell a prohibition (``never`` / ``not a rung`` / ``do not`` /
  ``must not`` / ``denied`` / ``refused`` / ``forbidden``). A governed block is (a) a
  Markdown section whose heading mentions ``governed`` — up to the next heading of the
  same or a higher level — or (b) a paragraph / list-item run (contiguous non-blank lines,
  fenced code included) any line of which mentions ``governed``. Outside governed blocks
  the write CLI stays legitimate (a human session indexes its own repo).
* ``governed-ladder-names-the-shim`` — the skills that carry a grounding ladder
  (``search``, ``repo-learn``, ``mem``) must have a governed block that names the shim
  (``_estate_client.py`` or ``estate_memory.py``) together with the literal ``--readonly``
  token — the FIRST rung of the governed ladder, and the argv shape the fence allows.

The allowlist is EMPTY on purpose: a violation is fixed in the skill text. Run directly for
the report: ``python3 tests/test_skill_governed_grounding.py``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
SKIP_NAMES = {"__pycache__", ".DS_Store", "node_modules", ".venv"}

WRITE_VERBS = ("index", "scip", "tfstate", "import-telemetry", "compact", "watch")
# `wicked-estate <write verb>` — the program word may carry `.exe`; `clusters` writes only with
# `--annotate` (judged on the same line, the way the fence judges the same segment).
WRITE_CLI_RE = re.compile(
    r"wicked-estate(?:\.exe)?\s+(?:" + "|".join(re.escape(v) for v in WRITE_VERBS) + r")(?![A-Za-z0-9_-])"
)
ANNOTATE_RE = re.compile(r"wicked-estate(?:\.exe)?\s+clusters\b[^\n]*--annotate|clusters\s+--annotate")
GOVERNED_RE = re.compile(r"\bgoverned\b", re.IGNORECASE)
PROHIBITION_RE = re.compile(
    r"\b(?:never|not a rung|do not|must not|don't|denied|denies|refus(?:e|ed|es)|forbidden|no longer)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
SHIM_RE = re.compile(r"_estate_client\.py|estate_memory\.py")
READONLY_TOKEN = "--readonly"

# The skills whose ladder MUST open, in governed mode, with the shim in --readonly.
LADDER_SKILLS = ("skills/search/SKILL.md", "skills/repo-learn/SKILL.md", "skills/mem/SKILL.md")


@dataclass(frozen=True)
class Violation:
    token: str
    file: str
    line: int
    detail: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return f"{self.file}:{self.line}: [{self.token}] {self.detail}"


def governed_lines(text: str) -> set[int]:
    """1-based line numbers that sit inside a governed block (heading section or paragraph)."""
    lines = text.split("\n")
    governed: set[int] = set()

    # (a) heading sections: a heading mentioning "governed" owns every line up to the next
    #     heading of the same or a higher level (a smaller `#` count).
    open_level: int | None = None
    for i, line in enumerate(lines, 1):
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            if open_level is not None and level <= open_level:
                open_level = None
            if open_level is None and GOVERNED_RE.search(line):
                open_level = level
        if open_level is not None:
            governed.add(i)

    # (b) paragraphs / list-item runs: contiguous non-blank lines; any "governed" mention
    #     marks the whole run. Fenced code inside the run is part of it (a rung is often a fence).
    run: list[int] = []

    def flush() -> None:
        if run and any(GOVERNED_RE.search(lines[n - 1]) for n in run):
            governed.update(run)
        run.clear()

    in_fence = False
    for i, line in enumerate(lines, 1):
        if re.match(r"^\s*(?:```|~~~)", line):
            in_fence = not in_fence
            run.append(i)
            continue
        if line.strip() or in_fence:
            run.append(i)
        else:
            flush()
    flush()
    return governed


def write_cli_hits(line: str) -> list[str]:
    hits = [m.group(0) for m in WRITE_CLI_RE.finditer(line)]
    hits += [m.group(0) for m in ANNOTATE_RE.finditer(line)]
    return hits


def scan_text(rel_file: str, text: str) -> list[Violation]:
    out: list[Violation] = []
    governed = governed_lines(text)
    for lineno, line in enumerate(text.split("\n"), 1):
        if lineno not in governed:
            continue
        hits = write_cli_hits(line)
        if hits and not PROHIBITION_RE.search(line):
            out.append(Violation(
                "governed-write-cli", rel_file, lineno,
                f"`{hits[0]}` is a write-CLI invocation inside a governed-mode block — the write CLI is "
                "never a rung in a governed run; ground through the estate shim in --readonly "
                "(or spell the prohibition on the same line)",
            ))
    return out


def ladder_names_the_shim(text: str) -> bool:
    """A governed block contains a line naming the shim together with the literal `--readonly`."""
    governed = governed_lines(text)
    lines = text.split("\n")
    return any(SHIM_RE.search(lines[n - 1]) and READONLY_TOKEN in lines[n - 1] for n in governed)


def text_files(root: Path = SKILLS) -> Iterator[Path]:
    for p in sorted(root.rglob("*.md")):
        if p.is_file() and not any(part in SKIP_NAMES for part in p.parts):
            yield p


def scan_repo(repo: Path = REPO) -> tuple[list[Violation], dict[str, int]]:
    violations: list[Violation] = []
    files = 0
    governed_files = 0
    write_cli_mentions = 0
    for f in text_files(repo / "skills"):
        files += 1
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(repo).as_posix()
        if governed_lines(text):
            governed_files += 1
        write_cli_mentions += sum(len(write_cli_hits(l)) for l in text.split("\n"))
        violations.extend(scan_text(rel, text))
    counts = {
        "files_scanned": files,
        "files_with_governed_blocks": governed_files,
        "write_cli_mentions": write_cli_mentions,
        "violations": len(violations),
    }
    return violations, counts


def _report(violations: Iterable[Violation], counts: dict[str, int]) -> str:
    lines = [str(v) for v in sorted(violations, key=lambda v: (v.file, v.line))]
    lines.append("counts: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_VIOLATIONS, _COUNTS = scan_repo()


def test_no_write_cli_rung_in_any_governed_block():
    """Every skill text: a governed-mode block never coaches the write CLI. Allowlist: none."""
    assert not _VIOLATIONS, (
        f"{len(_VIOLATIONS)} governed-grounding violation(s) under skills/ — the write CLI "
        "(`wicked-estate index|scip|tfstate|import-telemetry|compact|watch`, `clusters --annotate`) "
        "is never a rung in a governed run; ground through the estate shim in --readonly:\n"
        + _report(_VIOLATIONS, _COUNTS)
    )


def test_scan_is_not_vacuous():
    """The rule must be exercised: governed blocks exist, and the write CLI is mentioned somewhere
    (a human-session `index` step) — otherwise a regex drift could hide every hit."""
    assert _COUNTS["files_scanned"] > 300, _COUNTS
    assert _COUNTS["files_with_governed_blocks"] >= 5, _COUNTS
    assert _COUNTS["write_cli_mentions"] >= 5, _COUNTS


@pytest.mark.parametrize("rel", LADDER_SKILLS)
def test_governed_ladder_opens_with_the_shim_in_readonly(rel):
    """search / repo-learn / mem: the governed rung names the shim AND the literal --readonly —
    the FIRST rung in governed mode and the argv shape the gate hook allows (core #471)."""
    text = (REPO / rel).read_text(encoding="utf-8")
    assert governed_lines(text), f"{rel} has no governed-mode block"
    assert ladder_names_the_shim(text), (
        f"{rel}: no governed block names the shim (_estate_client.py / estate_memory.py) "
        f"together with `{READONLY_TOKEN}`"
    )


@pytest.mark.parametrize("rel", ("skills/search/SKILL.md", "skills/repo-learn/SKILL.md"))
def test_governed_ladder_forbids_the_write_cli_explicitly(rel):
    """The two ladders spell the prohibition — a reader must not have to infer it."""
    text = (REPO / rel).read_text(encoding="utf-8")
    lines = text.split("\n")
    governed = governed_lines(text)
    assert any(
        write_cli_hits(lines[n - 1]) and PROHIBITION_RE.search(lines[n - 1]) for n in governed
    ), f"{rel}: no governed line forbids the write CLI by name"


# --- regression corpus: the rule, not the repo ------------------------------------------

_TRIPS = [
    ("heading section, shell fence rung",
     "## In a governed run\n\n1. Refresh first:\n```bash\nwicked-estate index .\n```\n"),
    ("paragraph mentioning governed, inline rung",
     "In governed mode run `wicked-estate index <path>` and then query.\n"),
    ("list item run, annotate",
     "- Governed workers: `wicked-estate clusters --annotate --db x` then read.\n"),
    ("heading section, later paragraph",
     "## Governed runs\n\nSome intro.\n\nThen `wicked-estate compact` to shrink the store.\n"),
    ("write verb with .exe",
     "In a governed run: `wicked-estate.exe scip load.scip`.\n"),
    ("prohibition on a DIFFERENT line does not excuse the rung",
     "## Governed\n\nNever write the graph.\nRun `wicked-estate watch .` to keep it fresh.\n"),
]

_QUIET = [
    ("prohibition on the same line",
     "In governed mode the write CLI (`wicked-estate index|scip|compact`) is never a rung.\n"),
    ("never + clusters --annotate",
     "- Governed: never `wicked-estate clusters --annotate`; `clusters` alone is fine.\n"),
    ("write CLI outside any governed block",
     "## Index / freshness\n\n```bash\nwicked-estate index <path>\n```\n\n## Governed\n\nUse the shim.\n"),
    ("read verbs in a governed block",
     "In a governed run: `wicked-estate stats --db x`, `wicked-estate blast-radius X`, `wicked-estate clusters --json`.\n"),
    ("heading section closed by a same-level heading",
     "## Governed\n\nUse the shim.\n\n## Local\n\n`wicked-estate index .`\n"),
    ("heading section closed by a higher-level heading",
     "### Governed rung\n\nshim\n\n## Build\n\n`wicked-estate index .`\n"),
    ("the word inside another word is not a mention",
     "Ungovernedly, run `wicked-estate index .`\n"),
    ("shim rung with --readonly",
     "In a governed run: `wicked-garden run scripts/_estate_client.py --readonly call '{}'`\n"),
]


@pytest.mark.parametrize("case", _TRIPS, ids=lambda c: c[0])
def test_corpus_trips(case):
    _, text = case
    got = scan_text("skills/x/SKILL.md", text)
    assert len(got) == 1 and got[0].token == "governed-write-cli", [str(v) for v in got]


@pytest.mark.parametrize("case", _QUIET, ids=lambda c: c[0])
def test_corpus_quiet(case):
    _, text = case
    got = scan_text("skills/x/SKILL.md", text)
    assert not got, [str(v) for v in got]


def test_ladder_probe_needs_shim_and_readonly_on_one_governed_line():
    assert ladder_names_the_shim("Governed: `… scripts/_estate_client.py --readonly health`\n")
    assert not ladder_names_the_shim("Governed: `… scripts/_estate_client.py health`\n")
    assert not ladder_names_the_shim("Local: `… scripts/_estate_client.py --readonly health`\n")
    assert not ladder_names_the_shim("Governed: spell --readonly.\n\nElsewhere: `_estate_client.py`\n")


if __name__ == "__main__":  # pragma: no cover - CLI report
    print(_report(_VIOLATIONS, _COUNTS))
    sys.exit(1 if _VIOLATIONS else 0)
