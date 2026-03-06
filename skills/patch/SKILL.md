---
name: patch
description: |
  Language-agnostic code generation and change propagation. Use this skill when
  adding fields to entities, renaming symbols across files, or propagating changes
  that affect multiple files. Triggered by: "add field", "rename everywhere",
  "propagate change", "generate migration", "update all references".

  This is the CODE MUTATION counterpart to wicked-search (which is read-only).
---

# wicked-patch

Generate and propagate code changes across your entire codebase using the symbol graph.

## Quick Start

```bash
# 1. Index your codebase (if not already done)
/wicked-garden:search:index /path/to/project

# 2. Add a field to an entity
/wicked-garden:patch:add-field "Entity.java::User" --name email --type String

# 3. Rename a field everywhere
/wicked-garden:patch:rename "Entity.java::User" --old status --new state

# 4. See propagation plan
/wicked-garden:patch:plan "Entity.java::User" --change add_field
```

## Commands

| Command | Purpose |
|---------|---------|
| `/wicked-garden:patch:plan` | Show what would be affected |
| `/wicked-garden:patch:add-field` | Add field with propagation |
| `/wicked-garden:patch:rename` | Rename across all usages |
| `/wicked-garden:patch:remove` | Remove field everywhere |
| `/wicked-garden:patch:apply` | Apply saved patches |

## Supported Languages

| Extension | Features |
|-----------|----------|
| `.java` | JPA @Column, getters/setters, validation |
| `.py` | SQLAlchemy, Pydantic, dataclass |
| `.ts`, `.js` | TypeORM, interfaces, types |
| `.jsp` | Spring form tags, EL expressions |
| `.sql` | ALTER TABLE (PostgreSQL, Oracle, MySQL, SQL Server) |

## How It Works

```
ChangeSpec (add field "email" to User)
           │
           ▼
   ┌───────────────────┐
   │ Propagation Engine │  ← Uses wicked-search lineage graph
   └───────────────────┘
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
  Java   Python   SQL      JSP
   │       │       │         │
   ▼       ▼       ▼         ▼
Patches  Patches Patches  Patches
```

## Examples

### Add Field to JPA Entity

```bash
/wicked-garden:patch:add-field "User.java::User" \
  --name email \
  --type String \
  --column USER_EMAIL \
  --required
```

**Generates:**

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

### Rename Field Everywhere

```bash
/wicked-garden:patch:rename "Order.java::Order" --old status --new orderStatus
```

**Updates:**
- Entity field declaration
- Getters/setters
- JSP form bindings (`${order.status}` → `${order.orderStatus}`)
- Service layer references
- Test files (with warning)

### Save and Review Patches

```bash
# Generate patches without applying
/wicked-garden:patch:add-field SYMBOL --name foo --type String --output patches.json

# Review the patches file
cat patches.json

# Apply when ready
/wicked-garden:patch:apply patches.json
```

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

## Integration with wicked-search

wicked-patch reads from the wicked-search symbol database:

```bash
# 1. wicked-search creates the graph
/wicked-garden:search:index /project --derive-all

# 2. wicked-patch uses it for propagation
/wicked-garden:patch:add-field SYMBOL --name foo --type String
```

## Safety Features

- **Dry-run by default**: Shows patches without applying
- **Confirmation prompt**: Asks before applying
- **Patch files**: Save for review before applying
- **Warnings**: Highlights test files and unsupported types
- **Reversible**: Use git to undo

## CLI Reference

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts
python3 patch.py --help
python3 patch.py generators  # List supported languages
```
