# Runtime execution — Python and Node

Reference for the `wicked-garden-core` skill (the former runtime-exec module, folded here in
wave-2 B10). Execute Python and Node scripts using the best available package manager. The launcher paragraph
in `SKILL.md`'s Runtime section is the short form; this ref is the detection ladder, the usage patterns and the
troubleshooting.

## Recommended: use the `wicked-garden` launcher

For scripts inside this plugin, prefer the launcher. It resolves the plugin
root itself (`WICKED_GARDEN_ROOT` → the host CLI's plugin root → its own npm
package) and the interpreter (`<root>/.venv` → `uv run --project <root>` →
`python3` / `python` / `py -3`) on macOS, Linux and Windows in one call, keeps
the caller's cwd, and never writes under the root. Bare `python3` is not
available on Windows; a flat skills-only install has no `scripts/` at all —
the launcher is what makes both cases work.

```bash
wicked-garden run scripts/{path-to}/your_script.py [args]   # .py → python · .mjs/.js → node · .sh → sh
wicked-garden python -c "print('inline python, same interpreter')"
wicked-garden path scripts/qe/lib                          # absolute path under the plugin root
wicked-garden doctor                                       # what it resolved, and why
```

`scripts/_python.sh` (`python3` → `python` → `py -3`) remains the shim the
plugin's hooks use. The detection logic below is reference material for
scripts that need a different fallback chain (e.g. dependency-aware `uv run`).

## Python Execution Priority

1. **`wicked-garden run`** (preferred for plugin scripts) - Resolves root + interpreter, never writes under the root
2. **uv** - Fast, reliable, handles dependencies automatically
3. **poetry** - Good for projects with poetry.lock
4. **.venv/bin/python** - Pre-existing virtual environment
5. **`python3` / `_python.sh` shim** - Cross-platform fallback; may miss dependencies

## Node Execution Priority

1. **pnpm** (preferred) - Fast, disk-efficient
2. **npm** - Standard, widely available
3. **yarn** - Alternative package manager
4. **npx** - For one-off script execution

## Usage Patterns

### Python Script Execution

```bash
# In a directory with pyproject.toml (the plugin root, for plugin scripts):
cd "$(wicked-garden root)"

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
# In a directory with package.json (e.g. the qe runner):
cd "$(wicked-garden path scripts/qe/runner)"

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
- For plugins, scripts are in `scripts/`

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
