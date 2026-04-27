---
name: propose-skills
description: |
  Mine recent Claude Code session transcripts to propose skills that would
  automate repetitive patterns the user actually does. Read-only MVP — outputs a
  markdown report only. No interactive UI, no scaffolding handoff in v1 (those
  are v2/v3 follow-ups).

  Use when: "find skills I should build", "what should I automate", "propose
  skills from my sessions", "mine my history for skill ideas",
  "session-mined skill builder", "skill discovery from past usage".
user-invocable: true
---

# Propose Skills (session-mined, MVP)

Detect recurring patterns in Claude Code session transcripts and emit a markdown
report of skill candidates. The framework grows from what the user *actually
does*, not from speculative authoring (#677).

## Quick Reference

```bash
# Default — current project, last 10 sessions
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/propose_skills.py"

# Scan a different project (use --project= because the slug starts with '-')
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/propose_skills.py" \
  --project=-Users-me-Projects-other --limit 25

# Print structured JSON alongside the markdown report
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/propose_skills.py" --json
```

The script prints the report path on stdout. Read the file, summarize the top 3
candidates inline, and stop — do not auto-invoke `/wg-scaffold`.

## What It Detects (3 cheap detectors, no LLM)

| Kind | Trigger |
|------|---------|
| **Repeated tool sequence** | Same ordered N-tuple of tool names appears in >= 3 distinct sessions (N in [2, 5]). Homogeneous sequences like `Bash → Bash → Bash` are filtered. |
| **Repeated prompt template** | User prompts whose first 5 normalized words match across >= 3 sessions. Generic continuations (`yes`, `continue`) and Claude Code system envelopes (`<local-command-...>`, `<command-name>`) are filtered. |
| **Repeated bash shape** | Same first 2 tokens of a bash command across >= 3 sessions (e.g. `gh pr ...`). Generic file-inspection commands (`ls`, `cat`, `cd`, ...) are filtered. |

## Pipeline

1. **Locate sessions**: `~/.claude/projects/{project-slug}/*.jsonl`. Default
   slug is derived from the current working directory.
2. **Parse**: each `.jsonl` line, extracting `tool_use` items from assistant
   messages and the leading text of user messages. Robust against malformed
   lines.
3. **Privacy filter**: skip any session whose user prompt contains the literal
   token `private` or `secret` (case-insensitive).
4. **Detect**: run the 3 detectors over the parsed sessions.
5. **Dedupe**: drop any tool-sequence candidate that is a contiguous
   subsequence of a more-frequent (or equal-frequency) longer parent.
6. **Propose**: for each candidate, build a kebab-case slug, a frontmatter-ready
   description (≤140 chars), and a `/wg-scaffold skill <name> --domain <d>`
   suggestion. Domain is inferred from tool / bash keywords.
7. **Render**: write a markdown report to
   `${TMPDIR:-/tmp}/wg-propose-skills-{timestamp}.md`. Print the path.
8. **Summarize inline**: read the top 3 candidates from the report and quote
   them in the assistant reply.

## Hard Constraints

- **Read-only.** Never writes outside `tempfile.gettempdir()`. Never modifies
  session files.
- **Local-only.** No network, no telemetry, no LLM calls inside the analyzer.
- **stdlib-only.** Cross-platform Python — `pathlib.Path`,
  `tempfile.gettempdir()`, no third-party deps.
- **Privacy-first.** Absolute paths under `$HOME` are scrubbed to `~/...` in the
  report. Sessions mentioning `private` / `secret` are skipped entirely.
- **Heuristic, not deterministic.** Treat each candidate as a *prompt for
  judgment*, not a directive. False positives are expected.

## What v1 Does NOT Do

These are explicit v2 / v3 follow-ups and out of scope for this MVP:

- Interactive accept/reject UI.
- Direct handoff to `/wg-scaffold` or the `scaffolding` skill.
- LLM-based pattern extraction or summarization.
- Cross-project mining (only the current project's sessions are scanned).
- Propose agents, hooks, or commands — the issue scope is *skills only*.

## Inline Summary Format

After running the script, the assistant should reply with something like:

```
Report: /tmp/wg-propose-skills-20260427T030000Z.md (4 candidates)

Top 3 candidates:
1. run-curl-s — `curl -s …` shell pattern, 12x across 12 sessions
2. run-pnpm-run — `pnpm run …` shell pattern, 6x across 6 sessions
3. run-lsof-ti-4321 — `lsof -ti:4321 …` shell pattern, 5x across 5 sessions

Run `/wg-scaffold skill <name> --domain <d>` for any candidate that's
worth building.
```

## Related

- `/wg-scaffold skill ...` — manual scaffolding (the v2 handoff target).
- `hookify:hookify` — different direction (proposes *hooks*, not skills).
- `claude-code-setup:claude-automation-recommender` — codebase-level analysis,
  not session-level.

## Provenance

- Issue: [#677](https://github.com/mikeparcewski/wicked-garden/issues/677)
- Helper script: `scripts/smaht/propose_skills.py`
- Tests: `tests/smaht/test_propose_skills.py` (3 detectors + dedupe + privacy
  scrub + end-to-end smoke).
- Scenario: `scenarios/smaht/propose-skills-shape.md`.
