# Agent Lift Eval — v12 Surface Cut (2026-06-12)

## Method

A per-agent **blinded lift eval** compared a baseline arm (base model, no agent
prompt) against an agent arm (base model + the agent's system prompt) on
representative tasks for each agent's domain. An **independent grader** (not the
arm being measured) scored outputs. "Lift" = the measured quality delta of the
agent arm over the baseline arm.

- **lift = 0** → the agent's dedicated system prompt produced no measurable
  improvement over the base model on its own domain tasks. The agent is pure
  overhead (extra surface, extra dispatch hop, no benefit) → **cut candidate**.
- **lift = +1** → the agent measurably improves on the base model → **keep**.
- Differentiated agents (security, compliance, privacy, a11y, ui-reviewer,
  agentic/\*, jam/council, qe/semantic-reviewer, persona-agent, migration-engineer,
  requirements-analyst) and all crew agents were **out of scope** for the cut —
  kept regardless.

## Scorecard

| Agent | Lift | Decision | Notes |
|-------|------|----------|-------|
| engineering/senior-engineer | 0 | **CUT** | Code-quality review now inline via engineering review skill / crew:reviewer |
| engineering/backend-engineer | 0 | **CUT** | Inline via engineering skill |
| engineering/frontend-engineer | 0 | **CUT** | Inline via engineering skill |
| engineering/debugger | 0 | **CUT** | Inline via engineering debugging skill (skill `agent:` binding removed) |
| engineering/technical-writer | 0 | **CUT** | Narrative docs inline; API docs → api-documentarian |
| product/product-manager | 0 | **CUT** | No live command/skill dispatch; routing repointed |
| product/user-researcher | 0 | **CUT** | Research lens folded into ux-designer dispatch |
| product/market-strategist | 0 | **CUT** | Market lens runs inline in product:strategy |
| platform/sre | 0 | **CUT** | Log/triage inline via platform errors + observability skills |
| platform/incident-responder | 0 | **CUT** | Inline via /platform:incident command + incident archetype |
| data/data-analyst | 0 | **CUT** | Routes to data-engineer / data analysis skill inline |
| data/data-architect | 0 | **CUT** | Data modeling → solution-architect / data-engineer |
| data/ml-engineer | 0 | **CUT** | Routes to data-engineer |
| skills/product/product-management | 0 | **CUT (skill)** | Superseded by acceptance-criteria + requirements-analysis skills |
| engineering/solution-architect | +1 | **KEEP** | Untouched |
| product/ux-designer | +1 | **KEEP** | Untouched; now also carries the research lens |
| product/value-strategist | +1 | **KEEP** | Untouched; carries the value lens in product:strategy |

## Result

- **14/14 candidates cut** (13 agents + 1 skill). **0 kept-due-to-wiring.**
- Net agent count: **36 → 23** (−13). Product skills: 16 → 15 (−1).
- No candidate's removal broke the build; every reference degraded cleanly to a
  kept agent or inline skill execution. The `specialist_resolver` degrades unknown
  roles to `(None, None)` (same path as the persona fallback) — verified for all
  cut roles.

## Graceful degradation map (how each reference class was handled)

1. **Command dispatches (hard wiring, would fail ref-integrity test):**
   - `commands/product/ux-review.md` user-researcher dispatch → folded into the
     ux-designer dispatch (research lens shares the same artifact + reviewer skill).
   - `commands/product/strategy.md` market-strategist dispatch → market lens now
     runs inline; value lens kept via value-strategist.
2. **Skill `agent:` frontmatter binding:** `skills/engineering/debugging/SKILL.md`
   `agent: debugger` removed → the debugging skill runs inline.
3. **Skill-ref prose / dispatch tables:** engineering/refs/{review,docs}.md,
   product/refs/{ux-review,strategy}.md, engineering/engineering/SKILL.md,
   platform/errors/SKILL.md, archetype/refs/review.md, persona/SKILL.md,
   integration-discovery/refs/{task-patterns,discovery-sources}.md — repointed to
   kept agents (solution-architect, api-documentarian, crew:reviewer/implementer,
   data-engineer, value-strategist) or to inline skill execution.
4. **Soft advisor:** `scripts/smaht/adapters/delegation_adapter.py` hints repointed
   (review→crew:reviewer, debug→solution-architect, data→data-engineer). Advisory
   only; not gated.
5. **Registry:** `.claude-plugin/components.json` regenerated via
   `scripts/ci/sync_components.py` (agents_by_domain, summary, skills_by_domain).
   `specialist.json` unchanged — it lists **domains**, not individual agents, and
   every cut domain (engineering, product, platform, data) still has live agents.
6. **Scenarios (`scenarios/crew/facilitator-rubric/*`, etc.):** left as-is. They
   are frozen eval/benchmark fixtures naming roles in expected-role checklists; no
   test or CI executes them, and the orphan checker only flags agents that *exist*
   but are unreached, so stale scenario names do not regress any gate. Touching the
   rubric fixtures would corrupt their baselines.
7. **docs/domains.md:** updated for accuracy (descriptive; excluded from orphan
   rooting).

## Verification (all green, post-cut)

- `python3 scripts/ci/find_orphan_agents.py` → 23 agents, 23 live, **0 orphaned**
- `python3 -m pytest tests/test_command_agent_refs_resolve.py -q` → **7 passed**
  (was 9; the 2 removed command dispatches dropped out)
- `python3 -m pytest tests/qe tests/compiler tests/crew tests/sentinel -q` →
  **265 passed** (unchanged from baseline)
- `python3 scripts/ci/validate.py` → **PASS (0 errors, 0 warnings)**
- `tests/persona -q` → 23 passed
- Resolver degradation verified: all cut roles → `(None, None)`; 3 KEEP agents
  resolve correctly and are untouched on disk.
