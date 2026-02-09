# Skills Guidelines

Context-efficient skill design for the Wicked Garden marketplace.

## Core Principles

### 1. Skills are Capabilities, Not Documentation

Skills activate during specific workflow moments. They should provide exactly the context needed for that moment, nothing more.

### 2. Graceful Degradation (Wicked Garden Pattern)

**Every plugin MUST work standalone. Enhanced features activate when dependencies are available.**

This is non-negotiable for wicked-garden. Users should never be forced to install multiple plugins just to get started.

```
┌─────────────────────────────────────────────────────────────┐
│                    STANDALONE (Always works)                 │
│  - Core functionality                                        │
│  - File-based persistence                                    │
│  - Basic commands                                            │
├─────────────────────────────────────────────────────────────┤
│                    ENHANCED (When available)                 │
│  + wicked-cache → Faster repeated operations                 │
│  + wicked-mem → Cross-session memory                         │
│  + wicked-kanban → Visual task tracking                      │
└─────────────────────────────────────────────────────────────┘
```

#### Implementation Pattern

```python
# Check for optional dependency
def _get_cache():
    """Get cache if available. Returns None for graceful degradation."""
    try:
        cache_path = Path.home() / ".claude" / "plugins" / "wicked-cache" / "scripts"
        if not cache_path.exists():
            return None
        sys.path.insert(0, str(cache_path))
        from cache import namespace
        return namespace("my-plugin")
    except ImportError:
        return None

# Use with fallback
cache = _get_cache()
if cache:
    cached = cache.get(key)
    if cached:
        return cached

# Always have standalone path
result = compute_result()

if cache:
    cache.set(key, result)

return result
```

#### Document Degradation Levels

Every plugin README should include an Integration table:

```markdown
## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-cache | Faster repeated analysis | Re-computes each time |
| wicked-mem | Cross-session insights | Session-only memory |
| wicked-kanban | Visual task board | TodoWrite fallback |
```

#### Skill Description Pattern

Skills should document their degradation behavior:

```yaml
---
name: my-capability
description: |
  Does X with optional Y integration.

  Use when:
  - Primary use case
  - Secondary use case

  Enhanced with:
  - wicked-cache: Caches results for faster repeat runs
  - wicked-mem: Stores learnings across sessions
---
```

## The 200-Line Rule

**SKILL.md entry points MUST be ≤200 lines.**

This limit isn't arbitrary. It's based on how much context an LLM can efficiently scan to decide what to load next.

```
✓ 150 lines - Efficient, focused
✓ 180 lines - Acceptable
✗ 245 lines - Needs refactoring
✗ 500 lines - Context overload
```

## Three-Tier Progressive Disclosure

### Tier 1: Metadata (Always Loaded)

YAML frontmatter only. ~100 words maximum.

```yaml
---
name: my-capability
description: |
  One sentence: what this enables.
  One sentence: when to use it.

  Use when:
  - Bullet point triggers
  - Specific workflow moments
---
```

This is sufficient for Claude to assess relevance without loading the full skill.

### Tier 2: Entry Point (SKILL.md)

The main SKILL.md file. **200 lines maximum.**

Contents:
- Overview (what, why)
- Quick-start (immediate value)
- Navigation map (what's in refs/)
- Common patterns (80% use cases)

```markdown
# My Capability

[Overview - 2-3 sentences]

## Quick Start

[Immediate usage - get started in 30 seconds]

## Reference

For detailed documentation:
- [API Reference](refs/api.md) - Full API documentation
- [Examples](refs/examples.md) - Usage patterns
- [Advanced](refs/advanced.md) - Complex scenarios
```

### Tier 3: Reference Files (On-Demand)

Modular files in `refs/` subdirectory. 200-300 lines each.

```
skills/my-skill/
├── SKILL.md           # ≤200 lines - entry point
└── refs/
    ├── api.md         # API documentation
    ├── examples.md    # Usage examples
    ├── patterns.md    # Common patterns
    └── advanced.md    # Advanced configuration
```

Each reference file:
- Single topic focus
- Self-contained
- Loaded only when needed

## Workflow-Capability Organization

Group by what developers DO, not by tool:

```
BAD: Individual tool skills
├── cloudflare.md (870 lines)
├── vercel.md (650 lines)
├── docker.md (420 lines)
└── kubernetes.md (580 lines)

GOOD: Capability-based
├── deployment/
│   ├── SKILL.md (180 lines)
│   └── refs/
│       ├── cloudflare.md
│       ├── vercel.md
│       └── containers.md
```

## Performance Targets

| Metric | Target | Red Flag |
|--------|--------|----------|
| SKILL.md lines | ≤200 | >200 |
| Frontmatter words | ~100 | >150 |
| Cold-start load | <500 lines | >800 lines |
| Relevant info ratio | ~90% | <50% |
| Activation time | <100ms | >500ms |

## Validation Checklist

Before merging a skill:

### Context Efficiency
- [ ] SKILL.md ≤200 lines
- [ ] Frontmatter ~100 words
- [ ] Clear "Use when" triggers in description
- [ ] Quick-start provides immediate value
- [ ] Detailed content in refs/ if needed
- [ ] Each ref file 200-300 lines max
- [ ] Single-topic focus per ref file

### Graceful Degradation
- [ ] Works completely standalone (no required dependencies)
- [ ] Optional dependencies use try/except pattern
- [ ] README has Integration table showing enhancement vs fallback
- [ ] Skill description documents "Enhanced with" plugins
- [ ] No hard failures when optional plugins missing

### Specialist Skills (v3)
- [ ] specialist.json exists with valid role
- [ ] `enhances` array declares phase enhancement
- [ ] Events follow `[namespace:entity:action:status]` format
- [ ] hooks.json matches specialist.json hooks declarations
- [ ] Persona agents referenced in workflow documentation

## Specialist Plugin Skills (v3)

Skills in specialist plugins enhance wicked-crew phases. They require additional metadata.

### Specialist Skill Description Pattern

```yaml
---
name: my-specialist-skill
description: |
  Brief capability description.

  Use when:
  - Primary trigger
  - Secondary trigger

  Enhanced with:
  - wicked-cache: Caches analysis results
  - wicked-mem: Stores learnings across sessions
---
```

### Phase Enhancement

Specialist skills declare which phases they enhance in `specialist.json`:

```json
{
  "enhances": [
    {
      "phase": "qe",
      "trigger": "crew:phase:started:success",
      "response": "qe:analysis:completed:success",
      "capabilities": ["test_generation", "risk_analysis"]
    }
  ]
}
```

### Event-Aware Skills

Skills that publish or subscribe to events should document this:

```yaml
---
name: quality-analysis
description: |
  Analyzes code quality and generates test scenarios.

  Subscribes to:
  - crew:phase:started:success (qe phase)

  Publishes:
  - qe:analysis:completed:success
  - qe:risk:identified:warning
---
```

Event format: `[namespace:entity:action:status]`

### Persona Integration

Specialist skills work with persona agents. Reference personas in skill content:

```markdown
## Analysis Workflow

1. **Risk Assessor** identifies failure modes
2. **Test Strategist** generates test scenarios
3. **Code Analyzer** checks testability

See [agents/](../agents/) for persona definitions.
```

## Refactoring Over-Limit Skills

When a SKILL.md exceeds 200 lines:

1. **Identify sections**:
   - Keep: Overview, quick-start, common patterns
   - Move: Detailed API, examples, advanced config

2. **Create refs/ structure**:
   ```bash
   mkdir -p skills/my-skill/refs
   ```

3. **Extract detailed content**:
   - API documentation → `refs/api.md`
   - Examples → `refs/examples.md`
   - Advanced patterns → `refs/advanced.md`

4. **Add navigation in SKILL.md**:
   ```markdown
   ## Reference

   - [API Reference](refs/api.md) - Full API documentation
   - [Examples](refs/examples.md) - Usage patterns
   ```

5. **Verify limits**:
   ```bash
   wc -l skills/my-skill/SKILL.md  # Should be ≤200
   wc -l skills/my-skill/refs/*.md  # Each 200-300
   ```

## Example: Before and After

### Before (450 lines, monolithic)

```markdown
# Deployment Skill

[50 lines overview]
[100 lines Cloudflare docs]
[100 lines Vercel docs]
[100 lines Docker docs]
[100 lines Kubernetes docs]
```

### After (Progressive Disclosure)

**SKILL.md (120 lines)**:
```markdown
# Deployment Skill

Deploy to any platform with unified commands.

## Quick Start

[20 lines - immediate deployment]

## Platforms

- Cloudflare - See [refs/cloudflare.md](refs/cloudflare.md)
- Vercel - See [refs/vercel.md](refs/vercel.md)
- Containers - See [refs/containers.md](refs/containers.md)

## Common Patterns

[80 lines - 80% use cases]
```

**refs/cloudflare.md (200 lines)** - Cloudflare-specific details
**refs/vercel.md (180 lines)** - Vercel-specific details
**refs/containers.md (250 lines)** - Docker/K8s details

## Credits

Based on insights from [ClaudeKit Skills REFACTOR.md](https://github.com/mrgoonie/claudekit-skills/blob/main/REFACTOR.md).
