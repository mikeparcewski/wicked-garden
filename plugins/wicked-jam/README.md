# wicked-jam

AI brainstorming with dynamic focus groups -- 4-6 personas that actually debate and build on each other's ideas. Get diverse trade-offs on architecture decisions, naming, and strategy in 60 seconds instead of scheduling a meeting. Real perspectives, real tension, real synthesis -- no meetings required.

## Quick Start

```bash
# Install
claude plugin install wicked-jam@wicked-garden

# Quick exploration (60 seconds, 4 personas)
/wicked-jam:jam "should we use Redis for sessions?"

# Full brainstorm (2-5 minutes, multiple rounds)
/wicked-jam:brainstorm "authentication approaches for our API"

# Raw perspectives without synthesis
/wicked-jam:perspectives "GraphQL vs REST for our public API"
```

## Commands

| Command | What It Does | Duration |
|---------|-------------|----------|
| `/wicked-jam:jam` | Quick exploration with 4 personas | ~60 seconds |
| `/wicked-jam:brainstorm` | Full facilitated session with synthesis | ~2-5 minutes |
| `/wicked-jam:perspectives` | Multi-perspective feedback, no synthesis | ~60 seconds |
| `/wicked-jam:help` | Usage and examples | Instant |

### When to Use What

- **`/jam`** - Quick gut check, focused topic, limited time
- **`/brainstorm`** - Significant decision, needs thorough exploration and action items
- **`/perspectives`** - Want raw viewpoints, you'll do your own synthesis

## How It Works

1. **Context gathering** - Understands the problem space
2. **Persona assembly** - Generates 4-6 relevant personas from archetypes
3. **Discussion rounds** - Personas contribute and build on each other
4. **Synthesis** - Key findings with confidence levels + action items

### Persona Archetypes

| Archetype | Example Personas |
|-----------|-----------------|
| Technical | Architect, Debugger, Optimizer, Security Reviewer |
| User-Focused | Power User, Newcomer, Support Rep |
| Business | Product Manager, Skeptic, Evangelist |
| Process | Maintainer, Tester, Documentarian |

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
2. OAuth2 integration - MEDIUM confidence
   - Good for third-party auth, more complex
3. Session-based fallback - LOW confidence
   - Simpler but doesn't scale

### Action Items
1. Prototype JWT implementation (2-3 days)
2. Research OAuth2 providers
3. Define token refresh strategy
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

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged during clarify phase | Use commands directly |
| wicked-mem | Recalls prior context, stores insights | Session-only memory |

## License

MIT
