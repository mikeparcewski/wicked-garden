# wicked-patch

Add a field to a Java entity and get the SQL migration, getters/setters, JSP form bindings, and TypeScript interface updates generated and applied in one command — propagated through the symbol graph, not string search.

## Quick Start

```bash
# 1. Install (wicked-search is a required dependency)
claude plugin install wicked-search@wicked-garden
claude plugin install wicked-patch@wicked-garden

# 2. Index your codebase once
/wicked-search:index .

# 3. Add a field — patches propagate to every affected layer
/wicked-patch:add-field "User.java::User" --name email --type String
```

## Workflows

### Add a field to an entity

Running `/wicked-patch:add-field "User.java::User" --name email --type String` produces:

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

Patches are shown for review by default. Add `--apply` to write them, or `-o patches.json` to save for team review.

### Preview impact before touching anything

```bash
/wicked-patch:plan "User.java::User" --change add_field
```

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

### Rename a field across every layer

```bash
/wicked-patch:rename "Order.java::Order" --old status --new orderStatus
```

Updates field declarations, getter/setter names, `this.status` property references, JSP EL expressions (`${entity.status}` → `${entity.orderStatus}`), Spring form bindings (`path="status"`), TypeScript interfaces, and generates `ALTER TABLE RENAME COLUMN` for SQL.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-patch:plan` | Show all files and symbols affected before making changes | `/wicked-patch:plan "Entity::Entity" --change add_field` |
| `/wicked-patch:add-field` | Add a field with full cross-layer propagation | `/wicked-patch:add-field "User::User" --name email --type String` |
| `/wicked-patch:rename` | Rename a field/symbol across every usage | `/wicked-patch:rename "Order::Order" --old status --new orderStatus` |
| `/wicked-patch:remove` | Remove a field and all references to it | `/wicked-patch:remove "User::User" --name legacyField` |
| `/wicked-patch:apply` | Apply a saved patch file | `/wicked-patch:apply patches.json` |
| `/wicked-patch:new-generator` | Scaffold a new language generator | `/wicked-patch:new-generator kotlin` |

## When to Use What

| You want to... | Use |
|----------------|-----|
| See the blast radius before committing | `/wicked-patch:plan` |
| Add a new attribute to a domain object | `/wicked-patch:add-field` |
| Fix a naming inconsistency across the codebase | `/wicked-patch:rename` |
| Delete deprecated fields cleanly | `/wicked-patch:remove` |
| Apply a reviewed patch file from a teammate | `/wicked-patch:apply` |
| Extend patch to a new language | `/wicked-patch:new-generator` |

## What Gets Patched

Adding `email: String` to a `User` entity generates language-specific code, not templates:

| Language | Generated Code |
|----------|---------------|
| Java | `@Column` annotation, getter, setter, optional `@NotNull` validation |
| SQL | `ALTER TABLE` for PostgreSQL, Oracle, MySQL, and SQL Server dialects |
| JSP | Spring form tags with `path=`, EL expressions |
| Python | SQLAlchemy `Column`, Pydantic `Field`, dataclass attribute |
| TypeScript | TypeORM `@Column`, interface property, type alias update |

## Safety

Patches are dry-run by default — nothing changes until you confirm:

- **Review first**: Default output shows diffs without writing files
- **Save for team review**: `-o patches.json` saves patches for manual inspection or PR review
- **Confirmation prompts**: `--apply` asks before writing each file
- **Reversible**: All changes are standard file edits; use `git diff` to inspect and `git checkout` to undo

## Skills

| Skill | What It Covers |
|-------|---------------|
| `patch` | Symbol graph navigation, change propagation patterns, generator extension, and the relationship between wicked-patch and wicked-search |

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-search | **Required** — provides the symbol graph that maps entities to every affected file | Cannot function; no symbol graph to traverse |
| wicked-startah | Cached symbol graph lookups between sessions | Re-queries the full graph on each command |

## License

MIT
