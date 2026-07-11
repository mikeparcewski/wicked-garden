---
name: wicked-garden-engineering-patch
description: |
  Language-agnostic code generation and change propagation. Use this skill when
  adding fields to entities, renaming symbols across files, or propagating changes
  that affect multiple files. Use when: "add field", "add a field to this entity",
  "rename everywhere", "rename this field across the codebase", "remove this
  field and all its usages", "propagate change", "generate migration",
  "update all references", "apply saved patches", "show what a change would
  affect" (patch-plan propagation preview), "create a new language generator
  for wicked-patch". Replaces the former /wicked-garden:engineering:
  {add-field,rename,remove,apply,patch-plan,new-generator} commands.

  This is the CODE MUTATION counterpart to wicked-garden-search (which is read-only).
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# wicked-patch

Generate and propagate code changes across your entire codebase using the symbol graph.

All sub-actions run the patch CLI. The full invocation is:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" <sub-action> [args]
```

Examples below abbreviate this to `patch.py <sub-action> …` — always run the full form.

## Sub-actions

| Sub-action | Purpose |
|------------|---------|
| `patch-plan` | Show what would be affected — propagation preview, no patches |
| `add-field` | Add field with propagation |
| `rename` | Rename across all usages |
| `remove` | Remove field everywhere (DELETES code — see warning) |
| `apply` | Apply saved patches from a JSON file |
| `new-generator` | Author a new language generator ([refs/new-generator.md](refs/new-generator.md)) |

## Quick Start

```bash
# 1. Index your codebase (if not already done) — use the wicked-garden-search
#    skill's `index` action to build/refresh the symbol graph

# 2. Add a field to an entity
patch.py add-field "Entity.java::User" --name email --type String

# 3. Rename a field everywhere
patch.py rename "Entity.java::User" --old status --new state

# 4. See propagation plan
patch.py plan "Entity.java::User" --change add_field
```

## How It Works

```
ChangeSpec (add field "email" to User)
           │
           ▼
   ┌───────────────────┐
   │ Propagation Engine │  ← Uses wicked-garden:search lineage graph
   └───────────────────┘
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
  Java   Python   SQL      JSP
   │       │       │         │
   ▼       ▼       ▼         ▼
Patches  Patches Patches  Patches
```

## patch-plan — propagation preview

Show what would be affected by a change without generating patches. **Distinct
from the engineering domain skill's `plan` action** (a human implementation plan
with risks and tests) — `patch-plan` is the impact preview for mechanical patches.
The CLI subcommand is `plan`.

**Arguments**: `symbol_id` (required — symbol to analyze); `--change`
(`add_field` | `rename_field` | `remove_field` | `modify_field`); `--depth`
(max traversal depth, default 5); `--json` (output as JSON).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" plan "<symbol_id>" --change "<change_type>" [--json]
```

Examples: `patch.py plan "User.java::User" --change add_field` ·
`patch.py plan "Order.java::Order" --change rename_field --json`

Output:

```
═══════════════════════════════════════════════════════════
PROPAGATION PLAN
═══════════════════════════════════════════════════════════

Source: User
  Type: entity
  File: /path/to/User.java
  Line: 22

Direct Impacts (3):
  • email (entity_field) @ User.java
  • name (entity_field) @ User.java
  • id (entity_field) @ User.java

Downstream Impacts (5):
  • USER_EMAIL (column) @ migration.sql
  • user-form.jsp (ui_binding) @ user-form.jsp
  ...

───────────────────────────────────────────────────────────
Total: 9 symbols in 4 files
═══════════════════════════════════════════════════════════
```

## add-field — add a field and propagate

Add a field to an entity/class and propagate to all affected files.

**Arguments**: `symbol_id` (required — e.g. `path/Entity.java::EntityName`);
`--name` (required — field name); `--type` (required — String, Integer, Boolean,
Date, etc.); `--column` (database column name, defaults to SNAKE_CASE of name);
`--label` (UI label for form fields); `--required` (mark field non-nullable);
`--output`/`-o` (save patches to JSON file); `--apply` (apply patches
immediately); `--verbose`/`-v` (show full diffs).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" add-field "<symbol_id>" \
  --name "<name>" \
  --type "<type>" \
  [--column "<column>"] \
  [--required] \
  [--verbose]
```

Examples:

```bash
# Add email field to User entity
patch.py add-field "User.java::User" --name email --type String --column USER_EMAIL

# Add required date field
patch.py add-field "Order.java::Order" --name createdAt --type datetime --required

# Save patches for review
patch.py add-field "Entity.java::Entity" --name foo --type String -o patches.json
```

For a JPA entity, `add-field … --name email --type String --column USER_EMAIL --required` generates:

```java
// User.java
@Column(name = "USER_EMAIL")
@NotNull
private String email;

public String getEmail() { return this.email; }
public void setEmail(String email) { this.email = email; }
```

```sql
-- migration.sql
ALTER TABLE USERS ADD COLUMN USER_EMAIL VARCHAR(255) NOT NULL;
```

Output shows generated patches grouped by file:

```
═══════════════════════════════════════════════════════════
GENERATED PATCHES
═══════════════════════════════════════════════════════════

Change: add_field
Target: User.java::User
Files affected: 3
Patches: 5

PATCHES:

  User.java
    [45-44] Add field 'email' (String)
    [98-97] Add getter for 'email'
    [99-98] Add setter for 'email'

  user-form.jsp
    [67-66] Add form field for 'email'

  migration.sql
    [10-9] Add column 'EMAIL' to 'USERS'

═══════════════════════════════════════════════════════════
```

## rename — rename a field/symbol across all usages

**Arguments**: `symbol_id` (required); `--old` (required — current field name);
`--new` (required — new field name); `--output`/`-o` (save patches to file);
`--apply` (apply patches immediately); `--verbose`/`-v` (show full diffs).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" rename "<symbol_id>" --old "<old_name>" --new "<new_name>" [--verbose]
```

Examples: `patch.py rename "User.java::User" --old status --new userStatus` ·
`patch.py rename "Order.java::Order" --old date --new orderDate -o patches.json`

What gets updated:

- Field declarations
- Getter/setter method names
- Property references (`this.oldName` → `this.newName`)
- JSP EL expressions (`${entity.oldName}` → `${entity.newName}`)
- Form bindings (`path="oldName"` → `path="newName"`)
- TypeScript interfaces and type aliases
- SQL column names (generates ALTER TABLE RENAME COLUMN)
- Service layer references, and test files (with warning)

## remove — remove a field and all its usages

**Arguments**: `symbol_id` (required); `--field` (required — field name to
remove); `--output`/`-o` (save patches to file); `--apply` (apply patches
immediately); `--verbose`/`-v` (show full diffs).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" remove "<symbol_id>" --field "<field_name>" [--verbose]
```

Examples: `patch.py remove "User.java::User" --field legacyStatus` ·
`patch.py remove "Entity.java::Entity" --field oldField --verbose` (preview)

### Warning

This operation DELETES code. Always review patches before applying:

```bash
# Generate and save patches
patch.py remove SYMBOL --field foo -o patches.json

# Review
cat patches.json

# Apply when confident
patch.py apply patches.json
```

## apply — apply patches from a saved JSON file

**Arguments**: `patches_file` (required — path to patches JSON file);
`--dry-run` (show what would be done without applying).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" apply "<patches_file>" [--dry-run]
```

Workflow:

```bash
# 1. Generate patches and save
patch.py add-field SYMBOL --name foo --type String -o patches.json

# 2. Review the patches
cat patches.json

# 3. Dry-run to verify
patch.py apply patches.json --dry-run

# 4. Apply for real
patch.py apply patches.json
```

Patches file format:

```json
{
  "change_type": "add_field",
  "target": "User.java::User",
  "files_affected": ["User.java", "migration.sql"],
  "patch_count": 3,
  "generated_at": "2024-01-15T10:30:00",
  "patches": [
    {
      "file": "User.java",
      "line_start": 45,
      "line_end": 44,
      "old": "",
      "new": "    private String email;",
      "description": "Add field 'email'"
    }
  ]
}
```

## new-generator — create a new language generator

Create a new language generator for wicked-patch with scaffolding, golden test
fixtures, and conformance validation. Arguments: `language` (required, e.g.
"scala", "swift", "elixir"); `framework` (optional ORM/framework, e.g. "Slick",
"CoreData", "Ecto"); `extensions` (optional file extensions, defaults to
lowercase language). Follow the full 7-step authoring workflow (generator
template with TYPE_MAP, `__init__.py` registration, golden fixture JSON,
`test_conformance.py` additions, run tests, report) in
[refs/new-generator.md](refs/new-generator.md).

## Supported Languages

| Extension | Features |
|-----------|----------|
| `.java` | JPA @Column, getters/setters, validation |
| `.py` | SQLAlchemy, Pydantic, dataclass |
| `.ts`, `.js` | TypeORM, interfaces, types |
| `.jsp` | Spring form tags, EL expressions |
| `.sql` | ALTER TABLE (PostgreSQL, Oracle, MySQL, SQL Server) |

## Type Mappings

Generic types are automatically mapped per language:

| Generic | Java | Python | TypeScript | SQL |
|---------|------|--------|------------|-----|
| `string` | String | str | string | VARCHAR(255) |
| `integer` | Integer | int | number | INTEGER |
| `boolean` | boolean | bool | boolean | BOOLEAN |
| `date` | LocalDate | date | Date | DATE |
| `datetime` | LocalDateTime | datetime | Date | TIMESTAMP |
| `decimal` | BigDecimal | Decimal | number | DECIMAL(18,2) |

## SQL Dialect Support

Auto-detected or specify via `--dialect`:

```sql
-- PostgreSQL (default)
ALTER TABLE users ADD COLUMN email VARCHAR(255);

-- Oracle
ALTER TABLE users ADD (email VARCHAR2(255));

-- MySQL
ALTER TABLE users ADD COLUMN email VARCHAR(255);

-- SQL Server
ALTER TABLE users ADD email NVARCHAR(255);
```

## Integration with wicked-garden-search

wicked-patch reads from the symbol database that the `wicked-garden-search`
skill builds: run its `index` action first (with `--derive-all`), then patch
sub-actions use the graph for propagation.

## Safety Features

- **Dry-run by default**: Shows patches without applying
- **Confirmation prompt**: Asks before applying
- **Patch files**: Save for review before applying
- **Warnings**: Highlights test files and unsupported types
- **Reversible**: Use git to undo

## CLI Reference

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" --help
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" generators  # List supported languages
```
