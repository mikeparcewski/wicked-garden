# wicked-patch — output samples, examples & language reference

Verbose material moved out of `SKILL.md` (Tier-2 slim-body cap). The SKILL body
keeps the argument lists, the full CLI invocations, the sub-action table, and the
`remove` DELETES warning; everything illustrative lives here. All examples
abbreviate the CLI to `patch.py <sub-action> …` — always run the full form
(`sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" …`).

## How it works

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

## Quick start

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

## patch-plan — examples & sample output

Examples: `patch.py plan "User.java::User" --change add_field` ·
`patch.py plan "Order.java::Order" --change rename_field --json`

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

## add-field — examples & sample output

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

## rename & remove — examples

```bash
# rename
patch.py rename "User.java::User" --old status --new userStatus
patch.py rename "Order.java::Order" --old date --new orderDate -o patches.json

# remove
patch.py remove "User.java::User" --field legacyStatus
patch.py remove "Entity.java::Entity" --field oldField --verbose   # preview
```

## apply — workflow & patches-file schema

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

## Language & type reference

### Supported languages

| Extension | Features |
|-----------|----------|
| `.java` | JPA @Column, getters/setters, validation |
| `.py` | SQLAlchemy, Pydantic, dataclass |
| `.ts`, `.js` | TypeORM, interfaces, types |
| `.jsp` | Spring form tags, EL expressions |
| `.sql` | ALTER TABLE (PostgreSQL, Oracle, MySQL, SQL Server) |

### Type mappings

Generic types are automatically mapped per language:

| Generic | Java | Python | TypeScript | SQL |
|---------|------|--------|------------|-----|
| `string` | String | str | string | VARCHAR(255) |
| `integer` | Integer | int | number | INTEGER |
| `boolean` | boolean | bool | boolean | BOOLEAN |
| `date` | LocalDate | date | Date | DATE |
| `datetime` | LocalDateTime | datetime | Date | TIMESTAMP |
| `decimal` | BigDecimal | Decimal | number | DECIMAL(18,2) |

### SQL dialect support

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
