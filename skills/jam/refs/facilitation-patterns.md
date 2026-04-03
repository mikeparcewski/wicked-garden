# Facilitation Patterns

Match persona archetypes to problem types for effective brainstorming sessions.

## Problem → Persona Map

### Architecture Decisions
**When**: choosing between technical approaches, evaluating trade-offs, designing systems

| Persona | Why They Matter |
|---------|----------------|
| Pragmatic Engineer | Builds it — knows what's realistic |
| System Architect | Sees structural consequences 5 years out |
| Ops/SRE | Lives with the decision in production |
| New Team Member | Tests learnability and documentation needs |

**Session type**: Full brainstorm (2 rounds). Round 1: independent assessment. Round 2: challenge each other's assumptions.

### Product Scope Decisions
**When**: deciding what to build, prioritizing features, defining MVP

| Persona | Why They Matter |
|---------|----------------|
| Product Manager | Balances business value vs effort |
| End User | Experiences the outcome directly |
| Support Engineer | Sees the failure modes |
| Skeptic | Challenges assumptions about demand |

**Session type**: Full brainstorm (2-3 rounds). Include a "what would we cut?" round.

### Process / Workflow Changes
**When**: changing how the team works, adopting tools, modifying release processes

| Persona | Why They Matter |
|---------|----------------|
| Team Lead | Manages the human impact |
| Individual Contributor | Does the actual work under the process |
| Maintainer | Thinks about long-term sustainability |
| External Stakeholder | Affected by the change but has no control |

**Session type**: Quick jam (1 round). Process decisions benefit from speed — long debates create analysis paralysis.

### Creative / Naming / Positioning
**When**: naming things, writing copy, positioning a product, crafting messaging

| Persona | Why They Matter |
|---------|----------------|
| Marketing Strategist | Knows what resonates in the market |
| Developer Advocate | Bridges technical accuracy and approachability |
| Casual User | Tests whether the name/message is intuitive |
| Brand Skeptic | Catches cringe, overreach, or inauthenticity |

**Session type**: Quick jam. Creative decisions die in committee — one round forces decisive opinions.

### Risk Assessment / Incident Response
**When**: evaluating risk, planning for failure, post-incident analysis

| Persona | Why They Matter |
|---------|----------------|
| Security Engineer | Sees attack vectors |
| SRE | Knows what breaks at scale |
| Compliance Officer | Knows what's legally required |
| Customer Advocate | Represents the user impact of failures |

**Session type**: Full brainstorm. Risk needs thoroughness — optimism bias is the enemy.

### Greenfield / Exploration
**When**: starting from scratch, exploring a new space, evaluating feasibility

| Persona | Why They Matter |
|---------|----------------|
| Visionary | Imagines the best possible outcome |
| Pragmatist | Anchors to what's buildable today |
| Skeptic | Asks "why would this fail?" |
| User Researcher | Asks "does anyone actually want this?" |

**Session type**: Full brainstorm (2 rounds). Round 1: dream. Round 2: reality-check.

## Anti-Patterns

### Avoid These Persona Combinations

- **All technical personas** — produces technically elegant solutions nobody wants
- **All business personas** — produces strategies that can't be built
- **All agreeable personas** — produces consensus without insight (strawman risk)
- **More than 6 personas** — produces noise; diminishing returns after 5-6

### Facilitation Mistakes

- **Summarizing instead of synthesizing** — synthesis finds the non-obvious connection between viewpoints; summary just lists them
- **Resolving tension too early** — productive disagreement between personas is the point; don't smooth it over in round 1
- **Ignoring the quiet persona** — if a persona has nothing to say, the panel is wrong for the problem, not the persona
- **Skipping confidence levels** — "HIGH confidence" vs "LOW confidence" is the most valuable signal in synthesis

## Adapting Session Length

| Signal | Recommendation |
|--------|---------------|
| User says "quick" or "gut check" | Quick jam — 1 round, 4 personas |
| User says "important" or "strategic" | Full brainstorm — 2-3 rounds, 5-6 personas |
| Complexity score >= 4 in crew | Full brainstorm with domain-specific personas |
| Ambiguity detected in clarify phase | Full brainstorm focused on framing the problem |
| Time pressure ("we need to decide today") | Quick jam — speed > thoroughness |
| User says "converge fast" or "get to the point" | Full brainstorm with `--converge fast` — personas + early exit |

## Convergence Assessment

After each discussion round, the facilitator should assess convergence before proceeding:

**Converged (skip remaining rounds in fast mode):**
- 2+ actionable insights have emerged
- Personas broadly agree on direction (details may differ)
- Remaining disagreements are well-characterized trade-offs, not confusion

**Not converged (continue to next round):**
- Personas are talking past each other (different framing, different assumptions)
- Key tensions are unresolved and unclear
- No actionable insight has emerged yet
- A persona raised a concern that others have not addressed

The goal is to reach synthesis as soon as the discussion has produced enough signal. Extra rounds that merely reinforce existing positions waste time without adding insight.
