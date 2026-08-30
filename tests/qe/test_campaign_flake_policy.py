"""One flaky scenario can neither silently deny nor silently pass a campaign
(TH-21 / RECON-TEST-HARNESS test-R23).

Exercises the flaky-verdict policy through the REAL CLI surfaces — the same
posture as tests/qe/test_campaign_scoreboard.py, whose hermetic harness
(tmp DomainStore-shaped ledger + WICKED_LEDGER_PKG_DIR stub) this reuses:

- ``scripts/qe/lib/campaign-scoreboard.mjs`` applies the policy on every
  assembly: an ACTIVE quarantine record (hunter tasks row: ``quarantined:
  true`` + scenario binding + taxonomy cause + owner + unexpired deadline)
  excludes the scenario from the certification calculus WITH reason —
  ``certification.excluded`` + ``gate_summary`` — while its rows stay on the
  board; invalid/expired records are NOT honored (fail closed, the scenario
  keeps denying); mixed verdicts inside a campaign are a ``flake_signal``
  blocker (both recorded — never best-of-N); ``rerun_bound_exceeded`` and
  ``pass_laundering_risk`` violations police the diagnostic re-run bound and
  ``--runs`` cherry-picking.
- ``scripts/qe/lib/gate.mjs --exclusions-from`` carries the exclusions into
  the acceptance payload's ``verdict_summary`` and refuses an exclusion
  missing id/reason/owner/deadline (exit 3) — exclusions ALWAYS carry reasons.

Written policy: skills/qe/refs/campaign-flake-policy.md. Unit-level engine
tests: scripts/qe/runner/test/th21-flake-policy.test.mjs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.qe.test_campaign_scoreboard import (
    Ledger,
    _STUB_INDEX,
    _envelope,
    _run_cli,
    _write_stub,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE = _REPO_ROOT / "scripts" / "qe" / "lib" / "gate.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

_FUTURE = "2030-01-01T00:00:00.000Z"
_PAST = "2020-01-01T00:00:00.000Z"


def _quarantine(led: Ledger, scenario_id: str, *, owner: str | None = "alice",
                cause: str = "env", expires: str | None = _FUTURE,
                status: str = "blocked", **body_extra) -> str:
    """A hunter quarantine record — the ledger tasks row the gate consumes."""
    body = {
        "quarantined": True,
        "scenario_id": scenario_id,
        "cause": cause,
        "flake_rate": 0.12,
        "proposed_fix": "pin TZ in scenario frontmatter",
        **body_extra,
    }
    if owner is not None:
        body["owner"] = owner
    if expires is not None:
        body["quarantine_expires"] = expires
    return led._row("tasks", {
        "project_id": led.project_id,
        "title": f"Flake root-cause ({cause})",
        "status": status,
        "assignee_skill": f"flaky-test-hunter:{cause}",
        "body": json.dumps(body),
    })


def _passing(led: Ledger, name: str) -> str:
    sid = led.scenario(name)
    rid = led.run(sid)
    led.manifest(rid, sid, name)
    led.verdict(rid, "PASS", "acceptance-test-reviewer", "all assertions satisfied")
    return sid


def _run_gate(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", "")}
    return subprocess.run(
        ["node", str(_GATE), *args],
        capture_output=True, text=True, cwd=str(tmp_path), env=env, timeout=60,
    )


# --- exclusion honored: cannot silently DENY -----------------------------------


def test_quarantined_deny_is_excluded_with_reason_and_campaign_certifies(tmp_path):
    """A known-flaky FAIL under a VALID quarantine (owner+deadline+taxonomy
    cause) no longer denies the campaign — but only excluded-WITH-REASON:
    the row stays on the board, the exclusion is itemized in
    certification.excluded and gate_summary, and TH-6's per-scenario flake
    history is attached."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    _passing(led, "S1")
    sid2 = led.scenario("S2")
    rid2 = led.run(sid2, status="failed")
    led.manifest(rid2, sid2, "S2", claim="FAIL")
    led.verdict(rid2, "FAIL", "acceptance-test-reviewer", "TZ-dependent assertion flipped")
    _quarantine(led, sid2)

    env = _envelope(tmp_path, stub)
    assert env["certification"]["disposition"] == "certified"
    # the row is NOT dropped — verbatim 4-key shape, FAIL still visible
    rows = {r["id"]: r for r in env["scoreboard"]}
    assert sorted(rows["S2"].keys()) == ["evidence_ok", "executor_claim", "grade", "id"]
    assert rows["S2"]["grade"] == "FAIL"
    # the exclusion always carries reason + owner + deadline + cause
    excluded = env["certification"]["excluded"]
    assert [e["id"] for e in excluded] == ["S2"]
    assert excluded[0]["owner"] == "alice"
    assert excluded[0]["cause"] == "env"
    assert excluded[0]["deadline"] == _FUTURE
    assert excluded[0]["reason"].strip()
    assert excluded[0]["observed_grades"] == ["FAIL"]
    # visible wherever the disposition is
    assert "excluded-with-reason" in env["certification"]["gate_summary"]
    assert "owner=alice" in env["certification"]["gate_summary"]
    # quarantine skipped the classification fork — no unclassified blocker
    assert env["findings"]["unclassified"] == []
    # TH-6 flake history per stable scenario_id, consumed at the gate
    assert env["flake_policy"]["history"]["S2"]["runs"] == 1
    assert env["flake_policy"]["quarantine"]["active"][0]["scenario"] == "S2"


def test_quarantine_missing_owner_is_not_honored(tmp_path):
    """Fail-closed: a quarantine record without an owner is INVALID — the
    scenario keeps denying the campaign, and the refusal is reported."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S2")
    rid = led.run(sid, status="failed")
    led.manifest(rid, sid, "S2", claim="FAIL")
    led.verdict(rid, "FAIL", "acceptance-test-reviewer", "[scenario-defect] flaky selector")
    _quarantine(led, sid, owner=None)

    env = _envelope(tmp_path, stub)
    assert env["certification"]["disposition"] == "not-certified"
    assert env["certification"]["excluded"] == []
    invalid = env["flake_policy"]["quarantine"]["invalid"]
    assert len(invalid) == 1
    assert any("owner" in p for p in invalid[0]["problems"])
    assert any("non-PASS" in b for b in env["certification"]["blockers"])


def test_expired_quarantine_is_not_honored(tmp_path):
    """An expired quarantine is dead: the scenario re-enters the gate and the
    expiry is reported (the hunter auto-reopens expired quarantines)."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S2")
    rid = led.run(sid, status="failed")
    led.manifest(rid, sid, "S2", claim="FAIL")
    led.verdict(rid, "FAIL", "acceptance-test-reviewer", "[scenario-defect] flaky selector")
    _quarantine(led, sid, expires=_PAST)

    env = _envelope(tmp_path, stub)
    assert env["certification"]["disposition"] == "not-certified"
    assert env["certification"]["excluded"] == []
    expired = env["flake_policy"]["quarantine"]["expired"]
    assert len(expired) == 1
    assert any("expired" in p for p in expired[0]["problems"])


# --- exclusion is symmetric: cannot silently PASS either ------------------------


def test_quarantined_pass_is_excluded_not_counted(tmp_path):
    """A quarantined scenario's PASS is excluded too (counting passes while
    excluding failures would itself be laundering) — and a fully-quarantined
    campaign cannot certify vacuously."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = _passing(led, "S3")
    _quarantine(led, sid)

    env = _envelope(tmp_path, stub)
    assert env["certification"]["disposition"] == "not-certified"
    assert any("all rows excluded by quarantine" in b for b in env["certification"]["blockers"])
    assert env["certification"]["excluded"][0]["observed_grades"] == ["PASS"]
    assert env["summary"]["excluded"] == 1


def test_diagnostic_rerun_records_both_verdicts_and_signals_flake(tmp_path):
    """A diagnostic re-run's PASS never replaces the FAIL: both rows stand on
    the scoreboard, and the mixed outcome is a flake-signal blocker naming
    the hunter — the gate is never best-of-N."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S4")
    rid1 = led.run(sid, status="failed")
    led.manifest(rid1, sid, "S4", claim="FAIL")
    led.verdict(rid1, "FAIL", "acceptance-test-reviewer", "[scenario-defect] raced the WS connect")
    rid2 = led.run(sid)
    led.manifest(rid2, sid, "S4")
    led.verdict(rid2, "PASS", "acceptance-test-reviewer", "green on diagnostic re-run")

    env = _envelope(tmp_path, stub)
    grades = sorted(r["grade"] for r in env["scoreboard"] if r["id"] == "S4")
    assert grades == ["FAIL", "PASS"]  # BOTH verdicts recorded
    assert env["certification"]["disposition"] == "not-certified"
    signal_blockers = [b for b in env["certification"]["blockers"] if b.startswith("flake signal on S4")]
    assert signal_blockers and "flaky-test-hunter" in signal_blockers[0]
    signals = env["flake_policy"]["flake_signals"]
    assert len(signals) == 1 and sorted(signals[0]["run_ids"]) == sorted([rid1, rid2])


def test_rerun_bound_exceeded_is_a_violation(tmp_path):
    """More than 1 original + 2 diagnostic runs of one scenario is
    pass-laundering even when all green — rerun_bound_exceeded blocks."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S5")
    for _ in range(4):
        rid = led.run(sid)
        led.manifest(rid, sid, "S5")
        led.verdict(rid, "PASS", "acceptance-test-reviewer", "ok")

    env = _envelope(tmp_path, stub)
    kinds = [v["kind"] for v in env["violations"]]
    assert "rerun_bound_exceeded" in kinds
    assert env["certification"]["disposition"] == "not-certified"


def test_runs_selection_omitting_deny_sibling_is_pass_laundering(tmp_path):
    """Assembling with --runs pinned to the passing re-run while the same-day
    FAIL sits outside the selection is flagged — the omission cannot launder
    the verdict."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S6")
    rid_fail = led.run(sid, status="failed")
    led.manifest(rid_fail, sid, "S6", claim="FAIL")
    led.verdict(rid_fail, "FAIL", "acceptance-test-reviewer", "[scenario-defect] flaky")
    rid_pass = led.run(sid)
    led.manifest(rid_pass, sid, "S6")
    led.verdict(rid_pass, "PASS", "acceptance-test-reviewer", "green this time")

    env = _envelope(tmp_path, stub, "--runs", rid_pass)
    launder = [v for v in env["violations"] if v["kind"] == "pass_laundering_risk"]
    assert len(launder) == 1
    assert launder[0]["id"] == "S6" and launder[0]["run_id"] == rid_fail
    assert env["certification"]["disposition"] == "not-certified"


# --- the acceptance payload: gate.mjs --exclusions-from --------------------------


def test_gate_exclusions_from_appends_the_reason_clause(tmp_path):
    """The exclusions reach the acceptance payload: gate.mjs --exclusions-from
    appends the canonical excluded-with-reason clause (id, cause, owner,
    deadline, reason) to verdict_summary — the 8-field wire contract's
    existing field, no new fields."""
    stub_pkg = _write_stub(tmp_path / "node_modules", "wicked-ledger", _STUB_INDEX)
    assert stub_pkg.exists()
    led = Ledger(tmp_path)
    _passing(led, "S1")
    sid2 = led.scenario("S7")
    rid2 = led.run(sid2, status="failed")
    led.manifest(rid2, sid2, "S7", claim="FAIL")
    led.verdict(rid2, "FAIL", "acceptance-test-reviewer", "TZ flake")
    _quarantine(led, sid2)

    # assemble the envelope through the real scoreboard CLI
    out = tmp_path / "scoreboard.json"
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    proc = _run_cli(tmp_path, stub, "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    envelope = json.loads(out.read_text(encoding="utf-8"))
    assert envelope["certification"]["excluded"], "quarantine must be honored before the gate step"

    gate = _run_gate(
        tmp_path,
        "--project-id", led.project_id,
        "--run-id", rid2,
        "--verdict", "PASS",
        "--verdict-summary", envelope["certification"]["gate_summary"],
        "--exclusions-from", str(out),
        "--dry-run",
    )
    assert gate.returncode == 0, f"stdout={gate.stdout}\nstderr={gate.stderr}"
    result = json.loads(gate.stdout)
    summary = result["verdict_summary"]
    assert "quarantined excluded-with-reason (1)" in summary
    assert "owner=alice" in summary and "cause=env" in summary and _FUTURE in summary


def test_gate_refuses_exclusions_without_reasons(tmp_path):
    """Fail-closed at the payload seam: an exclusion missing owner (or reason,
    or deadline) exits 3 — a reason-less exclusion can never reach the
    acceptance payload."""
    bad = tmp_path / "scoreboard.json"
    bad.write_text(json.dumps({
        "certification": {
            "excluded": [{"id": "S7", "cause": "env", "deadline": _FUTURE, "reason": "flaky"}],  # no owner
        },
    }), encoding="utf-8")
    gate = _run_gate(
        tmp_path,
        "--project-id", "p", "--run-id", "r", "--verdict", "PASS",
        "--verdict-summary", "s", "--exclusions-from", str(bad), "--dry-run",
    )
    assert gate.returncode == 3
    assert "EXCLUSION_MISSING_REASON" in gate.stderr
    assert "owner" in gate.stderr
