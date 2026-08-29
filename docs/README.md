# Wicked Garden Documentation

Detailed guides for getting the most out of wicked-garden.

Work in wicked-garden is organized around **9 work-shape archetypes** — not a fixed pipeline. Each prompt classifies into one or more archetypes (triage, explore, specify, decide, ship, review, incident, build, migrate); each owns its own phase shape, produces contract, and HITL discipline.

## Guides

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Installation, required peers, first session, common workflows |
| [Archetypes](v11/archetypes.md) | The 9 work-shape archetypes — why the universal pipeline went away |
| [Domains](domains.md) | The 10 domain skills archetypes invoke for expertise |
| [Required Peers](required-peers.md) | The five required peer plugins and the install/runtime stance |
| [The Compiler](compiler.md) | `/wicked-garden-prove compile` — emit a self-contained vault-backed gate into any repo |
| [Extending the Catalog](extending.md) | Ship a third-party pack — `{vendor}-{domain}-{role}` skills, the `wicked-pack.json` manifest, the shipped conformance gate, install + crew routing |
| [Brain Chunk Format](brain-chunk-format.md) | Historical: how content was chunked for the retired wicked-brain index (the migrated chunks in wicked-estate keep this shape) | <!-- historical -->

## Quick Links

- **New to wicked-garden?** Start with [Getting Started](getting-started.md).
- **Want to understand how work is shaped?** Read [Archetypes](v11/archetypes.md).
- **Setting up?** The [Required Peers](required-peers.md) — wicked-vault, wicked-estate, wicked-bus — are verified by `/wicked-garden-core setup` (the loom engine ships in-package; the qe domain is in-catalog).
- **Looking for domain expertise or a specific action?** Browse [Domains](domains.md).
- **Want a build gate that runs without wicked-garden present?** See [The Compiler](compiler.md).
- **Shipping your own domain pack?** Follow [Extending the Catalog](extending.md) — `npx wicked-garden pack check` validates it against the same rules the built-ins follow.

## Need Help?

```bash
/wicked-garden-core setup              # verify required peers + onboard
/wicked-garden-core help               # list all skills
/wicked-garden-core where-am-i         # show current session state
```
