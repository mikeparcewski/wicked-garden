# Extending the catalog — shipping a third-party pack

Garden is **the** catalog, not a closed product: the built-in domains follow a
naming contract anyone can follow, and the runtime discovers conformant
third-party **packs** without a garden PR. Your fintech-risk domain, your
games-QA fleet, your compliance cast — they sit beside the built-ins, under
the same evidence discipline.

This is the complete pack-author guide. Everything here is executable today;
the sections at the end state plainly which parts of the contract are still
minimal.

## What a pack is

A directory (npm package, git checkout, or plain folder) with:

```
acme-seo-pack/
├── wicked-pack.json                      # the manifest (see schema)
└── skills/
    ├── acme-seo/SKILL.md                 # ONE router per domain (user-invocable)
    ├── acme-seo-keyword-analyst/SKILL.md # fork worker (context: fork)
    ├── acme-seo-content-auditor/SKILL.md # fork worker (context: fork)
    └── acme-seo-content-auditor/refs/…   # tier-3 refs (optional)
```

Schema: [`schemas/wicked-pack.schema.json`](../schemas/wicked-pack.schema.json).
A complete working example (used as garden's own e2e fixture):
[`tests/fixtures/packs/acme-seo/`](../tests/fixtures/packs/acme-seo/).

### The manifest

```json
{
  "spec": 1,
  "name": "acme-seo",
  "vendor": "acme",
  "version": "0.1.0",
  "description": "ACME's SEO domain pack.",
  "skills_dir": "skills",
  "domains": [
    {
      "name": "seo",
      "specialist": {
        "role": "seo-engineering",
        "description": "SEO specialist — keyword strategy and evidence-backed audits.",
        "enhances": ["design", "build", "review"]
      },
      "produces": [
        { "archetype": "review", "produces": ["seo-audit"], "gate": "vault" }
      ]
    }
  ],
  "peers": { "wicked-garden": ">=12.0.0", "wicked-vault": ">=0.5.0" },
  "provenance": { "source": "https://github.com/acme/acme-seo-pack", "publisher": "acme" }
}
```

## The rules (the same ones the built-ins follow)

1. **One router per domain.** A single user-invocable skill named
   `{vendor}-{domain}` fronts the domain; sub-capabilities are *actions* of
   the router, never sibling top-level skills. ≤ 200-line body.
2. **Workers are `{vendor}-{domain}-{role}`** with `context: fork` in
   frontmatter — isolated subagent contexts with their own tool boundaries.
3. **Your prefix is your vendor name.** `wicked-*` (and `wicked-garden-*`)
   is reserved for the first-party catalog; the conformance gate rejects
   squatting, and the resolver indexes garden first so a pack can never
   shadow a first-party name.
4. **kebab-case, ≤ 64 chars; three-tier disclosure** — frontmatter ~100
   words, SKILL.md ≤ 200 lines (fork workers exempt — they load into an
   isolated context), refs/ 200–300 lines each.
5. **NOT-THIS-WHEN reciprocity.** If two of your skills are twins
   (executor vs advisor), each names the other in a `NOT THIS WHEN:` block —
   the gate enforces reciprocity inside your pack.
6. **Evidence via vault.** Your pack's "done" goes through the same gate:
   record evidence with `wicked-vault record … --actor <doer>` and let the
   produces-gate re-derive it. A pack never ships its own gate logic
   (`"gate": "vault"` is the only backend).
7. **Events** (if you emit them): 4-segment
   `wicked.<domain>.<noun>.<past-verb>` — bus SPEC.md is the authority.

## Validate: the shipped conformance gate

```bash
npx wicked-garden pack check ./acme-seo-pack          # human output
npx wicked-garden pack check ./acme-seo-pack --json   # CI
```

Exit 0 = conformant (warnings allowed), 1 = errors. The gate checks the
manifest, router/worker shape, naming, disclosure tiers, NOT-THIS-WHEN
reciprocity, produces contracts (archetype names must exist in garden's
catalog), and peer-floor syntax — rule codes PK001–PK050, each with an
actionable message. It runs anywhere Python ≥ 3.10 exists; no garden install
required (`scripts/pack/check.py` ships in the npm package).

## Install + register

Registration is what makes the runtime *see* the pack. Any of:

```bash
# acquire + install + validate + register in one step (wicked-installer —
# the same code path garden's own `pack install` delegates to):
npx wicked-installer pack add acme-seo-pack          # npm package name
npx wicked-installer pack add ./acme-seo-pack        # local directory

# or register an on-disk pack directly with garden:
npx wicked-garden pack register ./acme-seo-pack --source https://github.com/acme/acme-seo-pack

# see what the runtime sees:
npx wicked-garden pack list --json
npx wicked-garden pack unregister acme-seo
```

Registration is **fail-closed**: a pack that fails the conformance gate does
not register (`--force` exists, on your own head). Discovery itself also
picks packs up from, in priority order:

1. `WICKED_PACK_PATH` (pathsep-separated pack roots or dirs of packs),
2. the registered-pack file (`~/.something-wicked/wicked-garden/packs/registered.json`),
3. Claude Code plugin dirs (`~/.claude/plugins/*`, `~/.claude/plugins/cache/*/*`)
   containing a `wicked-pack.json`,
4. `<project>/.wicked/packs/*`.

So a pack shipped **as a Claude Code plugin** is discovered automatically —
the harness loads your skills, garden registers your routing. A pack that is
not a plugin needs its skills visible to the harness some other way
(`~/.claude/skills/`, which `wicked-installer pack add` handles for Claude
Code today).

## What registration gets you

- **Catalog**: `pack list` surfaces the pack, its domains, specialists,
  produces contracts, and provenance. No garden file is edited — 
  `components.json`/`specialist.json` stay first-party-only and the sync
  tooling ignores packs by design.
- **Crew routing** (the specialist seam): workers resolve through
  `scripts/crew/specialist_resolver.py` by full name
  (`acme-seo-keyword-analyst`), bare role (`keyword-analyst`), with the
  specialist domain `{vendor}-{domain}` (`acme-seo`). Specialist-engagement
  tracking (the SubagentStop hook) accepts pack domains that declare a
  `specialist` block.
- **Steering data**: declared `produces` contracts are validated and exposed
  (`_pack_registry.pack_produces()`); see honesty notes below.
- **Peer floors**: checked at SessionStart (cheap, fail-open) and on demand
  via `npx wicked-garden pack floors`.

## Honesty notes — where the contract is still minimal

The parts above are implemented and e2e-tested
(`tests/packs/test_e2e_toy_pack.py`). Three parts are deliberately minimal;
their current state, plainly:

**Trust & provenance (minimal).** Packs *declare* provenance; registration
*records* it plus a sha256 of the manifest and a content hash of the skills
tree. That detects post-registration drift — it does **not** prove
authorship. There is no signing, no central marketplace listing, and no
review process. Skills carry shell: **install packs only from sources you
trust**, exactly as you would an npm dependency. A signed/marketplace model
is future work (wicked-installer's `registry.json` is the named seam).

**Produces-contracts (data layer implemented; steering attach designed).**
Your declared produces are validated (PK040/PK041), surfaced in the catalog,
and the gate engine consumes a produces id directly — running
`loom gate <produces-id>` (i.e. `wicked-vault cross-check --phase seo-audit`)
against evidence your workers record works today, and your router should
instruct exactly that (see the fixture router). What does *not* happen yet:
the archetype steering engine (`scripts/crew/archetypes_v11.py`) does not
automatically append pack produces to an archetype's gate set when your
domain is engaged. That attach point is the named seam:
`archetypes_v11.steering_directives()` merging
`_pack_registry.pack_produces()` into each matched archetype's
`produces` list — filtered by *engaged* specialist domains (the
specialist-engagement ledger), because attaching unconditionally would
gate every `review` on every installed pack's contract. Until that
lands, pack gates are explicit-invocation, not auto-steered.

**Peer floors (implemented, deliberately fail-open).** Floors are syntax-
checked by the gate, compared at SessionStart against garden's own version
(zero subprocesses), and fully probed by `pack floors` (`--version` probes
for binary peers like `wicked-vault`). Violations *warn*; nothing blocks.
An unprobeable peer reports `unknown`, never a violation.

## Checklist before you publish

- [ ] `npx wicked-garden pack check .` exits 0
- [ ] every worker declares `context: fork`; the router does not
- [ ] evidence-writing workers record via `wicked-vault record … --actor <worker-name>`
- [ ] `peers` floors reflect what you actually tested against
- [ ] `provenance.source` points at the canonical repo
- [ ] ship `wicked-pack.json` at the package root (npm: include it in `files`)
