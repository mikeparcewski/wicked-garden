---
phase_relevance: ["bootstrap"]
archetype_relevance: ["*"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     the retired wicked-testing plugin's `setup` orchestrator). Loaded on demand <!-- historical -->
     via Read() from the router's `setup` action — not a skill. -->


# qe setup — full playbook

Initialize the qe domain for the current project. Creates
`.wicked-qe/config.json`, detects available test CLIs, and registers a
project record in the DomainStore. This is the remediation for `ERR_NO_CONFIG`
anywhere in the qe domain (plan, acceptance-testing, test-oracle,
release-readiness all point here).

This skill runs in the main context (Bash/Write) — it is an orchestrating
entry point, not an isolated worker.

## Usage

```
wicked-garden-qe setup [--project <name>] [--json]
```

- `--project <name>` — project name to register (defaults to directory name)
- `--json` — emit JSON envelope output

## Instructions

### 1. Detect Available Test CLIs

Check for test CLI tools:

```bash
command -v playwright > /dev/null 2>&1 && echo "playwright: true" || echo "playwright: false"
command -v cypress > /dev/null 2>&1 && echo "cypress: true" || echo "cypress: false"
command -v k6 > /dev/null 2>&1 && echo "k6: true" || echo "k6: false"
command -v curl > /dev/null 2>&1 && echo "curl: true" || echo "curl: false"
command -v pa11y > /dev/null 2>&1 && echo "pa11y: true" || echo "pa11y: false"
npx --no-install playwright --version > /dev/null 2>&1 && echo "npx-playwright: true" || echo "npx-playwright: false"
npx --no-install cypress --version > /dev/null 2>&1 && echo "npx-cypress: true" || echo "npx-cypress: false"
```

### 2. Create .wicked-qe Directory

```bash
mkdir -p .wicked-qe/projects .wicked-qe/strategies .wicked-qe/scenarios \
         .wicked-qe/runs .wicked-qe/verdicts .wicked-qe/tasks \
         .wicked-qe/evidence
```

### 3. Write config.json

Write `.wicked-qe/config.json` using Python cross-platform pattern:

```bash
python3 -c "
import json, sys, os
config = {
    'project': os.path.basename(os.getcwd()),
    'version': '1.0',
    'capabilities': {
        'playwright': False,
        'cypress': False,
        'k6': False,
        'curl': True,
        'pa11y': False
    },
    'created_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat().replace('+00:00', 'Z'),
    'claim_nudge': False
}
open('.wicked-qe/config.json', 'w').write(json.dumps(config, indent=2))
" 2>/dev/null || python -c "<same script>"
```

Update the capabilities based on detection results from Step 1.

### 4. Register Project in DomainStore

Determine project name: use `--project` arg, or basename of current directory.

Write a project record. If SQLite is available, it will be indexed; otherwise JSON-only.

If SQLite is unavailable, print a warning:
```
WARNING: better-sqlite3 not available — store running in JSON-only mode.
Oracle and stats commands require SQLite. Run: npm rebuild better-sqlite3
```

### 5. Output

**Without `--json`**:

```markdown
## QE Setup Complete

**Project**: {name}
**Store mode**: {sqlite+json | json-only}

### Capabilities Detected

| Tool | Status |
|------|--------|
| playwright | {Installed / Not found} |
| cypress | {Installed / Not found} |
| k6 | {Installed / Not found} |
| curl | {Installed / Not found} |
| pa11y | {Installed / Not found} |

**Config**: .wicked-qe/config.json
**Project ID**: {id}

Next steps:
- `wicked-garden-qe plan` skill — create a test strategy
- `wicked-garden-qe author` skill — author test scenarios
- `wicked-garden-qe accept` skill (e.g. on `scenarios/test-runner.md`) — run the acceptance test pipeline
- **Claim-boundary nudge (optional, off by default):** set `"claim_nudge": true` in
  `.wicked-qe/config.json` to be reminded to run `acceptance` whenever a turn
  claims "tests pass" with no acceptance verdict on record. Auto-registers under a
  marketplace/plugin install; loose-skill installs require plugin-mode (see CHANGELOG).
```

**With `--json`** — emit the JSON envelope via Python pattern:

```bash
python3 -c "import json,sys; sys.stdout.write(json.dumps({'ok': True, 'data': {'project': '{name}', 'project_id': '{id}', 'capabilities': {...}, 'store_mode': '...'}, 'meta': {'command': 'wicked-garden-qe setup', 'duration_ms': 0, 'schema_version': 1, 'store_mode': '...' }}))" 2>/dev/null || python -c "..."
```
