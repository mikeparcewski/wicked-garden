#!/usr/bin/env python3
"""Phase-0 falsification harness.

For each target repo: detect -> emit -> stage honest+fabricated claim
fixtures -> run the EMITTED lint -> record a per-repo verdict. Writes
evidence + a verdict summary. Zero wicked-garden runtime touches the
target repo: only the emitted stdlib lint runs there.

Gate: >= 2/3 real repos PASS, where PASS =
  (a) test_command detected unaided (source=detected, conf>=0.5), AND
  (b) emitted lint passes an honest claim, AND
  (c) emitted lint catches a missing-evidence fabricated claim, AND
  (d) emitted lint catches a failure-evidence fabricated claim.

usage: run_probe.py <repo1> [<repo2> ...]
Stdlib-only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detect as detect_mod  # noqa: E402
import emit as emit_mod      # noqa: E402

EVID = HERE / "evidence"
EVID.mkdir(exist_ok=True)


def _run(cmd, cwd=None, timeout=120):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"<timeout after {timeout}s>"
    except FileNotFoundError as e:
        return 127, f"<not found: {e}>"
    except Exception as e:  # noqa: BLE001
        return 1, f"<error: {e}>"


def _real_pass_evidence(ecosystem: str, repo_root: Path):
    """Produce REAL evidence by running a minimal passing test in the repo's
    runner family. Returns (text, is_real, note). Falls back to a clearly
    labelled synthetic pass when the toolchain/runner is unavailable —
    the lint can't tell provenance; it only reads content."""
    tmp = Path(tempfile.mkdtemp(prefix="wgprobe-"))
    try:
        if ecosystem == "node":
            spec = tmp / "wgprobe.test.mjs"
            spec.write_text(
                "import { test, expect } from 'vitest'\n"
                "test('wgprobe', () => { expect(1+1).toBe(2) })\n"
            )
            rc, out = _run(["npx", "vitest", "run", str(spec)],
                           cwd=str(repo_root), timeout=120)
            if rc == 0 and ("pass" in out.lower()):
                return out[-1500:], True, "real vitest run"
            return ("Test Files  1 passed (1)\n Tests  1 passed (1)\n"
                    "(synthetic: real vitest run unavailable rc=%s)" % rc), False, \
                   f"synthetic; vitest rc={rc}"
        if ecosystem == "python":
            t = tmp / "test_wgprobe.py"
            t.write_text("def test_wgprobe():\n    assert 1 + 1 == 2\n")
            rc, out = _run([sys.executable, "-m", "pytest", "-q", str(t)],
                           cwd=str(repo_root), timeout=90)
            if rc == 0 and ("passed" in out.lower()):
                return out[-1500:], True, "real pytest run"
            # fall back to a real plain-python assertion run (always available)
            rc2, out2 = _run([sys.executable, "-c",
                              "assert 1+1==2; print('1 passed (plain python assert OK)')"],
                             timeout=30)
            if rc2 == 0:
                return out2 + f"\n(pytest unavailable rc={rc}; real python assert used)", \
                       True, "real python assert (pytest unavailable)"
            return "1 passed\n(synthetic)", False, "synthetic"
        if ecosystem == "go":
            rc, out = _run(["go", "test", "./..."], cwd=str(repo_root), timeout=120)
            if rc == 0:
                return out[-1500:] or "ok\tPASS\n", True, "real go test"
            return "ok  PASS\n(synthetic: go rc=%s)" % rc, False, f"synthetic; go rc={rc}"
        if ecosystem == "rust":
            rc, out = _run(["cargo", "test"], cwd=str(repo_root), timeout=180)
            if rc == 0:
                return out[-1500:] or "test result: ok. 1 passed\n", True, "real cargo test"
            return "test result: ok. 1 passed\n(synthetic rc=%s)" % rc, False, f"synthetic; cargo rc={rc}"
        return "1 passed\n(synthetic; unknown ecosystem)", False, "synthetic"
    finally:
        pass  # leave tmp; harmless


def probe_repo(repo_path: str) -> dict:
    root = Path(repo_path).resolve()
    name = root.name
    bindings = detect_mod.detect(str(root))
    (EVID / f"{name}.bindings.json").write_text(json.dumps(bindings, indent=2))

    eco = bindings["test_command"].get("ecosystem")
    tc = bindings["test_command"]
    detected = tc.get("source") == detect_mod.DETECTED and tc.get("value") and tc.get("confidence", 0) >= 0.5

    # emit the lint into an isolated staging dir (NOT the repo tree)
    stage = EVID / f"{name}.stage"
    if stage.exists():
        for p in stage.rglob("*"):
            if p.is_file():
                p.unlink()
    stage.mkdir(parents=True, exist_ok=True)
    lint_path = emit_mod.emit(bindings, str(stage))

    # build fixtures: a fake "repo root" = stage, with an evidence sink
    sink = stage / bindings["evidence_sink"]["value"]
    sink.mkdir(parents=True, exist_ok=True)

    # honest evidence (real where possible)
    ev_text, ev_real, ev_note = _real_pass_evidence(eco, root)
    (sink / "honest-tests.txt").write_text(ev_text)
    # failure evidence for the contradiction case
    (sink / "failing-tests.txt").write_text(
        "FAIL src/foo.test\n 2 failed | 1 passed\nError: expected 2 received 3\nexit code 1\n"
    )

    honest_doc = stage / "honest.build.md"
    honest_doc.write_text(
        "---\nphase: build\nclaims:\n"
        "  - id: c-honest\n    evidence: honest-tests\n"
        '    text: "tests pass: 1/1 passing, exit 0"\n'
        "---\n# honest\n"
    )
    fab_missing_doc = stage / "fab-missing.build.md"
    fab_missing_doc.write_text(
        "---\nphase: build\nclaims:\n"
        "  - id: c-fab-missing\n    evidence: tests-that-were-never-run\n"
        '    text: "all tests pass, build clean, ready to merge"\n'
        "---\n# fabricated: evidence file does not exist\n"
    )
    fab_fail_doc = stage / "fab-fail.build.md"
    fab_fail_doc.write_text(
        "---\nphase: build\nclaims:\n"
        "  - id: c-fab-fail\n    evidence: failing-tests\n"
        '    text: "tests pass — all green"\n'
        "---\n# fabricated: evidence actually shows failure\n"
    )

    def run_lint(doc):
        return _run([sys.executable, lint_path, "--repo-root", str(stage),
                     "--claims-file", str(doc)], timeout=30)

    h_rc, h_out = run_lint(honest_doc)
    fm_rc, fm_out = run_lint(fab_missing_doc)
    ff_rc, ff_out = run_lint(fab_fail_doc)

    (EVID / f"{name}.lint-output.txt").write_text(
        f"$ emitted lint (test_command={tc.get('value')})\n\n"
        f"--- honest (expect exit 0) -> rc={h_rc} ---\n{h_out}\n"
        f"--- fabricated/missing (expect exit 1) -> rc={fm_rc} ---\n{fm_out}\n"
        f"--- fabricated/failure (expect exit 1) -> rc={ff_rc} ---\n{ff_out}\n"
    )

    lint_ok = (h_rc == 0) and (fm_rc == 1) and (ff_rc == 1)
    verdict = "PASS" if (detected and lint_ok) else ("FAIL" if not detected else "FAIL")

    return {
        "repo": name,
        "ecosystem": eco,
        "detection": {
            "test_command": tc.get("value"),
            "declared_script": tc.get("declared_script"),
            "source": tc.get("source"),
            "confidence": tc.get("confidence"),
            "ambiguity": tc.get("ambiguity"),
            "hand_correction_needed": not detected,
        },
        "evidence_sink": bindings["evidence_sink"]["value"]
                         + f" ({bindings['evidence_sink']['source']})",
        "claims_surface": bindings["claims_surface"]["value"]
                          + f" ({bindings['claims_surface']['source']})",
        "lint": {
            "honest_exit": h_rc, "expect": 0,
            "fab_missing_exit": fm_rc, "fab_failure_exit": ff_rc,
            "honest_evidence_real": ev_real, "honest_evidence_note": ev_note,
            "behaviour_ok": lint_ok,
        },
        "verdict": verdict,
    }


def main(argv):
    targets = argv or []
    if not targets:
        print("usage: run_probe.py <repo1> [<repo2> ...]", file=sys.stderr)
        return 2
    results = [probe_repo(t) for t in targets]
    passes = sum(1 for r in results if r["verdict"] == "PASS")
    summary = {
        "targets": len(results),
        "passes": passes,
        "gate": "PASS" if passes >= max(2, (len(results) + 1) // 2) else "FAIL",
        "gate_rule": ">=2/3 real repos detect test_command unaided AND emitted lint catches both fabrication shapes",
        "results": results,
    }
    (EVID / "verdict.json").write_text(json.dumps(summary, indent=2))

    print("=" * 70)
    print(f"PHASE-0 VERDICT: {summary['gate']}  ({passes}/{len(results)} repos PASS)")
    print("=" * 70)
    for r in results:
        d = r["detection"]
        l = r["lint"]
        print(f"\n[{r['verdict']}] {r['repo']} ({r['ecosystem']})")
        print(f"   test_command : {d['test_command']}  "
              f"[{d['source']} conf={d['confidence']}]"
              + (f"  AMBIGUITY: {d['ambiguity']}" if d.get('ambiguity') else ""))
        if d.get("declared_script"):
            print(f"   declared     : {d['declared_script']}")
        print(f"   evidence_sink: {r['evidence_sink']}")
        print(f"   claims       : {r['claims_surface']}")
        print(f"   lint exits   : honest={l['honest_exit']}(want 0) "
              f"fab-missing={l['fab_missing_exit']}(want 1) "
              f"fab-failure={l['fab_failure_exit']}(want 1)  ok={l['behaviour_ok']}")
        print(f"   honest-ev    : {'REAL' if l['honest_evidence_real'] else 'synthetic'} "
              f"({l['honest_evidence_note']})")
    print(f"\nevidence dir: {EVID}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
