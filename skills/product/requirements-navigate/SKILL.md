---
name: requirements-navigate
description: |
  Navigate, query, and maintain requirements graphs. Regenerates meta.md
  on demand, checks coverage, finds gaps, and lints the graph structure.

  Use when: "show requirements", "coverage report", "requirements status",
  "refresh meta", "lint requirements", "find gaps", "navigate requirements"
---

# Requirements Navigate

Read, query, and maintain requirements graph structures. Generates and
refreshes meta.md files. Checks coverage and finds gaps.

## Commands

### Navigate (read graph)

Read a requirements node or area with progressive depth:

**Depth 0** — frontmatter only (~5 tokens per node):
```bash
# Read just the frontmatter of all ACs in a story
for f in requirements/auth/US-001/AC-*.md; do
  head -20 "$f"  # frontmatter block
done
```

**Depth 1** — meta.md (summary + tables):
```bash
# Read the story summary
cat requirements/auth/US-001/meta.md
```

**Depth 2** — full content of specific nodes:
```bash
# Read a specific AC
cat requirements/auth/US-001/AC-001-login-success.md
```

**Always start at depth 1** (meta.md) unless you need specific AC content.

### Refresh meta.md

Regenerate a meta.md from its children when stale:

1. Read all sibling/child files in the directory
2. Parse frontmatter from each
3. Rebuild the summary table (counts, priorities, coverage stats)
4. Write updated meta.md preserving the `id` and `type` fields

**Staleness check**: Compare `generated_at` in meta.md frontmatter against
`stat()` mtimes of children. If any child is newer, regenerate.

**When to refresh**:
- Before displaying requirements status to user
- Before crew gate evaluation
- After batch AC creation
- On explicit user request

### Coverage Query

Check which ACs have trace links:

```
For each AC in requirements/**/*.md where type: acceptance-criterion:
  - Has IMPLEMENTED_BY? → code coverage
  - Has TESTED_BY? → test coverage
  - Has VERIFIES? → verification coverage
```

**Output format**:
```
Coverage: auth
  US-001: 3/3 ACs, 1/3 implemented, 0/3 tested
  US-002: 2/2 ACs, 0/2 implemented, 0/2 tested
  Total: 5 ACs, 1 implemented (20%), 0 tested (0%)
```

### Gap Analysis

Find structural problems:

- **Orphan ACs**: AC files not referenced in parent story meta.md
- **Empty stories**: Story directories with meta.md but no AC files
- **Missing traces**: P0 ACs without IMPLEMENTED_BY or TESTED_BY
- **Broken traces**: Trace targets that don't exist on disk
- **Stale meta.md**: Generated timestamps older than children
- **ID mismatches**: `id:` field doesn't match file path

### Lint

Validate graph structure:

```
For each .md in requirements/**/:
  1. Has valid YAML frontmatter with required fields
  2. id: matches relative path from requirements/
  3. type: is a valid node type
  4. traces: targets exist (warn, don't fail — code may not exist yet)
  5. ACs have: priority, category, story
  6. Stories have: priority, complexity, persona, status
  7. meta.md tables match actual children
```

**Fix mode**: `--fix` auto-corrects:
- Regenerate stale meta.md files
- Update `id:` to match current path
- Add missing AC references to parent meta.md

## Integration with traceability.py

The navigate skill reads graph nodes directly. For cross-phase queries
that span beyond requirements (design, code, tests, evidence),
`traceability.py` provides BFS traversal.

**Bridge**: When navigate finds `IMPLEMENTED_BY` or `TESTED_BY` traces
in frontmatter, these are the authoritative links for the requirement
layer. `traceability.py` can read these as an additional data source
alongside its DomainStore links.

## Integration with search

Requirements graph nodes are indexable by `search:index`:

```bash
/wicked-garden:search:index requirements/
```

Enables queries like:
- "All P0 ACs without TESTED_BY" (frontmatter + FTS5)
- "All ACs tagged 'authentication'" (tag search)
- "Which stories trace to src/auth/" (reverse trace)

## Progressive Disclosure

- **SKILL.md** (this file): Commands, query patterns, integration
- **refs/meta-templates.md**: Copy-paste meta.md templates for each level
