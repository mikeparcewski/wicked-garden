"""qe campaign recon+generation glue + dispatch guard (TH-7 / test-R7).

Two AC halves:

1. **A generated three-lens plan validates against the schema.** The
   assembler merges estate + docs + probe lenses (probe seeded from a crew
   endpoint-manifest fixture) into a plan that conforms to
   schemas/campaign-recon.schema.json v1 — verified against the SCHEMA
   ITSELF via the repo's stdlib draft-07 validator, never a re-statement.
   Honesty invariants are fail-closed: unindexed degradation is derived,
   doc-derived claims are forced PROPOSED, confirmed rungs cannot certify
   proposed capabilities, persistence refuses a nonconforming plan.

2. **The dispatch guard blocks retired-specialist resolution.** A
   `wicked-testing-*` name raises at dispatch with a clear error naming the
   garden replacement; garden `wicked-garden-qe-*` names (and the `qe-*`
   shorthand) resolve against the real skills catalog; non-qe and unknown
   names are refused.

Disjoint-build discipline: imports only the campaign glue modules (module
scope is stdlib + the import-safe schema validator — no DomainStore).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import campaign_dispatch as cd  # noqa: E402
import campaign_plan as cp  # noqa: E402
from domain.validate_domain_model import _validate  # noqa: E402


# --------------------------------------------------------------------------
# fixtures — the three lenses for a target repo
# --------------------------------------------------------------------------

ENDPOINT_MANIFEST = {
    "version": 1,
    "apiTypesVersion": "0.10.0",
    "endpoints": [
        {"method": "GET", "path": "/api/v1/health"},
        {"method": "GET", "path": "/api/v1/projects"},
        {"method": "POST", "path": "/api/v1/projects"},
        {"method": "GET", "path": "/api/v1/projects/:id"},
    ],
}


def estate_lens():
    return [
        {
            "id": "projects-crud",
            "surface": "Projects CRUD — /projects (ProjectsPage), NewProjectModal",
            "apis": "POST/GET /projects (client.ts:560-578)",
            "test_shape": "PASS = new project card on /projects; wire = 200 {project}",
            "needs": "isolated daemon",
            "citations": ["client.ts:560-578", "ProjectsPage.tsx:422"],
        }
    ]


def docs_lens():
    return [
        {
            "id": "export-pdf",
            "surface": "Export as PDF (claimed by README, unverified in code)",
            "apis": "POST /export (README.md:88 — no route node found)",
            "test_shape": "PASS = downloadable PDF artifact",
            "needs": "unknown",
            "citations": ["README.md:88"],
        }
    ]


def probe_lens():
    return cp.capabilities_from_endpoint_manifest(
        ENDPOINT_MANIFEST, manifest_path="packages/crew/endpoint-manifest.json"
    )


def ladder():
    return [
        {
            "id": "S1",
            "title": "API smoke over the manifest-derived surface",
            "category": "api",
            "capability_ids": ["api-projects"],
            "deps": [],
            "pass_criteria": {
                "terminal_state": "daemon healthy after the CRUD sequence",
                "artifact": "captured wire JSON for POST + follow-up GET",
                "consumer_state": "created project present in a later GET /projects",
            },
            "claim_ceiling": "machinery-verified",
        },
        {
            "id": "S2",
            "title": "Projects CRUD through the real UI",
            "category": "ui",
            "capability_ids": ["projects-crud"],
            "deps": ["S1"],
            "pass_criteria": {
                "terminal_state": "project persisted across a hard reload",
                "artifact": "screenshot 1440x700 + wire capture",
                "consumer_state": "dashboard route renders the project",
            },
            "claim_ceiling": "certified",
        },
        {
            "id": "S3",
            "title": "Doc-claimed PDF export (unverified)",
            "category": "ui",
            "capability_ids": ["export-pdf"],
            "deps": ["S2"],
            "pass_criteria": {
                "terminal_state": "export completes",
                "artifact": "PDF file exists and is non-empty",
                "consumer_state": "download visible in the browser context",
            },
            "claim_ceiling": "machinery-verified",
        },
    ]


def three_lens_plan():
    return cp.assemble_plan(
        target={
            "repo": "mikeparcewski/wicked-crew",
            "ref": "deadbeef",
            "surface_url": "http://127.0.0.1:7899/",
        },
        estate_capabilities=estate_lens(),
        docs_capabilities=docs_lens(),
        probe_capabilities=probe_lens(),
        scenarios=ladder(),
        environment_manifest={"ref": "environment-manifest.json"},
        name="crew-campaign-smoke",
        generated_at="2026-08-29T12:00:00Z",
    )


# --------------------------------------------------------------------------
# AC 1 — the generated plan validates against the schema (the schema itself)
# --------------------------------------------------------------------------


def test_generated_three_lens_plan_validates_against_the_schema():
    plan = three_lens_plan()
    schema = json.loads(
        (_REPO / "schemas" / "campaign-recon.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errors: list[str] = []
    _validate(plan, schema, "", schema, errors)
    assert errors == []
    # and the glue's own full gate (schema + ladder + honesty) agrees
    assert cp.plan_errors(plan) == []


def test_three_lenses_are_reflected_in_sources_and_provenance():
    plan = three_lens_plan()
    assert plan["sources"] == {
        "estate": "indexed",
        "docs_recall": True,
        "live_probe": True,
    }
    by_source = {c["source"] for c in plan["capabilities"]}
    assert by_source == {"estate", "docs", "probe"}
    # probe lens came from the committed crew endpoint manifest
    probe = [c for c in plan["capabilities"] if c["source"] == "probe"]
    assert any(c["id"] == "api-projects" for c in probe)
    assert any("endpoint-manifest.json" in c["apis"] for c in probe)


def test_unindexed_degradation_is_honest_and_derived():
    plan = cp.assemble_plan(
        target={"repo": "some/unindexed-repo"},
        docs_capabilities=docs_lens(),
        probe_capabilities=probe_lens(),
        scenarios=[r for r in ladder() if r["id"] == "S1"],
        environment_manifest={"ref": "environment-manifest.json"},
        name="unindexed-campaign",
    )
    assert plan["sources"]["estate"] == "unindexed"
    assert cp.plan_errors(plan) == []
    # …and claiming an estate-sourced capability while unindexed is rejected
    plan["capabilities"].append({**estate_lens()[0], "source": "estate", "status": "verified"})
    errs = cp.plan_errors(plan)
    assert any("unindexed" in e or "not 'indexed'" in e for e in errs)


def test_doc_derived_claims_are_forced_proposed():
    plan = three_lens_plan()
    docs = [c for c in plan["capabilities"] if c["source"] == "docs"]
    assert docs and all(c["status"] == "proposed" for c in docs)
    # the rung bound to the doc-derived capability auto-demoted to proposed
    s3 = next(r for r in plan["scenarios"] if r["id"] == "S3")
    assert s3["status"] == "proposed"
    # a caller forcing that rung to 'confirmed' is caught fail-closed
    s3["status"] = "confirmed"
    errs = cp.plan_errors(plan)
    assert any("'proposed' (pending review)" in e for e in errs)


def test_ladder_order_and_binding_are_enforced():
    plan = three_lens_plan()
    plan["scenarios"][0]["deps"] = ["S2"]  # forward reference
    assert any("earlier rung" in e for e in cp.plan_errors(plan))
    plan = three_lens_plan()
    plan["scenarios"][0]["capability_ids"] = ["no-such-capability"]
    assert any("does not name a capability" in e for e in cp.plan_errors(plan))


def test_persist_writes_plan_and_v1_stubs_fail_closed(tmp_path):
    plan = three_lens_plan()
    written = cp.persist_plan(plan, out_dir=tmp_path / "campaign")
    plan_path = Path(written["plan"][0])
    assert plan_path.name == "campaign-recon.json"
    persisted = json.loads(plan_path.read_text(encoding="utf-8"))
    assert cp.plan_errors(persisted) == []
    # stubs are scenario-format v1 markdown, bound back into the plan
    stubs = {Path(p).name: Path(p).read_text(encoding="utf-8") for p in written["scenarios"]}
    assert len(stubs) == 3
    for text in stubs.values():
        assert 'version: "1.0"' in text
        assert "category: " in text
        assert "assertions:" in text
    # ui rung → browser category; proposed rung → pending-review status
    s3_text = stubs["crew-campaign-smoke-s3.md"]
    assert "category: browser" in s3_text
    assert "status: pending-review" in s3_text
    for rung in persisted["scenarios"]:
        assert rung["scenario_path"].startswith("scenarios/")
    # fail-closed: a nonconforming plan writes NOTHING
    bad = three_lens_plan()
    bad.pop("environment_manifest")
    out = tmp_path / "refused"
    with pytest.raises(cp.CampaignPlanError):
        cp.persist_plan(bad, out_dir=out)
    assert not out.exists()


def test_desktop_rungs_have_no_v1_stub_yet():
    plan = three_lens_plan()
    rung = dict(plan["scenarios"][0], id="D1", category="desktop", deps=[])
    with pytest.raises(cp.CampaignPlanError, match="TH-15"):
        cp.scenario_stub_markdown(rung, plan)


def test_endpoint_manifest_conversion_rejects_garbage():
    with pytest.raises(cp.CampaignPlanError, match="no endpoints"):
        cp.capabilities_from_endpoint_manifest({"version": 1, "endpoints": []})


def test_endpoint_manifest_non_api_paths_never_group_on_params():
    # crew's real manifest carries /ws and /ws/terminals/:id — the group key
    # must be the literal segment, never a :param placeholder.
    caps = cp.capabilities_from_endpoint_manifest(
        {
            "version": 1,
            "apiTypesVersion": "0.10.0",
            "endpoints": [
                {"method": "GET", "path": "/ws"},
                {"method": "GET", "path": "/ws/terminals/:id"},
            ],
        }
    )
    assert [c["id"] for c in caps] == ["api-ws"]


# --------------------------------------------------------------------------
# AC 2 — dispatch guard: retired-specialist resolution is BLOCKED
# --------------------------------------------------------------------------


def test_wicked_testing_resolution_is_blocked_with_replacement_hint():
    with pytest.raises(cd.DispatchGuardError) as exc:
        cd.resolve_specialist("wicked-testing-a11y-test-engineer")
    msg = str(exc.value)
    assert "BLOCKED" in msg
    assert "retired" in msg
    assert "wicked-garden-qe-a11y-test-engineer" in msg


def test_every_retired_wicked_testing_specialist_shape_is_blocked():
    # the guard blocks the prefix itself — no allowlist gaps
    for name in (
        "wicked-testing-scenario-executor",
        "wicked-testing-acceptance-test-reviewer",
        "wicked-testing-security-test-engineer",
        "wicked-testing-anything-else",
    ):
        with pytest.raises(cd.DispatchGuardError, match="BLOCKED"):
            cd.resolve_specialist(name)


def test_wicked_brain_surface_is_blocked_too():
    with pytest.raises(cd.DispatchGuardError, match="BLOCKED"):
        cd.resolve_specialist("wicked-brain-recall")


def test_garden_qe_specialists_resolve_against_the_real_catalog():
    assert (
        cd.resolve_specialist("wicked-garden-qe-scenario-executor")
        == "wicked-garden-qe-scenario-executor"
    )
    # shorthand expands to canonical
    assert (
        cd.resolve_specialist("qe-acceptance-test-reviewer")
        == "wicked-garden-qe-acceptance-test-reviewer"
    )


def test_non_qe_and_unknown_names_are_refused():
    with pytest.raises(cd.DispatchGuardError, match="not a garden qe-"):
        cd.resolve_specialist("wicked-garden-engineering")
    with pytest.raises(cd.DispatchGuardError, match="not in the qe catalog"):
        cd.resolve_specialist("wicked-garden-qe-time-travel-engineer")
    with pytest.raises(cd.DispatchGuardError, match="router"):
        cd.resolve_specialist("wicked-garden-qe-")


def test_guard_cli_blocks_with_exit_2(capsys):
    assert cd.main(["wicked-garden-qe-scenario-executor"]) == 0
    assert cd.main(["wicked-testing-scenario-executor"]) == 2
    err = capsys.readouterr().err
    assert "BLOCKED" in err
