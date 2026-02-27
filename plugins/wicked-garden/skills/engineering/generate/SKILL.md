---
name: generate
description: |
  Generate documentation from code - extract types, comments, and signatures to create
  API docs, README files, and reference documentation. Focus on useful, actionable docs.

  Use when: "generate docs", "create documentation", "document the API",
  "generate README", "make docs from code"
---

# Generate Documentation Skill

Create useful documentation from code - extract information and present it clearly.

## Purpose

Transform code into documentation:
- Extract types, signatures, and comments
- Generate API documentation
- Create/update README files
- Discover and use documentation tools

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:engineering-generate [path]` | Generate docs from code |
| `/wicked-garden:engineering-generate --api` | Generate API documentation |
| `/wicked-garden:engineering-generate --readme` | Generate/update README |
| `/wicked-garden:engineering-generate --types` | Generate type documentation |

## Quick Start

```bash
# Generate general documentation
/wicked-garden:engineering-generate src/

# Generate API documentation
/wicked-garden:engineering-generate src/api --api

# Update README
/wicked-garden:engineering-generate --readme
```

## Process

### 1. Analyze Target

Understand what to document:
- Language and framework
- Code structure (functions, classes, modules)
- Existing comments and docstrings
- Type information

### 2. Discover Tools

Check for documentation tooling:
- JavaScript/TypeScript: TypeDoc, JSDoc, Docusaurus
- Python: Sphinx, MkDocs, pdoc
- Rust: rustdoc, Go: godoc

If tools exist, use them. Otherwise extract manually.

### 3. Extract Information

From code, extract:
- Function signatures and descriptions
- Class structure and methods
- API endpoints and schemas
- Type definitions

### 4. Generate Documentation

Create focused, useful docs:
- README: overview, installation, quick start
- API docs: endpoints, parameters, responses
- Reference: functions, classes, types

See [Templates](refs/templates.md) for standard formats.

## Language Patterns

Extract from:
- **JavaScript/TypeScript**: JSDoc comments and type definitions
- **Python**: Docstrings and type hints
- **REST APIs**: Route definitions and schemas
- **Other**: Language-specific doc comments

## Tool Integration

Check for existing doc tools (TypeDoc, Sphinx, rustdoc) and use them.
If none exist, extract and generate manually.

Read project metadata from `package.json` or `pyproject.toml` for README generation.

## Best Practices

1. **Include Examples** - Every function/endpoint needs an example
2. **Use Type Information** - Show parameter types clearly
3. **Document Edge Cases** - Note unusual behavior
4. **Don't Generate Boilerplate** - Focus on useful content
5. **Update, Don't Replace** - Preserve manual sections

## Integration

Use **wicked-search** to find code to document.
Use **wicked-mem** to learn and maintain project doc style.

## Events

- `[docs:generated:success]` - Documentation created
- `[docs:readme:updated:success]` - README updated
- `[docs:api:generated:success]` - API docs generated

## Tips

1. **Use Existing Tools** - Don't reinvent TypeDoc/Sphinx
2. **Parse, Don't Guess** - Read actual code structure
3. **Include Examples** - Show real usage
4. **Extract from Tests** - Tests are usage examples
5. **Link Related Docs** - Cross-reference related APIs
6. **Update, Don't Replace** - Preserve manual sections

## Reference

- [Templates](refs/templates.md) - Standard documentation templates
