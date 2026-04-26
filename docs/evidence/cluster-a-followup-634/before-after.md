# Before / After: crew:status empty-sections suppression

## Issue

PR #634 (v8.1.0) intended to suppress `### Phase Progress` when a project has
no phase work yet. The guard was `if phases:` (non-empty dict check), but
`phase_manager.py status --json` always returns a populated `phases` dict via
the `get_phase_order` topology fallback. The guard was unreachable.

---

## Bug 1: unreachable suppression guard

### Before (v8.1.0, PR #634)

```
Only render `### Phase Progress` when the `phases` dict from
`phase_manager.py status --json` is non-empty. If `phases` is empty
(project has no phases started yet), skip this section entirely — do
not emit the header or an empty table.
```

**What actually rendered for a project with no phase plan:**

```markdown
## wicked-garden:crew Project Status

**Project**: my-project
**Phase**: clarify
**Status**: pending
**Complexity**: 0/7 (review tier: minimal)

### Phase Progress

| Phase        | Status  | Notes   |
|--------------|---------|---------|
| ideate       | pending | {notes} |
| clarify      | pending | {notes} |
| design       | pending | {notes} |
| test-strategy| pending | {notes} |
| challenge    | pending | {notes} |
| build        | pending | {notes} |
| test         | pending | {notes} |
| review       | pending | {notes} |
| operate      | pending | {notes} |

### Next Steps
...
```

Problems:
- 9 meaningless "pending" rows from topology fallback
- `{notes}` placeholder rendered literally (no source field in Dict[str, str])
- Guard never fired because `phases` was always non-empty

### After (this PR)

```
Only render `### Phase Progress` when the project has real phase progress
to show. Suppress this section (skip the header and table entirely) when
**all** of the following are true:
- `phase_plan` from the JSON output is null or empty (no committed plan yet), AND
- every value in the `phases` dict is `"pending"` (no phase has been started)
```

**What renders for a project with no phase plan (suppressed):**

```markdown
## wicked-garden:crew Project Status

**Project**: my-project
**Phase**: clarify
**Status**: pending
**Complexity**: 0/7 (review tier: minimal)

### Available Integrations (Level 1)
...

### Next Steps

Run `/wicked-garden:crew:start` to begin the crew workflow for this project.
```

**What renders for a project mid-phase (shown):**

```markdown
## wicked-garden:crew Project Status

**Project**: my-project
**Phase**: build
**Status**: in_progress
**Complexity**: 4/7 (review tier: standard)

### Phase Progress

| Phase         | Status      |
|---------------|-------------|
| clarify       | completed   |
| design        | completed   |
| test-strategy | completed   |
| build         | in_progress |
| test          | pending     |
| review        | pending     |

### Available Integrations (Level 2)
...

### Next Steps
Continue build phase with `/wicked-garden:crew:execute`.
```

---

## Bug 2: `{notes}` placeholder with no source field

### Before

```markdown
| Phase | Status | Notes |
|-------|--------|-------|
| {phase} | {status} | {notes} |
```

`phase_manager.py status --json` returns `phases: Dict[str, str]` (phase name
→ status string only). There is no `notes` field. The `{notes}` placeholder
would render literally.

### After

```markdown
| Phase | Status |
|-------|--------|
| {phase} | {status} |
```

Notes column removed. If a notes source is added to the JSON schema in future,
it can be re-introduced then.

---

## Bug 3: Stale `qe` alias in Available Integrations table

### Before

```markdown
| product | built-in | qe, review |
```

`qe` was the legacy alias; the current phase name is `test-strategy`.

### After

```markdown
| product | built-in | test-strategy, review |
```
