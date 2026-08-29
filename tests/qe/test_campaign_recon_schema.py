"""campaign-recon.schema.json has teeth (TH-5 / RECON-TEST-HARNESS test-R5).

Validates the versioned qe-campaign plan contract in schemas/ using the
repo's own stdlib draft-07 subset validator (no jsonschema — the repo is
stdlib+pytest only): a conforming plan passes clean, and every class of
nonconforming plan is rejected with a specific error. Also enforces the one
invariant JSON Schema cannot express — the scenario ladder is
dependency-ordered (deps reference only EARLIER rungs, never unknown ids).

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
        "spec": 1,
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
                "notes": "API-substituted modal submit (disclosed)",
            },
        ],
    }


# --- the schema file itself ---------------------------------------------------


def test_schema_is_draft07_and_versioned_v1():
    schema = load_schema()
    assert schema["$schema"].startswith("http://json-schema.org/draft-07")
    assert schema["$id"].endswith("schemas/campaign-recon.schema.json")
    # format v1 is pinned as a const, wicked-pack.schema.json style
    assert schema["properties"]["spec"]["const"] == 1
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


# --- a conforming plan passes clean -------------------------------------------


def test_conforming_plan_validates_clean():
    doc = conforming_plan()
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
    errs = _mutated(lambda d: d.__setitem__("spec", 2))
    assert any("const" in e for e in errs)


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
