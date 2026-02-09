---
description: Intelligent codebase onboarding using the wicked-garden ecosystem
argument-hint: [path] [--skip-index] [--resume]
---

# /wicked-smaht:onboard

Intelligent onboarding that builds understanding of a codebase using parallel workflows. Indexes in the background while exploring in parallel, saves discoveries as memories, and validates navigability post-index.

## Arguments

- `path` (optional): Directory to onboard. Default: current working directory
- `--skip-index`: Skip indexing (use existing index or scout-only mode)
- `--resume`: Resume a previous onboarding session (recalls prior discoveries from wicked-mem)

## Instructions

### 1. Check for Prior Onboarding

Recall previous onboarding sessions for this path:

```
/wicked-mem:recall "onboarding {path}" --limit 3
```

If `--resume` and prior memories exist, show what was already discovered and skip to Phase 2 gaps.

If prior onboarding found, ask: "Previous onboarding found for this codebase. Resume from where you left off, or start fresh?"

### 2. Phase 1 — Parallel Discovery (Index + Explore)

Run indexing and exploration concurrently. The goal: build understanding while the index builds.

#### 2.1 Start Background Index

Unless `--skip-index`, start indexing in the background.

First, locate the wicked-search scripts directory. Check in order:
1. Plugin cache: `~/.claude/plugins/cache/wicked-garden/wicked-search/*/scripts/` (use highest version)
2. Local repo sibling: `../wicked-search/scripts/` relative to wicked-smaht

Then run:

```
Bash(command="cd {wicked-search-scripts-dir} && uv run python unified_search.py index '{path}'",
     run_in_background=true)
```

Store the task ID — we'll check on it in Phase 3.

#### 2.2 Quick Scout (Immediate)

While indexing runs, do a fast reconnaissance:

```
/wicked-search:scout {path}
```

This gives immediate results without waiting for the index.

#### 2.3 Parallel Exploration

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

### 3. Phase 2 — Synthesize & Store Discoveries

After all exploration agents complete:

#### 3.1 Synthesize Findings

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

#### 3.2 Store Discoveries as Memories

Save key discoveries to wicked-mem for future sessions:

```
/wicked-mem:store "Onboarding: {project-name} architecture is {pattern} using {framework}/{lang}. Key entry: {main entry}. {count} services/modules." --type procedural --tags onboarding,{project-name},architecture

/wicked-mem:store "Onboarding: {project-name} has {gap count} gaps: {top gaps}. Test ratio: {ratio}." --type episodic --tags onboarding,{project-name},quality

/wicked-mem:store "Onboarding: {project-name} key flows - {flow summaries}" --type procedural --tags onboarding,{project-name},flows
```

### 4. Phase 3 — Validate Against Index

Once the background index completes:

#### 4.1 Check Index Status

Read the background task output. If still running, report progress and continue to the report (validation can happen later).

#### 4.2 Validate Navigability

If index is ready, run validation checks:

```
/wicked-search:stats
```

Then verify the discovered architecture matches the indexed data:

- Can we find the entry points we discovered? → `/wicked-search:code "{main function/class}"`
- Can we trace the flows we identified? → `/wicked-search:refs "{key symbol}"`
- Do the layers map correctly? → `/wicked-search:service-map`

Report validation results:

```markdown
### Index Validation
| Check | Status | Detail |
|-------|--------|--------|
| Entry points findable | {pass/fail} | {count}/{total} found in index |
| Key flows traceable | {pass/fail} | {count}/{total} traceable |
| Service map matches | {pass/fail} | {detail} |
| Index coverage | {percentage} | {indexed}/{total} files |
```

If validation reveals gaps (symbols not indexed, flows not traceable), store as memories:

```
/wicked-mem:store "Onboarding gap: {project-name} - {gap description}. Files not indexed or symbols missing." --type episodic --tags onboarding,{project-name},gap
```

### 5. Generate Onboarding Report

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
{From Phase 3, or "Index still building — run `/wicked-smaht:onboard --resume` later to validate"}

---

### Recommended Next Steps

Based on your onboarding discoveries:

1. **Read first**: {most important file to understand} — {why}
2. **Try running**: {how to start/test the app}
3. **Good first change**: {suggested low-risk change based on gaps}
4. **Deep dive**: {area that needs most understanding}

### For Continued Learning

- `/wicked-search:lineage {key symbol}` — Trace data flow
- `/wicked-search:blast-radius {key symbol}` — Impact analysis
- `/wicked-delivery:report --orient` — Detailed orientation guide
- `/wicked-smaht:onboard --resume` — Continue from where you left off

### Memories Saved

{count} memories stored for future sessions. Next time you work in this codebase, context will be automatically recalled.
```

### 6. Offer Deeper Exploration

After the report, offer to go deeper:

```markdown
---

**Want to go deeper?** I can:
- `/wicked-search:index {path} --derive-all` — Full lineage + service map derivation
- Trace a specific flow end-to-end
- Explain any component in detail
- Generate a learning path for this codebase
```

## Graceful Degradation

| Plugin | Available | Fallback |
|--------|-----------|----------|
| wicked-search | Index + validate | Scout-only mode (Glob/Grep) |
| wicked-mem | Store/recall discoveries | No persistence between sessions |
| wicked-delivery | Learning paths | Generic next steps |

If wicked-search is unavailable, skip Phase 1 indexing and Phase 3 validation. Exploration still works via Glob/Grep.

If wicked-mem is unavailable, skip memory storage. Report is still generated but not persisted.

## Examples

```bash
# Onboard current directory
/wicked-smaht:onboard

# Onboard specific path
/wicked-smaht:onboard /path/to/project

# Resume previous onboarding
/wicked-smaht:onboard --resume

# Skip indexing (just explore)
/wicked-smaht:onboard --skip-index
```
