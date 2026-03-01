---
name: cp-session-analyzer
description: Post-session analysis of control plane errors with GitHub issue filing
triggers:
  - "session analyzer"
  - "cp errors this session"
  - "analyze transcript"
dev_only: true
---

# CP Session Analyzer

Post-session analysis tool that parses Claude Code transcripts to find control plane
error patterns, groups them by domain/source/code, deduplicates against existing
GitHub issues, and optionally auto-files new issues.

## When to Run

- **After sessions with persistent CP errors** -- the `stop.py` hook summarizes CP
  errors at session end; use this tool for deeper analysis of the raw transcript
- **As part of `/wg-check --full`** -- validates that known CP error patterns are
  covered by existing issues
- **Manually** -- when investigating a specific class of CP failures

## Quick Start

### Basic Report

```bash
python3 .claude/skills/cp-session-analyzer/scripts/analyze_session.py <transcript_path>
```

Reads the JSONL transcript and prints a JSON report to stdout with all CP error
occurrences grouped by `{domain}/{source}/{code}`.

### Auto-File Mode

```bash
python3 .claude/skills/cp-session-analyzer/scripts/analyze_session.py <transcript_path> \
  --auto-file --repo mikeparcewski/wicked-garden
```

For each NEW error group (not already tracked in a GitHub issue), runs
`gh issue create` with the `bug` and `cp-error` labels.

## What It Does

1. **Parse** -- reads each JSONL line from the transcript
2. **Match** -- looks for CP error patterns in stderr, content, and tool_error fields:
   - `[wicked-garden] Control plane HTTP` messages
   - `tool_error` fields in `PostToolUseFailure` hook entries
   - `CP rejected` or `CP error` in any text content
3. **Extract** -- for each match: domain, source script, HTTP status code, error
   message, and timestamp
4. **Group** -- aggregates matches by `{domain}/{source}/{code}`
5. **Deduplicate** -- shells out to `gh issue list --search` to check for existing
   issues covering each group
6. **Report** -- outputs structured JSON to stdout
7. **File** (optional) -- creates GitHub issues for new, untracked error groups

## Output Format

```json
{
  "transcript": "/path/to/transcript.jsonl",
  "total_errors": 12,
  "errors": [
    {
      "domain": "crew",
      "source": "phase_manager.py",
      "code": 502,
      "message": "Bad Gateway",
      "timestamp": "2026-03-01T14:22:01Z",
      "line_number": 347
    }
  ],
  "grouped": {
    "crew/phase_manager.py/502": {
      "count": 4,
      "first_seen": "2026-03-01T14:22:01Z",
      "last_seen": "2026-03-01T14:25:33Z",
      "sample_message": "Bad Gateway"
    }
  },
  "existing_issues": [
    {"number": 87, "title": "CP Error: crew/phase_manager.py HTTP 502"}
  ],
  "new_issues": [
    {
      "group_key": "mem/memory_store.py/500",
      "title": "CP Error: mem/memory_store.py HTTP 500",
      "count": 3
    }
  ]
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | No CP errors found in transcript |
| 1    | CP errors found (regardless of whether issues were filed) |

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `<transcript_path>` | (required) | Path to JSONL transcript file |
| `--auto-file` | off | File GitHub issues for new error groups |
| `--repo OWNER/REPO` | `mikeparcewski/wicked-garden` | Target repository for issues |

## Graceful Handling

- **Missing transcript file** -- prints error to stderr, exits 1
- **`gh` CLI not installed** -- skips dedup and filing, outputs report-only
- **Malformed JSONL lines** -- skips silently, continues processing
- **No errors found** -- outputs empty report, exits 0

## Integration

This skill complements the runtime CP error tracking chain:

- `_control_plane.py` catches HTTP errors at request time
- `post_tool.py` surfaces errors per-tool via PostToolUse hook
- `stop.py` summarizes session errors at session end
- **This tool** provides deep, offline analysis of the full transcript
