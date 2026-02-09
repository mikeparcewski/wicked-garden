# wicked-patch Test Scenarios

This directory contains real-world test scenarios demonstrating wicked-patch functionality. Each scenario proves actual value for code generation, refactoring, and change propagation workflows across multi-language codebases.

## Scenario Overview

| Scenario | Type | Difficulty | Time | Focus |
|----------|------|------------|------|-------|
| [add-field-propagation](./01-add-field-propagation.md) | Patch | Basic | 8 min | Multi-language field addition |
| [rename-symbol-across-codebase](./02-rename-symbol-across-codebase.md) | Propagation | Intermediate | 10 min | Cross-language symbol renaming |
| [change-plan-impact-analysis](./03-change-plan-impact-analysis.md) | Safety | Basic | 5 min | Dry-run impact preview |
| [remove-field-cleanup](./04-remove-field-cleanup.md) | Propagation | Intermediate | 10 min | Complete field removal and cleanup |
| [patch-save-and-apply](./05-patch-save-and-apply.md) | Safety | Basic | 6 min | Team review workflow |

## Quick Start

### Prerequisites

Before running scenarios, ensure:
- wicked-search plugin installed (required dependency for symbol graphs)
- Test directories writable (scenarios use `/tmp/wicked-patch-*`)

### Run a Basic Scenario

```bash
# Start with the simplest scenario
cd /path/to/scenarios
# Follow steps in 01-add-field-propagation.md

# Or jump to a specific scenario
# Follow steps in 03-change-plan-impact-analysis.md for dry-run safety
```

## What Each Scenario Proves

### 01: Add Field Propagation
**Problem solved**: Adding a field to a data model requires manual updates across Java entities, Python ORM, SQL schema, getters/setters, and related code.

**Value demonstrated**:
- Single command propagates changes across 3+ languages
- Automatic generation of language-specific code (Java getters/setters, Python SQLAlchemy columns, SQL ALTER TABLE)
- Consistency guaranteed across backend, ORM, and database layers
- **Time saved**: 10-15 minutes → 1 minute per field

**Real-world use**: Feature development requiring new entity fields across full stack.

---

### 02: Rename Symbol Across Codebase
**Problem solved**: Renaming a field in one language doesn't update references in frontend, backend, tests, or API contracts. Manual find/replace misses edge cases.

**Value demonstrated**:
- Finds ALL references across Java, TypeScript, Python, and other languages
- Respects language-specific naming conventions (camelCase vs snake_case)
- Updates method names (getters/setters), interface properties, and test assertions
- **Time saved**: 20-30 minutes → 2 minutes per rename

**Real-world use**: API refactoring, legacy code cleanup, terminology standardization.

---

### 03: Change Plan Impact Analysis
**Problem solved**: Developers make changes blindly, discovering breaking impacts only after deployment. No preview of what would be affected.

**Value demonstrated**:
- Dry-run planning shows complete blast radius BEFORE making changes
- Risk assessment (LOW/MEDIUM/HIGH) based on dependency analysis
- Identifies direct changes vs. indirect impacts
- Flags external dependencies (APIs, serialization, database contracts)
- **Time saved**: 30-60 minutes of manual impact analysis → 1 minute automatic

**Real-world use**: Pre-deployment risk assessment, code review preparation, compliance documentation.

---

### 04: Remove Field Cleanup
**Problem solved**: Removing deprecated fields leaves orphaned code (getters/setters, queries, tests) that confuses future developers and increases maintenance burden.

**Value demonstrated**:
- Complete cleanup across entity, service, repository, database, and test layers
- Automatic SQL migration generation (DROP COLUMN, DROP INDEX)
- Removal of obsolete tests that reference deleted fields
- Warning for deprecated functionality being removed
- **Time saved**: 45-60 minutes → 3 minutes per field removal

**Real-world use**: Tech debt cleanup, GDPR compliance (PII removal), database normalization, API versioning.

---

### 05: Patch Save and Apply
**Problem solved**: Direct code changes bypass review processes. Regulated industries need reviewable artifacts and audit trails.

**Value demonstrated**:
- Separation of patch generation from application
- Reviewable patch files (JSON with metadata and checksums)
- Version control integration (commit patches for review)
- Audit trail (git history of generation, approval, and application)
- Compliance workflow (generate → review → approve → apply)
- **Time saved**: 15-20 minutes of change preparation → 3 minutes automated

**Real-world use**: SOX/HIPAA compliance, Change Advisory Board (CAB) workflows, open source maintainer review, regulated industry audits.

## Learning Path

### New to wicked-patch? Start here:
1. [add-field-propagation](./01-add-field-propagation.md) - See basic multi-language propagation
2. [change-plan-impact-analysis](./03-change-plan-impact-analysis.md) - Learn dry-run safety
3. [patch-save-and-apply](./05-patch-save-and-apply.md) - Understand review workflow

### Refactoring focus? Follow this path:
1. [rename-symbol-across-codebase](./02-rename-symbol-across-codebase.md) - Safe cross-language renames
2. [remove-field-cleanup](./04-remove-field-cleanup.md) - Complete cleanup operations
3. [change-plan-impact-analysis](./03-change-plan-impact-analysis.md) - Plan before executing

### Compliance and safety focus?
1. [change-plan-impact-analysis](./03-change-plan-impact-analysis.md) - Risk assessment
2. [patch-save-and-apply](./05-patch-save-and-apply.md) - Review workflow
3. [remove-field-cleanup](./04-remove-field-cleanup.md) - Audit trail for deletions

## Command Coverage

All wicked-patch commands are demonstrated across scenarios:

| Command | Scenarios | Purpose |
|---------|-----------|---------|
| `/wicked-patch:add-field` | 01, 05 | Add a field to an entity with propagation |
| `/wicked-patch:rename` | 02 | Rename a symbol across all languages |
| `/wicked-patch:remove` | 04 | Remove a field with complete cleanup |
| `/wicked-patch:plan` | 03 | Preview impact without making changes |
| `/wicked-patch:apply` | 01, 04, 05 | Apply generated patches to codebase |

**Integration with wicked-search**:
- All scenarios use `/wicked-search:index` to build symbol graphs
- wicked-patch requires wicked-search for cross-file dependency analysis

## Scenario Format

Each scenario follows this structure:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: patch|propagation|safety
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

Brief explanation of what this proves.

## Setup
Concrete steps to create test data (bash commands to create realistic test files).

## Steps
Numbered executable steps with code blocks using /wicked-patch commands.

## Expected Outcome
What you should see at each step.

## Success Criteria
- [ ] Checkboxes for verification

## Value Demonstrated
WHY this matters in real-world usage.
```

## Use Cases by Role

These scenarios demonstrate value for different engineering roles:

| Role | Scenarios | Key Value |
|------|-----------|-----------|
| **Backend Engineer** | 01, 02, 04 | Multi-language code generation, refactoring automation |
| **Full-Stack Engineer** | 01, 02, 05 | Frontend-backend consistency, API contract alignment |
| **DevOps/SRE** | 03, 04, 05 | Risk assessment, change planning, compliance workflows |
| **Tech Lead** | 03, 05 | Code review preparation, impact analysis, team workflows |
| **Data Engineer** | 01, 04 | Schema evolution, migration generation, field lifecycle |

## Testing Philosophy

These scenarios are **functional tests**, not unit tests:

- **Real code patterns**: Actual Java/TypeScript/Python/SQL files with realistic structures
- **Real workflows**: End-to-end generation → review → apply processes
- **Real value**: Time savings, risk reduction, compliance improvement
- **Real problems**: Missed references, orphaned code, breaking changes

Each scenario answers: "Would I actually use this feature in production?"

## Integration Points

wicked-patch scenarios demonstrate integration with:

- **wicked-search** (required): Symbol graph indexing for dependency analysis (all scenarios)
- **wicked-kanban** (optional): Track cleanup tasks from field removal (scenario 04)
- **wicked-mem** (optional): Store common refactoring patterns (scenario 02)
- **Git**: Version control integration for patch review (scenario 05)

## Success Criteria Summary

Across all scenarios, you should verify:

### Functional Correctness
- [ ] Symbol graph indexing completes without errors
- [ ] Generated patches are valid JSON with correct structure
- [ ] Applied changes compile/parse in target languages
- [ ] Language-specific conventions respected (camelCase, snake_case)

### Multi-Language Support
- [ ] Java entity changes (fields, getters/setters)
- [ ] TypeScript interface and class updates
- [ ] Python SQLAlchemy model modifications
- [ ] SQL migration generation (ALTER TABLE, DROP COLUMN)

### Safety and Planning
- [ ] Plan command executes without modifying files (dry-run)
- [ ] Risk levels correctly assessed (LOW/MEDIUM/HIGH)
- [ ] All references identified in symbol graph
- [ ] Warnings issued for high-risk operations

### Workflow Integration
- [ ] Patches saved to `.patches/` directory
- [ ] Manifest.json contains metadata and checksums
- [ ] Git integration works (commit patches, apply later)
- [ ] Archive mechanism for audit trail

## Contributing New Scenarios

When adding scenarios, ensure:

1. **Real-world use case** - Not a toy example
2. **Complete setup** - Reproducible test data creation with bash commands
3. **Multi-language coverage** - Demonstrates cross-language propagation where applicable
4. **Realistic complexity** - Issues that actually occur in production (missing references, orphaned code)
5. **Clear value** - Articulates time saved AND risks reduced
6. **Verifiable criteria** - Checkboxes that can be tested programmatically

See existing scenarios as templates.

## Scenario Maintenance

- Test scenarios after each wicked-patch release
- Update if command interfaces or patch formats change
- Add scenarios for new capabilities (e.g., new languages, new operations)
- Keep setup scripts working on latest language versions
- Ensure wicked-search dependency version compatibility

## Troubleshooting

### Common Issues

**"Symbol graph not found"**
- Run `/wicked-search:index <project-path>` before wicked-patch commands
- Verify `.wicked-search/` directory exists in project root

**"No references found"**
- Check that files are indexed (wicked-search may skip certain file types)
- Verify symbol name matches exactly (case-sensitive)

**"Patch application failed"**
- Ensure target files haven't been modified since patch generation
- Check that file paths in patches are absolute, not relative
- Verify file permissions (patches directory must be writable)

**"Language not supported"**
- wicked-patch currently supports: Java, TypeScript, Python, SQL
- Check plugin documentation for language-specific limitations

## Advanced Usage

### Combining Scenarios

You can chain multiple scenarios to test complex workflows:

1. Run scenario 01 (add-field) to add a field
2. Run scenario 02 (rename) to rename the newly added field
3. Run scenario 03 (plan) to preview removal impact
4. Run scenario 04 (remove) to clean up the field completely

### Custom Patch Pipelines

Use scenario 05 as a template for custom workflows:
- Add approval gates (JIRA ticket validation, security scans)
- Integrate with CI/CD (automated patch application on merge)
- Create patch libraries (common refactorings as reusable patches)

## Performance Benchmarks

Expected execution times on a typical laptop (M1 Mac, 16GB RAM):

| Operation | Small Codebase (<100 files) | Medium Codebase (100-1000 files) | Large Codebase (1000+ files) |
|-----------|----------------------------|----------------------------------|------------------------------|
| Index | 1-2 seconds | 5-10 seconds | 30-60 seconds |
| Plan | 0.5-1 second | 2-5 seconds | 10-20 seconds |
| Generate patches | 1-2 seconds | 3-7 seconds | 15-30 seconds |
| Apply patches | 0.5-1 second | 2-5 seconds | 10-20 seconds |

*Times include wicked-search indexing overhead*

## Related Resources

- **Plugin Documentation**: `/plugins/wicked-patch/README.md`
- **Command Reference**: `/plugins/wicked-patch/commands/*.md`
- **Skill Documentation**: `/plugins/wicked-patch/skills/*/SKILL.md`
- **wicked-search Documentation**: `/plugins/wicked-search/README.md` (required dependency)

## License

Test scenarios and example code are provided under the same license as the wicked-patch plugin.
