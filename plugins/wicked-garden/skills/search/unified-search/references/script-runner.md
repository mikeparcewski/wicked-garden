# Script Runner Reference

Standard procedure for executing wicked-search Python scripts.

## Runner Detection

Before running any script, detect the available Python runner. Check in priority order and use the **first** match:

| Priority | Runner | Detection | Command Pattern |
|----------|--------|-----------|-----------------|
| 1 | **uv** | `command -v uv` succeeds | `uv run python <script> <args>` |
| 2 | **poetry** | `command -v poetry` succeeds AND `poetry.lock` exists in scripts dir | `poetry run python <script> <args>` |
| 3 | **venv** | `.venv/bin/python` exists in scripts dir | `.venv/bin/python <script> <args>` |
| 4 | **system** | fallback (always available) | `python3 <script> <args>` |

### Detection one-liner

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts

if command -v uv >/dev/null 2>&1; then
  RUNNER="uv run python"
elif command -v poetry >/dev/null 2>&1 && [ -f poetry.lock ]; then
  RUNNER="poetry run python"
elif [ -f .venv/bin/python ]; then
  RUNNER=".venv/bin/python"
else
  RUNNER="python3"
fi

$RUNNER <script> <args>
```

### Shorthand (when uv is known to be available)

In Claude Code environments where `uv` is always present:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python <script> <args>
```

## Scripts Available

| Script | Purpose |
|--------|---------|
| `unified_search.py index <path>` | Build code+doc index |
| `unified_search.py search <query>` | Search all indexed content |
| `unified_search.py code <query>` | Search code symbols only |
| `unified_search.py docs <query>` | Search documents only |
| `unified_search.py refs <symbol>` | Find symbol references |
| `unified_search.py impl <section>` | Find implementing code |
| `unified_search.py scout <pattern>` | Quick pattern recon (no index) |
| `unified_search.py stats` | Show index statistics |
| `unified_search.py blast-radius <symbol>` | Dependency analysis |
| `lineage_tracer.py <symbol>` | Data lineage tracing |
| `service_detector.py` | Service architecture detection |
| `coverage_reporter.py` | Lineage coverage reporting |
| `accuracy_validator.py` | Index accuracy validation |
| `index_quality_crew.py` | Automated quality improvement |

## Database Path

Most scripts that use `--db` need the graph database path. Find it from index metadata:

```bash
# The graph DB is stored alongside the index at:
~/.something-wicked/wicked-search/<hash>_graph.db
```

Use `/wicked-garden:search-stats` to find the active index and its database path.

## Troubleshooting

- **ModuleNotFoundError**: You're not running from the scripts directory or not using the detected runner. Always `cd ${CLAUDE_PLUGIN_ROOT}/scripts` first.
- **No index found**: Run `/wicked-garden:search-index <path>` first.
- **kreuzberg warning**: Should not occur — kreuzberg is a core dependency. If seen, run `uv sync` in the scripts directory.
