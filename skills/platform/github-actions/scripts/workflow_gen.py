#!/usr/bin/env python3
"""
GitHub Actions Workflow Generator

Generates secure, optimized workflows based on project detection.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any


TEMPLATES = {
    "node": {
        "name": "CI",
        "on": {"push": {"branches": ["main"]}, "pull_request": None},
        "permissions": {"contents": "read"},
        "concurrency": {"group": "ci-${{ github.ref }}", "cancel-in-progress": True},
        "jobs": {
            "test": {
                "runs-on": "ubuntu-latest",
                "timeout-minutes": 10,
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-node@v4", "with": {"node-version": "20", "cache": "npm"}},
                    {"run": "npm ci"},
                    {"run": "npm test"}
                ]
            }
        }
    },
    "python": {
        "name": "CI",
        "on": {"push": {"branches": ["main"]}, "pull_request": None},
        "permissions": {"contents": "read"},
        "concurrency": {"group": "ci-${{ github.ref }}", "cancel-in-progress": True},
        "jobs": {
            "test": {
                "runs-on": "ubuntu-latest",
                "timeout-minutes": 10,
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-python@v5", "with": {"python-version": "3.12", "cache": "pip"}},
                    {"run": "pip install -e '.[dev]' || pip install -r requirements.txt"},
                    {"run": "pytest || python -m unittest discover"}
                ]
            }
        }
    },
    "docker": {
        "name": "Docker",
        "on": {"push": {"branches": ["main"], "tags": ["v*"]}},
        "permissions": {"contents": "read", "packages": "write"},
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "timeout-minutes": 30,
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "docker/setup-buildx-action@v3"},
                    {
                        "uses": "docker/login-action@v3",
                        "with": {
                            "registry": "ghcr.io",
                            "username": "${{ github.actor }}",
                            "password": "${{ secrets.GITHUB_TOKEN }}"
                        }
                    },
                    {
                        "uses": "docker/build-push-action@v5",
                        "with": {
                            "push": "${{ github.event_name != 'pull_request' }}",
                            "tags": "ghcr.io/${{ github.repository }}:${{ github.sha }}",
                            "cache-from": "type=gha",
                            "cache-to": "type=gha,mode=max"
                        }
                    }
                ]
            }
        }
    }
}


def detect_project_type(path: Path) -> List[str]:
    """Detect project type from files present."""
    types = []

    if (path / "package.json").exists():
        types.append("node")
    if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
        types.append("python")
    if (path / "Dockerfile").exists():
        types.append("docker")
    if (path / "Cargo.toml").exists():
        types.append("rust")
    if (path / "go.mod").exists():
        types.append("go")

    return types or ["generic"]


def generate_workflow(project_type: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate workflow YAML structure."""
    options = options or {}

    if project_type not in TEMPLATES:
        # Generic fallback
        return {
            "name": "CI",
            "on": {"push": {"branches": ["main"]}, "pull_request": None},
            "permissions": {"contents": "read"},
            "jobs": {
                "build": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 10,
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {"run": "echo 'Add your build steps here'"}
                    ]
                }
            }
        }

    workflow = dict(TEMPLATES[project_type])

    # Apply options
    if options.get("matrix"):
        workflow["jobs"]["test"]["strategy"] = {
            "matrix": options["matrix"],
            "fail-fast": False
        }

    if options.get("deploy"):
        workflow["jobs"]["deploy"] = {
            "needs": list(workflow["jobs"].keys())[0],
            "runs-on": "ubuntu-latest",
            "timeout-minutes": 30,
            "environment": "production",
            "steps": [
                {"uses": "actions/checkout@v4"},
                {"run": "echo 'Add deploy steps'"}
            ]
        }
        workflow["permissions"]["id-token"] = "write"

    return workflow


def workflow_to_yaml(workflow: Dict[str, Any]) -> str:
    """Convert workflow dict to YAML string."""
    import yaml

    # Custom representer to handle None and booleans
    def represent_none(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:null', '')

    yaml.add_representer(type(None), represent_none)

    return yaml.dump(workflow, sort_keys=False, default_flow_style=False, allow_unicode=True)


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub Actions workflows")
    parser.add_argument("--type", choices=list(TEMPLATES.keys()) + ["auto", "generic"],
                       default="auto", help="Project type (default: auto-detect)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--detect-only", action="store_true", help="Only detect project type")
    parser.add_argument("--path", default=".", help="Project path to analyze")
    parser.add_argument("--with-deploy", action="store_true", help="Include deployment job")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of YAML")

    args = parser.parse_args()
    path = Path(args.path)

    # Detect project type
    detected = detect_project_type(path)

    if args.detect_only:
        print(json.dumps({"detected": detected}))
        return

    project_type = args.type if args.type != "auto" else detected[0]

    # Generate workflow
    options = {}
    if args.with_deploy:
        options["deploy"] = True

    workflow = generate_workflow(project_type, options)

    # Output
    if args.json:
        output = json.dumps(workflow, indent=2)
    else:
        try:
            output = workflow_to_yaml(workflow)
        except ImportError:
            print("PyYAML not installed. Use --json or install: pip install pyyaml",
                  file=sys.stderr)
            sys.exit(1)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
        print(f"Wrote workflow to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
