---
description: Show all available wicked-garden domains and commands
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# Wicked Garden Help

The Wicked Garden Marketplace — gap-filling capabilities for modern coding-agent
harnesses. It reads each prompt as one or more **work-shape archetypes** (v11) and
applies the right rigor/gate, re-derives "done" from evidence, surfaces relationships
grep can't see, and otherwise stays out of the harness's way.

## Headline Commands

| Command | What it does |
|---------|--------------|
| `/wicked-garden:prove` | Re-derive "done" from recorded evidence (the produces-gate). |
| `/wicked-garden:compile` | Emit a self-contained, vault-backed gate into any repo. |
| `/wicked-garden:intent` | Set or inspect the active work intent for the session. |
| `/wicked-garden:deliberate` | Critically analyze a request before doing the work — challenge assumptions, find root causes, propose better approaches. |
| `/wicked-garden:where-am-i` | Orient: show current phase, archetype, and project state. |
| `/wicked-garden:setup` | First-run setup and dependency/peer checks. |
| `/wicked-garden:reset` | Reset session/project state. |
| `/wicked-garden:report-issue` | File a structured issue against wicked-garden. |

## Archetypes (v11 work-shape model)

`/wicked-garden:archetype:{name}` runs a work-shape playbook. Each prompt classifies
into one or more of these; run them in dependency order.

| Archetype | Shape |
|-----------|-------|
| `archetype:triage` | classify → routing decision |
| `archetype:explore` | frame → diverge → converge |
| `archetype:specify` | elicit → structure → validate (SMART acceptance criteria) |
| `archetype:decide` | brief → options → score → record (ADR) |
| `archetype:ship` | canary → ramp → full → soak (rollout verdict) |
| `archetype:review` | scope → assess → findings → remediate-or-accept (hard verdict) |
| `archetype:incident` | triage → investigate → mitigate → resolve → followup |
| `archetype:build` | plan → implement → test → review |
| `archetype:migrate` | plan → expand → backfill → cutover → contract |

## Domains

| Domain | Description | Key Commands |
|--------|-------------|--------------|
| **agentic** | Design, review, and audit agentic AI systems | `agentic:design`, `agentic:review`, `agentic:audit`, `agentic:frameworks` |
| **archetype** | The 9 v11 work-shape playbooks (see table above) | `archetype:build`, `archetype:review`, `archetype:ship` |
| **data** | Data analysis, pipelines, ML, and ontology recommendations | `data:analyze`, `data:pipeline`, `data:ml`, `data:ontology` |
| **engineering** | Architecture, code review, debugging, docs, planning, and deterministic multi-file code transformations | `engineering:review`, `engineering:debug`, `engineering:arch`, `engineering:plan`, `engineering:apply` |
| **jam** | Multi-model brainstorming + structured council (independent second opinion) | `jam:council`, `jam:brainstorm`, `jam:quick`, `jam:revisit` |
| **persona** | Define and invoke named personas to perform work with a specific lens | `persona:as`, `persona:define`, `persona:list` |
| **platform** | Security, infrastructure, compliance, CI/CD, incidents, traces, and plugin diagnostics | `platform:security`, `platform:compliance`, `platform:incident`, `platform:health` |
| **product** | Requirements, customer feedback, strategy, UX, accessibility, and design review | `product:elicit`, `product:acceptance`, `product:analyze`, `product:strategy`, `product:ux-review` |
| **search** | Structural code search, lineage, blast-radius, and codebase intelligence | `search:blast-radius`, `search:lineage`, `search:hotspots`, `search:service-map`, `search:index` |
| **smaht** | On-demand context assembly + session briefing from brain, search, and the event log | `smaht:briefing`, `smaht:state`, `smaht:events-import` |

> **Memory & search are provided by sibling plugins**, not a wicked-garden domain:
> use `wicked-brain:memory` / `wicked-brain:query` for cross-session memory, and
> `wicked-brain:search` / `wicked-brain:graph` for code search and relationship graphs.

## Quick Start

### Read a prompt's work shape
```
/wicked-garden:where-am-i
```

### Build a feature (build archetype)
```
/wicked-garden:archetype:build "add a user authentication system"
```

### Re-derive "done" from evidence
```
/wicked-garden:prove
```

### Review code
```
/wicked-garden:engineering:review ./src
```

### Get an independent multi-model second opinion
```
/wicked-garden:jam:council "should we adopt event sourcing here?"
```

### Search code relationships
```
wicked-brain:search "handlePayment"
/wicked-garden:search:blast-radius src/payments.py
```

### Store a decision
Use `wicked-brain:memory` (store mode) to persist a decision directly.

## How It Works

1. Every prompt is classified into one or more **archetypes** by the
   `UserPromptSubmit` hook; each archetype owns its own phase shape, HITL
   discipline, and cost band (steering, not a fixed pipeline).
2. **smaht** assembles context on demand (pull-model) from brain, search, and
   the unified event log — there is no per-prompt push.
3. **Specialist domains** (engineering, platform, product, data, agentic, jam,
   search) provide deep expertise the harness routes into.
4. **`prove`** re-derives an archetype's "done" through the evidence gate rather
   than trusting a "tests pass" claim.
5. **State** persists across sessions via wicked-brain memory, search indexes,
   the event log, and native tasks.

## Getting Domain Help

Run `/wicked-garden:{domain}:{command}` for any command. Run a bare
`/wicked-garden:archetype:{name}` to invoke a work-shape playbook. Use
`/wicked-garden:help` to return to this overview.
```
