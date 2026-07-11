# docs — documentation generation rubric

Checklist, output templates, and quality standards for generating API docs, READMEs,
guides, and inline comments. API/reference docs route to the
`wicked-garden-engineering-api-documentarian` fork skill;
narrative docs (READMEs, guides, comments) are generated inline with this rubric.

## Documentation type routing

| `--type` | What to generate | Primary audience |
|----------|-----------------|-----------------|
| `api` | OpenAPI spec + endpoint reference | Integrating developers |
| `readme` | Project/component README | New users, contributors |
| `guide` | How-to tutorial for a specific task | Practitioners |
| `inline` | Code comments and docstrings | Code readers |

Infer if absent: `.ts/.py/.go` file → api or inline; top-level dir → readme; workflow request → guide.

## Pre-generation checklist (read the code first)

- [ ] Read all public interfaces and exports
- [ ] Read all function signatures, parameters, return types
- [ ] Read error conditions and what triggers them
- [ ] Read existing docs for drift (what's changed from docs vs code)
- [ ] Identify audience: who will read this?

## API documentation checklist (OpenAPI-first)

### Required per endpoint/function
- [ ] Summary (one line) and description (what, when to use, what not to use)
- [ ] All parameters: name, location, type, required/optional, description, example
- [ ] All response codes: 2xx success schema + example, 4xx client errors, 5xx server errors
- [ ] Authentication requirements stated explicitly
- [ ] Operation ID assigned (for SDK generation)
- [ ] At least one working request example (bash curl or language snippet)

### Schema documentation
- [ ] Required vs optional fields marked
- [ ] Types accurate (format: email, date-time, uuid, etc.)
- [ ] Descriptions for each field (not just the type)
- [ ] Constraints: min/max, pattern, enum values
- [ ] Example values provided

### OpenAPI quality bar
- [ ] Valid OpenAPI 3.0+ syntax
- [ ] All `$ref` targets exist
- [ ] Examples match schemas they illustrate
- [ ] Consistent naming: operations as verbs (getUser), paths lowercase-kebab, schemas PascalCase
- [ ] Deprecations documented with `Deprecation` header and `Sunset` date

### API output template

```yaml
openapi: 3.0.0
info:
  title: {Component} API
  version: {version}
  description: |
    {What this API does}. Base URL: {base_url}

paths:
  /{resource}/{id}:
    get:
      summary: {one-line description}
      operationId: {camelCaseVerb}
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
          description: {what it identifies}
      responses:
        '200':
          description: {success description}
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/{Resource}'
              example:
                {field}: {value}
        '404':
          description: Not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
      security:
        - bearerAuth: []

components:
  schemas:
    {Resource}:
      type: object
      required: [{required_fields}]
      properties:
        id:
          type: string
          description: Unique identifier
    Error:
      type: object
      properties:
        error: {type: string}
        message: {type: string}
        code: {type: string}
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

## README checklist

- [ ] What — one to two sentence description
- [ ] Why — what problem does this solve
- [ ] How — working quick-start example (tested)
- [ ] Where — links to detailed docs
- [ ] Keep under 300 lines; link to `/docs` for details
- [ ] Installation step-by-step
- [ ] Configuration options table (if applicable)
- [ ] Badge: CI status (optional but helpful)

### README template

```markdown
# {Component Name}

{One sentence description of what this does and why it exists.}

## Installation

{Step-by-step, tested}

## Quick Start

```{language}
{simplest working example}
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|

## API

{Key functions/endpoints — link to full API docs}

## Contributing

{Link to CONTRIBUTING.md or brief notes}
```

## How-to guide checklist

- [ ] Goal stated upfront (what you'll accomplish)
- [ ] Prerequisites listed (knowledge + tools needed)
- [ ] Steps numbered, tested, include expected output
- [ ] Result shown (what success looks like)
- [ ] Troubleshooting section for common failure modes
- [ ] Active voice throughout ("Run the command" not "The command should be run")
- [ ] Code examples before explanation (show, then tell)

## Inline comments checklist

- [ ] Comments explain WHY, not WHAT (the code shows what)
- [ ] Non-obvious algorithms or heuristics documented
- [ ] Docstrings: all public functions have summary + params + return + raises
- [ ] TODO/FIXME comments have an issue reference or an owner
- [ ] No commented-out code (delete it or track via issue)

## Writing quality standards

**Active voice**: "Run the command" not "The command should be run"
**Concise**: strip filler ("In order to" → "To")
**Example-first**: code block before prose explanation
**Consistent terminology**: pick one name per concept and stick to it
**Scannable**: headers, bullets, short paragraphs — most readers skim first

## Output locations

| Type | Write to |
|------|---------|
| OpenAPI spec | `docs/api/openapi.yaml` or alongside code |
| Endpoint reference | `docs/api/{resource}.md` |
| README | component root `README.md` |
| Guides | `docs/guides/{topic}.md` |
| Inline | use Edit tool in-file |

Always present for user review before writing to file.
