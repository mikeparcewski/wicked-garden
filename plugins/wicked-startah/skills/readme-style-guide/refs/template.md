# README Template

Annotated template for Wicked Garden plugin READMEs. Replace placeholders and remove comments before use.

---

```markdown
# wicked-{name}

<!-- TAGLINE: One sentence. Specific differentiating claim. No category labels. -->
{What this plugin does differently, stated as a concrete outcome.}

<!-- CONDITIONAL: Include only if core value requires multiple invocations to be visible.
     Examples: wicked-jam (decision lifecycle), wicked-mem (memory building over sessions).
     Omit for: wicked-engineering (one review = immediate value). -->
## {Lifecycle Title — varies by plugin}

{10-20 lines max. Show the compound value arc over time.
 Use a narrative flow or before/after contrast.}

## Quick Start

```bash
# Install
claude plugins add something-wicked/wicked-{name}

# {Label: first win — simplest useful command}
/wicked-{name}:{command} {example args}

# {Label: most common use case}
/wicked-{name}:{command} {example args}
```

<!-- WORKFLOWS: 2-3 real scenarios. Each has: heading, code block, optional output.
     This section appears BEFORE the Commands table.
     Workflows persuade; Commands reference. -->
## {Workflow Title}

### {Scenario 1 Name}

```bash
# Step-by-step real scenario
/wicked-{name}:{cmd1} {args}
/wicked-{name}:{cmd2} {args}
```

<!-- Show real output when possible -->
```
{Example output the user would actually see}
```

### {Scenario 2 Name}

```bash
/wicked-{name}:{cmd} {args}
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-{name}:{cmd}` | {Active-voice description} | `/wicked-{name}:{cmd} {args}` |

<!-- CONDITIONAL: Include when 3+ commands have overlapping scope.
     Place immediately after Commands table. -->
## When to Use What

| Command | Use When |
|---------|----------|
| `/wicked-{name}:{cmd1}` | {Trigger condition — when this is the right choice} |
| `/wicked-{name}:{cmd2}` | {Trigger condition — when this is the right choice} |

<!-- CONDITIONAL: Include only when the internal mechanism IS the value proposition.
     Examples: wicked-mem decay math, wicked-smaht routing tiers, wicked-crew signal scoring.
     Omit when: mechanism is just implementation detail. -->
## How It Works

{Explain the mechanism with diagrams or tables.
 Only include if understanding HOW it works helps users get more value.}

<!-- Include if plugin has agents. Merge with Skills if combined rows ≤5. -->
## Agents

| Agent | Role | Invoked By |
|-------|------|------------|
| `{agent-name}` | {What it does} | {Which commands use it, or "crew dispatch"} |

<!-- Include if plugin has skills. Merge with Agents if combined rows ≤5. -->
## Skills

| Skill | Purpose |
|-------|---------|
| `/wicked-{name}:{skill}` | {What it provides} |

<!-- CONDITIONAL: Required if plugin has wicked.json with data sources. -->
## Data API

Exposes data via the wicked-workbench gateway:

| Source | Verbs | Description |
|--------|-------|-------------|
| `{source}` | list, search, stats | {What data this exposes} |

## Integration

Works standalone. Enhanced with:

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| `wicked-{x}` | **{Specific capability enabled}** | {What happens without it — be honest and specific} |

## License

MIT
```
