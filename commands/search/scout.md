---
description: Quick pattern reconnaissance for common code patterns (no index required)
argument-hint: <pattern-type> [--path PATH]
---

# /wicked-garden:search:scout

Quick pattern reconnaissance without needing to build an index first. Uses direct file search to find common code patterns.

## Arguments

- `pattern-type` (required): Type of pattern to scout for
- `--path` (optional): Directory to scout (default: current)

## Pattern Types

- `api` - Find API endpoints and routes
- `test` - Find test files and functions
- `config` - Find configuration files
- `auth` - Find authentication code
- `db` - Find database queries and models

## Instructions

1. Based on the pattern type, use Grep and Glob tools to search the target directory:

   **api**: Search for route/endpoint definitions
   ```
   Grep: @(Get|Post|Put|Delete|Patch|Route|RequestMapping|app\.(get|post|put|delete)|router\.)
   Glob: **/routes/**,  **/controllers/**, **/api/**
   ```

   **test**: Search for test files and test functions
   ```
   Glob: **/*test*, **/*spec*, **/__tests__/**
   Grep: (describe|it|test|@Test|def test_|class Test)
   ```

   **config**: Find configuration files
   ```
   Glob: **/*.{yml,yaml,json,toml,ini,env,cfg,conf}, **/config/**, **/.env*
   ```

   **auth**: Find authentication code
   ```
   Grep: (authenticate|authorize|jwt|token|session|login|logout|password|oauth|bearer)
   Glob: **/auth/**, **/security/**
   ```

   **db**: Find database queries and models
   ```
   Grep: (SELECT|INSERT|UPDATE|DELETE|@Entity|@Table|models\.Model|Schema|migration)
   Glob: **/models/**, **/entities/**, **/migrations/**, **/schema/**
   ```

2. Report findings grouped by pattern:
   - File locations
   - Key patterns found
   - Count of matches

## Example

```
/wicked-garden:search:scout api --path /path/to/project
/wicked-garden:search:scout db
/wicked-garden:search:scout auth --path src/
```

## Notes

- No index required - uses direct pattern matching
- Faster than indexing for quick reconnaissance
- For deep structural analysis, use `/wicked-garden:search:index` followed by query commands
