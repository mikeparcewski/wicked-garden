# Vendored: the domain-model governance schema

**Pinned copy — do not hand-edit.** This is a byte-for-byte vendored copy of the
canonical domain-model JSON Schema, so garden's modernize/domain extraction
skills can emit + validate documents **without importing owner code**. This is
the disjoint-build discipline the Domain-Brain contract mandates: the only thing
that crosses repo lines is a document that validates against this schema plus a
SymbolId string.

**Canonical source (the LIVE OWNER):**
`wicked-core/crates/wicked-governance/schemas/` — the governance schema bundle
was re-homed there (AW-2 / arch-R10, 2026-08) out of the retired **wicked-brain** <!-- historical -->
repo. `wicked-brain/schemas/` remains on disk as a frozen read-only archive; it <!-- historical -->
is history, not the contract.

| | |
|---|---|
| Bundle version (`VERSION`) | `1.4.0` — mirrors the owner's `schemas/VERSION` (re-vendored 2026-11-25 from wicked-core#1922, J6 C2: domain-model 1.2.0, the J6 v3 model of checked statements, rule groups, follow-ups and targets; 1.3.2 was the optional boolean `metadata.product_only`, wicked-core#1697; 1.3.1 the business domains; 1.3.0 the real-requirements `metadata.coverage`, #1233) |
| Schema contract version (`$id` / `metadata.schema_version`) | `1.2.0` (accepts `1.0.0`, `1.1.0` and `1.2.0`) |
| Schema `$id` | `https://wickedagile.com/schemas/domain-model/1.2.0` |
| Canonical source | `wicked-core/crates/wicked-governance/schemas/domain-model.schema.json` |
| Draft | JSON Schema draft-07 |

## Two versions, deliberately

The **bundle** `VERSION` bumps when ANY schema in the owner's 4-file bundle
changes (the 1.0.0→1.1.0 bump added `conformance-rules.schema.json` to the
bundle; the 1.1.0→1.2.0 bump was the STEERING unification's optional fields on
`conformance-rules.schema.json`; the 1.2.0→1.2.1 bump was conformance-rules 1.2.0's
optional DC-S1 project-rule fields, wicked-core#699 — this file was byte-untouched
every time until 1.2.2→1.2.3, domain-model 1.1.0's optional `metadata.coverage` and
`requirement.corroboration`). The
**contract version** a document carries (`metadata.schema_version`,
an enum since 1.1.0 whose newest entry matches the `$id` segment) is independent —
the schemas document that independence themselves. Garden emits no document of its own since
J6 v3 (it writes the store); core's `domain-graph` emits `1.2.0`, and `1.1.0` behind
`--schema-version 1.1.0` until it is deleted.

## Drift gate (the cross-repo CI sync check)

`tests/domain/test_schema_vendor_pin.py` enforces:

1. The schema's `metadata.schema_version` const matches its `$id` version
   segment (self-consistency of the vendored bytes).
2. The vendored schema is byte-identical to the owner copy, and the vendored
   `VERSION` equals the owner's `VERSION`, **whenever the owner is reachable** —
   as a sibling `wicked-core` checkout beside this plugin root (its `crates/wicked-governance/schemas` directory), or
   via the `WICKED_SCHEMA_OWNER_DIR` env var (point CI at a checkout of
   wicked-core to make the check unconditional). When neither is present the
   compare skips gracefully — we never fail on the owner's absence, only on
   detected drift.

## Updating

Bump only by re-copying the canonical file from the owner at a known commit and
syncing `VERSION` to the owner's. A bundle bump is a semver event (additive
optional field = patch; new required field = minor; invariant change = major +
new `$id`). Never edit the JSON here directly.
