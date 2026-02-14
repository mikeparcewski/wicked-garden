# wicked-jam

Organizational decision memory. Every brainstorm produces a searchable decision record -- what was decided, why, what alternatives were considered. Weeks later, revisit decisions to record whether they worked. Future brainstorms automatically surface past outcomes as evidence, so personas argue from your team's actual history instead of generic opinions. Decisions compound into institutional knowledge that vanilla Claude prompts can never accumulate.

## The Decision Lifecycle

This is what makes wicked-jam different from "just asking Claude to brainstorm":

```
Week 1:  /brainstorm "caching strategy"
         → Personas debate with evidence from your codebase
         → Decision record stored: "Chose Redis, rationale: X, alternatives: Y, Z"

Week 3:  /revisit "caching strategy"
         → "How did this work out?" → Validated / Invalidated / Modified
         → Outcome recorded with lessons learned

Week 6:  /brainstorm "caching improvements"
         → Past decision + outcome surfaced automatically as evidence
         → Personas cite: "Redis was chosen in Week 1, validated in Week 3"
         → New decision builds on real history, not starting from zero
```

Vanilla Claude forgets everything between sessions. wicked-jam accumulates decision intelligence over time.

## Quick Start

```bash
# Install
claude plugin install wicked-jam@wicked-garden

# Quick exploration (60 seconds, 4 personas)
/wicked-jam:jam "should we use Redis for sessions?"

# Full brainstorm with evidence + decision record (2-5 minutes)
/wicked-jam:brainstorm "authentication approaches for our API"

# Revisit a past decision to record its outcome
/wicked-jam:revisit "authentication"
```

## Commands

| Command | What It Does | Duration |
|---------|-------------|----------|
| `/wicked-jam:brainstorm` | Full session: evidence gathering, personas, synthesis, decision record | ~2-5 minutes |
| `/wicked-jam:jam` | Quick exploration with 4 personas and lightweight record | ~60 seconds |
| `/wicked-jam:perspectives` | Multi-perspective feedback, no synthesis | ~60 seconds |
| `/wicked-jam:revisit` | Revisit a past decision and record its outcome | ~2 minutes |
| `/wicked-jam:help` | Usage and examples | Instant |

### When to Use What

- **`/brainstorm`** - Significant decision that should be tracked and revisited later
- **`/jam`** - Quick gut check, focused topic, limited time
- **`/perspectives`** - Want raw viewpoints, you'll do your own synthesis
- **`/revisit`** - A past decision needs outcome tracking (validated, invalidated, modified)

## How It Works

### 1. Evidence Gathering

Before personas debate, the facilitator gathers real data:
- **Past decisions** from wicked-mem: "Last time we discussed auth, we chose JWT because..."
- **Code context** from your codebase: "There are 3 existing cache implementations using pattern X"
- **Past outcomes** from wicked-mem: "The Redis decision from Jan was validated after load testing"

This evidence brief is injected into every persona's context. They cite your data, not generic opinions.

### 2. Persona Assembly & Debate

4-6 personas selected from archetypes, each armed with the evidence brief:

| Archetype | Example Personas |
|-----------|-----------------|
| Technical | Architect, Debugger, Optimizer, Security Reviewer |
| User-Focused | Power User, Newcomer, Support Rep |
| Business | Product Manager, Skeptic, Evangelist |
| Process | Maintainer, Tester, Documentarian |

2-3 rounds of debate where personas build on and challenge each other's positions.

### 3. Multi-AI Perspective (Optional)

After persona rounds, optionally sends the synthesis to an external AI (Gemini/Codex via wicked-startah) for a contrasting viewpoint that gets integrated into the final output.

### 4. Decision Record

Every brainstorm automatically stores a structured record:
- **What was decided** and why
- **Alternatives considered** with trade-offs
- **Confidence level** (HIGH/MEDIUM/LOW)
- **Evidence used** in the discussion

This record is searchable, recallable, and automatically surfaced in future brainstorms.

### Options

```bash
# Custom personas
/wicked-jam:brainstorm "error handling" --personas "Security,Tester,Debugger"

# Control discussion depth (1-5 rounds)
/wicked-jam:brainstorm "caching strategy" --rounds 3
```

## Example Output

```
## Brainstorm: Authentication Approaches

### Key Insights
1. JWT with refresh tokens - HIGH confidence
   - Stateless, scales well, industry standard
   - Evidence: existing session middleware uses stateless tokens
2. OAuth2 integration - MEDIUM confidence
   - Good for third-party auth, more complex
3. Session-based fallback - LOW confidence
   - Simpler but doesn't scale
   - Evidence: past decision on sessions was invalidated after load test

### Action Items
1. Prototype JWT implementation (2-3 days)
2. Research OAuth2 providers
3. Define token refresh strategy

### Decision Record Stored
Topic: Authentication Approaches | Confidence: HIGH | Tags: jam,decision,auth,jwt
```

## Agents & Skills

| Component | Type | What It Does |
|-----------|------|-------------|
| `facilitator` | Agent | Role-plays focus group personas and synthesizes discussions |
| `brainstorming` | Skill | Orchestrates the persona selection, discussion rounds, and synthesis workflow |

## Data API

This plugin exposes data via the standard Plugin Data API. Sources are declared in `wicked.json`.

| Source | Capabilities | Description |
|--------|-------------|-------------|
| sessions | list, get, search, stats | Brainstorming session history with perspectives and synthesis |

Query via the workbench gateway:
```
GET /api/v1/data/wicked-jam/{source}/{verb}
```

Or directly via CLI:
```bash
python3 scripts/api.py {verb} {source} [--limit N] [--offset N] [--query Q]
```

## Integration

Works standalone for brainstorming. Decision lifecycle requires wicked-mem.

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-mem | **Decision records + outcome tracking + evidence recall** -- the full decision lifecycle | Brainstorming works, but decisions aren't stored or recalled. No `/revisit`. |
| wicked-search | Code evidence for personas (existing implementations, blast radius) | Personas argue from general knowledge, not your codebase |
| wicked-crew | Auto-engaged during clarify/design phases of crew projects | Use commands directly |
| wicked-startah | Multi-AI debate (Gemini/Codex contrasting perspective) | Claude personas only |

## License

MIT
