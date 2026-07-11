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

The propagation diagram, quick-start recipes, per-action examples, the sample
`PROPAGATION PLAN` / `GENERATED PATCHES` output, the patches-file JSON schema,
and the language/type/SQL-dialect reference tables live in
[refs/output-samples.md](refs/output-samples.md).

## Sub-actions

| Sub-action | Purpose |
|------------|---------|
| `patch-plan` | Show what would be affected — propagation preview, no patches |
| `add-field` | Add field with propagation |
| `rename` | Rename across all usages |
| `remove` | Remove field everywhere (DELETES code — see warning) |
| `apply` | Apply saved patches from a JSON file |
| `new-generator` | Author a new language generator ([refs/new-generator.md](refs/new-generator.md)) |

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

See [refs/output-samples.md](refs/output-samples.md) for examples and the sample `PROPAGATION PLAN` output.

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

See [refs/output-samples.md](refs/output-samples.md) for examples, a JPA entity walkthrough (generated Java/SQL), and the `GENERATED PATCHES` output.

## rename — rename a field/symbol across all usages

**Arguments**: `symbol_id` (required); `--old` (required — current field name);
`--new` (required — new field name); `--output`/`-o` (save patches to file);
`--apply` (apply patches immediately); `--verbose`/`-v` (show full diffs).

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/engineering/patch/patch.py" rename "<symbol_id>" --old "<old_name>" --new "<new_name>" [--verbose]
```

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

See [refs/output-samples.md](refs/output-samples.md) for the save→review→dry-run→apply workflow and the patches-file JSON schema.

## new-generator — create a new language generator

Create a new language generator for wicked-patch with scaffolding, golden test
fixtures, and conformance validation. Arguments: `language` (required, e.g.
"scala", "swift", "elixir"); `framework` (optional ORM/framework, e.g. "Slick",
"CoreData", "Ecto"); `extensions` (optional file extensions, defaults to
lowercase language). Follow the full 7-step authoring workflow (generator
template with TYPE_MAP, `__init__.py` registration, golden fixture JSON,
`test_conformance.py` additions, run tests, report) in
[refs/new-generator.md](refs/new-generator.md).

## Language & type reference

Supported languages (`.java`, `.py`, `.ts`/`.js`, `.jsp`, `.sql`), the generic→
per-language type mappings, and SQL dialect support (PostgreSQL / Oracle / MySQL /
SQL Server, auto-detected or via `--dialect`) are tabulated in
[refs/output-samples.md](refs/output-samples.md#language--type-reference).

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
