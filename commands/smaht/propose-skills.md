---
description: |
  Mine recent Claude Code session transcripts to propose skills that would
  automate repetitive patterns. Read-only MVP — outputs a markdown report only.
argument-hint: "[--project=SLUG] [--limit=N] [--json]"
---

# /wicked-garden:smaht:propose-skills

Run the session-mined skill builder (#677). Reads Claude Code session transcripts
under `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/` for the current project,
detects repetitive patterns (tool sequences, prompt templates, bash command
shapes), and writes a markdown report of candidate skills.

## Usage

```bash
/wicked-garden:smaht:propose-skills                          # current project, last 10 sessions
/wicked-garden:smaht:propose-skills --limit=25               # scan more sessions
/wicked-garden:smaht:propose-skills --project=-Users-me-Projects-other --limit=25
/wicked-garden:smaht:propose-skills --json                   # JSON envelope (incl. candidates) on stdout
```

## Instructions

### 1. Run the analyzer

Invoke the helper script directly. It is stdlib-only and never reaches the
network. The helper honors `CLAUDE_CONFIG_DIR` so it finds sessions for users
running Claude Code with a non-default config dir.

- **Default mode** — prints the report path as a single line on stdout.
- **`--json` mode** — prints a JSON envelope (`report_path`, `sessions_root`,
  `candidates`, etc.) on stdout. The report is still written to disk; extract
  `report_path` from the JSON before reading the file.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/propose_skills.py" $ARGUMENTS
```

### 2. Read and summarize the report

Read the file at the printed path (default mode) or at `report_path` from the
JSON envelope (`--json` mode). Quote a short inline summary for the user:

```
Report: <path> (<N> candidates)

Top 3 candidates:
1. <slug> — <one-line pattern description>, <freq> occurrences across <sess> sessions
2. <slug> — ...
3. <slug> — ...

Run `/wg-scaffold skill <name> --domain <d>` for any candidate worth building.
```

### 3. Stop

This is the MVP. Do **not** auto-invoke `/wg-scaffold` or any other tool. The
user decides which (if any) candidates to scaffold.

## Notes

- Heuristic by design — false positives are expected. Treat each candidate as
  a prompt for judgment.
- Privacy: sessions whose user prompts mention `private` or `secret` (anywhere
  in the full prompt, not just the first 200 chars) are skipped; absolute paths
  under `$HOME` are scrubbed to `~/...` at path-segment boundaries in the report.
- Exit codes: `0` on graceful runs, `1` if the report file cannot be written.
- Interactive accept/reject UI and direct scaffolding handoff are explicit
  v2 / v3 follow-ups, not part of this MVP.
- See `skills/smaht/propose-skills/SKILL.md` for the full pipeline.
