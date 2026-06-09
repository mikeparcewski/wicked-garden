# agentic:frameworks — Framework Selection / Comparison Rubric

Full rubric sourced from `agents/agentic/framework-researcher.md` and
`skills/agentic/frameworks/SKILL.md`. Use for framework selection, comparison,
or the interactive wizard. Always use WebSearch for latest 2026 ecosystem state.

## Mode Detection

| Args | Mode |
|------|------|
| `--compare fw1,fw2,...` | Side-by-side comparison table |
| `--language` / `--use-case` only | Filtered selection guide |
| No args | Interactive 5-question wizard |

## Wizard (no args)

Ask in order (do not batch):

1. What is the primary task? (RAG, stateful workflows, role-based team, conversational, pipeline)
2. What language/runtime? (Python, TypeScript, C#, any)
3. What's the team's experience level? (beginner, intermediate, expert)
4. What are the production constraints? (cloud vendor, compliance, existing infra)
5. What is the expected scale? (prototype, small prod, high-volume)

Use answers to pick from the decision tree below.

## Decision Tree

```
Primary use case?
├─ Complex stateful workflow with branches/loops → LangGraph
├─ Role-based team of agents → CrewAI or ADK
├─ RAG-heavy application → LlamaIndex Agents
├─ Multi-agent conversations/debates → AutoGen
├─ Simple sequential — TypeScript → ADK
├─ Simple sequential — Python → Pydantic AI or LangChain
├─ Production pipeline → Haystack or ADK
└─ Maximum flexibility → LangGraph or build from scratch
```

## Comparison Table (current as of 2026 — verify with WebSearch)

| Feature | LangGraph | CrewAI | AutoGen | ADK | Pydantic AI |
|---------|-----------|--------|---------|-----|-------------|
| State management | ✅ StateGraph | ✅ Memory | ✅ GroupChat | ✅ Built-in | ❌ Manual |
| Multi-agent | ✅ Subgraphs | ✅ Crew | ✅ Native | ✅ Agents | ⚠️ Custom |
| HITL | ✅ Interrupts | ⚠️ Custom | ✅ human_proxy | ✅ Native | ⚠️ Custom |
| Streaming | ✅ Native | ⚠️ Limited | ✅ Native | ✅ Native | ✅ Native |
| Checkpointing | ✅ Built-in | ❌ No | ❌ No | ✅ Built-in | ❌ No |
| Learning curve | Medium | Low | Medium | Medium | Low |
| Production readiness | ✅ Stable | ⚠️ Evolving | ✅ Stable | ⚠️ Growing | ⚠️ New |

**Legend**: ✅ Strong | ⚠️ Partial | ❌ Not available

## Framework Scoring Template (comparison mode)

For each framework in `--compare`:

```markdown
## {Framework} — Score: {total}/100

**Version** (from WebSearch): {latest stable}
**Community** (from WebSearch): {GitHub stars, Discord, activity}

| Requirement | Weight | Score | Weighted | Notes |
|-------------|--------|-------|----------|-------|
| Multi-agent coordination | 10 | {0-10} | {w*s} | |
| State management | 8 | | | |
| HITL support | 7 | | | |
| Observability | 6 | | | |
| Learning curve | 5 | | | |
| Community support | 5 | | | |
| Production readiness | 9 | | | |
| **Total** | **50** | | **{sum}** | |

**Best for**: {use case}
**Not ideal for**: {anti-use-case}
**Latest news**: {from WebSearch}
```

## Output Format

End every output with a pointer to the next step:

```
→ Next: `/wicked-garden:agentic:design` to turn this framework choice into a five-layer architecture.
```

For comparison mode, render the Decision Matrix:

```markdown
## Framework Decision Matrix

| Framework | Score/100 | Recommendation |
|-----------|-----------|----------------|
| {fw} | {n} | RECOMMEND / CONSIDER / AVOID |

**Top recommendation**: {framework} — {one-line rationale}
**Runner-up**: {framework}
```

For wizard mode, render a single recommendation with rationale referencing the user's answers.
