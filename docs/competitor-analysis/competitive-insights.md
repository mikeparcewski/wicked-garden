# Competitive Insights & Strategic Takeaways

> Competitive analysis: `affaan-m/everything-claude-code` (ECC) vs `wicked-garden` (WG)
> Date: 2026-03-30

## Executive Summary

**Everything Claude Code** (ECC) is the most popular Claude Code plugin ecosystem (50K+ stars, 6K+ forks, 30 contributors, 7 languages). It takes a **breadth-first, individual-developer** approach: lots of components, many platforms, community-driven growth.

**Wicked Garden** takes a **depth-first, team-oriented** approach: fewer components but deeply integrated with intelligent orchestration, quality gates, and structured persistence.

These are fundamentally different products serving different needs. The competitive risk isn't feature parity — it's that ECC's breadth and community momentum could make it the default choice before users discover they need WG's depth.

## What We Can Learn

### 1. Community & Adoption Strategy

**ECC's strengths**:
- MIT license, open contribution model
- 30+ community contributors
- Translated to Korean and Chinese
- Sponsorship program (GitHub Sponsors)
- Hackathon-winner branding ("battle-tested")
- Clear installation: one command via marketplace or `install.sh`

**Lesson**: Our technical depth means nothing if adoption is friction-heavy. We should:
- Simplify first-run experience
- Create a "quick wins" onboarding path (use 3 commands, see value in 5 minutes)
- Consider community contribution pathways for skills and scenarios
- Invest in the marketplace listing description and examples

### 2. Documentation as Product

ECC has **three separate guides**:
- `the-shortform-guide.md` — Quick setup and essentials (~5 min read)
- `the-longform-guide.md` — Deep patterns and strategies (~30 min read)
- `the-security-guide.md` — Comprehensive agentic security (~20 min read)

Plus: `TROUBLESHOOTING.md`, `EVALUATION.md`, `CONTRIBUTING.md`, `COMMANDS-QUICK-REF.md`, `SOUL.md`

**Lesson**: Documentation IS the product for a Claude Code plugin. Users discover value through docs, not through code. Our current docs (`getting-started.md`, `architecture.md`, `crew-workflow.md`, `domains.md`, `advanced.md`) are developer-focused. We need:
- A "shortform guide" that shows immediate value
- A command quick-reference card
- Better discoverability of what's possible

### 3. The "SOUL.md" Pattern

ECC's `SOUL.md` defines the project's identity, principles, and philosophy in a machine-readable way. This is used as a grounding document for AI agents working on the project.

**Lesson**: We should consider a similar identity document that:
- Defines WG's core philosophy (depth over breadth, orchestration over manual selection, quality gates over advisory checks)
- Serves as grounding context for contributors (human and AI)
- Differentiates us from ECC's "toolkit" approach

### 4. Breadth vs. Depth Trade-offs

| ECC Approach | Impact | WG Response |
|-------------|--------|-------------|
| 136 skills across many topics | Wide coverage, but shallow | Keep our progressive disclosure model; it's architecturally superior |
| 30 agents for specific languages | Immediate language support | Add language awareness to existing specialists rather than proliferating agents |
| 60 commands for quick actions | Low barrier to entry | Consider adding more atomic commands alongside our orchestrated workflows |
| 34 rules always loaded | Consistent governance | Evaluate a rules system as a new component type |

### 5. The Rules Gap

ECC's most distinctive feature that we entirely lack is the **rules system** — always-loaded guidelines organized by common + language-specific layers.

Rules differ from skills:
- **Skills** are loaded on demand based on relevance
- **Rules** are always active, enforcing baseline standards

WG embeds rules in CLAUDE.md and skill frontmatter, but they're not composable, layerable, or language-specific.

**Recommendation**: Consider adding a `rules/` directory to the plugin structure:
```
rules/
├── common/
│   ├── coding-style.md
│   ├── git-workflow.md
│   ├── testing.md
│   └── security.md
└── {language}/
    ├── python.md
    ├── typescript.md
    └── go.md
```

**Important caveat**: ECC notes that "Rules cannot be distributed via plugins and must be installed manually." This is a Claude Code platform limitation. We should verify if this is still the case and, if so, whether there's a workaround.

### 6. Continuous Learning System

ECC has a notable **instinct/learning system** that we should study:

- `/learn` extracts reusable patterns from sessions → saves as skill files to `~/.claude/skills/learned/`
- Patterns categorized as: error resolution, debugging techniques, workarounds, project-specific
- **Confidence scoring with decay** — instincts lose confidence over time if not reinforced
- `/evolve` clusters related instincts into higher-level skills
- Import/export for team sharing of learned patterns
- PreToolUse/PostToolUse hooks observe patterns during sessions (claimed "100% reliable")
- Expired pending instincts pruned after 30-day TTL

**WG comparison**: Our wicked-mem stores learnings at gate failures and project completion, but lacks:
- Automated pattern extraction from general sessions (not just crew workflows)
- Confidence scoring with temporal decay
- Clustering of related memories into higher-level patterns
- Easy team sharing/import/export of learned patterns

**Recommendation**: Evaluate whether wicked-mem should gain automated session pattern extraction. The instinct → evolve → skill pipeline is a compelling feedback loop. However, their flat-file approach is fragile compared to our FTS5 store.

### 7. Example CLAUDE.md Templates

ECC provides **7 project-type-specific CLAUDE.md examples** that serve as onboarding accelerators:
- Generic project, user-level config, SaaS/Next.js, Go microservice, Django API, Laravel API, Rust API

Each includes project-specific rules like "Never trust client-side price data — always fetch from Stripe server-side" (SaaS example).

**Lesson**: We could offer template CLAUDE.md files that reference wicked-garden skills for common project types. This would accelerate onboarding and demonstrate immediate value.

### 8. Token Economics Awareness

ECC is highly conscious of token costs and context window management. This resonates with users paying for Claude API usage.

**Key ECC patterns we should document**:
- Model selection table (which model for which task)
- MCP replacement strategy (CLI wrapping vs. full MCP)
- Tool count discipline (keep under 80 tools)
- Strategic context clearing patterns

### 7. The "Chief of Staff" Pattern

ECC has a `chief-of-staff` agent — a meta-orchestrator that coordinates other agents. This is conceptually similar to our crew system but implemented as a single agent rather than a workflow engine.

**Lesson**: The naming is good — "chief of staff" is immediately understandable. Our "crew" and "smaht" naming requires explanation. Consider adding user-friendly aliases or descriptions.

## Competitive Positioning Matrix

| Dimension | ECC Position | WG Position | Market Winner |
|-----------|-------------|-------------|---------------|
| **Individual dev productivity** | Strong (atomic commands, quick setup) | Moderate (orchestrated, learning curve) | ECC |
| **Team SDLC** | Weak (no workflow engine) | Very strong (crew, gates, specialists) | WG |
| **Security** | Strong (AgentShield, security guide) | Moderate (fail-open, no scanning) | ECC |
| **Multi-language** | Very strong (12 ecosystems) | Weak (language-agnostic) | ECC |
| **AI orchestration** | Basic (manual agent selection) | Very strong (smaht, signal routing) | WG |
| **Quality enforcement** | Advisory (hooks) | Mandatory (gate system) | WG |
| **Cross-platform** | Strong (5 IDEs) | Single platform | ECC |
| **Memory/persistence** | Basic (flat files) | Advanced (FTS5, DomainStore) | WG |
| **Community** | Large (50K stars) | Developing | ECC |
| **Documentation** | Excellent (3 guides) | Good (5 docs) | ECC |

## Strategic Recommendations

### Short-Term (Next Release)

1. **Enrich PreCompact hook** with smaht adapter results and learning artifacts
2. **Add secret scanning** to PreToolUse hooks
3. **Document token economics** in a skill or guide
4. **Create command quick-reference** card
5. **Enhance wg-check** with injection pattern scanning

### Medium-Term (Next Quarter)

6. **Language-specific review criteria** in engineering skills
7. **Build error resolution** command/agent
8. **Rules system** evaluation and prototype
9. **Shortform getting-started guide** focused on immediate value
10. **Conventional commits** with domain scoping

### Long-Term (Strategic)

11. **Portable knowledge layer** for cross-platform export
12. **Community contribution pathways** for skills and scenarios
13. **Security audit skill** with comprehensive guidance
14. **Evaluation/benchmarking** commands in qe domain
15. **Session reflection** pattern wired into wicked-mem

## What NOT to Copy

1. **Don't chase platform count** — ECC's 5-platform support is mostly shallow. Depth on Claude Code is more valuable than breadth across IDEs.

2. **Don't flatten our architecture** — ECC's flat file approach (136 independent skills) is simpler but doesn't scale for complex workflows. Our domain + progressive disclosure model is architecturally superior.

3. **Don't add 30 language-specific agents** — Instead, make our existing specialists language-aware. One `engineering:review` agent that loads Python criteria is better than separate `python-reviewer`, `go-reviewer`, `rust-reviewer` agents.

4. **Don't adopt their memory approach** — Our DomainStore + SqliteStore + FTS5 is far more capable than their flat file + JSONL approach.

5. **Don't copy their hook sprawl** — ECC has 28+ hooks many of which overlap. Our 7 focused hooks with Python scripts are more maintainable.

## Final Assessment

ECC is a strong competitor in the **breadth + convenience** space. WG is stronger in the **depth + orchestration** space. The biggest risk is that ECC's community momentum and low friction make it the default choice for users who would actually benefit from WG's capabilities.

**The play**: Close the obvious gaps (language awareness, security scanning, token economics docs), maintain our architectural advantages (crew, smaht, gates, progressive disclosure), and invest in the adoption experience (docs, quick-start, marketplace listing).
