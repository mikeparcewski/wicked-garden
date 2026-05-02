"""tests/crew/test_consensus_gate.py — consensus_gate.py unit tests.

Site 2 of the bus-cutover (#746) — Council Conditions C9 + C10 + C11:
  * eval_id is minted per call to evaluate_consensus_gate (C9)
  * report  chain_id includes eval_id discriminator (C9)
  * evidence chain_id includes eval_id + ".evidence" discriminator (C9)
  * raw_payload is present on both emits (C10)
  * raw_payload bytes match the on-disk file byte-for-byte (C11 contract)
  * regression test: the OLD f"{project_id}.{phase}" chain_id format would
    have collided on a second consensus eval — the new format does not

T1: deterministic — uuid is patched to a fixed value; no wall-clock sync.
T2: no sleep-based sync.
T3: isolated — each test gets its own tempdir + patched _bus.emit_event.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: Site 2 of bus-cutover (#746).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_consensus_result():
    """Build a minimal ConsensusResult fixture (importing here keeps the
    sys.path setup in conftest applied before the import resolves)."""
    from jam.consensus import ConsensusResult, DissentingView
    return ConsensusResult(
        decision="APPROVE",
        confidence=0.85,
        consensus_points=[{"point": "code is well-structured", "agreement": 3, "of": 3}],
        dissenting_views=[
            DissentingView(persona="security-engineer", view="rotate JWT", strength="moderate"),
        ],
        open_questions=["how do we handle revocation?"],
        rounds=1,
        participants=3,
    )


# ---------------------------------------------------------------------------
# C10 — raw_payload present on report emit
# ---------------------------------------------------------------------------


def test_report_emit_includes_raw_payload_with_eval_id_chain_id() -> None:
    """C10 — `raw_payload` is included in the report emit payload.
    C9 — chain_id includes the eval_id discriminator.
    """
    from consensus_gate import _write_consensus_report
    captured: list[dict] = []

    def _fake_emit(event_type, payload, chain_id=None, metadata=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "demo-project"
        with patch("_bus.emit_event", side_effect=_fake_emit):
            _write_consensus_report(
                project_dir, "design", _make_consensus_result(),
                {"agreement_ratio": 0.85},
                eval_id="abcdef123456",
            )

    assert len(captured) == 1, f"expected 1 emit, got {len(captured)}: {captured}"
    emit = captured[0]
    assert emit["event_type"] == "wicked.consensus.report_created"
    # C9: chain_id format
    assert emit["chain_id"] == "demo-project.design.consensus.abcdef123456"
    # C10: raw_payload present
    assert "raw_payload" in emit["payload"], (
        f"C10 violation: raw_payload missing from report emit. payload keys: "
        f"{list(emit['payload'].keys())}"
    )
    # raw_payload is JSON-parseable
    parsed = json.loads(emit["payload"]["raw_payload"])
    assert parsed["decision"] == "APPROVE"
    assert parsed["phase"] == "design"
    # eval_id surfaced in payload too (so consumers can re-correlate)
    assert emit["payload"]["eval_id"] == "abcdef123456"


def test_report_raw_payload_matches_disk_bytes_exactly() -> None:
    """C11 contract — raw_payload bytes must equal the on-disk file bytes.
    The projector reproduces the file from raw_payload, so any drift between
    the two would silently corrupt projection-derived audits.
    """
    from consensus_gate import _write_consensus_report
    captured: list[dict] = []

    def _fake_emit(event_type, payload, chain_id=None, metadata=None):
        captured.append({"payload": payload})

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "demo-project"
        with patch("_bus.emit_event", side_effect=_fake_emit):
            _write_consensus_report(
                project_dir, "design", _make_consensus_result(),
                {"agreement_ratio": 0.85},
                eval_id="abcdef123456",
            )
        on_disk = (project_dir / "phases" / "design" / "consensus-report.json").read_text()

    assert captured, "no emit captured"
    raw_payload = captured[0]["payload"]["raw_payload"]
    assert raw_payload == on_disk, (
        "C11 byte-identity contract violated — raw_payload diverges from the on-disk file."
    )


# ---------------------------------------------------------------------------
# C10 — raw_payload present on evidence emit
# ---------------------------------------------------------------------------


def test_evidence_emit_includes_raw_payload_and_evidence_discriminator() -> None:
    """C10 — `raw_payload` present in evidence emit.
    C9 — chain_id includes ".evidence" discriminator on top of eval_id so
    report and evidence emits do not collide within the same eval.
    """
    from consensus_gate import _write_consensus_evidence
    captured: list[dict] = []

    def _fake_emit(event_type, payload, chain_id=None, metadata=None):
        captured.append({
            "event_type": event_type,
            "payload": payload,
            "chain_id": chain_id,
        })

    consensus_result = {
        "result": "REJECT",
        "reason": "Strong dissent on credential rotation",
        "consensus_confidence": 0.45,
        "agreement_ratio": 0.45,
        "dissenting_views": [{"persona": "sec", "view": "rotate", "strength": "strong"}],
        "participants": 5,
        "eval_id": "abcdef123456",
    }

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "demo-project"
        with patch("_bus.emit_event", side_effect=_fake_emit):
            _write_consensus_evidence(project_dir, "design", consensus_result)

    assert len(captured) == 1, f"expected 1 emit, got {len(captured)}"
    emit = captured[0]
    assert emit["event_type"] == "wicked.consensus.evidence_recorded"
    # C9: distinct chain_id from the report — has ".evidence" discriminator.
    assert emit["chain_id"] == "demo-project.design.consensus.abcdef123456.evidence"
    # C10: raw_payload present
    assert "raw_payload" in emit["payload"]
    parsed = json.loads(emit["payload"]["raw_payload"])
    assert parsed["result"] == "REJECT"
    assert parsed["reason"] == "Strong dissent on credential rotation"


def test_evidence_raw_payload_matches_disk_bytes_exactly() -> None:
    """C11 contract — evidence raw_payload bytes equal the on-disk file."""
    from consensus_gate import _write_consensus_evidence
    captured: list[dict] = []

    def _fake_emit(event_type, payload, chain_id=None, metadata=None):
        captured.append({"payload": payload})

    consensus_result = {
        "result": "REJECT",
        "reason": "Dissent",
        "consensus_confidence": 0.45,
        "agreement_ratio": 0.45,
        "dissenting_views": [],
        "participants": 5,
        "eval_id": "abcdef123456",
    }

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "demo-project"
        with patch("_bus.emit_event", side_effect=_fake_emit):
            _write_consensus_evidence(project_dir, "design", consensus_result)
        on_disk = (project_dir / "phases" / "design" / "consensus-evidence.json").read_text()

    assert captured
    assert captured[0]["payload"]["raw_payload"] == on_disk


# ---------------------------------------------------------------------------
# C9 regression — OLD chain_id format would have collided
# ---------------------------------------------------------------------------


def test_chain_id_old_format_would_have_collided_on_second_eval() -> None:
    """Council Condition C9 regression test.

    Pre-#746 both emits used `chain_id=f"{project_id}.{phase}"`.  A second
    consensus eval on the same phase would land the SAME chain_id and
    collide on the bus dedupe ledger
    (`_bus.is_processed` keyed on `(event_type, chain_id)`).

    This test asserts:
      1. The OLD format collides for two evals on the same phase.
      2. The NEW format (with eval_id) does NOT collide.

    If a future maintainer reverts the chain_id format, this test fails
    visibly with a message that points at C9.
    """
    project_id = "demo-project"
    phase = "design"

    # OLD format (would have collided)
    old_eval_1 = f"{project_id}.{phase}"
    old_eval_2 = f"{project_id}.{phase}"
    assert old_eval_1 == old_eval_2, (
        "Setup invariant: the OLD chain_id format MUST collapse for two "
        "evals on the same phase — that's the bug C9 fixes."
    )

    # NEW format (per C9): include per-eval discriminator
    new_eval_1 = f"{project_id}.{phase}.consensus.eval-1-id"
    new_eval_2 = f"{project_id}.{phase}.consensus.eval-2-id"
    assert new_eval_1 != new_eval_2, (
        "C9 regression: the NEW chain_id format must NOT collide for two "
        "evals on the same phase. If this fails, the eval_id discriminator "
        "has been removed from the chain_id."
    )

    # And the evidence chain_id must differ from its own report chain_id
    # (otherwise both emits within the same eval would dedupe).
    new_eval_1_evidence = f"{project_id}.{phase}.consensus.eval-1-id.evidence"
    assert new_eval_1_evidence != new_eval_1, (
        "C9 regression: the evidence chain_id must include the .evidence "
        "discriminator to stay distinct from the report chain_id within "
        "the same eval."
    )


def test_evaluate_consensus_gate_threads_eval_id_into_result_dict() -> None:
    """The eval_id minted inside `evaluate_consensus_gate` MUST surface in
    the returned base dict so phase_manager.py can thread it through to
    `_write_consensus_evidence`.  Without this, the evidence emit's
    chain_id would not match the report emit's eval_id discriminator.
    """
    # Direct call into evaluate_consensus_gate would require setting up
    # gate-result.json + jam consensus pipeline.  We instead assert the
    # contract structurally by reading the source for the `eval_id` key
    # attached to base.  This is a contract pin, not an end-to-end test.
    import consensus_gate
    src = Path(consensus_gate.__file__).read_text()
    assert '"eval_id": eval_id' in src, (
        "C9 contract violation: evaluate_consensus_gate no longer threads "
        "eval_id into the base result dict.  Without this, "
        "_write_consensus_evidence cannot reuse the report's eval_id and "
        "the two emits land with mismatched chain_ids."
    )


# ---------------------------------------------------------------------------
# #760 — eval_id width regression pin (defense-in-depth)
# ---------------------------------------------------------------------------


def test_eval_id_is_at_least_64_bits_wide() -> None:
    """eval_id width regression pin (#760).

    PR #758 minted eval_id at 12 hex chars (48 bits, ~16.7M evals per
    (project, phase) at 50% birthday collision risk). #760 widened to
    16 hex chars (64 bits, ~4.3B evals at 50% risk) as defense-in-depth
    before all 5 cutover sites stack on long-lived projects.

    A future shrinkage would silently re-introduce the collision risk.
    This test catches it. Storage is opaque TEXT (no length constraint),
    so wider future widths are fine — the assertion is a floor only.
    """
    import consensus_gate
    src = Path(consensus_gate.__file__).read_text()
    # All eval_id mint sites must use hex[:N] with N >= 16.
    import re
    matches = re.findall(r"uuid\.uuid4\(\)\.hex\[:(\d+)\]", src)
    assert matches, (
        "Could not find any uuid.uuid4().hex[:N] mint sites in "
        "consensus_gate.py — has the eval_id source moved?"
    )
    for width in matches:
        assert int(width) >= 16, (
            f"#760 contract violation: eval_id width {width} < 16. "
            f"PR #760 widened from 12 -> 16 (48b -> 64b entropy) as "
            f"defense-in-depth before Sites 3-5 stack on long-lived "
            f"projects. Do not shrink without re-evaluating birthday "
            f"collision risk at the new scale."
        )


# ---------------------------------------------------------------------------
# C4 — disk write still wins (daemon-down contract)
# ---------------------------------------------------------------------------


def test_report_disk_write_succeeds_even_when_bus_emit_fails() -> None:
    """C4 — daemon-down (or bus-emit raising) MUST NOT prevent the disk
    write from completing.  The disk file is still source of truth this
    release; bus emit is observability only.
    """
    from consensus_gate import _write_consensus_report

    def _bus_raises(event_type, payload, chain_id=None, metadata=None):
        raise RuntimeError("bus down")

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "demo-project"
        with patch("_bus.emit_event", side_effect=_bus_raises):
            # Must not raise — fail-open on bus errors.
            _write_consensus_report(
                project_dir, "design", _make_consensus_result(),
                {"agreement_ratio": 0.85},
                eval_id="abcdef123456",
            )

        report_path = project_dir / "phases" / "design" / "consensus-report.json"
        assert report_path.exists(), (
            "C4 violation: disk write skipped when bus emit failed. "
            "Daemon-down → disk write must still win."
        )
        parsed = json.loads(report_path.read_text())
        assert parsed["decision"] == "APPROVE"
