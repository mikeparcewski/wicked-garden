---
name: orient
description: |
  Provides codebase orientation and architecture overview. Use when a developer
  needs to understand project structure, key entry points, or get started with
  an unfamiliar codebase. Generates comprehensive getting-started guides.
---

# Codebase Orientation Skill

Get developers oriented in unfamiliar codebases quickly and effectively.

## When to Use

- First time exploring a codebase
- New team member onboarding
- User says "orient", "overview", "getting started", "help me understand this project"
- Switching to unfamiliar part of large codebase

## Orientation Process

### 1. Quick Assessment

Gather basics first:
- Read README, CONTRIBUTING, ARCHITECTURE docs if present
- Check package.json, requirements.txt, go.mod for tech stack
- Identify language and framework

### 2. Structure Analysis

Map project layout using common patterns:
- src/lib/ → source code
- test/tests/ → test suite
- docs/ → documentation
- Identify architecture pattern (MVC, layered, domain-driven, monorepo)

### 3. Entry Points

Find where execution starts:
- Backend/CLI: main.py, main.go, index.js, package.json scripts
- Frontend: index.html, App.tsx, main.ts
- Libraries: Exported modules, main interface

### 4. Tech Stack

Identify from dependency files and imports.

### 5. Getting Started

Build actionable setup:
1. Prerequisites
2. Setup steps
3. Verification
4. First simple task

## Output Structure

Progressive disclosure - TL;DR first:

```markdown
## Codebase Orientation: {Project Name}

### TL;DR
{2-3 sentence project description}

### Technology Stack
- Languages, frameworks, database, key libraries

### Project Structure
{Tree view with explanations}

### Key Entry Points
1. {Entry point}: {What it does}

### Architecture Pattern
{Pattern name and characteristics}

### Getting Started
Prerequisites → Setup → Verification → First Task

### Key Resources
Documentation, tests, examples locations

### Next Steps
{Immediate actions}
```

## Integration

### With wicked-search

If available:
1. Index: `/wicked-search:index .`
2. Find entries: `/wicked-search:code "main|startup|init"`
3. Find tests: `/wicked-search:code "test_"`
4. Find docs: `/wicked-search:docs "getting started"`

### With wicked-mem

At start:
```python
if has_plugin("wicked-mem"):
    prior = recall("onboarding", project=current_project)
    if prior: "Welcome back! Continue from {component}?"
```

At end:
```python
if has_plugin("wicked-mem"):
    store({"type": "onboarding_session", "oriented": True})
```

## Customization

### Large Codebases (1000+ files)
- Focus on critical path
- Module-by-module orientation

### Microservices
- System overview first
- Individual service orientation
- Service dependencies

### Libraries/SDKs
- Public API focus
- Usage patterns
- Examples

### Legacy Code
- Acknowledge complexity
- Tests as documentation
- Modernization areas

## Quality Checklist

- [ ] Entry points clearly identified
- [ ] Setup steps concrete and actionable
- [ ] Architecture pattern named and explained
- [ ] First task achievable in < 1 hour
- [ ] Resources linked with file paths
- [ ] Next steps specific

## Common Pitfalls

Avoid:
- Generic advice ("read the code")
- Overwhelming detail
- Assuming prior knowledge
- Skipping verification

Instead:
- Specific paths and line numbers
- Progressive disclosure
- Explain domain concepts
- Include verification steps

## Reference

- [Onboarding Checklist](refs/checklist.md) - Comprehensive day-by-day guide
