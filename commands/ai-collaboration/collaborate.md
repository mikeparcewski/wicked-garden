---
description: Orchestrate multi-AI CLI collaboration — discover, review, council, and persist
---

# /wicked-garden:ai-collaboration:collaborate

Discover AI CLIs in the current environment and run multi-model collaboration workflows:
reviews, council sessions, and preference-driven orchestration.

## Usage

```
/wicked-garden:ai-collaboration:collaborate [--discover] [--review FILE] [--council "QUESTION"] [--prompt "PROMPT"]
```

## Arguments

- `--discover` — Detect installed AI CLIs and report what's available
- `--review FILE` — Run multi-model review of the given file
- `--council "QUESTION"` — Run a council session on a decision question
- `--prompt "PROMPT"` — Custom prompt to run across all detected CLIs
- `--models codex,gemini,...` — Limit to specific models (comma-separated)

## Instructions

### Step 1: Discover Available CLIs

Always start by detecting which AI CLIs are installed:

```bash
AVAILABLE=()
command -v codex    &>/dev/null && AVAILABLE+=("codex")
command -v gemini   &>/dev/null && AVAILABLE+=("gemini")
command -v opencode &>/dev/null && AVAILABLE+=("opencode")
command -v pi       &>/dev/null && AVAILABLE+=("pi")
command -v claude   &>/dev/null && AVAILABLE+=("claude")
```

If `--discover` flag only: report discovered CLIs, their paths, and quick-start commands. Done.

If no CLIs are detected: inform the user and suggest installation:
- `codex`: `brew install codex`
- `gemini`: `npm install -g @google/gemini-cli`
- `opencode`: `brew install opencode`
- `pi`: `brew install pi-mono`

### Step 2: Recall Preferences (if any)

Check wicked-mem for stored AI collaboration preferences:

```bash
/wicked-garden:mem:recall "ai cli preferences"
```

Use stored preferences to weight or order models (e.g., "use gemini for long docs, codex for code").

### Step 3: Execute Mode

**Mode: `--review FILE`**

1. Read the file
2. Determine appropriate review prompt based on file type (`.py`, `.ts` → code review; `.md` → design/spec review; `.yaml` → config review)
3. Run the prompt across all detected CLIs:
   ```bash
   PROMPT="Review this for issues, risks, and improvements"
   cat "$FILE" | gemini "$PROMPT"      # if detected
   cat "$FILE" | codex exec "$PROMPT" # if detected
   opencode run "$PROMPT" -f "$FILE" -m openai/gpt-4o  # if detected
   cat "$FILE" | pi exec "$PROMPT"    # if detected
   ```
4. Create a wicked-kanban task to track the review:
   ```bash
   /wicked-garden:kanban:new-task "Multi-model review: ${FILE}" --priority P1
   ```
5. Present each response with model attribution
6. Synthesize: identify consensus, unique insights, disagreements

**Mode: `--council "QUESTION"`**

1. Announce the question
2. Run across detected CLIs with a perspective-first framing:
   - Gemini/Codex/OpenCode: analytical, technical perspectives
   - Pi: empathetic, user-focused perspective
3. Present perspectives labeled by model
4. Synthesize consensus and disagreements
5. Ask user for their decision; offer to store it:
   ```bash
   /wicked-garden:mem:store "Decision: ${QUESTION}. [summary]" --type decision --tags multi-model-review
   ```

**Mode: `--prompt "PROMPT"` (custom)**

Run the given prompt across all detected CLIs and present results side-by-side.

### Step 4: Synthesize

After gathering all perspectives, present synthesis:

```markdown
## Multi-Model Review: [topic]

**Models used**: [list of detected CLIs that responded]

### Consensus (flagged by 2+)
- [issue flagged by multiple models]

### Unique Insights
- **[Model]**: [what only this model caught]

### Disagreements
- [topic]: [Model A says X] vs [Model B says Y]

### Recommended Action
[Based on consensus and unique insights]
```

### Step 5: Persist (optional)

Offer to store the decision in wicked-mem:

```bash
/wicked-garden:mem:store "[topic]: [decision summary].
Consensus: [models]. Unique: [notable unique insights]." \
  --type decision --tags multi-model-review
```

## Error Handling

- If a CLI is found but fails on query: note the failure, continue with others
- If only one CLI is available: run it and note single-model limitation
- If no CLIs available: report and suggest installation (never fail silently)
- Never block — always return something actionable
