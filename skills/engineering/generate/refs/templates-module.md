# Documentation Templates: OpenAPI, Error, Config & Usage

Templates for OpenAPI specs, error documentation, configuration docs, and template usage patterns.

## OpenAPI Endpoint Template

```yaml
{path}:
  {method}:
    summary: {summary}
    description: {description}
    operationId: {operation_id}
    tags:
      - {tag}
    {if parameters}
    parameters:
      - name: {param_name}
        in: {param_location}
        required: {required}
        schema:
          type: {type}
        description: {description}
    {end if}
    {if request_body}
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/{schema_name}'
          example:
            {example_object}
    {end if}
    responses:
      '{status_code}':
        description: {response_description}
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/{schema_name}'
            example:
              {example_object}
    {if security}
    security:
      - {security_scheme}: []
    {end if}
```

## OpenAPI Schema Template

```yaml
{schema_name}:
  type: object
  required:
    {for each required_property}
    - {property_name}
    {end for}
  properties:
    {property_name}:
      type: {type}
      {if format}
      format: {format}
      {end if}
      description: {description}
      {if example}
      example: {example}
      {end if}
      {if enum}
      enum:
        - {value1}
        - {value2}
      {end if}
```

## Error Documentation Template

```markdown
## Error Codes

{for each error}
### `{error_code}`

**Message:** {error_message}

**Description:** {when_occurs}

**HTTP Status:** {status_code}

**Example:**
```json
{
  "error": "{error_code}",
  "message": "{error_message}",
  "details": {
    {error_details}
  }
}
```

**Resolution:**
{how_to_fix}
{end for}
```

## Configuration Documentation Template

```markdown
## Configuration

{description}

### Configuration File

Location: `{config_file_path}`

Format: {format}

```{format}
{example_config}
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
{for each option}
| {name} | {type} | {default} | {description} |
{end for}

### Environment Variables

{for each env_var}
#### `{var_name}`

{description}

**Default:** `{default}`

**Example:**
```bash
export {var_name}="{example_value}"
```
{end for}
```

## Template Variables Reference

### Common Variables

- `{project_name}` - Project/package name
- `{short_description}` - One-line description
- `{long_description}` - Detailed description
- `{version}` - Current version
- `{language}` - Programming language
- `{license}` - License type

### Function/Method Variables

- `{function_name}` - Function name
- `{parameters}` - Parameter list
- `{return_type}` - Return type
- `{description}` - Function description
- `{usage_example}` - Code example

### API Variables

- `{method}` - HTTP method (GET, POST, etc.)
- `{path}` - Endpoint path
- `{auth_requirement}` - Auth description
- `{status_code}` - HTTP status code
- `{response_example}` - Response JSON

### Type Variables

- `{type_name}` - Type/interface name
- `{type_definition}` - Full type code
- `{properties}` - Property list
- `{required}` - Is required?

## Template Usage

### In Code

```typescript
function generateFunctionDoc(fn: FunctionInfo): string {
  const template = readTemplate('function.md');
  return template
    .replace('{function_name}', fn.name)
    .replace('{parameters}', fn.params.join(', '))
    .replace('{return_type}', fn.returnType)
    .replace('{description}', fn.description);
}
```

### Conditional Sections

Use `{if condition}...{end if}` for optional sections:

```markdown
{if has_examples}
## Examples

{examples}
{end if}
```

### Loops

Use `{for each item}...{end for}` for repeated sections:

```markdown
{for each parameter}
- `{name}` ({type}) - {description}
{end for}
```

## Tips

1. **Keep Templates Simple** - Easy to understand and maintain
2. **Use Consistent Formatting** - Follow markdown standards
3. **Include Examples** - Show what good output looks like
4. **Make Sections Optional** - Not everything applies everywhere
5. **Preserve Manual Content** - Don't overwrite custom sections
