# Wicked Garden Documentation

Detailed guides for getting the most out of wicked-garden.

Work in wicked-garden is organized around **9 work-shape archetypes** — not a fixed pipeline. Each prompt classifies into one or more archetypes (triage, explore, specify, decide, ship, review, incident, build, migrate); each owns its own phase shape, produces contract, and HITL discipline.

## Guides

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation, required peers, first session, common workflows |
| [Archetypes](v11/archetypes.md) | The 9 work-shape archetypes — why the universal pipeline went away |
| [Domains](domains.md) | The 10 domain skill/agent families archetypes invoke for expertise |
| [Required Peers](required-peers.md) | The four required peer plugins and the install/runtime stance |
| [The Compiler](compiler.md) | `/wicked-garden:compile` — emit a self-contained vault-backed gate into any repo |
| [Brain Chunk Format](brain-chunk-format.md) | How wicked-garden content is chunked for the brain index |

## Quick Links

- **New to wicked-garden?** Start with [Getting Started](getting-started.md).
- **Want to understand how work is shaped?** Read [Archetypes](v11/archetypes.md).
- **Setting up?** The [Required Peers](required-peers.md) — wicked-testing, wicked-vault, wicked-brain, wicked-bus — are verified by `/wicked-garden:setup`.
- **Looking for domain expertise or a specific command?** Browse [Domains](domains.md).
- **Want a build gate that runs without wicked-garden present?** See [The Compiler](compiler.md).

## Need Help?

```bash
/wicked-garden:setup                   # verify required peers + onboard
/wicked-garden:help                    # list all commands
/wicked-garden:where-am-i              # show current session state
```
