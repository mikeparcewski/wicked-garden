# Feature Comparison: Wicked Garden vs Everything Claude Code

> Competitive analysis: `affaan-m/everything-claude-code` (ECC) vs `wicked-garden` (WG)
> Date: 2026-03-30

## Component Inventory

| Component | ECC | WG | Notes |
|-----------|-----|-----|-------|
| Agents | 30 | ~25+ (14 domains × specialists) | Different philosophy (see below) |
| Skills | 136 | 14 domains with progressive disclosure | WG deeper per-domain; ECC wider breadth |
| Commands | 60 | ~40+ (14 domains) | ECC more atomic; WG more orchestrated |
| Hooks | 15+ event types, ~28 hooks | 7 lifecycle hooks, 6 scripts | ECC more granular; WG more integrated |
| Rules | 34 (common + 12 languages) | 0 (rules embedded in skills/CLAUDE.md) | **Gap** |
| MCP Configs | 6 pre-configured | Integration-discovery routing | Different approach |
| Test Suite | Node.js-based | Scenario-based acceptance tests | Different paradigm |

## Where Functionality Crosses

### 1. Code Review

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| Entry point | `/code-review` command + `code-reviewer` agent | `/wicked-garden:engineering:review` | Comparable |
| Language awareness | Dedicated per-language reviewer agents (10 languages) | Single review with persona flag | **ECC** for breadth |
| Security review | Separate `security-reviewer` agent | Integrated via platform domain specialists | **WG** for depth |
| Architecture review | `architect` agent | engineering + platform specialists via crew | **WG** for orchestration |
| Database review | Dedicated `database-reviewer` agent | data domain specialists | Comparable |

**Verdict**: ECC has broader language coverage; WG has deeper, more integrated review workflows with gate enforcement.

### 2. Planning & Architecture

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| Planning | `/plan` command + `planner` agent | crew workflow with clarify/design phases | **WG** significantly |
| Multi-step plans | `/multi-plan` + `/multi-execute` | Crew phase system with dependencies, gates, checkpoints | **WG** |
| Architecture | `architect` agent | engineering specialists + crew design phase | **WG** |
| Complexity scoring | Not present | 0-7 complexity scoring with signal analysis | **WG** |

**Verdict**: WG's crew system is far more sophisticated. ECC's planning is single-agent.

### 3. Testing

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| TDD workflow | `/tdd` command + `tdd-guide` agent | qe domain specialists + test-strategy phase | **WG** for integration |
| E2E testing | `/e2e` command + `e2e-runner` agent | qe:acceptance command | Comparable |
| Test scenarios | Node.js test runner | Markdown-based acceptance scenarios | Different paradigm |
| Quality gates | PostToolUse hooks for quality checks | Hard gate enforcement with REJECT/CONDITIONAL | **WG** significantly |

**Verdict**: WG's gate enforcement system is a major differentiator.

### 4. Build & Error Resolution

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| Build fixing | `/build-fix` + 6 language-specific resolvers | No dedicated build resolution | **ECC** |
| Error diagnosis | Language-specific build resolver agents | General engineering agents | **ECC** |

**Verdict**: ECC's per-language build resolvers are a practical feature we lack.

### 5. Memory & Context

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| Memory store | `.tmp` files in `.claude/` + observation JSONL | DomainStore + SqliteStore with FTS5 | **WG** significantly |
| Session persistence | Hook-based (PreCompact, Stop, SessionStart) | PreCompact + Stop + bootstrap (all 3 hooks present) | **WG** for infrastructure |
| Context assembly | Manual system prompt injection | smaht 3-tier routing (HOT/FAST/SLOW) | **WG** significantly |
| Cross-session recall | File-based with manual loading | wicked-mem with BM25 search | **WG** |

**Verdict**: WG's memory infrastructure is far more sophisticated.

### 6. Security

| Aspect | ECC | WG | Better |
|--------|-----|-----|--------|
| Security scanning | AgentShield (1282 tests, 98% coverage) | No dedicated security scanning tool | **ECC** |
| Security guide | Comprehensive dedicated guide | Security practices in CLAUDE.md | **ECC** for documentation |
| Secret detection | Hook-based prompt scanning | No explicit secret scanning | **ECC** |
| Permission model | Deny rules for sensitive paths | Graceful degradation, fail-open | Different philosophy |

**Verdict**: ECC has more explicit security tooling. See [security-lessons.md](security-lessons.md).

## Features ECC Has That We Lack (Must-Haves)

### Tier 1: Must-Have

1. **Language-specific review/build agents** — Even if we keep our domain model, adding language-aware review criteria is essential. Users working in Go expect Go idioms to be checked.

2. **Rules system** — ECC has 34 always-loaded rules covering coding style, git workflow, testing, performance, security. We embed these in CLAUDE.md and skills, but having extractable, composable rules would improve governance.

3. **Enriched PreCompact hook** — We have `pre_compact.py` that serializes session state, but ECC's approach of also persisting learning artifacts and adapter results before compaction is worth adopting.

4. **Build error resolution** — `/build-fix` with language-aware resolvers is practical. Users hit build errors constantly; a dedicated resolution path saves time.

5. **Continuous learning / instinct system** — ECC's `/learn` command extracts reusable patterns from sessions and saves them as skill files. Instincts have confidence scoring with decay, can be clustered into skills via `/evolve`, and imported/exported for team sharing. Our wicked-mem stores learnings at gate failures and project completion, but lacks automated pattern extraction from general sessions.

### Tier 2: Should-Have

6. **Token/cost tracking** — ECC's Stop hook tracks token usage and costs per session. Useful for teams managing budgets.

7. **Desktop notifications** — ECC notifies users when long-running agent tasks complete. Simple quality-of-life improvement.

8. **Troubleshooting guide** — Dedicated troubleshooting documentation for common failure modes.

9. **Conventional commit enforcement** — Structured commit messages improve changelog generation.

10. **Example CLAUDE.md templates** — ECC provides 7 project-type-specific CLAUDE.md examples (SaaS/Next.js, Go microservice, Django API, Laravel, Rust API). Useful as onboarding accelerators.

11. **Hook profiles** — ECC supports `ECC_HOOK_PROFILE` (minimal/standard/strict) and `ECC_DISABLED_HOOKS` for granular hook control. Users can tune strictness per project.

### Tier 3: Nice-to-Have

12. **llms.txt pattern** — Using `/llms.txt` endpoints from documentation sites for LLM-optimized docs loading.

13. **Voice input guidance** — Documentation on using transcription tools with Claude Code.

14. **Status line customization** — Guidance on customizing the Claude Code status bar.

15. **Autonomous loop safeguards** — ECC's `loop-operator` agent enforces quality gates, eval baselines, rollback paths, and branch isolation before running autonomous loops. Detects stalls and retry storms.

## Features WG Has That ECC Lacks (Our Advantages)

1. **Crew workflow system** — Multi-phase, signal-based specialist routing with complexity scoring. ECC has nothing comparable.

2. **Gate enforcement** — Hard quality gates with REJECT/CONDITIONAL/rollback. ECC relies on advisory hooks.

3. **smaht context assembly** — 3-tier intelligent routing (HOT/FAST/SLOW) that intercepts every prompt. ECC requires manual context injection.

4. **Progressive disclosure skills** — 3-tier loading (frontmatter → SKILL.md → refs/) for context efficiency. ECC skills are flat files.

5. **DomainStore + SqliteStore** — Structured persistence with FTS5 search. ECC uses flat files.

6. **On-demand personas** — Dynamic specialist invocation with rich characteristics. ECC has fixed agent definitions.

7. **Kanban integration** — Automatic task lifecycle tracking via PostToolUse hooks.

8. **Cross-domain communication** — Direct Python imports between domain scripts. ECC components are isolated.

9. **Integration-discovery routing** — DomainStore auto-discovers MCP tools. ECC requires manual MCP configuration.

10. **Scenario-based acceptance testing** — Markdown-based test scenarios that validate end-to-end workflows.

## Architecture Philosophy Comparison

| Dimension | ECC | WG |
|-----------|-----|-----|
| **Organizing principle** | Component type (agents, skills, commands) | Domain (crew, engineering, platform, etc.) |
| **Depth vs. breadth** | Wide: 136 skills across many topics | Deep: 14 domains with progressive disclosure |
| **Orchestration** | Manual (user picks agents/commands) | Automated (crew routes to specialists) |
| **State management** | File-based, manual | Structured stores with search |
| **Quality enforcement** | Advisory hooks | Hard gates with reject/conditional |
| **Extension model** | Add more files | Scaffold into domain structure |
| **Target user** | Individual developer optimizing workflow | Teams running structured SDLC |

## Recommendation

WG's architecture is fundamentally stronger for complex, team-oriented workflows. ECC excels at breadth and individual developer convenience. The key gaps to close are:

1. Language-specific awareness in reviews
2. Build error resolution paths
3. PreCompact state protection
4. Extractable rules/governance system
5. Token economics documentation
