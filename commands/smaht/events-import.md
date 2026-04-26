---
description: "Import existing domain JSON records into the unified event log"
argument-hint: "[--domain D] [--dry-run]"
---

# /wicked-garden:smaht:events-import

Import existing DomainStore JSON records into the unified event log as historical events.

## Instructions

### 1. Discover Existing Records

Scan the DomainStore local root for all domain directories:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
from _domain_store import _LOCAL_ROOT
from pathlib import Path
import json

root = Path(_LOCAL_ROOT) if isinstance(_LOCAL_ROOT, str) else _LOCAL_ROOT
domains = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.exists() else []
print(json.dumps(domains))
"
```

### 2. For Each Domain

Read all JSON files and synthesize events with `action: "{source}.migrated"`:

```python
from _event_store import EventStore
from _domain_store import _LOCAL_ROOT
from pathlib import Path
import json

EventStore.ensure_schema()

domain_dir = Path(_LOCAL_ROOT) / domain_name
imported = 0
skipped = 0

for source_dir in domain_dir.iterdir():
    if not source_dir.is_dir():
        continue
    source = source_dir.name
    for json_file in source_dir.glob("*.json"):
        record = json.loads(json_file.read_text())
        record_id = record.get("id", json_file.stem)

        # Idempotent: skip if already imported
        existing = EventStore.query(
            domain=domain_name,
            action=f"{source}.migrated",
            limit=1,
        )
        # Check by record_id to avoid duplicates
        if any(e.get("record_id") == record_id for e in existing):
            skipped += 1
            continue

        EventStore.append(
            domain=domain_name,
            action=f"{source}.migrated",
            source=source,
            record_id=record_id,
            payload=record,
            tags=["migrated"],
        )
        imported += 1
```

### 3. Report Results

```markdown
## Import Complete

| Domain | Imported | Skipped (already exists) |
|--------|----------|--------------------------|
| crew | 45 | 0 |
| mem | 23 | 0 |
| jam | 12 | 0 |
| **Total** | **80** | **0** |

Events are tagged with `migrated` for easy filtering.
Query with: `/wicked-garden:crew:activity --fts migrated`
```

### Flags

- `--domain D`: Import only one domain (default: all)
- `--dry-run`: Show what would be imported without writing
