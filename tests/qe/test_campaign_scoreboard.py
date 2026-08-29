"""Campaign grading has no self-grade path (TH-10 / RECON-TEST-HARNESS test-R10).

Exercises scripts/qe/lib/campaign-scoreboard.mjs — the deterministic glue that
assembles the campaign scoreboard in the campaign-proven verbatim shape
``{id, grade, executor_claim, evidence_ok}`` — through its REAL CLI surface
(``node campaign-scoreboard.mjs --json`` as a subprocess against a tmp ledger
root), the same posture as tests/e2e/test_e2e_gate_cli.py.

What is pinned here (the TH-10 acceptance criteria):

- **No self-graded campaign verdicts are possible in the flow**: verdict rows
  written by executor identities (``qe-runner/executor-claim``,
  ``*executor*``, the ``test-designer`` dev-loop) are refused as grade
  sources and surfaced as ``self_grade_attempt`` violations; a run without an
  isolated-reviewer verdict grades UNGRADED and blocks certification.
- **The scoreboard shape is validated against wicked-ledger manifest 2.1's
  scenario-evidence shape**: ``executor_claim`` derives from
  ``scenario_evidence.status`` (the field the ledger contract marks "the
  EXECUTOR'S CLAIM ... never the verdict of record"); ``evidence_ok`` is
  ``validateManifest()`` + the major floor, and validator-unavailable fails
  CLOSED (published wicked-ledger 0.3.0 predates validateManifest — the
  floor rides the XC-4 release wave).
- **Findings mirror out**: the ``[scenario-defect]`` / ``[product-finding]``
  reason-tag fork lands in the envelope's findings buckets; product findings
  mirror to ledger ``tasks`` rows idempotently (``--mirror-tasks``).
- **Certification terminates**: ``certification.disposition`` is always
  exactly ``certified`` or ``not-certified`` — never a third, pending state.

Hermetic: wicked-ledger is stubbed via WICKED_LEDGER_PKG_DIR (a minimal
package dir implementing the manifest-2.1 validateManifest contract — the
same override the TH-6 wiring uses), so the suite needs node but no npm
install. Skips (never fake-passes) when node is missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "qe" / "lib" / "campaign-scoreboard.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

# --- the wicked-ledger stub (manifest-2.1 floor of validateManifest) ---------

_STUB_INDEX = r"""
export const MANIFEST_VERSION = "2.1.0";
export const CLAIM_LEVELS = Object.freeze(["certified", "machinery-verified", "skipped"]);
export const VERDICT_VALUES = Object.freeze(["PASS", "FAIL", "PARTIAL", "CONDITIONAL", "INCONCLUSIVE", "N-A", "SKIP"]);
const RANK = { certified: 2, "machinery-verified": 1, skipped: 0 };

export function validateManifest(m) {
  const violations = [];
  const bad = (field, message) => violations.push({ field, message });
  if (!m || typeof m !== "object") { bad("$", "not an object"); return { ok: false, violations }; }
  for (const k of ["manifest_version","run_id","project_id","scenario_id","scenario_name","started_at","finished_at","duration_ms","status","verdict","environment","artifacts"]) {
    if (!(k in m)) bad(k, `missing required field '${k}'`);
  }
  if (m.verdict && !VERDICT_VALUES.includes(m.verdict.value)) bad("verdict.value", "invalid");
  const se = m.scenario_evidence;
  if (se !== undefined) {
    for (const k of ["scenario","status","claim_level"]) if (!(k in se)) bad(`scenario_evidence.${k}`, `missing '${k}'`);
    if (se.claim_level !== undefined && !CLAIM_LEVELS.includes(se.claim_level)) bad("scenario_evidence.claim_level", "invalid claim_level");
    if (se.status !== undefined && !VERDICT_VALUES.includes(se.status)) bad("scenario_evidence.status", "invalid status");
    if (Array.isArray(se.legs) && se.claim_level in RANK) {
      for (const leg of se.legs) {
        if (leg && leg.claim_level in RANK && RANK[se.claim_level] > RANK[leg.claim_level]) {
          bad("scenario_evidence.claim_level", `stronger than leg '${leg.leg}' — certify the journey, not the proxy`);
        }
      }
    }
  }
  return { ok: violations.length === 0, violations };
}

// Minimal DomainStore stand-in: JSON-row writes only (what --mirror-tasks needs).
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
export function createDomainStore({ root }) {
  return {
    create(table, payload) {
      const id = "t-" + Math.random().toString(36).slice(2, 10);
      const record = { id, ...payload, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), deleted: 0 };
      mkdirSync(join(root, table), { recursive: true });
      writeFileSync(join(root, table, id + ".json"), JSON.stringify(record), "utf8");
      return record;
    },
  };
}
"""

# A "published 0.3.0" stand-in: resolvable, but PREDATES validateManifest.
_OLD_STUB_INDEX = "export const MANIFEST_VERSION = \"2.0.0\";\nexport function buildManifest() {}\n"


def _write_stub(tmp_path: Path, name: str, index_source: str) -> Path:
    pkg = tmp_path / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text(
        json.dumps({"name": "wicked-ledger", "version": "0.0.0-test", "type": "module", "main": "index.mjs"}),
        encoding="utf-8",
    )
    (pkg / "index.mjs").write_text(index_source, encoding="utf-8")
    return pkg


# --- ledger-root fixture builders ---------------------------------------------


def _iso(minute: int) -> str:
    return f"2026-08-29T12:{minute:02d}:00.000Z"


class Ledger:
    """Builds a tmp `.wicked-qe/` DomainStore-shaped JSON tree + evidence dirs."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.root = repo_root / ".wicked-qe"
        for table in ("projects", "scenarios", "runs", "verdicts", "tasks"):
            (self.root / table).mkdir(parents=True, exist_ok=True)
        self.project_id = self._row("projects", {"name": "campaign-target"})

    def _row(self, table: str, payload: dict) -> str:
        rid = str(uuid.uuid4())
        record = {"id": rid, "created_at": _iso(0), "updated_at": _iso(0), "deleted": 0, **payload}
        (self.root / table / f"{rid}.json").write_text(json.dumps(record), encoding="utf-8")
        return rid

    def scenario(self, name: str) -> str:
        return self._row("scenarios", {"project_id": self.project_id, "name": name, "format_version": "1"})

    def run(self, scenario_id: str, status: str = "passed") -> str:
        run_id = str(uuid.uuid4())
        record = {
            "id": run_id, "project_id": self.project_id, "scenario_id": scenario_id,
            "started_at": _iso(1), "finished_at": _iso(2), "status": status,
            "evidence_path": f".wicked-qe/evidence/{run_id}",
            "created_at": _iso(1), "updated_at": _iso(2), "deleted": 0,
        }
        (self.root / "runs" / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
        (self.root / "evidence" / run_id).mkdir(parents=True, exist_ok=True)
        return run_id

    def verdict(self, run_id: str, verdict: str, reviewer: str, reason: str = "", minute: int = 3) -> str:
        return self._row("verdicts", {
            "run_id": run_id, "verdict": verdict, "reviewer": reviewer, "reason": reason,
            "created_at": _iso(minute), "updated_at": _iso(minute),
        })

    def manifest(self, run_id: str, scenario_id: str, name: str, *,
                 claim: str = "PASS", claim_level: str = "certified",
                 legs: list | None = None, notes: str = "wire+db+readback consistent",
                 omit_scenario_evidence: bool = False) -> None:
        m = {
            "manifest_version": "2.1.0", "run_id": run_id, "project_id": self.project_id,
            "scenario_id": scenario_id, "scenario_name": name,
            "started_at": _iso(1), "finished_at": _iso(2), "duration_ms": 60000,
            "status": "passed",
            "verdict": {"value": claim, "reviewer": "qe-runner/executor-claim",
                        "reason": "executor claim — grading via qe accept trio", "recorded_at": _iso(2)},
            "environment": {"os": "darwin", "qe_version": "0.0.0-test"},
            "artifacts": [],
        }
        if not omit_scenario_evidence:
            se = {"scenario": name, "status": claim, "claim_level": claim_level, "notes": notes}
            if legs is not None:
                se["legs"] = legs
            m["scenario_evidence"] = se
        (self.root / "evidence" / run_id / "manifest.json").write_text(json.dumps(m), encoding="utf-8")


def _run_cli(repo_root: Path, stub_dir: Path | None, *extra: str) -> subprocess.CompletedProcess:
    env = {"PATH": __import__("os").environ.get("PATH", "")}
    if stub_dir is not None:
        env["WICKED_LEDGER_PKG_DIR"] = str(stub_dir)
    return subprocess.run(
        ["node", str(_SCRIPT), "--repo-root", str(repo_root), "--json", *extra],
        capture_output=True, text=True, cwd=str(repo_root), env=env, timeout=60,
    )


def _envelope(repo_root: Path, stub_dir: Path | None, *extra: str) -> dict:
    proc = _run_cli(repo_root, stub_dir, *extra)
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    return json.loads(proc.stdout)


# --- tests ----------------------------------------------------------------------


def test_scoreboard_row_is_the_verbatim_campaign_shape(tmp_path):
    """Graded PASS on a valid 2.1 bundle → the exact 4-key campaign row, with
    executor_claim derived from manifest-2.1 scenario_evidence.status."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S1")
    rid = led.run(sid)
    led.manifest(rid, sid, "S1")
    led.verdict(rid, "PASS", "acceptance-test-reviewer", "all assertions satisfied")

    env = _envelope(tmp_path, stub)
    assert len(env["scoreboard"]) == 1
    row = env["scoreboard"][0]
    # verbatim shape: these four keys and NOTHING else (studio-campaign-results.json)
    assert sorted(row.keys()) == ["evidence_ok", "executor_claim", "grade", "id"]
    assert row["id"] == "S1"
    assert row["grade"] == "PASS"
    assert row["evidence_ok"] is True
    # executor_claim ← scenario_evidence.status (+claim_level), the manifest-2.1 field
    assert row["executor_claim"].startswith("PASS [certified]")
    assert env["certification"]["disposition"] == "certified"
    assert env["validator"] == "wicked-ledger"


def test_executor_claim_never_becomes_the_grade(tmp_path):
    """A run whose ONLY verdicts are executor identities grades UNGRADED, each
    refused row is a self_grade_attempt violation, and certification is denied
    — no self-graded campaign verdict is possible in the flow."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S2")
    rid = led.run(sid)
    led.manifest(rid, sid, "S2")
    led.verdict(rid, "PASS", "qe-runner/executor-claim", "looked fine to me", minute=3)
    led.verdict(rid, "PASS", "acceptance-test-executor", "command exited 0", minute=4)
    led.verdict(rid, "PASS", "qe-test-designer", "dev-loop fast path", minute=5)

    env = _envelope(tmp_path, stub)
    row = env["scoreboard"][0]
    assert row["grade"] == "UNGRADED"  # never PASS from an executor identity
    kinds = [v["kind"] for v in env["violations"]]
    assert kinds.count("self_grade_attempt") == 3
    assert env["certification"]["disposition"] == "not-certified"
    assert any("UNGRADED" in b for b in env["certification"]["blockers"])


def test_manifest_verdict_block_never_sources_a_grade(tmp_path):
    """The manifest is EXECUTOR-authored: even when its verdict block claims a
    reviewer identity ('acceptance-test-reviewer'), it never becomes the grade
    — grades are born in ledger verdicts rows only. The impersonation is
    flagged and certification is denied."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S2b")
    rid = led.run(sid)
    led.manifest(rid, sid, "S2b")
    # executor forges a reviewer identity into its own manifest verdict block
    mpath = led.root / "evidence" / rid / "manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    m["verdict"] = {"value": "PASS", "reviewer": "acceptance-test-reviewer",
                    "reason": "looks great", "recorded_at": _iso(2)}
    mpath.write_text(json.dumps(m), encoding="utf-8")
    # no verdicts row at all

    env = _envelope(tmp_path, stub)
    row = env["scoreboard"][0]
    assert row["grade"] == "UNGRADED"  # never PASS from an executor-authored file
    assert any(v["kind"] == "manifest_verdict_impersonation" for v in env["violations"])
    assert env["certification"]["disposition"] == "not-certified"


def test_empty_ledger_is_not_certified(tmp_path):
    """Certification terminates on the empty edge too: zero runs → disposition
    is 'not-certified' (never pending, never vacuously certified)."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    Ledger(tmp_path)  # tables exist, no rows

    env = _envelope(tmp_path, stub)
    assert env["scoreboard"] == []
    assert env["certification"]["disposition"] == "not-certified"
    assert any("no scoreboard rows" in b for b in env["certification"]["blockers"])


def test_schema_fail_bundle_cannot_carry_a_pass(tmp_path):
    """Honest-cap violation (overall certified over a machinery-verified leg)
    → evidence_ok false; a PASS rendered on it is a graded_invalid_bundle
    violation (SCHEMA-CONTRACT: schema-fail grades INCONCLUSIVE)."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S3")
    rid = led.run(sid)
    led.manifest(rid, sid, "S3", claim_level="certified",
                 legs=[{"leg": "acceptance", "claim_level": "machinery-verified", "reason": "API-substituted"}])
    led.verdict(rid, "PASS", "acceptance-test-reviewer", "rubber stamp")

    env = _envelope(tmp_path, stub)
    row = env["scoreboard"][0]
    assert row["evidence_ok"] is False
    assert any(v["kind"] == "graded_invalid_bundle" for v in env["violations"])
    assert env["certification"]["disposition"] == "not-certified"


def test_validator_unavailable_fails_closed(tmp_path):
    """A resolvable wicked-ledger that PREDATES validateManifest (the published
    0.3.0 shape) → evidence_ok false everywhere, envelope says so, and a PASS
    grade on top is flagged — never silently certified."""
    old_stub = _write_stub(tmp_path, "old-ledger-stub", _OLD_STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S4")
    rid = led.run(sid)
    led.manifest(rid, sid, "S4")
    led.verdict(rid, "PASS", "acceptance-test-reviewer", "fine")

    env = _envelope(tmp_path, old_stub)
    assert env["validator"] == "unavailable"
    assert env["scoreboard"][0]["evidence_ok"] is False
    assert any(v["kind"] == "graded_invalid_bundle" for v in env["violations"])
    assert env["certification"]["disposition"] == "not-certified"


def test_fork_classification_and_termination(tmp_path):
    """The scenario-defect vs product-finding fork: tagged non-PASS grades land
    in their buckets, untagged non-PASS blocks certification, and disposition
    is always one of exactly two terminal values."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    cases = {
        "S5": ("FAIL", "[scenario-defect] data-testid drifted: connection-status → connection-dot"),
        "S6": ("FAIL", "[product-finding] 409 duplicate not surfaced in-modal"),
        "S7": ("FAIL", "no tag — reviewer forgot to classify"),
    }
    for name, (verdict, reason) in cases.items():
        sid = led.scenario(name)
        rid = led.run(sid, status="failed")
        led.manifest(rid, sid, name, claim="FAIL")
        led.verdict(rid, verdict, "acceptance-test-reviewer", reason)

    env = _envelope(tmp_path, stub)
    f = env["findings"]
    assert [d["id"] for d in f["scenario_defects"]] == ["S5"]
    assert "re-author" in f["scenario_defects"][0]["next"]
    assert [d["id"] for d in f["product_findings"]] == ["S6"]
    mirror = f["product_findings"][0]["mirror"]
    assert mirror["title"].startswith("[product-finding] S6:")
    assert mirror["status"] == "open"
    assert "GitHub issue" in mirror["body"]  # mirrors OUT, campaign does not expand
    assert [d["id"] for d in f["unclassified"]] == ["S7"]
    # certification TERMINATES: exactly one of two dispositions, never pending
    assert env["certification"]["disposition"] in ("certified", "not-certified")
    assert env["certification"]["disposition"] == "not-certified"
    assert any("unclassified" in b for b in env["certification"]["blockers"])


def test_product_findings_mirror_to_ledger_tasks_idempotently(tmp_path):
    """--mirror-tasks writes a ledger tasks row per product finding and skips
    already-mirrored titles on re-run."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S8")
    rid = led.run(sid, status="failed")
    led.manifest(rid, sid, "S8", claim="FAIL")
    led.verdict(rid, "FAIL", "acceptance-test-reviewer", "[product-finding] health rail shows stale roster")

    env1 = _envelope(tmp_path, stub, "--mirror-tasks")
    assert env1["mirror"]["ok"] is True and env1["mirror"]["mirrored"] == 1
    tasks = list((led.root / "tasks").glob("*.json"))
    assert len(tasks) == 1
    task = json.loads(tasks[0].read_text(encoding="utf-8"))
    assert task["title"].startswith("[product-finding] S8:")
    assert task["project_id"] == led.project_id
    assert task["status"] == "open"

    env2 = _envelope(tmp_path, stub, "--mirror-tasks")
    assert env2["mirror"]["mirrored"] == 0  # idempotent
    assert len(list((led.root / "tasks").glob("*.json"))) == 1


def test_grades_stay_inside_the_ledger_verdict_taxonomy(tmp_path):
    """Scoreboard grades are ledger VERDICT_VALUES or UNGRADED — the shape
    stays consistent with the manifest-2.1 contract's enum."""
    verdict_values = {"PASS", "FAIL", "PARTIAL", "CONDITIONAL", "INCONCLUSIVE", "N-A", "SKIP"}
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    led = Ledger(tmp_path)
    for i, (verdict, reviewer) in enumerate([
        ("PASS", "acceptance-test-reviewer"),
        ("INCONCLUSIVE", "campaign-grading/schema-preflight"),
        (None, None),  # ungraded
    ]):
        sid = led.scenario(f"T{i}")
        rid = led.run(sid)
        led.manifest(rid, sid, f"T{i}")
        if verdict:
            led.verdict(rid, verdict, reviewer, "[scenario-defect] bundle rejected" if verdict != "PASS" else "ok")

    env = _envelope(tmp_path, stub)
    assert len(env["scoreboard"]) == 3
    for row in env["scoreboard"]:
        assert row["grade"] in verdict_values | {"UNGRADED"}


def test_validate_only_exit_codes(tmp_path):
    """--validate-only: 0 conformant · 5 schema-fail · 6 validator unavailable
    (the pre-dispatch preflight the grading playbook mandates)."""
    stub = _write_stub(tmp_path, "ledger-stub", _STUB_INDEX)
    old_stub = _write_stub(tmp_path, "old-ledger-stub", _OLD_STUB_INDEX)
    led = Ledger(tmp_path)
    sid = led.scenario("S9")
    good = led.run(sid)
    led.manifest(good, sid, "S9")
    bad = led.run(sid)
    led.manifest(bad, sid, "S9", claim_level="certified",
                 legs=[{"leg": "acceptance", "claim_level": "skipped"}])

    ok = _run_cli(tmp_path, stub, "--validate-only", str(led.root / "evidence" / good))
    assert ok.returncode == 0, ok.stderr
    fail = _run_cli(tmp_path, stub, "--validate-only", str(led.root / "evidence" / bad))
    assert fail.returncode == 5
    assert "claim_level" in fail.stdout
    unavailable = _run_cli(tmp_path, old_stub, "--validate-only", str(led.root / "evidence" / good))
    assert unavailable.returncode == 6
