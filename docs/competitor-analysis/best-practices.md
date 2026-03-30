# Best Practices to Adopt from Everything Claude Code

> Competitive analysis: `affaan-m/everything-claude-code` (ECC) vs `wicked-garden` (WG)
> Date: 2026-03-30

## 1. Token Economics & Context Window Management

**What ECC does well**: ECC has explicit, documented strategies for token optimization that we lack.

### Recommendations

| Practice | ECC Approach | WG Status | Priority |
|----------|-------------|-----------|----------|
| Model selection per task | Haiku for search/docs, Sonnet for coding, Opus for architecture/security | We default to parent model for all subagents | **HIGH** |
| MCP replacement strategy | Replace heavy MCPs with lightweight CLI-wrapping skills/commands | We load MCPs without optimization guidance | **MEDIUM** |
| Context clearing discipline | `/clear` between unrelated tasks; `/compact` at breakpoints | smaht handles assembly but no explicit clearing guidance | **LOW** |
| MAX_THINKING_TOKENS limits | Recommends capping at 10K for cost control | No guidance | **MEDIUM** |
| Tool count discipline | Keep under 10 MCPs and 80 tools enabled | No explicit limits documented | **MEDIUM** |

### Action Items

- [ ] Add `model` field guidance to agent frontmatter standards (haiku/sonnet/opus selection criteria)
- [ ] Document token-conscious patterns in CLAUDE.md or a dedicated skill
- [ ] Evaluate which MCP integrations could be replaced with CLI-wrapping commands

## 2. Language-Specific Rules & Reviewers

**What ECC does well**: 12 language ecosystems with dedicated reviewers and build resolvers.

ECC provides:
- Language-specific code reviewers (Python, TypeScript, Go, Rust, Java, Kotlin, C++, Flutter)
- Language-specific build error resolvers (Go, Java, Kotlin, C++, Rust, PyTorch)
- Layered rules: `common/` base + `{language}/` overrides

### Current WG Gap

We have domain-based organization (engineering, platform, qe, etc.) but no language-specific specialization. Our `engineering:review` command is language-agnostic.

### Recommendations

- [ ] Add language-detection to `engineering:review` that loads language-specific review criteria
- [ ] Consider language-specific refs/ in the engineering skill for top languages (Python, TypeScript, Go, Rust)
- [ ] Evaluate whether language-specific build resolvers would add value (ECC's approach of per-language agents is pragmatic)

**Priority**: MEDIUM — Our domain-specialist approach is architecturally stronger, but language-specific review criteria would meaningfully improve review quality.

## 3. Continuous Learning & Session Persistence

**What ECC does well**: Explicit hooks for learning across sessions.

| Hook | Purpose | WG Equivalent |
|------|---------|---------------|
| `PreCompact` | Save critical state before context compaction | None |
| `Stop` | Persist learnings at session end | We have Stop hooks but for kanban sync, not learning |
| `SessionStart` | Auto-load previous context | We have bootstrap but focused on crew state, not general learning |

### Recommendations

- [ ] Add a `PreCompact` hook that persists smaht context and active crew state before compaction
- [ ] Enhance Stop hook to capture session learnings into wicked-mem (beyond just crew gate failures)
- [ ] Consider a "session reflection" pattern: at session end, extract patterns/gotchas into mem store

**Priority**: HIGH — We already have the wicked-mem infrastructure; we just need to wire it into more lifecycle hooks.

## 4. Evaluation & Benchmarking Patterns

**What ECC documents**: pass@k and pass^k metrics, checkpoint vs. continuous evals, worktree-based A/B testing.

### Recommendations

- [ ] Add evaluation methodology to our qe domain skills
- [ ] Document how to benchmark skill effectiveness (token usage before/after, success rate)
- [ ] Consider a `/wicked-garden:qe:benchmark` command that runs worktree-based A/B comparisons

**Priority**: MEDIUM — Useful for validating our own skills and for users evaluating their workflows.

## 5. Parallelization Best Practices

**What ECC documents**: Git worktree patterns, cascade method (3-4 max parallel tasks), two-instance kickoff.

### Current WG State

Our crew system supports parallel phase execution and parallel agent dispatch, but we don't document general parallelization patterns for users.

### Recommendations

- [ ] Document worktree-based parallel development patterns in a skill or guide
- [ ] Add guidance on when to fork vs. when to use crew parallel phases
- [ ] Consider a `/wicked-garden:crew:fork` command that sets up parallel worktree instances

**Priority**: LOW — Our crew system already handles orchestrated parallelism well.

## 6. Conventional Commits

**What ECC enforces**: `feat(skills):`, `fix(hooks):` conventional commit format with commitlint.

### Current WG State

No enforced commit convention. CLAUDE.md doesn't specify commit message format.

### Recommendations

- [ ] Adopt conventional commits with domain scoping: `feat(crew):`, `fix(smaht):`, `docs(engineering):`
- [ ] Add commit message guidance to CLAUDE.md
- [ ] Consider a pre-commit hook or delivery skill that enforces the format

**Priority**: MEDIUM — Improves changelog generation and release management.

## 7. Troubleshooting Documentation

**What ECC provides**: Dedicated TROUBLESHOOTING.md covering common failure modes, diagnostic techniques, environment variables for debugging.

### Current WG Gap

No troubleshooting guide. Users hitting issues have no reference.

### Recommendations

- [ ] Create a troubleshooting skill or ref doc covering common failure modes
- [ ] Document diagnostic environment variables and debugging techniques
- [ ] Add hook failure debugging guidance (our hooks fail-open, but users need to know how to diagnose)

**Priority**: MEDIUM — Improves adoption experience.

## Summary: Top 5 Practices to Adopt

1. **Model selection per subagent** — Assign haiku/sonnet/opus based on task complexity
2. **PreCompact hook for state persistence** — Don't lose critical context during compaction
3. **Session learning persistence** — Wire Stop hook into wicked-mem for pattern capture
4. **Language-specific review criteria** — Load language-aware refs in engineering:review
5. **Conventional commits** — Structured commit messages for better changelog/release flow
