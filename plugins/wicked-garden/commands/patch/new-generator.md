---
description: Create a new language generator for wicked-patch with scaffolding, tests, and validation
---

# /wicked-garden:patch-new-generator

Create a new language generator for wicked-patch with scaffolding, tests, and validation.

## Arguments

- `language` (required): Language name (e.g., "scala", "swift", "elixir")
- `framework` (optional): ORM/framework to target (e.g., "Slick", "CoreData", "Ecto")
- `extensions` (optional): File extensions (e.g., ".scala", defaults to lowercase language)

## Instructions

When this skill is invoked, follow these steps to create a complete generator:

### Step 1: Gather Information

If not provided, ask the user:
1. What ORM/framework should this generator target?
2. What file extensions should it handle?
3. What are the common class/entity patterns in this language?

### Step 2: Create the Generator

Create a new file at:
```
~/Projects/wicked-garden/plugins/wicked-patch/scripts/generators/{language}_generator.py
```

Use this template structure (adapt for the specific language):

```python
"""
{Language} code generator.

Generates patches for {Language} files including:
- {Framework} models (add/modify fields)
- Classes (add properties)
- [Other patterns specific to this language]

{Framework} format: [Example of generated code]
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

from .base import (
    BaseGenerator,
    register_generator,
    ChangeSpec,
    ChangeType,
    FieldSpec,
    Patch,
)

logger = logging.getLogger(__name__)


@register_generator
class {Language}Generator(BaseGenerator):
    """Generate patches for {Language} files."""

    name = "{language}"
    extensions = {"{extensions}"}
    symbol_types = {"class", "entity", "model", ...}

    # Type mappings from generic types to {Language} types
    TYPE_MAP = {
        "string": "{StringType}",
        "str": "{StringType}",
        "text": "{StringType}",
        "int": "{IntType}",
        "integer": "{IntType}",
        "long": "{LongType}",
        "bigint": "{LongType}",
        "float": "{FloatType}",
        "double": "{DoubleType}",
        "decimal": "{DecimalType}",
        "boolean": "{BoolType}",
        "bool": "{BoolType}",
        "date": "{DateType}",
        "datetime": "{DateTimeType}",
        "timestamp": "{TimestampType}",
        "uuid": "{UUIDType}",
        "binary": "{BinaryType}",
        "json": "{JsonType}",
    }

    def generate(
        self,
        change_spec: ChangeSpec,
        symbol: Dict[str, Any],
        file_content: str,
    ) -> List[Patch]:
        """Generate patches for a {Language} file."""
        patches = []

        if change_spec.change_type == ChangeType.ADD_FIELD:
            patches.extend(self._add_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.REMOVE_FIELD:
            patches.extend(self._remove_field(change_spec, symbol, file_content))
        elif change_spec.change_type == ChangeType.RENAME_FIELD:
            patches.extend(self._rename_field(change_spec, symbol, file_content))

        return patches

    def _add_field(self, change_spec, symbol, file_content) -> List[Patch]:
        # Implement field addition logic
        pass

    def _remove_field(self, change_spec, symbol, file_content) -> List[Patch]:
        # Implement field removal logic
        pass

    def _rename_field(self, change_spec, symbol, file_content) -> List[Patch]:
        # Implement field rename logic
        pass

    def _map_type(self, generic_type: str, language: str = None) -> str:
        """Map generic type to {Language} type."""
        return self.TYPE_MAP.get(generic_type.lower(), generic_type)
```

### Step 3: Update __init__.py

Add import to `~/Projects/wicked-garden/plugins/wicked-patch/scripts/generators/__init__.py`:

```python
from . import {language}_generator
```

### Step 4: Create Golden Test Fixture

Create `~/Projects/wicked-garden/plugins/wicked-patch/scripts/tests/fixtures/{language}_add_field.json`:

```json
{
  "name": "{language}_add_field",
  "description": "Add a new field to a {Framework} model",
  "generator": "{language}",
  "input": {
    "change_type": "add_field",
    "field_spec": {
      "name": "email",
      "type": "String",
      "nullable": false
    },
    "sample_content": "[Minimal valid {Language} class/entity code]",
    "symbol": {
      "id": "path/to/file.{ext}::ClassName",
      "name": "ClassName",
      "type": "class",
      "file_path": "path/to/file.{ext}",
      "line_start": 1,
      "line_end": 10
    }
  },
  "expected": {
    "patch_count_min": 1,
    "must_contain": [
      "email",
      "[expected type]",
      "[expected annotation/decorator]"
    ],
    "must_not_contain": [
      "undefined"
    ]
  }
}
```

### Step 5: Update Test File

Add to `~/Projects/wicked-garden/plugins/wicked-patch/scripts/tests/test_conformance.py`:

1. Add contract test in `TestGeneratorContract`:
```python
def test_{language}_generator_contract(self):
    """{Language} generator passes all contract tests."""
    from generators.{language}_generator import {Language}Generator

    sample = """[minimal valid code]"""
    report = run_conformance_tests({Language}Generator, sample)
    assert report.passed, report.summary()
```

2. Add golden test in `TestGoldenOutput`:
```python
def test_{language}_add_field(self):
    """{Language} add_field golden test."""
    self._run_golden_test("{language}_add_field")
```

3. Add to `ext_map` in `_run_golden_test`:
```python
"{language}": ".{ext}",
```

4. Add to `samples` in `run_all_tests`:
```python
".{ext}": "[minimal sample code]",
```

5. Add import in `run_all_tests`:
```python
from generators import {language}_generator
```

### Step 6: Run Tests

Execute:
```bash
cd ~/Projects/wicked-garden/plugins/wicked-patch/scripts
python3 tests/test_conformance.py
```

Verify:
- Contract tests pass for the new generator
- Golden test passes
- No regressions in other generators

### Step 7: Report Results

Output a summary:
```
## New Generator: {Language}

- **File**: `generators/{language}_generator.py`
- **Extensions**: {extensions}
- **Framework**: {Framework}
- **Tests**: PASS/FAIL

### Type Mappings
| Generic | {Language} |
|---------|-----------|
| String  | {type}    |
| Integer | {type}    |
| ...     | ...       |

### Example Output
[Show example of generated code for add_field]
```

## Examples

```
/wicked-garden:patch-new-generator scala Slick
/wicked-garden:patch-new-generator swift CoreData .swift
/wicked-garden:patch-new-generator elixir Ecto .ex,.exs
```
