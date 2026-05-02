#!/usr/bin/env python3
"""archetype_detect.py — Heuristic project archetype classifier (D1).

Classifies a crew project into one of 7 archetypes based on changed files and
process-plan text. Priority-ordered: the first archetype whose signals match (after
honoring negative signals) wins.

Archetype enum (priority order):
  1. schema-migration
  2. multi-repo
  3. testing-only
  4. config-infra
  5. skill-agent-authoring
  6. docs-only
  7. code-repo  (fallback)

Public API:
    detect_archetype(project_dir, plan_path=None) -> dict

Return shape:
    {
        "archetype": str,        # 7-value enum
        "confidence": float,     # [0.0, 1.0]; <0.5 triggers caller log warning
        "signals":   list[str],  # non-empty; explains match
        "priority_matched": int, # optional debug
        "fallback": bool,        # true when code-repo reached by exhaustion
        "detector_version": str,
    }

Stdlib-only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Stack-shape projection (#723). Imported lazily-tolerant: if the module is
# absent for any reason the archetype result still ships, just without the
# additive `detected_stack` field. Stack identity is a *projection*, never
# persisted state.
try:
    from crew._stack_signals import detect_stack as _detect_stack  # type: ignore
except Exception:  # pragma: no cover — optional dependency at runtime
    try:
        from _stack_signals import detect_stack as _detect_stack  # type: ignore
    except Exception:
        _detect_stack = None  # type: ignore

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# DOMINANCE_RATIO = 4: if non-md source files > 4 * skill/agent md files,
# skill-agent-authoring is downgraded to code-repo.
# Decision: challenge-phase pattern-advisor validated 4:1 with strict >
# operator. See phases/challenge/build-notes.md §A3.
DOMINANCE_RATIO = 4

ARCHETYPE_ENUM = frozenset({
    "code-repo",
    "docs-only",
    "skill-agent-authoring",
    "config-infra",
    "multi-repo",
    "testing-only",
    "schema-migration",
})

DETECTOR_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# File-pattern helpers (compiled once at module load)
# ---------------------------------------------------------------------------

# Test file patterns to EXCLUDE from API-surface detection (MINOR-3).
_TEST_PATTERNS = (
    re.compile(r"^tests/"),
    re.compile(r"test_[^/]+\.py$"),
    re.compile(r"conftest\.py$"),
)

_SCHEMA_FILE_PATTERNS = (
    re.compile(r"\.sql$"),
    re.compile(r"\.alembic$"),
    re.compile(r"\.migration\.py$"),
    re.compile(r"(^|/)migrations/"),
    re.compile(r"-schema\.md$"),
    re.compile(r"-schema\.json$"),
    re.compile(r"scripts/re-eval-addendum-schema"),
    re.compile(r"(^|/)migration[s]?(/|$)"),
)

_SCHEMA_VALIDATOR_PATTERNS = (
    re.compile(r"validator.*\.py$"),
    re.compile(r"schema.*\.py$"),
)

_SCHEMA_KW = re.compile(
    r"schema bump|schema migration|schema version|additive schema|"
    r"backward compat|migration rollback|reeval_addendum|addendum schema",
    re.IGNORECASE,
)

_MULTI_REPO_KW = re.compile(
    r"affected_repos|cross-repo|multi-repo|multiple repositories|"
    r"\brepo:\s|\brepos:\s|coordinated across",
    re.IGNORECASE,
)

_TESTING_ONLY_FILE_PATTERNS = (
    re.compile(r"^tests/"),
    re.compile(r"test_[^/]+\.py$"),
    re.compile(r"[^/]+_test\.py$"),
    re.compile(r"\.spec\.ts$"),
    re.compile(r"\.spec\.js$"),
    re.compile(r"\.test\.ts$"),
    re.compile(r"\.test\.js$"),
    re.compile(r"^scenarios/.*\.md$"),
    re.compile(r"^fixtures/"),
)

_TESTING_ONLY_KW = re.compile(
    r"testing-only|test coverage|test matrix|\bfixture\b|scenario authoring",
    re.IGNORECASE,
)

_CONFIG_INFRA_FILE_PATTERNS = (
    re.compile(r"^\.claude-plugin/.*\.json$"),
    re.compile(r"^hooks/hooks\.json$"),
    re.compile(r"^scripts/_[^/]+\.json$"),
    re.compile(r"^\.github/.*\.(yaml|yml)$"),
    re.compile(r"^\.circleci/.*\.(yaml|yml)$"),
    re.compile(r"(^|/)Dockerfile$"),
    re.compile(r"docker-compose[^/]*\.yml$"),
    re.compile(r"\.tf$"),
    re.compile(r"\.bicep$"),
)

_CONFIG_INFRA_KW = re.compile(
    r"gate-policy|config update|infra change|consumer registry|"
    r"hooks\.json|plugin\.json|bus consumer",
    re.IGNORECASE,
)

# Skill/agent .md files MUST have YAML frontmatter to count for skill-agent-authoring.
_AGENT_SKILL_CMD_PATH = re.compile(
    r"^(agents|skills|commands)/.*\.md$"
)

_SKILL_AGENT_KW = re.compile(
    r"agent authoring|skill authoring|new agent|new skill|command definition|"
    r"subagent_type|crew agent|gate-adjudicator|qe-evaluator|test-strategist",
    re.IGNORECASE,
)

_DOCS_ONLY_FILE_EXTENSIONS = {".md", ".rst", ".txt"}
_DOCS_ONLY_PATH_PATTERN = re.compile(r"^docs/")

_DOCS_ONLY_KW = re.compile(
    r"docs update|documentation only|\breadme\b|reference material|"
    r"evidence-framing|SKILL\.md update",
    re.IGNORECASE,
)

_SOURCE_CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".go", ".java", ".rs", ".rb", ".cs", ".cpp", ".c",
}

_NON_DOC_EXTENSIONS = {
    ".py", ".ts", ".js", ".go", ".java", ".rs", ".rb", ".cs", ".cpp", ".c",
    ".json", ".yaml", ".yml", ".toml", ".sh", ".bash",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_test_file(path: str) -> bool:
    """Return True if path matches test/conftest exclusion patterns (MINOR-3)."""
    for pat in _TEST_PATTERNS:
        if pat.search(path):
            return True
    return False


def _has_yaml_frontmatter(file_path: Path) -> bool:
    """Return True if the file starts with a YAML frontmatter block (---...---)."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return False
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return i > 0  # found closing ---
        return False
    except OSError:
        return False


def _file_content(path: Path) -> str:
    """Read file content; return empty string on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_plan_text(plan_path: Optional[Path]) -> str:
    if plan_path is None or not plan_path.exists():
        return ""
    return _file_content(plan_path)


def _match_any(path: str, patterns: tuple) -> bool:
    return any(pat.search(path) for pat in patterns)


def _file_suffix(path: str) -> str:
    return Path(path).suffix.lower()


# ---------------------------------------------------------------------------
# Per-archetype detection functions
# Each returns (confidence, signals) or (0.0, []) when not matched.
# Negative signals MUST be honored before returning a match.
# ---------------------------------------------------------------------------

def _detect_schema_migration(
    files: List[str],
    plan_text: str,
    project_dir: Path,
) -> Tuple[float, List[str]]:
    """Priority 1: schema-migration."""
    signals: List[str] = []

    has_file_signal = False
    has_schema_doc_only = True  # guilty until proven otherwise
    validator_changed = False
    non_test_files = [f for f in files if not _is_test_file(f)]

    for f in non_test_files:
        if _match_any(f, _SCHEMA_FILE_PATTERNS):
            has_file_signal = True
            signals.append(f"schema-migration file match: {f}")
            # If it is a .md file, check for code counterpart
            if f.endswith(".md"):
                pass  # still a schema doc unless we find a paired validator
            else:
                has_schema_doc_only = False
        if _match_any(f, _SCHEMA_VALIDATOR_PATTERNS) and not _is_test_file(f):
            validator_changed = True

    # Negative signal 1: all files are docs-only (.md/.rst) with no code/validator
    if has_file_signal and has_schema_doc_only and not validator_changed:
        # Check if all matched schema files are .md
        schema_files_matched = [
            f for f in non_test_files if _match_any(f, _SCHEMA_FILE_PATTERNS)
        ]
        all_docs = all(f.endswith(".md") or f.endswith(".rst") for f in schema_files_matched)
        if all_docs:
            # Negative signal: doc-only schema change without a validator counterpart
            return 0.0, []

    # Keyword signal
    kw_match = bool(_SCHEMA_KW.search(plan_text))
    if kw_match:
        signals.append("schema-migration keyword match in plan text")

    # Negative signal 2: "docs-only" in goals/scope section
    if re.search(r"docs.only", plan_text, re.IGNORECASE):
        return 0.0, []

    # File-only match is insufficient — need keyword signal too.
    if not kw_match:
        return 0.0, []

    if not signals:
        return 0.0, []

    confidence = 0.85 if has_file_signal else 0.55
    return confidence, signals


def _detect_multi_repo(
    files: List[str],
    plan_text: str,
) -> Tuple[float, List[str]]:
    """Priority 2: multi-repo."""
    signals: List[str] = []

    # File signal: affected_repos in plan or cross-repo paths
    if "affected_repos" in plan_text:
        signals.append("multi-repo: affected_repos key referenced in plan text")

    kw_match = bool(_MULTI_REPO_KW.search(plan_text))
    if kw_match:
        signals.append("multi-repo keyword match in plan text")

    if not signals:
        return 0.0, []

    # Negative signal: affected_repos present but empty list
    if re.search(r"affected_repos.*\[\s*\]", plan_text) or re.search(
        r'"affected_repos"\s*:\s*\[\s*\]', plan_text
    ):
        return 0.0, []

    confidence = 0.9 if "affected_repos" in plan_text and not kw_match else 0.7
    if "affected_repos" in plan_text:
        confidence = 0.9
    return confidence, signals


def _detect_testing_only(
    files: List[str],
    plan_text: str,
) -> Tuple[float, List[str]]:
    """Priority 3: testing-only. ALL changed files must be test/fixture files."""
    if not files:
        return 0.0, []

    signals: List[str] = []
    non_test_any = False

    for f in files:
        if _match_any(f, _TESTING_ONLY_FILE_PATTERNS):
            signals.append(f"testing-only file match: {f}")
        else:
            non_test_any = True
            break  # Any non-test file disqualifies

    # Negative signal: any non-test file present
    if non_test_any:
        return 0.0, []

    # Negative signal: plan references non-test deliverables
    if re.search(r"\bagents/|\bscripts/|\bproduction\b", plan_text):
        return 0.0, []

    if not signals:
        return 0.0, []

    return 0.9, signals


def _detect_config_infra(
    files: List[str],
    plan_text: str,
    project_dir: Path,
) -> Tuple[float, List[str]]:
    """Priority 4: config-infra.

    Negative signals:
    - Any changed file contains substantial new function/class definitions
      (>20 lines of non-comment, non-whitespace added, not in file-signals list)
    - A new agent/skill .md file with YAML frontmatter is added (skill-agent-authoring takes over)
    """
    signals: List[str] = []
    non_test_files = [f for f in files if not _is_test_file(f)]

    has_file_signal = False
    for f in non_test_files:
        if _match_any(f, _CONFIG_INFRA_FILE_PATTERNS):
            has_file_signal = True
            signals.append(f"config-infra file match: {f}")

    kw_match = bool(_CONFIG_INFRA_KW.search(plan_text))
    if kw_match:
        signals.append("config-infra keyword match in plan text")

    if not has_file_signal and not kw_match:
        return 0.0, []

    # CRITICAL negative signal (Vector 4 from challenge phase):
    # If any .md file under agents/, skills/, commands/ has YAML frontmatter,
    # config-infra is DISQUALIFIED and skill-agent-authoring wins.
    # NOTE: This MUST be honored — strict priority-order alone is NOT sufficient.
    # See: phases/challenge/build-notes.md §MAJOR + archetype-detection-rules.md conflict table.
    for f in non_test_files:
        if _AGENT_SKILL_CMD_PATH.match(f):
            full_path = project_dir / f
            if full_path.exists() and _has_yaml_frontmatter(full_path):
                # Negative signal fires — config-infra is disqualified
                return 0.0, []

    # Negative signal: substantial new code added outside file-signals list
    # (heuristic: >20 non-comment, non-whitespace lines in a .py file not in config patterns)
    for f in non_test_files:
        if _file_suffix(f) == ".py" and not _match_any(f, _CONFIG_INFRA_FILE_PATTERNS):
            fp = project_dir / f
            if fp.exists():
                content = _file_content(fp)
                code_lines = [
                    ln for ln in content.splitlines()
                    if ln.strip() and not ln.strip().startswith("#")
                ]
                if len(code_lines) > 20:
                    return 0.0, []

    confidence = 0.9 if (has_file_signal and kw_match) else 0.8
    return confidence, signals


def _detect_skill_agent_authoring(
    files: List[str],
    plan_text: str,
    project_dir: Path,
) -> Tuple[float, List[str]]:
    """Priority 5: skill-agent-authoring.

    Negative signals:
    - Changed .md files lack YAML frontmatter → docs-only
    - Dominant source code at ratio > DOMINANCE_RATIO:1 over .md skill files
    """
    signals: List[str] = []
    non_test_files = [f for f in files if not _is_test_file(f)]

    skill_agent_md_files: List[str] = []
    for f in non_test_files:
        if _AGENT_SKILL_CMD_PATH.match(f):
            full_path = project_dir / f
            if full_path.exists():
                if _has_yaml_frontmatter(full_path):
                    skill_agent_md_files.append(f)
                    signals.append(f"skill-agent-authoring: YAML frontmatter in {f}")
            else:
                # File may be new (not yet on disk in project_dir context) — treat as matching
                # if path matches agents/skills/commands pattern
                skill_agent_md_files.append(f)
                signals.append(f"skill-agent-authoring: new agent/skill/command path {f}")

    kw_match = bool(_SKILL_AGENT_KW.search(plan_text))
    if kw_match:
        signals.append("skill-agent-authoring keyword match in plan text")

    if not skill_agent_md_files and not kw_match:
        return 0.0, []

    if not skill_agent_md_files:
        # Keyword only
        return 0.75, signals

    # Dominance threshold: if non-md source files > DOMINANCE_RATIO * skill_agent_md_files,
    # fall through to code-repo. Strict > operator per challenge phase A3 decision.
    non_md_source_files = [
        f for f in non_test_files
        if _file_suffix(f) in _SOURCE_CODE_EXTENSIONS
    ]
    if len(non_md_source_files) > DOMINANCE_RATIO * len(skill_agent_md_files):
        # Downgraded — fall through; return 0.6 which will lose to code-repo
        return 0.0, []  # Let code-repo win by exhaustion

    return 0.85, signals


def _detect_docs_only(
    files: List[str],
    plan_text: str,
    project_dir: Path,
) -> Tuple[float, List[str]]:
    """Priority 6: docs-only. ALL changed files must be documentation."""
    if not files:
        return 0.0, []

    non_test_files = [f for f in files if not _is_test_file(f)]
    if not non_test_files:
        return 0.0, []

    signals: List[str] = []
    all_docs = True

    for f in non_test_files:
        suffix = _file_suffix(f)
        is_doc_path = _DOCS_ONLY_PATH_PATTERN.match(f)
        is_doc_ext = suffix in _DOCS_ONLY_FILE_EXTENSIONS

        if not (is_doc_ext or is_doc_path):
            # Negative signal: non-doc extension present
            all_docs = False
            break

        # Negative signal: .md file with YAML frontmatter (subagent_type or name)
        if suffix == ".md":
            fp = project_dir / f
            if fp.exists() and _has_yaml_frontmatter(fp):
                content = _file_content(fp)
                if re.search(r"^subagent_type:|^name:", content, re.MULTILINE):
                    all_docs = False
                    break
            signals.append(f"docs-only file: {f}")
        else:
            signals.append(f"docs-only file: {f}")

    if not all_docs:
        return 0.0, []

    kw_match = bool(_DOCS_ONLY_KW.search(plan_text))
    if kw_match:
        signals.append("docs-only keyword match in plan text")

    if not signals:
        return 0.0, []

    confidence = 0.85 if all_docs else 0.5
    return confidence, signals


def _detect_code_repo(files: List[str]) -> Tuple[float, List[str]]:
    """Priority 7 (fallback): code-repo."""
    signals: List[str] = []
    for f in files:
        if _file_suffix(f) in _SOURCE_CODE_EXTENSIONS:
            signals.append(f"code-repo source file: {f}")

    if signals:
        return 0.7, signals[:5]  # keep signals concise
    # No source files at all — exhaustion fallback
    return 0.3, ["fallback: no strong archetype signal detected"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_archetype(
    project_dir: "Path | str | dict",
    plan_path: "Optional[Path | str]" = None,
) -> Dict[str, Any]:
    """Classify a crew project into one of 7 archetypes.

    Args:
        project_dir: Path to the project directory (or a dict with ``files``
                     and optional ``plan_path`` keys for testing convenience).
        plan_path:   Optional explicit path to process-plan.md. When omitted,
                     falls back to ``project_dir/process-plan.md``.

    Returns:
        {
            "archetype": str,         # 7-value enum
            "confidence": float,      # [0.0, 1.0]
            "signals": list[str],     # non-empty
            "priority_matched": int,  # 1-7
            "fallback": bool,
            "detector_version": str,
        }

    The detector MUST NOT raise. All exceptions are caught and returned as a
    code-repo fallback with a signal describing the error.
    """
    try:
        return _detect_archetype_inner(project_dir, plan_path)
    except Exception as exc:
        # Resolve a plausible stack-projection root from whatever raw input
        # the caller passed, but never raise from this fallback branch.
        if isinstance(project_dir, dict):
            stack_root: "Path | str | None" = project_dir.get("project_dir") or "."
        else:
            stack_root = project_dir
        return {
            "archetype": "code-repo",
            "confidence": 0.3,
            "signals": [f"fallback: detect_archetype raised: {exc}"],
            "priority_matched": 7,
            "fallback": True,
            "detector_version": DETECTOR_VERSION,
            "detected_stack": _safe_detect_stack(stack_root),
        }


def _detect_archetype_inner(
    project_dir_or_dict: "Path | str | dict",
    plan_path: "Optional[Path | str]",
) -> Dict[str, Any]:
    # Support dict-style input for testing convenience.
    if isinstance(project_dir_or_dict, dict):
        files: List[str] = project_dir_or_dict.get("files") or []
        raw_plan_path = project_dir_or_dict.get("plan_path")
        # When the dict carries no project_dir AND no files, fall back to
        # an unknown-stub result instead of `Path('.')` — which would
        # surface the current working directory's stack to a caller that
        # explicitly didn't provide one. (PR #744 review fix.)
        raw_project_dir = project_dir_or_dict.get("project_dir")
        if not raw_project_dir and not files:
            return {
                "archetype": "code-repo",
                "confidence": 0.3,
                "signals": ["fallback: no project_dir or files supplied"],
                "priority_matched": 7,
                "fallback": True,
                "detector_version": DETECTOR_VERSION,
                "detected_stack": _safe_detect_stack(None),
            }
        project_dir = Path(raw_project_dir or ".")
        if raw_plan_path:
            plan_path = Path(raw_plan_path)
    else:
        project_dir = Path(project_dir_or_dict)
        files = []  # callers must pass files explicitly or via dict

    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)

    if plan_path is None:
        plan_path = project_dir / "process-plan.md"
    else:
        plan_path = Path(plan_path)

    plan_text = _read_plan_text(plan_path)

    # Collect files from project_dir when not provided explicitly
    if not files and project_dir.exists():
        files = _collect_project_files(project_dir)

    # -----------------------------------------------------------------------
    # Priority-ordered detection (negative signals honored at each step)
    # -----------------------------------------------------------------------

    checks = [
        (1, "schema-migration",      lambda: _detect_schema_migration(files, plan_text, project_dir)),
        (2, "multi-repo",            lambda: _detect_multi_repo(files, plan_text)),
        (3, "testing-only",          lambda: _detect_testing_only(files, plan_text)),
        (4, "config-infra",          lambda: _detect_config_infra(files, plan_text, project_dir)),
        (5, "skill-agent-authoring", lambda: _detect_skill_agent_authoring(files, plan_text, project_dir)),
        (6, "docs-only",             lambda: _detect_docs_only(files, plan_text, project_dir)),
    ]

    detected_stack = _safe_detect_stack(project_dir)

    for priority, archetype, detector in checks:
        confidence, signals = detector()
        if confidence > 0.0:
            return {
                "archetype": archetype,
                "confidence": confidence,
                "signals": signals or [f"{archetype}: matched"],
                "priority_matched": priority,
                "fallback": False,
                "detector_version": DETECTOR_VERSION,
                "detected_stack": detected_stack,
            }

    # Fallback: code-repo
    confidence, signals = _detect_code_repo(files)
    return {
        "archetype": "code-repo",
        "confidence": confidence,
        "signals": signals,
        "priority_matched": 7,
        "fallback": True,
        "detector_version": DETECTOR_VERSION,
        "detected_stack": detected_stack,
    }


def _unknown_stack_stub(reason: str | None = None) -> Dict[str, Any]:
    """Return the canonical 'no stack info available' projection shape.

    Used both when the optional `_stack_signals` import is missing and when
    the caller passed no project_dir to scan — falling back to the current
    working directory would surface an unrelated repo's stack (#742, Copilot
    finding 3).
    """
    files_seen: List[str] = []
    if reason:
        files_seen.append(f"reason: {reason}")
    return {
        "language": "unknown",
        "package_manager": "unknown",
        "frameworks": [],
        "has_ui": False,
        "has_api_surface": False,
        "signals": {"files_seen": files_seen, "deps_seen": []},
    }


def _safe_detect_stack(project_dir: "Path | str | None") -> Dict[str, Any]:
    """Run the stack-shape projector with belt-and-braces guards.

    The archetype detector is the gate-keeper for downstream phase routing,
    so it must never raise. The stack signal is purely additive — return a
    safe default on any error so the archetype path is unaffected.

    When ``project_dir`` is None we *do not* fall back to ``Path('.')`` —
    doing so would surface an unrelated repo's stack signals to whichever
    caller happened to be running from a different cwd. Instead we return
    the unknown stub so the caller has to pass an explicit directory.
    """
    if _detect_stack is None:
        return _unknown_stack_stub(reason="_stack_signals module unavailable")
    if project_dir is None:
        # Explicit refusal — the caller must name the project directory.
        # See #742, Copilot finding 3 ("cwd fallback surfaces wrong repo").
        return _unknown_stack_stub(reason="project_dir not provided")
    try:
        path = Path(project_dir) if not isinstance(project_dir, Path) else project_dir
        return _detect_stack(path)
    except Exception as exc:  # pragma: no cover — defensive
        return _unknown_stack_stub(reason=f"error: {exc}")


def _collect_project_files(project_dir: Path) -> List[str]:
    """Walk project_dir and return relative paths (strings) for all non-hidden files."""
    result: List[str] = []
    try:
        for path in project_dir.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(project_dir)).replace("\\", "/")
                # Skip hidden directories
                if any(part.startswith(".") for part in rel.split("/")):
                    continue
                result.append(rel)
    except OSError:
        pass  # fail open — return whatever was collected before the error
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Classify a crew project archetype from changed files + plan text."
    )
    parser.add_argument("project_dir", type=Path, help="Project directory")
    parser.add_argument("--files", nargs="*", default=None, help="Changed file paths")
    parser.add_argument("--plan", type=Path, default=None, help="Path to process-plan.md")
    args = parser.parse_args(argv)

    files = args.files or []
    result = detect_archetype(
        {"files": files, "project_dir": str(args.project_dir)},
        plan_path=args.plan,
    )
    print(json.dumps(result, indent=2))
    if result.get("confidence", 0.0) < 0.5:
        print(
            f"WARNING: low confidence {result['confidence']:.2f} for archetype "
            f"{result['archetype']!r}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
