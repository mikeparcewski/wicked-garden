---
name: wicked-garden-data
user-invocable: true
description: |
  Data engineering, analysis, and ML toolkit. One skill, routed sub-actions:
  analyze (interactive EDA on a CSV/Excel/data file), profile / validate /
  quality (schema-level data engineering ops), ml review / ml pipeline
  (model review + training-pipeline design), pipeline design / pipeline
  review (ETL architecture), and ontology (recommend Schema.org, Dublin
  Core, DCAT, FOAF, GoodRelations, SKOS, or a custom shape for a dataset).

  Use when: "analyze this CSV/Excel/data file" / "explore this dataset" /
  one-off data exploration; "profile this dataset" / "validate data against
  a schema" / "generate a data quality report" (completeness, uniqueness,
  validity); "review this ML model" / "design an ML training pipeline";
  "design a data pipeline" / "review this ETL" / "optimize data
  processing"; "recommend an ontology for this data" / "map columns to a
  public ontology". Replaces the former /wicked-garden:data:* commands
  (analyze, data, ml, ontology, pipeline).

  NOT for delegated subagent work — dispatch the wicked-garden-data-engineer
  fork skill for that.
# TODO #339: When Claude Code supports 'paths' in skill frontmatter for
# file-context auto-activation, add:
#   paths: ["**/dags/**", "**/pipelines/**", "**/etl/**", "**/airflow/**", "**/prefect/**"]
phase_relevance: ["clarify", "design", "build"]
archetype_relevance: ["*"]
---

# wicked-garden:data — data engineering, analysis, and ML

Every sub-action runs inline (no dispatch): parse the arguments, pre-read the
data where noted, load the Tier-3 rubric from refs/, apply it, and emit
structured markdown with tables and prioritized findings. For delegated or
parallel worker execution, dispatch the **wicked-garden-data-engineer** fork
skill instead.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Routing

| Sub-action | Use for | Rubric |
|------------|---------|--------|
| `analyze <file-path> [--focus stats\|quality\|warehouse\|ml] [--context <file>] [--refresh] [--scenarios]` | one-off exploration of a CSV/Excel/data file | [refs/analyze.md](refs/analyze.md) |
| `profile <path>` | dataset structure + quality profile | [refs/data.md](refs/data.md) |
| `validate --schema <schema> --data <path>` | schema validation | [refs/data.md](refs/data.md) |
| `quality <path>` | quality report (completeness, uniqueness, validity) | [refs/data.md](refs/data.md) |
| `ml review <path>` | ML model review | [refs/ml.md](refs/ml.md) |
| `ml pipeline --type <classification\|regression\|ranking>` | training-pipeline design | [refs/ml.md](refs/ml.md) |
| `pipeline design --source <src> --target <tgt> [--frequency <freq>]` | ETL pipeline design | [refs/pipeline.md](refs/pipeline.md) |
| `pipeline review <path>` | ETL pipeline review | [refs/pipeline.md](refs/pipeline.md) |
| `ontology <file-path>` | ontology recommendation for a dataset | inline (§ Ontology) |

Detailed templates and examples: [refs/analysis-templates.md](refs/analysis-templates.md),
[refs/ml-templates.md](refs/ml-templates.md),
[refs/pipeline-templates.md](refs/pipeline-templates.md),
[refs/data-examples.md](refs/data-examples.md).

## Analyze — interactive data analysis

Interactive analysis on a CSV/Excel/data file. Use for one-off data
exploration. NOT for schema-level checks (use `profile` / `validate` /
`quality`) or pipeline review (use `pipeline review`).

1. Parse `<file-path>`, `--focus` (stats|quality|warehouse|ml, default
   `stats`), `--context`, `--refresh`, `--scenarios`.
2. Read first rows of the file to capture column names / types / nulls / sample.
3. Read `refs/analyze.md` (relative to this skill's base directory) — the EDA
   rubric, quality/warehouse/ml modes, insight pattern, and output format.
4. Apply the rubric directly for the chosen `--focus` mode and emit the analysis.

## Profile / Validate / Quality — core data engineering ops

Schema-level engineering ops on a dataset. NOT for interactive exploration
(use `analyze`) or ML pipeline review (use `ml`).

1. Parse the sub-action (profile|validate|quality) and its args (`<path>`,
   `--schema` for validate).
2. Read the data file head/tail to capture columns / types / nulls / sample.
3. Read `refs/data.md` — the profile,
   validate, and quality rubrics with output formats and quality thresholds.
4. Apply the rubric for the requested sub-action and emit structured markdown
   with tables and prioritized findings.

**Optional scripted paths** (deterministic profiling/validation):

```bash
wicked-garden run scripts/data/data_profiler.py \
  --input data.csv --output profile.json
```

```bash
wicked-garden run scripts/data/schema_validator.py \
  --schema schemas/expected.json \
  --data data/actual.csv
```

For files >1GB, use the `analyze` sub-action for efficient SQL-based profiling
via DuckDB.

## ML — model review and training-pipeline design

ML model `review` and training-`pipeline` design. NOT for ETL pipeline design
(use `pipeline`) or data profiling (use `profile`).

1. Parse the sub-action (review|pipeline) and args (`<path>` for review,
   `--type` for pipeline).
2. For `review`, read model files at `<path>`.
3. Read `refs/ml.md` — the model review
   checklist, pipeline design template, deployment readiness checklist, and
   MLOps standards.
4. Apply the rubric for the requested sub-action and emit structured markdown.

## Pipeline — data pipeline design and review

Data pipeline `design` and `review`. NOT for ML training pipelines (use
`ml pipeline`) or one-off file analysis (use `analyze`).

1. Parse the sub-action (design|review) and args. For `review`, read pipeline
   files at `<path>`. For `design`, capture `--source`, `--target`,
   `--frequency`.
2. Read `refs/pipeline.md` — the design
   checklist, review rubric with P1/P2/P3 findings, pattern selection, and
   engineering standards.
3. Apply the rubric for the requested sub-action and emit structured markdown.

## Ontology — recommend ontologies for a dataset

Sample a dataset (CSV/Excel/Parquet/JSON) and recommend matching public
ontologies (Schema.org, Dublin Core, DCAT, FOAF, GoodRelations, SKOS) or a
custom shape. Use this for ontology mapping. NOT for interactive analysis
(use `analyze`) or quality reports (use `quality`).

1. **Arg parse** — extract `file-path` from the arguments.
2. **Run recommender**:

   ```bash
   wicked-garden run scripts/_run.py scripts/data/ontology_recommender.py "${file_path}"
   ```

3. Present the script's match table, column-mapping suggestions, and any
   custom-ontology fallback inline.
