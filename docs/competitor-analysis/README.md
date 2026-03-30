# Competitor Analysis: Everything Claude Code

> Analysis of `affaan-m/everything-claude-code` (ECC) — the most popular Claude Code plugin ecosystem (50K+ stars) — compared against Wicked Garden.
>
> Date: 2026-03-30

## Documents

| Document | Focus | Key Findings |
|----------|-------|-------------|
| [best-practices.md](best-practices.md) | Practices we should adopt | Model selection per subagent, PreCompact hooks, session learning, language-specific reviews, conventional commits |
| [feature-comparison.md](feature-comparison.md) | Functionality overlap & implementation quality | WG stronger in orchestration/gates/memory; ECC stronger in language breadth/security tooling |
| [cross-platform-strategy.md](cross-platform-strategy.md) | CLI/IDE cross-platform handling | ECC supports 5 platforms; recommend WG stays deep on Claude Code, exports portable knowledge layer |
| [security-lessons.md](security-lessons.md) | Security practices to adopt | Secret scanning, supply chain scanning, memory sanitization, deny rules |
| [competitive-insights.md](competitive-insights.md) | Strategic takeaways & recommendations | ECC wins breadth + convenience; WG wins depth + orchestration; close obvious gaps, maintain architectural advantages |

## TL;DR

**ECC** = breadth-first, individual-developer toolkit (136 skills, 30 agents, 5 platforms, 12 languages)
**WG** = depth-first, team SDLC engine (crew orchestration, quality gates, intelligent routing, structured persistence)

### Top 5 Action Items

1. Add **PreCompact hook** for state persistence before context compaction
2. Add **secret detection** in PreToolUse hooks
3. Add **language-specific review criteria** to engineering domain
4. Create **build error resolution** command/agent
5. Document **token economics** and model selection guidance

### Top 5 Advantages to Protect

1. **Crew workflow system** — multi-phase orchestration with signal-based routing
2. **Gate enforcement** — hard quality gates (REJECT/CONDITIONAL) vs advisory hooks
3. **smaht context assembly** — 3-tier intelligent routing (HOT/FAST/SLOW)
4. **Progressive disclosure skills** — 3-tier loading for context efficiency
5. **DomainStore + SqliteStore** — structured persistence with FTS5 search
