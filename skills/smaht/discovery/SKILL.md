---
name: discovery
description: |
  Contextual command discovery — suggests related commands based on what was just used.
  Discovers relationships dynamically from command/skill content, not a static map.
  Invoked by the Stop hook and smaht:briefing to surface one relevant suggestion.
user-invocable: false
---

# Contextual Discovery

After a command or skill runs, suggest ONE related command the user hasn't tried.

## How It Works

Relationships are discovered dynamically, not hardcoded:

### 1. Parse the just-used command/skill

Read the command's `.md` file from `commands/{domain}/{command}.md`. Look for:
- **Explicit references** to other commands (e.g., `/wicked-garden:search:blast-radius`)
- **"See also"** or **"Integration"** sections listing related commands
- **Agent dispatches** (`subagent_type="wicked-garden:{domain}:{agent}"`) — the dispatched agent's domain has related commands
- **Skill references** (`Skill(skill="wicked-garden:{domain}:{skill}")`) — related domain commands

### 2. Check what the user has already used this session

Query session state for commands invoked in this session. Only suggest commands NOT already used.

### 3. Rank candidates

Priority:
1. Commands explicitly referenced in the just-used command's `.md` file
2. Commands in the same domain (sibling commands)
3. Commands in domains listed in the "Integration" section
4. Cross-domain commands that share the same specialist role

### 4. Select ONE suggestion

Pick the highest-ranked candidate the user hasn't used. Frame contextually:
- Include a specific argument from the current context when possible
- Use the user's own terms (file paths, symbol names, project descriptions)

## Selection Rules

1. Pick ONE suggestion (never more)
2. Only suggest commands the user has NOT used in this session
3. Match based on the most recent command, not full session history
4. If no good match, suggest nothing — silence is better than noise
5. Frame as a question: "You might find X useful" not "Run X"
6. Include specific arguments from context when possible (symbol name, file path)

## Common Patterns

These natural workflows emerge from command cross-references:

- **Review → Impact**: After reviewing code, check what depends on it
- **Search → Plan**: After finding a symbol, plan the change
- **Brainstorm → Store**: After deciding something, persist the decision
- **Analyze → Synthesize**: After understanding data, generate recommendations
- **Scenarios → Automate**: After defining test scenarios, generate test code
- **Security → Compliance**: After security scan, check regulatory alignment
- **Incident → Store**: After resolving an incident, capture learnings
