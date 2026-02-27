---
name: runtime-exec
description: Smart runtime execution for Python and Node scripts with automatic package manager detection.
triggers:
  - python script
  - node script
  - run script
  - execute python
  - uv run
  - poetry run
  - npm run
  - pnpm run
---

# Runtime Execution Skill

Execute Python and Node scripts using the best available package manager.

## Python Execution Priority

1. **uv** (preferred) - Fast, reliable, handles dependencies automatically
2. **poetry** - Good for projects with poetry.lock
3. **.venv/bin/python** - Pre-existing virtual environment
4. **python3** - Last resort, may miss dependencies

## Node Execution Priority

1. **pnpm** (preferred) - Fast, disk-efficient
2. **npm** - Standard, widely available
3. **yarn** - Alternative package manager
4. **npx** - For one-off script execution

## Usage Patterns

### Python Script Execution

```bash
# In a directory with pyproject.toml:
cd ${PLUGIN_DIR}/scripts

# Preferred (auto-installs deps)
uv run python script.py [args]

# Alternative
poetry run python script.py [args]

# If venv exists
.venv/bin/python script.py [args]

# Last resort (may fail on deps)
python3 script.py [args]
```

### Node Script Execution

```bash
# In a directory with package.json:
cd ${PLUGIN_DIR}/scripts

# Preferred
pnpm run script-name
pnpm exec script.js

# Alternative
npm run script-name
npx script.js

# Yarn
yarn run script-name
```

## Detection Logic

When executing a script, detect the runtime context:

```bash
# Python detection
if command -v uv &>/dev/null && [ -f pyproject.toml ]; then
    uv run python "$@"
elif command -v poetry &>/dev/null && [ -f poetry.lock ]; then
    poetry run python "$@"
elif [ -f .venv/bin/python ]; then
    .venv/bin/python "$@"
else
    python3 "$@"
fi

# Node detection
if command -v pnpm &>/dev/null && [ -f pnpm-lock.yaml ]; then
    pnpm exec "$@"
elif command -v npm &>/dev/null && [ -f package-lock.json ]; then
    npx "$@"
elif command -v yarn &>/dev/null && [ -f yarn.lock ]; then
    yarn exec "$@"
else
    node "$@"
fi
```

## Important Notes

- Always `cd` to the script directory first (where pyproject.toml/package.json lives)
- Use `uv run` for Python - it auto-syncs dependencies from pyproject.toml
- Warn user if falling back to system Python/Node (deps may be missing)
- For plugins, scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`

## Common Issues

### Missing Dependencies
If using system python3 and imports fail:
```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or create venv manually
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Wrong Python Version
```bash
# Check version
uv run python --version

# Specify version in pyproject.toml:
# requires-python = ">=3.10"
```
