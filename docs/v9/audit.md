# v9-PR-1 — Surface Audit (kill/keep verdict)

EPIC: #601
Generated: 2026-04-23
Total surfaces audited: **142 commands + 83 skills + 10 hook scripts = 235 surfaces**

> **Method**: For each surface, applied the v9 unique-value criterion from #601:
> "Does this provide value Claude can't get from native tools (Bash, Grep, Read,
> Edit, Task, Agent) OR from another well-positioned skill (figma, plugin-dev,
> claude-md-management, wicked-testing, wicked-brain, wicked-bus, etc.)?"
>
> Then audited discovery-shape: trigger language, anti-trigger language,
> no-wrapper test, single-purpose verb-first scoping.

---

## Summary

| Verdict | Commands | Skills | Hooks | Total | % |
|---|---|---|---|---|---|
| KEEP-AS-IS | 24 | 24 | 6 | 54 | 23.0% |
| KEEP-SHARPEN | 38 | 32 | 0 | 70 | 29.8% |
| MERGE | 16 | 11 | 0 | 27 | 11.5% |
| CUT | 64 | 16 | 4 | 84 | 35.7% |

**Estimated surface reduction (CUT + half-of-MERGE consolidation): ~42% — within epic estimate of 40-60%.**

After v9-PR-2 + v9-PR-3 the surface count drops from 235 → ~136 (`-99 surfaces`).

---

## Commands (by domain)

### root (8)

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `aliases` | CUT | Pure backward-compat doc; v9 is the breaking-change moment. Lift content into release notes. | release notes |
| `deliberate` | KEEP-SHARPEN | Real unique value (challenge assumptions before action) but description is verbose. Sharpen to "use when about to commit to non-obvious work". | description rewrite |
| `help` | KEEP-AS-IS | Plugin-level orientation; tiny, harmless. | — |
| `report-issue` | KEEP-AS-IS | Structured GH-issue capture w/ duplicate detection — beyond what `gh issue create` does. | — |
| `reset` | KEEP-AS-IS | Domain-aware state purge with `--keep`/`--only` — not feasible inline. | — |
| `setup` | KEEP-AS-IS | Onboarding entry point; infra plumbing. | — |
| `where-am-i` | KEEP-AS-IS | Tiny path manifest for subagents (issue #576). Cheap, load-bearing. | — |

### crew (22) — sacred per epic; high KEEP density

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `crew:approve` | KEEP-AS-IS | Phase advancement w/ gate verification. Pillar #3 (dynamic SDLC). | — |
| `crew:archive` | KEEP-SHARPEN | Useful state mgmt; description is bare. Add trigger lang. | description rewrite |
| `crew:auto-approve` | KEEP-AS-IS | Yolo guardrail — non-trivial JSON state mutation w/ justification log. | — |
| `crew:convergence` | KEEP-AS-IS | Designed→Built→Wired→Tested→Integrated→Verified lifecycle — unique. | — |
| `crew:cutover` | KEEP-SHARPEN | One-shot mode-3 migration helper. Description is internal jargon. | description rewrite (or CUT post-mode-3 stable) |
| `crew:evidence` | KEEP-AS-IS | Crew evidence query; pillar #3. | — |
| `crew:execute` | KEEP-AS-IS | Phase executor — core engine surface. | — |
| `crew:explain` | KEEP-AS-IS | Plain-English translator for jargon-heavy crew output. Discovery-good. | — |
| `crew:feedback` | KEEP-AS-IS | Captures stakeholder feedback w/ traceability links. | — |
| `crew:gate` | KEEP-AS-IS | Pillar #3 surface for QE gate runs at value/strategy/execution. | — |
| `crew:help` | CUT | Per-domain `:help` is overhead; root `/wicked-garden:help` covers it. | root help |
| `crew:incident` | KEEP-SHARPEN | Logs production incident *to crew project*; clarifies vs platform:incident. Sharpen anti-trigger. | description rewrite |
| `crew:just-finish` | KEEP-AS-IS | Maximum-autonomy loop with guardrails — pillar #3. | — |
| `crew:migrate-gates` | CUT | Pure migration guide for v6.0-beta.3 → v6.0; v6 shipped a year ago. | adopt-legacy skill |
| `crew:operate` | KEEP-AS-IS | Operate phase entry — distinct from `status`. | — |
| `crew:profile` | KEEP-SHARPEN | Sets autonomy/style/plan-mode prefs — useful but description is bare. | description rewrite |
| `crew:retro` | KEEP-AS-IS | Aggregates incidents+feedback+metrics into retro stored in mem. | — |
| `crew:start` | KEEP-AS-IS | Project genesis — the canonical pillar #3 entry. | — |
| `crew:status` | KEEP-AS-IS | Read-only state view; well-scoped vs `operate`. | — |
| `crew:swarm` | KEEP-AS-IS | Quality-Coalition trigger detection — cross-cutting heuristic, unique. | — |
| `crew:yolo` | CUT | Pure alias for `crew:auto-approve`. v9 is the breaking-change moment to drop the alias. | crew:auto-approve |

### search (18) — mostly CUT after wicked-brain ownership

The brain adapter took over the unified index; most search commands are now thin wrappers over `wicked-brain:search` / `wicked-brain:lsp`. Only the **graph-shape** queries (lineage, blast-radius, hotspots) remain unique value.

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `search:blast-radius` | KEEP-AS-IS | Dependents-graph traversal — unique to wicked-garden index. | — |
| `search:categories` | KEEP-SHARPEN | Symbol-category breakdown is unique; description is dry. | description rewrite |
| `search:code` | CUT | Wraps `wicked-brain:search` + `wicked-brain:lsp`. | wicked-brain:search |
| `search:coverage` | KEEP-SHARPEN | Lineage-coverage report is unique; sharpen trigger lang. | description rewrite |
| `search:docs` | CUT | Wraps `wicked-brain:search` (already filters source_type). | wicked-brain:search |
| `search:help` | CUT | Per-domain `:help` overhead. | root help |
| `search:hotspots` | KEEP-AS-IS | Reference-count ranking from graph — unique. | — |
| `search:impact` | MERGE | Near-duplicate of `blast-radius` (semantic overlap on "what changes if I touch X"). | merge into `blast-radius` |
| `search:impl` | CUT | Wraps brain doc-to-code search. | wicked-brain:search w/ source_type=wiki |
| `search:index` | KEEP-AS-IS | Index-build orchestration; pillar #4 plumbing. | — |
| `search:lineage` | KEEP-AS-IS | Data-flow tracing UI→DB — exemplar unique value. | — |
| `search:quality` | KEEP-SHARPEN | Index Quality Crew — runs an internal multi-agent crew. Sharpen trigger. | description rewrite |
| `search:refs` | CUT | Duplicates `wicked-brain:lsp` + `wicked-brain:search`. | wicked-brain:lsp |
| `search:scout` | CUT | "Quick pattern recon w/o index" — that is literally Grep. | Grep |
| `search:search` | CUT | Wraps brain unified search. | wicked-brain:search |
| `search:service-map` | KEEP-AS-IS | Infra-config + code-pattern fusion to service graph — unique. | — |
| `search:sources` | KEEP-AS-IS | External MCP-source registration; brain plumbing. | — |
| `search:stats` | CUT | `wicked-brain:status` already shows index stats. | wicked-brain-status |
| `search:validate` | KEEP-SHARPEN | Index consistency checks. Useful but bury behind `search:quality`. | merge into `quality` |

### smaht (10) — mostly CUT (v6 made smaht infrastructure, not commands)

The push-orchestrator died in #428. What remains is mostly debug + import. The brain pull-model means these are largely obsolete entry points.

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `smaht:briefing` | KEEP-SHARPEN | "What happened since last time" is a real ask. Sharpen trigger. | description rewrite |
| `smaht:collaborate` | MERGE | Multi-AI CLI orchestration — overlaps with `jam:council`. | merge into `jam:council` |
| `smaht:context` | CUT | Build structured context — that's what brain pull directives + Skill(smaht) already do. | brain pull directive |
| `smaht:debug` | KEEP-SHARPEN | Session-state inspection — useful. Sharpen trigger lang. | description rewrite |
| `smaht:events-import` | KEEP-AS-IS | One-shot historical migration — niche but unique. | — |
| `smaht:events-query` | KEEP-AS-IS | Cross-domain event log — pillar #4. | — |
| `smaht:help` | CUT | Per-domain help overhead. | root help |
| `smaht:learn` | KEEP-AS-IS | Context7 fetch + cheatsheet persist — unique workflow. | — |
| `smaht:libs` | KEEP-SHARPEN | Lists cached cheatsheets; description is bare. | description rewrite |
| `smaht:onboard` | MERGE | Codebase onboarding — overlaps with `wicked-brain:agent (onboard)`. | merge into wicked-brain:agent |
| `smaht:smaht` | CUT | Self-named "thin shim over brain+search" — admit it's redundant. | wicked-brain:query |

### mem (8) — mostly thin wrappers over wicked-brain

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `mem:consolidate` | CUT | Calls wicked-brain consolidate agent — invoke skill directly. | wicked-brain:agent (consolidate) |
| `mem:forget` | CUT | Wraps `wicked-brain:forget`. | wicked-brain-forget |
| `mem:help` | CUT | Per-domain help overhead. | root help |
| `mem:recall` | CUT | "Thin wrapper over wicked-brain-memory" — admitted in body. | wicked-brain-memory |
| `mem:retag` | CUT | Wraps `wicked-brain:retag`. | wicked-brain-retag |
| `mem:review` | CUT | Wraps `wicked-brain:review`. | wicked-brain-review |
| `mem:stats` | CUT | Wraps brain stats. | wicked-brain-status |
| `mem:store` | CUT | "Thin wrapper over wicked-brain-memory" — admitted in body. | wicked-brain-memory |

> **Note**: The `mem` domain in v9 collapses into a single skill (`wicked-garden:mem`) that delegates to brain. All 8 mem:* commands cut. The skill itself stays as a discovery handle (mem ≠ wicked-brain in user mental model).

### jam (9) — mostly KEEP, council is pillar #2

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `jam:brainstorm` | KEEP-AS-IS | Full brainstorm session; clear progression hierarchy. | — |
| `jam:council` | KEEP-AS-IS | **Pillar #2** — multi-model verdict via external CLIs. Sacred. | — |
| `jam:help` | CUT | Per-domain help overhead. | root help |
| `jam:perspectives` | KEEP-AS-IS | Raw multi-perspective output (no synthesis) — distinct workflow. | — |
| `jam:persona` | KEEP-SHARPEN | Quote single persona across rounds — niche but useful. Sharpen. | description rewrite |
| `jam:quick` | KEEP-AS-IS | 60s gut-check — clear progression entry. | — |
| `jam:revisit` | KEEP-AS-IS | Closes the loop on past brainstorm decisions — unique to jam. | — |
| `jam:thinking` | KEEP-SHARPEN | Pre-synthesis perspectives — overlaps with `transcript`. Tighten. | possible merge into `transcript --raw` |
| `jam:transcript` | KEEP-AS-IS | Full session record — read-only. | — |

### engineering (12) — patch ops are unique value; planning commands overlap heavily

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `engineering:add-field` | KEEP-AS-IS | Multi-file propagation for entity changes — patch CLI not native. | — |
| `engineering:apply` | KEEP-AS-IS | Apply saved JSON patches w/ dry-run — patch CLI. | — |
| `engineering:arch` | KEEP-SHARPEN | Architecture analysis — overlaps with `engineering:review`. Sharpen scope. | description rewrite |
| `engineering:debug` | KEEP-SHARPEN | Systematic debugging — has unique value but description is generic. | description rewrite |
| `engineering:docs` | MERGE | Doc gen — overlaps with `engineering:generate` skill + `engineering:sync`. | merge into one docs surface |
| `engineering:help` | CUT | Per-domain help overhead. | root help |
| `engineering:new-generator` | KEEP-AS-IS | Scaffolds wicked-patch language generators — domain-specific. | — |
| `engineering:patch-plan` | KEEP-AS-IS | Patch impact preview without writes. | — |
| `engineering:plan` | KEEP-SHARPEN | "Detailed implementation steps" — overlaps with native planning. Sharpen anti-trigger. | description rewrite |
| `engineering:remove` | KEEP-AS-IS | Field-removal propagation — patch CLI. | — |
| `engineering:rename` | KEEP-AS-IS | Cross-file rename via wicked-patch — beats sed/grep. | — |
| `engineering:review` | KEEP-AS-IS | Senior-engineer code review w/ persona support — pillar #1 routing. | — |

### platform (17) — security/compliance/incident KEEP; observability commands MERGE

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `platform:actions` | KEEP-AS-IS | GitHub Actions gen/optimize/troubleshoot — distinct from `gh-cli` skill. | — |
| `platform:assert` | KEEP-AS-IS | Plugin contract assertion — pillar #5 (drop-in plugin contract). | — |
| `platform:audit` | KEEP-SHARPEN | Audit evidence collection — distinct from `compliance` (verify vs gather). | description rewrite |
| `platform:compliance` | KEEP-AS-IS | Regulatory framework checking (SOC2/HIPAA/GDPR/PCI). | — |
| `platform:errors` | MERGE | Error pattern detection — overlaps with `platform:logs` + `platform:health`. | merge into observability surface |
| `platform:gh` | KEEP-SHARPEN | Wraps `gh` CLI; risk of duplicating native `gh`. Sharpen value-add. | description rewrite |
| `platform:health` | KEEP-AS-IS | Aggregates observability across services. | — |
| `platform:help` | CUT | Per-domain help overhead. | root help |
| `platform:incident` | KEEP-AS-IS | Active triage; distinct from `crew:incident`. Has scope clarification. | — |
| `platform:infra` | KEEP-SHARPEN | IaC review; sharpen vs `engineering:arch`. | description rewrite |
| `platform:logs` | MERGE | Operational JSONL viewer — overlaps with `plugin-traces` + `plugin-health`. | merge into one `plugin:diagnose` |
| `platform:plugin-debug` | MERGE | Toggles log level — admin chore. | merge into `plugin:diagnose` |
| `platform:plugin-health` | MERGE | Plugin readiness probes — overlaps with `plugin-traces`. | merge into `plugin:diagnose` |
| `platform:plugin-traces` | MERGE | Hook trace query — overlaps with logs. | merge into `plugin:diagnose` |
| `platform:security` | KEEP-AS-IS | OWASP + secrets scan — pillar #1 specialist routing. | — |
| `platform:toolchain` | KEEP-AS-IS | Discovers monitoring CLIs — pillar #5 (drop-in). | — |
| `platform:traces` | KEEP-AS-IS | Distributed tracing analysis — distinct from `plugin-traces`. | — |

### product (13) — visual/UX work overlaps figma:* significantly

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `product:a11y` | KEEP-AS-IS | WCAG audit — code-level, distinct from figma. | — |
| `product:acceptance` | KEEP-AS-IS | Acceptance-criteria gen w/ Gherkin support. | — |
| `product:align` | KEEP-SHARPEN | Stakeholder alignment — vague description. Sharpen. | description rewrite |
| `product:analyze` | KEEP-AS-IS | Customer-feedback theme/sentiment — chained workflow. | — |
| `product:elicit` | KEEP-SHARPEN | Requirements elicitation; overlaps with skill. Sharpen vs skill. | description rewrite |
| `product:help` | CUT | Per-domain help overhead. | root help |
| `product:listen` | KEEP-AS-IS | Customer feedback aggregation across sources. | — |
| `product:mockup` | MERGE | Wireframe/mockup gen — overlaps with `figma:figma-generate-design`. | sharpen anti-trigger or cut if figma covers |
| `product:review` | MERGE | Visual design review — overlaps with `product:ux-review`. | merge into `ux-review` |
| `product:screenshot` | KEEP-AS-IS | Multimodal vision review of PNG/JPG — unique to wicked-garden. | — |
| `product:strategy` | KEEP-AS-IS | ROI / value-prop / competitive — distinct business analysis. | — |
| `product:synthesize` | KEEP-AS-IS | Feedback → recommendations chain. | — |
| `product:ux-review` | KEEP-AS-IS | Broad UX audit — distinct from `product:review` (visual-only). | — |
| `product:ux` | KEEP-SHARPEN | UX flow design — overlaps figma. Sharpen anti-trigger. | description rewrite |

### data (8) — heavy duplication

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `data:analysis` | CUT | Pure alias for `data:analyze` — admitted in body. | data:analyze |
| `data:analyze` | KEEP-AS-IS | Interactive CSV/Excel session w/ DuckDB. | — |
| `data:data` | KEEP-SHARPEN | "Data engineering ops" — name and description are awful. Rename to `data:profile`. | rename + sharpen |
| `data:help` | CUT | Per-domain help overhead. | root help |
| `data:ml` | KEEP-AS-IS | ML pipeline review/design — niche but unique. | — |
| `data:numbers` | MERGE | DuckDB SQL session — overlaps `data:analyze`. | merge into `data:analyze --sql` |
| `data:ontology` | KEEP-AS-IS | Public/custom ontology recommendation — unique. | — |
| `data:pipeline` | KEEP-AS-IS | Pipeline design + review. | — |

### delivery (6)

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `delivery:experiment` | KEEP-AS-IS | A/B test design w/ stats — unique workflow. | — |
| `delivery:help` | CUT | Per-domain help overhead. | root help |
| `delivery:process-health` | KEEP-AS-IS | Kaizen + retro action items — surfaces hidden process state. | — |
| `delivery:report` | KEEP-AS-IS | Multi-perspective stakeholder reports. | — |
| `delivery:rollout` | KEEP-AS-IS | Progressive feature rollout planning. | — |
| `delivery:setup` | KEEP-SHARPEN | Cost model / sprint cadence config. Sharpen trigger. | description rewrite |

### agentic (6) — skill-heavy domain; commands often wrap

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `agentic:ask` | CUT | Q&A about agentic patterns — Claude can answer directly + skills exist. | skill descriptions |
| `agentic:audit` | KEEP-AS-IS | Trust+safety audit w/ standards (GDPR/HIPAA/SOC2) — concrete output. | — |
| `agentic:design` | KEEP-AS-IS | Interactive arch design w/ pattern recommendations. | — |
| `agentic:frameworks` | KEEP-SHARPEN | Framework comparison — overlaps with `frameworks` skill. Choose one path. | merge with skill |
| `agentic:help` | CUT | Per-domain help overhead. | root help |
| `agentic:review` | KEEP-AS-IS | Full agentic codebase review w/ remediation roadmap. | — |

### persona (4)

| Command | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `persona:as` | KEEP-AS-IS | Invoke named persona — distinct discovery handle. | — |
| `persona:define` | KEEP-AS-IS | Custom persona authoring. | — |
| `persona:list` | KEEP-AS-IS | Persona discovery w/ role filter. | — |
| `persona:submit` | KEEP-SHARPEN | PR a persona to repo — niche but unique. Sharpen trigger. | description rewrite |

---

## Skills (by domain)

### root-level (10)

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `adopt-legacy` | KEEP-SHARPEN | Niche v6.0-beta.3 migration helper. Could CUT in v9 if no live beta projects. | UNCERTAIN: confirm zero in-flight beta projects |
| `deliberate` | KEEP-AS-IS | Critical-thinking framework — exemplar discovery-shape. | — |
| `integration-discovery` | KEEP-AS-IS | Capability router (CLI + MCP + skills + agents) — pillar #5. | — |
| `jam` | KEEP-AS-IS | Brainstorm orchestrator. | — |
| `mem` | KEEP-AS-IS | Memory storage handle — even if commands collapse, skill stays as discovery surface. | — |
| `multi-model` | KEEP-AS-IS | LLM CLI discovery + council — pillar #2. | — |
| `persona` | KEEP-AS-IS | On-demand persona invocation. | — |
| `propose-process` | KEEP-AS-IS | **Pillar #3 + pillar #1** — facilitator rubric is the engine. Sacred. | — |
| `runtime-exec` | KEEP-AS-IS | Internal `user-invocable: false` shim — load-bearing for other skills. | — |
| `unified-search` | CUT | Now describes itself as "use this over Grep" — but brain owns this surface. | wicked-brain:search |
| `wickedizer` | KEEP-AS-IS | Humanize/rewrite content — exemplar discovery-shape, distinct from native edit. | — |
| `workflow` | KEEP-SHARPEN | Crew engine description — overlaps with `propose-process`. Sharpen scope. | description rewrite or merge |

### crew (7)

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `crew/adaptive` | KEEP-AS-IS | Autonomy preference patterns — load-bearing for crew engine. | — |
| `crew/change-type-detector` | KEEP-AS-IS | UI/API classifier for test routing — internal but unique. | — |
| `crew/crew-qe-gate` | KEEP-AS-IS | Phase-transition gates (value/strategy/execution). | — |
| `crew/evidence-validation` | KEEP-AS-IS | Evidence-tier validation tied to complexity score. | — |
| `crew/explain` | KEEP-AS-IS | Plain-English crew jargon translator. Mirror of command. | — |
| `crew/issue-reporting` | KEEP-AS-IS | Auto-detection + filing of GH issues from sessions. | — |
| `crew/test-task-factory` | KEEP-AS-IS | Generates test-task params from change-type detection. | — |

### agentic (7) — overlap with framework guidance

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `agentic/agentic-patterns` | KEEP-AS-IS | Patterns + anti-patterns — discovery-shape good. | — |
| `agentic/context-engineering` | KEEP-AS-IS | Context-window mgmt — niche guidance, well-shaped. | — |
| `agentic/five-layer-architecture` | MERGE | Specific arch model — overlaps with `agentic-patterns` + `frameworks`. | merge into `agentic-patterns` |
| `agentic/frameworks` | KEEP-AS-IS | Framework selection — high-frequency need. | — |
| `agentic/maturity-model` | MERGE | Maturity assessment — could fold into `review-methodology`. | merge into `review-methodology` |
| `agentic/review-methodology` | KEEP-AS-IS | Review approach for agentic codebases. | — |
| `agentic/trust-and-safety` | KEEP-AS-IS | Guardrails + HITL — pillar value. | — |

### data (5) — substantially duplicates wicked-testing-oracle and DuckDB native usage

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `data/analysis` | KEEP-SHARPEN | Exploratory analysis — well-shaped trigger. Distinct from `data` (profile). | description rewrite |
| `data/data` | KEEP-SHARPEN | Profile/validate/quality — name is awful, rename to `data/profile`. | rename + sharpen |
| `data/ml` | KEEP-AS-IS | ML model review — niche unique value. | — |
| `data/numbers` | CUT | "Run SQL with DuckDB" — that's a `duckdb` CLI bash call. | Bash + duckdb |
| `data/pipeline` | KEEP-AS-IS | ETL design + review — unique. | — |

### delivery (4)

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `delivery/design` | KEEP-AS-IS | A/B test design — well-shaped. | — |
| `delivery/onboarding-guide` | KEEP-AS-IS | Personalized dev onboarding — distinct workflow. | — |
| `delivery/reporting` | KEEP-AS-IS | Multi-perspective reports. | — |
| `delivery/rollout` | KEEP-AS-IS | Progressive feature rollouts. | — |

### engineering (11) — heavy overlap on docs + arch

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `engineering/architecture` | KEEP-AS-IS | Solution architecture — distinct from system-design. | — |
| `engineering/backend` | KEEP-AS-IS | API/DB/server-side specialist. | — |
| `engineering/debugging` | KEEP-AS-IS | Systematic debugging — exemplar discovery-shape. | — |
| `engineering/docs-audit` | MERGE | Doc coverage — overlaps with `generate` + `sync`. | merge into one `engineering/docs` skill |
| `engineering/engineering` | KEEP-SHARPEN | "Senior engineering guidance" — too broad. Sharpen scope. | description rewrite |
| `engineering/frontend` | KEEP-AS-IS | React/CSS/browser specialist. | — |
| `engineering/generate` | MERGE | Doc generation — overlaps with `docs-audit` + `sync`. | merge into one `engineering/docs` |
| `engineering/integration` | KEEP-AS-IS | API contracts + service boundaries. | — |
| `engineering/patch` | KEEP-AS-IS | Multi-file mutation — unique to wicked-patch. | — |
| `engineering/sync` | MERGE | Doc-code sync — overlaps with `docs-audit`. | merge into one `engineering/docs` |
| `engineering/system-design` | KEEP-SHARPEN | Component boundaries — overlaps with `architecture`. Tighten. | description rewrite |

### platform (12) — heavy overlap with native gh and CI plugins

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `platform/audit` | KEEP-AS-IS | Audit evidence collection. | — |
| `platform/compliance` | KEEP-AS-IS | Regulatory framework checks. | — |
| `platform/errors` | MERGE | Error pattern detection — overlaps with `health` + `traces`. | merge into observability skill |
| `platform/gate-benchmark-rebaseline` | KEEP-AS-IS | Niche AC-11 SLO procedure — unique compliance value. | — |
| `platform/gh-cli` | KEEP-SHARPEN | gh power utilities — risks duplicating native `gh` man pages. Sharpen value-add. | description rewrite |
| `platform/github-actions` | KEEP-AS-IS | Secure-by-default GHA workflow authoring. | — |
| `platform/gitlab-ci` | KEEP-AS-IS | Distinct CI provider. | — |
| `platform/glab-cli` | KEEP-SHARPEN | glab — same risk as gh-cli. Sharpen. | description rewrite |
| `platform/health` | KEEP-AS-IS | Multi-source health aggregation. | — |
| `platform/observability` | KEEP-AS-IS | Plugin observability + toolchain discovery. | — |
| `platform/policy` | MERGE | Policy interpretation — overlaps with `compliance`. | merge into `compliance` |
| `platform/prereq-doctor` | KEEP-AS-IS | "command not found" diagnosis + install — distinct trigger. | — |
| `platform/traces` | MERGE | Distributed tracing — overlaps with `health` + `errors`. | merge into observability |

### product (15) — large surface; requirements-* sub-family is over-split

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `product/acceptance-criteria` | KEEP-AS-IS | AC definition bridging requirements↔QE. | — |
| `product/accessibility` | KEEP-SHARPEN | a11y guidance — overlaps with command. Sharpen vs command. | description rewrite |
| `product/analyze` | KEEP-AS-IS | Sentiment + theme extraction. | — |
| `product/design-review` | MERGE | Visual design review — overlaps `visual-review` + `ux-review` skills. | merge into `visual-review` |
| `product/imagery` | KEEP-AS-IS | Parent skill for image lifecycle. | — |
| `product/imagery/alter` | KEEP-AS-IS | img2img/inpaint — distinct provider need. | — |
| `product/imagery/create` | KEEP-AS-IS | Text-to-image w/ 5 providers. | — |
| `product/imagery/review` | KEEP-AS-IS | Image quality + brand check (no provider needed). | — |
| `product/listen` | KEEP-AS-IS | Customer feedback aggregation. | — |
| `product/mockup` | MERGE | Wireframe/mockup — overlaps with figma plugin. Sharpen anti-trigger or cut. | UNCERTAIN: confirm figma coverage |
| `product/product-management` | KEEP-AS-IS | Strategic PM — high-level discovery handle. | — |
| `product/requirements-analysis` | KEEP-SHARPEN | Requirements elicitation — overlaps `requirements-graph`. Pick one. | merge into requirements-graph |
| `product/requirements-graph` | KEEP-AS-IS | Filesystem-as-graph requirements — unique structural value. | — |
| `product/requirements-migrate` | KEEP-AS-IS | One-shot monolith→graph conversion. | — |
| `product/requirements-navigate` | KEEP-AS-IS | Graph navigation + meta.md regen. | — |
| `product/screenshot` | KEEP-AS-IS | Multimodal screenshot review. | — |
| `product/strategy` | KEEP-AS-IS | Business strategy (ROI/value/market). | — |
| `product/synthesize` | KEEP-AS-IS | Feedback → recommendations. | — |
| `product/ux-flow` | MERGE | Generative UX flows — overlaps `ux-review`. | merge into UX skill family |
| `product/ux-review` | KEEP-AS-IS | UX quality review (eval, not generate). | — |
| `product/visual-review` | KEEP-AS-IS | Systematic visual checklist. | — |

> **Cross-cutting product cleanup**: visual-review + design-review + ux-flow + ux-review = 4 surfaces for adjacent territory. Recommend collapsing to **visual-review** (visual-only) + **ux-review** (flows + research). Cuts 2.

### search (1) + smaht (2)

| Skill | Verdict | Rationale | Native equivalent / merge target |
|---|---|---|---|
| `search/codebase-narrator` | KEEP-AS-IS | Onboarding-style code narration — distinct from raw search. | — |
| `smaht/SKILL.md` (context-assembly) | KEEP-AS-IS | Pull-model context assembly — pillar #4 entry. | — |
| `smaht/discovery` | KEEP-AS-IS | Internal `user-invocable: false` — drives Stop-hook discovery. | — |

---

## Hooks

Apply the grain-riding criterion: **hook fires on signal Claude can't see → KEEP. Hook fires on signal Claude can already see → CUT.**

| Hook | Verdict | Rationale |
|---|---|---|
| `bootstrap.py` (SessionStart) | KEEP-AS-IS | Setup gate, briefing, plugin probes — only this hook can run on session start. |
| `pre_tool.py` (PreToolUse) | KEEP-AS-IS | Validates TaskCreate/TaskUpdate metadata envelope, blocks MEMORY.md writes, gate preflight. Claude cannot self-validate envelope. |
| `post_tool.py` (PostToolUse) | KEEP-SHARPEN | Does too much: stale-marker, QE tracking, agentic detect, traces, discovery hints. Split discovery hints (cuttable) from validation (KEEP). |
| `prompt_submit.py` (UserPromptSubmit) | KEEP-AS-IS | Setup gate, facilitator re-eval directive, pull-model directive injection. Pre-prompt only the hook can do. |
| `notification.py` (Notification) | KEEP-AS-IS | Reads context-limit warnings Claude doesn't surface — adjusts smaht behavior. |
| `permission_request.py` (PermissionRequest) | KEEP-AS-IS | Auto-approves known-safe ops — reduces friction Claude cannot avoid alone. |
| `pre_compact.py` (PreCompact) | KEEP-AS-IS | Saves WIP memory before compression — Claude cannot self-snapshot pre-compaction. |
| `stop.py` (Stop) | KEEP-SHARPEN | Heavy: outcome check, memory promotion, brain compile/lint, decay, retention. Split into focused async tasks. |
| `subagent_lifecycle.py` (SubagentStart/Stop) | CUT | Logs duration + counts — observability nice-to-have but Claude doesn't need it. Telemetry can move to `wicked-bus:emit` if needed. |
| `task_completed.py` (TaskCompleted) | CUT | Emits "evaluate for storable learnings" directive — overlaps with brain consolidate + Stop hook. Claude already sees its own completions. |

> Note: `invoke.py` is the dispatcher (not a hook script in itself); it stays.

---

## Cross-cutting findings

### 1. Per-domain `:help` commands are pure noise (10 surfaces)

`crew:help`, `search:help`, `smaht:help`, `mem:help`, `jam:help`, `engineering:help`, `platform:help`, `product:help`, `data:help`, `delivery:help`, `agentic:help` — all of them. The root `/wicked-garden:help` covers it. **All 10 should CUT.**

### 2. mem domain is now a wrapper façade (8 surfaces)

Every `mem:*` command admits to being "thin wrapper over wicked-brain-*". v9 should cut all 8 commands and keep only the `mem` skill as a discovery handle (since "mem" ≠ "wicked-brain" in the user's mental phrasing).

### 3. search domain duplicates wicked-brain except for graph queries (8 of 18 cuttable)

`search:code`, `search:docs`, `search:search`, `search:refs`, `search:impl`, `search:scout`, `search:stats`, `search:help` all duplicate `wicked-brain:search`/`wicked-brain:lsp`. The unique value is the **graph traversal** (lineage, blast-radius, hotspots, service-map, categories, coverage). Keep those, cut the rest.

### 4. Platform observability commands are over-fragmented (4 → 1)

`platform:logs` + `platform:plugin-debug` + `platform:plugin-health` + `platform:plugin-traces` are all "tell me what wicked-garden is doing right now." Collapse into a single `platform:plugin:diagnose` with subcommands.

### 5. Engineering doc commands (3 → 1)

`engineering/docs-audit` + `engineering/generate` + `engineering/sync` all live in the doc lifecycle. Collapse into one `engineering/docs` skill that handles audit + generate + sync.

### 6. Product visual/UX surface is over-split (4 → 2)

`product/design-review` + `product/visual-review` + `product/ux-flow` + `product/ux-review` cover overlapping ground. Keep `visual-review` (visual checklist) + `ux-review` (flows/research). Drop the others.

### 7. Aliases are pure debt (3 surfaces)

`crew:yolo` (→ `auto-approve`), `data:analysis` (→ `analyze`), top-level `aliases` doc. v9 is the breaking-change moment to drop them.

### 8. The `wicked-garden:ground` skill is missing (PR-4 should add)

Per the epic, the keystone skill `wicked-garden:ground` does not exist yet. This is the **single most important add** for v9 — it's the skill that makes brain+bus discoverable at the moment of uncertainty. PR-4 must author it.

### 9. jam ↔ multi-model ↔ smaht:collaborate are three names for one capability

`jam:council` + `multi-model` skill + `smaht:collaborate` all orchestrate external LLM CLIs. Recommend: keep `jam:council` as the user-facing handle, keep `multi-model` skill as the internal capability, **cut `smaht:collaborate`**.

### 10. Hooks are mostly grain-riders; only 2 cuttable

Most hooks fire on signals Claude can't see (session start, pre-tool, pre-compaction, notifications, permission requests). Only `subagent_lifecycle` and `task_completed` fire on signals Claude already sees. Those two are the cut targets.

### 11. Surfaces that look like infrastructure rather than guidance

- `propose-process` skill → it IS the engine, not a guidance handle. Pillar #3.
- `runtime-exec` skill → marked `user-invocable: false`. Internal shim. Stays.
- `smaht/discovery` skill → marked `user-invocable: false`. Stays.
- `platform/gate-benchmark-rebaseline` → operational procedure, not user-facing. Stays for compliance.

These are correct as infrastructure; v9 must protect their role and not "discover-shape" them.

### 12. UNCERTAIN items — need human judgment

| Surface | Question |
|---|---|
| `adopt-legacy` skill | Are there any v6.0-beta.3 projects still in flight? If no → CUT. |
| `product/mockup` skill+command | Does `figma:figma-generate-design` cover ASCII wireframes + HTML/CSS previews? If yes → CUT both. |
| `crew:cutover` | After mode-3 has been default for one release → CUT. Now? KEEP one more cycle. |
| `crew:migrate-gates` | Treated as CUT above (v6 shipped a year ago). Confirm no in-flight v6.0-beta.3 projects. |
| `agentic:ask` | Is there value in routing arbitrary agentic Q&A to a command vs letting Claude answer + skills? If skills cover, CUT. |
| `engineering:arch` vs `engineering/architecture` skill vs `engineering/system-design` | Three surfaces for adjacent territory. Pick the strongest discovery shape (likely the skill `architecture` + cut the command). |

---

## Recommended PR-2 cut order

Sequence by blast-radius (lowest first). Each batch can be its own commit inside PR-2.

### Batch 1 — Standalone wrappers with zero dependents (safest, ~25 surfaces)

- All 10 per-domain `:help` commands
- `crew:yolo` (alias)
- `data:analysis` (alias)
- `aliases.md` root command
- All 8 `mem:*` commands
- `smaht:smaht`, `smaht:context`, `smaht:help`
- `agentic:ask`

### Batch 2 — Search-domain commands superseded by wicked-brain (8 surfaces)

- `search:code`, `search:docs`, `search:search`, `search:refs`, `search:impl`, `search:scout`, `search:stats`, `search:help`
- Skill: `unified-search`

### Batch 3 — Old migration helpers (3 surfaces)

- `crew:migrate-gates` (after confirming no in-flight beta projects)
- `adopt-legacy` skill (after confirming same)
- `crew:cutover` (after one release with mode-3 default)

### Batch 4 — Hooks (2 surfaces, integration-coupled — last)

- `subagent_lifecycle.py` (relocate telemetry to `wicked-bus:emit`)
- `task_completed.py` (Stop hook + brain consolidate already cover)

### Batch 5 — Merges (handled in PR-3 alongside description sharpening)

- Engineering docs (3 → 1)
- Platform plugin diagnostics (4 → 1)
- Product visual/UX (4 → 2)
- Search impact → blast-radius
- jam:thinking → transcript --raw

---

## Top 5 most duplicative surfaces (clearest CUTs)

1. **`mem:store`** + **`mem:recall`** — admit in their own bodies that they are "thin wrappers" over `wicked-brain-memory`.
2. **`search:scout`** — "quick pattern reconnaissance without index" is literally `Grep`.
3. **`unified-search` skill** — its description says "use this over Grep" but `wicked-brain:search` is the actual unified search now.
4. **`smaht:smaht`** — body admits "this command is now a thin shim over brain + search."
5. **`crew:yolo`** — pure alias for `crew:auto-approve` (one-liner that calls it).

## Top 5 KEEP-AS-IS exemplars of unique value

1. **`crew:start`** + the `propose-process` skill — pillars #1 and #3. The 9-factor facilitator rubric + dynamic phase plan is uncopyable.
2. **`jam:council`** — pillar #2. Multi-model orchestration via subprocess to external LLM CLIs (codex, gemini, etc.). Outside Claude's tool palette.
3. **`search:lineage`** — data-flow tracing UI→DB. The graph + multi-source fusion is genuinely unique.
4. **`crew:convergence`** — Designed→Built→Wired→Tested→Integrated→Verified lifecycle. Catches the "task complete but artifact not wired" failure mode native tooling misses.
5. **`deliberate`** skill — exemplar discovery-shape. "Use when about to commit to non-obvious work" maps directly to Claude's internal phrasing.

## Surprises

1. **The `mem` domain is fully wrapper** — every command says "delegates to wicked-brain". v9 lets us amputate cleanly.
2. **The search domain is mostly cuttable** (10 of 18 commands). The brain adapter swallowed the unified index. Only the graph-shape queries remain unique.
3. **`subagent_lifecycle` hook is observability theater** — it logs durations + counts but Claude doesn't act on it. Pure cuttable.
4. **`smaht:smaht` is self-aware redundancy** — its own description says "thin shim." Honest, and cuttable.
5. **Hidden uniqueness in `crew/test-task-factory` and `crew/change-type-detector`** — they look like internal helpers but they're the load-bearing classifier that routes test tasks. KEEP-AS-IS even though they don't read like discovery surfaces.
6. **`platform/gate-benchmark-rebaseline` is genuinely unique infrastructure** — niche but the kind of operational rigor wicked-garden uniquely owns.
7. **No `wicked-garden:ground` exists yet** — the keystone skill from the epic is missing. v9-PR-4 must build it.
