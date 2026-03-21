# File Classification Rules

Complete extension tables, path segment tables, and keyword lists for the
change-type-detector skill. Rules are ordered — apply earlier rules first
and stop when a match is found.

---

## Extension Classification Tables

### Table 1 — UI Extensions (Pass 1, Rule 1.1)

These extensions classify a file as `ui` without needing path confirmation.

| Extension | Rationale |
|-----------|-----------|
| `.tsx` | React/TypeScript component |
| `.jsx` | React/JavaScript component |
| `.vue` | Vue single-file component |
| `.svelte` | Svelte component |
| `.html` | HTML document |
| `.htm` | HTML document (alternate) |
| `.css` | Stylesheet |
| `.scss` | Sass stylesheet |
| `.sass` | Sass stylesheet (indent syntax) |
| `.less` | Less stylesheet |

**Exception — .tsx-in-api/ override rule**

Applied BEFORE returning `ui` for the extensions above. This rule fires
when all three conditions are true:

1. File has a UI extension (from Table 1)
2. File path contains at least one API path segment (Table 3) AND no UI path segments (Table 2)
3. Task description contains at least one API keyword (Table 5)

When the override fires: classify as `api` with reasoning:
`"UI extension {ext} overridden by API path segments and API task description keywords"`

When the override does NOT fire (any condition false): classify as `ui` (extension wins).

**Design rationale**: Next.js API routes use `.ts`/`.tsx` in `pages/api/` directories.
The API path context is a stronger signal than the extension for these files.

---

### Table 2 — API-Confirming Extensions (Pass 1, Rule 1.2)

These extensions need path context to confirm API classification.

| Extension | Language |
|-----------|----------|
| `.py` | Python |
| `.rb` | Ruby |
| `.go` | Go |
| `.java` | Java |
| `.kt` | Kotlin |
| `.rs` | Rust |
| `.cs` | C# |
| `.php` | PHP |
| `.scala` | Scala |
| `.clj` | Clojure |
| `.ex` | Elixir |
| `.exs` | Elixir script |

**Classification rules (in order)**:

| Condition | Result | Confidence |
|-----------|--------|------------|
| Path has API segment | `api` | High |
| Path has UI segment (no API) | `ambiguous` | Medium — backend file in UI dir |
| No path signal | `api` | Medium — backend languages default to API |

---

### Table 3 — Ambiguous Extensions (Pass 2 required)

| Extension | Notes |
|-----------|-------|
| `.ts` | TypeScript — used in both frontend and backend |
| `.js` | JavaScript — used in both frontend and backend |
| `.mjs` | ES module — context-dependent |
| `.cjs` | CommonJS module — context-dependent |

---

## Path Segment Tables

Path segments are derived by splitting the file path on `/` (normalize `\` to `/`
first) and lowercasing all parts.

### Table 4 — UI Path Segments

A file path containing any of these segments indicates UI code.

| Segment | Context |
|---------|---------|
| `components` | React/Vue/Angular components |
| `pages` | Page-level components (but see api/ override) |
| `views` | MVC views |
| `layouts` | Layout templates |
| `templates` | HTML/component templates |
| `ui` | Explicit UI directory |
| `frontend` | Frontend-specific code |
| `client` | Client-side code |
| `public` | Public static files |
| `static` | Static assets |
| `styles` | Stylesheets |
| `assets` | Static assets |
| `icons` | Icon files |
| `images` | Image files |
| `fonts` | Font files |
| `stories` | Storybook stories |
| `src/app` | Next.js src/app router (multi-segment match) |

**Multi-segment matching**: `src/app` matches when the path contains the
substring `src/app` (join segments with `/` and check for substring).

---

### Table 5 — API Path Segments

A file path containing any of these segments indicates API code.

| Segment | Context |
|---------|---------|
| `api` | API directory (e.g., `pages/api/`, `src/api/`) |
| `routes` | Router definitions |
| `controllers` | MVC controllers |
| `handlers` | Request handlers |
| `endpoints` | API endpoint definitions |
| `server` | Server-side code |
| `backend` | Backend-specific code |
| `services` | Service layer |
| `graphql` | GraphQL schema/resolvers |
| `rest` | REST API |
| `grpc` | gRPC service definitions |
| `middleware` | HTTP middleware |
| `resolvers` | GraphQL resolvers |
| `mutations` | GraphQL mutations |
| `queries` | GraphQL queries |

---

## Keyword Tables (Task Description Resolution)

Used as tiebreaker when path segments are ambiguous or absent.
Tokenize the task description on non-alphanumeric characters (split on `[^a-z0-9]+`)
and match whole tokens against these sets.

### Table 6 — API Keywords

`api, endpoint, route, handler, controller, request, response, payload, schema,
contract, webhook, rest, graphql, grpc, rpc, http, get, post, put, patch, delete,
service, middleware, resolver, mutation, query, server-side, backend`

### Table 7 — UI Keywords

`component, render, view, page, style, layout, visual, ui, form, button, modal,
dialog, menu, nav, navigation, frontend, client-side, browser, display, css, scss,
animation, transition, theme, accessibility, a11y, wcag`

**Tiebreaker logic**:

| API keywords matched | UI keywords matched | Result |
|---------------------|--------------------|---------|
| Yes | No | `api` |
| No | Yes | `ui` |
| Yes | Yes | `ambiguous` (conservative, treated as both) |
| No | No | `ambiguous` (no signal) |

---

## Ambiguity Resolution Rules

These rules apply when a file cannot be definitively classified:

**Rule A1** — Ambiguous files are collected in `ambiguous_files` list.
**Rule A2** — If `ambiguous_files` is non-empty, the overall `change_type` is
promoted to `both` (over-inclusive conservative fallback).
**Rule A3** — Confidence is 0.7 when ambiguous files contribute to the result.
**Rule A4** — Unrecognized files (docs, config, etc.) go in `unrecognized_files`
and do NOT contribute to `change_type`.

---

## Edge Cases

| Scenario | Rule | Result |
|----------|------|--------|
| Empty file list | — | `unknown`, confidence 1.0 |
| All unrecognized | A4 | `unknown`, confidence 0.8 |
| `.tsx` in `pages/api/handler.tsx` with "Add request handler" desc | .tsx-in-api/ override | `api` |
| `.py` in `components/` | Rule 1.2 + UI path | `ambiguous` |
| `.ts` in `src/` with no path signal, no keywords | Pass 2 fallback | `ambiguous` |
| `.json` in `api/` | Rule 1.4 + API path | `api` |
| `.md` in `docs/` | Rule 1.4 + no signal | `unrecognized` |
