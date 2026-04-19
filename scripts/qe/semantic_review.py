#!/usr/bin/env python3
"""Semantic reviewer — spec-to-code alignment verification (issue #444).

Autonomous post-implementation pass that extracts numbered acceptance criteria
(AC-*) and functional requirements (FR-*/REQ-*) from clarify-phase specs
(``acceptance-criteria.md``, ``objective.md``) and compares them against the
build-phase implementation corpus plus test results.

Emits a structured Gap Report (JSON) per spec item with ``status`` in
``{aligned, divergent, missing}``, confidence score, evidence, and reason.

This complements — but does NOT replace — ``verification_protocol.py``
check #6 (traceability), which verifies existence of req → design → code →
test chains. Semantic review asks a different question: given the chain
exists, does the code actually implement what the AC described?

CLI::

    semantic_review.py review \\
        --project-dir <dir> [--ac-file <path>] [--objective-file <path>] \\
        [--impl-dir <dir>] [--test-dir <dir>] [--output <json-path>]

    semantic_review.py constraints \\
        --adr-dir <dir> [--output <json-path>]

Python API::

    from semantic_review import (
        extract_spec_items, generate_gap_report, extract_adr_constraints,
    )

Design notes
------------
- **Stdlib-only**. No external deps. Cross-platform.
- **Heuristic-based** — LLM-free. Uses keyword overlap + reference counting
  and a curated list of ``constraint signals`` (numeric limits, scoping
  phrases like "per session", modal verbs).
- **Conservative** on missing — only reports MISSING when the AC identifier
  literal is absent from both the implementation corpus and the test corpus.
- **Conservative** on aligned — requires the AC identifier in BOTH corpora
  AND a minimum keyword overlap with the code context around the reference.
- **Divergent** — everything else where the AC is referenced but signals
  don't line up. Confidence score reports how sure we are.

The agent consuming this output (``agents/qe/semantic-reviewer.md``) can
promote MISSING/DIVERGENT findings to gate conditions when complexity >= 3.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Spec-id extraction — accept AC-*, FR-*, REQ-* (with optional domain infix,
# e.g. REQ-auth-3). Matches existing patterns used by verification_protocol.py
# and traceability_generator.
_SPEC_ID_RE = re.compile(
    r"\b(?:AC|FR|REQ|NFR|US)-[A-Za-z]*-?\d+\b",
)

# Table-row AC extraction  (from verification_protocol._AC_TABLE_ROW_RE)
_AC_TABLE_ROW_RE = re.compile(
    r"\|\s*(?P<id>AC-\d+|[A-Z]{1,4}-\d+|\d+)\s*\|"
    r"\s*(?P<desc>[^|]+)\s*\|"
    r"\s*(?P<test>[^|]*)\s*\|",
    re.IGNORECASE,
)

# List-style AC extraction
_AC_LIST_RE = re.compile(
    r"[-*]\s+(?:\*\*)?(?P<id>AC-\d+|[A-Z]{1,4}-\d+)(?:\*\*)?\s*[:\-]\s*(?P<desc>.+)",
    re.IGNORECASE,
)

# Inline AC extraction (e.g. "AC1: Given ... When ... Then ...")
_AC_INLINE_RE = re.compile(
    r"(?P<id>AC\d+|[A-Z]{1,4}-\d+|AC-\d+)\s*[:\-]\s*(?P<desc>Given[^\n]+)",
    re.IGNORECASE,
)

# Constraint signals — numeric quantifiers, scoping qualifiers, and modal
# verbs that frequently appear in ACs and must be honored verbatim.
_NUMERIC_CONSTRAINT_RE = re.compile(
    r"\b(\d+)\s*(ms|s|seconds?|min(?:utes?)?|hours?|days?|%|requests?|"
    r"attempts?|tries|sessions?|users?|bytes?|kb|mb|gb|tokens?|items?)\b",
    re.IGNORECASE,
)

_SCOPE_PHRASE_RE = re.compile(
    r"\bper\s+(session|request|user|tenant|account|minute|hour|day|page|call|token|device|ip)\b",
    re.IGNORECASE,
)

_MODAL_DIRECTIVE_RE = re.compile(
    r"\b(MUST NOT|MUST|SHALL NOT|SHALL|SHOULD NOT|SHOULD|REQUIRED|FORBIDDEN)\b",
)

# Word extraction for overlap scoring — alphanumeric tokens of length 3+,
# lowercase normalised, minus stopwords.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")

_STOPWORDS = frozenset({
    "the", "and", "for", "when", "then", "given", "that", "with", "this",
    "has", "have", "will", "shall", "should", "must", "not", "are", "was",
    "were", "from", "user", "users", "system", "code", "test", "case",
    "example", "into", "than", "less", "more", "which", "while", "its",
    "any", "all", "one", "two", "three", "four", "five", "also", "their",
    "been", "being", "upon", "other", "some", "such", "each", "them",
    "they", "these", "those", "there", "here", "above", "below",
})

# Context window around AC references (chars on either side) for overlap
# scoring.
_CONTEXT_WINDOW = 400

# Alignment thresholds.
_ALIGNED_OVERLAP_THRESHOLD = 0.35  # >= this ratio of AC keywords seen in context
_DIVERGENT_MIN_OVERLAP = 0.10      # below this & referenced => divergent

_DEFAULT_IMPL_EXTENSIONS = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
    ".swift", ".rb", ".c", ".h", ".cpp", ".hpp", ".md", ".json", ".yaml",
    ".yml", ".sh",
)
_DEFAULT_TEST_DIR_NAMES = ("tests", "test", "__tests__", "spec", "specs")

# Complexity threshold at/above which semantic alignment is MANDATORY.
SEMANTIC_ALIGNMENT_COMPLEXITY_THRESHOLD = 3

# Gate-result verdicts
_VERDICT_APPROVE = "APPROVE"
_VERDICT_CONDITIONAL = "CONDITIONAL"
_VERDICT_REJECT = "REJECT"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SpecItem:
    """A single extracted acceptance criterion / functional requirement."""
    id: str
    description: str
    source_file: str
    priority: Optional[str] = None  # P0/P1/P2 when detected

    def keywords(self) -> List[str]:
        """Return deduped, lowercased, stopword-filtered keywords."""
        return _keywords(self.description)

    def constraints(self) -> List[str]:
        """Return concrete constraint literals from the description."""
        return _extract_constraint_literals(self.description)


@dataclass
class Finding:
    """One Gap Report finding for a single spec item."""
    id: str
    description: str
    source_file: str
    status: str  # aligned | divergent | missing
    confidence: float  # 0.0 - 1.0
    evidence: List[str]  # file paths / snippets supporting the verdict
    reason: str  # human-readable why
    expected_constraints: List[str] = field(default_factory=list)
    matched_constraints: List[str] = field(default_factory=list)
    unmatched_constraints: List[str] = field(default_factory=list)
    in_impl: bool = False
    in_tests: bool = False


@dataclass
class GapReport:
    """Full Gap Report payload."""
    project: str
    complexity: int
    total: int
    aligned: int
    divergent: int
    missing: int
    verdict: str  # APPROVE | CONDITIONAL | REJECT
    score: float  # aligned / total
    findings: List[Finding]
    summary: str
    # Emit schema_version so downstream consumers can evolve safely.
    schema_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    """Read file as UTF-8 text, replacing bad bytes. Returns "" on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def _keywords(text: str) -> List[str]:
    """Return deduped, lowercased, stopword-filtered tokens from text."""
    seen: set = set()
    out: List[str] = []
    for tok in _WORD_RE.findall(text):
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        if low not in seen:
            seen.add(low)
            out.append(low)
    return out


def _extract_constraint_literals(text: str) -> List[str]:
    """Extract concrete numeric + scope constraints from a description.

    Example: "3 failed attempts per session" -> ["3 attempts", "per session"].
    Returned literals are normalised-lowercase and deduped preserving order.
    """
    found: List[str] = []
    seen: set = set()

    for match in _NUMERIC_CONSTRAINT_RE.finditer(text):
        literal = f"{match.group(1)} {match.group(2).lower()}"
        if literal not in seen:
            seen.add(literal)
            found.append(literal)

    for match in _SCOPE_PHRASE_RE.finditer(text):
        literal = f"per {match.group(1).lower()}"
        if literal not in seen:
            seen.add(literal)
            found.append(literal)

    return found


def _iter_source_files(
    root: Path,
    extensions: Sequence[str] = _DEFAULT_IMPL_EXTENSIONS,
    exclude_paths: Optional[Sequence[Path]] = None,
) -> Iterable[Path]:
    """Yield source files under root with matching extensions.

    Skips common build / vcs / dep dirs so we don't index node_modules.
    Also skips any path inside the explicit ``exclude_paths`` set (used to
    prevent the spec files themselves from being scanned as implementation,
    which otherwise self-matches every AC).
    """
    if not root.is_dir():
        return
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
        "build", ".pytest_cache", ".mypy_cache", "target", ".next",
        "coverage", ".claude",
    }
    # The ``phases/`` tree of a crew project holds spec artefacts — never
    # scan those as implementation. Using a ``parts`` check so we catch
    # phases/ at any depth relative to ``root``.
    skip_top_segments = {"phases"}
    resolved_excludes = {Path(p).resolve() for p in (exclude_paths or [])}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts[:-1]
        if any(part in skip_dirs for part in rel_parts):
            continue
        if rel_parts and rel_parts[0] in skip_top_segments:
            continue
        if path.resolve() in resolved_excludes:
            continue
        if path.suffix.lower() in extensions:
            yield path


# ---------------------------------------------------------------------------
# Spec extraction
# ---------------------------------------------------------------------------

def extract_spec_items(
    ac_file: Optional[Path] = None,
    objective_file: Optional[Path] = None,
    extra_sources: Optional[Sequence[Path]] = None,
) -> List[SpecItem]:
    """Extract numbered spec items (AC / FR / REQ) from given files.

    Args:
        ac_file: Path to ``acceptance-criteria.md`` (preferred primary source).
        objective_file: Path to ``objective.md`` (secondary source; FR lines).
        extra_sources: Additional markdown files to scan (e.g. ADRs).

    Returns:
        Deduped list of SpecItem ordered by first appearance.
    """
    sources: List[Path] = []
    if ac_file and ac_file.exists():
        sources.append(ac_file)
    if objective_file and objective_file.exists():
        sources.append(objective_file)
    if extra_sources:
        for src in extra_sources:
            if src and src.exists():
                sources.append(src)

    items: List[SpecItem] = []
    seen_ids: set = set()

    for src in sources:
        text = _read_text(src)
        if not text:
            continue
        for item in _extract_from_text(text, str(src)):
            # Normalise id casing — AC-1 and ac-1 should dedupe.
            key = item.id.upper().replace(" ", "")
            if key in seen_ids:
                # Enrich: merge description if we had a shorter one before.
                continue
            seen_ids.add(key)
            items.append(SpecItem(
                id=item.id.upper().replace(" ", ""),
                description=item.description,
                source_file=item.source_file,
                priority=item.priority,
            ))

    return items


def _extract_from_text(text: str, source_file: str) -> List[SpecItem]:
    """Pull AC/FR items out of a single markdown body."""
    out: List[SpecItem] = []
    seen: set = set()

    # Strategy 1 — table rows
    for match in _AC_TABLE_ROW_RE.finditer(text):
        ac_id = match.group("id").strip()
        desc = match.group("desc").strip()
        if "criterion" in desc.lower() or "description" in desc.lower():
            continue  # header row
        if ac_id and ac_id not in seen:
            seen.add(ac_id)
            out.append(SpecItem(
                id=ac_id,
                description=desc,
                source_file=source_file,
                priority=_detect_priority(desc),
            ))

    # Strategy 2 — bulleted list "- AC-1: Given ..., When ..., Then ..."
    for match in _AC_LIST_RE.finditer(text):
        ac_id = match.group("id").strip()
        desc = match.group("desc").strip()
        if ac_id and ac_id not in seen:
            seen.add(ac_id)
            out.append(SpecItem(
                id=ac_id,
                description=desc,
                source_file=source_file,
                priority=_detect_priority(desc),
            ))

    # Strategy 3 — inline "AC1: Given ... When ... Then ..."
    for match in _AC_INLINE_RE.finditer(text):
        ac_id = match.group("id").strip()
        desc = match.group("desc").strip()
        if ac_id and ac_id not in seen:
            seen.add(ac_id)
            out.append(SpecItem(
                id=ac_id,
                description=desc,
                source_file=source_file,
                priority=_detect_priority(desc),
            ))

    # Strategy 4 — bare id mentions as last resort, pair with surrounding line
    if not out:
        for match in _SPEC_ID_RE.finditer(text):
            ac_id = match.group(0)
            if ac_id in seen:
                continue
            # Capture up to 240 chars of context after the id as description.
            start = match.end()
            tail = text[start:start + 240].strip()
            if not tail:
                continue
            # Cut at next newline-newline (end of paragraph) if present.
            end_idx = tail.find("\n\n")
            if end_idx >= 0:
                tail = tail[:end_idx].strip()
            seen.add(ac_id)
            out.append(SpecItem(
                id=ac_id,
                description=tail[:240],
                source_file=source_file,
                priority=_detect_priority(tail),
            ))

    return out


_PRIORITY_RE = re.compile(r"\bP([012])\b")


def _detect_priority(text: str) -> Optional[str]:
    match = _PRIORITY_RE.search(text)
    return f"P{match.group(1)}" if match else None


# ---------------------------------------------------------------------------
# Alignment scoring
# ---------------------------------------------------------------------------

def _find_references(corpus: Dict[str, str], spec_id: str) -> List[Tuple[str, str]]:
    """Return list of (file_path, context_snippet) for occurrences of spec_id.

    Uses case-insensitive literal search. Returns up to 20 hits per id to
    keep reports bounded.
    """
    needle = spec_id.upper()
    needle_lower = spec_id.lower()
    results: List[Tuple[str, str]] = []
    for file_path, text in corpus.items():
        if not text:
            continue
        # Quick reject — case-insensitive substring check.
        lower = text.lower()
        if needle_lower not in lower:
            continue
        # Collect each occurrence's context window.
        idx = 0
        while True:
            pos = lower.find(needle_lower, idx)
            if pos < 0:
                break
            start = max(0, pos - _CONTEXT_WINDOW)
            end = min(len(text), pos + len(needle) + _CONTEXT_WINDOW)
            snippet = text[start:end]
            results.append((file_path, snippet))
            idx = pos + len(needle)
            if len(results) >= 20:
                return results
    return results


def _keyword_overlap(spec_keywords: Sequence[str], context: str) -> float:
    """Ratio of spec keywords that appear in context text. Range 0.0-1.0."""
    if not spec_keywords:
        return 1.0
    context_lower = context.lower()
    hits = sum(1 for kw in spec_keywords if kw in context_lower)
    return hits / len(spec_keywords)


def _best_overlap(
    spec_keywords: Sequence[str],
    refs: Sequence[Tuple[str, str]],
) -> float:
    """Return highest keyword-overlap ratio across all references."""
    if not refs:
        return 0.0
    return max(_keyword_overlap(spec_keywords, snippet) for _, snippet in refs)


def _constraints_matched(
    constraints: Sequence[str],
    context: str,
) -> Tuple[List[str], List[str]]:
    """Return (matched, unmatched) constraint literals against context."""
    matched: List[str] = []
    unmatched: List[str] = []
    lower = context.lower()
    for literal in constraints:
        if literal.lower() in lower:
            matched.append(literal)
        else:
            unmatched.append(literal)
    return matched, unmatched


def _aggregate_constraints(
    constraints: Sequence[str],
    refs: Sequence[Tuple[str, str]],
) -> Tuple[List[str], List[str]]:
    """Aggregate constraint matching across ALL reference contexts.

    A constraint is counted as matched if it appears in ANY reference snippet.
    """
    if not constraints:
        return [], []
    combined = "\n".join(snippet for _, snippet in refs)
    return _constraints_matched(constraints, combined)


def _classify(
    item: SpecItem,
    impl_refs: Sequence[Tuple[str, str]],
    test_refs: Sequence[Tuple[str, str]],
) -> Finding:
    """Produce a Finding for a single spec item given impl + test references."""
    in_impl = bool(impl_refs)
    in_tests = bool(test_refs)

    spec_keywords = item.keywords()
    all_refs = list(impl_refs) + list(test_refs)

    overlap = _best_overlap(spec_keywords, all_refs)
    matched_c, unmatched_c = _aggregate_constraints(item.constraints(), all_refs)

    evidence = [fp for fp, _ in all_refs[:8]]

    # MISSING — literal id absent from both corpora.
    if not in_impl and not in_tests:
        return Finding(
            id=item.id,
            description=item.description,
            source_file=item.source_file,
            status="missing",
            confidence=0.9,
            evidence=[],
            reason=(
                f"Spec item {item.id} has no occurrence in implementation "
                f"corpus or test corpus. Expected at least a comment or "
                f"test-name reference."
            ),
            expected_constraints=item.constraints(),
            matched_constraints=[],
            unmatched_constraints=list(item.constraints()),
            in_impl=False,
            in_tests=False,
        )

    # DIVERGENT path 1 — referenced in one corpus only.
    partial = (in_impl and not in_tests) or (in_tests and not in_impl)

    # DIVERGENT path 2 — has numeric/scope constraints that aren't matched.
    has_unmatched_constraints = bool(unmatched_c) and bool(item.constraints())

    # DIVERGENT path 3 — keyword overlap below threshold
    low_overlap = overlap < _ALIGNED_OVERLAP_THRESHOLD

    if partial or has_unmatched_constraints or low_overlap:
        # Build specific reason.
        reasons: List[str] = []
        if partial:
            if in_impl and not in_tests:
                reasons.append(
                    f"{item.id} referenced in implementation but no matching "
                    f"test asserts it"
                )
            else:
                reasons.append(
                    f"{item.id} referenced in tests but not in implementation"
                )
        if has_unmatched_constraints:
            reasons.append(
                f"constraint(s) {unmatched_c} from spec not found near "
                f"{item.id} references"
            )
        if low_overlap and not (partial or has_unmatched_constraints):
            reasons.append(
                f"implementation context near {item.id} overlaps only "
                f"{overlap:.0%} with spec keywords — likely divergent intent"
            )
        # Confidence: high when we have concrete constraint gaps, medium
        # when only overlap is low.
        confidence = 0.85 if has_unmatched_constraints else (
            0.7 if partial else 0.6
        )
        return Finding(
            id=item.id,
            description=item.description,
            source_file=item.source_file,
            status="divergent",
            confidence=confidence,
            evidence=evidence,
            reason="; ".join(reasons),
            expected_constraints=item.constraints(),
            matched_constraints=matched_c,
            unmatched_constraints=unmatched_c,
            in_impl=in_impl,
            in_tests=in_tests,
        )

    # ALIGNED — in both corpora, overlap >= threshold, all constraints matched.
    return Finding(
        id=item.id,
        description=item.description,
        source_file=item.source_file,
        status="aligned",
        confidence=min(0.95, 0.5 + overlap * 0.5),
        evidence=evidence,
        reason=(
            f"{item.id} referenced in implementation ({sum(1 for _ in impl_refs)} "
            f"hit(s)) and tests ({sum(1 for _ in test_refs)} hit(s)); "
            f"keyword overlap {overlap:.0%} >= "
            f"{_ALIGNED_OVERLAP_THRESHOLD:.0%}"
        ),
        expected_constraints=item.constraints(),
        matched_constraints=matched_c,
        unmatched_constraints=[],
        in_impl=True,
        in_tests=True,
    )


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _build_corpus(
    directory: Path,
    extensions: Sequence[str] = _DEFAULT_IMPL_EXTENSIONS,
    file_limit: int = 5000,
    exclude_paths: Optional[Sequence[Path]] = None,
) -> Dict[str, str]:
    """Build a {path: text} corpus for a directory, bounded by file_limit.

    ``exclude_paths`` lets callers keep the spec files (``acceptance-criteria.md``,
    ``objective.md``) out of the implementation scan — otherwise every AC
    self-matches and every project looks 100% aligned.
    """
    corpus: Dict[str, str] = {}
    if not directory.is_dir():
        return corpus
    count = 0
    for path in _iter_source_files(directory, extensions, exclude_paths=exclude_paths):
        text = _read_text(path)
        if not text:
            continue
        corpus[str(path)] = text
        count += 1
        if count >= file_limit:
            break
    return corpus


def _build_corpus_from_files(files: Sequence[Path]) -> Dict[str, str]:
    """Build a {path: text} corpus from an explicit file list."""
    corpus: Dict[str, str] = {}
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        text = _read_text(path)
        if text:
            corpus[str(path)] = text
    return corpus


def _split_impl_and_tests(corpus: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Partition an arbitrary corpus into (impl_corpus, test_corpus).

    A file is considered a test file when any ancestor directory matches
    a known test-dir name (``tests``, ``test``, ``spec``, etc.) or when
    the filename starts with ``test_`` or ends with ``_test.py`` /
    ``.test.ts`` / ``.spec.ts``.
    """
    impl: Dict[str, str] = {}
    tests: Dict[str, str] = {}

    for path_str, text in corpus.items():
        p = Path(path_str)
        is_test = False
        for part in p.parts:
            if part.lower() in _DEFAULT_TEST_DIR_NAMES:
                is_test = True
                break
        if not is_test:
            name = p.name.lower()
            if (name.startswith("test_") or name.endswith("_test.py") or
                    name.endswith(".test.ts") or name.endswith(".test.tsx") or
                    name.endswith(".test.js") or name.endswith(".spec.ts") or
                    name.endswith(".spec.js")):
                is_test = True
        if is_test:
            tests[path_str] = text
        else:
            impl[path_str] = text

    return impl, tests


def generate_gap_report(
    spec_items: Sequence[SpecItem],
    impl_corpus: Dict[str, str],
    test_corpus: Dict[str, str],
    project: str = "unknown",
    complexity: int = 0,
) -> GapReport:
    """Produce a complete Gap Report from spec items + impl/test corpora.

    Args:
        spec_items: Extracted AC/FR items from clarify-phase specs.
        impl_corpus: {file_path: text} for non-test source files.
        test_corpus: {file_path: text} for test files.
        project: Project identifier (for the report header).
        complexity: Project complexity score (0-7).

    Returns:
        GapReport dataclass — ``asdict`` it for JSON output.
    """
    findings: List[Finding] = []

    for item in spec_items:
        impl_refs = _find_references(impl_corpus, item.id)
        test_refs = _find_references(test_corpus, item.id)
        findings.append(_classify(item, impl_refs, test_refs))

    total = len(findings)
    aligned = sum(1 for f in findings if f.status == "aligned")
    divergent = sum(1 for f in findings if f.status == "divergent")
    missing = sum(1 for f in findings if f.status == "missing")

    # Score = aligned ratio (1.0 when no specs — vacuously aligned).
    score = (aligned / total) if total > 0 else 1.0

    # Verdict: APPROVE only when all aligned; REJECT when anything missing;
    # CONDITIONAL when only divergent findings.
    if total == 0:
        verdict = _VERDICT_APPROVE
        summary = "No numbered spec items found — advisory skip."
    elif missing > 0:
        verdict = _VERDICT_REJECT
        summary = (
            f"{missing} spec item(s) missing from implementation. "
            f"Hard reject — implement referenced AC before approval."
        )
    elif divergent > 0:
        verdict = _VERDICT_CONDITIONAL
        summary = (
            f"{divergent} spec item(s) diverge from stated intent. "
            f"Fix divergences or explicitly document the deviation."
        )
    else:
        verdict = _VERDICT_APPROVE
        summary = f"All {aligned} spec items aligned with implementation."

    return GapReport(
        project=project,
        complexity=complexity,
        total=total,
        aligned=aligned,
        divergent=divergent,
        missing=missing,
        verdict=verdict,
        score=round(score, 3),
        findings=findings,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# ADR constraint extraction  (conservative MVP)
# ---------------------------------------------------------------------------

def extract_adr_constraints(adr_dir: Path) -> List[Dict[str, str]]:
    """Extract MUST/SHALL directives from ADR markdown files.

    Conservative regex-only approach: pulls every line containing a modal
    directive (MUST / MUST NOT / SHALL / SHALL NOT / SHOULD NOT) and returns
    ``{source, directive, statement}``. A follow-up iteration could run these
    statements against the implementation corpus and flag violations.

    Returns:
        List of dicts; empty if dir missing or no directives.

    Limitations:
        - Line-granular only (no multi-line parsing).
        - No negation / scope reasoning — downstream code must still decide
          whether a match is a violation or a legitimate exception.
        - Treats every modal-directive hit as equally important.
    """
    out: List[Dict[str, str]] = []
    if not adr_dir.is_dir():
        return out

    for md in sorted(adr_dir.rglob("*.md")):
        text = _read_text(md)
        if not text:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = _MODAL_DIRECTIVE_RE.search(line)
            if not match:
                continue
            # Skip section headers and front-matter noise.
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("---"):
                continue
            out.append({
                "source": str(md),
                "line": str(line_no),
                "directive": match.group(1),
                "statement": stripped[:240],
            })

    return out


# ---------------------------------------------------------------------------
# Orchestration — project-dir convention
# ---------------------------------------------------------------------------

def review_project(
    project_dir: Path,
    project_name: str = "",
    complexity: int = 0,
    ac_file: Optional[Path] = None,
    objective_file: Optional[Path] = None,
    impl_dir: Optional[Path] = None,
    test_dir: Optional[Path] = None,
) -> GapReport:
    """Run a full semantic review over a project directory.

    Expected layout (overrideable via args)::

        <project_dir>/
            phases/
                clarify/
                    acceptance-criteria.md   <-- ac_file default
                    objective.md             <-- objective_file default
            <impl sources>                   <-- impl_dir default = project_dir
            tests/                           <-- test_dir default

    Args:
        project_dir: Root dir containing phases/ and source.
        project_name: Name for the report header.
        complexity: Project complexity 0-7.
        ac_file: Override path to acceptance-criteria.md.
        objective_file: Override path to objective.md.
        impl_dir: Override implementation-scan root. Defaults to project_dir.
        test_dir: Override test-scan root. When None, impl_dir is scanned and
            files are partitioned by filename + dir heuristic.

    Returns:
        GapReport.
    """
    ac_path = ac_file or (project_dir / "phases" / "clarify" / "acceptance-criteria.md")
    obj_path = objective_file or (project_dir / "phases" / "clarify" / "objective.md")

    spec_items = extract_spec_items(ac_file=ac_path, objective_file=obj_path)

    impl_root = impl_dir or project_dir

    # Never scan the spec files themselves — otherwise every AC
    # self-matches and overlap is trivially 100%.
    spec_excludes: List[Path] = []
    if ac_path and ac_path.exists():
        spec_excludes.append(ac_path)
    if obj_path and obj_path.exists():
        spec_excludes.append(obj_path)

    if test_dir:
        impl_corpus = _build_corpus(impl_root, exclude_paths=spec_excludes)
        test_corpus = _build_corpus(test_dir, exclude_paths=spec_excludes)
        # Avoid double-counting: strip test files from impl_corpus.
        test_paths = set(test_corpus.keys())
        impl_corpus = {p: t for p, t in impl_corpus.items() if p not in test_paths}
    else:
        full_corpus = _build_corpus(impl_root, exclude_paths=spec_excludes)
        impl_corpus, test_corpus = _split_impl_and_tests(full_corpus)

    project = project_name or project_dir.name

    return generate_gap_report(
        spec_items=spec_items,
        impl_corpus=impl_corpus,
        test_corpus=test_corpus,
        project=project,
        complexity=complexity,
    )


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------

def report_to_dict(report: GapReport) -> Dict[str, Any]:
    """Convert a GapReport (incl. nested Findings) to a JSON-safe dict."""
    return asdict(report)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semantic_review.py",
        description="Semantic reviewer — spec-to-code alignment (issue #444).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_review = sub.add_parser("review", help="Run full semantic review")
    p_review.add_argument("--project-dir", required=True)
    p_review.add_argument("--project-name", default="")
    p_review.add_argument("--complexity", type=int, default=0)
    p_review.add_argument("--ac-file", default=None)
    p_review.add_argument("--objective-file", default=None)
    p_review.add_argument("--impl-dir", default=None)
    p_review.add_argument("--test-dir", default=None)
    p_review.add_argument("--output", default=None, help="Write JSON report to this path")

    p_constraints = sub.add_parser("constraints", help="Extract ADR constraints (MVP)")
    p_constraints.add_argument("--adr-dir", required=True)
    p_constraints.add_argument("--output", default=None)

    return parser


def _cli_review(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        print(f"error: project-dir not found: {project_dir}", file=sys.stderr)
        return 2

    report = review_project(
        project_dir=project_dir,
        project_name=args.project_name,
        complexity=args.complexity,
        ac_file=Path(args.ac_file).resolve() if args.ac_file else None,
        objective_file=Path(args.objective_file).resolve() if args.objective_file else None,
        impl_dir=Path(args.impl_dir).resolve() if args.impl_dir else None,
        test_dir=Path(args.test_dir).resolve() if args.test_dir else None,
    )
    payload = report_to_dict(report)
    data = json.dumps(payload, indent=2)
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(data)
    else:
        sys.stdout.write(data + "\n")
    # Non-zero exit only when verdict is REJECT — CONDITIONAL is advisory.
    if report.verdict == _VERDICT_REJECT:
        return 1
    return 0


def _cli_constraints(args: argparse.Namespace) -> int:
    adr_dir = Path(args.adr_dir).resolve()
    constraints = extract_adr_constraints(adr_dir)
    data = json.dumps({"constraints": constraints, "count": len(constraints)}, indent=2)
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(data)
    else:
        sys.stdout.write(data + "\n")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "review":
        return _cli_review(args)
    if args.command == "constraints":
        return _cli_constraints(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
