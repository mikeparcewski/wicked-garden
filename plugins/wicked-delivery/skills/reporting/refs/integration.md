# Integration Details

Report structure, caching, storage, and validation patterns.

## Report Structure

Each persona report includes:

```markdown
# {Persona} Report
Generated: {timestamp}
Source: {filename}

## Executive Summary
{3-5 bullet points of key findings}

## Key Metrics
{Tables of primary/secondary metrics}

## Analysis
{Detailed findings by focus area}

## Risks
{Identified risks with severity}

## Recommendations
{Actionable items with priority}
```

## Cache Strategy

Uses wicked-mem with file-based invalidation:

```python
from cache import namespace

cache = namespace("delivery")

# Cache with source file tracking
cache.set(
    key=f"analysis:{file_hash}:{persona}",
    value=analysis_result,
    source_file=input_file  # Auto-invalidates when file changes
)
```

## File Structure

```
plugins/wicked-delivery/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── report.md
├── skills/
│   └── reporting/
│       ├── SKILL.md
│       └── refs/
│           ├── personas.md
│           └── integration.md
├── scripts/
│   ├── generate_report.py
│   ├── persona_analysis.py
│   └── report_formatter.py
└── README.md
```

## Storage

Reports and cache stored in:

```
.something-wicked/wicked-delivery/
├── reports/
│   ├── report-delivery-lead.md
│   ├── report-engineering-lead.md
│   ├── report-product-lead.md
│   └── manifest.json
└── sessions/
    └── {session-id}/
```

Cache stored via wicked-mem:
```
.something-wicked/wicked-mem/namespaces/delivery/
├── index.json
└── data/
    ├── analysis:{hash}:{persona}.json
    └── mappings:{hash}.json
```

## Integration Examples

### With wicked-data
```python
# Data analysis queries
/wicked-data:numbers input.csv --query "SELECT status, COUNT(*) FROM data GROUP BY status"
```

### With utils:persona
```markdown
Generate a {persona_type} reviewer persona for project analysis.
Use /something-wicked:utils:persona with type "{persona_type}".
```

### With wicked-mem
```python
from cache import namespace
cache = namespace("delivery")
```

## Validation

Before generating reports, verify:
- [ ] Input file exists and is readable
- [ ] wicked-data is available
- [ ] Column mappings are confirmed (or auto-detected with high confidence)
- [ ] Selected personas are valid identifiers

## Error Handling

| Error | Recovery |
|-------|----------|
| File not found | Report error with path |
| Format detection fails | Ask user to confirm mappings |
| wicked-data missing | Prompt to install dependency |
| Insufficient data for persona | Generate partial report with warnings |
