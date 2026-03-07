# Tool Registry

Maps tool names to install commands per platform. Used by `prereq_doctor.py`.

## CLI Tools

| Tool | CLI | macOS (brew) | Linux (apt) | Generic | Docs |
|------|-----|-------------|-------------|---------|------|
| GitHub | `gh` | `brew install gh` | `apt install gh` | [manual](https://cli.github.com) | https://cli.github.com |
| Jira | `jira` | `brew install ankitpokhrel/jira-cli/jira-cli` | `go install github.com/ankitpokhrel/jira-cli/v2@latest` | — | https://github.com/ankitpokhrel/jira-cli |
| Linear | `linear` | `npm install -g @linear/cli` | `npm install -g @linear/cli` | `npm install -g @linear/cli` | https://developers.linear.app |
| Azure DevOps | `az` | `brew install azure-cli` | `curl -sL https://aka.ms/InstallAzureCLIDeb \| sudo bash` | [manual](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) | https://learn.microsoft.com/en-us/azure/devops/cli |
| Rally | `rally` | `pip install rallydev` | `pip install rallydev` | `pip install rallydev` | https://pypi.org/project/rallydev/ |
| GitLab | `glab` | `brew install glab` | `apt install glab` | [manual](https://gitlab.com/gitlab-org/cli) | https://gitlab.com/gitlab-org/cli |
| Shortcut | `sc` | `brew install shortcut-cli` | — | `npm install -g @shortcut/cli` | https://github.com/shortcut/cli |
| DuckDB | `duckdb` | `brew install duckdb` | `apt install duckdb` | [manual](https://duckdb.org/docs/installation) | https://duckdb.org |
| uv | `uv` | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | https://docs.astral.sh/uv |
| tree-sitter | `tree-sitter` | `brew install tree-sitter` | `npm install -g tree-sitter-cli` | `cargo install tree-sitter-cli` | https://tree-sitter.github.io |

## Python Dependencies

| Package | Import | Install | Used By |
|---------|--------|---------|---------|
| rapidfuzz | `from rapidfuzz import ...` | `uv sync` (from root pyproject.toml) | search |
| pydantic | `from pydantic import ...` | `uv sync` | search, smaht |
| tree-sitter | `import tree_sitter` | `uv sync` | search |
| aiofiles | `import aiofiles` | `uv sync` | search |
| pyyaml | `import yaml` | `uv sync` | search |
| lxml | `from lxml import ...` | `uv sync` | search |
| kreuzberg | `import kreuzberg` | `uv sync` | search |

## Error Pattern → Tool Mapping

| Error Pattern | Missing Tool | Fix |
|---------------|-------------|-----|
| `command not found: gh` | gh CLI | Install gh |
| `command not found: uv` | uv | Install uv |
| `command not found: jira` | jira-cli | Install jira-cli |
| `command not found: az` | azure-cli | Install az |
| `command not found: glab` | glab | Install glab |
| `ModuleNotFoundError: No module named 'rapidfuzz'` | Python deps | Run `uv sync` |
| `ModuleNotFoundError: No module named 'pydantic'` | Python deps | Run `uv sync` |
| `ModuleNotFoundError: No module named 'yaml'` | Python deps | Run `uv sync` |
| `ModuleNotFoundError: No module named 'tree_sitter'` | Python deps | Run `uv sync` |

## Azure DevOps Extension

After installing `az`, the azure-devops extension is also needed:

```bash
az extension add --name azure-devops
```

This is handled automatically by the prereq-doctor when `ado` is the target.
