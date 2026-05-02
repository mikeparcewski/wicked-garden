"""tests/crew/test_stack_signals.py — Unit tests for _stack_signals (#723).

Provenance: AC for #723 — stack signals as factor inputs (no presets,
no parallel state). Detection is *per call*, never persisted.

T1: deterministic — no randomness, no sleep, no network
T2: no sleep-based sync
T3: isolated — every test uses its own tempdir
T4: single focus per test
T5: descriptive names
T6: each docstring cites its rationale
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# conftest.py in this directory inserts scripts/ into sys.path. Belt-and-braces
# in case this file is collected before conftest runs in some harnesses.
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from crew import _stack_signals  # noqa: E402
from crew._stack_signals import detect_stack  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(files: dict) -> Path:
    """Create a temp repo with {relative_path: content} files."""
    tmp = Path(tempfile.mkdtemp(prefix="wg-stack-"))
    for rel, content in files.items():
        fp = tmp / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    return tmp


PYPROJECT_CLICK = """\
[project]
name = "demo-cli"
version = "0.1.0"
dependencies = [
    "click>=8.0",
    "requests",
]
"""

PACKAGE_JSON_REACT = """\
{
  "name": "react-demo",
  "version": "0.1.0",
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
"""

PACKAGE_JSON_EXPRESS = """\
{
  "name": "node-api",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.0"
  }
}
"""


# ---------------------------------------------------------------------------
# Public API contract
# ---------------------------------------------------------------------------

def test_detect_stack_returns_required_keys():
    """Result always carries the documented keys, even on an empty repo."""
    tmp = _make_repo({})
    result = detect_stack(tmp)
    for key in ("language", "package_manager", "frameworks",
                "has_ui", "has_api_surface", "signals"):
        assert key in result, f"missing key: {key}"
    assert "files_seen" in result["signals"]
    assert "deps_seen" in result["signals"]


def test_detect_stack_never_raises_on_missing_root():
    """Vanishingly bad input collapses to language=unknown rather than raising."""
    bogus = Path(tempfile.gettempdir()) / "wg-stack-does-not-exist-xyz123"
    if bogus.exists():
        bogus.rmdir()
    result = detect_stack(bogus)
    assert result["language"] == "unknown"
    assert result["frameworks"] == []
    assert result["has_ui"] is False
    assert result["has_api_surface"] is False


# ---------------------------------------------------------------------------
# Per-stack detection
# ---------------------------------------------------------------------------

def test_python_cli_with_click_detected():
    """pyproject.toml + click in deps -> language=python, framework=click, no UI/API."""
    tmp = _make_repo({"pyproject.toml": PYPROJECT_CLICK})
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert result["package_manager"] == "pip"  # no uv.lock
    assert "click" in result["frameworks"]
    assert result["has_ui"] is False
    assert result["has_api_surface"] is False


def test_python_with_uv_lock_uses_uv_package_manager():
    """uv.lock present -> package_manager=uv (instead of pip)."""
    tmp = _make_repo({
        "pyproject.toml": PYPROJECT_CLICK,
        "uv.lock": "# uv lockfile placeholder\n",
    })
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert result["package_manager"] == "uv"


def test_web_react_typescript_detected():
    """package.json with react + tsconfig.json + .tsx file -> ts + has_ui."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_REACT,
        "tsconfig.json": "{}",
        "src/App.tsx": "export const App = () => null;\n",
    })
    result = detect_stack(tmp)
    assert result["language"] == "typescript"
    assert result["package_manager"] == "npm"  # no pnpm/yarn lock
    assert "react" in result["frameworks"]
    assert result["has_ui"] is True
    assert result["has_api_surface"] is False


def test_node_express_api_detected():
    """package.json with express -> has_api_surface=True."""
    tmp = _make_repo({"package.json": PACKAGE_JSON_EXPRESS})
    result = detect_stack(tmp)
    assert result["language"] == "javascript"  # no tsconfig.json
    assert result["package_manager"] == "npm"
    assert "express" in result["frameworks"]
    assert result["has_api_surface"] is True
    assert result["has_ui"] is False


def test_pnpm_lockfile_picked_over_yarn_and_npm():
    """pnpm-lock.yaml -> package_manager=pnpm."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_REACT,
        "tsconfig.json": "{}",
        "pnpm-lock.yaml": "lockfileVersion: '6.0'\n",
    })
    result = detect_stack(tmp)
    assert result["package_manager"] == "pnpm"


def test_yarn_lockfile_picked_when_no_pnpm_lock():
    """yarn.lock -> package_manager=yarn."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_EXPRESS,
        "yarn.lock": "# yarn lockfile v1\n",
    })
    result = detect_stack(tmp)
    assert result["package_manager"] == "yarn"


def test_go_mod_detected():
    """go.mod -> language=go, package_manager=go-mod."""
    tmp = _make_repo({"go.mod": "module example.com/demo\ngo 1.21\n"})
    result = detect_stack(tmp)
    assert result["language"] == "go"
    assert result["package_manager"] == "go-mod"


def test_cargo_toml_detected():
    """Cargo.toml -> language=rust, package_manager=cargo."""
    tmp = _make_repo({"Cargo.toml": "[package]\nname = 'demo'\nversion = '0.1.0'\n"})
    result = detect_stack(tmp)
    assert result["language"] == "rust"
    assert result["package_manager"] == "cargo"


def test_pom_xml_detected_as_java_maven():
    """pom.xml -> language=java, package_manager=maven."""
    tmp = _make_repo({"pom.xml": "<project></project>"})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "maven"


def test_build_gradle_detected_as_java():
    """build.gradle -> language=java, package_manager=gradle (#742 — distinguish from maven)."""
    tmp = _make_repo({"build.gradle": "plugins { id 'java' }\n"})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "gradle"


# ---------------------------------------------------------------------------
# Empty / corrupt inputs
# ---------------------------------------------------------------------------

def test_empty_repo_returns_unknown():
    """Empty repo -> language=unknown, all flags False, no frameworks."""
    tmp = _make_repo({})
    result = detect_stack(tmp)
    assert result["language"] == "unknown"
    assert result["package_manager"] == "unknown"
    assert result["frameworks"] == []
    assert result["has_ui"] is False
    assert result["has_api_surface"] is False


def test_corrupt_package_json_does_not_raise():
    """Malformed JSON yields language=javascript (file present) with empty deps, no exception."""
    tmp = _make_repo({"package.json": "{not valid json"})
    result = detect_stack(tmp)
    # language is still detected from the file's existence; deps come up empty.
    assert result["language"] == "javascript"
    assert result["frameworks"] == []
    assert result["has_ui"] is False
    assert result["has_api_surface"] is False


# ---------------------------------------------------------------------------
# Skipped directories
# ---------------------------------------------------------------------------

def test_node_modules_not_walked_for_ui_signal():
    """A .tsx file inside node_modules/ must not trip has_ui."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_EXPRESS,  # express -> has_api_surface, no UI
        "src/node_modules/some-pkg/Component.tsx": "export const x = 1;\n",
    })
    result = detect_stack(tmp)
    assert result["has_ui"] is False, (
        f"node_modules .tsx file should not be walked, got files_seen="
        f"{result['signals']['files_seen']}"
    )


def test_venv_not_walked_for_ui_signal():
    """A .tsx file inside .venv/ must not trip has_ui."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_EXPRESS,
        "src/.venv/lib/Component.tsx": "export const x = 1;\n",
    })
    result = detect_stack(tmp)
    assert result["has_ui"] is False


# ---------------------------------------------------------------------------
# Mixed-stack precedence — Python wins because pyproject.toml is canonical
# project-root, while package.json frequently belongs to a frontend subdir.
# ---------------------------------------------------------------------------

def test_python_wins_over_node_when_both_at_root():
    """pyproject.toml + package.json at the same root -> language=python."""
    tmp = _make_repo({
        "pyproject.toml": PYPROJECT_CLICK,
        "package.json": PACKAGE_JSON_REACT,
        "tsconfig.json": "{}",
    })
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert result["package_manager"] == "pip"
    # React deps under a sibling package.json are intentionally ignored at
    # this layer — the precedence rule is documented and deterministic.
    assert "react" not in result["frameworks"]


# ---------------------------------------------------------------------------
# Bare requirements.txt support
# ---------------------------------------------------------------------------

def test_requirements_txt_only_detected_as_python_pip():
    """A bare requirements.txt with click -> python+pip+click."""
    tmp = _make_repo({"requirements.txt": "click==8.1.7\nrequests\n"})
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert result["package_manager"] == "pip"
    assert "click" in result["frameworks"]


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------

def test_max_scan_depth_is_a_named_constant():
    """No magic value: scan depth is a module-level named constant (R3)."""
    assert isinstance(_stack_signals.MAX_SCAN_DEPTH, int)
    assert _stack_signals.MAX_SCAN_DEPTH >= 1


def test_skip_dir_names_includes_critical_vendors():
    """SKIP_DIR_NAMES must always include node_modules, venv, .venv, .git."""
    skip = _stack_signals.SKIP_DIR_NAMES
    for name in ("node_modules", "venv", ".venv", ".git"):
        assert name in skip, f"{name!r} missing from SKIP_DIR_NAMES"


# ---------------------------------------------------------------------------
# Integration with factor_questionnaire — the rubric absorbs stack signals
# ---------------------------------------------------------------------------

from crew.factor_questionnaire import (  # noqa: E402
    score_all,
    _apply_stack_adjustments,
    MAX_BAND,
)


def test_apply_stack_adjustments_bumps_user_facing_impact_when_has_ui():
    """has_ui=True -> user_facing_impact moves one band toward higher risk."""
    base = score_all({})  # all factors HIGH (safest)
    assert base["user_facing_impact"]["reading"] == "HIGH"
    detected = {"has_ui": True, "has_api_surface": False}
    adjusted, audit = _apply_stack_adjustments(base, detected)
    assert adjusted["user_facing_impact"]["reading"] == "MEDIUM"
    assert any(
        e["factor"] == "user_facing_impact" and e["reason"] == "stack:has_ui"
        for e in audit
    )


def test_apply_stack_adjustments_bumps_blast_radius_when_api_surface():
    """has_api_surface=True -> blast_radius moves one band toward higher risk."""
    base = score_all({})
    detected = {"has_ui": False, "has_api_surface": True}
    adjusted, audit = _apply_stack_adjustments(base, detected)
    assert adjusted["blast_radius"]["reading"] == "MEDIUM"
    assert any(e["reason"] == "stack:has_api_surface" for e in audit)


def test_apply_stack_adjustments_caps_at_max_band():
    """LOW reading stays LOW even with the bump rule active (cap at MAX_BAND)."""
    base = score_all({})
    # Manually push user_facing_impact to LOW to test saturation.
    base["user_facing_impact"]["reading"] = "LOW"
    base["user_facing_impact"]["risk_level"] = "high_risk"
    detected = {"has_ui": True, "has_api_surface": False}
    adjusted, audit = _apply_stack_adjustments(base, detected)
    assert adjusted["user_facing_impact"]["reading"] == MAX_BAND
    capped = [e for e in audit if e["factor"] == "user_facing_impact"]
    assert capped and capped[0]["capped"] is True


def test_apply_stack_adjustments_no_op_when_detected_stack_none():
    """No projection -> no adjustment, empty audit."""
    base = score_all({})
    adjusted, audit = _apply_stack_adjustments(base, None)
    assert adjusted == base
    assert audit == []


def test_apply_stack_adjustments_does_not_mutate_input():
    """Input dict is never mutated (defensive copy)."""
    base = score_all({})
    snapshot_reading = base["user_facing_impact"]["reading"]
    _apply_stack_adjustments(base, {"has_ui": True, "has_api_surface": True})
    assert base["user_facing_impact"]["reading"] == snapshot_reading


# ---------------------------------------------------------------------------
# archetype_detect integration — the additive detected_stack field
# ---------------------------------------------------------------------------

from crew.archetype_detect import detect_archetype  # noqa: E402


def test_archetype_detect_includes_detected_stack_field():
    """detect_archetype result carries detected_stack as an additive projection."""
    tmp = _make_repo({
        "package.json": PACKAGE_JSON_REACT,
        "tsconfig.json": "{}",
        "src/App.tsx": "export const App = () => null;\n",
    })
    result = detect_archetype({"files": ["src/App.tsx", "package.json"], "project_dir": str(tmp)})
    assert "detected_stack" in result
    assert result["detected_stack"]["language"] == "typescript"
    assert result["detected_stack"]["has_ui"] is True


# ---------------------------------------------------------------------------
# #742 regression — TOML headers with trailing comments
# ---------------------------------------------------------------------------

def test_pyproject_with_trailing_comment_on_project_header_still_detects_deps():
    """`[project] # comment` is valid TOML and must not break dep extraction (#742)."""
    pyproject = """\
[project] # metadata table
name = "demo-cli"
version = "0.1.0"
dependencies = [
    "click>=8.0",
]
"""
    tmp = _make_repo({"pyproject.toml": pyproject})
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert "click" in result["frameworks"], (
        f"trailing comment broke header match; deps_seen={result['signals']['deps_seen']}"
    )


def test_pyproject_optional_dependencies_with_trailing_comment_still_detects():
    """`[project.optional-dependencies] # comment` must not break dep extraction."""
    pyproject = """\
[project]
name = "demo"
version = "0.1.0"
dependencies = []

[project.optional-dependencies] # extras tables
test = ["click"]
"""
    tmp = _make_repo({"pyproject.toml": pyproject})
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert "click" in result["frameworks"]


def test_poetry_table_with_trailing_comment_still_detects_deps():
    """`[tool.poetry.dependencies] # comment` must not break the poetry parser."""
    pyproject = """\
[tool.poetry]
name = "demo"
version = "0.1.0"

[tool.poetry.dependencies] # poetry deps
python = "^3.11"
click = "^8.0"
"""
    tmp = _make_repo({"pyproject.toml": pyproject})
    result = detect_stack(tmp)
    assert result["language"] == "python"
    assert "click" in result["frameworks"]


# ---------------------------------------------------------------------------
# #742 regression — Go framework parsing
# ---------------------------------------------------------------------------

GO_MOD_GIN_SINGLE = """\
module example.com/demo

go 1.21

require github.com/gin-gonic/gin v1.9.1
"""

GO_MOD_MULTI_FRAMEWORKS = """\
module example.com/demo

go 1.21

require (
\tgithub.com/labstack/echo/v4 v4.11.4
\tgithub.com/gofiber/fiber/v2 v2.50.0
\tgithub.com/gorilla/mux v1.8.1 // indirect
\tgithub.com/go-chi/chi/v5 v5.0.10
)
"""


def test_go_mod_gin_single_line_require_detected():
    """Single-line `require github.com/gin-gonic/gin v1.x` -> gin in frameworks (#742)."""
    tmp = _make_repo({"go.mod": GO_MOD_GIN_SINGLE})
    result = detect_stack(tmp)
    assert result["language"] == "go"
    assert "gin" in result["frameworks"], (
        f"gin not detected; deps_seen={result['signals']['deps_seen']}"
    )
    assert result["has_api_surface"] is True


def test_go_mod_multi_framework_require_block_detected():
    """`require (...)` block with echo/fiber/mux/chi -> all frameworks detected (#742)."""
    tmp = _make_repo({"go.mod": GO_MOD_MULTI_FRAMEWORKS})
    result = detect_stack(tmp)
    assert result["language"] == "go"
    for fw in ("echo", "fiber", "mux", "chi"):
        assert fw in result["frameworks"], (
            f"{fw} missing; got {result['frameworks']}"
        )
    assert result["has_api_surface"] is True


def test_go_mod_without_frameworks_has_api_surface_false():
    """Plain go.mod with no recognised web framework -> has_api_surface False."""
    tmp = _make_repo({"go.mod": "module example.com/lib\ngo 1.21\n"})
    result = detect_stack(tmp)
    assert result["language"] == "go"
    assert result["frameworks"] == []
    assert result["has_api_surface"] is False


def test_go_mod_malformed_returns_unknown_frameworks_no_raise():
    """A garbled go.mod must not raise — frameworks list comes back empty."""
    tmp = _make_repo({"go.mod": "this is not a valid go.mod file at all"})
    result = detect_stack(tmp)
    # Language still pegs as 'go' because the file exists; frameworks empty.
    assert result["language"] == "go"
    assert result["frameworks"] == []


# ---------------------------------------------------------------------------
# #742 regression — Rust framework parsing
# ---------------------------------------------------------------------------

CARGO_TOML_AXUM = """\
[package]
name = "demo"
version = "0.1.0"

[dependencies]
axum = "0.7"
serde = { version = "1.0", features = ["derive"] }
"""

CARGO_TOML_MULTI_WEB = """\
[package]
name = "demo"
version = "0.1.0"

[dependencies] # web stack
actix-web = "4.4"
rocket = "0.5"
warp = "0.3"
tide = "0.16"
"""


def test_cargo_toml_axum_detected_as_api_framework():
    """Cargo.toml [dependencies] with axum -> axum in frameworks + has_api_surface (#742)."""
    tmp = _make_repo({"Cargo.toml": CARGO_TOML_AXUM})
    result = detect_stack(tmp)
    assert result["language"] == "rust"
    assert "axum" in result["frameworks"]
    assert result["has_api_surface"] is True


def test_cargo_toml_multi_web_frameworks_all_detected():
    """actix-web/rocket/warp/tide all surface, even with trailing comment on header (#742)."""
    tmp = _make_repo({"Cargo.toml": CARGO_TOML_MULTI_WEB})
    result = detect_stack(tmp)
    assert result["language"] == "rust"
    for fw in ("actix-web", "rocket", "warp", "tide"):
        assert fw in result["frameworks"], (
            f"{fw} missing; got {result['frameworks']}"
        )
    assert result["has_api_surface"] is True


def test_cargo_toml_malformed_returns_no_frameworks_no_raise():
    """Garbled Cargo.toml must not raise — language stays rust, frameworks empty."""
    tmp = _make_repo({"Cargo.toml": "completely{bogus]content"})
    result = detect_stack(tmp)
    assert result["language"] == "rust"
    assert result["frameworks"] == []


# ---------------------------------------------------------------------------
# #742 regression — Java/Spring framework parsing
# ---------------------------------------------------------------------------

POM_XML_SPRING_BOOT = """\
<?xml version="1.0" encoding="UTF-8"?>
<project>
  <groupId>com.example</groupId>
  <artifactId>demo</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
"""

BUILD_GRADLE_SPRING_BOOT = """\
plugins {
    id 'org.springframework.boot' version '3.2.0'
    id 'io.spring.dependency-management' version '1.1.4'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
}
"""

BUILD_GRADLE_KTS_SPRING_BOOT = """\
plugins {
    id("org.springframework.boot") version "3.2.0"
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
}
"""


def test_pom_xml_with_spring_boot_starter_detected():
    """pom.xml with spring-boot-starter-web -> spring frameworks + has_api_surface (#742)."""
    tmp = _make_repo({"pom.xml": POM_XML_SPRING_BOOT})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "maven"
    assert "spring" in result["frameworks"], (
        f"spring missing; got {result['frameworks']}"
    )
    assert "spring-boot" in result["frameworks"]
    assert result["has_api_surface"] is True


def test_build_gradle_groovy_with_spring_boot_detected():
    """build.gradle with spring-boot plugin -> spring frameworks + has_api_surface (#742)."""
    tmp = _make_repo({"build.gradle": BUILD_GRADLE_SPRING_BOOT})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "gradle"
    assert "spring" in result["frameworks"]
    assert "spring-boot" in result["frameworks"]
    assert result["has_api_surface"] is True


def test_build_gradle_kts_with_spring_boot_detected():
    """build.gradle.kts (Kotlin DSL) variants must also surface spring frameworks (#742)."""
    tmp = _make_repo({"build.gradle.kts": BUILD_GRADLE_KTS_SPRING_BOOT})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "gradle"
    assert "spring" in result["frameworks"]
    assert "spring-boot" in result["frameworks"]
    assert result["has_api_surface"] is True


def test_pom_xml_malformed_returns_no_frameworks_no_raise():
    """Garbled pom.xml must not raise — language stays java, frameworks empty."""
    tmp = _make_repo({"pom.xml": "<<not valid xml>>"})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["frameworks"] == []


def test_pom_xml_takes_precedence_over_gradle_for_package_manager():
    """When both pom.xml and build.gradle present -> package_manager=maven (#742)."""
    tmp = _make_repo({
        "pom.xml": "<project></project>",
        "build.gradle": "plugins { id 'java' }",
    })
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "maven"


def test_build_gradle_kts_only_reports_gradle_package_manager():
    """build.gradle.kts alone -> package_manager=gradle (#742)."""
    tmp = _make_repo({"build.gradle.kts": "plugins { kotlin(\"jvm\") version \"1.9.0\" }"})
    result = detect_stack(tmp)
    assert result["language"] == "java"
    assert result["package_manager"] == "gradle"


def test_archetype_detect_detected_stack_safe_on_bad_input():
    """Even when archetype detection raises, detected_stack is present + correctly shaped.

    The exact `language` value depends on what the fallback root resolves to
    (None -> current working dir), so assert structural correctness rather
    than a specific language value. The point is the field is *always there*
    and is *always safe to read*.
    """
    result = detect_archetype(None)  # type: ignore[arg-type]
    assert "detected_stack" in result
    stack = result["detected_stack"]
    for key in ("language", "package_manager", "frameworks",
                "has_ui", "has_api_surface", "signals"):
        assert key in stack, f"missing key in fallback detected_stack: {key}"
    assert isinstance(stack["frameworks"], list)
    assert isinstance(stack["has_ui"], bool)
    assert isinstance(stack["has_api_surface"], bool)


# ---------------------------------------------------------------------------
# #742 regression — depth-cap must short-circuit *every* recursion frame
# ---------------------------------------------------------------------------

def test_walk_for_extensions_cap_short_circuits_ancestor_frames(monkeypatch):
    """Hitting MAX_MATCHES must stop ancestor recursion frames, not just the
    current one (#742, Copilot finding 1).

    Build a deep src/ tree where ``MAX_MATCHES`` matching .tsx files all sit
    under the *first* sibling directory we'd descend into. Then assert we
    never visit the second sibling — the cap unwinds the full stack via the
    sentinel exception. Without the fix, ancestor frames keep iterating.
    """
    tmp = _make_repo({"package.json": PACKAGE_JSON_REACT, "tsconfig.json": "{}"})

    # Sibling A: stuff MAX_MATCHES + 3 tsx files at one depth so we trip the cap
    # immediately while still inside Sibling A.
    src_a = tmp / "src" / "a"
    src_a.mkdir(parents=True)
    cap = _stack_signals.MAX_MATCHES
    for i in range(cap + 3):
        (src_a / f"Comp{i}.tsx").write_text("export const x = 1;\n", encoding="utf-8")

    # Sibling B: place a unique sentinel file. If the cap fix works the walker
    # never sees this directory.
    src_b = tmp / "src" / "b"
    src_b.mkdir(parents=True)
    sentinel = src_b / "ShouldNeverBeVisited.tsx"
    sentinel.write_text("export const y = 2;\n", encoding="utf-8")

    # Track every directory iterdir() visits. If ancestor frames truly unwind,
    # src/b should never be iterated.
    visited: list = []
    real_iterdir = Path.iterdir

    def tracked_iterdir(self):  # type: ignore[no-untyped-def]
        visited.append(str(self.resolve()))
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", tracked_iterdir)

    matches = _stack_signals._walk_for_extensions(
        tmp / "src",
        _stack_signals.UI_FILE_SUFFIXES,
        tmp,
    )

    # Cap honored.
    assert len(matches) == cap, (
        f"cap not honoured; got {len(matches)} matches, expected {cap}"
    )

    # Sibling B was NOT walked — proves the sentinel exception unwinds
    # ancestor frames instead of letting them iterate further.
    sib_b_resolved = str(src_b.resolve())
    assert sib_b_resolved not in visited, (
        f"ancestor frame kept walking after cap; visited sibling B: "
        f"{sib_b_resolved} in {visited}"
    )


def test_walk_for_extensions_returns_at_most_max_matches():
    """Total returned paths never exceed MAX_MATCHES (#742)."""
    tmp = _make_repo({"package.json": PACKAGE_JSON_EXPRESS})
    src = tmp / "src"
    src.mkdir(parents=True)
    # 20 tsx files spread across siblings.
    for d in range(4):
        sib = src / f"dir{d}"
        sib.mkdir()
        for i in range(5):
            (sib / f"x{i}.tsx").write_text("export const z = 0;\n", encoding="utf-8")

    matches = _stack_signals._walk_for_extensions(
        src, _stack_signals.UI_FILE_SUFFIXES, tmp,
    )
    assert len(matches) <= _stack_signals.MAX_MATCHES


def test_max_matches_constant_exposed():
    """MAX_MATCHES must be a module-level named constant for the cap (R3 + #742)."""
    assert hasattr(_stack_signals, "MAX_MATCHES")
    assert isinstance(_stack_signals.MAX_MATCHES, int)
    assert _stack_signals.MAX_MATCHES >= 1


# ---------------------------------------------------------------------------
# #742 regression — _safe_detect_stack refuses to fall back to cwd
# ---------------------------------------------------------------------------

def test_safe_detect_stack_returns_unknown_when_project_dir_is_none():
    """project_dir=None must NOT silently scan the current working directory
    (#742, Copilot finding 3) — that would surface an unrelated repo's stack.
    """
    from crew.archetype_detect import _safe_detect_stack

    result = _safe_detect_stack(None)
    assert result["language"] == "unknown", (
        f"None project_dir leaked cwd stack info; got language="
        f"{result['language']}"
    )
    assert result["package_manager"] == "unknown"
    assert result["frameworks"] == []
    assert result["has_ui"] is False
    assert result["has_api_surface"] is False
    # Reason marker must be in signals so debugging is possible.
    files_seen = result["signals"]["files_seen"]
    assert any("project_dir not provided" in s for s in files_seen), (
        f"reason marker missing; files_seen={files_seen}"
    )


def test_safe_detect_stack_with_explicit_dir_still_works():
    """Passing an explicit project_dir to _safe_detect_stack must still scan it."""
    from crew.archetype_detect import _safe_detect_stack

    tmp = _make_repo({"pyproject.toml": PYPROJECT_CLICK})
    result = _safe_detect_stack(tmp)
    assert result["language"] == "python"
    assert "click" in result["frameworks"]
