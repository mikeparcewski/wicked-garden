"""Drift-guard: the workflow skill must stay consistent with the engine's data.

SKILL-RATIONALIZATION overlap #19: ``skills/workflow`` is the crew-engine
reference that garden *workers* consume mid-run — capability-plane consumption
of a control-plane contract. Prose drifts; data doesn't. This suite pins the
skill body to the contract's data sources so a divergence fails CI instead of
rotting silently (the way the skill's ``phases.json`` reference outlived the
file itself):

  1. Every repo-relative data file the skill body names must exist.
  2. The gate-verdict vocabulary the skill documents must exactly match the
     engine seam's ``VALID_VERDICTS`` (scripts/_event_schema.py).
  3. The skill must anchor itself to crew's workflows-as-data contract by
     name (``WorkflowDef``), not to a dead local file.
  4. When a wicked-crew checkout is resolvable (WICKED_CREW_ROOT env, or the
     ``../wicked-crew`` sibling), the contract terms the skill leans on must
     still exist in crew's ``WorkflowDef``/``PhaseDef`` source. Skipped —
     never vacuously passed — when crew isn't present (graceful-degradation
     doctrine: a peer's absence must not fail garden CI).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

_WORKFLOW_SKILL = _REPO_ROOT / "skills" / "workflow" / "SKILL.md"

# PhaseDef/WorkflowDef fields the garden skill documents as load-bearing.
# If crew renames one, the skill (and the workers reading it) must follow.
_CREW_CONTRACT_TERMS = ("WorkflowDef", "PhaseDef", "depends_on", "gate_type", "skill_ref")

# Names the skill mentions that are RUNTIME artifacts (written during a run),
# not repo data files — exempt from the existence check by design.
_RUNTIME_ARTIFACTS = {"conditions-manifest.json"}


def _skill_text() -> str:
    assert _WORKFLOW_SKILL.exists(), "skills/workflow/SKILL.md is missing"
    return _WORKFLOW_SKILL.read_text(encoding="utf-8")


def _resolve_crew_root() -> Path | None:
    """A wicked-crew checkout: WICKED_CREW_ROOT env, else the repo sibling."""
    env = os.environ.get("WICKED_CREW_ROOT")
    candidates = [Path(env)] if env else []
    candidates.append(_REPO_ROOT.parent / "wicked-crew")
    for cand in candidates:
        if (cand / "packages" / "crew" / "src" / "core" / "types.ts").is_file():
            return cand
    return None


def test_workflow_skill_data_file_references_exist():
    """Any .json data file the skill names must exist somewhere in the repo.

    This is the check that would have caught ``phases.json`` — the skill
    cited it as the gate-config source of truth long after the file was
    deleted.
    """
    text = _skill_text()
    missing = []
    for ref in set(re.findall(r"[\w./-]*[\w-]+\.json", text)):
        name = ref.lstrip("./")
        if Path(name).name in _RUNTIME_ARTIFACTS:
            continue
        candidates = [
            _REPO_ROOT / name,
            _REPO_ROOT / ".claude-plugin" / Path(name).name,
        ]
        if not any(c.exists() for c in candidates):
            missing.append(ref)
    assert not missing, (
        f"skills/workflow/SKILL.md references data files that do not exist: "
        f"{sorted(missing)} — repoint the skill or restore the data."
    )


def test_workflow_skill_verdicts_match_engine_vocabulary():
    """The skill's gate-verdict table == the engine seam's VALID_VERDICTS."""
    from _event_schema import VALID_VERDICTS  # noqa: PLC0415

    text = _skill_text()
    documented = {v for v in ("APPROVE", "CONDITIONAL", "REJECT", "PASS", "FAIL")
                  if re.search(rf"\*\*{v}\*\*", text)}
    assert documented == set(VALID_VERDICTS), (
        f"workflow skill documents verdicts {sorted(documented)} but the "
        f"engine's VALID_VERDICTS is {sorted(VALID_VERDICTS)} "
        "(scripts/_event_schema.py) — update both together."
    )


def test_workflow_skill_anchors_to_crew_workflows_as_data():
    """The skill must name the crew contract (WorkflowDef), not a dead file."""
    text = _skill_text()
    assert "WorkflowDef" in text, (
        "skills/workflow/SKILL.md no longer names crew's WorkflowDef — the "
        "skill must anchor to the workflows-as-data contract it documents."
    )
    assert "tests/test_workflow_drift.py" in text, (
        "the skill should point maintainers at this drift-guard so the "
        "update-both-together rule is discoverable."
    )


def test_workflow_skill_terms_exist_in_crew_contract():
    """Cross-check against crew's types.ts when a checkout is resolvable."""
    crew_root = _resolve_crew_root()
    if crew_root is None:
        pytest.skip("no wicked-crew checkout (set WICKED_CREW_ROOT to enable)")
    types_ts = (crew_root / "packages" / "crew" / "src" / "core" / "types.ts").read_text(
        encoding="utf-8"
    )
    gone = [term for term in _CREW_CONTRACT_TERMS if term not in types_ts]
    assert not gone, (
        f"crew's workflow contract no longer defines {gone} "
        f"(checked {crew_root}/packages/crew/src/core/types.ts) — "
        "skills/workflow/SKILL.md documents these terms and must be updated "
        "with the contract."
    )
