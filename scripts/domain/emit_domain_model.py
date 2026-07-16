#!/usr/bin/env python3
"""emit_domain_model — the deterministic domain-model assembler.

This is the modernize extractor's **deterministic core** (the piece that is real
code in PHASE-1). It takes:

  - extracted rules (the LLM rule-statement step is INJECTED as input — that is
    the stubbed seam), and
  - an ``EstateClient`` (mocked in PHASE-1) that resolves node names to SymbolId
    references,

and assembles a document that validates against
``skills/domain/vendor/domain-model.schema.json`` (@wicked/domain-model-schema
@1.0.0), enforcing the HARD invariants at build time so a malformed document can
never be emitted:

  * every requirement has >= 1 business rule;
  * every business rule carries a numeric confidence in [0,1] and a
    provenance{source, ref, source_kinds};
  * a disposition == "drop" carries a disposition_reason;
  * ids match RULE-/VAL-/ERR- + 3..6 digits and are unique within a requirement;
  * facts reference SymbolId strings — the assembler never embeds code/file/line;
  * metadata.schema_version == "1.0.0".

Usage:
    emit_domain_model.py --fixture            # print a conformant fixture doc
    emit_domain_model.py --fixture --validate # ... and self-validate it

Stdlib only (the --validate path uses the stdlib schema validator in
``validate_domain_model.py`` — no third-party dependency).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = "1.0.0"

_RULE_ID = re.compile(r"^RULE-[0-9]{3,6}$")
_VAL_ID = re.compile(r"^VAL-[0-9]{3,6}$")
_ERR_ID = re.compile(r"^ERR-[0-9]{3,6}$")
_SOURCE_KINDS = {"code-body", "type-def", "comment", "doc"}
_DISPOSITIONS = {"keep", "modify", "drop", "new"}
_STATUSES = {"active", "review", "unresolvable"}
_MIGRATION_MODES = {"structural", "functional"}

# Config-driven miner kind-sets (invariant 6) — generic modern defaults. A
# conformant emitter reads these from config.coverage.*, never hardcodes them as
# a domain signal. Exposed so a caller can pass a COBOL/mainframe config.
DEFAULT_COVERAGE_CONFIG: dict[str, list[str]] = {
    "behavior_kinds": ["module", "function", "method"],
    "type_kinds": ["class", "interface", "struct", "trait", "enum", "record"],
    "structural_kinds": ["field", "variable"],
    "estate_behavior_kinds": [],
}


class EmitError(ValueError):
    """A hard-invariant violation caught at assembly time (fail-closed)."""


def build_provenance(source: str, ref: str,
                     source_kinds: Sequence[str]) -> dict[str, Any]:
    if not source:
        raise EmitError("provenance.source is required and must be non-empty")
    if not ref:
        raise EmitError("provenance.ref is required and must be non-empty")
    kinds = list(source_kinds)
    if not kinds:
        raise EmitError("provenance.source_kinds must name >= 1 grounding tier")
    bad = [k for k in kinds if k not in _SOURCE_KINDS]
    if bad:
        raise EmitError(f"provenance.source_kinds has unknown tiers: {bad}")
    return {"source": source, "ref": ref, "source_kinds": kinds}


def build_rule(rule_id: str, statement: str, confidence: float,
               source: str, ref: str, source_kinds: Sequence[str],
               source_ref: str | None = None) -> dict[str, Any]:
    if not _RULE_ID.match(rule_id):
        raise EmitError(f"rule id {rule_id!r} must match ^RULE-[0-9]{{3,6}}$")
    if not statement:
        raise EmitError(f"{rule_id}: statement must be non-empty")
    # bool is not a valid confidence (ISS-11 — numeric only).
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise EmitError(f"{rule_id}: confidence must be a number, got {confidence!r}")
    if not (0.0 <= float(confidence) <= 1.0):
        raise EmitError(f"{rule_id}: confidence {confidence} out of [0,1]")
    rule: dict[str, Any] = {
        "id": rule_id,
        "statement": statement,
        "confidence": float(confidence),
        "provenance": build_provenance(source, ref, source_kinds),
    }
    if source_ref is not None:
        rule["source_ref"] = source_ref
    return rule


def build_requirement(*, title: str, description: str,
                      legacy_components: Sequence[str],
                      business_rules: Sequence[dict[str, Any]],
                      data_access: Sequence[str] = (),
                      dependencies: Sequence[str] = (),
                      validations: Sequence[dict[str, Any]] = (),
                      error_paths: Sequence[dict[str, Any]] = (),
                      status: str | None = None,
                      disposition: str | None = None,
                      disposition_reason: str | None = None,
                      merged_programs: Sequence[str] | None = None) -> dict[str, Any]:
    if legacy_components is None:
        raise EmitError("legacy_components is non-null and must never be dropped")
    if len(business_rules) < 1:
        raise EmitError(
            "a requirement needs >= 1 business rule (minItems 1); a rule-less "
            "requirement must instead be status 'unresolvable' with a reason"
        )
    # id uniqueness within the requirement (schema can't express this).
    _assert_unique_ids(business_rules, validations, error_paths)
    # round-trip: every validation.error_ref points at an ErrorPath in-req.
    err_ids = {e["id"] for e in error_paths}
    for v in validations:
        ref = v.get("error_ref")
        if ref is not None and ref not in err_ids:
            raise EmitError(
                f"validation {v['id']} error_ref {ref} has no matching ErrorPath "
                "in this requirement (round-trip check)"
            )
    if status is not None and status not in _STATUSES:
        raise EmitError(f"status {status!r} not in {sorted(_STATUSES)}")
    if disposition is not None and disposition not in _DISPOSITIONS:
        raise EmitError(f"disposition {disposition!r} not in {sorted(_DISPOSITIONS)}")
    if disposition == "drop" and not disposition_reason:
        raise EmitError(
            "disposition 'drop' requires a disposition_reason — a reason-less "
            "drop is not honored by the coverage gate"
        )
    req: dict[str, Any] = {
        "title": title,
        "description": description,
        "legacy_components": list(legacy_components),
        "data_access": list(data_access),
        "dependencies": list(dependencies),
        "business_rules": list(business_rules),
        "validations": list(validations),
        "error_paths": list(error_paths),
    }
    if status is not None:
        req["status"] = status
    if disposition is not None:
        req["disposition"] = disposition
    if disposition_reason is not None:
        req["disposition_reason"] = disposition_reason
    if merged_programs is not None:
        req["merged_programs"] = list(merged_programs)
    return req


def build_entity(description: str,
                 fields: Sequence[dict[str, str]]) -> dict[str, Any]:
    for f in fields:
        missing = {"name", "type", "description"} - set(f)
        if missing:
            raise EmitError(f"entity field missing {sorted(missing)}: {f}")
    return {"description": description, "fields": [dict(f) for f in fields]}


def build_domain(*, requirements: dict[str, dict[str, Any]],
                 entities: dict[str, dict[str, Any]],
                 description: str | None = None,
                 cluster_id: int | None = None) -> dict[str, Any]:
    domain: dict[str, Any] = {"requirements": requirements, "entities": entities}
    if description is not None:
        domain["description"] = description
    if cluster_id is not None:
        if isinstance(cluster_id, bool) or not isinstance(cluster_id, int):
            raise EmitError(f"cluster_id must be an integer, got {cluster_id!r}")
        domain["cluster_id"] = cluster_id
    return domain


def build_document(domains: dict[str, dict[str, Any]], *,
                   migration_mode: str = "functional",
                   source: str | None = None) -> dict[str, Any]:
    if not domains:
        raise EmitError("a document requires >= 1 domain")
    if migration_mode not in _MIGRATION_MODES:
        raise EmitError(f"migration_mode {migration_mode!r} not in {sorted(_MIGRATION_MODES)}")
    metadata: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "migration_mode": migration_mode,
    }
    if source is not None:
        metadata["source"] = source
    return {"metadata": metadata, "domains": domains}


def _assert_unique_ids(*groups: Sequence[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                raise EmitError(
                    f"every business_rule / validation / error_path must be a dict, "
                    f"got {type(item).__name__}"
                )
            # Fail closed with an actionable EmitError rather than a raw KeyError
            # (contract: the assembler never leaks bare exceptions). Runs before
            # the round-trip check, so every later item['id'] access is guarded too.
            rid = item.get("id")
            if rid is None:
                raise EmitError("every business_rule / validation / error_path needs an 'id'")
            if rid in seen:
                raise EmitError(f"duplicate id {rid} within a requirement")
            seen.add(rid)


# --- fixture (mocks estate + injected rules) --------------------------------

def fixture_document() -> dict[str, Any]:
    """A conformant two-domain fixture, built through the mocked EstateClient.

    Mirrors what the extractor + translator would emit: SymbolId references
    resolved via the mock, injected rules with confidence + provenance, a
    reason-carrying 'drop', and cluster_id advisory provenance.
    """
    from domain._mocks import EstateClient  # local import: mocks are test-only

    estate = EstateClient()
    src = "acme-billing-legacy"

    def sym(name: str) -> str:
        hits = estate.resolve(name)
        if not hits:
            raise EmitError(f"fixture: unresolved node {name!r}")
        return hits[0]

    # --- billing domain (cluster 0) ---
    late_fee = build_requirement(
        title="Assess late fee on overdue invoices",
        description="Invoices unpaid past the grace window accrue a late fee.",
        legacy_components=[sym("Invoice.assessLateFee"), sym("LateFee.calc")],
        data_access=["invoices", "fee_schedule"],
        dependencies=["REQ-BILL-CLOSE"],
        business_rules=[
            build_rule(
                "RULE-001",
                "Invoices more than 30 days overdue accrue a 1.5% monthly late fee.",
                0.86, src, sym("LateFee.calc"), ["code-body"],
                source_ref="src/billing/late_fee.py#L40",
            ),
            build_rule(
                "RULE-002",
                "The late fee is capped at 25% of the original invoice amount.",
                0.72, src, sym("LateFee.calc"), ["code-body", "comment"],
            ),
        ],
        validations=[
            {"id": "VAL-001", "statement": "Invoice amount must be positive.",
             "field": "amount_due", "error_ref": "ERR-001"},
        ],
        error_paths=[
            {"id": "ERR-001",
             "statement": "Reject fee assessment when amount_due <= 0.",
             "code": "422"},
        ],
        status="active",
        disposition="keep",
    )
    close_invoice = build_requirement(
        title="Close a fully-paid invoice",
        description="An invoice with zero balance transitions to closed.",
        legacy_components=[sym("Invoice.close")],
        data_access=["invoices"],
        dependencies=[],
        business_rules=[
            build_rule(
                "RULE-001",
                "An invoice closes automatically once amount_due reaches zero.",
                0.91, src, sym("Invoice.close"), ["code-body", "type-def"],
            ),
        ],
        status="active",
        disposition="modify",
    )
    # A reason-carrying drop — honored by the coverage gate.
    legacy_dunning = build_requirement(
        title="Nightly paper dunning letter batch",
        description="Legacy overnight batch printed paper overdue notices.",
        legacy_components=[sym("Charge")],  # ambiguous name -> resolved SymbolId
        data_access=["invoices"],
        dependencies=[],
        business_rules=[
            build_rule(
                "RULE-001",
                "Overdue invoices generated a mailed paper dunning letter nightly.",
                0.64, src, sym("Charge"), ["doc"],
            ),
        ],
        status="review",
        disposition="drop",
        disposition_reason="Paper dunning is replaced by the email notification "
                           "service in the target; no parity obligation.",
    )
    billing = build_domain(
        description="Billing and invoice lifecycle",
        cluster_id=0,
        requirements={
            "REQ-BILL-LATEFEE": late_fee,
            "REQ-BILL-CLOSE": close_invoice,
            "REQ-BILL-DUNNING": legacy_dunning,
        },
        entities={
            "Invoice": build_entity(
                "A customer invoice.",
                [
                    {"name": "invoice_id", "type": "string",
                     "description": "Unique invoice key."},
                    {"name": "amount_due", "type": "decimal",
                     "description": "Outstanding balance."},
                    {"name": "status", "type": "string",
                     "description": "open | closed | void."},
                ],
            ),
        },
    )

    # --- payments domain (cluster 1) ---
    charge = build_requirement(
        title="Charge a payment method",
        description="Authorize and capture a charge against a saved method.",
        legacy_components=[sym("Payment.charge")],
        data_access=["payments", "payment_methods"],
        dependencies=["REQ-BILL-LATEFEE"],
        business_rules=[
            build_rule(
                "RULE-001",
                "A charge is declined if the payment method is expired.",
                0.88, src, sym("Payment.charge"), ["code-body", "type-def"],
            ),
        ],
        validations=[
            {"id": "VAL-001", "statement": "Charge amount must be > 0.",
             "field": "amount"},
        ],
        error_paths=[
            {"id": "ERR-001", "statement": "Return DECLINED on expired method.",
             "code": "402"},
        ],
        status="active",
        disposition="keep",
    )
    payments = build_domain(
        description="Payment authorization and settlement",
        cluster_id=1,
        requirements={"REQ-PAY-CHARGE": charge},
        entities={
            "Payment": build_entity(
                "A payment attempt.",
                [
                    {"name": "payment_id", "type": "string",
                     "description": "Unique payment key."},
                    {"name": "amount", "type": "decimal",
                     "description": "Charged amount."},
                ],
            ),
        },
    )

    return build_document(
        {"billing": billing, "payments": payments},
        migration_mode="functional",
        source=src,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true",
                        help="emit the built-in conformant fixture document")
    parser.add_argument("--validate", action="store_true",
                        help="self-validate the emitted document before printing")
    args = parser.parse_args(argv)

    if not args.fixture:
        parser.error("PHASE-1 supports --fixture only (real estate/brain wiring "
                     "is the next phase); pass --fixture")

    doc = fixture_document()
    if args.validate:
        from domain.validate_domain_model import validate_document
        errors = validate_document(doc)
        if errors:
            for e in errors:
                sys.stderr.write(f"INVALID: {e}\n")
            return 1
    json.dump(doc, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    # Make ``modernize`` importable when run as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
