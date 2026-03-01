---
name: sync
description: |
  Keep documentation in sync with code changes. Detect stale docs, identify documentation
  drift, and suggest updates when code changes.

  Use when: "check doc freshness", "sync docs", "find stale documentation",
  "update docs", "docs out of sync"
---

# Sync Documentation Skill

Keep documentation fresh by detecting when code changes have made docs stale.

## Purpose

Maintain documentation accuracy:
- Detect code changes that affect docs
- Identify stale documentation
- Suggest specific updates
- Track documentation freshness
- Prevent documentation drift

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:engineering:sync` | Check all documentation freshness |
| `/wicked-garden:engineering:sync [path]` | Check specific path |
| `/wicked-garden:engineering:sync --fix` | Auto-update where possible |

## Quick Start

```bash
# Check all documentation
/wicked-garden:engineering:sync

# Check specific directory
/wicked-garden:engineering:sync src/api

# Auto-fix simple issues
/wicked-garden:engineering:sync --fix
```

## Detection Strategies

Compare file timestamps (code modified after docs = STALE).
Compare function signatures (code vs docs = DRIFT).
Validate API specs against code (path/method mismatches = DRIFT).

## Issue Categories

**STALE** - Documentation older than code:
- Docs not updated after code changes
- File modification time comparison
- Risk: Medium

**DRIFT** - Documentation doesn't match code:
- Function signatures changed
- Parameters added/removed
- Types modified
- Risk: High

**MISSING** - Documentation incomplete:
- New code not documented
- New parameters not described
- Risk: Medium

**OUTDATED** - Referenced deprecated code:
- Docs reference removed functions
- Examples use old API
- Risk: Low

## Sync Report Format

```markdown
# Documentation Sync Report

## Summary
- Issues found: 7
- STALE: 3
- DRIFT: 2
- MISSING: 2

## Issues

### DRIFT: docs/api/users.md

**Issue:** Function signature changed

**Code:**
```typescript
function createUser(data: UserInput, options?: CreateOptions)
```

**Docs:**
```markdown
### createUser(data: UserInput)
```

**Suggestion:**
Add documentation for `options` parameter

**Priority:** HIGH
```

## Auto-Fix Capabilities

Can auto-fix simple type changes, timestamps, and link updates.
Cannot auto-fix parameter descriptions, behavior changes, or examples (requires human review).

## Integration

Use **wicked-search** to find docs. **wicked-crew** auto-checks after build.
**wicked-kanban** creates tasks for updates. Git hooks check on commit.

## Events

- `[docs:stale:warning]` - Stale documentation found
- `[docs:drift:warning]` - Documentation drift detected
- `[docs:missing:warning]` - Missing documentation found
- `[docs:synced:success]` - Documentation synchronized

## Configuration

```yaml
sync:
  max_staleness_days: 30      # Warn if docs unchanged for 30 days
  check_signatures: true      # Compare function signatures
  check_types: true           # Compare type definitions
  check_openapi: true         # Validate OpenAPI against code
  auto_fix: false             # Auto-fix simple issues
```

## Best Practices

1. **Run Regularly** - Check sync after major changes
2. **Prioritize High Impact** - Fix signature mismatches first
3. **Track Over Time** - Monitor documentation health
4. **Automate Checks** - Use git hooks or CI
5. **Review Auto-Fixes** - Don't blindly apply changes

## Tips

1. **Compare Timestamps** - Quick first check
2. **Parse Code** - Extract actual signatures
3. **Validate Specs** - Check OpenAPI against routes
4. **Check Examples** - Ensure examples still work
5. **Link Issues** - Connect doc issues to code changes
6. **Make It Actionable** - Specific suggestions, not just warnings
