"""qe campaign degradation generator (TH-23 / test-R19a).

The S19/S20/ledger-readonly negatives generalized as a generator archetype:
for every DECLARED external dependency, a break-it scenario whose pass bar
is honest error naming + zero crashes + recovery. Proven here:

- the deps declaration is validated fail-closed (a skipped dependency is a
  degradation scenario that never exists);
- generated rungs carry the non-negotiables: `isolation: exclusive`,
  `claim_ceiling: machinery-verified`, all three pass_criteria legs;
- generated scenario markdown follows the stub doctrine — the placeholder
  step `exit 1`s until authored, so a generated scenario can never
  silently PASS;
- `augment_plan` is fail-closed end to end: spec-1 plans are refused
  without an explicit bump (isolation is a spec-2 field — silent version
  bumps are versioning lies), id collisions are refused (never renamed),
  `--after` must name a real rung, and the augmented plan passes
  campaign_plan.plan_errors in full or nothing is written.

Disjoint-build discipline: stdlib + the campaign glue modules only.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "qe"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import campaign_degradation as cd  # noqa: E402
import campaign_plan as cp  # noqa: E402


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def deps_doc():
    return {
        "deps": [
            {
                "id": "estate-binary",
                "kind": "binary",
                "name": "wicked-estate",
                "healthy_signal": "GET /graph returns the graph JSON",
                "category": "api",
            },
            {"id": "crew-daemon", "kind": "daemon", "name": "wicked-crew daemon", "category": "ui"},
            {"id": "qe-ledger-dir", "kind": "state-dir", "name": ".wicked-qe ledger dir"},
        ]
    }


def base_plan(spec=2):
    plan = cp.assemble_plan(
        target={"repo": "acme/target", "ref": "deadbeef"},
        probe_capabilities=[
            {
                "id": "api-health",
                "surface": "health endpoint",
                "apis": "GET /api/v1/health",
                "test_shape": "curl asserts 200 + JSON ok",
                "needs": "isolated daemon",
            }
        ],
        scenarios=[
            {
                "id": "s1-health",
                "title": "API health",
                "category": "api",
                "capability_ids": ["api-health"],
                "deps": [],
                "pass_criteria": {
                    "terminal_state": "daemon answering",
                    "artifact": "health JSON capture",
                    "consumer_state": "no restart loops",
                },
                "claim_ceiling": "machinery-verified",
            }
        ],
        environment_manifest={"ref": "environment-manifest.json"},
        name="dogfood",
    )
    plan["spec"] = spec
    return plan


# --------------------------------------------------------------------------
# load_deps — fail-closed declaration validation
# --------------------------------------------------------------------------


def test_load_deps_normalizes_and_defaults_category():
    deps = cd.load_deps(deps_doc())
    assert [d["id"] for d in deps] == ["estate-binary", "crew-daemon", "qe-ledger-dir"]
    assert deps[2]["category"] == "api"  # default
    assert deps[1]["category"] == "ui"


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d.pop("deps"), "deps[] array"),
        (lambda d: d["deps"].clear(), "zero deps"),
        (lambda d: d["deps"][0].pop("id"), "kebab-case"),
        (lambda d: d["deps"][0].update(id="Bad_Id"), "kebab-case"),
        (lambda d: d["deps"][1].update(id="estate-binary"), "duplicate dep id"),
        (lambda d: d["deps"][0].update(kind="socket"), "kind must be one of"),
        (lambda d: d["deps"][0].pop("name"), "name"),
        (lambda d: d["deps"][0].update(category="cli"), "category must be one of"),
    ],
)
def test_load_deps_rejects_every_defect(mutate, fragment):
    doc = deps_doc()
    mutate(doc)
    with pytest.raises(cd.DegradationError, match=None) as exc:
        cd.load_deps(doc)
    assert fragment in str(exc.value)


def test_custom_kind_has_no_defaults_on_purpose():
    doc = {"deps": [{"id": "webhook", "kind": "custom", "name": "partner webhook"}]}
    with pytest.raises(cd.DegradationError) as exc:
        cd.load_deps(doc)
    assert "custom" in str(exc.value) and "break" in str(exc.value)

    doc["deps"][0]["break"] = "point the webhook URL at a closed port"
    doc["deps"][0]["honest_signal"] = "delivery queue reports a NAMED endpoint failure"
    deps = cd.load_deps(doc)
    arch, brk, honest, _ = cd._resolved(deps[0])
    assert arch == "custom-break"
    assert "closed port" in brk and "NAMED endpoint failure" in honest


# --------------------------------------------------------------------------
# generate — the archetype invariants
# --------------------------------------------------------------------------


def test_generated_rungs_carry_the_non_negotiables():
    gen = cd.generate(cd.load_deps(deps_doc()), plan_name="dogfood")
    assert len(gen["capabilities"]) == len(gen["scenarios"]) == 3
    for rung in gen["scenarios"]:
        assert rung["isolation"] == "exclusive"
        assert rung["claim_ceiling"] == "machinery-verified"
        assert set(rung["pass_criteria"]) == {"terminal_state", "artifact", "consumer_state"}
        # honest error naming is IN the pass bar, not prose around it
        assert "NAMES" in rung["pass_criteria"]["artifact"]
        assert "zero crashes" in rung["pass_criteria"]["terminal_state"]
        assert rung["pass_criteria"]["consumer_state"].startswith("recovery proven")
    ids = [r["id"] for r in gen["scenarios"]]
    assert ids == [
        "degradation-estate-binary-absent",
        "degradation-crew-daemon-down",
        "degradation-qe-ledger-dir-readonly",
    ]


def test_generated_capability_is_declared_hence_verified():
    caps = cd.generate(cd.load_deps(deps_doc()))["capabilities"]
    for cap in caps:
        assert cap["source"] == "human"
        assert cap["status"] == "verified"
    # undeclared healthy signal degrades honestly, never invents one
    assert "undeclared" in caps[1]["apis"]
    assert caps[0]["apis"] == "GET /graph returns the graph JSON"


def test_scenario_markdown_is_a_stub_that_cannot_silently_pass():
    gen = cd.generate(cd.load_deps(deps_doc()), plan_name="dogfood")
    for rel, text in gen["scenario_texts"].items():
        assert rel.startswith("scenarios/") and rel.endswith(".md")
        assert "`exit 1`" in text  # stub doctrine
        assert "isolation: exclusive" in text
        assert 'version: "1.1"' in text  # isolation is a v1.1 field
        assert "TODO(author)" in text
    ui = gen["scenario_texts"]["scenarios/dogfood-degradation-crew-daemon-down.md"]
    assert "category: browser" in ui  # ui rung → browser scenario category


# --------------------------------------------------------------------------
# augment_plan — fail-closed end to end
# --------------------------------------------------------------------------


def test_augment_appends_and_the_result_conforms():
    deps = cd.load_deps(deps_doc())
    result = cd.augment_plan(base_plan(), deps, after="s1-health")
    plan = result["plan"]
    assert cp.plan_errors(plan) == []
    assert len(plan["scenarios"]) == 4 and len(plan["capabilities"]) == 4
    for rung in plan["scenarios"][1:]:
        assert rung["deps"] == ["s1-health"]
        assert rung["scenario_path"].startswith("scenarios/dogfood-degradation-")


def test_augment_refuses_spec1_without_explicit_bump():
    with pytest.raises(cd.DegradationError, match="spec 2"):
        cd.augment_plan(base_plan(spec=1), cd.load_deps(deps_doc()))
    bumped = cd.augment_plan(
        base_plan(spec=1), cd.load_deps(deps_doc()), allow_spec_bump=True
    )["plan"]
    assert bumped["spec"] == 2 and cp.plan_errors(bumped) == []


def test_augment_refuses_id_collisions_never_renames():
    plan = base_plan()
    plan["capabilities"].append(
        {
            "id": "degradation-estate-binary",
            "surface": "s",
            "apis": "a",
            "test_shape": "t",
            "needs": "n",
        }
    )
    with pytest.raises(cd.DegradationError, match="never silently renamed"):
        cd.augment_plan(plan, cd.load_deps(deps_doc()))


def test_augment_refuses_unknown_after_rung():
    with pytest.raises(cd.DegradationError, match="does not name a rung"):
        cd.augment_plan(base_plan(), cd.load_deps(deps_doc()), after="nope")


def test_persist_writes_plan_and_scenarios(tmp_path):
    result = cd.augment_plan(base_plan(), cd.load_deps(deps_doc()))
    written = cd.persist_augmented(result, tmp_path)
    plan_path = Path(written["plan"][0])
    assert plan_path.name == cp.PLAN_FILENAME
    persisted = json.loads(plan_path.read_text(encoding="utf-8"))
    assert cp.plan_errors(persisted) == []
    assert len(written["scenarios"]) == 3
    for s in written["scenarios"]:
        assert Path(s).exists()


# --------------------------------------------------------------------------
# CLI — the two subcommands round-trip through files
# --------------------------------------------------------------------------


def test_cli_generate_and_augment(tmp_path, capsys):
    deps_path = tmp_path / "deps.json"
    deps_path.write_text(json.dumps(deps_doc()), encoding="utf-8")
    assert cd.main(["generate", "--deps", str(deps_path), "--plan-name", "dogfood"]) == 0
    gen = json.loads(capsys.readouterr().out)
    assert len(gen["scenarios"]) == 3

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(base_plan()), encoding="utf-8")
    out_dir = tmp_path / "campaign"
    assert (
        cd.main(
            [
                "augment",
                "--deps",
                str(deps_path),
                "--plan",
                str(plan_path),
                "--out",
                str(out_dir),
                "--after",
                "s1-health",
            ]
        )
        == 0
    )
    assert (out_dir / cp.PLAN_FILENAME).exists()
    assert len(list((out_dir / cp.SCENARIO_DIRNAME).glob("*.md"))) == 3


def test_cli_reports_defects_on_stderr_and_exits_1(tmp_path, capsys):
    deps_path = tmp_path / "deps.json"
    deps_path.write_text(json.dumps({"deps": []}), encoding="utf-8")
    assert cd.main(["generate", "--deps", str(deps_path)]) == 1
    assert "zero deps" in capsys.readouterr().err
