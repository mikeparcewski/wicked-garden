#!/usr/bin/env python3
"""
prereq_doctor.py — Diagnose missing tools and dependencies, suggest installs.

Commands:
  check <tool>           Check if a specific tool is available
  diagnose "<error>"     Parse an error message to identify missing tools
  check-all              Check all wicked-garden prerequisites

Output: JSON with diagnosis and install instructions.

stdlib-only — no external dependencies (must work before deps are installed).
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Tool Registry — single source of truth
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "gh": {
        "name": "GitHub CLI",
        "cli": "gh",
        "test_cmd": ["gh", "--version"],
        "install": {
            "darwin": "brew install gh",
            "linux": "sudo apt install gh || sudo dnf install gh",
            "generic": "https://cli.github.com — download from website",
        },
        "docs": "https://cli.github.com",
        "mcp_patterns": ["github"],
    },
    "jira": {
        "name": "Jira CLI",
        "cli": "jira",
        "test_cmd": ["jira", "--version"],
        "install": {
            "darwin": "brew install ankitpokhrel/jira-cli/jira-cli",
            "linux": "go install github.com/ankitpokhrel/jira-cli/v2@latest",
            "generic": "https://github.com/ankitpokhrel/jira-cli",
        },
        "docs": "https://github.com/ankitpokhrel/jira-cli",
        "mcp_patterns": ["jira", "atlassian"],
    },
    "linear": {
        "name": "Linear CLI",
        "cli": "linear",
        "test_cmd": ["linear", "--version"],
        "install": {
            "darwin": "npm install -g @linear/cli",
            "linux": "npm install -g @linear/cli",
            "generic": "npm install -g @linear/cli",
        },
        "docs": "https://developers.linear.app",
        "mcp_patterns": ["linear"],
    },
    "az": {
        "name": "Azure CLI (DevOps)",
        "cli": "az",
        "test_cmd": ["az", "--version"],
        "post_install": "az extension add --name azure-devops",
        "install": {
            "darwin": "brew install azure-cli",
            "linux": "curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash",
            "generic": "https://learn.microsoft.com/en-us/cli/azure/install-azure-cli",
        },
        "docs": "https://learn.microsoft.com/en-us/azure/devops/cli",
        "mcp_patterns": ["azure-devops", "ado"],
    },
    "rally": {
        "name": "Rally CLI",
        "cli": "rally",
        "test_cmd": ["rally", "--version"],
        "install": {
            "darwin": "pip install rallydev",
            "linux": "pip install rallydev",
            "generic": "pip install rallydev",
        },
        "docs": "https://pypi.org/project/rallydev/",
        "mcp_patterns": ["rally"],
    },
    "glab": {
        "name": "GitLab CLI",
        "cli": "glab",
        "test_cmd": ["glab", "--version"],
        "install": {
            "darwin": "brew install glab",
            "linux": "sudo apt install glab",
            "generic": "https://gitlab.com/gitlab-org/cli",
        },
        "docs": "https://gitlab.com/gitlab-org/cli",
        "mcp_patterns": ["gitlab"],
    },
    "uv": {
        "name": "uv (Python package manager)",
        "cli": "uv",
        "test_cmd": ["uv", "--version"],
        "extra_paths": [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".cargo" / "bin"),
        ],
        "install": {
            "darwin": "brew install uv",
            "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
            "generic": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        },
        "docs": "https://docs.astral.sh/uv",
        "mcp_patterns": [],
    },
    "duckdb": {
        "name": "DuckDB",
        "cli": "duckdb",
        "test_cmd": ["duckdb", "--version"],
        "install": {
            "darwin": "brew install duckdb",
            "linux": "https://duckdb.org/docs/installation",
            "generic": "https://duckdb.org/docs/installation",
        },
        "docs": "https://duckdb.org",
        "mcp_patterns": [],
    },
    "tree-sitter": {
        "name": "tree-sitter CLI",
        "cli": "tree-sitter",
        "test_cmd": ["tree-sitter", "--version"],
        "install": {
            "darwin": "brew install tree-sitter",
            "linux": "npm install -g tree-sitter-cli",
            "generic": "cargo install tree-sitter-cli",
        },
        "docs": "https://tree-sitter.github.io",
        "mcp_patterns": [],
    },
    # --- Infrastructure & Container Tools ---
    "docker": {
        "name": "Docker",
        "cli": "docker",
        "test_cmd": ["docker", "--version"],
        "install": {
            "darwin": "brew install --cask docker",
            "linux": "curl -fsSL https://get.docker.com | sh",
            "generic": "https://docs.docker.com/get-docker/",
        },
        "docs": "https://docs.docker.com",
        "mcp_patterns": [],
        "category": "infra",
    },
    "kubectl": {
        "name": "Kubernetes CLI",
        "cli": "kubectl",
        "test_cmd": ["kubectl", "version", "--client"],
        "install": {
            "darwin": "brew install kubectl",
            "linux": "sudo apt install kubectl",
            "generic": "https://kubernetes.io/docs/tasks/tools/",
        },
        "docs": "https://kubernetes.io/docs/reference/kubectl/",
        "mcp_patterns": [],
        "category": "infra",
    },
    "ollama": {
        "name": "Ollama",
        "cli": "ollama",
        "test_cmd": ["ollama", "--version"],
        "install": {
            "darwin": "brew install ollama",
            "linux": "curl -fsSL https://ollama.com/install.sh | sh",
            "generic": "https://ollama.com/download",
        },
        "docs": "https://ollama.com",
        "mcp_patterns": [],
        "category": "ai",
    },
    # --- Multi-Model CLIs ---
    "codex": {
        "name": "OpenAI Codex CLI",
        "cli": "codex",
        "test_cmd": ["codex", "--version"],
        "install": {
            "darwin": "brew install codex",
            "linux": "npm install -g @openai/codex",
            "generic": "npm install -g @openai/codex",
        },
        "docs": "https://github.com/openai/codex-cli",
        "mcp_patterns": [],
        "category": "ai",
    },
    "gemini": {
        "name": "Google Gemini CLI",
        "cli": "gemini",
        "test_cmd": ["gemini", "--version"],
        "install": {
            "darwin": "npm install -g @google/gemini-cli",
            "linux": "npm install -g @google/gemini-cli",
            "generic": "npm install -g @google/gemini-cli",
        },
        "docs": "https://github.com/google-gemini/gemini-cli",
        "mcp_patterns": [],
        "category": "ai",
    },
    "opencode": {
        "name": "OpenCode CLI",
        "cli": "opencode",
        "test_cmd": ["opencode", "--version"],
        "install": {
            "darwin": "brew install opencode",
            "linux": "go install github.com/sst/opencode@latest",
            "generic": "https://github.com/sst/opencode",
        },
        "docs": "https://github.com/sst/opencode",
        "mcp_patterns": [],
        "category": "ai",
    },
    # --- Scenario Testing Tools ---
    "hurl": {
        "name": "Hurl (HTTP testing)",
        "cli": "hurl",
        "test_cmd": ["hurl", "--version"],
        "install": {
            "darwin": "brew install hurl",
            "linux": "curl -LO https://github.com/Orange-OpenSource/hurl/releases/latest/download/hurl_amd64.deb && sudo dpkg -i hurl_amd64.deb && rm hurl_amd64.deb",
            "generic": "https://hurl.dev/docs/installation.html",
        },
        "docs": "https://hurl.dev",
        "mcp_patterns": [],
        "category": "testing",
    },
    "k6": {
        "name": "k6 (load testing)",
        "cli": "k6",
        "test_cmd": ["k6", "version"],
        "install": {
            "darwin": "brew install k6",
            "linux": "sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D68 && echo 'deb https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt-get update && sudo apt-get install k6",
            "generic": "https://k6.io/docs/get-started/installation/",
        },
        "docs": "https://k6.io",
        "mcp_patterns": [],
        "category": "testing",
    },
    "hey": {
        "name": "hey (HTTP load generator)",
        "cli": "hey",
        "test_cmd": ["hey", "-h"],
        "install": {
            "darwin": "brew install hey",
            "linux": "sudo apt-get install -y hey",
            "generic": "go install github.com/rakyll/hey@latest",
        },
        "docs": "https://github.com/rakyll/hey",
        "mcp_patterns": [],
        "category": "testing",
    },
    "trivy": {
        "name": "Trivy (security scanner)",
        "cli": "trivy",
        "test_cmd": ["trivy", "--version"],
        "install": {
            "darwin": "brew install trivy",
            "linux": "sudo apt-get install -y trivy",
            "generic": "https://aquasecurity.github.io/trivy/",
        },
        "docs": "https://aquasecurity.github.io/trivy/",
        "mcp_patterns": [],
        "category": "security",
    },
    "semgrep": {
        "name": "Semgrep (static analysis)",
        "cli": "semgrep",
        "test_cmd": ["semgrep", "--version"],
        "install": {
            "darwin": "brew install semgrep",
            "linux": "pip install semgrep",
            "generic": "pip install semgrep",
        },
        "docs": "https://semgrep.dev",
        "mcp_patterns": [],
        "category": "security",
    },
    "pa11y": {
        "name": "pa11y (accessibility testing)",
        "cli": "pa11y",
        "test_cmd": ["pa11y", "--version"],
        "install": {
            "darwin": "npm install -g pa11y",
            "linux": "npm install -g pa11y",
            "generic": "npm install -g pa11y",
        },
        "docs": "https://pa11y.org",
        "mcp_patterns": [],
        "category": "testing",
    },
}

# Map selection names (from setup) to registry keys
SELECTION_TO_CLI = {
    "github": "gh",
    "jira": "jira",
    "linear": "linear",
    "ado": "az",
    "rally": "rally",
    "gitlab": "glab",
}

# Error patterns that indicate missing tools
_MISSING_TOOL_PATTERNS = [
    (r"command not found:\s*(\S+)", "cli"),
    (r"not found:\s*(\S+)", "cli"),
    (r"No such file or directory.*?(\S+)$", "cli"),
    (r"ModuleNotFoundError: No module named ['\"](\S+?)['\"]", "python_module"),
    (r"ImportError: No module named ['\"](\S+?)['\"]", "python_module"),
]

# Python module → fix mapping
_PYTHON_MODULE_FIXES = {
    "rapidfuzz": "uv_sync",
    "pydantic": "uv_sync",
    "yaml": "uv_sync",
    "tree_sitter": "uv_sync",
    "aiofiles": "uv_sync",
    "lxml": "uv_sync",
    "pathspec": "uv_sync",
    "kreuzberg": "uv_sync",
}

# Core prereqs that wicked-garden needs
_CORE_PREREQS = ["uv"]
_OPTIONAL_PREREQS = ["gh", "duckdb", "tree-sitter", "docker", "kubectl", "ollama"]


def _detect_platform() -> str:
    """Return 'darwin', 'linux', or 'generic'."""
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    elif system == "linux":
        return "linux"
    return "generic"


def _find_tool(cli: str, extra_paths: list[str] | None = None) -> str | None:
    """Find a tool on PATH or in extra known locations."""
    found = shutil.which(cli)
    if found:
        return found
    for p in (extra_paths or []):
        candidate = Path(p) / cli
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _check_mcp(patterns: list[str]) -> dict | None:
    """Check if an MCP server matching the patterns is configured."""
    if not patterns:
        return None
    mcp_paths = [
        Path.home() / ".claude" / "claude_desktop_config.json",
        Path.home() / ".config" / "claude" / "settings.json",
        Path.home() / ".claude.json",
    ]
    for mcp_path in mcp_paths:
        try:
            if not mcp_path.exists():
                continue
            data = json.loads(mcp_path.read_text())
            servers = data.get("mcpServers", {})
            for name in servers:
                name_lower = name.lower()
                if any(p in name_lower for p in patterns):
                    return {"server": name, "config": str(mcp_path)}
        except Exception:
            continue
    return None


def check_tool(tool_key: str) -> dict:
    """Check a single tool's availability. Returns diagnosis dict."""
    # Resolve selection names to CLI keys
    tool_key = SELECTION_TO_CLI.get(tool_key, tool_key)

    if tool_key not in TOOL_REGISTRY:
        return {"tool": tool_key, "status": "unknown", "message": f"Unknown tool: {tool_key}"}

    info = TOOL_REGISTRY[tool_key]
    plat = _detect_platform()
    result = {
        "tool": tool_key,
        "name": info["name"],
        "cli": info["cli"],
        "status": "missing",
        "via": None,
        "install_cmd": info["install"].get(plat, info["install"].get("generic", "")),
        "post_install": info.get("post_install"),
        "docs": info["docs"],
    }

    # Check MCP first (preferred)
    mcp = _check_mcp(info.get("mcp_patterns", []))
    if mcp:
        result["status"] = "available"
        result["via"] = "mcp"
        result["mcp_server"] = mcp["server"]

    # Check CLI (works as fallback or primary)
    cli_path = _find_tool(info["cli"], info.get("extra_paths"))
    if cli_path:
        if result["status"] != "available":
            result["status"] = "available"
            result["via"] = "cli"
        result["cli_path"] = cli_path
    elif result["status"] != "available":
        result["status"] = "missing"

    return result


def diagnose_error(error_text: str) -> dict:
    """Parse an error message to identify missing tools/modules."""
    for pattern, error_type in _MISSING_TOOL_PATTERNS:
        match = re.search(pattern, error_text, re.MULTILINE)
        if not match:
            continue
        token = match.group(1)

        if error_type == "python_module":
            fix = _PYTHON_MODULE_FIXES.get(token)
            if fix == "uv_sync":
                uv_info = check_tool("uv")
                return {
                    "error_type": "python_module",
                    "module": token,
                    "fix": "uv_sync",
                    "fix_cmd": "uv sync",
                    "uv_available": uv_info["status"] == "available",
                    "uv_path": uv_info.get("cli_path"),
                    "message": f"Python module '{token}' not installed. Run 'uv sync' from the plugin root.",
                }
            return {
                "error_type": "python_module",
                "module": token,
                "fix": "unknown",
                "message": f"Python module '{token}' not installed.",
            }

        if error_type == "cli":
            # Try to match the CLI name to a known tool
            for key, info in TOOL_REGISTRY.items():
                if info["cli"] == token:
                    return {
                        "error_type": "missing_cli",
                        "tool": key,
                        **check_tool(key),
                        "message": f"CLI '{token}' not found.",
                    }
            return {
                "error_type": "missing_cli",
                "tool": token,
                "status": "unknown",
                "message": f"CLI '{token}' not found. Not in the known tool registry.",
            }

    return {"error_type": "unknown", "message": "Could not identify a missing tool from the error."}


def check_all() -> dict:
    """Check all wicked-garden prerequisites."""
    results = {"core": {}, "optional": {}, "python_deps": False}

    for tool in _CORE_PREREQS:
        results["core"][tool] = check_tool(tool)

    for tool in _OPTIONAL_PREREQS:
        results["optional"][tool] = check_tool(tool)

    # Check Python deps via uv
    uv = results["core"].get("uv", {})
    if uv.get("status") == "available":
        uv_path = uv.get("cli_path", "uv")
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ".")).resolve()
        try:
            proc = subprocess.run(
                [uv_path, "sync", "--dry-run", "--quiet"],
                cwd=str(plugin_root),
                capture_output=True, text=True, timeout=30,
            )
            results["python_deps"] = proc.returncode == 0
        except Exception:
            results["python_deps"] = False

    return results


def check_category(category: str) -> dict:
    """Check all tools in a given category (e.g. 'testing', 'security', 'ai', 'infra')."""
    results = {}
    for key, info in TOOL_REGISTRY.items():
        if info.get("category") == category:
            results[key] = check_tool(key)
    return results


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: prereq_doctor.py <check|diagnose|check-all|check-category> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check" and len(sys.argv) >= 3:
        result = check_tool(sys.argv[2])
        print(json.dumps(result, indent=2))
    elif cmd == "diagnose" and len(sys.argv) >= 3:
        result = diagnose_error(sys.argv[2])
        print(json.dumps(result, indent=2))
    elif cmd == "check-all":
        result = check_all()
        print(json.dumps(result, indent=2))
    elif cmd == "check-category" and len(sys.argv) >= 3:
        result = check_category(sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
