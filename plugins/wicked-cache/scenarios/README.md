# wicked-cache Test Scenarios

This directory contains real-world test scenarios demonstrating wicked-cache functionality. Each scenario is designed to prove actual value, not just toy examples.

## Scenario Overview

| Scenario | Type | Difficulty | Time | Focus |
|----------|------|------------|------|-------|
| [file-schema-cache](./file-schema-cache.md) | Workflow | Basic | 5 min | File-based invalidation |
| [ttl-cache](./ttl-cache.md) | Workflow | Basic | 4 min | Time-based expiration |
| [manual-mode-config](./manual-mode-config.md) | Workflow | Basic | 3 min | Persistent configuration |
| [cross-plugin-integration](./cross-plugin-integration.md) | Integration | Intermediate | 5 min | Namespace isolation |
| [cache-management-commands](./cache-management-commands.md) | Feature | Basic | 6 min | Observability & control |
| [plugin-development-workflow](./plugin-development-workflow.md) | Workflow | Advanced | 8 min | All modes together |

## Quick Start

### Run a Basic Scenario

```bash
cd /path/to/wicked-cache
# Follow the steps in any scenario markdown file
```

### What Each Scenario Proves

**file-schema-cache**
- Caches expensive CSV analysis results
- Automatically invalidates when source file changes
- Shows 500ms → <1ms performance improvement
- Real-world use: Data analysis plugins

**ttl-cache**
- Caches external API responses with time expiration
- Prevents rate limiting issues
- Shows 1s → <1ms for API calls during TTL
- Real-world use: Documentation lookup, package checkers

**manual-mode-config**
- Stores plugin configuration that never expires
- Only manual invalidation removes data
- Perfect for preferences and persistent state
- Real-world use: Plugin settings, feature flags

**cross-plugin-integration**
- Shows multiple plugins using wicked-cache simultaneously
- Proves namespace isolation works correctly
- Demonstrates shared infrastructure pattern
- Real-world use: Marketplace with 10+ plugins

**cache-management-commands**
- List, stats, clear, invalidate operations
- Monitor cache effectiveness (hit/miss rates)
- Debug stale data issues
- Real-world use: Production monitoring and debugging

**plugin-development-workflow**
- All three cache modes in realistic plugin
- Shows how to architect plugin caching strategy
- Comprehensive performance demonstration
- Real-world use: Building production plugins

## Scenario Format

Each scenario follows this structure:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: workflow|integration|feature
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

Brief explanation of what this proves.

## Setup
Concrete steps to create test data.

## Steps
Numbered, executable steps with code blocks.

## Expected Outcome
What you should see.

## Success Criteria
- [ ] Checkboxes for verification

## Value Demonstrated
WHY this matters in real-world usage.
```

## Learning Path

**New to wicked-cache?** Start here:
1. [file-schema-cache](./file-schema-cache.md) - See file invalidation in action
2. [ttl-cache](./ttl-cache.md) - Understand time-based caching
3. [manual-mode-config](./manual-mode-config.md) - Learn persistent storage

**Building a plugin?** Follow this path:
1. [plugin-development-workflow](./plugin-development-workflow.md) - See all modes together
2. [cache-management-commands](./cache-management-commands.md) - Add observability
3. [cross-plugin-integration](./cross-plugin-integration.md) - Understand isolation

**Debugging cache issues?**
- [cache-management-commands](./cache-management-commands.md) - Inspect and manage cache

## Testing Philosophy

These scenarios are **functional tests**, not unit tests:

- **Real data**: Actual CSV files, realistic JSON structures
- **Real operations**: File I/O, time delays, cache hits/misses
- **Real value**: Performance improvements, rate limit prevention
- **Real problems**: Stale data detection, invalidation strategies

Each scenario answers: "Would I actually use this feature in production?"

## Contributing New Scenarios

When adding scenarios, ensure:

1. **Real-world use case** - Not a toy example
2. **Functional proof** - Actually demonstrates it works
3. **Concrete setup** - Reproducible test data
4. **Verifiable criteria** - Checkboxes that can be tested
5. **Clear value** - Articulates WHY someone would use this

See existing scenarios as templates.

## Running All Scenarios

To validate all scenarios work:

```bash
# Run each scenario in order
for scenario in file-schema-cache ttl-cache manual-mode-config cross-plugin-integration cache-management-commands plugin-development-workflow; do
    echo "=== Testing $scenario ==="
    # Follow steps in scenarios/${scenario}.md
done
```

## Scenario Maintenance

- Test scenarios after each release
- Update if API changes
- Add new scenarios for new features
- Remove scenarios for deprecated functionality
