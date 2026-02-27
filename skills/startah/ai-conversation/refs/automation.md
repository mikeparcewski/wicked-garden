# Automation: Multi-Model Review Scripts

Scripts and patterns for automating multi-AI conversations.

## Basic Multi-Review Script

```bash
#!/bin/bash
# multi-review.sh - Get perspectives from multiple AI models

CONTEXT_FILE=$1
PROMPT=$2

if [[ -z "$CONTEXT_FILE" || -z "$PROMPT" ]]; then
  echo "Usage: ./multi-review.sh <context-file> <prompt>"
  exit 1
fi

echo "=== Claude's Perspective ==="
echo "(Already in conversation - share your analysis)"
echo

echo "=== Gemini's Perspective ==="
cat "$CONTEXT_FILE" | gemini "$PROMPT" 2>/dev/null || echo "gemini CLI not available"
echo

echo "=== Codex's Perspective ==="
cat "$CONTEXT_FILE" | codex exec "$PROMPT" 2>/dev/null || echo "codex CLI not available"
echo

echo "=== OpenCode (GPT-4o) Perspective ==="
opencode run "$PROMPT" -f "$CONTEXT_FILE" -m openai/gpt-4o 2>/dev/null || echo "opencode CLI not available"
```

**Usage:**
```bash
chmod +x multi-review.sh
./multi-review.sh docs/design.md "Review for security and scalability"
```

## Enhanced Script with Kanban Integration

```bash
#!/bin/bash
# multi-review-kanban.sh - Multi-model review with kanban task creation

CONTEXT_FILE=$1
PROMPT=$2
TASK_TITLE=${3:-"Multi-model review"}

# Create kanban task
echo "Creating kanban task..."
TASK_ID=$(python3 -c "
import subprocess
result = subprocess.run(['python3', 'plugins/wicked-kanban/scripts/kanban.py',
                        'create', '--title', '$TASK_TITLE', '--priority', 'P1'],
                       capture_output=True, text=True)
print(result.stdout.strip().split()[-1])
" 2>/dev/null)

echo "Task created: $TASK_ID"
echo

# Collect perspectives
PERSPECTIVES=""

echo "=== Gathering Gemini's Perspective ==="
GEMINI_RESP=$(cat "$CONTEXT_FILE" | gemini "$PROMPT" 2>/dev/null)
if [[ -n "$GEMINI_RESP" ]]; then
  PERSPECTIVES="$PERSPECTIVES\n## Gemini\n$GEMINI_RESP\n"
  echo "Captured."
fi

echo "=== Gathering Codex's Perspective ==="
CODEX_RESP=$(cat "$CONTEXT_FILE" | codex exec "$PROMPT" 2>/dev/null)
if [[ -n "$CODEX_RESP" ]]; then
  PERSPECTIVES="$PERSPECTIVES\n## Codex\n$CODEX_RESP\n"
  echo "Captured."
fi

echo "=== Gathering OpenCode's Perspective ==="
OPENCODE_RESP=$(opencode run "$PROMPT" -f "$CONTEXT_FILE" -m openai/gpt-4o 2>/dev/null)
if [[ -n "$OPENCODE_RESP" ]]; then
  PERSPECTIVES="$PERSPECTIVES\n## OpenCode (GPT-4o)\n$OPENCODE_RESP\n"
  echo "Captured."
fi

# Add all perspectives as comment
echo -e "$PERSPECTIVES" | python3 plugins/wicked-kanban/scripts/kanban.py \
  comment "$TASK_ID" --stdin 2>/dev/null

echo "All perspectives added to task $TASK_ID"
```

## Python Alternative

```python
#!/usr/bin/env python3
"""multi_review.py - Orchestrate multi-model reviews"""

import subprocess
import sys
from pathlib import Path

def run_model(name: str, cmd: list[str]) -> str | None:
    """Run a model and capture output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None

def main(context_file: str, prompt: str):
    context = Path(context_file).read_text()

    models = {
        "Gemini": ["gemini", prompt],
        "Codex": ["codex", "exec", prompt],
        "OpenCode": ["opencode", "run", prompt, "-f", context_file, "-m", "openai/gpt-4o"],
    }

    results = {}
    for name, cmd in models.items():
        print(f"Querying {name}...", file=sys.stderr)
        # For gemini/codex, pipe context
        if name in ("Gemini", "Codex"):
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True)
            stdout, _ = proc.communicate(input=context, timeout=120)
            results[name] = stdout.strip() if stdout else None
        else:
            results[name] = run_model(name, cmd)

    # Output results
    for name, response in results.items():
        print(f"\n## {name}\n")
        print(response if response else f"({name} not available)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python multi_review.py <context-file> <prompt>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
```

## Makefile Integration

```makefile
# Add to your project Makefile

REVIEW_PROMPT ?= "Review for security, scalability, and maintainability"

.PHONY: review-design review-api review-security

review-design:
	@./scripts/multi-review.sh docs/design.md $(REVIEW_PROMPT)

review-api:
	@./scripts/multi-review.sh docs/api-spec.yaml "Review API design for consistency and REST best practices"

review-security:
	@./scripts/multi-review.sh . "Identify security vulnerabilities and suggest fixes"
```

## CI Integration

```yaml
# .github/workflows/ai-review.yml
name: Multi-Model Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get changed files
        id: changed
        run: |
          echo "files=$(git diff --name-only ${{ github.event.before }} ${{ github.sha }} | tr '\n' ' ')" >> $GITHUB_OUTPUT

      - name: Run multi-model review
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          # Install CLIs
          npm install -g @anthropic/codex gemini-cli opencode

          # Review changed files
          for file in ${{ steps.changed.outputs.files }}; do
            echo "Reviewing $file..."
            ./scripts/multi-review.sh "$file" "Review this code change for issues"
          done
```
