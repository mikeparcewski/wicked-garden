# Multi-Model Orchestration Patterns

Patterns for coordinating multiple AI models via external CLI dispatch.
Each model responds independently to a fixed question scaffold, then Claude synthesizes.

## The Orchestration Loop

```
1. Detect CLIs (which codex gemini opencode pi)
2. Quorum check (need 2+ for true council)
3. Build question scaffold (4 fixed questions)
4. Dispatch scaffold to each CLI in parallel (stdin pipe)
5. Claude answers the same scaffold independently
6. Synthesize all responses (3-stage output)
7. Persist transcript + decision record
```

## CLI Detection

```bash
# Council agent detects available CLIs at runtime
which codex 2>/dev/null && echo "codex:available" || echo "codex:missing"
which copilot 2>/dev/null && echo "copilot:available" || echo "copilot:missing"
which gemini 2>/dev/null && echo "gemini:available" || echo "gemini:missing"
which opencode 2>/dev/null && echo "opencode:available" || echo "opencode:missing"
which pi 2>/dev/null && echo "pi:available" || echo "pi:missing"
```

### Quorum Rules

| Available External CLIs | Behavior |
|------------------------|----------|
| 0 | Refuse council. Suggest `/jam:brainstorm` instead. |
| 1 | Run as "brainstorm with external guest" — warn not a true council. |
| 2+ | Full council mode. |

## Question Scaffold

Every external model answers the **same fixed question set** for comparability:

```
Topic: {topic}
Options under evaluation: {options}
Evaluation criteria: {criteria}

Answer these 4 questions:

1. RECOMMENDATION: Which option do you recommend and why?
2. TOP RISK: What is the single biggest risk in your recommendation?
3. WHAT WOULD CHANGE YOUR MIND: What evidence would reverse your recommendation?
4. DISQUALIFIER: Is any option fundamentally unviable? If so, which and why?
```

## Parallel Dispatch

**Non-negotiable**: Each model responds independently. No model sees another's output.

```bash
# Write scaffold to temp file (avoids shell quoting issues)
SCAFFOLD_FILE="${TMPDIR:-/tmp}/council-scaffold-$$.md"
cat > "$SCAFFOLD_FILE" <<'SCAFFOLD_EOF'
{question_scaffold_content}
SCAFFOLD_EOF

# Dispatch in parallel (all run simultaneously via multiple Bash calls)
cat "$SCAFFOLD_FILE" | codex exec "Evaluate the options. Answer the 4 questions."
cat "$SCAFFOLD_FILE" | copilot -p "Evaluate the options. Answer the 4 questions." --output-format text --available-tools=""
cat "$SCAFFOLD_FILE" | gemini "Evaluate the options. Answer the 4 questions."
cat "$SCAFFOLD_FILE" | opencode run "Evaluate the options. Answer the 4 questions."
cat "$SCAFFOLD_FILE" | pi exec "Evaluate the options. Answer the 4 questions."
```

Claude also answers the scaffold independently before reading external responses.

## Synthesis Framework

### Three-Stage Output

**Stage 1: Independent Responses** — Raw answers per model, clearly separated.

```markdown
## Council Evaluation: {topic}

*Each model responded independently. No model saw another's output.*

### Claude
{Claude's 4 answers}

### Codex
{Codex's 4 answers}

### Gemini
{Gemini's 4 answers}
```

**Stage 2: Synthesis Matrix** — Structured comparison.

```markdown
| Model | Recommendation | Top Risk | Disqualifier |
|-------|---------------|----------|-------------|
| Claude | {option} | {risk} | {disqualifier or None} |
| Codex | {option} | {risk} | {disqualifier or None} |
| Gemini | {option} | {risk} | {disqualifier or None} |

### Risk Convergence
**High signal** (3+ models cite): {risks in 3+ responses}
**Notable** (1-2 models cite): {risks from 1-2 responses}
```

**Stage 3: Verdict** — Consensus or fault lines.

```markdown
## Verdict
**Council recommends {Option X}** ({count}-{dissent}).
Primary risk: {most-cited risk}.
```

Or if no consensus:
```markdown
## Verdict
**No consensus.** Fault lines: {Option A} vs {Option B}.
Key disagreement: {fundamental question models disagree on}.
```

## Transcript Persistence

Council responses are persisted via `save_transcript.py`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/jam/save_transcript.py" \
  --session-id "{session_id}" \
  --entries '{json_array_of_entries}'
```

Each model response becomes one entry:
```json
{
  "session_id": "{session_id}",
  "round": 1,
  "persona_name": "Gemini",
  "persona_type": "council",
  "raw_text": "{full response}",
  "timestamp": "{ISO timestamp}",
  "entry_type": "council_response"
}
```

Synthesis is appended as `entry_type: synthesis`, `persona_name: Council`.

### Decision Records (via wicked-mem)

```bash
/wicked-garden:mem:store "Auth: JWT with 15min/7day expiry.
Council: Claude (architect), Gemini (security), Codex (ux).
Consensus: idempotency critical, session store risky at scale.
Unique: Gemini flagged Redis cluster cost." \
  --type decision --tags auth,council
```

## Anti-Patterns

```
# BAD: No quorum check
Run council with 0 external CLIs  # just Claude talking to itself

# GOOD: Check quorum first
which codex copilot gemini opencode pi    # need 2+ for real council

# BAD: Sequential dispatch (one model could influence the next)
response1=$(codex exec "$q"); echo "$response1" | gemini "$q"

# GOOD: Parallel dispatch (all independent)
codex exec "$q" &  gemini "$q" &  # simultaneous, isolated

# BAD: Confidence scores in synthesis
"Gemini is 85% confident..."  # LLMs produce uncalibrated numbers

# GOOD: Risk convergence
"3/3 models flagged this risk"  # count-based signal
```

## Important Rules

1. **No confidence scores** — Use risk convergence (count-based) instead
2. **No rounds** — Single structured pass; rounds break isolation
3. **No editorial gloss on Stage 1** — Present raw answers without interpretation
4. **Parallel only** — Never run CLIs sequentially
5. **Claude participates** — Always a council member, same scaffold
