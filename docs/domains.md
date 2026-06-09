# Domains

Domains are **skill and agent families** — the discipline expertise wicked-garden ships. They are not an orchestrator and they do not run a workflow on their own.

Work is shaped by the **9 archetypes** (triage, explore, specify, decide, ship, review, incident, build, migrate — see [Archetypes](v11/archetypes.md)). When an archetype's playbook needs domain expertise — a code review, a security scan, a requirements pass, a structural lookup — it **invokes a domain skill or agent** to get it. You can also call any domain command directly, without an archetype, when you just want that capability.

Every command follows the pattern `/wicked-garden:{domain}:{command}`. Every agent declares `subagent_type: wicked-garden:{domain}:{name}` for Task-tool dispatch.

There are **9 domains**: engineering, platform, product, data, jam, search, agentic, persona, smaht.

> **v12 cleanup (ADR 0002).** Most domain commands are *rubric-wrappers* — a checklist the agent already applies. These were **collapsed**: the rubric moved to an on-demand `skills/{domain}/refs/{name}.md` and the command now loads it and works **inline** (no `Task` dispatch hop). Dispatch is kept only where it earns it — real parallelism (multiple lenses at once), a real external tool, or an independent gate. The dispatch-only agents that nothing reaches anymore were removed; agents still referenced by a surviving command, skill, scenario, or the specialist registry stay. Capability is preserved; only the token-burning hop is gone.

---

## engineering — Software Engineering

Senior engineer, solution architect, backend/frontend specialists, debugger, technical writer, API documentarian, and migration engineer. The workhorse for `build` and `migrate` work. The wicked-patch family (`patch-plan`/`apply`/`rename`/`add-field`/`remove`) and `new-generator` are real refactor/scaffolding tools and stay as-is; `arch`/`debug`/`docs`/`plan`/`review` collapsed to inline skill-refs.

| Command | What It Does |
|---------|-------------|
| `engineering:review` | Code review from a senior engineering perspective |
| `engineering:arch` | Architecture analysis and recommendations |
| `engineering:debug` | Systematic debugging with root cause analysis |
| `engineering:plan` | Review changes against the codebase and plan steps |
| `engineering:patch-plan` | Show what a change would affect without patching |
| `engineering:apply` | Apply patches from a saved JSON file |
| `engineering:rename` | Rename a field/symbol across all usages |
| `engineering:add-field` | Add a field to an entity and propagate it |
| `engineering:remove` | Remove a field and all its usages |
| `engineering:docs` | Generate or improve documentation |
| `engineering:new-generator` | Create a language generator for wicked-patch |

**Agents**: `senior-engineer`, `solution-architect`, `backend-engineer`, `frontend-engineer`, `debugger`, `technical-writer`, `api-documentarian`, `migration-engineer` — the dispatch-only `system-designer` and `devex-engineer` were removed when their commands collapsed inline.

## platform — DevSecOps

SRE, security, compliance, incident response, and privacy engineering. Backs `ship`, `incident`, and `review` work. `security` (real gitleaks/semgrep), `toolchain`, `assert`, and `plugin-health` stay as real tools; `actions`/`audit`/`compliance`/`gh`/`health`/`incident`/`infra`/`traces` collapsed to inline skill-refs.

| Command | What It Does |
|---------|-------------|
| `platform:security` | OWASP vulnerability assessment |
| `platform:compliance` | SOC2/HIPAA/GDPR/PCI checks |
| `platform:audit` | Collect audit evidence |
| `platform:health` | System health and reliability assessment |
| `platform:incident` | Incident response and triage |
| `platform:infra` | Infrastructure review and IaC analysis |
| `platform:actions` | GitHub Actions workflow generation |
| `platform:traces` | Distributed tracing analysis |
| `platform:toolchain` | Discover and query monitoring tools |
| `platform:gh` | GitHub CLI power utilities |
| `platform:assert` | Contract assertions against subprocess outputs |
| `platform:plugin-health` | Health probes against installed plugins |

**Agents**: `security-engineer`, `sre`, `compliance-officer`, `incident-responder`, `privacy-expert` — the dispatch-only `infrastructure-engineer`, `devops-engineer`, `release-engineer`, `auditor`, `chaos-engineer`, and `observability-engineer` were removed when their commands collapsed inline.

## product — Product Management & Design

Requirements, UX, customer voice, market/value strategy, accessibility, visual design review. Backs `specify` and `explore` work.

| Command | What It Does |
|---------|-------------|
| `product:elicit` | Requirements elicitation through structured inquiry |
| `product:acceptance` | Define acceptance criteria from requirements |
| `product:listen` | Aggregate customer feedback from available sources |
| `product:analyze` | Analyze feedback for themes and sentiment |
| `product:synthesize` | Generate actionable recommendations |
| `product:align` | Facilitate stakeholder alignment |
| `product:strategy` | ROI, value proposition, competitive analysis |
| `product:ux` | UX flow design and analysis |
| `product:ux-review` | UX and design quality review |
| `product:mockup` | Wireframe and prototype generation |
| `product:screenshot` | Screenshot-based UI review (multimodal) |
| `product:a11y` | WCAG 2.1 AA accessibility audit |

> **Collapsed to skill (cleanup ADR 0002).** Most product commands now load their rubric inline from `skills/product/refs/<name>.md` and apply it directly — no `Task` dispatch hop. Dispatch is kept only where multiple lenses run in parallel: `product:ux-review --focus all` (flows + ui + a11y + research) and `product:strategy --focus all` (market + value).

**Agents**: `product-manager`, `requirements-analyst`, `ux-designer`, `user-researcher`, `market-strategist`, `value-strategist`, `a11y-expert`, `ui-reviewer` — the dispatch-only `ux-analyst`, `user-voice`, and `mockup-generator` were removed when their commands collapsed inline.

## data — Data Engineering

Data analyst, data engineer, ML engineer, and a unified data architect for OLTP + OLAP design.

| Command | What It Does |
|---------|-------------|
| `data:analyze` | Interactive data analysis on files |
| `data:data` | Data profiling and schema validation |
| `data:pipeline` | Data pipeline design and review |
| `data:ml` | ML model review and training pipeline |
| `data:ontology` | Dataset ontology recommendations |

**Agents**: `data-analyst`, `data-engineer`, `data-architect`, `ml-engineer`

## jam — AI Brainstorming

Dynamic focus groups with AI personas plus structured multi-model council sessions using external LLM CLIs. The natural fit for `explore` work.

| Command | What It Does |
|---------|-------------|
| `jam:brainstorm` | Full multi-perspective session with dynamic focus groups |
| `jam:quick` | Lightweight exploration (fewer personas, one round) |
| `jam:council` | Structured multi-model evaluation via external LLM CLIs |
| `jam:revisit` | Revisit a past brainstorm decision |

**Agents**: `brainstorm-facilitator`, `quick-facilitator`, `council`. The post-hoc viewers (`perspectives`/`thinking`/`persona`/`transcript`) were removed — niche retrieval the agent rarely reached for.

## search — Code Intelligence

Structural code intelligence on the **codegraph** graph (column-precise tree-sitter) plus the plugin's **injected edges** — bus producer→consumer, command→agent dispatch, agent→capability — that grep and a static call-graph can't see. Heavily used during `build`, `migrate`, and `review` to ground changes.

| Command | What It Does |
|---------|-------------|
| `search:index` | Refresh both layers — brain (semantic) + codegraph (structural) incl. injected edges |
| `search:blast-radius` | Dependencies and dependents of a symbol, including injected (string-keyed) links |
| `search:lineage` | Trace data/reference flow from UI to DB (or reverse) |
| `search:service-map` | Detect service architecture from infra files |
| `search:hotspots` | Most-referenced symbols (find god-objects / coupling) |

> For open-ended symbol and concept search, prefer `wicked-brain:search` / `wicked-brain:query`; the `search:*` commands cover the structural + injected-relationship analysis the brain doesn't. The thin index-admin wrappers (`categories`/`coverage`/`sources`/`quality`/`validate`) were removed — they duplicated `wicked-brain` tooling.

## agentic — Agentic Architecture

Architecture review, safety auditing, and performance analysis — for reviewing and designing AI agent systems. All four commands (`review`/`design`/`audit`/`frameworks`) collapsed to inline skill-refs (the 8-layer trust-and-safety rubric is preserved in `skills/agentic/refs/`).

| Command | What It Does |
|---------|-------------|
| `agentic:review` | Full agentic codebase review with framework detection |
| `agentic:design` | Interactive architecture design guide |
| `agentic:audit` | Trust and safety audit |
| `agentic:frameworks` | Research and compare frameworks |

**Agents**: `architect`, `safety-reviewer`, `performance-analyst` — the dispatch-only `pattern-advisor` and `framework-researcher` were removed when their commands collapsed inline.

## persona — On-Demand Personas

Invoke any specialist persona directly. Define custom personas with personality, constraints, and preferences.

| Command | What It Does |
|---------|-------------|
| `persona:as` | Invoke a named persona to perform a task |
| `persona:define` | Create or update a custom persona |
| `persona:list` | List all available personas |

**Agents**: `persona-agent` (`persona:as` builds its prompt from the registry at runtime — kept). `persona:define` collapsed to an inline skill-ref; the no-op `persona:submit` stub was deleted.

## smaht — Context Assembly

On-demand context assembly over wicked-brain and the search index. A pull-model skill — archetypes and subagents call it when they need a briefing, rather than pushing context onto every prompt.

| Command | What It Does |
|---------|-------------|
| `smaht:briefing` | What happened since the last session — recent events and updates |
| `smaht:state` | Snapshot and report current session state |
| `smaht:events-import` | Import existing domain JSON records into the event log |

> `smaht:briefing` and `events-import` are real event-store tools and stay; `smaht:state` collapsed to an inline skill-ref (its dead v6 half dropped); the weak-signal `smaht:propose-skills` was deleted.

---

## How archetypes invoke domains

An archetype playbook (`skills/archetype/refs/{archetype}.md`) doesn't hardcode a domain pipeline — it reaches for whatever expertise the work needs:

- A `build` reaches for `engineering` to implement and review, `search` to ground changes, and `wicked-testing` for evidence.
- A `review` reaches for `engineering:review`, `platform:security`, and `agentic:review` depending on the target.
- An `explore` reaches for `jam` to diverge across perspectives.
- A `specify` reaches for `product:elicit` and `product:acceptance`.
- A `ship` runs its own canary→ramp→soak rollout playbook and reaches for `platform:health`.

Domains are the *how*; archetypes are the *when* and *what shape*. The two compose — neither replaces the other.
