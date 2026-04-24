---
name: docs
description: |
  Use when generating documentation from code, auditing documentation coverage for gaps, or detecting
  code-doc drift after a refactor. Covers generate (API docs, READMEs), audit (coverage metrics,
  undocumented exports), and sync (stale docs detection) in one skill.
  NOT for architecture documentation (use the architecture skill) or product requirements (use product/requirements-analysis).
---

# Documentation Engineering Skill

Generate, audit, and sync documentation across the codebase.

## Quick Start

### Generate docs from code

```bash
/wicked-garden:engineering:docs <file-or-component> --type api|readme|guide|inline
```

Extracts types, signatures, and comments to produce API docs, READMEs, or inline comments.

### Audit documentation coverage

```bash
/wicked-garden:engineering:docs <path> --audit
```

Reports coverage (documented vs total exports), quality score, and prioritized gaps.

### Detect stale docs after code changes

```bash
/wicked-garden:engineering:docs <path> --sync
```

Identifies documentation that has drifted from implementation after a refactor or rename.

## Generate

Transform code into documentation:
- Extract types, method signatures, and inline comments
- Generate API reference (JSDoc / docstring style)
- Create or update README files
- Add inline comments where missing

**Output**: Markdown docs ready to commit, or inline comment patches.

## Audit

Evaluate documentation health across the codebase:
- Find undocumented exported functions, classes, and API endpoints
- Calculate coverage percentage and quality score (description + params + examples)
- Prioritize gaps: High = public APIs, Medium = internal utilities, Low = private/test

**Quality Score (0-100)**:
- Has description: +25
- Has parameters: +25
- Has examples: +30
- Has edge cases: +20

**Coverage Report format**:
```markdown
# Documentation Coverage Report

## Summary
| Category  | Total | Documented | Coverage |
|-----------|-------|------------|----------|
| Functions | 145   | 98         | 67.6%    |

## Top Issues
### Undocumented Public Functions (12)
- `src/api/auth.ts::authenticate` — Core auth
```

## Sync

Detect and fix documentation drift:
- Compare code signatures against existing doc strings
- Flag mismatched parameter names, changed return types, removed methods
- Suggest specific doc updates with before/after diffs

## Integration

- Use `wicked-garden:search` to scope the file set before auditing
- Native TaskCreate (with `metadata.event_type="task"`) tracks doc tasks
- CI: run audit in `--report` mode to gate PRs that drop below coverage threshold

## Best Practices

1. Prioritize public APIs first — that is what users see
2. Set realistic targets — 80% with good quality beats 100% with stubs
3. Run sync after every significant refactor — don't let drift accumulate
4. Automate in CI — block PRs that reduce coverage
