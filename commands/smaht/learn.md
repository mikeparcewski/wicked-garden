---
description: Learn a library by fetching docs via Context7 and storing a local cheatsheet
argument-hint: "<library> [--version <hint>]"
---

# /wicked-garden:smaht:learn

Fetch live documentation for a library via Context7, synthesize it into a structured cheatsheet, and persist it locally. Future prompts mentioning this library will use the cached cheatsheet instead of making a live MCP call.

## Usage

```
/wicked-garden:smaht:learn react
/wicked-garden:smaht:learn fastapi --version 0.115
/wicked-garden:smaht:learn "next.js"
```

## Instructions

### 1. Parse Arguments

Extract from the command arguments:
- `library` (required, positional): Library or framework name
- `--version` (optional): Version hint string (e.g. "18.x", "0.115")

### 2. Resolve Library ID via Context7

Call the Context7 MCP tool to resolve the canonical library identifier:

```
mcp__context7__resolve-library-id(libraryName="{library}")
```

If resolution fails or returns no match, report to the user and stop:

```
Could not resolve "{library}" in Context7. Try a different spelling or check available libraries at https://context7.com.
```

### 3. Fetch Documentation

Call Context7 to retrieve key documentation using the resolved ID:

```
mcp__context7__get-library-docs(
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

### 5. Store the Cheatsheet

Persist via the cheatsheet store script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/cheatsheet_store.py" store \
  --library "{library}" \
  {--version-hint "{version}"} \
  --data '{synthesized_json}'
```

### 6. Confirm to User

Report success with a summary:

```
Cheatsheet stored for {library}{version_hint}.

Key APIs captured: {count}
Common patterns: {count}
Gotchas noted: {count}

This cheatsheet will be used automatically when you ask about {library} — no live Context7 call needed.

To view all stored cheatsheets: /wicked-garden:smaht:libs
```

## Graceful Degradation

| Condition | Behaviour |
|-----------|-----------|
| Context7 MCP unavailable | Report error; suggest manually providing docs |
| Library not found in Context7 | Inform user with suggested alternative spellings |
| StorageManager offline | Cheatsheet still stored locally via fallback |
