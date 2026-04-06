---
name: requirements-graph-authoring
title: Graph-Based Requirements from Vague Brief
description: Transform a product brief into a requirements/ graph with atomic AC nodes, directory structure, and valid frontmatter
type: requirements
difficulty: intermediate
estimated_minutes: 15
---

# Graph-Based Requirements from Vague Brief

This scenario tests the requirements-graph skill's ability to produce a well-structured filesystem graph from a vague product brief — atomic AC files, proper directory hierarchy, valid frontmatter, and cross-references.

## Setup

Create a realistic but incomplete product brief:

```bash
# Create test project
mkdir -p ~/test-wicked-graph/task-management
cd ~/test-wicked-graph/task-management

# Create a vague brief
cat > brief.md <<'EOF'
# Task Management Feature

## Background
Our internal tool needs task management. Teams are using spreadsheets.

## What We Want
- Create and assign tasks
- Set due dates and priorities
- Some kind of board view (like Trello?)
- Notifications when things change

## Notes
- Should integrate with Slack
- Mobile-friendly
- Manager needs to see team progress
EOF
```

## Steps

### 1. Generate Requirements Graph

```bash
/wicked-garden:product:elicit brief.md
```

Instruct the agent to use graph mode (the default for complexity >= 3):

> "Produce requirements as a graph structure using the requirements-graph skill.
> Create the requirements/ directory with atomic AC files."

**Expected**: Agent creates a `requirements/` directory tree, NOT a monolithic markdown file.

### 2. Verify Directory Structure

Check that the graph has the expected layout:

```bash
find requirements/ -type f -name "*.md" | sort
```

**Expected structure** (areas may vary based on agent's decomposition):

```
requirements/
  meta.md
  _scope.md
  _risks.md
  _questions.md
  {area-1}/
    meta.md
    US-001/
      meta.md
      AC-001-*.md
      AC-002-*.md
    ...
  {area-2}/
    ...
```

**Check**:
- [ ] Root `meta.md` exists
- [ ] At least 2 feature areas as directories
- [ ] Each area has a `meta.md`
- [ ] At least 2 user stories (US-NNN directories) total
- [ ] Each story has at least 2 AC files
- [ ] `_scope.md` exists with in/out scope
- [ ] `_questions.md` exists with open questions

### 3. Validate Frontmatter Schema

For each AC file, verify YAML frontmatter:

```bash
# Check a sample AC file
head -20 requirements/*/US-*/AC-*.md
```

**Required AC frontmatter fields**:
- [ ] `id` — matches path (e.g., `tasks/US-001/AC-001`)
- [ ] `type: acceptance-criterion`
- [ ] `priority` — one of P0, P1, P2
- [ ] `category` — one of happy-path, error, edge-case, non-functional
- [ ] `story` — matches parent directory (e.g., `tasks/US-001`)

**AC body**:
- [ ] Contains Given/When/Then format
- [ ] Body is concise (under 10 lines, no essays)

### 4. Validate Story meta.md

```bash
# Check a story meta.md
cat requirements/*/US-001/meta.md
```

**Required story frontmatter**:
- [ ] `id` — matches path
- [ ] `type: user-story`
- [ ] `priority`, `complexity`, `persona`, `status`

**Story body**:
- [ ] Has As a/I want/So that block
- [ ] Has AC summary table listing child ACs
- [ ] Persona is specific (not generic "user")

### 5. Validate Area meta.md

```bash
cat requirements/*/meta.md
```

**Check**:
- [ ] `id` matches directory name
- [ ] `type: area`
- [ ] Has story summary table
- [ ] Has coverage section (even if 0%)

### 6. Validate Root meta.md

```bash
cat requirements/meta.md
```

**Check**:
- [ ] `type: requirements-root`
- [ ] Has area summary table with story/AC counts
- [ ] Links to _scope.md, _risks.md, _questions.md

### 7. Check Content Quality

**From the brief**, the agent should have:
- [ ] Identified at least 2 personas (e.g., team member, manager)
- [ ] Covered core flows: create task, assign, set due date, board view
- [ ] Addressed Slack integration (at least as a story or open question)
- [ ] Addressed mobile-friendly (as NFR or story)
- [ ] Surfaced open questions about the vague parts ("like Trello?", "some kind of")
- [ ] Not duplicated content between stories and functional requirements

## Expected Outcome

- `requirements/` directory with 15-25 files total
- 2-3 feature areas
- 4-6 user stories with specific personas
- 10-15 atomic AC files
- Valid YAML frontmatter on every node
- Open questions surfacing gaps in the brief
- No monolithic requirements document

## Success Criteria

- [ ] Graph structure created (not monolith)
- [ ] All AC files have valid frontmatter (id, type, priority, category, story)
- [ ] All story meta.md have valid frontmatter and As a/I want/So that
- [ ] IDs match file paths
- [ ] At least 2 distinct personas identified
- [ ] Open questions surface 3+ gaps from the brief
- [ ] AC bodies are concise Given/When/Then (not essays)
- [ ] Root meta.md aggregates areas with counts

## Cleanup

```bash
rm -rf ~/test-wicked-graph
```

## Value Demonstrated

**Real-world value**: Traditional requirements elicitation produces monolithic documents that are hard to trace, hard to query, and waste context when loaded by AI agents. The graph approach produces atomic, traceable nodes that:

- Load progressively (frontmatter only = 5 tokens per AC vs 800 tokens for full monolith)
- Enable coverage queries ("which P0 ACs lack tests?")
- Integrate naturally with crew phases (each phase adds trace edges)
- Scale down for simple features (3 ACs = 6 files) and up for complex ones
