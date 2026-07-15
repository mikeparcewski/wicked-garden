---
name: wicked-garden-core
description: |
  Core utility surface for the wicked-garden plugin: help/overview, first-run
  setup + codebase onboarding, the wicked-* peer installer, selective state
  reset, the where-am-i path manifest, and structured issue filing.

  Use when: "wicked-garden help", "show wicked-garden commands", "what can
  wicked-garden do", "set up wicked-garden", "setup", "--reconfigure",
  "onboard this codebase", "install wicked tools", "add peers", "install
  layers", "reset wicked-garden", "clear state", "--list-projects",
  "where am I", "path manifest", "report issue", "file a bug",
  "--list-unfiled", or any former /wicked-garden:{help|setup|install|reset|
  where-am-i|report-issue} invocation.
user-invocable: true
allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write", "Grep", "Skill", "Agent"]
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# Wicked Garden Core

One entry point for the plugin's utility verbs. **Never fork this skill** — the
setup / install / reset / report-issue actions are interactive wizards that must
converse with the user (AskUserQuestion, or plain-text STOP-and-wait in
dangerous mode). Run everything inline in the parent context.

## Action router

| Action | Trigger phrases / args | How |
|--------|------------------------|-----|
| `help` | no args, "help", "overview" | Default — show the overview below |
| `setup` | "setup", "--reconfigure", "onboard this codebase" | `Read("${CLAUDE_PLUGIN_ROOT}/skills/core/refs/setup.md")` and follow it |
| `install` | "install", "add peers", "install layers" | `Read("${CLAUDE_PLUGIN_ROOT}/skills/core/refs/install.md")` and follow it |
| `reset` | "reset", "clear state", `--all` `--only` `--keep` `--force` `--list-projects` `--all-projects` | `Read("${CLAUDE_PLUGIN_ROOT}/skills/core/refs/reset.md")` and follow it |
| `where-am-i` | "where am I", "path manifest", `--fence` `--env` | Inline section below |
| `report-issue` | "report issue", "file a bug", `bug` `ux-friction` `unmet-outcome` `--list-unfiled` | `Read("${CLAUDE_PLUGIN_ROOT}/skills/core/refs/report-issue.md")` and follow it |

## Action: help (default)

Show this overview when invoked with no action or asked for help.

The Wicked Garden Marketplace — gap-filling capabilities for modern coding-agent
harnesses. It reads each prompt as one or more **work-shape archetypes** (v11) and
applies the right rigor/gate, re-derives "done" from evidence, surfaces relationships
grep can't see, and otherwise stays out of the harness's way.

### Headline skills

| Skill | What it does |
|-------|--------------|
| `wicked-garden-prove` | Re-derive "done" from recorded evidence (the produces-gate). Its `compile` action emits a self-contained, vault-backed gate into any repo. |
| `wicked-garden-core` | This skill — setup, install, reset, where-am-i, report-issue, help. |
| `wicked-garden-deliberate` | Critically analyze a request before doing the work — challenge assumptions, find root causes, propose better approaches. |
| `wicked-garden-smaht` | On-demand context assembly + session briefing; its `intent` action sets or inspects the active session intent. |
| `wicked-garden-archetype` | The v11 work-shape playbooks (below). |

### Archetypes (v11 work-shape model)

Invoke the `wicked-garden-archetype` skill with a work-shape name to run its
playbook. Each prompt classifies into one or more of these; run them in
dependency order.

| Archetype | Shape |
|-----------|-------|
| `triage` | classify → routing decision |
| `explore` | frame → diverge → converge |
| `specify` | elicit → structure → validate (SMART acceptance criteria) |
| `decide` | brief → options → score → record (ADR) |
| `ship` | canary → ramp → full → soak (rollout verdict) |
| `review` | scope → assess → findings → remediate-or-accept (hard verdict) |
| `incident` | triage → investigate → mitigate → resolve → followup |
| `build` | plan → implement → test → review |
| `migrate` | plan → expand → backfill → cutover → contract |

### Domain skills

Each domain is one consolidated skill that routes to its actions.

| Skill | Description | Key actions |
|-------|-------------|-------------|
| `wicked-garden-agentic` | Design, review, and audit agentic AI systems | review · design · audit · frameworks |
| `wicked-garden-data` | Data analysis, pipelines, ML, and ontology recommendations | analyze · pipeline · ml · ontology |
| `wicked-garden-engineering` | Architecture, code review, debugging, docs, planning, and deterministic multi-file code transformations | review · debug · arch · plan · apply |
| `wicked-garden-jam` | Multi-model brainstorming + structured council (independent second opinion) | council · brainstorm · quick · revisit |
| `wicked-garden-domain` | Extract a codebase's domain model — business rules + provenance, entities, requirements on the estate graph — a foundational substrate build/migrate/review/modernize all consume (none own) | extractor · modeler · coverage |
| `wicked-garden-persona` | Define and invoke named personas to perform work with a specific lens | as · define · list |
| `wicked-garden-platform` | Security, infrastructure, compliance, CI/CD, incidents, traces, and plugin diagnostics | security · compliance · incident · health |
| `wicked-garden-product` | Requirements, customer feedback, strategy, UX, accessibility, and design review | elicit · acceptance · analyze · strategy · ux-review |
| `wicked-garden-search` | Structural code search, lineage, blast-radius, and codebase intelligence | blast-radius · lineage · hotspots · service-map · index |
| `wicked-garden-smaht` | On-demand context assembly + session briefing from brain, search, and the event log | briefing · state · events-import · intent |

> **Memory & search are provided by sibling plugins**, not a wicked-garden domain:
> use `wicked-brain:memory` / `wicked-brain:query` for cross-session memory, and
> `wicked-brain:search` / `wicked-brain:graph` for code search and relationship graphs.

### Quick start

- **Orient**: invoke this skill's `where-am-i` action.
- **Build a feature**: `wicked-garden-archetype` with `build "add a user authentication system"`.
- **Re-derive "done" from evidence**: `wicked-garden-prove`.
- **Review code**: `wicked-garden-engineering` with `review ./src`.
- **Independent multi-model second opinion**: `wicked-garden-jam` with `council "should we adopt event sourcing here?"`.
- **Search code relationships**: `wicked-brain:search "handlePayment"`, then `wicked-garden-search` with `blast-radius src/payments.py`.
- **Store a decision**: `wicked-brain:memory` (store mode).

### How it works

1. Every prompt is classified into one or more **archetypes** by the
   `UserPromptSubmit` hook; each archetype owns its own phase shape, HITL
   discipline, and cost band (steering, not a fixed pipeline).
2. **smaht** assembles context on demand (pull-model) from brain, search, and
   the unified event log — there is no per-prompt push.
3. **Specialist domains** (engineering, platform, product, data, agentic, jam,
   search) provide deep expertise the harness routes into.
4. **`wicked-garden-prove`** re-derives an archetype's "done" through the
   evidence gate rather than trusting a "tests pass" claim.
5. **State** persists across sessions via wicked-brain memory, search indexes,
   the event log, and native tasks.

### Getting more help

Invoke any domain skill with an action name (e.g. `wicked-garden-engineering`
with `review`). Invoke `wicked-garden-core` with no action to return to this
overview.

## Action: where-am-i

Read-only query that prints a single compact manifest of the five storage
roots used by wicked-garden dispatches. Subagents should include
"invoke wicked-garden-core where-am-i first" as a directive instead of
hand-enumerating paths — it costs fewer tokens and closes a class of
path-mismatch bugs. Provenance: Issue #576.

Arguments: `--json` (JSON manifest, default) · `--fence` (wrap the JSON in a
```json fence for paste) · `--env` (substitute env-var forms such as
`$CLAUDE_PLUGIN_ROOT` where the corresponding environment variable is present).

Invoke the helper script and stream its stdout to the user verbatim. This
action is a thin wrapper — do not re-interpret the manifest.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/where_am_i.py" "$@"
```

Output shape:

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

Any field that cannot be resolved emits `null` and logs a one-line note to
stderr. The script never raises and is safe to invoke from any cwd. Graceful
degradation: missing `CLAUDE_PLUGIN_ROOT` falls back to the checkout inferred
from the script location; missing brain config emits `"brain": null`; missing
bus DB emits `"bus_db": null`; no active crew project emits
`"active_project_id": null` and points `project_artifacts` at the crew
projects domain root.
