---
description: Sample a dataset and recommend public or custom ontologies based on the data
argument-hint: <file-path>
---

# /wicked-garden:data:ontology

Analyze a dataset's structure and recommend matching ontologies.

## Instructions

### 1. Parse Arguments

Extract the file path from arguments. Supported formats: CSV, Excel (.xlsx), Parquet, JSON.

### 2. Sample the Dataset

Use DuckDB to read the first 100 rows and extract:
- Column names and data types
- Sample values (first 5 non-null per column)
- Null percentage per column
- Cardinality estimates

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/ontology_recommender.py "${file_path}"
```

### 3. Match Against Known Ontologies

The script matches column names and patterns against these ontology catalogs:
- **Schema.org** — general web data (Person, Organization, Event, Product, etc.)
- **Dublin Core** — metadata and documents (title, creator, date, subject, etc.)
- **DCAT** — data catalogs and datasets (distribution, accessURL, byteSize, etc.)
- **FOAF** — social/people data (name, mbox, knows, interest, etc.)
- **GoodRelations** — commerce (price, currency, eligibleRegion, etc.)
- **SKOS** — knowledge organization (broader, narrower, prefLabel, etc.)

### 4. Report Recommendations

Present results:
```markdown
## Ontology Recommendations for {filename}

### Dataset Profile
- **Rows**: {count} | **Columns**: {count}
- **Types**: {type distribution}

### Recommended Ontologies

| Ontology | Match Score | Matched Columns | Notes |
|----------|-------------|-----------------|-------|
| Schema.org/Person | 85% | name, email, phone, address | Strong match for person data |
| Dublin Core | 40% | title, date, creator | Partial metadata match |

### Column Mapping

| Column | Type | Suggested Ontology Property | Confidence |
|--------|------|---------------------------|------------|
| name | string | schema:name | High |
| email | string | schema:email / foaf:mbox | High |
| created_at | datetime | dc:created | Medium |

### Custom Ontology Suggestion
If no public ontology matches well, suggest a custom ontology structure based on the data patterns.
```
