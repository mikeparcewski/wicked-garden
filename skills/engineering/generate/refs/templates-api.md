# Documentation Templates: README, Function, API & Class

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
