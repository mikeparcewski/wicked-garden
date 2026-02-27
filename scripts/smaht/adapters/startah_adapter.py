"""Startah adapter — surfaces available third-party CLIs for context assembly."""
import subprocess


def _check_cli(name):
    """Check if a CLI tool is available."""
    try:
        result = subprocess.run(
            ["which", name], capture_output=True, text=True, timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


# Known third-party CLIs that wicked-startah skills orchestrate
KNOWN_CLIS = {
    "codex": {"skill": "codex-cli", "desc": "OpenAI Codex for code review and generation"},
    "gemini": {"skill": "gemini-cli", "desc": "Google Gemini for multi-modal AI tasks"},
    "opencode": {"skill": "opencode-cli", "desc": "OpenCode for AI-assisted coding"},
    "agent-browser": {"skill": "agent-browser", "desc": "Browser automation and scraping"},
}


async def query(prompt: str, **kwargs) -> list:
    """Return available CLI tools that could help with the current task."""
    from dataclasses import dataclass

    @dataclass
    class ContextItem:
        source: str
        title: str
        summary: str

    results = []
    available = []

    for cli_name, info in KNOWN_CLIS.items():
        if _check_cli(cli_name):
            available.append(
                ContextItem(
                    source="startah",
                    title=f"{cli_name} available",
                    summary=f"{info['desc']} — Use /wicked-startah:{info['skill']}"
                )
            )

    return available
