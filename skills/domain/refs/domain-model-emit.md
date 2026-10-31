# domain-model-emit — the field map + hard invariants

The document every modernize worker emits validates against
`vendor/domain-model.schema.json` — the vendored, pinned
`@wicked/domain-model-schema@1.1.0` (every 1.0.0 document stays valid). This ref is the human-readable map of that
schema. The schema is authoritative; where this doc and the schema disagree, the
schema wins.

## Top-level shape

```json
{
  "metadata": {
    "schema_version": "1.1.0",          // "1.0.0" or "1.1.0"; 1.1.0 adds the optional fields below
    "coverage": {                       // optional (1.1.0): the share mapped, set by core's build
      "mapped_pct": 82, "min_pct": 80, "behavior_bearing": 500,
      "mapped": 410, "resolved": 380, "unmapped": 90
    },
    "migration_mode": "functional",     // functional (capability-grouped, default) | structural (1:1)
    "source": "acme-billing-legacy"     // optional: the repo/service mined
  },
  "domains": {
    "<domain-slug>": { "...": "Domain" }
  }
}
```

`required: ["domains", "metadata"]`.

## Domain

`required: ["requirements", "entities"]`.

```json
{
  "description": "Billing and invoice lifecycle",   // optional human label
  "cluster_id": 3,                                    // optional — advisory Louvain index, NOT authoritative
  "requirements": { "<req-id>": { "...": "Requirement" } },
  "entities":     { "<EntityName>": { "...": "Entity" } }
}
```

## Requirement — the heart

`required: ["title","description","legacy_components","data_access","dependencies","business_rules","validations","error_paths"]`.

| Field | Type | Rule |
|---|---|---|
| `title`, `description` | string | required |
| `legacy_components` | string[] | required, **non-null, never dropped**. The estate SymbolIds / node names this requirement covers. A **reference**, not a copy. (Synonym in prose: `source_components`.) |
| `data_access` | string[] | required. Table/collection/store names touched. |
| `dependencies` | string[] | required. Other requirement ids / external services. |
| `business_rules` | Rule[] | required, **minItems 1** (HARD). Zero rules ⇒ mark the requirement `status:"unresolvable"` with a reason instead. |
| `validations` | Validation[] | required (may be empty). |
| `error_paths` | ErrorPath[] | required (may be empty). |
| `status` | enum | `active \| review \| unresolvable` |
| `disposition` | enum | `keep \| modify \| drop \| new` (HARD) |
| `disposition_reason` | string | **MANDATORY when `disposition == "drop"`** (schema if/then). A reason-less drop is NOT honored by the coverage gate. |
| `merged_programs` | string[] | optional |
| `corroboration` | object | optional (1.1.0), **computed by core, never asserted by a worker**: `{status: validated\|unconfirmed, sources, call_sites, tests, docs, extra_extractors, why?: {code, text}}`. `validated` at 2+ independent sources; `unconfirmed` carries why (`unindexed_file`, `dead_code`, `config_only`, `single_caller`, `test_only`, `doc_only`, `extractors_only`). |

## Rule (`business_rules[]`) — `required: ["id","statement","confidence","provenance"]`

```json
{
  "id": "RULE-001",                       // ^RULE-[0-9]{3,6}$, unique within the requirement
  "statement": "Invoices past 30 days accrue a 1.5% late fee",
  "confidence": 0.82,                     // REQUIRED number in [0,1] (HARD — ISS-11). Non-numeric = failure.
  "provenance": {
    "source": "acme-billing-legacy",      // repo / service / module
    "ref": "sym::billing::LateFee.calc",  // file#anchor OR estate SymbolId — a reference, never a copy
    "source_kinds": ["code-body"]         // ⊆ {code-body, type-def, comment, doc}
  },
  "source_ref": "src/billing/fees.cbl#L120"  // optional
}
```

**Trust rule:** a rule is *trusted* only when grounded in `code-body` and/or
`type-def`. Resting on `comment`/`doc` alone makes it RISK-eligible — the
antagonist flags it.

## Validation / ErrorPath — object-only

- **Validation** `required: ["id","statement"]`; `id ^VAL-[0-9]{3,6}$`; optional
  `field`, `error_ref ^ERR-[0-9]{3,6}$` (intra-requirement join to an ErrorPath —
  the round-trip check), optional `confidence`, optional `provenance`.
- **ErrorPath** `required: ["id","statement"]`; `id ^ERR-[0-9]{3,6}$`; optional
  `code` (status/return code), optional `confidence`, optional `provenance`.

Confidence + provenance are **optional** on validations/error-paths (unlike
business rules, where both are HARD-required).

## Entity — `required: ["description","fields"]`

```json
{
  "description": "A customer invoice",
  "fields": [
    { "name": "invoice_id", "type": "string", "description": "Unique invoice key" },
    { "name": "amount_due", "type": "decimal", "description": "Outstanding balance" }
  ]
}
```

Each field is `required: ["name","type","description"]`.

## The seven hard invariants (the cross-review checklist)

These are what the assembler enforces at build time and the validator re-checks —
a document that violates any is non-conformant and crew's cross-product review
fails:

1. `domains` is required; every domain has `requirements` **and** `entities`.
2. `business_rules.minItems == 1` per requirement.
3. Every business rule carries **numeric `confidence ∈ [0,1]`** **and**
   `provenance{source, ref, source_kinds}`.
4. `disposition ∈ {keep, modify, drop, new}`; a `drop` needs a
   `disposition_reason` to be honored by coverage.
5. A domain fact stores a **SymbolId reference**, never a copy of symbol
   structure; estate is the only writer of graph structure.
6. Miner kind-sets are config-driven (`config.coverage.*`), never hardcoded —
   the same schema serves a COBOL estate and a Rust monorepo.
7. All artifacts share one bundle semver; every document declares
   `metadata.schema_version`; a consumer rejects an unknown version rather than
   best-efforting it.

## The SymbolId reference rule (invariant 5, expanded)

A domain fact stores an estate **`SymbolId`** reference in `legacy_components[]`
and `provenance.ref` — the stable interned identity, **never** a content-hash,
file, line, or a copy of the symbol's code. This is why the reference survives a
rename or reindex: names are not unique (a legacy `MAIN-PARA` may appear ×21),
the SymbolId is. To render a rule's code, a consumer calls estate live
(`source <symbol_id>`) — the document never carries the body.
