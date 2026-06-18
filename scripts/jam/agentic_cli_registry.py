#!/usr/bin/env python3
"""
agentic_cli_registry.py — machine-readable registry of agentic / chat / local
LLM CLIs that wicked-garden's council can convene.

This is the single source of truth for "which command-line LLM tools exist,
how do you invoke them headlessly, and what auth/trust do they need". It
mirrors the dataclass + stdlib-only pattern of ``scripts/_capability_registry.py``:
no third-party imports, ``from __future__ import annotations``, ``@dataclass``,
detection via ``shutil.which``.

The council orchestration (``agents/jam/council.md``) is driven by this
registry: it detects installed CLIs, probes their headless usability, and
renders the per-CLI invocation from these records rather than hardcoding a
drifting bash block per tool.

Headless invocation templates use a ``{PROMPT}`` placeholder (and ``{MODEL}``
for local runners). ``trust_flags`` are appended for non-interactive runs so a
CLI does not block on a permission / trust / git-repo prompt. Records flagged
``confidence="confirm-on-probe"`` have an UNCERTAIN headless flag — the probe
in ``detect_clis.py`` must verify them before the council relies on them.

Usage:
    from agentic_cli_registry import (
        AGENTIC_CLI_REGISTRY, AgenticCLI, COUNCIL_CLIS, detect,
    )
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Record type
# ---------------------------------------------------------------------------


@dataclass
class AgenticCLI:
    """One command-line LLM tool the council can talk to.

    Fields capture everything the orchestrator needs to detect the binary,
    invoke it headlessly with the SAME prompt every other CLI gets, classify
    its usability, and disambiguate binary collisions by version string.
    """

    key: str  # stable registry id (kebab-case)
    display_name: str  # human-facing name for synthesis attribution
    binary: str  # primary binary name for shutil.which()
    vendor: str  # who ships it
    category: str  # "agentic-coder" | "chat" | "local-runner"
    headless_invocation: str  # argv-ish template using {PROMPT} (and {MODEL})
    input_mode: str  # "prompt-arg" | "stdin" | "at-file" | "message-file" | "model-arg"
    model_flag_style: str  # "-m" | "--model" | "provider-model" | "config-only" | "model-arg" | "none"
    version_probe: list[str]  # argv to print version (collision disambiguation)
    auth_hint: str  # what auth / config / daemon it needs
    install: dict[str, str] = field(default_factory=dict)  # {darwin,linux,generic}
    trust_flags: list[str] = field(default_factory=list)  # appended for headless runs
    alt_binaries: list[str] = field(default_factory=list)  # other names the tool may install as
    confidence: str = "verified"  # "verified" | "confirm-on-probe"
    collision_note: str = ""  # binary-name collision / rename caveat
    enabled_for_council: bool = True  # False = excluded from default convening

    def binaries(self) -> list[str]:
        """Primary binary first, then any alternates."""
        return [self.binary, *self.alt_binaries]

    def render(self, prompt: str, model: str = "") -> str:
        """Fill the headless template. {PROMPT} and {MODEL} are substituted;
        trust flags are NOT injected here (the probe / orchestrator appends
        them) so this stays a faithful echo of the registry template."""
        return self.headless_invocation.replace("{PROMPT}", prompt).replace(
            "{MODEL}", model
        )


# ---------------------------------------------------------------------------
# Registry — one record per CLI
# ---------------------------------------------------------------------------
# VERIFIED entries hard-code a confirmed headless form. CONFIRM-ON-PROBE
# entries have an uncertain headless flag and MUST be verified by the probe
# before the council relies on them.

AGENTIC_CLI_REGISTRY: dict[str, AgenticCLI] = {
    # ----- VERIFIED: agentic coders -----
    "claude": AgenticCLI(
        key="claude",
        display_name="Claude",
        binary="claude",
        vendor="Anthropic",
        category="agentic-coder",
        headless_invocation='claude -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["claude", "--version"],
        trust_flags=["--dangerously-skip-permissions"],
        auth_hint="Anthropic OAuth or ANTHROPIC_API_KEY",
        install={"generic": "bundled with Claude Code"},
        confidence="verified",
        collision_note="Council host. Claude participates in-process, not as an external CLI seat.",
    ),
    "codex": AgenticCLI(
        key="codex",
        display_name="Codex",
        binary="codex",
        vendor="OpenAI",
        category="agentic-coder",
        headless_invocation='codex exec "{PROMPT}"',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="-m",
        version_probe=["codex", "--version"],
        trust_flags=["--skip-git-repo-check"],
        auth_hint="`codex login` or OPENAI_API_KEY",
        install={"darwin": "brew install codex", "generic": "npm i -g @openai/codex"},
        confidence="verified",
    ),
    "gemini": AgenticCLI(
        key="gemini",
        display_name="Gemini",
        binary="gemini",
        vendor="Google",
        category="agentic-coder",
        headless_invocation='gemini -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="-m",
        version_probe=["gemini", "--version"],
        trust_flags=["--skip-trust"],  # or env GEMINI_CLI_TRUST_WORKSPACE=true
        auth_hint="Google login or GEMINI_API_KEY",
        install={"generic": "npm i -g @google/gemini-cli"},
        confidence="verified",
    ),
    "agy": AgenticCLI(
        key="agy",
        display_name="Antigravity",
        binary="agy",
        vendor="Google Antigravity",
        category="agentic-coder",
        headless_invocation='agy -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",  # `agy models` to list
        version_probe=["agy", "--version"],
        trust_flags=["--dangerously-skip-permissions"],
        auth_hint="Antigravity login",
        install={"generic": "agy install"},
        confidence="verified",
    ),
    "pi": AgenticCLI(
        key="pi",
        display_name="Pi",
        binary="pi",
        vendor="earendil-works",
        category="agentic-coder",
        headless_invocation='pi -p "{PROMPT}"',
        input_mode="prompt-arg",  # also supports @file attach
        model_flag_style="provider-model",  # --provider X --model Y
        version_probe=["pi", "--version"],
        auth_hint="provider API key (Google default; OpenAI/Anthropic/etc.)",
        install={"generic": "npm i -g @mariozechner/pi-coding-agent"},
        confidence="verified",
    ),
    "opencode": AgenticCLI(
        key="opencode",
        display_name="OpenCode",
        binary="opencode",
        vendor="opencode",
        category="agentic-coder",
        headless_invocation='opencode run "{PROMPT}"',
        input_mode="prompt-arg",  # also supports -f file
        model_flag_style="-m",  # provider/model
        version_probe=["opencode", "--version"],
        auth_hint="`opencode auth` provider login",
        install={"darwin": "brew install opencode", "generic": "https://github.com/sst/opencode"},
        confidence="verified",
    ),
    "aider": AgenticCLI(
        key="aider",
        display_name="Aider",
        binary="aider",
        vendor="Aider",
        category="agentic-coder",
        headless_invocation=(
            'aider --message "{PROMPT}" --yes-always --no-git '
            "--no-auto-commits --no-stream --no-analytics"
        ),
        input_mode="message-file",  # --message-file FILE preferred for scaffolds; -m to pick model
        model_flag_style="--model",
        version_probe=["aider", "--version"],
        trust_flags=[],  # trust handled inline by the flags in the invocation
        auth_hint="model provider key (ANTHROPIC_API_KEY / OPENAI_API_KEY / …)",
        install={"darwin": "brew install aider", "generic": "pip install aider-install"},
        confidence="verified",
        collision_note="Expects a writable cwd (.aider.* cache); run from a scratch tempdir.",
    ),
    "copilot": AgenticCLI(
        key="copilot",
        display_name="Copilot",
        binary="copilot",
        vendor="GitHub",
        category="agentic-coder",
        headless_invocation='copilot -p "{PROMPT}" --allow-all-tools',
        input_mode="prompt-arg",
        model_flag_style="--model",
        version_probe=["copilot", "--version"],
        trust_flags=["--allow-all-tools"],  # REQUIRED for headless (else blocks on tool approval)
        auth_hint="GitHub auth (Copilot subscription)",
        install={"generic": "npm i -g @github/copilot"},
        confidence="verified",
    ),
    "goose": AgenticCLI(
        key="goose",
        display_name="Goose",
        binary="goose",
        vendor="Block",
        category="agentic-coder",
        headless_invocation='goose run -t "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="config-only",
        version_probe=["goose", "--version"],
        auth_hint="`goose configure` provider setup",
        install={"darwin": "brew install block-goose-cli"},
        confidence="verified",
    ),
    "cursor-agent": AgenticCLI(
        key="cursor-agent",
        display_name="Cursor Agent",
        binary="cursor-agent",
        vendor="Cursor",
        category="agentic-coder",
        headless_invocation='cursor-agent -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["cursor-agent", "--version"],
        alt_binaries=["agent"],
        auth_hint="`cursor-agent login`",
        install={"generic": "cursor install"},
        confidence="verified",
        collision_note=(
            "Alt binary 'agent' collides with other tools. QUIRK: `-p` may hang — "
            "rely on the per-CLI timeout to bound it."
        ),
    ),
    "amp": AgenticCLI(
        key="amp",
        display_name="Amp",
        binary="amp",
        vendor="Sourcegraph",
        category="agentic-coder",
        headless_invocation='amp -x "{PROMPT}"',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="none",
        version_probe=["amp", "--version"],
        trust_flags=["--dangerously-allow-all"],
        auth_hint="Amp API key (consumes credits)",
        install={"generic": "npm i -g @sourcegraph/amp"},
        confidence="verified",
    ),
    "droid": AgenticCLI(
        key="droid",
        display_name="Droid",
        binary="droid",
        vendor="Factory",
        category="agentic-coder",
        headless_invocation='droid exec "{PROMPT}"',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="none",
        version_probe=["droid", "--version"],
        trust_flags=["--auto", "medium"],
        auth_hint="~/.factory/config.json",
        install={"generic": "factory install"},
        confidence="verified",
    ),
    "qwen": AgenticCLI(
        key="qwen",
        display_name="Qwen Code",
        binary="qwen",
        vendor="Alibaba",
        category="agentic-coder",
        headless_invocation='qwen -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["qwen", "--version"],
        auth_hint="OAuth or provider key",
        install={"generic": "npm i -g @qwen-code/qwen-code"},
        confidence="verified",
    ),
    "openhands": AgenticCLI(
        key="openhands",
        display_name="OpenHands",
        binary="openhands",
        vendor="OpenHands",
        category="agentic-coder",
        headless_invocation='openhands --headless -t "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["openhands", "--version"],
        auth_hint="LLM config (provider key)",
        install={"generic": "pip install openhands-ai"},
        confidence="verified",
    ),
    "interpreter": AgenticCLI(
        key="interpreter",
        display_name="Open Interpreter",
        binary="interpreter",
        vendor="Open Interpreter",
        category="agentic-coder",
        headless_invocation='interpreter -y "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["interpreter", "--version"],
        trust_flags=["-y"],
        auth_hint="model provider key",
        install={"generic": "pip install open-interpreter"},
        confidence="verified",
        collision_note="Executes code locally by design — treat output as untrusted.",
    ),
    "gptme": AgenticCLI(
        key="gptme",
        display_name="gptme",
        binary="gptme",
        vendor="gptme",
        category="agentic-coder",
        headless_invocation='gptme "{PROMPT}" --non-interactive',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["gptme", "--version"],
        auth_hint="provider API key",
        install={"generic": "pip install gptme"},
        confidence="verified",
    ),
    "crush": AgenticCLI(
        key="crush",
        display_name="Crush",
        binary="crush",
        vendor="Charm",
        category="agentic-coder",
        headless_invocation='crush run "{PROMPT}" --quiet',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="config-only",
        version_probe=["crush", "--version"],
        auth_hint="provider API key",
        install={"darwin": "brew install charmbracelet/tap/crush"},
        confidence="verified",
    ),
    # ----- VERIFIED: chat clients -----
    "llm": AgenticCLI(
        key="llm",
        display_name="llm",
        binary="llm",
        vendor="Simon Willison",
        category="chat",
        headless_invocation='llm "{PROMPT}"',
        input_mode="prompt-arg",  # also pipe-native (stdin)
        model_flag_style="-m",
        version_probe=["llm", "--version"],
        auth_hint="`llm keys set <provider>`",
        install={"darwin": "brew install llm", "generic": "pip install llm"},
        confidence="verified",
    ),
    "aichat": AgenticCLI(
        key="aichat",
        display_name="aichat",
        binary="aichat",
        vendor="sigoden",
        category="chat",
        headless_invocation='aichat -S "{PROMPT}"',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="-m",  # client:model
        version_probe=["aichat", "--version"],
        auth_hint="config provider key",
        install={"darwin": "brew install aichat"},
        confidence="verified",
        collision_note="-S disables streaming so output captures cleanly.",
    ),
    "mods": AgenticCLI(
        key="mods",
        display_name="mods",
        binary="mods",
        vendor="Charm",
        category="chat",
        headless_invocation='mods "{PROMPT}"',  # also: echo "{PROMPT}" | mods
        input_mode="stdin",  # stdin-native; prompt-arg also works
        model_flag_style="config-only",
        version_probe=["mods", "--version"],
        auth_hint="provider API key",
        install={"darwin": "brew install charmbracelet/tap/mods"},
        confidence="verified",
    ),
    "sgpt": AgenticCLI(
        key="sgpt",
        display_name="ShellGPT",
        binary="sgpt",
        vendor="shell-gpt",
        category="chat",
        headless_invocation='sgpt "{PROMPT}"',
        input_mode="prompt-arg",  # also accepts stdin
        model_flag_style="config-only",
        version_probe=["sgpt", "--version"],
        trust_flags=[],  # NB: --execute runs shell commands — NEVER enable for council
        auth_hint="OPENAI_API_KEY",
        install={"generic": "pip install shell-gpt"},
        confidence="verified",
        collision_note="`--execute`/`-s` runs shell commands; council must never pass it.",
    ),
    "q": AgenticCLI(
        key="q",
        display_name="Amazon Q",
        binary="q",
        vendor="Amazon",
        category="chat",
        headless_invocation='q chat --no-interactive --trust-all-tools "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["q", "--version"],
        alt_binaries=["kiro-cli"],
        trust_flags=["--trust-all-tools"],
        auth_hint="AWS Builder ID",
        install={"generic": "AWS CLI install"},
        confidence="verified",
        collision_note=(
            "'q' is a very common binary name (collision risk). QUIRK: renamed to "
            "`kiro-cli` (Nov 2025) — verify version string before trusting."
        ),
    ),
    # ----- VERIFIED: local runner -----
    "ollama": AgenticCLI(
        key="ollama",
        display_name="Ollama",
        binary="ollama",
        vendor="Ollama",
        category="local-runner",
        headless_invocation='ollama run {MODEL} "{PROMPT}"',
        input_mode="model-arg",  # model name then prompt
        model_flag_style="model-arg",
        version_probe=["ollama", "--version"],
        auth_hint="no auth, but REQUIRES the daemon (`ollama serve`) + a pulled model",
        install={"darwin": "brew install ollama", "generic": "https://ollama.com/download"},
        confidence="verified",
        collision_note="Needs a running daemon AND a pulled model; bare `ollama run` with no model fails.",
    ),
    # ----- CONFIRM-ON-PROBE: headless flag uncertain, verify before relying -----
    "grok": AgenticCLI(
        key="grok",
        display_name="Grok (xAI)",
        binary="grok",
        vendor="xAI Grok Build",
        category="agentic-coder",
        headless_invocation='grok -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["grok", "--version"],
        auth_hint="xAI API key",
        install={"generic": "see xAI Grok Build docs"},
        confidence="confirm-on-probe",
        collision_note="Binary 'grok' collides with community grok-cli — disambiguate by version.",
    ),
    "grok-cli": AgenticCLI(
        key="grok-cli",
        display_name="Grok CLI (community)",
        binary="grok",
        vendor="community",
        category="agentic-coder",
        headless_invocation='grok -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["grok", "--version"],
        auth_hint="xAI / provider key",
        install={"generic": "npm i -g grok-cli (community)"},
        confidence="confirm-on-probe",
        collision_note="Shares the 'grok' binary with xAI's official build — version string disambiguates.",
    ),
    "forge": AgenticCLI(
        key="forge",
        display_name="Forge",
        binary="forge",
        vendor="forgecode",
        category="agentic-coder",
        headless_invocation='forge -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["forge", "--version"],
        auth_hint="provider API key",
        install={"generic": "see forgecode docs"},
        confidence="confirm-on-probe",
        collision_note="Binary 'forge' collides with Foundry's forge (Solidity) — disambiguate by version.",
    ),
    "continue": AgenticCLI(
        key="continue",
        display_name="Continue",
        binary="cn",
        vendor="Continue",
        category="agentic-coder",
        headless_invocation='cn -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["cn", "--version"],
        auth_hint="provider config",
        install={"generic": "see continue.dev docs"},
        confidence="confirm-on-probe",
    ),
    "cline": AgenticCLI(
        key="cline",
        display_name="Cline",
        binary="cline",
        vendor="Cline",
        category="agentic-coder",
        headless_invocation='cline "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["cline", "--version"],
        auth_hint="provider config",
        install={"generic": "see cline docs"},
        confidence="confirm-on-probe",
    ),
    "cody": AgenticCLI(
        key="cody",
        display_name="Cody (deprecated)",
        binary="cody",
        vendor="Sourcegraph",
        category="agentic-coder",
        headless_invocation='cody chat -m "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="-m",
        version_probe=["cody", "--version"],
        auth_hint="Sourcegraph enterprise token",
        install={"generic": "DEPRECATED — enterprise-only"},
        confidence="confirm-on-probe",
        collision_note="DEPRECATED / enterprise-only.",
        enabled_for_council=False,
    ),
    "plandex": AgenticCLI(
        key="plandex",
        display_name="Plandex (winding down)",
        binary="plandex",
        vendor="Plandex",
        category="agentic-coder",
        headless_invocation='plandex tell "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["plandex", "--version"],
        auth_hint="provider key",
        install={"generic": "see plandex docs"},
        confidence="confirm-on-probe",
        collision_note="Project winding down.",
        enabled_for_council=False,
    ),
    "mistral-vibe": AgenticCLI(
        key="mistral-vibe",
        display_name="Mistral Vibe",
        binary="vibe",
        vendor="Mistral",
        category="agentic-coder",
        headless_invocation='vibe -p "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["vibe", "--version"],
        auth_hint="Mistral API key (paid)",
        install={"generic": "see Mistral docs (paid)"},
        confidence="confirm-on-probe",
    ),
    "mentat": AgenticCLI(
        key="mentat",
        display_name="Mentat",
        binary="mentat",
        vendor="AbanteAI",
        category="agentic-coder",
        headless_invocation='mentat "{PROMPT}"',
        input_mode="prompt-arg",
        model_flag_style="none",
        version_probe=["mentat", "--version"],
        auth_hint="OPENAI_API_KEY",
        install={"generic": "pip install mentat"},
        confidence="confirm-on-probe",
        collision_note="Primarily interactive — headless behaviour uncertain.",
    ),
}


# ---------------------------------------------------------------------------
# Council ordering — preferred convening order for external CLIs.
# Claude is the in-process host (not an external seat) so it is NOT listed here.
# Order roughly tracks confidence + diversity of vendor/provider.
# ---------------------------------------------------------------------------

COUNCIL_CLIS: list[str] = [
    "codex",
    "gemini",
    "copilot",
    "opencode",
    "pi",
    "agy",
    "aider",
    "goose",
    "amp",
    "droid",
    "cursor-agent",
    "qwen",
    "crush",
    "openhands",
    "gptme",
    "interpreter",
    "llm",
    "aichat",
    "mods",
    "sgpt",
    "q",
    "ollama",
]


def council_clis(include_disabled: bool = False) -> list[AgenticCLI]:
    """Return council-eligible CLI records in convening order.

    Skips Claude (in-process host) and, unless ``include_disabled``, any record
    with ``enabled_for_council=False`` (deprecated / winding-down tools).
    Confirm-on-probe records ARE included — the probe gates their actual use.
    """
    out: list[AgenticCLI] = []
    seen: set[str] = set()
    for key in COUNCIL_CLIS:
        cli = AGENTIC_CLI_REGISTRY.get(key)
        if cli is None or key in seen:
            continue
        if not include_disabled and not cli.enabled_for_council:
            continue
        out.append(cli)
        seen.add(key)
    # Append any council-eligible records not explicitly ordered above.
    for key, cli in AGENTIC_CLI_REGISTRY.items():
        if key in seen or key == "claude":
            continue
        if not include_disabled and not cli.enabled_for_council:
            continue
        out.append(cli)
        seen.add(key)
    return out


def detect(probe: bool = False) -> dict:
    """Detect which registry CLIs are installed via ``shutil.which``.

    With ``probe=False`` (default) this is a pure PATH scan — no subprocesses,
    safe to call anywhere. The ``probe=True`` path (actually running each CLI's
    headless form to classify usable vs unusable) lives in ``detect_clis.py`` so
    this module stays import-light and side-effect-free; calling ``detect(probe=True)``
    here raises to make that boundary explicit.

    Returns:
        {
          "detected": [ {key, display_name, binary, resolved_path, category,
                         confidence, enabled_for_council}, ... ],
          "collisions": [ {binary, keys:[...]}, ... ],
        }
    """
    if probe:
        raise NotImplementedError(
            "Usability probing lives in detect_clis.py (subprocess-based). "
            "Call agentic_cli_registry.detect() for a pure PATH scan, or run "
            "detect_clis.py --probe for the full probe."
        )

    detected: list[dict] = []
    binary_to_keys: dict[str, list[str]] = {}

    for key, cli in AGENTIC_CLI_REGISTRY.items():
        # Track every binary this record could claim, for collision reporting.
        for b in cli.binaries():
            binary_to_keys.setdefault(b, []).append(key)
        # Resolve the first of (primary, *alts) that exists on PATH.
        resolved = None
        used_binary = cli.binary
        for b in cli.binaries():
            found = shutil.which(b)
            if found:
                resolved = found
                used_binary = b
                break
        if resolved:
            detected.append(
                {
                    "key": key,
                    "display_name": cli.display_name,
                    "binary": used_binary,
                    "resolved_path": resolved,
                    "category": cli.category,
                    "confidence": cli.confidence,
                    "enabled_for_council": cli.enabled_for_council,
                }
            )

    collisions = [
        {"binary": b, "keys": keys}
        for b, keys in sorted(binary_to_keys.items())
        if len(keys) > 1
    ]

    return {"detected": detected, "collisions": collisions}


if __name__ == "__main__":  # pragma: no cover — manual inspection
    import json

    print(json.dumps(detect(probe=False), indent=2))
