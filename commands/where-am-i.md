---
allowed-tools: ["Bash"]
description: "Emit a compact path manifest (plugin, source, project, brain, bus) for the current session"
argument-hint: "[--fence] [--env]"
---

# /wicked-garden:where-am-i

Read-only query that prints a single compact manifest of the five storage
roots used by wicked-garden dispatches. Subagents should include
"run /wicked-garden:where-am-i first" as a directive instead of
hand-enumerating paths — it costs fewer tokens and closes a class of
path-mismatch bugs.

Provenance: Issue #576.

## Arguments

- `--json` — Emit JSON manifest (default).
- `--fence` — Wrap the JSON manifest in a ```json fence for paste.
- `--env` — Substitute env-var forms (e.g. `$CLAUDE_PLUGIN_ROOT`) where
  the corresponding environment variable is present.

## Output shape

```json
{
  "plugin_root": "/abs/path",
  "source_cwd": "/abs/path",
  "active_project_id": "string-or-null",
  "project_artifacts": "/abs/path/to/projects-or-specific-project",
  "brain": {"path": "/abs/path", "port": 4243},
  "bus_db": "/abs/path"
}
```

Any field that cannot be resolved emits `null` and logs a one-line note
to stderr. The command never raises and is safe to invoke from any cwd.

## Instructions

Invoke the helper script and stream its stdout to the user verbatim.
This command is a thin wrapper — do not re-interpret the manifest.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/where_am_i.py" "$@"
```

## Graceful Degradation

- Missing `CLAUDE_PLUGIN_ROOT`: falls back to the checkout inferred from
  the script location.
- Missing brain config: emits `"brain": null` and continues.
- Missing bus DB: emits `"bus_db": null` and continues.
- No active crew project: emits `"active_project_id": null` and points
  `project_artifacts` at the crew projects domain root.
