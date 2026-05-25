#!/usr/bin/env python3
"""Phase-0 detection probe — repo root -> bindings.json.

Falsification question: can ONE repo-agnostic detector infer a repo's
test-invocation, evidence sink, claims surface, and risk surfaces well
enough to drive an emitted enforcement lint, WITHOUT hand-correction,
across structurally different repos?

Every binding records {value, source, confidence} so the verdict can
distinguish "detected unaided" from "fell back to a proposed default".
Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DETECTED = "detected"          # inferred from a real repo signal
DEFAULT = "proposed-default"   # emitted convention; repo had none


def _exists(root: Path, *names: str) -> str | None:
    for n in names:
        if (root / n).exists():
            return n
    return None


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _pkg_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _detect_test_command(root: Path) -> dict:
    # node
    pkg = root / "package.json"
    if pkg.exists():
        data = _read_json(pkg)
        scripts = data.get("scripts", {}) or {}
        pm = _pkg_manager(root)
        monorepo = bool(data.get("workspaces")) or (root / "pnpm-workspace.yaml").exists()
        if scripts.get("test"):
            run = "test" if pm == "npm" else "test"
            cmd = f"{pm} {('run ' if pm=='npm' else '')}{run}".strip()
            # npm needs `npm test`; pnpm/yarn `pnpm test`
            cmd = f"{pm} test"
            return {"value": cmd, "source": DETECTED, "confidence": 0.9,
                    "ecosystem": "node", "monorepo": monorepo,
                    "declared_script": scripts["test"]}
        return {"value": f"{pm} test", "source": DEFAULT, "confidence": 0.3,
                "ecosystem": "node", "monorepo": monorepo,
                "note": "package.json has no scripts.test"}

    # rust
    if (root / "Cargo.toml").exists():
        return {"value": "cargo test", "source": DETECTED, "confidence": 0.9,
                "ecosystem": "rust"}

    # go
    if (root / "go.mod").exists():
        return {"value": "go test ./...", "source": DETECTED, "confidence": 0.9,
                "ecosystem": "go"}

    # python — the ambiguous case: Makefile test target vs pytest vs pyproject
    py_signals = []
    has_pyproject = (root / "pyproject.toml").exists()
    has_setup = (root / "setup.py").exists() or (root / "setup.cfg").exists()
    tests_dir = ("tests" if (root / "tests").is_dir()
                 else "test" if (root / "test").is_dir() else None)
    has_tests_dir = tests_dir is not None
    # Scope pytest to the tests dir when one exists. Bare `pytest` collects
    # from the repo root and trips over stray test-like files elsewhere in the
    # tree (a real failure mode found dogfooding the garden: scripts/**/test_*.py
    # with broken imports → exit 2). Scoped collection matches how repos
    # actually run their suite (`pytest tests/`).
    _pytest = "python3 -m pytest" + (f" {tests_dir}" if tests_dir else "")
    make = root / "Makefile"
    make_test = False
    if make.exists():
        try:
            make_test = bool(re.search(r"(?m)^test:", make.read_text()))
        except Exception:
            make_test = False
    pytest_cfg = False
    if has_pyproject:
        try:
            txt = (root / "pyproject.toml").read_text()
            pytest_cfg = "[tool.pytest" in txt
        except Exception:
            pass
    if (root / "pytest.ini").exists():
        pytest_cfg = True

    if has_pyproject or has_setup or has_tests_dir:
        # Priority: declared Makefile target (explicit author intent) >
        # ecosystem default pytest. Confidence drops when both exist
        # (genuine ambiguity the detector must flag, not silently pick).
        if make_test and (pytest_cfg or has_tests_dir):
            return {"value": _pytest, "source": DETECTED,
                    "confidence": 0.55, "ecosystem": "python",
                    "ambiguity": "Makefile `test:` target AND pytest config both present",
                    "alt": "make test"}
        if make_test:
            return {"value": "make test", "source": DETECTED, "confidence": 0.8,
                    "ecosystem": "python"}
        return {"value": _pytest, "source": DETECTED,
                "confidence": 0.8 if (pytest_cfg or has_tests_dir) else 0.5,
                "ecosystem": "python"}

    return {"value": None, "source": DEFAULT, "confidence": 0.0,
            "ecosystem": "unknown", "note": "no recognized test ecosystem"}


def _detect_evidence_sink(root: Path) -> dict:
    # existing convention?
    candidates = []
    for p in root.rglob("evidence"):
        if p.is_dir() and ".git" not in p.parts and "node_modules" not in p.parts:
            candidates.append(p.relative_to(root).as_posix())
            if len(candidates) >= 5:
                break
    if candidates:
        # pick the shallowest existing evidence dir
        candidates.sort(key=lambda s: s.count("/"))
        return {"value": candidates[0], "source": DETECTED, "confidence": 0.8,
                "others": candidates[1:]}
    for d in ("test-results", "coverage", "reports"):
        if (root / d).is_dir():
            return {"value": d, "source": DETECTED, "confidence": 0.5}
    return {"value": ".wg/evidence", "source": DEFAULT, "confidence": 0.3,
            "note": "no existing evidence convention; proposing default"}


def _detect_claims_surface(root: Path) -> dict:
    # structured claims doc? (frontmatter `claims:` block, command_iq build.md shape)
    search_roots = [root / ".projects", root / "docs", root]
    hits = []
    for sr in search_roots:
        if not sr.exists():
            continue
        for md in sr.rglob("*.md"):
            if "node_modules" in md.parts or ".git" in md.parts:
                continue
            try:
                head = md.read_text(errors="ignore")[:2000]
            except Exception:
                continue
            if re.search(r"(?m)^claims:\s*$", head):
                hits.append(md.relative_to(root).as_posix())
            if len(hits) >= 5:
                break
        if hits:
            break
    if hits:
        return {"value": "frontmatter", "glob": hits, "source": DETECTED,
                "confidence": 0.85}
    return {"value": "commit-msg", "source": DEFAULT, "confidence": 0.4,
            "note": "no structured claims doc; default to commit-message scanning"}


def _detect_risk_surfaces(root: Path) -> dict:
    # explicit surface table? (a markdown with a Surface|Skill dispatch table)
    for md in (root / "CLAUDE.md", root / "AGENTS.md"):
        if md.exists():
            try:
                txt = md.read_text(errors="ignore")
            except Exception:
                txt = ""
            if re.search(r"Surface\b.*\bSkill", txt) or "surface-skill" in txt:
                rows = re.findall(r"(?m)^\|\s*`?([a-z][\w/.-]+)`?\s*\|", txt)
                return {"value": sorted(set(rows))[:20], "source": DETECTED,
                        "confidence": 0.7, "from": md.name}
    # else: derive candidate surfaces from code module dirs
    surfaces = []
    for base in ("src", "packages", "lib"):
        b = root / base
        if b.is_dir():
            for sub in sorted(b.iterdir()):
                if sub.is_dir() and not sub.name.startswith("."):
                    surfaces.append(f"{base}/{sub.name}")
            if surfaces:
                break
    if surfaces:
        return {"value": surfaces[:20], "source": DETECTED, "confidence": 0.4,
                "note": "derived from top-level module dirs; no explicit surface map"}
    return {"value": [], "source": DEFAULT, "confidence": 0.0,
            "note": "no module structure detected"}


def _node_script_cmd(root: Path, script: str) -> str | None:
    """Return the run-command for a package.json script, or None if absent."""
    pkg = root / "package.json"
    if not pkg.exists():
        return None
    scripts = (_read_json(pkg).get("scripts") or {})
    if script not in scripts:
        return None
    pm = _pkg_manager(root)
    return f"npm run {script}" if pm == "npm" else f"{pm} {script}"


def _detect_lint_command(root: Path) -> dict:
    """Detect a lint/static-check command. Omitted (value=None) when none —
    pinning a non-existent linter would make the gate fail forever."""
    # node — only if the repo declares a lint script (don't assume eslint).
    cmd = _node_script_cmd(root, "lint")
    if cmd:
        return {"value": cmd, "source": DETECTED, "confidence": 0.9, "ecosystem": "node"}
    if (root / "package.json").exists():
        return {"value": None, "source": DEFAULT, "confidence": 0.0, "ecosystem": "node"}

    # go — `go vet` is standard and always runnable for a module, no config.
    if (root / "go.mod").exists():
        return {"value": "go vet ./...", "source": DETECTED, "confidence": 0.85, "ecosystem": "go"}

    # rust — clippy ships with the toolchain.
    if (root / "Cargo.toml").exists():
        return {"value": "cargo clippy", "source": DETECTED, "confidence": 0.7, "ecosystem": "rust"}

    # python — ruff > flake8 > Makefile lint target. Only if configured.
    if (root / "pyproject.toml").exists():
        try:
            txt = (root / "pyproject.toml").read_text()
        except Exception:
            txt = ""
        if "[tool.ruff" in txt:
            return {"value": "ruff check .", "source": DETECTED, "confidence": 0.85, "ecosystem": "python"}
    if (root / "ruff.toml").exists() or (root / ".ruff.toml").exists():
        return {"value": "ruff check .", "source": DETECTED, "confidence": 0.85, "ecosystem": "python"}
    if (root / ".flake8").exists():
        return {"value": "flake8", "source": DETECTED, "confidence": 0.8, "ecosystem": "python"}
    make = root / "Makefile"
    if make.exists():
        try:
            if re.search(r"(?m)^lint:", make.read_text()):
                return {"value": "make lint", "source": DETECTED, "confidence": 0.75, "ecosystem": "python"}
        except Exception:
            pass

    return {"value": None, "source": DEFAULT, "confidence": 0.0,
            "note": "no lint command detected"}


def _detect_build_command(root: Path) -> dict:
    """Detect a build/compile command. Omitted when none (e.g. most pure-Python
    libs don't have a build step)."""
    cmd = _node_script_cmd(root, "build")
    if cmd:
        return {"value": cmd, "source": DETECTED, "confidence": 0.9, "ecosystem": "node"}
    if (root / "package.json").exists():
        return {"value": None, "source": DEFAULT, "confidence": 0.0, "ecosystem": "node"}

    if (root / "go.mod").exists():
        return {"value": "go build ./...", "source": DETECTED, "confidence": 0.85, "ecosystem": "go"}
    if (root / "Cargo.toml").exists():
        return {"value": "cargo build", "source": DETECTED, "confidence": 0.85, "ecosystem": "rust"}

    make = root / "Makefile"
    if make.exists():
        try:
            if re.search(r"(?m)^build:", make.read_text()):
                return {"value": "make build", "source": DETECTED, "confidence": 0.7, "ecosystem": "make"}
        except Exception:
            pass

    return {"value": None, "source": DEFAULT, "confidence": 0.0,
            "note": "no build command detected"}


def detect(repo_root: str) -> dict:
    root = Path(repo_root).resolve()
    return {
        "repo": root.name,
        "root": str(root),
        "test_command": _detect_test_command(root),
        "lint_command": _detect_lint_command(root),
        "build_command": _detect_build_command(root),
        "evidence_sink": _detect_evidence_sink(root),
        "claims_surface": _detect_claims_surface(root),
        "risk_surfaces": _detect_risk_surfaces(root),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: detect.py <repo_root>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(detect(sys.argv[1]), indent=2))
