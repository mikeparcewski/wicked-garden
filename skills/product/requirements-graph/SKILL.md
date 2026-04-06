---
name: requirements-graph
description: |
  Graph-based requirements as atomic markdown files with rich frontmatter.
  Filesystem-as-graph: each AC is a node, directories are groupings,
  meta.md files are the human interface, frontmatter traces are the edges.

  Use when: "requirements", "user stories", "acceptance criteria",
  "elicit requirements", "define requirements", "graph requirements"
---

# Requirements Graph

Atomic, graph-structured requirements using the filesystem. Each acceptance
criterion is a file. Each user story is a directory. Traces live in frontmatter.
`meta.md` files aggregate for humans.

## Why Graph Over Monolith

| Monolith (old) | Graph (new) |
|----------------|-------------|
| 200-260 line single file | 10-30 line atomic nodes |
| Duplicates stories + functional reqs | One node per concept |
| Traceability in separate store | Traces in frontmatter |
| Grep for coverage | FTS5 + frontmatter queries |
| All-or-nothing context load | Progressive: frontmatter, meta.md, or full |

## Directory Layout

```
requirements/
  meta.md                             # Project-level summary
  {area}/                             # Epic/feature area (kebab-case)
    meta.md                           # Area summary + story table
    {US-NNN}/                         # User story directory
      meta.md                         # Story definition + AC table
      {AC-NNN}-{slug}.md             # Atomic acceptance criterion
    {NFR-NNN}-{slug}.md              # Non-functional requirements (area-level)
  _decisions/                         # ADR-style decision records
    {DEC-NNN}-{slug}.md
  _scope.md                           # In/out/future scope
  _risks.md                           # Risk register
  _questions.md                       # Open questions
```

## Node Types

Five node types, each a small markdown file with YAML frontmatter:

| Type | Lives at | Required fields |
|------|----------|----------------|
| `acceptance-criterion` | `{area}/{US-NNN}/{AC-NNN}-{slug}.md` | id, type, priority, category, story |
| `user-story` | `{area}/{US-NNN}/meta.md` | id, type, priority, complexity, persona, status |
| `area` | `{area}/meta.md` | id, type |
| `nfr` | `{area}/{NFR-NNN}-{slug}.md` | id, type, priority, category, target |
| `decision` | `_decisions/{DEC-NNN}-{slug}.md` | id, type, status, date |
| `requirements-root` | `meta.md` | type, project, created, status |

**Minimal AC** (the atomic unit):

```yaml
---
id: auth/US-001/AC-001
type: acceptance-criterion
priority: P0
category: happy-path
story: auth/US-001
---

Given valid credentials
When user submits login form
Then user is redirected to dashboard and session is created
```

12 lines. See `refs/schema.md` for all fields and `refs/examples.md` for
complete story, area, NFR, and decision examples.

## Frontmatter Schema

**Required fields** (all node types):
- `id` — path-derived slug, canonical reference
- `type` — `acceptance-criterion`, `user-story`, `area`, `nfr`, `decision`, `requirements-root`

**Required for ACs**:
- `priority` — P0/P1/P2
- `category` — happy-path, error, edge-case, non-functional
- `story` — parent story slug

**Required for stories**:
- `priority`, `complexity`, `persona`, `status`

**Optional (all types)**:
- `traces` — list of `{target, type}` objects (graph edges)
- `tags` — keyword list for search
- `compliance` — regulatory refs (SOC2, HIPAA, GDPR controls)

**Trace types** (edges):
- `DECOMPOSES_TO` — story to ACs
- `TRACES_TO` — requirement to design
- `IMPLEMENTED_BY` — AC to source code
- `TESTED_BY` — AC to test file
- `VERIFIES` — test result back to AC
- `SATISFIES` — evidence to requirement
- `DEPENDS_ON` — cross-story/cross-area dependency

## Authoring Process

### 1. Initialize graph

Create `requirements/` with root meta.md, _scope.md, _questions.md:

```bash
mkdir -p requirements
# Write root meta.md, _scope.md, _risks.md, _questions.md
```

### 2. Create areas from discovery

For each feature area, create `requirements/{area}/meta.md`.

### 3. Decompose into stories

For each story, create `requirements/{area}/{US-NNN}/meta.md` with
the As a/I want/So that definition.

### 4. Write atomic ACs

For each acceptance criterion, create individual files:
`requirements/{area}/{US-NNN}/{AC-NNN}-{slug}.md`

**Keep AC files small**: Given/When/Then + frontmatter. No essays.

### 5. Add traces as work progresses

Update `traces:` frontmatter as code and tests are written.
Traces are bidirectional by convention — if AC-001 has
`IMPLEMENTED_BY: src/login.ts`, the navigate skill can reverse-query.

## Crew Integration

| Crew Phase | Graph Action |
|------------|-------------|
| clarify | Create requirements/ structure, areas, stories, ACs |
| design | Add TRACES_TO links from stories to design docs |
| build | Add IMPLEMENTED_BY links from ACs to code |
| test | Add TESTED_BY links from ACs to test files |
| review | Navigate skill generates fresh meta.md, gate checks coverage |

## Progressive Disclosure

- **SKILL.md** (this file): Overview, layout, schema, process
- **refs/schema.md**: Complete frontmatter reference with all fields
- **refs/examples.md**: Full worked examples for different project types
