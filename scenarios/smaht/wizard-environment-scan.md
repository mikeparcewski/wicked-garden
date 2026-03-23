---
name: wizard-environment-scan
title: Setup Wizard — Environment Scan (Project Type and Integration Detection)
description: Verify the environment scan scripts in setup.md correctly detect project type from filesystem markers and available CLI integrations
type: testing
difficulty: beginner
estimated_minutes: 6
---

# Setup Wizard — Environment Scan (Project Type and Integration Detection)

This scenario tests Step 4.0 of `commands/setup.md` (AC-278-1, AC-278-2). The two detection
scripts — project type from filesystem markers and available integrations from PATH — are
exercised in a controlled directory and must produce valid, parseable JSON.

## Setup

```bash
export TMPDIR=$(mktemp -d)

# Create a synthetic Python project directory
PROJ_DIR="${TMPDIR}/test-project"
mkdir -p "${PROJ_DIR}"
touch "${PROJ_DIR}/pyproject.toml"
```

## Steps

## Step 1: Project type detection identifies Python from pyproject.toml (AC-278-1)

Run the detection script from `setup.md` against the synthetic project directory. It must
return a JSON object with a `languages` array that includes `"Python"`.

```bash
cd "${PROJ_DIR}"
python3 -c "
import json
from pathlib import Path
cwd = Path.cwd()
markers = {
    'Python': ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
    'Node/TypeScript': ['package.json', 'tsconfig.json'],
    'Go': ['go.mod'],
    'Rust': ['Cargo.toml'],
    'Java/Kotlin': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    'Ruby': ['Gemfile'],
    'PHP': ['composer.json'],
    'Swift': ['Package.swift'],
    'C/C++': ['CMakeLists.txt', 'Makefile'],
}
frameworks = {
    'FastAPI': ['app/main.py', 'main.py'],
    'Django': ['manage.py'],
    'Flask': ['app.py'],
    'Next.js': ['next.config.js', 'next.config.ts'],
    'React': ['src/App.tsx', 'src/App.jsx'],
    'Vue': ['vue.config.js'],
    'Rails': ['config/routes.rb'],
    'Claude Plugin': ['.claude-plugin/plugin.json'],
}
detected_langs = [l for l, fs in markers.items() if any((cwd / f).exists() for f in fs)]
detected_fws = [fw for fw, fs in frameworks.items() if any((cwd / f).exists() for f in fs)]
result = {'languages': detected_langs, 'frameworks': detected_fws}
print(json.dumps(result))
" | python3 -c "
import sys, json
data = json.load(sys.stdin)
langs = data.get('languages', [])
fws = data.get('frameworks', [])
print('VALID_JSON=true')
print('PYTHON_DETECTED=' + str('Python' in langs).lower())
print('languages=' + json.dumps(langs))
print('frameworks=' + json.dumps(fws))
"
```

### Expected

- Output contains `VALID_JSON=true`
- Output contains `PYTHON_DETECTED=true`
- `languages` JSON array includes `"Python"`

---

## Step 2: Integration detection finds gh CLI when it is installed (AC-278-2)

Run the integration detection script from `setup.md`. It must return a valid JSON object
with boolean values for each tool. When `gh` is installed on the test machine, `gh` must
be `true`.

```bash
python3 -c "
import shutil, json
tools = {
    'gh': shutil.which('gh') is not None,
    'tree-sitter': shutil.which('tree-sitter') is not None,
    'duckdb': shutil.which('duckdb') is not None,
    'ollama': shutil.which('ollama') is not None,
    'docker': shutil.which('docker') is not None,
    'kubectl': shutil.which('kubectl') is not None,
}
print(json.dumps(tools))
" | python3 -c "
import sys, json
data = json.load(sys.stdin)
all_bool = all(isinstance(v, bool) for v in data.values())
expected_keys = {'gh', 'tree-sitter', 'duckdb', 'ollama', 'docker', 'kubectl'}
has_all_keys = expected_keys.issubset(data.keys())
gh_detected = data.get('gh', False)
print('VALID_JSON=true')
print('ALL_VALUES_BOOL=' + str(all_bool).lower())
print('ALL_KEYS_PRESENT=' + str(has_all_keys).lower())
print('gh=' + str(gh_detected).lower())
"
```

### Expected

- Output contains `VALID_JSON=true`
- Output contains `ALL_VALUES_BOOL=true`
- Output contains `ALL_KEYS_PRESENT=true`
- `gh=true` when `gh` is installed on the system (informational — not a hard failure if absent)

---

## Step 3: Both scripts produce parseable JSON in combination (AC-278-1, AC-278-2)

Verify that both outputs can be independently parsed and combined into a single context
object, mimicking how `setup.md` uses `DETECTED_LANGS`, `DETECTED_FWS`, and `DETECTED_TOOLS`.

```bash
cd "${PROJ_DIR}"
python3 - <<'PYEOF'
import json, shutil
from pathlib import Path

# --- Project type detection ---
cwd = Path.cwd()
markers = {
    'Python': ['pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile'],
    'Node/TypeScript': ['package.json', 'tsconfig.json'],
    'Go': ['go.mod'],
    'Rust': ['Cargo.toml'],
    'Java/Kotlin': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    'Ruby': ['Gemfile'],
    'PHP': ['composer.json'],
    'Swift': ['Package.swift'],
    'C/C++': ['CMakeLists.txt', 'Makefile'],
}
frameworks = {
    'FastAPI': ['app/main.py', 'main.py'],
    'Django': ['manage.py'],
    'Flask': ['app.py'],
    'Next.js': ['next.config.js', 'next.config.ts'],
    'React': ['src/App.tsx', 'src/App.jsx'],
    'Vue': ['vue.config.js'],
    'Rails': ['config/routes.rb'],
    'Claude Plugin': ['.claude-plugin/plugin.json'],
}
detected_langs = [l for l, fs in markers.items() if any((cwd / f).exists() for f in fs)]
detected_fws = [fw for fw, fs in frameworks.items() if any((cwd / f).exists() for f in fs)]

# --- Integration detection ---
tools = {
    'gh': shutil.which('gh') is not None,
    'tree-sitter': shutil.which('tree-sitter') is not None,
    'duckdb': shutil.which('duckdb') is not None,
    'ollama': shutil.which('ollama') is not None,
    'docker': shutil.which('docker') is not None,
    'kubectl': shutil.which('kubectl') is not None,
}

# Combine as setup.md would
combined = {
    'DETECTED_LANGS': detected_langs,
    'DETECTED_FWS': detected_fws,
    'DETECTED_TOOLS': tools,
    'DETECTED_TOOLS_SUMMARY': [k for k, v in tools.items() if v],
}

# Validate round-trip
raw = json.dumps(combined)
parsed = json.loads(raw)
assert parsed['DETECTED_LANGS'] == detected_langs, 'langs mismatch'
assert isinstance(parsed['DETECTED_TOOLS']['gh'], bool), 'gh must be bool'
print('COMBINED_JSON_VALID=true')
print('DETECTED_LANGS=' + json.dumps(detected_langs))
print('DETECTED_TOOLS_SUMMARY=' + json.dumps(combined['DETECTED_TOOLS_SUMMARY']))
PYEOF
```

### Expected

- Output contains `COMBINED_JSON_VALID=true`
- `DETECTED_LANGS` includes `"Python"`
- `DETECTED_TOOLS_SUMMARY` is a JSON array of strings (tools available on the path)

## Expected Outcome

Both environment scan scripts from `setup.md` Step 4.0 produce valid JSON. The project type
detector correctly identifies the primary language from filesystem markers. The integration
detector reports boolean availability for each tool without crashing when tools are absent.
The outputs compose cleanly into the onboarding memory summary format.

## Success Criteria

- [ ] Project type script outputs valid JSON with `languages` and `frameworks` keys (AC-278-1)
- [ ] `"Python"` detected in `languages` when `pyproject.toml` is present (AC-278-1)
- [ ] Integration script outputs valid JSON with exactly the six expected tool keys (AC-278-2)
- [ ] All tool values are booleans, not null or strings (AC-278-2)
- [ ] `gh=true` when `gh` is on PATH (informational)
- [ ] Combined context object round-trips through JSON without error

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
