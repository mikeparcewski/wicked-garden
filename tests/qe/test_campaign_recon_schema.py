"""campaign-recon.schema.json has teeth (TH-5 / test-R5; v2 bump TH-16+TH-22).

Validates the versioned qe-campaign plan contract in schemas/ using the
repo's own stdlib draft-07 subset validator (no jsonschema — the repo is
stdlib+pytest only): a conforming plan passes clean, and every class of
nonconforming plan is rejected with a specific error. Also enforces the one
invariant JSON Schema cannot express — the scenario ladder is
dependency-ordered (deps reference only EARLIER rungs, never unknown ids).

Format v2 (TH-16 + TH-22, ONE shared bump): rungs gain the optional
`isolation` annotation and spec becomes `enum: [1, 2]` — every v1 plan
stays valid (backward compat is proven here, not asserted).

Disjoint-build discipline: imports only the shared schema-layer validator
(domain.validate_domain_model._validate is import-safe — module scope is
constants + lru_cache loaders, no DomainStore).
"""

import copy
import json
from pathlib import Path

from domain.validate_domain_model import _validate

_REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO / "schemas" / "campaign-recon.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(doc):
    """Run the stdlib draft-07 subset validator against the campaign schema."""
    schema = load_schema()
    errors: list[str] = []
    _validate(doc, schema, "", schema, errors)
    return errors


def ladder_order_errors(doc):
    """The extra invariant the schema's `scenarios` description mandates:
    topological order — every dep names a rung that appeared EARLIER."""
    errors = []
    seen = set()
    for i, rung in enumerate(doc.get("scenarios", [])):
        for dep in rung.get("deps", []):
            if dep not in seen:
                errors.append(
                    f"scenarios[{i}] ({rung.get('id')}): dep '{dep}' does not "
                    "name an earlier rung"
                )
        seen.add(rung.get("id"))
    return errors


def conforming_plan():
    """Minimal-but-real plan modeled on the proven studio campaign shape."""
    return {
        "spec": 2,
        "name": "studio-e2e-smoke",
        "generated_at": "2026-08-29T12:00:00Z",
        "target": {
            "repo": "mikeparcewski/wicked-studio",
            "ref": "v0.4.0",
            "surface_url": "http://127.0.0.1:7701/",
        },
        "sources": {"estate": "indexed", "docs_recall": True, "live_probe": True},
        "capabilities": [
            {
                "id": "projects-crud",
                "surface": "Projects CRUD — /projects (ProjectsPage), NewProjectModal",
                "apis": "POST/GET /projects, GET/PATCH /projects/:id (client.ts:560-578)",
                "test_shape": "PASS = new project card on /projects; wire = 200 {project}",
                "needs": "daemon only",
                "citations": ["client.ts:560-578", "ProjectsPage.tsx:422"],
                "source": "estate",
                "status": "verified",
            }
        ],
        "environment_manifest": {
            "ref": "environment-manifest.json",
            "sha256": "a" * 64,
        },
        "scenarios": [
            {
                "id": "S1",
                "title": "Cold start, chrome, WS, health rail",
                "category": "ui",
                "capability_ids": ["projects-crud"],
                "deps": [],
                "pass_criteria": {
                    "terminal_state": "page interactive + WS connected",
                    "artifact": "screenshot 1440x700 + captured GET /health JSON",
                    "consumer_state": "health rail renders real seat rows",
                },
                "claim_ceiling": "certified",
                "isolation": "stateless",
                "scenario_path": "scenarios/s1-cold-start.md",
                "status": "confirmed",
            },
            {
                "id": "S2",
                "title": "Project creation via UI",
                "category": "api",
                "deps": ["S1"],
                "pass_criteria": {
                    "terminal_state": "project persisted across a hard reload",
                    "artifact": "project row in a later GET /projects",
                    "consumer_state": "dashboard route renders the project",
                },
                "claim_ceiling": "machinery-verified",
                "isolation": "shares-state",
                "notes": "API-substituted modal submit (disclosed)",
            },
        ],
    }


def v1_plan():
    """A pre-bump plan exactly as TH-5 shipped it: spec 1, no isolation."""
    doc = conforming_plan()
    doc["spec"] = 1
    for rung in doc["scenarios"]:
        rung.pop("isolation", None)
    return doc


# --- the schema file itself ---------------------------------------------------


def test_schema_is_draft07_and_versioned():
    schema = load_schema()
    assert schema["$schema"].startswith("http://json-schema.org/draft-07")
    assert schema["$id"].endswith("schemas/campaign-recon.schema.json")
    # ONE shared bump for TH-16 + TH-22: v2 current, v1 still accepted
    assert schema["properties"]["spec"]["enum"] == [1, 2]
    assert "spec" in schema["required"]


def test_schema_encodes_the_contract_enums():
    schema = load_schema()
    rung = schema["$defs"]["rung"]
    assert rung["properties"]["category"]["enum"] == ["api", "ui", "desktop"]
    # claim ceilings are plannable levels only — 'skipped' is outcome-only
    assert schema["$defs"]["claim_ceiling"]["enum"] == [
        "certified",
        "machinery-verified",
    ]
    # pass criteria = terminal state + artifact + consumer state, all required
    assert schema["$defs"]["pass_criteria"]["required"] == [
        "terminal_state",
        "artifact",
        "consumer_state",
    ]
    # v2: the per-rung isolation annotation (TH-22) — optional, closed enum,
    # default (shares-state) documented rather than schema-defaulted
    isolation = rung["properties"]["isolation"]
    assert isolation["enum"] == ["shares-state", "exclusive", "stateless"]
    assert "isolation" not in rung["required"]
    assert "shares-state" in isolation["description"]  # the documented default


# --- a conforming plan passes clean -------------------------------------------


def test_conforming_plan_validates_clean():
    doc = conforming_plan()
    assert schema_errors(doc) == []
    assert ladder_order_errors(doc) == []


def test_v1_plan_still_validates_clean():
    # backward compat is proven, not asserted: the pre-bump shape passes v2
    doc = v1_plan()
    assert schema_errors(doc) == []
    assert ladder_order_errors(doc) == []


# --- nonconforming plans are rejected, each for its own reason ----------------


def _mutated(mutator):
    doc = copy.deepcopy(conforming_plan())
    mutator(doc)
    return schema_errors(doc)


def test_missing_required_top_level_field_rejected():
    errs = _mutated(lambda d: d.pop("environment_manifest"))
    assert any("missing required property 'environment_manifest'" in e for e in errs)


def test_wrong_spec_version_rejected():
    errs = _mutated(lambda d: d.__setitem__("spec", 3))
    assert any("is not one of [1, 2]" in e for e in errs)


def test_bad_isolation_value_rejected():
    errs = _mutated(lambda d: d["scenarios"][0].__setitem__("isolation", "solo"))
    assert any(
        "is not one of ['shares-state', 'exclusive', 'stateless']" in e
        for e in errs
    )


def test_bad_scenario_category_rejected():
    errs = _mutated(lambda d: d["scenarios"][0].__setitem__("category", "browser"))
    assert any("is not one of ['api', 'ui', 'desktop']" in e for e in errs)


def test_skipped_is_not_a_plannable_claim_ceiling():
    errs = _mutated(lambda d: d["scenarios"][0].__setitem__("claim_ceiling", "skipped"))
    assert any("claim_ceiling" in e and "is not one of" in e for e in errs)


def test_pass_criteria_missing_consumer_state_rejected():
    errs = _mutated(lambda d: d["scenarios"][1]["pass_criteria"].pop("consumer_state"))
    assert any("missing required property 'consumer_state'" in e for e in errs)


def test_capability_missing_test_shape_rejected():
    errs = _mutated(lambda d: d["capabilities"][0].pop("test_shape"))
    assert any("missing required property 'test_shape'" in e for e in errs)


def test_unindexed_marker_is_the_only_degradation_spelling():
    errs = _mutated(lambda d: d["sources"].__setitem__("estate", "partial"))
    assert any("is not one of ['indexed', 'unindexed']" in e for e in errs)


def test_unknown_top_level_key_rejected():
    errs = _mutated(lambda d: d.__setitem__("extra_lens", {}))
    assert any("additional property 'extra_lens' is not allowed" in e for e in errs)


def test_env_manifest_bad_sha_rejected():
    errs = _mutated(
        lambda d: d["environment_manifest"].__setitem__("sha256", "not-a-sha")
    )
    assert any("does not match pattern" in e for e in errs)


def test_forward_dep_fails_ladder_order():
    doc = conforming_plan()
    doc["scenarios"][0]["deps"] = ["S2"]  # S2 comes later — forward reference
    assert schema_errors(doc) == []  # shape-valid…
    assert ladder_order_errors(doc)  # …but not a valid ladder


def test_unknown_dep_fails_ladder_order():
    doc = conforming_plan()
    doc["scenarios"][1]["deps"] = ["S99"]
    assert ladder_order_errors(doc)
