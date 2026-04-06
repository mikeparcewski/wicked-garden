---
name: requirements-migrate
description: |
  Convert monolithic requirements documents into graph-structured
  requirements directories. Parses user stories and acceptance criteria
  from existing docs and creates atomic graph nodes.

  Use when: "migrate requirements", "convert to graph",
  "split requirements", "restructure requirements"
---

# Requirements Migrate

Convert existing monolithic requirements documents into the graph structure.

## Process

### 1. Parse Source Document

Read the monolithic requirements file and extract:
- User stories (As a/I want/So that blocks)
- Acceptance criteria (Given/When/Then blocks)
- Functional requirements (REQ-XXX entries)
- Non-functional requirements (REQ-PERF/SEC/SCALE/UX entries)
- Scope (in/out/future)
- Risks, assumptions, open questions
- Dependencies

### 2. Plan Graph Structure

Map extracted content to graph nodes:
- Group stories by feature area (infer from headings or REQ prefixes)
- Each story becomes a `US-NNN` directory
- Each AC becomes an `AC-NNN-{slug}.md` file
- Functional requirements that duplicate stories are merged (not duplicated)
- NFRs become area-level `NFR-NNN-{slug}.md` files
- Decisions/rationale become `_decisions/DEC-NNN-{slug}.md`

### 3. Create Graph

```
For each area:
  mkdir -p requirements/{area}
  Write requirements/{area}/meta.md

  For each story in area:
    mkdir -p requirements/{area}/{US-NNN}
    Write requirements/{area}/{US-NNN}/meta.md

    For each AC in story:
      Write requirements/{area}/{US-NNN}/{AC-NNN}-{slug}.md

  For each NFR in area:
    Write requirements/{area}/{NFR-NNN}-{slug}.md

Write requirements/meta.md (root)
Write requirements/_scope.md
Write requirements/_risks.md
Write requirements/_questions.md
```

### 4. Verify

After migration:
- Run navigate lint to check structure
- Compare AC count: source doc vs graph nodes (should match)
- Check no content was lost (stories, criteria, NFRs)
- Verify frontmatter IDs match paths

### 5. Archive Source

Move the original monolith to `requirements/_archived/` so it's
preserved but not the active source of truth.

## Handling Ambiguity

- **Stories without clear ACs**: Create the story directory + meta.md,
  add a note in `_questions.md` that ACs need to be defined
- **Functional reqs that aren't stories**: If REQ-XXX doesn't map to a
  user story, create it as an AC under a synthetic story
- **Inline NFRs**: Extract performance/security mentions from story text
  into area-level NFR nodes
- **Missing personas**: Default to the most common persona in the doc,
  flag in `_questions.md`

## Progressive Disclosure

- **SKILL.md** (this file): Migration process
