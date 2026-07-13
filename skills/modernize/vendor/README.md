# Vendored: `@wicked/domain-model-schema`

**Pinned copy — do not hand-edit.** This is a byte-for-byte vendored copy of the
canonical domain-model JSON Schema that lives in **wicked-brain** (the schema
owner), so garden's modernize extraction skills can emit + validate documents
**without importing brain code**. This is the disjoint-build discipline the
Domain-Brain contract mandates: the only thing that crosses repo lines is a
document that validates against this schema plus a SymbolId string.

| | |
|---|---|
| Package | `@wicked/domain-model-schema` |
| Version (`VERSION`) | `1.0.0` |
| Schema `$id` | `https://wickedagile.com/schemas/domain-model/1.0.0` |
| Canonical source | `wicked-brain/schemas/domain-model.schema.json` |
| Draft | JSON Schema draft-07 |

## Why vendored, not a dependency

`@wicked/domain-model-schema` is brain-owned and not yet published to a registry
garden pulls from. Per the contract (§1), JS/TS consumers *add it as a
dependency* once published; until then, garden **pins a vendored copy** and
gates drift with a byte-compare test — the same discipline estate (Rust) uses to
vendor its copy. `tests/modernize/test_schema_vendor_pin.py` enforces:

1. `VERSION` matches the version segment of the schema `$id`.
2. The vendored copy is byte-identical to `wicked-brain/schemas/…` **when that
   sibling repo is present** (skips gracefully in a repo-isolated checkout / CI
   where the sibling isn't checked out — we never fail on the sibling's absence,
   only on a detected drift).

## Updating

Bump only by re-copying the canonical file from brain at a known git tag and
updating `VERSION`. A version bump is a schema-bundle semver event (additive
optional field = patch; new required field = minor; invariant change = major +
new `$id`). Never edit the JSON here directly.
