# agentic:review — Full Agentic Codebase Review Rubric

Full rubric sourced from `agents/agentic/architect.md`,
`agents/agentic/safety-reviewer.md`, `agents/agentic/performance-analyst.md`,
and `skills/agentic/review-methodology/`. Apply to the target path.

## Step 1: Framework + Topology Detection

Run the detection scripts directly:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/agentic/detect_framework.py --path "$TARGET_PATH"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/agentic/analyze_agents.py \
  --path "$TARGET_PATH" --framework "${FRAMEWORK_OVERRIDE:-$DETECTED_FRAMEWORK}"
```

If `--quick` is set, stop here and return the structural summary.

## Step 2: Architecture Assessment (Five-Layer)

Using `skills/agentic/agentic-patterns/` catalog, score each layer PASS / FAIL:

| Layer | Check |
|-------|-------|
| Cognition | Single-responsibility, clear reasoning pattern, prompt versioning |
| Context | Memory scoping, context limits respected, checkpointing |
| Interaction | Tool interfaces defined, rate limits handled, graceful degradation |
| Runtime | Orchestration strategy explicit, error handling, observability |
| Governance | Input/output validation, HITL gates positioned, audit logging |

**Topology health checks** (from `analyze_agents.py` output):
- Circular dependencies → CRITICAL
- God agents (>5 responsibilities) → HIGH
- Orphaned agents → MEDIUM
- Deep nesting (>4 levels) → MEDIUM

## Step 3: Safety Assessment (8-Layer)

Apply the full 8-layer rubric from `skills/agentic/refs/audit.md`.
Focus: tool risk, HITL, PII, prompt injection, failure modes.

Build risk matrix:

| Category | Findings | Critical | High | Medium |
|----------|----------|----------|------|--------|
| Tool Risk | | | | |
| HITL Gates | | | | |
| PII Handling | | | | |
| Prompt Injection | | | | |
| AuthN/AuthZ | | | | |
| Rate Limits | | | | |
| Observability | | | | |
| Failure Modes | | | | |

## Step 4: Performance Assessment

Using `skills/agentic/context-engineering/` and pattern catalog:

**Token analysis**:
- System prompt size and cacheability
- Context window utilization (target: leave 35%+ buffer)
- Opportunities for prompt compression

**Latency analysis**:
```bash
# Find sequential agent calls that could parallelize
grep -r "await.*agent\|agent\.run" --include="*.py" "$TARGET_PATH" -A 3
```

| Metric | Target | Finding |
|--------|--------|---------|
| Avg latency p50 | < 5s | |
| Sequential ops that can parallelize | 0 | |
| Cache hit rate | > 60% | |
| Cost per request | {baseline} | |

**Parallelization opportunities**: list agents that have no mutual dependencies
and can run with `asyncio.gather()`.

## Step 5: Pattern Scoring + Issue Taxonomy

Run the pattern scorer to get quantitative data:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/agentic/pattern_scorer.py \
  --agents "$AGENTS_FILE" --framework "$DETECTED_FRAMEWORK"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/agentic/issue_taxonomy.py \
  --findings "$FINDINGS_FILE" --agents "$AGENTS_FILE" \
  --framework "$FRAMEWORK_FILE" --format markdown
```

**Anti-pattern detection** (from `skills/agentic/agentic-patterns/refs/anti-patterns-design.md`):

| Anti-Pattern | Severity | Detection |
|--------------|----------|-----------|
| God Agent | HIGH | > 5 responsibilities |
| Circular Dependency | CRITICAL | A → B → A in call graph |
| State Mutation | HIGH | Shared mutable context |
| Error Swallowing | MEDIUM | bare `except: pass` |
| Tight Coupling | MEDIUM | Direct class instantiation |
| Duplicated Orchestration | LOW | Same pipeline in 2+ places |

## Output Format

```markdown
## Agentic Review: {Project}

**Date**: {date} | **Framework**: {fw} v{version} | **Path**: {path}

### Executive Summary
{2-3 sentences — overall health, top 2 risks, main recommendation}

### Five-Layer Architecture Scores

| Layer | Score | Top Finding |
|-------|-------|-------------|
| Cognition | PASS/FAIL | |
| Context | PASS/FAIL | |
| Interaction | PASS/FAIL | |
| Runtime | PASS/FAIL | |
| Governance | PASS/FAIL | |

### Safety Risk Matrix
{table from Step 3}

### Performance Summary
{token / latency / cost findings, parallelization opportunities}

### Issue Inventory by Severity

**CRITICAL** (fix immediately):
- {issue} — {file:line} — Fix: {action}

**HIGH** (before production):
- {issue} — {file:line} — Fix: {action}

**MEDIUM** (next sprint):
- …

### 4-Phase Remediation Roadmap

| Phase | Window | Items |
|-------|--------|-------|
| P0 | Immediate | CRITICAL items |
| P1 | This sprint | HIGH items |
| P2 | Next sprint | MEDIUM items |
| P3 | Backlog | LOW + tech debt |
```

Write to `$OUTPUT_FILE` when `--output` is set; otherwise return inline.
