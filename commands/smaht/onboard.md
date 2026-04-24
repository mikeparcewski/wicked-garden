---
description: Intelligent codebase onboarding using the wicked-garden ecosystem
argument-hint: "[path] [--skip-index] [--resume]"
---

# /wicked-garden:smaht:onboard

Intelligent onboarding that builds understanding of a codebase using parallel workflows. Indexes in the background while exploring in parallel, saves discoveries as memories, and validates navigability post-index.

## Arguments

- `path` (optional): Directory to onboard. Default: current working directory
- `--skip-index`: Skip indexing (use existing index or scout-only mode)
- `--resume`: Resume a previous onboarding session (recalls prior discoveries from wicked-garden:mem)

## Instructions

### 1. MANDATORY FIRST ACTION: Start Background Index

> **NON-NEGOTIABLE**: Unless `--skip-index` was explicitly passed, you MUST run this command BEFORE any other action. Do not skip this step. Do not defer it. Run it now.

Invoke `wicked-brain:ingest` to index the target path. Run in background:
```
Skill(skill="wicked-brain:ingest", args="{path}")
```

Store the task ID — you will need it in Phase 3 to validate the index.

If `--skip-index` was passed, skip this step and note: "Indexing skipped — Phase 3 validation will be limited."

### 2. Check for Prior Onboarding

Recall previous onboarding sessions for this path:

```
wicked-brain:memory "onboarding {path}" --limit 3
```

If `--resume` and prior memories exist, show what was already discovered and skip to Phase 2 gaps.

If prior onboarding found, ask: "Previous onboarding found for this codebase. Resume from where you left off, or start fresh?"

### 3. Phase 1 — Parallel Discovery (Scout + Explore)

The background index is already running. Now build understanding while it builds.

#### 3.1 Quick Scout (Immediate)

While indexing runs, do a fast reconnaissance:

```
wicked-brain:search {path}
```

This gives immediate results without waiting for the index.

#### 3.2 Parallel Exploration

Launch 3 exploration agents concurrently:

**Agent 1: Architecture Discovery**
```
Task(subagent_type="Explore",
     prompt="Explore {path} and identify:
     1. Languages and frameworks (check package.json, requirements.txt, go.mod, Cargo.toml, etc.)
     2. Architecture pattern (MVC, layered, microservices, monorepo, monolith)
     3. Directory structure and what each top-level dir does
     4. Key entry points (main files, CLI entry, server startup, app bootstrap)
     5. Database/storage layer (what DB, ORM, migration patterns)
     Return structured findings.")
```

**Agent 2: Flow Tracing**
```
Task(subagent_type="Explore",
     prompt="Explore {path} and trace key data flows:
     1. Find API endpoints or route definitions
     2. Trace a request from entry point through middleware to handler to DB
     3. Identify key abstractions (services, repositories, controllers, models)
     4. Find configuration and environment setup patterns
     5. Identify external integrations (APIs, queues, caches)
     Return structured findings with file paths and line numbers.")
```

**Agent 3: Quality & Gaps**
```
Task(subagent_type="Explore",
     prompt="Explore {path} and assess quality signals:
     1. Test coverage: find test directories, count test files vs source files
     2. Documentation: README quality, inline docs, API docs
     3. CI/CD: find workflow files (.github/workflows, .gitlab-ci.yml, Jenkinsfile)
     4. Gaps: missing tests, undocumented modules, no error handling patterns
     5. Tech debt signals: TODO/FIXME/HACK comments, deprecated usage
     Return structured findings with file paths.")
```

### 4. Phase 2 — Synthesize & Store Discoveries

After all exploration agents complete:

#### 4.1 Synthesize Findings

Combine results from all 3 agents into a structured onboarding profile:

```markdown
## Codebase Profile: {project-name}

### TL;DR
{2-3 sentence description based on discoveries}

### Technology Stack
| Layer | Technology | Files |
|-------|-----------|-------|
| Language | {lang} | {count} files |
| Framework | {framework} | |
| Database | {db} | |
| Testing | {test framework} | {count} test files |

### Architecture
**Pattern**: {pattern name}
**Key insight**: {most important architectural decision}

### Entry Points
1. {entry}: {what it does} → `{file:line}`
2. ...

### Key Flows
1. {flow name}: {source} → {middleware} → {handler} → {storage}
2. ...

### Quality Signals
- Tests: {ratio} ({count} test files / {count} source files)
- Docs: {quality assessment}
- CI/CD: {present/absent}
- Tech debt: {count} TODOs/FIXMEs

### Gaps Identified
1. {gap}: {description} — {severity}
2. ...
```

#### 4.2 Store Discoveries as Individual Memories

Save each discovery as its own memory — one fact per memory, not monolithic summaries.
This ensures each fact surfaces independently when relevant, rather than requiring
the entire onboarding dump to match a keyword.

**Technology stack** (one per layer):
```
wicked-brain:memory "{project-name} is a {language} project using {framework}" --type procedural --tags onboarding,{project-name},stack,{language}
wicked-brain:memory "{project-name} uses {database} for persistence" --type procedural --tags onboarding,{project-name},stack,database
wicked-brain:memory "{project-name} tests use {test-framework} — {ratio} test/source ratio" --type procedural --tags onboarding,{project-name},testing
```

**Architecture** (one per insight):
```
wicked-brain:memory "{project-name} follows {pattern} architecture — {key insight}" --type procedural --tags onboarding,{project-name},architecture
wicked-brain:memory "{project-name} main entry point: {entry} at {file:line}" --type procedural --tags onboarding,{project-name},entry-point
```

**Key flows** (one per flow):
```
wicked-brain:memory "{project-name} {flow-name} flow: {source} → {handler} → {storage}" --type procedural --tags onboarding,{project-name},flow,{flow-name}
```
Repeat for each significant flow discovered.

**Quality signals** (one per finding):
```
wicked-brain:memory "{project-name} has {count} TODOs/FIXMEs — tech debt concentrated in {area}" --type episodic --tags onboarding,{project-name},tech-debt
wicked-brain:memory "{project-name} CI/CD: {present/absent} — {details}" --type procedural --tags onboarding,{project-name},ci
```

**Gaps** (one per gap):
```
wicked-brain:memory "{project-name} gap: {description} — {severity}" --type episodic --tags onboarding,{project-name},gap
```
Repeat for each gap found.

**Tagging rules**:
- Every memory gets `onboarding` + `{project-name}` tags
- Add a category tag: `stack`, `architecture`, `flow`, `testing`, `gap`, `entry-point`, `ci`, `tech-debt`
- Add specific tags for the technology: `react`, `python`, `postgres`, etc.
- This enables targeted recall: `mem:recall --tags postgres` finds the database choice

### 5. Phase 3 — Validate Against Index

> **GATE CHECK**: Before proceeding, verify that Step 1 (background indexing) was started. If `--skip-index` was NOT passed and you did not start the indexing task, you MUST start it now before continuing. Do not skip this check.

Once the background index completes:

#### 5.1 Check Index Status

Read the background task output. If still running, report progress and continue to the report (validation can happen later).

#### 5.2 Deep Linking (Lineage + Service Map)

If the index is ready, derive cross-layer relationships that raw indexing alone doesn't produce:

```
/wicked-garden:search:service-map
```

This detects services, layers, and their dependencies. Then derive lineage for key entry points discovered in Phase 1:

```
/wicked-garden:search:lineage "{key_symbol}" --direction both
```

Run this for 2-3 key symbols from the exploration to populate the lineage graph.

#### 5.3 Validate Navigability

Run validation checks against the fully-linked index:

```
wicked-brain-status
```

Then verify the discovered architecture matches the indexed data:

- Can we find the entry points we discovered? → `wicked-brain:search "{main function/class}"`
- Can we trace the flows we identified? → `wicked-brain:lsp "{key symbol}"`
- Do the layers map correctly? → (service-map already generated above)

Report validation results:

```markdown
### Index Validation
| Check | Status | Detail |
|-------|--------|--------|
| Entry points findable | {pass/fail} | {count}/{total} found in index |
| Key flows traceable | {pass/fail} | {count}/{total} traceable |
| Service map derived | {pass/fail} | {service_count} services, {layer_count} layers |
| Lineage paths | {pass/fail} | {lineage_count} paths traced |
| Index coverage | {percentage} | {indexed}/{total} files |
```

If validation reveals gaps (symbols not indexed, flows not traceable), store as memories:

```
wicked-brain:memory "Onboarding gap: {project-name} - {gap description}. Files not indexed or symbols missing." --type episodic --tags onboarding,{project-name},gap
```

### 6. Generate Onboarding Report

Produce the final report combining all phases:

```markdown
## Onboarding Complete: {project-name}

**Duration**: {total time}
**Path**: {path}
**Index**: {status — complete/in-progress/skipped}

---

{Codebase Profile from Phase 2}

---

### Validation Results
{From Phase 3, or "Index still building — run `/wicked-garden:smaht:onboard --resume` later to validate"}

---

### Recommended Next Steps

Based on your onboarding discoveries:

1. **Read first**: {most important file to understand} — {why}
2. **Try running**: {how to start/test the app}
3. **Good first change**: {suggested low-risk change based on gaps}
4. **Deep dive**: {area that needs most understanding}

### For Continued Learning

- `/wicked-garden:search:blast-radius {key symbol}` — Impact analysis (index + lineage already built)
- `/wicked-garden:search:lineage {key symbol}` — Trace additional data flows
- `/wicked-garden:search:hotspots` — Find the most-referenced symbols
- `/wicked-garden:delivery:report --orient` — Detailed orientation guide
- `/wicked-garden:smaht:onboard --resume` — Continue from where you left off

### Memories Saved

{count} memories stored for future sessions. Next time you work in this codebase, context will be automatically recalled.
```

### 7. Offer Deeper Exploration

After the report, offer to go deeper:

```markdown
---

**Want to go deeper?** I can:
- `/wicked-garden:search:blast-radius {symbol}` — Analyze impact of changing a symbol
- `/wicked-garden:search:lineage {symbol}` — Trace more data flows end-to-end
- Explain any component in detail
- Generate a learning path for this codebase
- Re-index with `/wicked-garden:search:index {path}` if the index looks incomplete
```

## Graceful Degradation

| Component | Available | Fallback |
|-----------|-----------|----------|
| wicked-brain | FTS5 search + LSP symbols | Scout-only mode (Glob/Grep) |
| search | Index + validate (built-in) | Scout-only mode (Glob/Grep) |
| mem | Store/recall discoveries (built-in) | No persistence between sessions |
| delivery | Learning paths (built-in) | Generic next steps |

If wicked-brain is unavailable, skip Phase 1 indexing and Phase 3 validation. Exploration still works via Glob/Grep.

If wicked-garden:mem is unavailable, skip memory storage. Report is still generated but not persisted.

## Examples

```bash
# Onboard current directory
/wicked-garden:smaht:onboard

# Onboard specific path
/wicked-garden:smaht:onboard /path/to/project

# Resume previous onboarding
/wicked-garden:smaht:onboard --resume

# Skip indexing (just explore)
/wicked-garden:smaht:onboard --skip-index
```
