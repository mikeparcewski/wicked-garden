---
name: wicked-garden-smaht-discovery
description: |
  Contextual discovery — suggests a related skill or action based on what was
  just used. Discovers relationships dynamically from skill content, not a
  static map. Invoked by the Stop hook and the smaht `briefing` sub-action
  (skills/smaht/refs/briefing.md, step 5) to surface one relevant suggestion.
user-invocable: false
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# Contextual Discovery

After a skill or action runs, suggest ONE related skill or action the user hasn't tried.

## How It Works

Relationships are discovered dynamically, not hardcoded:

### 1. Parse the just-used skill/action

Read the skill's `SKILL.md` from `skills/{domain}/SKILL.md` (the consolidated
per-domain router skill; for a sub-action, that same file documents the action).
Look for:
- **Explicit references** to other skills/actions (e.g., the `wicked-garden-search` skill's `blast-radius` action)
- **"See also"** or **"Integration"** sections listing related skills
- **Fork-worker dispatches** (`Skill(skill="wicked-garden-{domain}-{role}")`, or the legacy `subagent_type="wicked-garden:{domain}:{role}"` compat form) — the dispatched worker's domain has related skills
- **Skill references** (`Skill(skill="wicked-garden-{domain}")`) — related domain skills

### 2. Check what the user has already used this session

Query session state for skills/actions invoked in this session. Only suggest ones NOT already used.

### 3. Rank candidates

Priority:
1. Skills/actions explicitly referenced in the just-used skill's `SKILL.md`
2. Sibling actions in the same domain skill
3. Skills in domains listed in the "Integration" section
4. Cross-domain skills that share the same specialist role

### 4. Select ONE suggestion

Pick the highest-ranked candidate the user hasn't used. Frame contextually:
- Include a specific argument from the current context when possible
- Use the user's own terms (file paths, symbol names, project descriptions)

## Selection Rules

1. Pick ONE suggestion (never more)
2. Only suggest skills/actions the user has NOT used in this session
3. Match based on the most recent skill/action, not full session history
4. If no good match, suggest nothing — silence is better than noise
5. Frame as a question: "You might find X useful" not "Run X"
6. Include specific arguments from context when possible (symbol name, file path)

## Common Patterns

These natural workflows emerge from skill cross-references:

- **Review → Impact**: After reviewing code, check what depends on it
- **Search → Plan**: After finding a symbol, plan the change
- **Brainstorm → Store**: After deciding something, persist the decision
- **Analyze → Synthesize**: After understanding data, generate recommendations
- **Scenarios → Automate**: After defining test scenarios, generate test code
- **Security → Compliance**: After security scan, check regulatory alignment
- **Incident → Store**: After resolving an incident, capture learnings
