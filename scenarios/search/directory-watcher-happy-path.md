---
name: directory-watcher-happy-path
title: Directory Watcher Detects Stale Index
description: Detect filesystem changes since last index and trigger incremental reindex
type: feature
difficulty: intermediate
estimated_minutes: 8
---

# Directory Watcher Detects Stale Index

## Setup

Create a test project and index it:

```bash
mkdir -p /tmp/wicked-watcher-test/src

cat > /tmp/wicked-watcher-test/src/api.py << 'EOF'
class ApiHandler:
    """Handles API requests."""

    def handle_request(self, path: str) -> dict:
        """Process an incoming API request."""
        return {"path": path, "status": "ok"}
EOF

# Index the project first
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py index /tmp/wicked-watcher-test

# Save watcher state to a temp file so the watcher has a baseline
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/watcher.py status --dirs /tmp/wicked-watcher-test --state /tmp/wicked-watcher-state.json
```

## Steps

1. Check watcher status — no changes yet (freshly indexed):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/watcher.py check \
     --dirs /tmp/wicked-watcher-test \
     --state /tmp/wicked-watcher-state.json \
     --json
   ```

2. Modify a file to simulate real development:
   ```bash
   cat > /tmp/wicked-watcher-test/src/api.py << 'EOF'
   class ApiHandler:
       """Handles API requests."""

       def handle_request(self, path: str) -> dict:
           """Process an incoming API request."""
           return {"path": path, "status": "ok"}

       def validate_token(self, token: str) -> bool:
           """Validate an API auth token."""
           return len(token) > 0
   EOF
   ```

3. Run watcher check — should detect the changed file:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/watcher.py check \
     --dirs /tmp/wicked-watcher-test \
     --state /tmp/wicked-watcher-state.json \
     --json
   ```

4. Add a new file:
   ```bash
   cat > /tmp/wicked-watcher-test/src/middleware.py << 'EOF'
   class AuthMiddleware:
       """Authentication middleware."""

       def process(self, request: dict) -> dict:
           """Check auth before passing request."""
           return request
   EOF
   ```

5. Check again — should detect both the modified and new file:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/watcher.py check \
     --dirs /tmp/wicked-watcher-test \
     --state /tmp/wicked-watcher-state.json \
     --json
   ```

6. Check watcher status summary:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/watcher.py status \
     --dirs /tmp/wicked-watcher-test \
     --state /tmp/wicked-watcher-state.json \
     --json
   ```

## Expected Outcomes

- Initial check after indexing reports 0 changed files
- After modifying api.py, check detects exactly that file as changed
- After adding middleware.py, both files appear as changed (new file is detected)
- Status command shows watched directories and last-checked timestamp
- JSON output is well-formed and includes `changed_files` list and `stale` boolean
- State file is updated with new mtimes after each check

## Success Criteria

- [ ] `check` returns `{"stale": false, "changed_files": []}` immediately after indexing
- [ ] `check` returns `{"stale": true, "changed_files": [...]}` after file modification
- [ ] New files added after last check are included in changed_files
- [ ] `status` output includes watched dirs and last-checked timestamp
- [ ] State JSON file is written/updated on each check call
- [ ] Watcher handles non-existent state file gracefully (starts fresh)
- [ ] JSON output valid and parseable

## Value Demonstrated

**Problem solved**: Search index becomes stale silently — developers search and get outdated results without knowing it.

**Why this matters**:
- **Stale index detection**: SessionStart hook can run `watcher.py check` to warn users when index is out of date
- **Targeted updates**: Only re-index changed files rather than the entire codebase
- **Developer trust**: Eliminates confusion from missing symbols or outdated references in search results
- **CI integration**: Watcher check can gate searches in pipelines that require a fresh index
