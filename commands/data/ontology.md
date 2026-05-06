---
description: Sample a dataset and recommend public or custom ontologies based on the data
argument-hint: "<file-path>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:data:ontology

Sample a dataset (CSV/Excel/Parquet/JSON) and recommend matching public ontologies (Schema.org, Dublin Core, DCAT, FOAF, GoodRelations, SKOS) or a custom shape. Use this for ontology mapping. NOT for interactive analysis (use `data:analyze`) or quality reports (use `data:data`).

## 1. Arg parse

Extract `file-path` from arguments.

## 2. Run recommender

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/data/ontology_recommender.py "${file_path}"
```

Present the script's match table, column-mapping suggestions, and any custom-ontology fallback inline.
