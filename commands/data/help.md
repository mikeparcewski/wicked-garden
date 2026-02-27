---
description: Show available data engineering commands and usage
---

# /wicked-garden:data:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-data Help

Data analysis and ontology recommendations for CSV, Excel, and structured datasets.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:data:analyze <file>` | Interactive data analysis session for CSV/Excel files |
| `/wicked-garden:data:ontology <file>` | Sample a dataset and recommend ontologies |
| `/wicked-garden:data:help` | This help message |

## Quick Start

```
/wicked-garden:data:analyze sales.csv --focus quality
/wicked-garden:data:ontology users.csv
```

## Examples

### Data Analysis
```
/wicked-garden:data:analyze data.csv --focus profiling
/wicked-garden:data:analyze report.xlsx --context schema.md --refresh
/wicked-garden:data:analyze metrics.csv --scenarios
```

### Ontology Discovery
```
/wicked-garden:data:ontology products.csv
```

## Integration

- **wicked-crew**: Specialist routing for data engineering phases
- **wicked-search**: Lineage tracing through data pipelines
- **wicked-mem**: Stores analysis results and data decisions
```
