"""The modernize extraction slice emits schema-conformant domain-model docs.

Validates the fixture + the live emitter output against the vendored
@wicked/domain-model-schema@1.0.0, and asserts the assembler enforces the HARD
invariants at build time (fail-closed) rather than emitting a malformed doc.

Disjoint-build discipline: this suite imports ONLY garden's own modernize slice
plus the vendored schema — no brain / estate / crew code.
"""

import json
from pathlib import Path

import pytest

from domain import _mocks
from domain.emit_domain_model import (
    EmitError,
    build_document,
    build_domain,
    build_requirement,
    build_rule,
    fixture_document,
)
from domain.validate_domain_model import (
    SCHEMA_PATH,
    load_schema,
    validate_document,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "skills" / "domain" / "refs" / "fixtures" / "example-domain-model.json"


def test_vendored_schema_is_present_and_draft07():
    schema = load_schema()
    assert schema["$schema"].startswith("http://json-schema.org/draft-07")
    assert schema["$id"] == "https://wickedagile.com/schemas/domain-model/1.0.0"
    assert schema["required"] == ["domains", "metadata"] or set(
        schema["required"]
    ) == {"domains", "metadata"}


def test_checked_in_fixture_conforms():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors = validate_document(doc)
    assert errors == [], f"checked-in fixture is non-conformant: {errors}"


def test_live_emitter_output_conforms():
    doc = fixture_document()
    errors = validate_document(doc)
    assert errors == [], f"emitter output non-conformant: {errors}"


def test_checked_in_fixture_matches_emitter():
    """The committed fixture must be exactly what the emitter produces."""
    on_disk = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert on_disk == fixture_document(), (
        "fixture drifted from emitter — regenerate with "
        "`python scripts/domain/emit_domain_model.py --fixture`"
    )


def test_fixture_exercises_reason_carrying_drop():
    doc = fixture_document()
    dunning = doc["domains"]["billing"]["requirements"]["REQ-BILL-DUNNING"]
    assert dunning["disposition"] == "drop"
    assert dunning["disposition_reason"], "a drop must carry a reason to be honored"


def test_every_business_rule_has_numeric_confidence_and_provenance():
    doc = fixture_document()
    for domain in doc["domains"].values():
        for req in domain["requirements"].values():
            assert len(req["business_rules"]) >= 1
            for rule in req["business_rules"]:
                assert isinstance(rule["confidence"], float)
                assert 0.0 <= rule["confidence"] <= 1.0
                prov = rule["provenance"]
                assert set(prov) >= {"source", "ref", "source_kinds"}
                assert prov["source_kinds"], "source_kinds names >= 1 grounding tier"


def test_facts_reference_symbolids_not_copies():
    doc = fixture_document()
    for domain in doc["domains"].values():
        for req in domain["requirements"].values():
            for comp in req["legacy_components"]:
                assert comp.startswith("sym::"), f"not a SymbolId reference: {comp}"
                assert "\n" not in comp


# --- fail-closed assembler invariants ---------------------------------------

def test_rule_rejects_non_numeric_confidence():
    with pytest.raises(EmitError, match="confidence must be a number"):
        build_rule("RULE-001", "x", True, "s", "sym::a::b", ["code-body"])


def test_rule_rejects_out_of_range_confidence():
    with pytest.raises(EmitError, match="out of"):
        build_rule("RULE-001", "x", 1.5, "s", "sym::a::b", ["code-body"])


def test_rule_rejects_bad_id_pattern():
    with pytest.raises(EmitError, match="must match"):
        build_rule("R-1", "x", 0.5, "s", "sym::a::b", ["code-body"])


def test_rule_rejects_unknown_source_kind():
    with pytest.raises(EmitError, match="unknown tiers"):
        build_rule("RULE-001", "x", 0.5, "s", "sym::a::b", ["hearsay"])


def test_requirement_rejects_zero_business_rules():
    with pytest.raises(EmitError, match="minItems 1"):
        build_requirement(
            title="t", description="d", legacy_components=["sym::a::b"],
            business_rules=[],
        )


def test_requirement_rejects_reasonless_drop():
    rule = build_rule("RULE-001", "x", 0.5, "s", "sym::a::b", ["code-body"])
    with pytest.raises(EmitError, match="disposition_reason"):
        build_requirement(
            title="t", description="d", legacy_components=["sym::a::b"],
            business_rules=[rule], disposition="drop",
        )


def test_requirement_rejects_dangling_error_ref():
    rule = build_rule("RULE-001", "x", 0.5, "s", "sym::a::b", ["code-body"])
    with pytest.raises(EmitError, match="round-trip"):
        build_requirement(
            title="t", description="d", legacy_components=["sym::a::b"],
            business_rules=[rule],
            validations=[{"id": "VAL-001", "statement": "v", "error_ref": "ERR-099"}],
        )


def test_document_rejects_bad_migration_mode():
    rule = build_rule("RULE-001", "x", 0.5, "s", "sym::a::b", ["code-body"])
    req = build_requirement(
        title="t", description="d", legacy_components=["sym::a::b"],
        business_rules=[rule],
    )
    domain = build_domain(requirements={"REQ-1": req}, entities={})
    with pytest.raises(EmitError, match="migration_mode"):
        build_document({"d": domain}, migration_mode="sideways")


# --- validator catches what the schema alone cannot -------------------------

def test_validator_rejects_unknown_schema_version():
    doc = fixture_document()
    doc["metadata"]["schema_version"] = "9.9.9"
    errors = validate_document(doc)
    assert any("no validator" in e for e in errors)


def test_validator_flags_embedded_code_copy_in_reference():
    doc = fixture_document()
    req = doc["domains"]["billing"]["requirements"]["REQ-BILL-LATEFEE"]
    req["legacy_components"].append("def calc():\n    return amount * 0.015\n")
    errors = validate_document(doc)
    assert any("embedded copy" in e for e in errors)


def test_validator_flags_duplicate_ids_within_requirement():
    doc = fixture_document()
    req = doc["domains"]["billing"]["requirements"]["REQ-BILL-LATEFEE"]
    # two rules already RULE-001/002; force a collision on a validation id
    req["validations"].append({"id": "VAL-001", "statement": "dup"})
    errors = validate_document(doc)
    assert any("duplicate id" in e for e in errors)


# --- the stdlib schema layer has teeth (rejects malformed docs) -------------
# The schema layer is a stdlib-only draft-07 subset validator (no jsonschema —
# the repo is stdlib+pytest only). These prove it actually validates against the
# vendored schema, resolving $ref/if-then, not just rubber-stamps every doc.


def _mutate(mutator):
    doc = fixture_document()
    mutator(doc)
    return validate_document(doc)


def test_schema_layer_rejects_missing_required_field():
    errs = _mutate(
        lambda d: d["domains"]["billing"]["requirements"]["REQ-BILL-CLOSE"].pop("title")
    )
    assert any("missing required property 'title'" in e for e in errs)


def test_schema_layer_rejects_bad_enum():
    errs = _mutate(
        lambda d: d["domains"]["billing"]["requirements"]["REQ-BILL-CLOSE"].__setitem__(
            "disposition", "maybe"
        )
    )
    assert any("is not one of" in e for e in errs)


def test_schema_layer_rejects_empty_business_rules():
    errs = _mutate(
        lambda d: d["domains"]["payments"]["requirements"]["REQ-PAY-CHARGE"].__setitem__(
            "business_rules", []
        )
    )
    assert any("minItems 1" in e for e in errs)


def test_schema_layer_rejects_out_of_range_confidence():
    errs = _mutate(
        lambda d: d["domains"]["payments"]["requirements"]["REQ-PAY-CHARGE"][
            "business_rules"
        ][0].__setitem__("confidence", 1.7)
    )
    assert any("maximum" in e for e in errs)


def test_schema_layer_rejects_additional_property():
    errs = _mutate(
        lambda d: d["domains"]["payments"]["requirements"]["REQ-PAY-CHARGE"][
            "business_rules"
        ][0].__setitem__("bogus", "x")
    )
    assert any("additional property" in e for e in errs)


def test_schema_layer_enforces_disposition_drop_conditional():
    """if/then: a drop that loses its reason must fail the schema layer itself."""
    errs = _mutate(
        lambda d: d["domains"]["billing"]["requirements"]["REQ-BILL-DUNNING"].pop(
            "disposition_reason"
        )
    )
    assert any("disposition_reason" in e for e in errs)


def test_schema_layer_rejects_bad_source_kind_enum_via_ref():
    """Exercises $ref resolution into provenance.source_kinds[].enum."""
    errs = _mutate(
        lambda d: d["domains"]["payments"]["requirements"]["REQ-PAY-CHARGE"][
            "business_rules"
        ][0]["provenance"].__setitem__("source_kinds", ["hearsay"])
    )
    assert any("is not one of" in e for e in errs)


# --- the disjoint mock seam --------------------------------------------------

def test_estate_mock_refuses_bare_name_write():
    estate = _mocks.EstateClient()
    with pytest.raises(ValueError, match="silent no-op"):
        estate.set_requirement("Invoice.close", "REQ-BILL-CLOSE", True)


def test_estate_mock_resolves_ambiguous_name_to_multiple_symbolids():
    estate = _mocks.EstateClient()
    hits = estate.resolve("Charge")
    assert len(hits) >= 2, "ambiguous names resolve to multiple SymbolIds"
    assert all(h.startswith("sym::") for h in hits)


def test_brain_mock_builds_from_conformant_doc_and_counts_drops():
    brain = _mocks.BrainClient()
    summary = brain.build_domain_graph(fixture_document())
    assert summary["domains"] == 2
    assert summary["dropped"] == 1


def test_brain_mock_refuses_nonconformant_doc():
    brain = _mocks.BrainClient()
    with pytest.raises(ValueError, match="non-conformant"):
        brain.build_domain_graph({"metadata": {}, "domains": {}})


# --- type-guard regression tests (garden#990 / garden#992 fixes) -------

def test_build_requirement_non_dict_business_rule_raises_emit_error():
    """_assert_unique_ids must raise EmitError for non-dict items, not crash."""
    with pytest.raises(EmitError, match="must be a dict"):
        build_requirement(
            title="T", description="D",
            legacy_components=["C"],
            business_rules=["oops"],  # non-dict item in list
        )


def test_validate_document_non_list_business_rules_does_not_crash():
    """validate_document used to crash with AttributeError when business_rules
    was a non-list value (e.g. 42).  The type-guard fix skips it; schema
    errors are returned instead."""
    doc = fixture_document()
    domain_key = next(iter(doc["domains"]))
    req_key = next(iter(doc["domains"][domain_key]["requirements"]))
    doc["domains"][domain_key]["requirements"][req_key]["business_rules"] = 42
    errors = validate_document(doc)
    assert isinstance(errors, list)  # no AttributeError, just schema errors
