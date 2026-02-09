---
description: Generate or improve documentation for code
argument-hint: "<file or component> [--type api|readme|guide|inline]"
---

# /wicked-engineering:docs

Generate documentation from code or improve existing documentation. Supports API docs, READMEs, guides, and inline comments.

## Instructions

### 1. Determine Documentation Type

Based on `--type` or infer from context:
- **api**: OpenAPI specs, endpoint documentation, type definitions
- **readme**: Project/component README with setup, usage, examples
- **guide**: How-to guides for specific workflows
- **inline**: Add/improve code comments and docstrings

### 2. Read Source Code

Read the code to document:
- Public interfaces and exports
- Function signatures and parameters
- Types and data structures
- Error conditions and edge cases

### 3. Dispatch Documentation Agent

For API documentation:
```python
Task(
    subagent_type="wicked-engineering:api-documentarian",
    prompt="""Generate API documentation for this code.

## Code
{code content}

## Required Sections
1. Endpoint/function descriptions
2. Parameter documentation
3. Return value documentation
4. Error responses
5. Usage examples

## Return Format
API reference with examples, formatted in markdown.
"""
)
```

For other documentation:
```python
Task(
    subagent_type="wicked-engineering:technical-writer",
    prompt="""Generate {type} documentation for this code.

## Code
{code content}

## Context
- Purpose: {purpose}
- Audience: {audience}

## Quality Standards
1. Clear, accessible language
2. Practical examples
3. Proper structure
4. Accurate technical details

## Return Format
{type} documentation formatted in markdown.
"""
)
```

### 4. Generate Documentation

Based on type:

**API Documentation:**
```markdown
## API Reference: {component}

### {function/endpoint}

{description}

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|

**Returns:** {type} - {description}

**Errors:**
- `{ErrorType}`: {when thrown}

**Example:**
```{language}
{usage example}
```
```

**README:**
```markdown
# {Component Name}

{brief description}

## Installation
{setup steps}

## Usage
{basic usage with examples}

## API
{key functions/methods}

## Configuration
{options if applicable}
```

**Guide:**
```markdown
# How to {task}

## Overview
{what this guide covers}

## Prerequisites
{what's needed}

## Steps

### 1. {First step}
{instructions}

### 2. {Second step}
{instructions}

## Troubleshooting
{common issues}
```

### 5. Write or Present

If writing to file:
- API docs → alongside code or in docs/
- README → component root
- Guides → docs/guides/

If inline comments, use Edit tool to add them.

Present the documentation for user review before writing.
