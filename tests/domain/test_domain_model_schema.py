"""Garden's vendored domain-model schema and its stdlib validator, against real documents.

Two documents: the checked-in 1.0.0 example (``refs/fixtures/example-domain-model.json``), and a
1.2.0 model ``wicked-core domain-graph`` built from the store garden's own ``domain-run`` route wrote
(``refs/fixtures/core-1.2.0-mini-cobol.json``; its provenance is in ``refs/fixtures/README.md``). The
mutations prove the validator has teeth. Stdlib + pytest only: no brain / estate / crew code.
"""

import copy
import json
from pathlib import Path

from domain.validate_domain_model import load_schema, validate_document

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "skills" / "domain" / "refs" / "fixtures"
FIXTURE = FIXTURES / "example-domain-model.json"
CORE_V3 = FIXTURES / "core-1.2.0-mini-cobol.json"


def fixture_document():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def core_v3():
    return json.loads(CORE_V3.read_text(encoding="utf-8"))


def _rules(doc):
    return [r for d in doc["domains"].values() for q in d["requirements"].values() for r in q["business_rules"]]


def test_vendored_schema_is_present_and_draft07():
    schema = load_schema()
    assert schema["$schema"].startswith("http://json-schema.org/draft-07")
    assert schema["$id"] == "https://wickedagile.com/schemas/domain-model/1.2.0"
    assert schema["required"] == ["domains", "metadata"] or set(
        schema["required"]
    ) == {"domains", "metadata"}


def test_checked_in_fixture_conforms():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors = validate_document(doc)
    assert errors == [], f"checked-in fixture is non-conformant: {errors}"


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
                assert comp.startswith("sym synthetic "), f"not a SymbolId reference: {comp}"
                assert "\n" not in comp


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


# --- type-guard regression (garden#992) ---------------------------------------

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


def _core_1_1_doc():
    """The shape `wicked-core domain-graph` emits since the configurable coverage minimum."""
    rule = {"id": "RULE-001", "statement": "sum adds every element", "confidence": 0.9,
            "provenance": {"source": "code-graph", "ref": "src/math.js#sum",
                           "source_kinds": ["code-body"]}}
    req = {"title": "sum", "description": "adds", "legacy_components": ["src/math.js#sum"],
           "data_access": [], "dependencies": [], "business_rules": [rule],
           "validations": [], "error_paths": [], "status": "active",
           "corroboration": {"status": "validated", "sources": 3, "call_sites": 1,
                             "tests": 1, "docs": 1, "extra_extractors": 0}}
    return {"metadata": {"schema_version": "1.1.0", "migration_mode": "functional",
                         "source": "estate-graph",
                         "coverage": {"real_pct": 70, "min_pct": 80, "behavior_bearing": 100,
                                      "real": 70, "placeholders": 12, "unmapped": 18,
                                      "not_product": 9}},
            "domains": {"src": {"description": "src", "requirements": {"REQ-001": req},
                                "entities": {}}}}


def test_a_1_1_0_document_with_coverage_and_corroboration_conforms():
    assert validate_document(_core_1_1_doc()) == []
    # bundle 1.3.0 (wicked-core#1233): the old `mapped_pct` label no longer conforms
    stale = _core_1_1_doc()
    stale["metadata"]["coverage"] = {"mapped_pct": 82, "min_pct": 80, "behavior_bearing": 100,
                                     "mapped": 82, "resolved": 70, "unmapped": 18}
    assert validate_document(stale) != []
    old = _core_1_1_doc()
    old["metadata"]["schema_version"] = "1.0.0"  # 1.0.0 stays an accepted version
    assert validate_document(old) == []


def test_an_unconfirmed_item_must_say_why():
    doc = _core_1_1_doc()
    corr = doc["domains"]["src"]["requirements"]["REQ-001"]["corroboration"]
    corr.update(status="unconfirmed", sources=1, docs=0, tests=0)
    assert validate_document(doc), "unconfirmed without why must not conform"
    corr["why"] = {"code": "single_caller", "text": "One caller, and no test or doc touches it."}
    assert validate_document(doc) == []
    corr["why"]["code"] = "vibes"
    assert validate_document(doc)


# --- domain-model 1.2.0: the model core builds from garden's v3 rows -------------

def test_the_core_built_1_2_0_model_conforms():
    doc = core_v3()
    assert doc["metadata"]["schema_version"] == "1.2.0"
    assert validate_document(doc) == []
    statuses = sorted(r["status"] for r in _rules(doc))
    assert statuses == ["Checked", "open", "open", "open"]


def test_a_1_2_0_statement_must_carry_its_key_and_status():
    doc = core_v3()
    rule = _rules(doc)[0]
    rule.pop("statement_key")
    assert any("statement_key" in e for e in validate_document(doc))
    doc = core_v3()
    _rules(doc)[0].pop("status")
    assert any("'status'" in e for e in validate_document(doc))
    doc = core_v3()
    _rules(doc)[0]["status"] = "rejected"  # a rejected statement is never emitted as a rule
    assert any("is not one of" in e for e in validate_document(doc))


def test_a_repaired_statement_id_conforms_and_a_bad_one_does_not():
    doc = core_v3()
    rule = _rules(doc)[0]
    rule["id"] = rule["id"] + "~r0"  # garden check.py names a repair <id>~r<k>
    assert validate_document(doc) == []
    rule["id"] = "no-number"
    assert any("anyOf" in e for e in validate_document(doc))


def test_a_1_2_0_document_needs_its_accounting():
    doc = core_v3()
    doc["metadata"].pop("accounting")
    assert any("accounting" in e for e in validate_document(doc))
    legacy = copy.deepcopy(fixture_document())
    assert "accounting" not in legacy["metadata"] and validate_document(legacy) == []

