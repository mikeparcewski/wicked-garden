---
name: audit
description: |
  Audit documentation coverage and quality. Find undocumented code, assess documentation
  completeness, and provide coverage metrics.

  Use when: "audit docs", "check coverage", "find undocumented code",
  "documentation quality", "what's missing docs"
---

# Audit Documentation Skill

Assess documentation coverage and quality across the codebase.

## Purpose

Evaluate documentation health:
- Find undocumented code
- Measure coverage metrics
- Assess documentation quality
- Identify gaps and priorities
- Track improvement over time

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-engineering:audit [path]` | Audit documentation coverage |
| `/wicked-engineering:audit --full` | Comprehensive audit with quality scoring |
| `/wicked-engineering:audit --report` | Generate coverage report |

## Quick Start

```bash
# Basic coverage audit
/wicked-engineering:audit src/

# Full audit with quality assessment
/wicked-engineering:audit src/ --full

# Generate report
/wicked-engineering:audit --report docs/coverage-report.md
```

## Process

### 1. Scan Codebase

Discover all documentable items:
- Exported functions and classes
- Public methods and interfaces
- API endpoints
- Type definitions

### 2. Check Documentation

For each item, verify:
- Has documentation (comments, docs, specs)
- Documentation quality (description, parameters, examples)
- Completeness (all aspects covered)

### 3. Calculate Metrics

**Coverage Percentage:**
```
Coverage = (Documented Items / Total Items) × 100
```

**Quality Score (0-100):**
- Has description: +25%
- Has parameters: +25%
- Has examples: +30%
- Has edge cases: +20%

### 4. Identify Gaps

Prioritize undocumented items:
- **High Priority**: Public APIs, exported functions
- **Medium Priority**: Internal utilities, types
- **Low Priority**: Private methods, test utilities

## Coverage Analysis

Check each function/class/API for documentation.
Calculate coverage percentage and quality score.
Identify undocumented (✗), partial (⚠), and documented (✓) items.

## Quality Scoring

Rate documentation quality (0-100):

- **Minimal (0-25)**: Exists but poor
- **Basic (26-50)**: Functional
- **Good (51-75)**: Useful
- **Excellent (76-100)**: Comprehensive

## Audit Report Format

```markdown
# Documentation Coverage Report

Generated: {timestamp}

## Summary

| Category | Total | Documented | Coverage |
|----------|-------|------------|----------|
| Functions | 145 | 98 | 67.6% |
| Classes | 23 | 21 | 91.3% |
| APIs | 28 | 28 | 100% |
| **Overall** | **196** | **147** | **75.0%** |

## Quality Distribution

| Quality | Count | Percentage |
|---------|-------|------------|
| Excellent (76-100) | 45 | 30.6% |
| Good (51-75) | 89 | 60.5% |
| Basic (26-50) | 13 | 8.9% |

**Average Quality Score:** 65.2/100

## Top Issues

### Undocumented Public Functions (12)

**High Priority:**
- `src/api/auth.ts::authenticate` - Core auth function
- `src/api/users.ts::deleteUser` - Destructive operation
- `src/utils/validation.ts::validateInput` - Public API

### Missing Examples (67)

Functions without usage examples

## Recommendations

1. Document 12 high-priority public functions
2. Add examples to 67 functions
3. Complete parameter docs for 23 functions
```

## Integration

Use **wicked-search** to find code to audit.
**wicked-kanban** creates documentation tasks for gaps.
**wicked-product** reviews documentation quality.

## Events

- `[docs:coverage:info]` - Coverage metrics calculated
- `[docs:missing:warning]` - Undocumented code found
- `[docs:quality:info]` - Quality assessment completed

## Configuration

```yaml
audit:
  min_coverage: 80              # Target coverage percentage
  min_quality: 60               # Target quality score

  scope:
    include_private: false      # Audit private members
    include_tests: false        # Audit test files

  quality:
    require_description: true   # Description required
    require_parameters: true    # Parameter docs required
    require_examples: true      # Examples required
```

## Best Practices

1. **Set Realistic Targets** - 100% coverage may not be needed
2. **Prioritize Public APIs** - Focus on what users see
3. **Track Over Time** - Monitor improvement trends
4. **Focus on Quality** - Better good docs for 80% than poor docs for 100%
5. **Automate Checks** - Run in CI to prevent regression
6. **Make It Actionable** - Provide specific next steps

## Tips

1. **Start with Public API** - Most important to document
2. **Parse Code Structure** - Extract actual info
3. **Check Multiple Sources** - Comments, docs, specs
4. **Measure Quality** - Not just presence
5. **Show Trends** - Track improvement
6. **Integrate with CI** - Block PRs that reduce coverage
7. **Provide Context** - Explain why items are high priority
