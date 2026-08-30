"""AW-25 golden-path artifacts stay conformant (arch-R21).

The committed golden-path scenario (evidence/aw25-golden/) is the wiki
pipeline's own evidence-gated proof — a plan artifact, a seed ruleset, and a
re-runnable chain script. This test pins the parts a later change could
silently rot without ever running the (daemon-heavy) scenario itself:

- the plan artifact validates against campaign-recon.schema.json (spec 2)
  plus the ladder-order extra invariant — the same checks
  `scripts/qe/campaign_plan.py validate` runs;
- the plan's rung binds a scenario_path that exists;
- the seed doc and the paired deny Policy stay id-twinned (POL-2500 in both,
  the doc↔gate pairing the governance packs convention requires) and both
  keep citing the wiki URI the recorded denial evidence carries;
- run.sh keeps asserting the two AC-critical strings (the wiki URI and the
  canary token) so a rewrite cannot quietly drop the citation assertions.

Stdlib-only, hermetic: no daemon, no network, no stores.
"""

import json
import re
from pathlib import Path

from domain.validate_domain_model import _validate

_REPO = Path(__file__).resolve().parents[2]
AW25 = _REPO / "evidence" / "aw25-golden"
SCHEMA_PATH = _REPO / "schemas" / "campaign-recon.schema.json"

WIKI_URI = "wiki://aw25-golden#POL-2500"
MARKER = "AW25-GOLDEN-" + "DENY-ME"  # split so this test file never trips the canary rule itself


def _plan():
    return json.loads((AW25 / "campaign-recon.aw25.json").read_text(encoding="utf-8"))


def test_plan_artifact_validates_against_campaign_recon_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    _validate(_plan(), schema, "", schema, errors)
    assert errors == [], f"campaign-recon.aw25.json no longer validates: {errors}"


def test_plan_ladder_is_dependency_ordered_and_binds_a_real_scenario():
    plan = _plan()
    seen: set[str] = set()
    for i, rung in enumerate(plan["scenarios"]):
        for dep in rung.get("deps", []):
            assert dep in seen, f"scenarios[{i}]: dep '{dep}' does not name an earlier rung"
        seen.add(rung["id"])
    rung = plan["scenarios"][0]
    scenario = (AW25 / rung["scenario_path"]).resolve()
    assert scenario.is_file(), f"rung binds a missing scenario file: {rung['scenario_path']}"
    assert scenario.name == "aw25-golden-path.md"


def test_seed_doc_and_policy_stay_id_twinned_and_cite_the_wiki_uri():
    doc = (AW25 / "ruleset" / "aw25-golden.md").read_text(encoding="utf-8")
    policy = json.loads((AW25 / "ruleset" / "policies" / "POL-2500.json").read_text(encoding="utf-8"))
    # The doc mints conformance rule POL-2500; the Policy twin carries the same id.
    assert re.search(r"^- `POL-2500` \(critical\):", doc, re.M), "doc lost rule POL-2500"
    assert policy["id"] == "POL-2500", "policy id drifted from the doc rule id"
    assert policy["effect"] == "deny" and policy["trigger"]["contains"] == MARKER
    # Both citation paths carry the wiki URI (statement → obligations; criteria → claim).
    assert WIKI_URI in doc, "seed-doc rule statement lost the wiki URI"
    assert WIKI_URI in policy["criteria"], "policy criteria lost the wiki URI"


def test_run_script_keeps_the_ac_critical_assertions():
    script = (AW25 / "run.sh").read_text(encoding="utf-8")
    assert script.count(WIKI_URI) >= 3, "run.sh no longer asserts the wiki-URI citation on every hop"
    assert MARKER in script, "run.sh lost the canary marker"
    assert "runs/$RUN_ID/acceptance" in script, "run.sh no longer reads the acceptance payload"
    assert "7701" in script, "run.sh lost the real-daemon port guard"
