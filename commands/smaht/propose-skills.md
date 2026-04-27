---
description: |
  Mine recent Claude Code session transcripts to propose skills that would
  automate repetitive patterns. Read-only MVP — outputs a markdown report only.
argument-hint: "[--project=SLUG] [--limit=N]"
---

# /wicked-garden:smaht:propose-skills

Run the session-mined skill builder (#677). Reads Claude Code session transcripts
under `~/.claude/projects/` for the current project, detects repetitive patterns
(tool sequences, prompt templates, bash command shapes), and writes a markdown
report of candidate skills.

## Usage

```bash
/wicked-garden:smaht:propose-skills                          # current project, last 10 sessions
/wicked-garden:smaht:propose-skills --limit=25               # scan more sessions
/wicked-garden:smaht:propose-skills --project=-Users-me-Projects-other --limit=25
```

## Instructions

### 1. Run the analyzer

Invoke the helper script directly. It is stdlib-only and never reaches the
network. The helper prints the report path on stdout.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/propose_skills.py" $ARGUMENTS
```

### 2. Read and summarize the report

Read the file at the printed path. Quote a short inline summary for the user:

```
Report: <path> (<N> candidates)

Top 3 candidates:
1. <slug> — <one-line pattern description>, <freq>x across <sess> sessions
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
- Privacy: sessions whose user prompts mention `private` or `secret` are
  skipped; absolute paths under `$HOME` are scrubbed to `~/...` in the report.
- Interactive accept/reject UI and direct scaffolding handoff are explicit
  v2 / v3 follow-ups, not part of this MVP.
- See `skills/smaht/propose-skills/SKILL.md` for the full pipeline.
