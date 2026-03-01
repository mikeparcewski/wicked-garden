# Documentation Templates

Standard templates for generating documentation from code.

## README Template

```markdown
# {project_name}

{short_description}

## Installation

```bash
{install_command}
```

## Quick Start

```{language}
{simple_example}
```

## Features

{feature_list}

## Documentation

- [API Reference]({api_docs_link})
- [Getting Started Guide]({guide_link})
- [Examples]({examples_link})

## Configuration

{config_section}

## Contributing

{contributing_link}

## License

{license}
```

## Function Documentation Template

```markdown
### `{function_name}({parameters}): {return_type}`

{description}

**Parameters:**
{for each parameter}
- `{name}` ({type}) - {description}
  {if has properties}
  - `{property}` ({type}) - {description}
  {end if}
{end for}

**Returns:**
{return_type} - {return_description}

{if throws}
**Throws:**
{for each exception}
- `{exception_type}` - {when_thrown}
{end for}
{end if}

**Example:**
```{language}
{usage_example}
```

{if notes}
**Notes:**
{notes}
{end if}
```

## API Endpoint Template

```markdown
## {method} {path}

{description}

**Authentication:** {auth_requirement}

**Parameters:**

{if path_params}
**Path:**
| Name | Type | Description |
|------|------|-------------|
{for each param}
| {name} | {type} | {description} |
{end for}
{end if}

{if query_params}
**Query:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
{for each param}
| {name} | {type} | {required} | {default} | {description} |
{end for}
{end if}

{if body}
**Request Body:**
```json
{body_schema}
```
{end if}

**Response:**

{for each status}
**{status_code} - {status_name}**
```json
{response_example}
```
{end for}

**Example Request:**
```bash
curl -X {method} "{full_url}" \
  {if auth}
  -H "Authorization: Bearer {token}" \
  {end if}
  {if body}
  -H "Content-Type: application/json" \
  -d '{body_example}'
  {end if}
```
```

## Class Documentation Template

```markdown
## {class_name}

{description}

{if extends}
**Extends:** {parent_class}
{end if}

{if implements}
**Implements:** {interfaces}
{end if}

### Constructor

```{language}
new {class_name}({constructor_params})
```

{constructor_description}

**Parameters:**
{for each param}
- `{name}` ({type}) - {description}
{end for}

### Properties

{for each property}
#### `{property_name}: {type}`
{property_description}
{end for}

### Methods

{for each method}
#### `{method_name}({parameters}): {return_type}`
{method_description}
{end for}

### Example

```{language}
{usage_example}
```
```

## Type Definition Template

```markdown
## {type_name}

{description}

```{language}
{type_definition}
```

**Properties:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
{for each property}
| {name} | {type} | {required} | {description} |
{end for}

{if example}
**Example:**
```{language}
{example}
```
{end if}

{if related_types}
**Related Types:**
{for each type}
- [{type_name}](#{type_anchor})
{end for}
{end if}
```

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
