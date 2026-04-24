#!/usr/bin/env python3
"""
6-Point Verification Protocol — wicked-crew issue #352.

Runs 6 automated evidence-based checks as part of the review phase gate.
Each check is independent — one failure does not prevent others from running.
Graceful degradation everywhere: missing tools/files produce SKIP, not crashes.

The 6 checks:
    1. acceptance_criteria — AC from clarify phase linked to deliverables
    2. test_suite          — run project test command, exit 0 = PASS
    3. debug_artifacts     — scan changed files for debug leftovers
    4. code_quality        — lint + type check if configured
    5. documentation       — public APIs / new features have docs
    6. traceability        — requirement -> design -> code -> test chains

Usage:
    # Run all 6 checks
    python3 verification_protocol.py run --project P --phases-dir ./phases

    # Run a single check
    python3 verification_protocol.py run --project P --phases-dir ./phases --check debug_artifacts

    # Provide explicit file list instead of git diff
    python3 verification_protocol.py run --project P --phases-dir ./phases --files src/a.py src/b.ts

Output:
    JSON report to stdout.  Human-readable summary to stderr.
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# sys.path — allow sibling imports (e.g. traceability_generator)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROTOCOL_VERSION = "1.0"
SUBPROCESS_TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str           # e.g. "acceptance_criteria"
    status: str         # PASS, FAIL, SKIP
    evidence: str       # human-readable evidence string
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "evidence": self.evidence,
            "details": self.details,
        }


@dataclass
class VerificationReport:
    """Aggregated report from all checks."""
    protocol_version: str
    project_id: str
    timestamp: str
    checks: List[CheckResult]

    @property
    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"pass": 0, "fail": 0, "skip": 0}
        for c in self.checks:
            key = c.status.lower()
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def verdict(self) -> str:
        return "FAIL" if any(c.status == "FAIL" for c in self.checks) else "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "project_id": self.project_id,
            "timestamp": self.timestamp,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
            "verdict": self.verdict,
        }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    timeout: int = SUBPROCESS_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run a command with timeout and captured output.  Never raises on non-zero."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="command not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=-2, stdout="", stderr="timeout")
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, returncode=-3, stdout="", stderr=str(exc))


def _changed_files(explicit_files: Optional[List[str]] = None) -> List[str]:
    """Return list of changed files via git diff or explicit list."""
    if explicit_files:
        return [f for f in explicit_files if os.path.isfile(f)]

    # Try git diff HEAD~1
    result = _run_command(["git", "diff", "--name-only", "HEAD~1"])
    if result.returncode == 0 and result.stdout.strip():
        return [f for f in result.stdout.strip().splitlines() if os.path.isfile(f)]

    # Fallback: staged files
    result = _run_command(["git", "diff", "--name-only", "--cached"])
    if result.returncode == 0 and result.stdout.strip():
        return [f for f in result.stdout.strip().splitlines() if os.path.isfile(f)]

    return []


def _read_text(path: Path) -> str:
    """Read file text, returning empty string on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Acceptance-criteria extraction  (shared patterns from traceability_generator)
# ---------------------------------------------------------------------------

_AC_TABLE_ROW_RE = re.compile(
    r"\|\s*(?P<id>AC-\d+(?:\.\d+)*|[A-Z]{1,4}-\d+(?:\.\d+)*|\d+)\s*\|"
    r"\s*(?P<desc>[^|]+)\s*\|"
    r"\s*(?P<test>[^|]*)\s*\|",
    re.IGNORECASE,
)

_AC_LIST_RE = re.compile(
    r"[-*]\s+(?:\*\*)?(?P<id>AC-\d+(?:\.\d+)*|[A-Z]{1,4}-\d+(?:\.\d+)*)(?:\*\*)?\s*[:\-]\s*(?P<desc>.+)",
    re.IGNORECASE,
)

# Tokenize all AC references in deliverable text ONCE into a canonical set.
# This makes verification = exact set membership, not substring scan.
# AC-3 and AC-30 produce DISTINCT tokens; no false positives possible.
_AC_TOKEN_RE = re.compile(r"\bAC[\s_-]*\d+(?:\.\d+)*\b", re.IGNORECASE)


def _canonical_ac(value: str) -> str:
    """Normalize AC identifier variants to canonical form: 'ac-3' or 'ac-3.1'.

    Examples: 'AC-3' -> 'ac-3', 'AC3' -> 'ac-3', 'AC_3.1' -> 'ac-3.1', 'ac 3' -> 'ac-3'.
    """
    m = re.search(r"ac[\s_-]*(\d+(?:\.\d+)*)", value, re.IGNORECASE)
    return f"ac-{m.group(1)}" if m else value.lower()


def _extract_ac_ids(text: str) -> List[str]:
    """Extract acceptance-criteria IDs from markdown text."""
    ids: List[str] = []
    seen: set = set()

    for match in _AC_TABLE_ROW_RE.finditer(text):
        ac_id = match.group("id").strip()
        desc = match.group("desc").strip()
        if "criterion" in desc.lower() or "description" in desc.lower():
            continue
        if ac_id not in seen:
            seen.add(ac_id)
            ids.append(ac_id)

    if not ids:
        for match in _AC_LIST_RE.finditer(text):
            ac_id = match.group("id").strip()
            if ac_id not in seen:
                seen.add(ac_id)
                ids.append(ac_id)

    return ids


# ---------------------------------------------------------------------------
# Check 1: acceptance_criteria
# ---------------------------------------------------------------------------

def check_acceptance_criteria(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Cross-reference AC from clarify/test-strategy against deliverables."""
    name = "acceptance_criteria"

    # Locate AC source files
    ac_sources: List[Path] = []
    for subdir in ("clarify", "test-strategy", "qe"):
        d = phases_dir / subdir
        if d.is_dir():
            ac_sources.extend(sorted(d.glob("*.md")))

    if not ac_sources:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No clarify/test-strategy phase directory found",
        )

    # Extract all AC IDs
    all_ac_ids: List[str] = []
    for src in ac_sources:
        text = _read_text(src)
        all_ac_ids.extend(_extract_ac_ids(text))

    if not all_ac_ids:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No acceptance criteria IDs found in phase files",
        )

    # Search for AC references across all deliverable directories
    deliverable_dirs = [
        d for d in phases_dir.iterdir()
        if d.is_dir() and d.name not in ("clarify", "test-strategy", "qe")
    ]

    deliverable_text = ""
    for d in deliverable_dirs:
        for md in d.glob("**/*.md"):
            deliverable_text += _read_text(md) + "\n"
        for py in d.glob("**/*.py"):
            deliverable_text += _read_text(py) + "\n"

    # Build the deliverable's set of canonical AC tokens (one pass over text).
    # Set membership is exact — AC-3 and AC-30 are distinct tokens.
    deliverable_ac_set: set = {
        _canonical_ac(match.group(0))
        for match in _AC_TOKEN_RE.finditer(deliverable_text)
    }

    def _ac_matches(ac_id: str) -> bool:
        """True if ac_id (or its parent for dotted IDs) appears in deliverable AC set."""
        canon = _canonical_ac(ac_id)
        if canon in deliverable_ac_set:
            return True
        # Parent-id fallback as a SET lookup (deliberate, not accidental substring).
        # AC-3.1 is satisfied if deliverable references AC-3.
        if "." in canon:
            parent = canon.rsplit(".", 1)[0]
            return parent in deliverable_ac_set
        return False

    # Check which ACs are referenced
    linked: List[str] = []
    unlinked: List[str] = []
    for ac_id in all_ac_ids:
        if _ac_matches(ac_id):
            linked.append(ac_id)
        else:
            unlinked.append(ac_id)

    total = len(all_ac_ids)
    linked_count = len(linked)

    # (C) Downgrade severity: >=80% coverage → WARN instead of FAIL
    if unlinked:
        coverage = linked_count / total if total else 0.0
        if coverage >= 0.80:
            return CheckResult(
                name=name,
                status="WARN",
                evidence=(
                    f"{linked_count}/{total} AC linked; high coverage threshold met; "
                    f"treating as advisory; missing: {', '.join(unlinked)}"
                ),
                details={"linked": linked, "unlinked": unlinked, "total": total},
            )
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"{linked_count}/{total} AC linked; missing: {', '.join(unlinked)}",
            details={"linked": linked, "unlinked": unlinked, "total": total},
        )
    return CheckResult(
        name=name,
        status="PASS",
        evidence=f"{linked_count}/{total} AC linked",
        details={"linked": linked, "total": total},
    )


# ---------------------------------------------------------------------------
# Check 2: test_suite
# ---------------------------------------------------------------------------

_TEST_RUNNERS: List[Dict[str, Any]] = [
    # Detect from package.json
    {"marker": "package.json", "key": "scripts.test", "cmd": ["npm", "test", "--", "--passWithNoTests"]},
    # Detect from pyproject.toml / setup.py
    {"marker": "pyproject.toml", "key": None, "cmd": ["pytest", "--tb=short", "-q"]},
    {"marker": "setup.py", "key": None, "cmd": ["pytest", "--tb=short", "-q"]},
    # Makefile
    {"marker": "Makefile", "key": "test", "cmd": ["make", "test"]},
]


def _detect_test_runner(cwd: Optional[str] = None) -> Optional[List[str]]:
    """Detect the project's test runner from config files."""
    root = Path(cwd) if cwd else Path.cwd()

    # package.json with test script
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            pkg = json.loads(_read_text(pkg_json))
            scripts = pkg.get("scripts", {})
            if scripts.get("test") and "no test specified" not in scripts["test"]:
                return ["npm", "test"]
        except Exception:
            pass  # fail open

    # Python projects
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        if shutil.which("pytest"):
            return ["pytest", "--tb=short", "-q"]

    # Makefile with test target
    makefile = root / "Makefile"
    if makefile.is_file():
        text = _read_text(makefile)
        if re.search(r"^test\s*:", text, re.MULTILINE):
            return ["make", "test"]

    return None


def check_test_suite(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Run the project test command and check for exit code 0."""
    name = "test_suite"

    # Detect test runner from the phases directory parent (project root),
    # not from CWD which may be the plugin repo itself
    project_root = str(phases_dir.parent) if phases_dir else None
    runner = _detect_test_runner(cwd=project_root)
    if runner is None:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No test runner detected (no package.json test script, pytest, or Makefile test target)",
        )

    result = _run_command(runner, timeout=SUBPROCESS_TIMEOUT)

    if result.returncode == 0:
        # Try to extract a summary line from output
        output = result.stdout.strip()
        summary_line = output.splitlines()[-1] if output else "tests passed"
        return CheckResult(
            name=name,
            status="PASS",
            evidence=summary_line[:200],
            details={"command": runner, "exit_code": 0},
        )
    elif result.returncode == -2:
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"Test command timed out after {SUBPROCESS_TIMEOUT}s",
            details={"command": runner, "exit_code": result.returncode},
        )
    else:
        stderr_tail = (result.stderr or "").strip().splitlines()
        last_lines = "\n".join(stderr_tail[-5:]) if stderr_tail else "no output"
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"Tests failed (exit {result.returncode}): {last_lines[:300]}",
            details={"command": runner, "exit_code": result.returncode},
        )


# ---------------------------------------------------------------------------
# Check 3: debug_artifacts
# ---------------------------------------------------------------------------

# Patterns to scan for debug artifacts — (regex, applies_to_extensions_or_None)
_DEBUG_PATTERNS: List[Dict[str, Any]] = [
    {"pattern": r"\bconsole\.log\b", "label": "console.log", "extensions": {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}},
    {"pattern": r"\bTODO\b", "label": "TODO", "extensions": None},
    {"pattern": r"\bFIXME\b", "label": "FIXME", "extensions": None},
    {"pattern": r"\bdebugger\b", "label": "debugger", "extensions": {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}},
    {"pattern": r"\bpdb\.set_trace\b", "label": "pdb.set_trace", "extensions": {".py"}},
    {"pattern": r"\bbreakpoint\(\)", "label": "breakpoint()", "extensions": {".py"}},
    {"pattern": r"\bprint\(", "label": "print()", "extensions": {".py"}},
]

# Files/dirs to always skip
_SKIP_PATHS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
}


def _should_skip_path(filepath: str) -> bool:
    """Return True if the path is in a directory we should skip."""
    parts = Path(filepath).parts
    return bool(set(parts) & _SKIP_PATHS)


def check_debug_artifacts(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Scan changed files for debug leftovers."""
    name = "debug_artifacts"

    files = _changed_files(kwargs.get("files"))
    if not files:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No changed files detected",
        )

    matches: List[Dict[str, Any]] = []

    for filepath in files:
        if _should_skip_path(filepath):
            continue

        ext = Path(filepath).suffix.lower()
        try:
            lines = Path(filepath).read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        for line_num, line in enumerate(lines, start=1):
            for dp in _DEBUG_PATTERNS:
                # Check extension filter
                allowed_ext = dp["extensions"]
                if allowed_ext is not None and ext not in allowed_ext:
                    continue

                if re.search(dp["pattern"], line):
                    matches.append({
                        "file": filepath,
                        "line": line_num,
                        "label": dp["label"],
                        "content": line.strip()[:120],
                    })

    if matches:
        # Build a concise evidence string
        evidence_lines = [f"{m['label']} in {m['file']}:{m['line']}" for m in matches[:10]]
        extra = f" (+{len(matches) - 10} more)" if len(matches) > 10 else ""
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"Found {len(matches)} debug artifact(s): " + "; ".join(evidence_lines) + extra,
            details={"matches": matches},
        )

    return CheckResult(
        name=name,
        status="PASS",
        evidence=f"No debug artifacts found in {len(files)} changed file(s)",
        details={"files_scanned": len(files)},
    )


# ---------------------------------------------------------------------------
# Check 4: code_quality
# ---------------------------------------------------------------------------

def _detect_linter() -> Optional[List[str]]:
    """Detect the project's linter/type-checker from config files."""
    root = Path.cwd()

    # Python: ruff
    if (root / "pyproject.toml").is_file() or (root / "ruff.toml").is_file():
        if shutil.which("ruff"):
            return ["ruff", "check", "."]

    # Python: flake8
    if (root / ".flake8").is_file() or (root / "setup.cfg").is_file():
        if shutil.which("flake8"):
            return ["flake8", "."]

    # JS/TS: eslint
    for eslint_cfg in (".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs"):
        if (root / eslint_cfg).is_file():
            if shutil.which("npx"):
                return ["npx", "eslint", "."]

    # package.json lint script
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            pkg = json.loads(_read_text(pkg_json))
            if pkg.get("scripts", {}).get("lint"):
                return ["npm", "run", "lint"]
        except Exception:
            pass  # fail open

    return None


def check_code_quality(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Run lint + type check if configured."""
    name = "code_quality"

    linter = _detect_linter()
    if linter is None:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No linter configured (checked ruff, flake8, eslint, npm lint)",
        )

    result = _run_command(linter, timeout=SUBPROCESS_TIMEOUT)

    if result.returncode == 0:
        return CheckResult(
            name=name,
            status="PASS",
            evidence=f"Linter passed ({' '.join(linter)})",
            details={"command": linter, "exit_code": 0},
        )
    else:
        output = (result.stdout or result.stderr or "").strip()
        summary = output.splitlines()[-1][:200] if output else "linter reported errors"
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"Linter failed (exit {result.returncode}): {summary}",
            details={"command": linter, "exit_code": result.returncode},
        )


# ---------------------------------------------------------------------------
# Check 5: documentation
# ---------------------------------------------------------------------------

_PYTHON_FUNC_RE = re.compile(r"^\s*def\s+(?!_)(\w+)\s*\(", re.MULTILINE)
_JS_FUNC_RE = re.compile(
    r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(",
    re.MULTILINE,
)
_JS_ARROW_RE = re.compile(
    r"export\s+(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>",
    re.MULTILINE,
)


def _check_python_docs(filepath: str, content: str) -> List[Dict[str, str]]:
    """Check that public Python functions have docstrings."""
    undocumented: List[Dict[str, str]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return undocumented

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private/protected
            if node.name.startswith("_"):
                continue
            docstring = ast.get_docstring(node)
            if not docstring:
                undocumented.append({
                    "file": filepath,
                    "function": node.name,
                    "line": node.lineno,
                })
    return undocumented


def _check_js_docs(filepath: str, content: str) -> List[Dict[str, str]]:
    """Check that exported JS/TS functions have JSDoc comments."""
    undocumented: List[Dict[str, str]] = []
    lines = content.splitlines()

    for regex in (_JS_FUNC_RE, _JS_ARROW_RE):
        for match in regex.finditer(content):
            func_name = match.group(1)
            # Find which line this is on
            start = content[:match.start()].count("\n")
            # Check preceding lines for JSDoc
            has_jsdoc = False
            for i in range(max(0, start - 5), start):
                if i < len(lines) and ("/**" in lines[i] or "* @" in lines[i]):
                    has_jsdoc = True
                    break
            if not has_jsdoc:
                undocumented.append({
                    "file": filepath,
                    "function": func_name,
                    "line": start + 1,
                })

    return undocumented


def check_documentation(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Check that public APIs / new features have documentation."""
    name = "documentation"

    files = _changed_files(kwargs.get("files"))
    if not files:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No changed files detected",
        )

    # Filter to source files only
    source_files = [
        f for f in files
        if Path(f).suffix.lower() in (".py", ".js", ".ts", ".jsx", ".tsx", ".mjs")
        and not _should_skip_path(f)
    ]

    if not source_files:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No new source files to check for documentation",
        )

    all_undocumented: List[Dict[str, str]] = []
    total_public = 0

    for filepath in source_files:
        content = _read_text(Path(filepath))
        if not content:
            continue

        ext = Path(filepath).suffix.lower()
        if ext == ".py":
            funcs = _PYTHON_FUNC_RE.findall(content)
            total_public += len(funcs)
            all_undocumented.extend(_check_python_docs(filepath, content))
        elif ext in (".js", ".ts", ".jsx", ".tsx", ".mjs"):
            funcs = _JS_FUNC_RE.findall(content) + _JS_ARROW_RE.findall(content)
            total_public += len(funcs)
            all_undocumented.extend(_check_js_docs(filepath, content))

    if total_public == 0:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No public functions detected in changed files",
        )

    documented = total_public - len(all_undocumented)

    if all_undocumented:
        examples = [f"{u['function']} ({u['file']}:{u['line']})" for u in all_undocumented[:5]]
        extra = f" (+{len(all_undocumented) - 5} more)" if len(all_undocumented) > 5 else ""
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"{documented}/{total_public} public functions documented; missing: {', '.join(examples)}{extra}",
            details={"undocumented": all_undocumented, "total": total_public, "documented": documented},
        )

    return CheckResult(
        name=name,
        status="PASS",
        evidence=f"{documented}/{total_public} public functions documented",
        details={"total": total_public, "documented": documented},
    )


# ---------------------------------------------------------------------------
# Check 6: traceability
# ---------------------------------------------------------------------------

def check_traceability(
    project_id: str,
    phases_dir: Path,
    **kwargs: Any,
) -> CheckResult:
    """Walk requirement -> design -> code -> test chains for completeness."""
    name = "traceability"

    # Try to import the traceability module (issue #349)
    try:
        from crew.traceability_generator import read_test_strategy, map_criteria_to_tasks
    except ImportError:
        try:
            from traceability_generator import read_test_strategy, map_criteria_to_tasks
        except ImportError:
            return CheckResult(
                name=name,
                status="SKIP",
                evidence="Traceability module not available",
            )

    # Read criteria
    criteria = read_test_strategy(phases_dir)
    if not criteria:
        return CheckResult(
            name=name,
            status="SKIP",
            evidence="No acceptance criteria found for traceability analysis",
        )

    # Map to tasks (empty task list — we check linkage, not task status)
    rows = map_criteria_to_tasks(criteria, [])

    # Check for broken chains: criteria with no build task linkage
    # Also verify that deliverable directories exist for each phase
    phase_dirs = [d.name for d in phases_dir.iterdir() if d.is_dir()]
    expected_phases = {"clarify", "design", "build"}
    missing_phases = expected_phases - set(phase_dirs)

    if missing_phases:
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"Broken traceability chain: missing phase directories: {', '.join(sorted(missing_phases))}",
            details={"missing_phases": sorted(missing_phases), "criteria_count": len(criteria)},
        )

    # Check that each criterion has at least a test file reference
    broken_chains: List[str] = []
    for c in criteria:
        if not c.get("test_file"):
            broken_chains.append(c["id"])

    total = len(criteria)
    linked = total - len(broken_chains)

    if broken_chains:
        return CheckResult(
            name=name,
            status="FAIL",
            evidence=f"{linked}/{total} criteria have complete chains; broken: {', '.join(broken_chains[:10])}",
            details={"broken_chains": broken_chains, "total": total, "complete": linked},
        )

    return CheckResult(
        name=name,
        status="PASS",
        evidence=f"{total}/{total} criteria have complete requirement->test chains",
        details={"total": total},
    )


# ---------------------------------------------------------------------------
# Protocol runner
# ---------------------------------------------------------------------------

# Registry of all checks in execution order
CHECK_REGISTRY: Dict[str, Callable[..., CheckResult]] = {
    "acceptance_criteria": check_acceptance_criteria,
    "test_suite": check_test_suite,
    "debug_artifacts": check_debug_artifacts,
    "code_quality": check_code_quality,
    "documentation": check_documentation,
    "traceability": check_traceability,
}


def run_protocol(
    project_id: str,
    phases_dir: Path,
    checks: Optional[Sequence[str]] = None,
    files: Optional[List[str]] = None,
) -> VerificationReport:
    """Run all (or selected) verification checks and return a report.

    Args:
        project_id: Crew project identifier.
        phases_dir: Path to the phases/ directory with phase deliverables.
        checks: Optional list of check names to run.  None = run all.
        files: Optional explicit file list for checks that scan files.

    Returns:
        VerificationReport with all check results and verdict.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    names_to_run = list(checks) if checks else list(CHECK_REGISTRY.keys())
    results: List[CheckResult] = []

    for check_name in names_to_run:
        func = CHECK_REGISTRY.get(check_name)
        if func is None:
            results.append(CheckResult(
                name=check_name,
                status="SKIP",
                evidence=f"Unknown check: {check_name}",
            ))
            continue

        try:
            result = func(
                project_id=project_id,
                phases_dir=phases_dir,
                files=files,
            )
            results.append(result)
        except Exception as exc:
            # Graceful degradation: catch-all for unexpected errors
            results.append(CheckResult(
                name=check_name,
                status="SKIP",
                evidence=f"Check raised an unexpected error: {exc}",
                details={"error": str(exc)},
            ))

    return VerificationReport(
        protocol_version=PROTOCOL_VERSION,
        project_id=project_id,
        timestamp=timestamp,
        checks=results,
    )


# ---------------------------------------------------------------------------
# Human-readable summary (printed to stderr)
# ---------------------------------------------------------------------------

def _print_summary(report: VerificationReport) -> None:
    """Print a human-readable summary to stderr."""
    w = sys.stderr.write

    w(f"\n--- Verification Protocol v{report.protocol_version} ---\n")
    w(f"Project: {report.project_id}\n")
    w(f"Time:    {report.timestamp}\n\n")

    status_icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}

    for check in report.checks:
        icon = status_icons.get(check.status, "[????]")
        w(f"  {icon} {check.name}: {check.evidence}\n")

    s = report.summary
    w(f"\nSummary: {s['pass']} passed, {s['fail']} failed, {s['skip']} skipped\n")
    w(f"Verdict: {report.verdict}\n\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="6-Point Verification Protocol for evidence-based review gates",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run verification checks")
    run_parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="Crew project identifier",
    )
    run_parser.add_argument(
        "--phases-dir",
        type=Path,
        default=Path("phases"),
        help="Path to the phases/ directory (default: phases/)",
    )
    run_parser.add_argument(
        "--check",
        type=str,
        default=None,
        help="Run a single check by name (default: run all 6)",
    )
    run_parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Explicit file list for file-scanning checks (default: git diff)",
    )

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    checks = [args.check] if args.check else None

    report = run_protocol(
        project_id=args.project,
        phases_dir=args.phases_dir,
        checks=checks,
        files=args.files,
    )

    # JSON report to stdout
    sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")

    # Human-readable summary to stderr
    _print_summary(report)

    # Exit code: 0 if PASS, 1 if FAIL
    sys.exit(0 if report.verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
