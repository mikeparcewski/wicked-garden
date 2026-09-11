# Agent Instructions

**The canonical agent instructions for this repository live in [`.claude/CLAUDE.md`](.claude/CLAUDE.md).**
Read that file — it is the single source of truth for how to work in wicked-garden:
conventions, v11/v12 architecture, evidence-re-derivation, delegation, code search,
memory, storage, and security.

> **Why (identity):** see [`ETHOS.md`](ETHOS.md) for what wicked-garden believes / refuses /
> optimizes for. `CLAUDE.md` is *how to act*; `ETHOS.md` is *why*.

This file is intentionally a thin pointer so there is exactly one source of truth.
Other AI coding tools (Codex, Cursor, Aider, OpenCode, Zed/ACP, …) that read `AGENTS.md`:
follow the link above to `.claude/CLAUDE.md`.

## Cross-CLI skills (portability rule) — mirrored from `.claude/CLAUDE.md`

A skill's text must work wherever it is installed — Claude Code (plugin), Codex, OpenCode, Pi and Antigravity (skills-only, flat by name) and wicked-crew's snapshot. Therefore, under `skills/`: (1) refer to your own files by a path relative to the skill's base directory (`refs/plan.md`), never `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_SKILL_DIR}` or `../`; (2) refer to another skill by its **name** (`wicked-garden-qe`, "its `refs/review.md`"), never by a filesystem path — the installer lays skills out flat by name; (3) run shared runtime code only through the launcher: `wicked-garden run scripts/<path> [args]` (or `wicked-garden path <dir>`, `wicked-garden python -c …`), include the standard `## Runtime` block once (exact text in `tests/portability_rules.json`), and give a manual alternative for hosts without it; (4) write harness features with a fallback: "invoke skill X (Skill tool) — otherwise open its SKILL.md and follow it inline", "ask the user (AskUserQuestion where available, else plain text and wait)"; (5) `context: fork` and `allowed-tools` are Claude Code loading hints, fine to keep — say in the body what to do when the harness cannot fork. Hooks (`hooks/`) are Claude-plugin mechanics and keep `${CLAUDE_PLUGIN_ROOT}`. `tests/test_skill_portability.py` fails the build on any violation; run `python3 scripts/wg/portability_codemod.py --dry-run` to see the fix. The launcher lives once in `scripts/wicked-garden.mjs` (twins `scripts/wicked-garden`, `scripts/wicked-garden.cmd`; npm bin `wicked-garden run|python|path|root|doctor`); root order `WICKED_GARDEN_ROOT` → `CLAUDE_PLUGIN_ROOT` → its own package; it never writes under the root.
