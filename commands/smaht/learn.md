---
description: Learn a library by fetching docs via Context7 and storing a local cheatsheet
argument-hint: "<library> [--version <hint>] [--remove] [--update-all]"
---

# /wicked-garden:smaht:learn

Fetch live documentation for a library via Context7, synthesize it into a structured cheatsheet, and persist it locally. Future prompts mentioning this library will use the cached cheatsheet instead of making a live MCP call.

Supports update detection (diffs against cached version), deletion, and bulk refresh.

## Usage

```
/wicked-garden:smaht:learn react
/wicked-garden:smaht:learn fastapi --version 0.115
/wicked-garden:smaht:learn "next.js"
/wicked-garden:smaht:learn react --remove
/wicked-garden:smaht:learn --update-all
```

## Instructions

### 1. Parse Arguments

Extract from the command arguments:
- `library` (required unless `--update-all`): Library or framework name
- `--version` (optional): Version hint string (e.g. "18.x", "0.115")
- `--remove` (optional, flag): Delete the cached cheatsheet for this library
- `--update-all` (optional, flag): Re-fetch all cached cheatsheets and report changes

### 1a. Handle --remove

If `--remove` is present, delete the cheatsheet and stop:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/smaht/cheatsheet_store.py remove \
  --library "{library}"
```

Report the result:

```
Removed cheatsheet for {library}.

To re-learn it: /wicked-garden:smaht:learn {library}
```

If the library was not found, report that and stop.

### 1b. Handle --update-all

If `--update-all` is present, get the list of all cached libraries:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/smaht/cheatsheet_store.py update-all
```

This returns `{"libraries": [...], "count": N}`. For each library in the list, run the full learn flow (steps 2-6) sequentially, collecting the diff results. After all are processed, report a summary:

```
Updated {count} cheatsheet(s).

| Library    | Status      | Changes                     |
|------------|-------------|-----------------------------|
| react      | updated     | +2 APIs, -1 pattern         |
| fastapi    | no changes  | —                           |
| next.js    | updated     | +1 gotcha                   |
```

Then stop.

### 2. Resolve Library ID via Context7

Use the Context7 MCP tool to resolve the canonical library identifier. The tool name depends on your MCP server configuration — look for a `resolve-library-id` tool from a context7 server:

```
resolve-library-id(libraryName="{library}")
```

If resolution fails or returns no match, report to the user and stop:

```
Could not resolve "{library}" in Context7. Try a different spelling or check available libraries at https://context7.com.
```

### 3. Fetch Documentation

Use the Context7 `get-library-docs` tool with the resolved ID:

```
get-library-docs(
  libraryId="{resolved_id}",
  topic="key APIs and common patterns"
)
```

### 4. Synthesize Cheatsheet

Analyze the returned documentation and produce a structured cheatsheet JSON with this schema:

```json
{
  "library": "{library}",
  "version_hint": "{version or null}",
  "key_apis": [
    {
      "name": "FunctionOrClassName",
      "signature": "fn(arg: Type) -> ReturnType",
      "description": "One-sentence purpose",
      "example": "minimal usage snippet"
    }
  ],
  "common_patterns": [
    {
      "name": "Pattern name",
      "description": "What it solves",
      "code": "short illustrative snippet"
    }
  ],
  "gotchas": [
    "Pitfall or non-obvious behaviour worth noting"
  ],
  "source_url": "{canonical docs URL if available, else null}"
}
```

Target 5-10 key APIs and 3-5 common patterns. Focus on the 20% that covers 80% of usage.

> **Note**: The store script automatically adds `fetched_at`, `last_updated`, and `previous_fetched_at` metadata fields. You do not need to include them in the synthesized JSON.

### 5. Store the Cheatsheet

Persist via the cheatsheet store script:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/smaht/cheatsheet_store.py store \
  --library "{library}" \
  {--version-hint "{version}"} \
  --data '{synthesized_json}'
```

### 6. Confirm to User

The store script returns JSON with `updated` (boolean) and `diff` (object with `has_changes` and `changes`) fields.

**If this is a new cheatsheet** (`updated: false`):

```
Cheatsheet stored for {library}{version_hint}.

Key APIs captured: {count}
Common patterns: {count}
Gotchas noted: {count}

This cheatsheet will be used automatically when you ask about {library} — no live Context7 call needed.

To view all stored cheatsheets: /wicked-garden:smaht:libs
```

**If this is an update** (`updated: true`), show what changed:

```
Cheatsheet updated for {library}{version_hint}.

Key APIs captured: {count}
Common patterns: {count}
Gotchas noted: {count}

Changes from previous version:
  Key APIs: +{added} / -{removed}
  Patterns: +{added} / -{removed}
  Gotchas: +{added} / -{removed}

To view all stored cheatsheets: /wicked-garden:smaht:libs
```

If `diff.has_changes` is false, say "No changes detected — cheatsheet content is identical to the cached version." instead of the changes block.

## Graceful Degradation

| Condition | Behaviour |
|-----------|-----------|
| Context7 MCP unavailable | Report error; suggest manually providing docs |
| Library not found in Context7 | Inform user with suggested alternative spellings |
| DomainStore offline | Cheatsheet still stored locally via fallback |
