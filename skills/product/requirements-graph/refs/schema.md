# Requirements Graph: Frontmatter Schema Reference

Complete field reference for all requirement node types.

## Common Fields (all types)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | yes | string | Path-derived slug from `requirements/` root. E.g., `auth/US-001/AC-001` |
| `type` | yes | enum | Node type (see below) |
| `tags` | no | string[] | Keywords for search indexing |
| `traces` | no | object[] | Graph edges to other artifacts |
| `compliance` | no | string[] | Regulatory controls. E.g., `["SOC2-CC6.1", "GDPR-Art.32"]` |

## Node Types

### `acceptance-criterion`

The atomic unit. One file per criterion.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `priority` | yes | enum | `P0`, `P1`, `P2` |
| `category` | yes | enum | `happy-path`, `error`, `edge-case`, `non-functional` |
| `story` | yes | string | Parent story slug. E.g., `auth/US-001` |
| `status` | no | enum | `draft`, `review`, `approved`, `implemented`, `verified` |

**Body**: Given/When/Then block. Keep it to 1-5 lines. No essays.

**Naming**: `AC-{NNN}-{slug}.md` where NNN is zero-padded, slug is kebab-case.

### `user-story`

A directory's `meta.md`. Groups acceptance criteria.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `priority` | yes | enum | `P0`, `P1`, `P2` |
| `complexity` | yes | enum | `S`, `M`, `L`, `XL` |
| `persona` | yes | string | Who this story is for |
| `status` | yes | enum | `draft`, `review`, `approved`, `implemented`, `verified` |

**Body**: As a/I want/So that + AC summary table + dependencies + questions.

**Naming**: Directory is `US-{NNN}` (zero-padded). `meta.md` inside.

### `area`

Groups stories by feature/epic. Directory `meta.md`.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `status` | no | enum | `draft`, `review`, `approved` |

**Body**: Summary + story table + NFR table + coverage stats.

**Naming**: Directory is kebab-case feature name. `meta.md` inside.

### `nfr`

Non-functional requirement. Lives at area level.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `priority` | yes | enum | `P0`, `P1`, `P2` |
| `category` | yes | enum | `performance`, `security`, `scalability`, `usability`, `reliability` |
| `target` | yes | string | Measurable target. E.g., `< 2s at 1000 concurrent` |
| `measured_by` | no | string | How to verify |

**Naming**: `NFR-{NNN}-{slug}.md`

### `decision`

Lightweight ADR. Lives in `_decisions/`.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `status` | yes | enum | `proposed`, `accepted`, `superseded` |
| `date` | yes | string | ISO date |
| `supersedes` | no | string | ID of decision this replaces |

**Naming**: `DEC-{NNN}-{slug}.md`

### `requirements-root`

Root `meta.md` only. One per project.

| Field | Required | Type | Values |
|-------|----------|------|--------|
| `project` | yes | string | Project name |
| `created` | yes | string | ISO date |
| `status` | yes | enum | `draft`, `review`, `approved` |

## Traces Schema

Each trace is an edge in the graph:

```yaml
traces:
  - target: path/to/artifact    # relative path or code file
    type: IMPLEMENTED_BY         # edge type
```

### Edge Types

| Type | From | To | Direction |
|------|------|----|-----------|
| `DECOMPOSES_TO` | story | AC | parent → child |
| `TRACES_TO` | requirement | design doc | forward |
| `IMPLEMENTED_BY` | AC | source file | forward |
| `TESTED_BY` | AC | test file | forward |
| `VERIFIES` | test result | AC | reverse |
| `SATISFIES` | evidence | requirement | reverse |
| `DEPENDS_ON` | story/AC | story/AC | lateral |

### Trace Target Conventions

- **Graph nodes**: relative from `requirements/` root — `auth/US-001/AC-001`
- **Code files**: relative from project root — `src/auth/login.ts`
- **Test files**: relative from project root — `tests/auth/login.test.ts`
- **Design docs**: relative from project root — `phases/design/auth-flow.md`
- **External**: full path or URL

## ID Convention

The `id` field is a **path-derived slug**:

```
requirements/auth/US-001/AC-001-login-success.md
              ↓
id: auth/US-001/AC-001
```

Rules:
- Strip `requirements/` prefix
- Strip file extension
- For meta.md: use directory path (e.g., `auth/US-001`)
- For AC/NFR files: use up to the AC/NFR number (drop the slug suffix)

**Lint catches mismatches** between `id:` and actual path.

## Minimal Valid AC

```yaml
---
id: auth/US-001/AC-001
type: acceptance-criterion
priority: P0
category: happy-path
story: auth/US-001
---

Given valid email and password
When user submits login form
Then session is created and user sees dashboard
```

12 lines. Compare to the old monolith's 260 lines for an entire feature.
