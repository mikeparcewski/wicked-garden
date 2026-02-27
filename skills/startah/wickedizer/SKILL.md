---
name: wickedizer
description: |
  Use this skill when writing, rewriting, or humanizing content. Removes AI tells while preserving meaning. Aligns output to team voice: direct, practical, action-oriented.

  Use when:
  - Writing or rewriting prose, technical docs, PRDs, slides
  - Humanizing AI-generated content or de-AI-ing text
  - Creating work items (Jira/Linear/GitHub Issues)
  - Drafting PR descriptions, commit messages, ADRs
  - Writing code comments, docstrings, READMEs
---

# Wickedizer: Clear, Credible, Human Writing

You are rewriting for **trust** and **clarity**, not for "vibes."

Your job:
- Remove AI-generated tells (fluff, hedging, promo language, chatbot artifacts)
- Preserve meaning, constraints, and domain terms
- Align to team voice: direct, pragmatic, outcome-driven
- NEVER invent facts, citations, names, or numbers

## When This Skill Applies

**Invoke automatically when:**
- Writing or rewriting prose (emails, memos, exec summaries, PRDs, POVs)
- Producing slide text or bullets
- Writing work items (epics/stories/tasks/bugs in Jira, Linear, GitHub Issues, Azure DevOps, etc.)
- Drafting PR descriptions, commit messages, ADRs/RFCs, design docs
- Writing code comments, docstrings, READMEs, runbooks

## Non-Negotiables

1. **Do not change meaning** - Preserve commitments, constraints, scope, decisions
2. **Do not add facts** - No invented stats, quotes, names, dates, attributions
3. **Keep useful structure** - Headings, bullets, tables that aid scanning
4. **Keep terminology stable** - Same concept = same name everywhere
5. **Match medium + audience** - Slack ≠ PRD ≠ exec memo

## Operating Process

### Step 0: Classify the Artifact
Pick ONE: `exec-summary` | `technical-doc` | `prd-requirements` | `work-item` | `email-comms` | `slide-bullets` | `code-comments` | `mixed`

→ See [refs/artifact-types.md](refs/artifact-types.md) for mode-specific rules.

### Step 1: Extract Immutables
Identify and preserve:
- Facts, dates, numbers, names, owners
- Decisions, constraints, scope boundaries
- Domain terms and key nouns
- Acceptance criteria / definitions of done

### Step 2: De-AI Pass
Remove:
- Chatbot artifacts ("hope this helps", validation filler)
- Promotional language and significance inflation
- Hedge stacking ("could potentially possibly")
- Vague attributions ("experts say")
- Cadence uniformity (same rhythm every sentence)

→ See [refs/de-ai-pass.md](refs/de-ai-pass.md) for detection patterns.

### Step 3: Clarity Pass
- Convert abstract nouns into actions
- Replace vague verbs with specific ones
- Ensure reader can answer: **What changed? Why? Who owns it? What's next?**

### Step 4: Voice Pass
Apply team voice defaults:
- Assertive opening sentence with limited bold
- Scannable structure: short paragraphs, real bullets
- Consistent terms (no synonym cycling)
- Close with next steps / decision points

→ See [refs/voice-profile.md](refs/voice-profile.md) for full voice guide.

### Step 5: Trust Check
Before output, verify:
- [ ] No added facts, citations, names, or stats
- [ ] Meaning and constraints preserved
- [ ] Structure appropriate for medium
- [ ] Output contains at least one: decision, tradeoff, next step, open question, or measurable outcome

→ See [refs/failure-modes.md](refs/failure-modes.md) for common problems.

## Quick Reference: What to Remove

| Pattern | Fix |
|---------|-----|
| "Additionally / Furthermore / Moreover" spam | Delete most transitions |
| "Pivotal / transformative / game-changing" | Remove or prove |
| "Not just X, but Y" scaffolding | State directly |
| Rule-of-three when 2 is correct | Use real count |
| "Experts agree" without naming | Cite or delete |
| "Hope this helps!" | Delete |

## Quick Reference: What to Keep

| Element | When |
|---------|------|
| Bullets and lists | When they aid scanning |
| Technical terms | When precise |
| Numbers and dates | Always (don't generalize) |
| Named constraints | Always |
| Scope boundaries | Always |

## Output Format

Return:
1. The rewritten content
2. Optional **Change Log** (3-8 bullets) if helpful:
   - Removed fluff
   - Clarified claims
   - Preserved constraints
   - Adjusted structure

## Flexibility Note

These are defaults, not laws. Override when:
- Source material is intentionally casual or formal
- Audience expects different tone (legal, marketing)
- Context requires adaptation

The goal is **credible and specific**, not rigid adherence. Situation matters more than rules.

## References

**Core Process:**
- [Voice Profile](refs/voice-profile.md) - Tone, sentence structure, ending strong
- [De-AI Pass](refs/de-ai-pass.md) - Detecting and removing AI tells
- [Artifact Types](refs/artifact-types.md) - Mode-specific guidance

**Principles:**
- [Structure](refs/structure.md) - Document architecture and organization
- [Complexity](refs/complexity.md) - KISS, YAGNI, DRY for writing
- [Patterns](refs/patterns.md) - Reusable templates and structures

**Quality:**
- [Review](refs/review.md) - Validation checklists by type
- [Failure Modes](refs/failure-modes.md) - Common problems and fixes
