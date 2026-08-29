# Vendored: the domain-model governance schema

**Pinned copy — do not hand-edit.** This is a byte-for-byte vendored copy of the
canonical domain-model JSON Schema, so garden's modernize/domain extraction
skills can emit + validate documents **without importing owner code**. This is
the disjoint-build discipline the Domain-Brain contract mandates: the only thing
that crosses repo lines is a document that validates against this schema plus a
SymbolId string.

**Canonical source (the LIVE OWNER):**
`wicked-core/crates/wicked-governance/schemas/` — the governance schema bundle
was re-homed there (AW-2 / arch-R10, 2026-08) out of the retired **wicked-brain**
repo. `wicked-brain/schemas/` remains on disk as a frozen read-only archive; it
is history, not the contract.

| | |
|---|---|
| Bundle version (`VERSION`) | `1.1.0` — mirrors the owner's `schemas/VERSION` |
| Schema contract version (`$id` / `metadata.schema_version`) | `1.0.0` |
| Schema `$id` | `https://wickedagile.com/schemas/domain-model/1.0.0` |
| Canonical source | `wicked-core/crates/wicked-governance/schemas/domain-model.schema.json` |
| Draft | JSON Schema draft-07 |

## Two versions, deliberately

The **bundle** `VERSION` bumps when ANY schema in the owner's 4-file bundle
changes (the 1.0.0→1.1.0 bump was a coverage-schema change — this file was
untouched). The **contract version** a document carries (`metadata.schema_version`,
const-pinned by the schema, matching the `$id` segment) is independent — the
schemas document that independence themselves. Documents emitted here still carry
`schema_version: "1.0.0"`.

## Drift gate (the cross-repo CI sync check)

`tests/domain/test_schema_vendor_pin.py` enforces:

1. The schema's `metadata.schema_version` const matches its `$id` version
   segment (self-consistency of the vendored bytes).
2. The vendored schema is byte-identical to the owner copy, and the vendored
   `VERSION` equals the owner's `VERSION`, **whenever the owner is reachable** —
   as the sibling checkout `../wicked-core/crates/wicked-governance/schemas`, or
   via the `WICKED_SCHEMA_OWNER_DIR` env var (point CI at a checkout of
   wicked-core to make the check unconditional). When neither is present the
   compare skips gracefully — we never fail on the owner's absence, only on
   detected drift.

## Updating

Bump only by re-copying the canonical file from the owner at a known commit and
syncing `VERSION` to the owner's. A bundle bump is a semver event (additive
optional field = patch; new required field = minor; invariant change = major +
new `$id`). Never edit the JSON here directly.
