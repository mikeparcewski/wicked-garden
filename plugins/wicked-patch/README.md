# wicked-patch

Language-agnostic code generation using symbol graphs — add a field to a Java entity and automatically propagate changes to SQL migrations, DAOs, JSP views, REST APIs, and UI components. Cross-language change propagation with language-specific idioms across 5 languages, not string replacement.

## Quick Start

```bash
# Install (wicked-search is required for the symbol graph)
claude plugin install wicked-patch@wicked-garden
claude plugin install wicked-search@wicked-garden

# Build the symbol graph
/wicked-search:index .

# Add a field - patches propagate to every layer
/wicked-patch:add-field "User.java::User" --name email --type String

# Preview impact before changing anything
/wicked-patch:plan "User.java::User" --change add_field

# Rename across the entire codebase
/wicked-patch:rename "Order.java::Order" --old status --new orderStatus

# Remove a field and every reference to it
/wicked-patch:remove "User.java::User" --name legacyField
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-patch:plan` | Show what would be affected by a change | `/wicked-patch:plan "Entity::Entity" --change add_field` |
| `/wicked-patch:add-field` | Add a field with propagation to all layers | `/wicked-patch:add-field "User::User" --name email --type String` |
| `/wicked-patch:rename` | Rename a symbol across all usages | `/wicked-patch:rename "Order::Order" --old status --new orderStatus` |
| `/wicked-patch:remove` | Remove a field and all references | `/wicked-patch:remove "User::User" --name legacyField` |
| `/wicked-patch:apply` | Apply saved patch file | `/wicked-patch:apply patches.json` |
| `/wicked-patch:new-generator` | Create a new language generator | `/wicked-patch:new-generator kotlin` |

## What Gets Patched

Adding `email` to a `User` entity generates patches for:

| Language | Generated Code |
|----------|---------------|
| Java | `@Column`, getter/setter, `@NotNull` validation |
| SQL | `ALTER TABLE` for PostgreSQL, Oracle, MySQL, SQL Server |
| JSP | Spring form tags, EL expressions |
| Python | SQLAlchemy Column, Pydantic Field, dataclass |
| TypeScript | TypeORM `@Column`, interfaces, type aliases |

```
Your Change → wicked-search symbol graph → Find all affected files → Generate patches
                                                  │
                        ┌──────┬──────┬──────┬─────┤
                        Java  Python  SQL   JSP   TypeScript
```

## Safety

- **Dry-run by default**: Shows patches without applying
- **Save for review**: `-o patches.json` for team review before applying
- **Confirmation prompts**: Asks before applying changes
- **Reversible**: Use git to undo

## Integration

Requires **wicked-search** for the symbol graph.

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-search | **Required** - provides symbol graph | Cannot function |
| wicked-cache | Cached graph lookups | Re-queries each time |

## License

MIT
