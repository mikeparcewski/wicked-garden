---
name: change-type-detector
description: |
  Classifies a list of file paths into change types (ui, api, both, unknown)
  using an explicit two-pass decision algorithm: extension matching first,
  then path-segment matching for ambiguous cases.

  Use when: "detect change type", "classify files", "what kind of change",
  "ui or api change", "change-type detection", or before creating test tasks.
---

# Change Type Detector Skill

Classify file paths to determine which test types are needed.

## Output Format

```json
{
  "change_type": "ui|api|both|unknown",
  "ui_files": [...],
  "api_files": [...],
  "ambiguous_files": [...],
  "confidence": 0.0-1.0,
  "reasoning": "file1: reason; file2: reason; ..."
}
```

## Two-Pass Classification Algorithm

Apply to EACH file independently, then combine results.

### Pass 1 — Extension Matching (ordered)

**Rule 1.1 — UI Extensions (unambiguous by default)**

Files with these extensions classify as `ui`:
`.tsx, .jsx, .vue, .svelte, .html, .htm, .css, .scss, .sass, .less`

**Exception — .tsx-in-api/ override rule (apply before returning ui)**:
If a UI-extension file has API path segments (api, routes, controllers,
handlers, endpoints, server, backend, services, graphql, rest, grpc,
middleware, resolvers, mutations, queries) AND no UI path segments,
AND the task description contains API keywords — classify as `api`.
Otherwise keep `ui` (extension wins).

**Rule 1.2 — API-Confirming Extensions**

Files with `.py, .rb, .go, .java, .kt, .rs, .cs, .php, .scala, .clj, .ex, .exs`:
- If path has API segments → `api`
- If path has UI segments → `ambiguous` (treat as both)
- Otherwise → `api` (default for backend languages)

**Rule 1.3 — Ambiguous Extensions**

Files with `.ts, .js, .mjs, .cjs` → proceed to Pass 2.

**Rule 1.4 — Unrecognized Extensions**

All other extensions (.md, .yaml, .json, .sh, Makefile, etc.):
- If path has UI segments only → `ui`
- If path has API segments only → `api`
- If path has both → `ambiguous`
- If path has neither → `unrecognized` (does not contribute to change type)

### Pass 2 — Path Segment Matching (for .ts/.js/.mjs/.cjs only)

Check path segments (split on `/`, lowercase) against segment tables.

| Outcome | Condition |
|---------|-----------|
| `ui` | Has UI segment, no API segment |
| `api` | Has API segment, no UI segment |
| Use task description | Has both UI and API segments |
| Use task description | Has neither UI nor API segment |

**Task description tiebreaker**: tokenize description on non-alphanumeric
characters, check against API keywords and UI keywords (see
[File Classification Rules](refs/file-classification-rules.md)).
- API keywords only → `api`
- UI keywords only → `ui`
- Both or neither → `ambiguous`

## Combining File Results

After classifying all files:

| Files Present | change_type | confidence |
|---------------|-------------|------------|
| Only ui_files | `ui` | 1.0 |
| Only api_files | `api` | 1.0 |
| Both ui + api | `both` | 0.9 |
| ambiguous_files present | promotes to `both` | 0.7 |
| Only unrecognized | `unknown` | 0.8 |
| No files | `unknown` | 1.0 |

Ambiguous files are conservative: they promote the result to `both` (over-inclusive).

## Quick Decision Table

| Extension | Path Signals | Task Keywords | Result |
|-----------|-------------|---------------|--------|
| .tsx/.jsx/.vue/.svelte | — | — | `ui` |
| .tsx + api/ path | API kws in desc | yes | `api` |
| .css/.scss/.sass/.less | — | — | `ui` |
| .html/.htm | — | — | `ui` |
| .py/.rb/.go/.java/.kt | api/ path | — | `api` |
| .py/.rb/.go/.java/.kt | — (no path) | — | `api` |
| .ts/.js | components/ | — | `ui` |
| .ts/.js | api/ routes/ | — | `api` |
| .ts/.js | neither | API kws | `api` |
| .ts/.js | neither | UI kws | `ui` |
| .ts/.js | neither | neither | `ambiguous` |
| .md/.yaml/.json | — | — | `unrecognized` |

See [File Classification Rules](refs/file-classification-rules.md) for the
complete extension tables, path segment tables, and keyword lists.
