# Domains

Domains are **skill families** — the discipline expertise wicked-garden ships. They are not an orchestrator and they do not run a workflow on their own.

Work is shaped by the **archetypes** (triage, explore, specify, decide, ship, review, incident, build, migrate, modernize — see [Archetypes](v11/archetypes.md)). When an archetype's playbook needs domain expertise — a code review, a security scan, a requirements pass, a structural lookup — it **invokes a domain skill** to get it. You can also invoke any domain skill directly, without an archetype, when you just want that capability.

The plugin is **skills-only** (v12.25). Each domain is one consolidated, user-invokable skill — `skills/{domain}/SKILL.md`, frontmatter name `wicked-garden-{domain}` — that routes to its **actions** (the former `/wicked-garden:{domain}:{command}` surfaces) and loads rubrics on demand from `skills/{domain}/refs/` and nested knowledge modules. The former dispatch agents are **fork worker skills** — `skills/{domain}-{role}/SKILL.md` with `context: fork`, frontmatter name `wicked-garden-{domain}-{role}` — reached by `Skill()`/`Task()` dispatch, never invoked as entry points. Invoke a domain action as `/wicked-garden-{domain} {action} [args]` (or just describe what you want — the skill descriptions carry the triggers).

There are **9 domains**: engineering, platform, product, data, jam, search, agentic, persona, smaht.

> **v12 cleanup (ADR 0002).** Most former domain commands were *rubric-wrappers* — a checklist the agent already applies. These were **collapsed**: the rubric moved to an on-demand `skills/{domain}/refs/{name}.md` and the action now loads it and works **inline** (no `Task` dispatch hop). Dispatch is kept only where it earns it — real parallelism (multiple lenses at once), a real external tool, or an independent gate. The dispatch-only agents that nothing reaches anymore were removed; workers still referenced by a surviving action, skill, scenario, or the specialist registry live on as fork skills. Capability is preserved; only the token-burning hop is gone.

---

## engineering — Software Engineering

`wicked-garden-engineering` — the workhorse for `build` and `migrate` work. The five review/analysis actions run inline; the wicked-patch family is the real refactor/scaffolding tool (nested skill `wicked-garden-engineering-patch`). Code-quality, backend/frontend, debugging, and technical-writing work run inline via the domain skill (the dedicated `senior-engineer`/`backend-engineer`/`frontend-engineer`/`debugger`/`technical-writer` agents were cut in the v12 lift eval — they produced zero measured lift over the base model; see `tests/agents/EVAL_RESULTS.md`).

| Action | What It Does |
|--------|-------------|
| `review` | Code review from a senior engineering perspective |
| `arch` | Architecture analysis and recommendations |
| `debug` | Systematic debugging with root cause analysis |
| `plan` | Review changes against the codebase and plan steps |
| `docs` | Generate or improve documentation |

The deterministic multi-file transformations live in the nested **patch** skill (`skills/engineering/patch/`): `patch-plan` (show what a change would affect), `apply` (apply patches from a saved JSON file), `rename`, `add-field`, `remove`, and `new-generator` (create a language generator for wicked-patch).

**Fork workers**: `wicked-garden-engineering-solution-architect` (system design, ADRs), `wicked-garden-engineering-migration-engineer` (expand-contract schema/data migrations), `wicked-garden-engineering-api-documentarian` (OpenAPI/endpoint reference docs). The dispatch-only `system-designer` and `devex-engineer` were removed when their commands collapsed inline.

## platform — DevSecOps

`wicked-garden-platform` — SRE, security, compliance, incident response, and privacy engineering. Backs `ship`, `incident`, and `review` work. `security` (real gitleaks/semgrep) stays a real tool; the rest are inline actions or nested sub-skills.

| Action | What It Does |
|--------|-------------|
| `security` | OWASP vulnerability assessment (real scanners + triage) |
| `incident` | Incident response and triage |
| `infra` | Infrastructure review and IaC analysis |
| `traces` | Distributed tracing analysis |

Nested sub-skills under `skills/platform/`: `audit` (collect audit evidence), `compliance` (SOC2/HIPAA/GDPR/PCI checks), `errors`, `health` (system health and reliability), `observability` (plugin diagnostics, hook traces, contract assertions, toolchain discovery), `gh-cli` / `glab-cli` (GitHub/GitLab CLI power utilities), `github-actions` / `gitlab-ci` (workflow generation), `prereq-doctor`, `gate-benchmark-rebaseline`, and `peer-health` (wicked-* peer reachability probes).

**Fork workers**: `wicked-garden-platform-security-engineer`, `wicked-garden-platform-compliance-officer`, `wicked-garden-platform-privacy-expert` — the dispatch-only `infrastructure-engineer`, `devops-engineer`, `release-engineer`, `auditor`, `chaos-engineer`, and `observability-engineer` were removed when their commands collapsed inline; `sre` and `incident-responder` were cut in the v12 lift eval (zero measured lift), with incident/log work now handled inline via the `incident` action + errors/observability sub-skills.

## product — Product Management & Design

`wicked-garden-product` — requirements, UX, customer voice, market/value strategy, accessibility, visual design review. Backs `specify` and `explore` work.

| Action | What It Does |
|--------|-------------|
| `elicit` | Requirements elicitation through structured inquiry |
| `acceptance` | Define acceptance criteria from requirements |
| `listen` | Aggregate customer feedback from available sources |
| `analyze` | Analyze feedback for themes and sentiment |
| `synthesize` | Generate actionable recommendations |
| `align` | Facilitate stakeholder alignment |
| `strategy` | ROI, value proposition, competitive analysis |
| `ux` | UX flow design and analysis |
| `ux-review` | UX and design quality review |
| `mockup` | Wireframe and prototype generation |
| `screenshot` | Screenshot-based UI review (multimodal) |
| `a11y` | WCAG 2.1 AA accessibility audit |

> **Collapsed to inline (cleanup ADR 0002).** Most product actions load their rubric from `skills/product/refs/<name>.md` and apply it directly — no `Task` dispatch hop. Dispatch is kept only where multiple lenses run in parallel: `ux-review --focus all` (flows + ui + a11y + research) and `strategy --focus all` (market + value).

**Fork workers**: `wicked-garden-product-requirements-analyst`, `wicked-garden-product-ux-designer`, `wicked-garden-product-value-strategist`, `wicked-garden-product-a11y-expert`, `wicked-garden-product-ui-reviewer` — the dispatch-only `ux-analyst`, `user-voice`, and `mockup-generator` were removed when their commands collapsed inline; `product-manager`, `user-researcher`, and `market-strategist` were cut in the v12 lift eval (zero measured lift). The user-researcher lens is folded into `ux-designer`; the market-strategist lens runs inline in the `strategy` action (value lens kept via `value-strategist`).

### Requirements skills — which one? (router)

The `product` domain ships four `requirements-*` sub-skills (under `skills/product/`)
that are **stages of one lifecycle**, not duplicates. Reach for them in this order:

| Skill | Use it when | Hands off to |
|-------|-------------|--------------|
| `requirements-analysis` | Turning a vague idea/stakeholder ask into structured user stories + ACs. For complexity ≥ 3 or compliance work it defaults to **graph mode**. | `requirements-graph` (graph mode) |
| `requirements-graph` | Laying out ACs as atomic markdown nodes with traceable frontmatter edges (filesystem-as-graph). | `requirements-navigate` |
| `requirements-navigate` | Querying/maintaining an existing graph — coverage reports, gap-finding, `meta.md` refresh, lint. | — |
| `requirements-migrate` | One-shot converting a monolithic requirements doc into the graph structure. | `requirements-navigate` |

> Quick decision: **starting fresh →** `requirements-analysis`. **defining the graph directly →** `requirements-graph`. **already have a graph →** `requirements-navigate`. **have a legacy doc to convert →** `requirements-migrate`. For *testable* "definition of done" use the `acceptance` action (sub-skill `acceptance-criteria`); for stakeholder *disagreement* use the `align` action.

### "review" appears in three domains — which one? (router)

`review` is intentionally split across three domains by *what is being reviewed*.
They do not overlap; pick by target:

| Surface | Reviews | Output |
|---------|---------|--------|
| engineering `review` | Source code — quality, patterns, maintainability, security/perf focus | findings list (advisory) |
| agentic `review` | An *agentic AI system* — framework detection, agent topology, safety/performance | remediation roadmap |
| archetype `review` | Any artifact/PR/commit as the v11 **review work-shape** | a HARD verdict (APPROVE / CONDITIONAL / REJECT) + remediation |
| product `ux-review` | UX/visual/accessibility quality of a UI | UX findings |

> Quick decision: **code →** engineering `review`. **an AI agent system →** agentic `review`. **a UI →** product `ux-review`. **need a binding go/no-go verdict on anything →** archetype `review` (the only one that gates).

## data — Data Engineering

`wicked-garden-data` — data analyst, data engineer, ML engineer, and a unified data architect for OLTP + OLAP design.

| Action | What It Does |
|--------|-------------|
| `analyze` | Interactive data analysis on files (plain English → SQL via DuckDB) |
| `profile` / `validate` / `quality` | Data profiling, schema validation, quality reports |
| `pipeline` | Data pipeline design and review |
| `ml` | ML model review and training pipeline design |
| `ontology` | Dataset ontology recommendations |

**Fork worker**: `wicked-garden-data-engineer` — `data-analyst`, `data-architect`, and `ml-engineer` were cut in the v12 lift eval (zero measured lift); their work routes to the data-engineer worker or runs inline via the `analyze` action.

## jam — AI Brainstorming

`wicked-garden-jam` — dynamic focus groups with AI personas plus structured multi-model council sessions using external LLM CLIs. The natural fit for `explore` work.

| Action | What It Does |
|--------|-------------|
| `brainstorm` | Full multi-perspective session with dynamic focus groups |
| `quick` | Lightweight exploration (fewer personas, one round — inline) |
| `council` | Structured multi-model evaluation via external LLM CLIs |
| `revisit` | Revisit a past brainstorm decision (inline, interactive) |

**Fork workers**: `wicked-garden-jam-brainstorm-facilitator`, `wicked-garden-jam-council`. The `quick` facilitation runs inline from `refs/quick.md`; the post-hoc viewers (`perspectives`/`thinking`/`persona`/`transcript`) were removed — niche retrieval the agent rarely reached for.

## search — Code Intelligence

`wicked-garden-search` — structural code intelligence on the **codegraph** graph (column-precise tree-sitter) plus the plugin's **injected edges** — bus producer→consumer, dispatch, capability — that grep and a static call-graph can't see. Heavily used during `build`, `migrate`, and `review` to ground changes.

| Action | What It Does |
|--------|-------------|
| `index` | Refresh the estate code graph (static + injected edges) |
| `blast-radius` | Dependencies and dependents of a symbol, including injected (string-keyed) links |
| `lineage` | Trace data/reference flow from UI to DB (or reverse) |
| `service-map` | Detect service architecture from infra files |
| `hotspots` | Most-referenced symbols (find god-objects / coupling) |
| `narrate` | Codebase orientation / architecture walkthrough (nested `codebase-narrator` skill) |

> For open-ended concept/memory search, prefer the `wicked-garden-mem` skill (recall/answer); the search actions cover the structural + injected-relationship analysis. The thin index-admin wrappers (`categories`/`coverage`/`sources`/`quality`/`validate`) were removed — they duplicated backend tooling.

## agentic — Agentic Architecture

`wicked-garden-agentic` — architecture review, safety auditing, and performance analysis for reviewing and designing AI agent systems. All four actions run inline from `skills/agentic/refs/` (the 8-layer trust-and-safety rubric is preserved there).

| Action | What It Does |
|--------|-------------|
| `review` | Full agentic codebase review with framework detection |
| `design` | Interactive architecture design guide |
| `audit` | Trust and safety audit (GDPR/HIPAA/SOC2/NIST standards) |
| `frameworks` | Research and compare frameworks |

**Fork workers**: `wicked-garden-agentic-architect`, `wicked-garden-agentic-safety-reviewer`, `wicked-garden-agentic-performance-analyst` — the dispatch-only `pattern-advisor` and `framework-researcher` were removed when their commands collapsed inline.

## persona — On-Demand Personas

`wicked-garden-persona` — invoke any specialist persona directly. Define custom personas with personality, constraints, and preferences.

| Action | What It Does |
|--------|-------------|
| `as` | Invoke a named persona to perform a task |
| `define` | Create or update a custom persona |
| `list` | List all available personas (Methodology vs Generic tiers) |

**Fork worker**: `wicked-garden-persona-agent` (the `as` action builds its prompt from the registry at runtime and dispatches to it — kept). `define` runs inline from `refs/define.md`; the no-op `persona:submit` stub was deleted.

## smaht — Context Assembly

`wicked-garden-smaht` — on-demand context assembly over the wicked-estate knowledge layer and the search index. A pull-model skill — archetypes and subagents call it when they need a briefing, rather than pushing context onto every prompt.

| Action | What It Does |
|--------|-------------|
| `briefing` | What happened since the last session — recent events and updates |
| `state` | Snapshot and report current session state |
| `events-import` | Import existing domain JSON records into the event log |
| `intent` | Set or inspect the active session intent (nested `intent` sub-skill) |

> `briefing` and `events-import` are real event-store tools and stay; `state` runs inline from `refs/state.md` (its dead v6 half dropped). Nested sub-skills: `discovery`, `intent`, `propose-skills`.

---

## How archetypes invoke domains

An archetype playbook (`skills/archetype/refs/{archetype}.md`) doesn't hardcode a domain pipeline — it reaches for whatever expertise the work needs:

- A `build` reaches for `engineering` to implement and review, `search` to ground changes, and `qe` for evidence.
- A `review` reaches for engineering `review`, platform `security`, and agentic `review` depending on the target.
- An `explore` reaches for `jam` to diverge across perspectives.
- A `specify` reaches for product `elicit` and product `acceptance`.
- A `ship` runs its own canary→ramp→soak rollout playbook and reaches for the platform `health` sub-skill.

Domains are the *how*; archetypes are the *when* and *what shape*. The two compose — neither replaces the other.
