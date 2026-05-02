#!/usr/bin/env python3
"""_stack_signals.py — Stack-shape projection for the 9-factor rubric (#723).

Detects language, package manager, frameworks, and surface flags (UI / API)
from a project's manifest files. The result is a *projection* — read fresh
on every call from disk. Never persisted, never cached, never written to a
config file. Stack identity is not state; it is a derivation of the files
already in the repo.

Used by:
  - scripts/crew/factor_questionnaire.py — bumps user_facing_impact when
    has_ui is True, bumps blast_radius when has_api_surface is True. Caps
    each adjustment at +1 band (HIGH -> MEDIUM -> LOW).
  - scripts/crew/archetype_detect.py — adds detected_stack to the result so
    callers can name the stack back to the user.
  - smaht briefing surface — names the detected stack in plain English.

Public API:
    detect_stack(repo_root: Path) -> dict

ETHOS alignment:
  - Project shape determines ceremony — the rubric absorbs the shape, not
    a hand-curated preset list.
  - No new state surface — no .wicked-garden/config.yml, no presets/ dir.
  - Fail-open — language=unknown on any error, never raises.

Stdlib-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

# ---------------------------------------------------------------------------
# Constants — no magic values (R3)
# ---------------------------------------------------------------------------

# Cap directory recursion depth to keep the scan cheap on large repos.
# 3 levels covers project root + immediate package dirs (e.g. src/, packages/x/).
MAX_SCAN_DEPTH = 3

# Directories we never descend into — vendored or ignored content has no
# bearing on the project's own stack identity.
SKIP_DIR_NAMES: frozenset[str] = frozenset({
    "node_modules",
    "venv",
    ".venv",
    ".git",
    "__pycache__",
    ".tox",
    ".pytest_cache",
    "target",
    "dist",
    "build",
    ".next",
    ".nuxt",
})

# Frameworks recognised across ecosystems. Keep this list small and
# focused — the value is in correctly identifying *that* a framework is
# present, not in cataloguing every npm package.
KNOWN_FRAMEWORKS: frozenset[str] = frozenset({
    # JS/TS UI
    "react", "react-dom", "vue", "svelte", "@angular/core", "next", "nuxt",
    "remix", "solid-js", "preact",
    # JS/TS API
    "express", "fastify", "koa", "hapi", "@nestjs/core", "@hono/node-server", "hono",
    # Python UI / API
    "fastapi", "flask", "django", "starlette", "quart", "sanic", "tornado",
    # Python CLI
    "click", "typer", "argparse-manpage", "rich-cli", "fire",
    # Go web
    "gin", "echo", "fiber", "chi", "mux",
    # Rust web
    "actix-web", "axum", "rocket", "warp", "tide",
    # Java web
    "spring", "spring-boot", "spring-web",
})

UI_FRAMEWORKS: frozenset[str] = frozenset({
    "react", "react-dom", "vue", "svelte", "@angular/core", "next", "nuxt",
    "remix", "solid-js", "preact",
})

API_FRAMEWORKS: frozenset[str] = frozenset({
    "express", "fastify", "koa", "hapi", "@nestjs/core", "@hono/node-server", "hono",
    "fastapi", "flask", "django", "starlette", "quart", "sanic", "tornado",
    "gin", "echo", "fiber", "chi", "mux",
    "actix-web", "axum", "rocket", "warp", "tide",
    "spring", "spring-boot", "spring-web",
})

# Go module-path -> framework key mapping. Defensive parsing extracts
# `module/path vX.Y.Z` lines from go.mod's require block(s).
# Source: https://pkg.go.dev/std (web framework idioms).
GO_MODULE_FRAMEWORKS: Dict[str, str] = {
    "github.com/gin-gonic/gin": "gin",
    "github.com/labstack/echo": "echo",
    "github.com/labstack/echo/v4": "echo",
    "github.com/gofiber/fiber": "fiber",
    "github.com/gofiber/fiber/v2": "fiber",
    "github.com/gofiber/fiber/v3": "fiber",
    "github.com/gorilla/mux": "mux",
    "github.com/go-chi/chi": "chi",
    "github.com/go-chi/chi/v5": "chi",
}

# Rust crate -> framework key mapping for [dependencies] keys in Cargo.toml.
RUST_CRATE_FRAMEWORKS: Dict[str, str] = {
    "actix-web": "actix-web",
    "rocket": "rocket",
    "axum": "axum",
    "warp": "warp",
    "tide": "tide",
}

UI_FILE_SUFFIXES: frozenset[str] = frozenset({".tsx", ".jsx"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_stack(repo_root: Path) -> Dict[str, Any]:
    """Return a stack-shape projection for repo_root.

    Args:
        repo_root: Path to the project's root directory.

    Returns:
        {
            "language":        "python" | "typescript" | "javascript" |
                                "go" | "rust" | "java" | "unknown",
            "package_manager": "uv" | "pip" | "npm" | "pnpm" | "yarn" |
                                "go-mod" | "cargo" | "maven" | "unknown",
            "frameworks":      sorted list[str] of detected framework keys,
            "has_ui":          bool — UI framework present OR .tsx/.jsx in src/,
            "has_api_surface": bool — API framework present in deps,
            "signals": {
                "files_seen": list[str] (relative paths, capped),
                "deps_seen":  list[str] (raw dep keys observed),
            },
        }

    Never raises — all errors collapse to language=unknown with empty signals.
    """
    try:
        return _detect_stack_inner(Path(repo_root))
    except Exception as exc:  # R4: surface the failure mode in signals
        return _unknown_result(error=str(exc))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _unknown_result(error: str | None = None) -> Dict[str, Any]:
    signals: Dict[str, List[str]] = {"files_seen": [], "deps_seen": []}
    if error:
        signals["files_seen"].append(f"error: {error}")
    return {
        "language": "unknown",
        "package_manager": "unknown",
        "frameworks": [],
        "has_ui": False,
        "has_api_surface": False,
        "signals": signals,
    }


def _detect_stack_inner(repo_root: Path) -> Dict[str, Any]:
    if not repo_root.exists() or not repo_root.is_dir():
        return _unknown_result(error="repo_root does not exist or is not a directory")

    files_seen: List[str] = []
    deps_seen: Set[str] = set()
    frameworks: Set[str] = set()

    # Probe manifest files at the project root.
    pyproject = repo_root / "pyproject.toml"
    requirements = repo_root / "requirements.txt"
    package_json = repo_root / "package.json"
    tsconfig = repo_root / "tsconfig.json"
    go_mod = repo_root / "go.mod"
    cargo_toml = repo_root / "Cargo.toml"
    pom_xml = repo_root / "pom.xml"
    build_gradle_groovy = repo_root / "build.gradle"
    build_gradle_kts = repo_root / "build.gradle.kts"

    # Lockfiles influence package_manager selection.
    uv_lock = repo_root / "uv.lock"
    pnpm_lock = repo_root / "pnpm-lock.yaml"
    yarn_lock = repo_root / "yarn.lock"
    package_lock = repo_root / "package-lock.json"

    # ---- Language + package manager precedence ----
    # Python wins over JS/TS when both are present at the root, because
    # pyproject.toml is always project-root in Python convention while
    # package.json may belong to a frontend subdir of a Python project.
    language = "unknown"
    package_manager = "unknown"

    if pyproject.exists():
        language = "python"
        package_manager = "uv" if uv_lock.exists() else "pip"
        files_seen.append("pyproject.toml")
        if uv_lock.exists():
            files_seen.append("uv.lock")
        py_deps = _read_python_deps(pyproject, requirements)
        deps_seen.update(py_deps)
    elif package_json.exists():
        files_seen.append("package.json")
        if tsconfig.exists():
            language = "typescript"
            files_seen.append("tsconfig.json")
        else:
            language = "javascript"
        if pnpm_lock.exists():
            package_manager = "pnpm"
            files_seen.append("pnpm-lock.yaml")
        elif yarn_lock.exists():
            package_manager = "yarn"
            files_seen.append("yarn.lock")
        else:
            package_manager = "npm"
            if package_lock.exists():
                files_seen.append("package-lock.json")
        js_deps = _read_node_deps(package_json)
        deps_seen.update(js_deps)
    elif go_mod.exists():
        language = "go"
        package_manager = "go-mod"
        files_seen.append("go.mod")
        deps_seen.update(_read_go_deps(go_mod))
    elif cargo_toml.exists():
        language = "rust"
        package_manager = "cargo"
        files_seen.append("Cargo.toml")
        deps_seen.update(_read_rust_deps(cargo_toml))
    elif pom_xml.exists() or build_gradle_groovy.exists() or build_gradle_kts.exists():
        language = "java"
        # Maven and Gradle are distinct toolchains — pom.xml drives Maven,
        # build.gradle{,.kts} drives Gradle. When only Gradle files exist,
        # report `gradle`; pom.xml takes precedence when both are present
        # (a multi-module project may carry build.gradle wrappers).
        if pom_xml.exists():
            package_manager = "maven"
        else:
            package_manager = "gradle"
        if pom_xml.exists():
            files_seen.append("pom.xml")
            deps_seen.update(_read_java_pom_deps(pom_xml))
        if build_gradle_groovy.exists():
            files_seen.append("build.gradle")
            deps_seen.update(_read_java_gradle_deps(build_gradle_groovy))
        if build_gradle_kts.exists():
            files_seen.append("build.gradle.kts")
            deps_seen.update(_read_java_gradle_deps(build_gradle_kts))
    elif requirements.exists():
        # Bare requirements.txt without pyproject.toml → still python+pip.
        language = "python"
        package_manager = "pip"
        files_seen.append("requirements.txt")
        deps_seen.update(_read_python_deps(None, requirements))

    # ---- Frameworks ----
    for dep in deps_seen:
        key = dep.lower().strip()
        if key in KNOWN_FRAMEWORKS:
            frameworks.add(key)

    # ---- has_ui ----
    has_ui = any(f in UI_FRAMEWORKS for f in frameworks)
    if not has_ui:
        # Walk src/ for .tsx/.jsx files (cheap — capped depth, skip vendors).
        src_dir = repo_root / "src"
        if src_dir.is_dir():
            for ui_file in _walk_for_extensions(src_dir, UI_FILE_SUFFIXES, repo_root):
                has_ui = True
                files_seen.append(ui_file)
                break  # one match is enough

    # ---- has_api_surface ----
    has_api_surface = any(f in API_FRAMEWORKS for f in frameworks)

    return {
        "language": language,
        "package_manager": package_manager,
        "frameworks": sorted(frameworks),
        "has_ui": has_ui,
        "has_api_surface": has_api_surface,
        "signals": {
            "files_seen": files_seen[:20],  # cap for sanity
            "deps_seen": sorted(deps_seen)[:50],
        },
    }


def _read_python_deps(pyproject: Path | None, requirements: Path) -> Set[str]:
    """Extract dependency names from pyproject.toml + requirements.txt.

    Best-effort regex parser — we want package *names* not full pinned
    specs, and the stdlib does not ship a TOML parser before 3.11. Falls
    back gracefully on anything it can't read.
    """
    deps: Set[str] = set()

    if pyproject is not None and pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""

        # [project.dependencies] = ["click>=8.0", "requests"]
        # [tool.poetry.dependencies] table form: click = "^8.0"
        deps.update(_extract_pep621_deps(text))
        deps.update(_extract_poetry_deps(text))

    if requirements.exists():
        try:
            for raw in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                # name[extras]==1.0 → name
                m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
                if m:
                    deps.add(m.group(1).lower())
        except OSError:
            pass

    return deps


def _extract_pep621_deps(toml_text: str) -> Set[str]:
    """Best-effort PEP 621 [project] dependencies extractor.

    Tolerates trailing comments on the table header — `[project] # metadata`
    is valid TOML and must not break detection.
    """
    out: Set[str] = set()

    # Find the [project] table body and look for dependencies = [ ... ].
    # `(?:#[^\n]*)?` allows an optional trailing comment on the header line.
    proj = re.search(
        r"^\[project\]\s*(?:#[^\n]*)?$(.*?)(?=^\[|\Z)",
        toml_text,
        re.DOTALL | re.MULTILINE,
    )
    if proj:
        body = proj.group(1)
        deps_block = re.search(
            r"dependencies\s*=\s*\[(.*?)\]",
            body,
            re.DOTALL,
        )
        if deps_block:
            for raw in re.findall(r'"([^"]+)"|\'([^\']+)\'', deps_block.group(1)):
                spec = (raw[0] or raw[1]).strip()
                m = re.match(r"^([A-Za-z0-9_.\-]+)", spec)
                if m:
                    out.add(m.group(1).lower())

    # Optional dependencies: [project.optional-dependencies] table.
    for tbl in re.finditer(
        r"^\[project\.optional-dependencies\]\s*(?:#[^\n]*)?$(.*?)(?=^\[|\Z)",
        toml_text,
        re.DOTALL | re.MULTILINE,
    ):
        for arr in re.finditer(r"\[(.*?)\]", tbl.group(1), re.DOTALL):
            for raw in re.findall(r'"([^"]+)"|\'([^\']+)\'', arr.group(1)):
                spec = (raw[0] or raw[1]).strip()
                m = re.match(r"^([A-Za-z0-9_.\-]+)", spec)
                if m:
                    out.add(m.group(1).lower())

    return out


def _extract_poetry_deps(toml_text: str) -> Set[str]:
    """Best-effort Poetry [tool.poetry.dependencies] extractor.

    Tolerates trailing comments on the table header.
    """
    out: Set[str] = set()
    poetry = re.search(
        r"^\[tool\.poetry\.dependencies\]\s*(?:#[^\n]*)?$(.*?)(?=^\[|\Z)",
        toml_text,
        re.DOTALL | re.MULTILINE,
    )
    if not poetry:
        return out
    for line in poetry.group(1).splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key and key.lower() != "python":
            out.add(key.lower())
    return out


def _read_node_deps(package_json: Path) -> Set[str]:
    """Extract dependency keys from package.json (deps + devDeps + peerDeps)."""
    deps: Set[str] = set()
    try:
        text = package_json.read_text(encoding="utf-8", errors="replace")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError, ValueError):
        return deps  # corrupt JSON → no deps detected, language stays detected

    if not isinstance(data, dict):
        return deps

    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            for name in section.keys():
                if isinstance(name, str):
                    deps.add(name.lower())

    return deps


def _read_go_deps(go_mod: Path) -> Set[str]:
    """Extract framework keys from a go.mod file's require block(s).

    Best-effort regex parser — defensively handles single-line `require x v0`
    statements and multi-line `require ( ... )` blocks. Returns the framework
    *key* (gin, echo, fiber, mux, chi) for any recognised module path.
    Malformed go.mod -> empty set, never raises.
    """
    deps: Set[str] = set()
    try:
        text = go_mod.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    # Collect every `module/path vX.Y.Z` line. Two forms:
    #   require github.com/foo/bar v1.2.3
    #   require (\n  github.com/foo/bar v1.2.3\n)
    # We don't try to be a full go.mod parser — we only need the path tokens.
    paths: Set[str] = set()

    # Single-line require statements.
    for m in re.finditer(
        r"^\s*require\s+([^\s\(]+)\s+v[\w\.\-]+",
        text,
        re.MULTILINE,
    ):
        paths.add(m.group(1).strip())

    # Multi-line require ( ... ) blocks — capture every non-comment line
    # that looks like `module/path vX.Y.Z`.
    for block in re.finditer(
        r"^\s*require\s*\((.*?)\)",
        text,
        re.DOTALL | re.MULTILINE,
    ):
        for line in block.group(1).splitlines():
            stripped = line.split("//", 1)[0].strip()
            if not stripped:
                continue
            m = re.match(r"^([^\s]+)\s+v[\w\.\-]+", stripped)
            if m:
                paths.add(m.group(1).strip())

    for path in paths:
        key = GO_MODULE_FRAMEWORKS.get(path)
        if key:
            deps.add(key)

    return deps


def _read_rust_deps(cargo_toml: Path) -> Set[str]:
    """Extract framework keys from Cargo.toml [dependencies] section.

    Best-effort: scans `[dependencies]` and `[dev-dependencies]` table
    bodies for `crate-name = ...` lines and matches against
    RUST_CRATE_FRAMEWORKS. Tolerates trailing comments on table headers.
    Malformed Cargo.toml -> empty set, never raises.
    """
    deps: Set[str] = set()
    try:
        text = cargo_toml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    for header in (r"\[dependencies\]", r"\[dev-dependencies\]"):
        for tbl in re.finditer(
            r"^" + header + r"\s*(?:#[^\n]*)?$(.*?)(?=^\[|\Z)",
            text,
            re.DOTALL | re.MULTILINE,
        ):
            for line in tbl.group(1).splitlines():
                stripped = line.split("#", 1)[0].strip()
                if not stripped or "=" not in stripped:
                    continue
                key = stripped.split("=", 1)[0].strip().strip('"').lower()
                framework = RUST_CRATE_FRAMEWORKS.get(key)
                if framework:
                    deps.add(framework)

    return deps


def _read_java_pom_deps(pom_xml: Path) -> Set[str]:
    """Detect Spring (Boot) usage from a Maven pom.xml.

    Best-effort: looks for any `<groupId>org.springframework...</groupId>`
    element. Returns {'spring'} when present, else empty.
    Malformed XML -> empty set, never raises.
    """
    deps: Set[str] = set()
    try:
        text = pom_xml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    # Generous Spring detection — matches Spring Boot, Spring Web,
    # spring-cloud-starter-*, etc. We only need to know "Spring is here".
    if re.search(r"<groupId>\s*org\.springframework", text):
        deps.add("spring")
    # Spring Boot has a distinct artifactId pattern worth surfacing too.
    if re.search(r"<artifactId>\s*spring-boot-starter-web", text):
        deps.add("spring-boot")

    return deps


def _read_java_gradle_deps(build_gradle: Path) -> Set[str]:
    """Detect Spring (Boot) usage from a build.gradle or build.gradle.kts.

    Best-effort: looks for `implementation 'org.springframework...'` style
    dependency declarations or the Spring Boot plugin id. Returns the
    framework keys ('spring', 'spring-boot') as detected. Malformed file ->
    empty set, never raises.
    """
    deps: Set[str] = set()
    try:
        text = build_gradle.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    # Match dependency strings like 'org.springframework.boot:spring-boot-starter-web:3.0.0'
    # in either single or double quotes (Groovy + Kotlin DSL both supported).
    if re.search(r"['\"]org\.springframework[^'\"]*['\"]", text):
        deps.add("spring")
    if re.search(r"spring-boot-starter-web", text):
        deps.add("spring-boot")
    # Gradle Spring Boot plugin id is also a strong signal.
    if re.search(r"id\s*[\(\s]['\"]org\.springframework\.boot['\"]", text):
        deps.add("spring-boot")
        deps.add("spring")

    return deps


def _walk_for_extensions(
    root: Path,
    suffixes: frozenset[str],
    repo_root: Path,
) -> List[str]:
    """Yield relative paths under root with matching suffixes, depth-capped.

    Returns at most a handful — callers usually break on first hit. Skips
    SKIP_DIR_NAMES so node_modules content cannot trip framework detection.
    """
    matches: List[str] = []
    root = root.resolve()
    repo_root = repo_root.resolve()

    def _walk(current: Path, depth: int) -> None:
        if depth > MAX_SCAN_DEPTH:
            return
        try:
            entries = list(current.iterdir())
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if name in SKIP_DIR_NAMES:
                continue
            if name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    _walk(entry, depth + 1)
                elif entry.is_file() and entry.suffix.lower() in suffixes:
                    try:
                        rel = str(entry.relative_to(repo_root)).replace("\\", "/")
                    except ValueError:
                        rel = entry.name
                    matches.append(rel)
                    if len(matches) >= 5:
                        return
            except OSError:
                continue

    _walk(root, depth=0)
    return matches


# ---------------------------------------------------------------------------
# CLI helper — useful for ad-hoc inspection and the scenario file
# ---------------------------------------------------------------------------

def _main(argv: List[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Print stack-shape projection for a project directory.",
    )
    parser.add_argument("repo_root", type=Path, help="Project root directory")
    args = parser.parse_args(argv)
    result = detect_stack(args.repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
