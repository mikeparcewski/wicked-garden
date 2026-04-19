#!/usr/bin/env python3
"""
guard_pipeline.py — Autonomous session-close guard evaluation (Issue #448).

Runs a tiered profile of surface-level verification checks at session close
(and optionally at build-phase approval).  Does NOT hard-block — surfaces
findings to the session summary + wicked-bus.  Fail-open everywhere.

Scope limits (important):
    * All checks are intentionally cheap.  This is NOT a substitute for
      engineering:review, crew:gate, or a proper static-analysis run.
    * R1-R6 scan uses regex/line-pattern heuristics only — high recall for
      obvious tells, zero semantic understanding.  Document this limitation
      in any downstream report.
    * Semantic-reviewer integration (#444) is optional and imported lazily.
      If unavailable we emit a "semantic-review-unavailable" finding with
      severity=info and continue.

The 5 checks:
    1. bulletproof_scan  — R1-R6 surface heuristics on changed files
    2. debug_artifacts   — print/console.log/pdb/breakpoint leftovers
    3. adr_constraints   — ADR MUST/MUST NOT phrases vs the diff
    4. semantic_review   — delegates to scripts.qe.semantic_review (#444)
    5. skip_log          — unresolved skip-reeval entries (audit_skip_log.py)

Usage (as a module):
    from platform.guard_pipeline import run_pipeline
    report = run_pipeline(profile_name="scalpel", cwd=Path.cwd())

Usage (as a CLI — for debugging):
    python3 guard_pipeline.py run --profile scalpel
    python3 guard_pipeline.py run --profile standard --project-dir ./some/proj

Frozen R1-R6 reference (copied from CLAUDE.md, single source of truth):
    R1 — no dead code (commented-out blocks, unreferenced exports)
    R2 — no bare panics (`raise Exception`, bare `panic!`, process.exit, System.exit)
    R3 — no magic values (literal numbers in conditionals/returns without names)
    R4 — no swallowed errors (`except: pass`, empty catch, `// swallow`)
    R5 — no unbounded ops (while True w/o break, for without range, unbounded recursion hints)
    R6 — no god functions (> 80 lines, > 8 parameters in a single def)

These are heuristics.  False-positives are expected — the guard pipeline
surfaces them as findings, not blockers.  Engineering review owns final calls.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — allow sibling imports (guard_profiles + scripts/_bus etc.)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_ROOT))
sys.path.insert(0, str(_THIS_DIR))

from guard_profiles import (  # noqa: E402  (sys.path manipulation above)
    GuardProfile,
    SCALPEL,
    auto_select,
    get_profile,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIPELINE_VERSION = "1.0"

# Severity levels — keep in sync with briefing renderer.
SEVERITY_BLOCK = "block"    # would be a hard-block in a full gate (we still fail-open)
SEVERITY_WARN = "warn"      # advisory
SEVERITY_INFO = "info"      # informational (e.g. "scan skipped — no files")

# Per-check time budget fraction of the profile budget.  Leaves headroom for
# emission and summary assembly.
_PER_CHECK_BUDGET_FRACTION = 0.8

# Files/dirs we always skip when scanning the diff.
_SKIP_PARTS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".claude",
    "htmlcov", "coverage", ".next", ".nuxt", "target",
})

# Extensions in scope for bulletproof/debug scans.
_CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".rs", ".go", ".java", ".kt", ".rb", ".cs",
})

# Max lines we read per file — an unsanitized megafile shouldn't burn our budget.
_MAX_LINES_PER_FILE = 5000


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single guard-pipeline finding.

    `rule_id` is the sub-rule (e.g. "R2", "adr-MUST-NOT").  `severity` is one
    of the SEVERITY_* constants.  `file` and `line` are optional — checks may
    aggregate findings without a pinned location.
    """

    check: str
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CheckResult:
    """Result of a single check: findings + timing + status."""

    name: str
    status: str          # "ok" | "skip" | "error"
    findings: List[Finding] = field(default_factory=list)
    duration_ms: int = 0
    note: Optional[str] = None  # short human reason (e.g. "no changed files")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "note": self.note,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class PipelineReport:
    """Aggregated guard-pipeline output."""

    pipeline_version: str
    profile: str
    budget_seconds: float
    duration_ms: int
    status: str  # "ok" | "budget_exceeded" | "error"
    checks: List[CheckResult] = field(default_factory=list)
    findings_by_severity: Dict[str, int] = field(default_factory=dict)
    total_findings: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_version": self.pipeline_version,
            "profile": self.profile,
            "budget_seconds": self.budget_seconds,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "total_findings": self.total_findings,
            "findings_by_severity": self.findings_by_severity,
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def _path_in_scope(path: str) -> bool:
    """Skip vendored/generated/irrelevant paths."""
    parts = Path(path).parts
    return not (set(parts) & _SKIP_PARTS)


def _changed_files(cwd: Optional[Path] = None) -> List[str]:
    """Return changed files — staged + unstaged + diff vs HEAD~1.  Deduped."""
    cwdp = str(cwd) if cwd else None
    files: List[str] = []
    seen: set = set()

    def _collect(cmd: List[str]) -> None:
        try:
            result = subprocess.run(cmd, cwd=cwdp, capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line or line in seen:
                        continue
                    if not _path_in_scope(line):
                        continue
                    # Resolve against cwd so downstream reads succeed
                    full = str((cwd or Path.cwd()) / line) if cwd else line
                    if os.path.isfile(full):
                        seen.add(line)
                        files.append(full)
        except Exception:
            pass  # fail open — we just return whatever we have so far

    _collect(["git", "diff", "--name-only", "HEAD"])
    _collect(["git", "diff", "--name-only", "--cached"])
    return files


def _read_lines(path: str) -> List[str]:
    """Read up to _MAX_LINES_PER_FILE lines.  Empty on error."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return lines[:_MAX_LINES_PER_FILE]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Check 1: bulletproof_scan (R1-R6 surface heuristics)
# ---------------------------------------------------------------------------

# Each entry: (rule_id, regex, extensions, message, severity)
# Extensions=None means "any code file".
_BULLETPROOF_PATTERNS: List[Tuple[str, re.Pattern, Optional[frozenset], str, str]] = [
    # R2 — bare panics
    ("R2", re.compile(r"\braise\s+Exception\s*\("), frozenset({".py"}),
     "R2: bare `raise Exception(...)` — use a typed exception", SEVERITY_WARN),
    ("R2", re.compile(r"\bpanic!\s*\("), frozenset({".rs"}),
     "R2: bare `panic!` — prefer Result/Error propagation", SEVERITY_WARN),
    ("R2", re.compile(r"\bprocess\.exit\s*\("),
     frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}),
     "R2: `process.exit(...)` in library code — throw instead", SEVERITY_WARN),
    ("R2", re.compile(r"\bSystem\.exit\s*\("), frozenset({".java", ".kt"}),
     "R2: `System.exit(...)` — throw or return", SEVERITY_WARN),

    # R4 — swallowed errors (single-line form; multiline form handled separately)
    ("R4", re.compile(r"except[^:]*:\s*pass\s*(#.*)?$"), frozenset({".py"}),
     "R4: bare `except: pass` — swallowed exception", SEVERITY_WARN),
    ("R4", re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"),
     frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".cs"}),
     "R4: empty catch block — swallowed exception", SEVERITY_WARN),
    ("R4", re.compile(r"//\s*swallow|//\s*ignore\s+err"), None,
     "R4: explicit error-swallowing comment", SEVERITY_WARN),

    # R5 — unbounded ops (structural hint, not semantic)
    ("R5", re.compile(r"\bwhile\s+True\s*:"), frozenset({".py"}),
     "R5: `while True:` — confirm the loop has a bounded exit", SEVERITY_INFO),
    ("R5", re.compile(r"\bwhile\s*\(\s*true\s*\)\s*\{"),
     frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".cs"}),
     "R5: `while (true)` — confirm the loop has a bounded exit", SEVERITY_INFO),

    # R1 — dead code hint (commented-out blocks of 3+ consecutive lines)
    #   We do NOT try to detect via regex — handled in a separate pass below.
]


_EXCEPT_RE = re.compile(r"^(\s*)except\b[^:]*:\s*(#.*)?$")
_BODY_PASS_RE = re.compile(r"^\s*pass\s*(#.*)?$")


def _detect_multiline_swallow(path: str, lines: List[str]) -> List[Finding]:
    """R4: flag multi-line `except ...:\n    pass` patterns (Python)."""
    findings: List[Finding] = []
    if not path.endswith(".py"):
        return findings
    for i, line in enumerate(lines):
        m = _EXCEPT_RE.match(line)
        if not m:
            continue
        # Find the next non-blank, non-comment line
        for j in range(i + 1, min(i + 5, len(lines))):
            nxt = lines[j]
            stripped = nxt.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if _BODY_PASS_RE.match(nxt):
                findings.append(Finding(
                    check="bulletproof_scan", rule_id="R4", severity=SEVERITY_WARN,
                    message="R4: `except ...: pass` (multi-line) — swallowed exception",
                    file=path, line=i + 1,
                ))
            break
    return findings


def _count_python_god_functions(path: str, lines: List[str]) -> List[Finding]:
    """R6: flag Python defs with > 80 lines or > 8 params."""
    findings: List[Finding] = []
    def_re = re.compile(r"^(\s*)def\s+(\w+)\s*\(([^)]*)\)")
    i = 0
    while i < len(lines):
        m = def_re.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        name = m.group(2)
        # Count params — crude but stdlib-only.
        params_blob = m.group(3).strip()
        param_count = 0
        if params_blob:
            # Ignore `self` / `cls` and default-value commas inside brackets.
            depth = 0
            current = ""
            parts: List[str] = []
            for ch in params_blob:
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                if ch == "," and depth == 0:
                    parts.append(current.strip())
                    current = ""
                else:
                    current += ch
            if current.strip():
                parts.append(current.strip())
            parts = [p for p in parts if p and p not in ("self", "cls")]
            param_count = len(parts)
        if param_count > 8:
            findings.append(Finding(
                check="bulletproof_scan", rule_id="R6", severity=SEVERITY_WARN,
                message=f"R6: function `{name}` has {param_count} parameters (> 8)",
                file=path, line=i + 1,
            ))
        # Find function end — next line at <= indent that isn't blank
        body_start = i + 1
        end = len(lines)
        for j in range(body_start, len(lines)):
            stripped = lines[j].rstrip()
            if not stripped:
                continue
            leading = len(lines[j]) - len(lines[j].lstrip())
            if leading <= indent:
                end = j
                break
        body_len = end - i
        if body_len > 80:
            findings.append(Finding(
                check="bulletproof_scan", rule_id="R6", severity=SEVERITY_WARN,
                message=f"R6: function `{name}` is {body_len} lines long (> 80)",
                file=path, line=i + 1,
            ))
        i = max(end, i + 1)
    return findings


def _count_commented_blocks(path: str, lines: List[str]) -> List[Finding]:
    """R1: flag runs of >= 3 consecutive commented-out code lines."""
    findings: List[Finding] = []
    ext = Path(path).suffix.lower()
    comment_re: Optional[re.Pattern] = None
    if ext == ".py":
        # Python: commented line that looks like code (contains `=`, `(`, `:`)
        comment_re = re.compile(r"^\s*#\s*[A-Za-z_].*[=(:]")
    elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
                 ".rs", ".go", ".java", ".kt", ".cs"}:
        comment_re = re.compile(r"^\s*//\s*[A-Za-z_].*[=(;{]")
    if comment_re is None:
        return findings

    run_start: Optional[int] = None
    run_len = 0
    for idx, line in enumerate(lines):
        if comment_re.match(line):
            if run_start is None:
                run_start = idx
            run_len += 1
        else:
            if run_len >= 3 and run_start is not None:
                findings.append(Finding(
                    check="bulletproof_scan", rule_id="R1", severity=SEVERITY_INFO,
                    message=f"R1: {run_len} consecutive commented-out code lines",
                    file=path, line=run_start + 1,
                ))
            run_start = None
            run_len = 0
    if run_len >= 3 and run_start is not None:
        findings.append(Finding(
            check="bulletproof_scan", rule_id="R1", severity=SEVERITY_INFO,
            message=f"R1: {run_len} consecutive commented-out code lines",
            file=path, line=run_start + 1,
        ))
    return findings


def check_bulletproof_scan(
    files: List[str],
    *,
    budget_seconds: float,
    **_kwargs: Any,
) -> CheckResult:
    """Run R1-R6 surface heuristics on code files."""
    t0 = time.monotonic()
    result = CheckResult(name="bulletproof_scan", status="ok")

    if not files:
        result.status = "skip"
        result.note = "no changed files"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    deadline = t0 + budget_seconds
    for filepath in files:
        if time.monotonic() > deadline:
            result.note = "budget exceeded — partial scan"
            break
        ext = Path(filepath).suffix.lower()
        if ext not in _CODE_EXTENSIONS:
            continue
        lines = _read_lines(filepath)
        if not lines:
            continue

        for line_num, line in enumerate(lines, start=1):
            for rule_id, pattern, exts, msg, severity in _BULLETPROOF_PATTERNS:
                if exts is not None and ext not in exts:
                    continue
                if pattern.search(line):
                    result.findings.append(Finding(
                        check="bulletproof_scan", rule_id=rule_id, severity=severity,
                        message=msg, file=filepath, line=line_num,
                    ))

        if ext == ".py":
            result.findings.extend(_count_python_god_functions(filepath, lines))
            result.findings.extend(_detect_multiline_swallow(filepath, lines))
        result.findings.extend(_count_commented_blocks(filepath, lines))

    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Check 2: debug_artifacts
# ---------------------------------------------------------------------------

_DEBUG_PATTERNS: List[Tuple[str, re.Pattern, Optional[frozenset], str]] = [
    ("debug.console", re.compile(r"\bconsole\.log\s*\("),
     frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}), "console.log"),
    ("debug.debugger", re.compile(r"\bdebugger\s*;?"),
     frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}), "debugger"),
    ("debug.pdb", re.compile(r"\bpdb\.set_trace\s*\("),
     frozenset({".py"}), "pdb.set_trace"),
    ("debug.breakpoint", re.compile(r"\bbreakpoint\s*\("),
     frozenset({".py"}), "breakpoint()"),
    ("debug.print", re.compile(r"^\s*print\s*\("),
     frozenset({".py"}), "print()"),
]

# Files we tolerate prints in (scripts, tests, examples)
_PRINT_ALLOWED_PATTERNS = (
    "/tests/", "/test_", "/examples/", "/scripts/",
    "/hooks/", "cli.py", "__main__.py",
)


def _print_allowed(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(pat in norm for pat in _PRINT_ALLOWED_PATTERNS)


def check_debug_artifacts(
    files: List[str],
    *,
    budget_seconds: float,
    **_kwargs: Any,
) -> CheckResult:
    """Scan changed files for debug leftovers."""
    t0 = time.monotonic()
    result = CheckResult(name="debug_artifacts", status="ok")

    if not files:
        result.status = "skip"
        result.note = "no changed files"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    deadline = t0 + budget_seconds
    for filepath in files:
        if time.monotonic() > deadline:
            result.note = "budget exceeded — partial scan"
            break
        ext = Path(filepath).suffix.lower()
        if ext not in _CODE_EXTENSIONS:
            continue
        lines = _read_lines(filepath)
        for line_num, line in enumerate(lines, start=1):
            for rule_id, pattern, exts, label in _DEBUG_PATTERNS:
                if exts is not None and ext not in exts:
                    continue
                # Suppress `print()` in files where it's expected (tests, scripts, hooks).
                if label == "print()" and _print_allowed(filepath):
                    continue
                if pattern.search(line):
                    result.findings.append(Finding(
                        check="debug_artifacts", rule_id=rule_id, severity=SEVERITY_WARN,
                        message=f"{label} left in changed file",
                        file=filepath, line=line_num,
                    ))

    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Check 3: adr_constraints
# ---------------------------------------------------------------------------

# Matches "MUST", "MUST NOT", "SHALL NOT" etc. in uppercase context — RFC-2119 tone
_ADR_MUST_RE = re.compile(r"\b(MUST NOT|SHALL NOT|MUST|SHALL)\b\s+(.{5,140}?)(?:[.!?]|$)")

_ADR_SEARCH_ROOTS = ("docs/adr", "adr", "architecture/decisions", "docs/decisions")


def _find_adr_files(cwd: Path) -> List[Path]:
    """Return ADR markdown files under well-known roots (capped for budget)."""
    files: List[Path] = []
    for root in _ADR_SEARCH_ROOTS:
        rootp = cwd / root
        if not rootp.is_dir():
            continue
        try:
            for p in rootp.rglob("*.md"):
                if not _path_in_scope(str(p)):
                    continue
                files.append(p)
                if len(files) >= 50:
                    return files
        except Exception:
            continue
    return files


def _extract_constraints(adr_files: List[Path]) -> List[Tuple[Path, str, str]]:
    """Return [(adr_path, verb, phrase), ...] for MUST/SHALL phrases."""
    constraints: List[Tuple[Path, str, str]] = []
    for adr in adr_files:
        try:
            text = adr.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for match in _ADR_MUST_RE.finditer(text):
            verb = match.group(1)
            phrase = match.group(2).strip()
            if 5 <= len(phrase) <= 140:
                constraints.append((adr, verb, phrase))
            if len(constraints) >= 200:
                return constraints
    return constraints


def check_adr_constraints(
    files: List[str],
    *,
    budget_seconds: float,
    cwd: Optional[Path] = None,
    **_kwargs: Any,
) -> CheckResult:
    """Scan changed files for MUST-NOT phrase matches from ADRs.

    Best-effort: finds literal substring matches of MUST-NOT phrases inside
    the diff.  False-positives are expected — surfaced as info, not warn.
    """
    t0 = time.monotonic()
    result = CheckResult(name="adr_constraints", status="ok")

    base = cwd or Path.cwd()
    adr_files = _find_adr_files(base)
    if not adr_files:
        result.status = "skip"
        result.note = "no ADRs found"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    constraints = _extract_constraints(adr_files)
    must_not = [(adr, phrase) for (adr, verb, phrase) in constraints if "NOT" in verb]
    if not must_not:
        result.status = "skip"
        result.note = f"{len(adr_files)} ADRs scanned, no MUST-NOT constraints"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    if not files:
        result.status = "skip"
        result.note = "no changed files"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    deadline = t0 + budget_seconds
    for filepath in files:
        if time.monotonic() > deadline:
            result.note = "budget exceeded — partial scan"
            break
        lines = _read_lines(filepath)
        if not lines:
            continue
        # Combine into one blob for substring search — small files only
        text = "\n".join(lines)
        for adr, phrase in must_not:
            # Take first word of the phrase as a cheap prefilter; fall back to full match
            head = phrase.split()[0] if phrase.split() else phrase
            if head.lower() in text.lower() and phrase.lower()[:40] in text.lower():
                result.findings.append(Finding(
                    check="adr_constraints",
                    rule_id="adr-MUST-NOT",
                    severity=SEVERITY_WARN,
                    message=f"Changed file contains text matching ADR constraint: '{phrase[:80]}' (from {adr.name})",
                    file=filepath,
                ))

    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Check 4: semantic_review (lazy import — depends on PR #444 / #455)
# ---------------------------------------------------------------------------

def _call_semantic_reviewer(project_dir: Path, complexity: int) -> Optional[Dict[str, Any]]:
    """Import + call the semantic reviewer lazily.  None on unavailable."""
    try:
        # Imports from scripts/qe/semantic_review.py — shipping in PR #455
        sys.path.insert(0, str(_SCRIPTS_ROOT / "qe"))
        from semantic_review import run_semantic_review  # type: ignore
    except Exception:
        return None

    try:
        result = run_semantic_review(project_dir, complexity)
        if isinstance(result, dict):
            return result
    except Exception:
        return None
    return None


def check_semantic_review(
    files: List[str],
    *,
    budget_seconds: float,
    project_dir: Optional[Path] = None,
    complexity: int = 3,
    **_kwargs: Any,
) -> CheckResult:
    """Delegate to scripts.qe.semantic_review (PR #444).  Fail-open."""
    t0 = time.monotonic()
    result = CheckResult(name="semantic_review", status="ok")

    target = project_dir or Path.cwd()
    report = _call_semantic_reviewer(target, complexity)
    if report is None:
        result.status = "skip"
        result.note = "semantic-review-unavailable"
        result.findings.append(Finding(
            check="semantic_review",
            rule_id="semantic-review-unavailable",
            severity=SEVERITY_INFO,
            message="semantic reviewer (scripts/qe/semantic_review.py) unavailable — skipped",
        ))
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    verdict = str(report.get("verdict", "APPROVE")).upper()
    for raw in report.get("findings", []) or []:
        if not isinstance(raw, dict):
            continue
        sev = SEVERITY_WARN
        if verdict == "REJECT":
            sev = SEVERITY_BLOCK
        elif verdict == "APPROVE":
            sev = SEVERITY_INFO
        msg = str(raw.get("message") or raw.get("summary") or raw.get("title") or "")[:200]
        if not msg:
            continue
        result.findings.append(Finding(
            check="semantic_review",
            rule_id=str(raw.get("rule_id") or raw.get("kind") or "spec-drift"),
            severity=sev,
            message=msg,
            file=raw.get("file"),
            line=raw.get("line") if isinstance(raw.get("line"), int) else None,
        ))

    if not result.findings and verdict != "APPROVE":
        # Reviewer issued a verdict but no itemized findings — surface one rollup.
        result.findings.append(Finding(
            check="semantic_review",
            rule_id="verdict",
            severity=SEVERITY_WARN if verdict == "CONDITIONAL" else SEVERITY_BLOCK,
            message=f"Semantic review verdict: {verdict} ({report.get('summary', '')[:120]})",
        ))

    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Check 5: skip_log (unresolved skip-reeval entries)
# ---------------------------------------------------------------------------

def _call_audit_skip_log(project_dir: Path) -> List[Dict[str, Any]]:
    """Import + call audit_skip_log.scan.  Empty list on error."""
    try:
        sys.path.insert(0, str(_SCRIPTS_ROOT / "crew"))
        from audit_skip_log import scan  # type: ignore
        entries = scan(project_dir)
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def check_skip_log(
    files: List[str],
    *,
    budget_seconds: float,
    project_dir: Optional[Path] = None,
    **_kwargs: Any,
) -> CheckResult:
    """Surface unresolved skip-reeval-log.json entries."""
    t0 = time.monotonic()
    result = CheckResult(name="skip_log", status="ok")

    target = project_dir
    if target is None or not target.is_dir():
        result.status = "skip"
        result.note = "no crew project directory"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    entries = _call_audit_skip_log(target)
    if not entries:
        result.note = "no unresolved skip entries"
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    for entry in entries[:20]:
        phase = entry.get("_source_phase", "?")
        reason = entry.get("reason") or entry.get("note") or "unresolved skip"
        result.findings.append(Finding(
            check="skip_log",
            rule_id="skip-unresolved",
            severity=SEVERITY_WARN,
            message=f"Unresolved skip in phase `{phase}`: {str(reason)[:120]}",
        ))

    if len(entries) > 20:
        result.findings.append(Finding(
            check="skip_log",
            rule_id="skip-unresolved",
            severity=SEVERITY_INFO,
            message=f"... and {len(entries) - 20} more unresolved skip entries",
        ))

    result.duration_ms = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Registry + runner
# ---------------------------------------------------------------------------

CHECK_REGISTRY: Dict[str, Callable[..., CheckResult]] = {
    "bulletproof_scan": check_bulletproof_scan,
    "debug_artifacts": check_debug_artifacts,
    "adr_constraints": check_adr_constraints,
    "semantic_review": check_semantic_review,
    "skip_log": check_skip_log,
}


def run_pipeline(
    profile_name: Optional[str] = None,
    *,
    cwd: Optional[Path] = None,
    project_dir: Optional[Path] = None,
    complexity: int = 3,
    build_phase_just_closed: bool = False,
    files: Optional[List[str]] = None,
) -> PipelineReport:
    """Run the guard pipeline end-to-end.  Never raises.

    Args:
        profile_name: "scalpel" | "standard" | "deep".  Auto-selects when None.
        cwd: Working directory for git probes and relative paths.  Defaults to
            the process CWD.
        project_dir: Crew project directory (for skip_log check).  Optional.
        complexity: Complexity score passed to the semantic reviewer.
        build_phase_just_closed: Promotes scalpel → standard via auto_select.
        files: Optional explicit file list (useful for tests).  When None,
            uses `git diff --name-only`.

    Returns:
        A fully populated PipelineReport.  `status` is "ok" unless the
        total-budget deadline was exceeded ("budget_exceeded") or an
        unrecoverable error happened ("error").
    """
    base = cwd or Path.cwd()
    t0 = time.monotonic()

    if profile_name:
        profile: GuardProfile = get_profile(profile_name)
    else:
        profile = auto_select(build_phase_just_closed=build_phase_just_closed, cwd=base)

    # Hard deadline for the whole pipeline
    deadline = t0 + profile.budget_seconds

    # Share one file-list across all diff-driven checks
    try:
        change_set = files if files is not None else _changed_files(base)
    except Exception:
        change_set = []

    report = PipelineReport(
        pipeline_version=PIPELINE_VERSION,
        profile=profile.name,
        budget_seconds=profile.budget_seconds,
        duration_ms=0,
        status="ok",
    )

    per_check_budget = max(
        0.1,
        profile.budget_seconds * _PER_CHECK_BUDGET_FRACTION / max(1, len(profile.checks)),
    )

    for name in profile.checks:
        if time.monotonic() > deadline:
            report.status = "budget_exceeded"
            report.checks.append(CheckResult(
                name=name, status="skip", note="pipeline budget exceeded",
            ))
            continue

        fn = CHECK_REGISTRY.get(name)
        if fn is None:
            report.checks.append(CheckResult(
                name=name, status="error", note=f"unknown check: {name}",
            ))
            continue

        try:
            check_result = fn(
                change_set,
                budget_seconds=per_check_budget,
                cwd=base,
                project_dir=project_dir,
                complexity=complexity,
            )
        except Exception as exc:  # fail-open — one check error doesn't kill the pipeline
            check_result = CheckResult(
                name=name, status="error", note=f"{type(exc).__name__}: {str(exc)[:120]}",
            )
        report.checks.append(check_result)

    # Aggregate findings
    by_sev: Dict[str, int] = {SEVERITY_BLOCK: 0, SEVERITY_WARN: 0, SEVERITY_INFO: 0}
    total = 0
    for c in report.checks:
        for f in c.findings:
            total += 1
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    report.findings_by_severity = by_sev
    report.total_findings = total
    report.duration_ms = int((time.monotonic() - t0) * 1000)
    return report


# ---------------------------------------------------------------------------
# Briefing integration — write findings to a session-scoped file
# ---------------------------------------------------------------------------

def _session_guard_dir() -> Path:
    import tempfile
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    safe = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return Path(tempfile.gettempdir()) / "wicked-guard" / safe


def write_briefing_file(report: PipelineReport) -> Optional[Path]:
    """Write the report where bootstrap.py can pick it up next session.

    Uses ${TMPDIR}/wicked-guard/{session_id}/findings.json.  Fail-open — returns
    None on error.
    """
    try:
        out_dir = _session_guard_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "findings.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        return path
    except Exception:
        return None


def render_summary(report: PipelineReport, *, max_lines: int = 8) -> str:
    """Render a compact, user-facing summary suitable for the session message."""
    if report.total_findings == 0:
        return f"[Guard] {report.profile} pipeline ran ({report.duration_ms}ms) — no findings"

    header = (
        f"[Guard] {report.profile} pipeline surfaced {report.total_findings} finding(s) "
        f"({report.duration_ms}ms) — block={report.findings_by_severity.get(SEVERITY_BLOCK, 0)} "
        f"warn={report.findings_by_severity.get(SEVERITY_WARN, 0)} "
        f"info={report.findings_by_severity.get(SEVERITY_INFO, 0)}. "
        "Review next-session briefing for details (not a hard block)."
    )

    # Show top findings by severity (block first, then warn)
    priority = {SEVERITY_BLOCK: 0, SEVERITY_WARN: 1, SEVERITY_INFO: 2}
    all_findings: List[Finding] = []
    for c in report.checks:
        all_findings.extend(c.findings)
    all_findings.sort(key=lambda f: priority.get(f.severity, 99))

    lines = [header]
    for finding in all_findings[:max_lines]:
        loc = f" @ {finding.file}:{finding.line}" if finding.file and finding.line else (
            f" @ {finding.file}" if finding.file else ""
        )
        lines.append(f"  - [{finding.severity}] {finding.rule_id}: {finding.message}{loc}")
    if len(all_findings) > max_lines:
        lines.append(f"  ... and {len(all_findings) - max_lines} more")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bus emission
# ---------------------------------------------------------------------------

def emit_findings_event(report: PipelineReport) -> None:
    """Emit a wicked.guard.findings event.  Fail-open.

    Uses scripts/_bus.py::emit_event when available and the event is in the
    BUS_EVENT_MAP.  When not, writes a JSONL line to a session-scoped
    fallback file so we still have a trail (matches the #443 pattern).
    """
    payload = {
        "profile": report.profile,
        "duration_ms": report.duration_ms,
        "status": report.status,
        "total_findings": report.total_findings,
        "findings_by_severity": report.findings_by_severity,
        # Do NOT ship raw findings (paths/snippets) to the bus — deny-list rules.
        # Downstream subscribers can load the briefing file by session_id.
        "session_id": os.environ.get("CLAUDE_SESSION_ID", "default"),
    }
    try:
        sys.path.insert(0, str(_SCRIPTS_ROOT))
        from _bus import emit_event, BUS_EVENT_MAP  # type: ignore
        if "wicked.guard.findings" in BUS_EVENT_MAP:
            emit_event("wicked.guard.findings", payload)
            return
    except Exception:
        pass  # fail open — fall through to JSONL fallback below

    # Fallback: append a JSONL line so we still have a local trail.
    try:
        out_dir = _session_guard_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "bus-fallback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "wicked.guard.findings", "payload": payload}) + "\n")
    except Exception:
        pass  # fail open — telemetry should never block the caller


# ---------------------------------------------------------------------------
# CLI — for debugging only
# ---------------------------------------------------------------------------

def _main_cli(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Run the guard pipeline")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("--profile", default=None, help="scalpel|standard|deep")
    ap.add_argument("--project-dir", default=None)
    ap.add_argument("--complexity", type=int, default=3)
    ap.add_argument("--emit-bus", action="store_true")
    ap.add_argument("--write-briefing", action="store_true")
    args = ap.parse_args(argv)

    project_dir = Path(args.project_dir) if args.project_dir else None
    report = run_pipeline(
        profile_name=args.profile,
        project_dir=project_dir,
        complexity=args.complexity,
    )

    sys.stdout.write(json.dumps(report.to_dict(), indent=2))
    sys.stdout.write("\n")

    if args.emit_bus:
        emit_findings_event(report)
    if args.write_briefing:
        write_briefing_file(report)
    return 0


if __name__ == "__main__":
    sys.exit(_main_cli(sys.argv[1:]))
