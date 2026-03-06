# Multi-Model Orchestration Patterns

Patterns for coordinating multiple AI models via the collaboration API.
No CLI shelling required — models are spawned as real agent sessions
with different providers assigned per persona.

## The Orchestration Loop

```
1. Create collaboration (POST /scopes/:id/collaborations)
2. Run session (POST /collaborations/:id/run)
   → Backend discovers authenticated models
   → Assigns different model per persona (round-robin)
   → Spawns AgentRuntime sessions in parallel
   → Collects outputs as perspectives
3. Synthesize (current session reviews all perspectives)
4. Persist decision (wicked-mem + collaboration record)
```

## How Model Assignment Works

### Discovery

```typescript
// CollaborationService calls discoverAuthenticatedModels()
// which uses AuthStorage.create() to check provider credentials:

const MODEL_POOL = [
  { provider: 'anthropic',         modelId: 'claude-opus-4-6' },
  { provider: 'google-gemini-cli', modelId: 'gemini-2.5-pro' },
  { provider: 'openai-codex',      modelId: 'gpt-5.3-codex' },
  { provider: 'openai',            modelId: 'gpt-5.2' },
  { provider: 'google',            modelId: 'gemini-2.5-pro' },
];

// Only models with valid API keys are included.
// Provider families are deduplicated (openai-codex + openai = 1 slot).
```

### Round-Robin Assignment

```
5 personas, 3 authenticated providers:

architect       → anthropic:claude-opus-4-6      [index 0]
security-eng    → google-gemini-cli:gemini-2.5-pro [index 1]
product-manager → openai-codex:gpt-5.3-codex     [index 2]
ux-designer     → anthropic:claude-opus-4-6       [index 0, wraps]
staff-engineer  → google-gemini-cli:gemini-2.5-pro [index 1, wraps]
```

### Explicit Override

Pass `config.model_map` when creating a collaboration:

```json
{
  "type": "jam:council",
  "topic": "Auth architecture review",
  "config": {
    "personas": ["architect", "security-engineer", "ux-designer"],
    "model_map": {
      "architect": "anthropic:claude-opus-4-6",
      "security-engineer": "google-gemini-cli:gemini-2.5-pro"
    }
  }
}
```

Unmapped roles get auto-assigned via round-robin.

## Context Layers

```
┌────────────────────────────────────────────┐
│  Collaboration Record (perspectives[])      │  ← All model outputs stored
├────────────────────────────────────────────┤
│  Per-Session Runtime State                  │  ← Each AgentRuntime has own model
├────────────────────────────────────────────┤
│  Prompt Context (collaboration.prompt)      │  ← Shared prompt to all personas
└────────────────────────────────────────────┘
```

## Gathering Perspectives

### Via Collaboration API (Recommended)

```bash
# 1. Create collaboration
curl -X POST http://localhost:18889/api/v1/scopes/$SCOPE_ID/collaborations \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "jam:council",
    "topic": "Should we use JWT or sessions?",
    "prompt": "Review auth design for security, scalability, and UX",
    "config": { "personas": ["architect", "security-engineer", "ux-designer"] }
  }'

# 2. Run multi-model session (spawns agents with different models)
curl -X POST http://localhost:18889/api/v1/collaborations/$COLLAB_ID/run

# 3. Check perspectives
curl http://localhost:18889/api/v1/collaborations/$COLLAB_ID
# → perspectives[] with model attribution in metadata
```

### Via /jam:council Command

```bash
# From pi CLI — handles everything automatically
/jam:council "Should we use JWT or sessions for auth?"
```

## Synthesis Framework

After gathering perspectives, synthesize using:

| Signal | Meaning | Action |
|--------|---------|--------|
| **Consensus** (2+ models agree) | High confidence issue | Address immediately |
| **Unique insight** (1 model) | Worth evaluating | Don't dismiss |
| **Disagreement** | Genuine tradeoff | Human decides |
| **Silence** | No model flagged it | Lower priority |

### Synthesis Output Template

```markdown
## Multi-Model Council: [Topic]

**Models**: Claude Opus, Gemini Pro, Codex
**Personas**: architect, security-engineer, ux-designer

### Consensus (High Confidence)
- Issue 1: flagged by Claude, Gemini
- Issue 2: flagged by all 3

### Unique Insights
- **Gemini**: [long-context catch others missed]
- **Claude**: [architectural nuance]
- **Codex**: [implementation detail]

### Disagreements
- [Topic]: Gemini says X, Claude says Y → human decides

### Recommended Actions
1. [Highest priority]
2. [Second priority]

### Open Questions
- [What remains unresolved]
```

## Session Management

Each persona's agent session is tracked in the sessions table with:
- `model` — the assigned model spec
- `scope_id` — same scope as the collaboration
- `metadata.collaboration_id` — links back to the collaboration record

Sessions are fire-and-forget: the collaboration service polls for output
until timeout (`COLLAB_RUN_TURN_TIMEOUT_MS`, default 12s).

## Persistence

### Automatic

Every `/collaborations/:id/run` call:
- Creates session records with model attribution
- Emits events: `agent:session:spawning`, `agent:session:started`,
  `collaboration:perspective:added`, `collaboration:run:completed`
- Stores `model` in each perspective's metadata

### Decision Records

```bash
/memory_write content="Auth: JWT with 15min/7day expiry.
Council: Claude (architect), Gemini (security), Codex (ux).
Consensus: idempotency critical, session store risky at scale.
Unique: Gemini flagged Redis cluster cost." \
  type=decision tags=auth,council
```

## Anti-Patterns

```
# BAD: Shelling out to CLI tools
cat file.md | gemini "Review this"  # slow, fragile, no persistence

# GOOD: Use collaboration API
POST /collaborations/:id/run        # fast, model-diverse, persisted

# BAD: Same model for all personas
config: { default_model: "anthropic:claude-opus-4-6" }  # no diversity

# GOOD: Let the system auto-rotate
config: { personas: [...] }  # backend picks different model per role

# BAD: Manual synthesis by reading CLI output
# GOOD: Structured synthesis from perspectives[] with model attribution
```
