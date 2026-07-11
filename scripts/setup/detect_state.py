#!/usr/bin/env python3
"""detect_state.py — environment + config detection for the wicked-garden-core setup action.

Pure-function probes that the setup action would otherwise inline as
ad-hoc Python. Each subcommand prints a single JSON object so the
markdown body can `jq` or read raw.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT))


def detect_question_mode() -> str:
    """Return ``'PLAIN_TEXT'`` if dangerous mode is active, else ``'INTERACTIVE'``.

    The slash command branches between AskUserQuestion and numbered-list
    prompts on this value.
    """
    try:
        from _session import SessionState  # type: ignore
    except Exception:
        return "INTERACTIVE"
    try:
        state = SessionState.load()
    except Exception:
        return "INTERACTIVE"
    return "PLAIN_TEXT" if getattr(state, "dangerous_mode", False) else "INTERACTIVE"


def read_config() -> dict:
    """Read ``~/.something-wicked/wicked-garden/config.json`` if present."""
    path = Path.home() / ".something-wicked" / "wicked-garden" / "config.json"
    if not path.exists():
        return {"present": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"present": True, "path": str(path), "error": str(exc)}
    return {"present": True, "path": str(path), "config": data}


# Marker files used to fingerprint the working directory.
_LANGUAGE_MARKERS: dict[str, list[str]] = {
    "Python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "Node/TypeScript": ["package.json", "tsconfig.json"],
    "Go": ["go.mod"],
    "Rust": ["Cargo.toml"],
    "Java/Kotlin": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "Ruby": ["Gemfile"],
    "PHP": ["composer.json"],
    "Swift": ["Package.swift"],
    "C/C++": ["CMakeLists.txt", "Makefile"],
}

_FRAMEWORK_MARKERS: dict[str, list[str]] = {
    "FastAPI": ["app/main.py", "main.py"],
    "Django": ["manage.py"],
    "Flask": ["app.py"],
    "Next.js": ["next.config.js", "next.config.ts"],
    "React": ["src/App.tsx", "src/App.jsx"],
    "Vue": ["vue.config.js"],
    "Rails": ["config/routes.rb"],
    "Claude Plugin": [".claude-plugin/plugin.json"],
}


def detect_project_env(cwd: Path | None = None) -> dict:
    """Detect languages and frameworks in ``cwd`` (defaults to CWD)."""
    root = (cwd or Path.cwd()).resolve()
    languages = [
        name
        for name, files in _LANGUAGE_MARKERS.items()
        if any((root / f).exists() for f in files)
    ]
    frameworks = [
        name
        for name, files in _FRAMEWORK_MARKERS.items()
        if any((root / f).exists() for f in files)
    ]
    return {"cwd": str(root), "languages": languages, "frameworks": frameworks}


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("question-mode", help="INTERACTIVE | PLAIN_TEXT")
    sub.add_parser("config", help="Show wicked-garden config.json contents")
    env = sub.add_parser("project-env", help="Detect languages + frameworks in CWD")
    env.add_argument("--cwd", default=None)
    args = parser.parse_args()
    if args.cmd == "question-mode":
        sys.stdout.write(detect_question_mode() + "\n")
    elif args.cmd == "config":
        json.dump(read_config(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.cmd == "project-env":
        cwd = Path(args.cwd) if args.cwd else None
        json.dump(detect_project_env(cwd), sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
