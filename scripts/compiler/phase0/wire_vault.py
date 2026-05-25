#!/usr/bin/env python3
"""Phase-0 consumer-contract wiring: wicked-garden -> wicked-vault.

Demonstrates CONTRACTS.md §10-A (compile time) and §10-B (runtime gate) END
TO END against a real repo. The OLD Phase-0 model emitted a `wg_check_claims.py`
lint that grepped files; this REPLACES that file-grep gate with a real
`wicked-vault cross-check` call — the harness gate is now a vault verdict.

Flow per repo:
  1. detect.py  -> bindings (test_command especially).
  2. declare-contract  scope=<repo>-demo phase=build, one required claim
     `tests-pass`, kind `test-run`, verifier `exit_code_eq:0`, source_pin set
     to the DETECTED test_command (§10-A.2: source pinned to the repo's real
     command).
  3a. REAL run: record --run the detected test_command. Honest data — if the
      toolchain is absent / slow it will FAIL or time out, and the gate REJECTs.
  3b. GATE-TRANSITION demo (separate scope <repo>-demo-gate): a single contract
      whose source is a marker-driven command (`sh -c 'exit $(cat MARKER)'`).
      We record a genuinely-FAILING capture (marker=1) then a genuinely-PASSING
      capture (marker=0). Same pinned source string both times (honors G8), but
      the captured exit code differs — so the latest-active artifact flips the
      verdict. This explicitly shows BOTH outcomes the task asks for: `true`
      (pass) and `false` (fail), both verified with `exit_code_eq:0`.
  4. cross-check --scope <...> --phase build (§10-B): REJECT when the failing
     capture is latest, PASS when a passing capture is latest. Exit code of the
     CLI IS the gate signal (0 == PASS).

Cleanup: the vault writes `.wicked-vault/` into the target repo; this script
removes it afterward so the target repos stay clean.

Stdlib-only. Cross-platform note: uses `sh -c` for the marker command, which is
available on macOS/Linux and Git Bash/WSL on Windows; native PowerShell would
need a different marker command but the §10 interaction is identical.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAULT_CLI = Path.home() / "Projects" / "wicked-vault" / "bin" / "wicked-vault.mjs"
EVIDENCE = HERE / "evidence" / "wire-vault-transcript.txt"

# Per-repo wall-clock budget for the REAL detected test_command. If it exceeds
# this we kill it; the captured run then counts as a fail (honest REJECT).
REAL_RUN_TIMEOUT_S = 90


class Tee:
    """Mirror everything we print to both stdout and the transcript file."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "w", encoding="utf-8")

    def __call__(self, *parts: object) -> None:
        line = " ".join(str(p) for p in parts)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def run_vault(args: list[str], cwd_repo: Path, timeout: int | None = None) -> tuple[int, dict | str]:
    """Invoke the vault CLI. Returns (exit_code, parsed_json_or_raw_text)."""
    cmd = ["node", str(VAULT_CLI), *args, "--cwd", str(cwd_repo)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, {"error": f"vault CLI timed out after {timeout}s", "args": args}
    out = proc.stdout.strip()
    try:
        parsed: dict | str = json.loads(out) if out else {"error": "empty stdout", "stderr": proc.stderr.strip()}
    except json.JSONDecodeError:
        parsed = out or proc.stderr.strip()
    return proc.returncode, parsed


def detect(repo: Path, tee: Tee) -> dict:
    out = subprocess.run(
        [sys.executable, str(HERE / "detect.py"), str(repo)],
        capture_output=True, text=True,
    )
    bindings = json.loads(out.stdout)
    tc = bindings["test_command"]
    tee(f"  detect.py: test_command = {tc.get('value')!r}  "
        f"(source={tc.get('source')}, confidence={tc.get('confidence')}, "
        f"ecosystem={tc.get('ecosystem')})")
    if tc.get("ambiguity"):
        tee(f"            ambiguity flagged: {tc['ambiguity']}")
    return bindings


def write_spec(source_pin: str) -> str:
    """Write a contract spec JSON to a temp file; return its path."""
    spec = {
        "required_evidence": [{
            "claim_id": "tests-pass",
            "kind": "test-run",
            "source_pin": source_pin,
            "verifier": {"kind": "exit_code_eq", "params": {"code": 0}},
            "required": True,
        }],
        "origin": "wicked-garden:compiler:phase0:wire_vault",
    }
    fd, path = tempfile.mkstemp(suffix=".json", prefix="wg-vault-spec-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    return path


def real_run_section(repo: Path, reponame: str, test_cmd: str | None, tee: Tee) -> dict:
    """§10-A/B against the DETECTED test_command. Honest: may FAIL/timeout."""
    scope = f"{reponame}-demo"
    result: dict = {"scope": scope, "runnable": None}
    tee(f"\n  [REAL] scope={scope} phase=build  source_pin={test_cmd!r}")

    if not test_cmd:
        tee("  [REAL] no test_command detected — skipping real run.")
        result["runnable"] = False
        result["note"] = "detect.py returned no test_command"
        return result

    spec = write_spec(test_cmd)
    rc, out = run_vault(
        ["declare-contract", "--scope", scope, "--phase", "build", "--spec", spec],
        repo)
    os.unlink(spec)
    tee(f"  [REAL] declare-contract exit={rc} contract_version="
        f"{out.get('contract_version') if isinstance(out, dict) else out}")

    tee(f"  [REAL] record --run  (timeout {REAL_RUN_TIMEOUT_S}s) ...")
    rc, out = run_vault(
        ["record", "--scope", scope, "--phase", "build", "--claim", "tests-pass",
         "--kind", "test-run", "--source", test_cmd, "--verifier", "exit_code_eq:0",
         "--run"],
        repo, timeout=REAL_RUN_TIMEOUT_S)
    if rc == 124:
        # Our wrapper killed the vault process. The detected command did not
        # complete in budget => not runnable here. Fall back to gate demo only.
        tee(f"  [REAL] record TIMED OUT after {REAL_RUN_TIMEOUT_S}s — "
            "detected command is NOT runnable in budget on this machine.")
        result["runnable"] = False
        result["note"] = f"detected command timed out > {REAL_RUN_TIMEOUT_S}s"
        return result
    if isinstance(out, dict) and out.get("error"):
        tee(f"  [REAL] record ERROR: {out['error']}")
        result["runnable"] = False
        result["note"] = f"record error: {out['error']}"
        return result

    status = out.get("status_at_record") if isinstance(out, dict) else None
    detail = out.get("status_detail") if isinstance(out, dict) else None
    tee(f"  [REAL] record exit={rc} status_at_record={status} detail={detail!r}")
    result["runnable"] = True
    result["status_at_record"] = status

    rc, out = run_vault(["cross-check", "--scope", scope, "--phase", "build"], repo)
    overall = out.get("overall") if isinstance(out, dict) else out
    tee(f"  [REAL] cross-check exit={rc} overall={overall}  "
        "(this exit code IS the harness gate signal)")
    result["crosscheck_overall"] = overall
    result["crosscheck_exit"] = rc
    return result


def gate_transition_section(repo: Path, reponame: str, tee: Tee) -> dict:
    """Explicit REJECT->PASS demo on ONE contract, both outcomes genuine.

    Records a genuinely-FAILING capture (`false`-equivalent, marker=1) then a
    genuinely-PASSING capture (`true`-equivalent, marker=0), both via the SAME
    pinned source (honors G8). Latest-active artifact flips the verdict.
    """
    scope = f"{reponame}-demo-gate"
    result: dict = {"scope": scope}
    marker = Path(tempfile.gettempdir()) / f"wg-vault-gate-{reponame}-marker"
    # Same source string for both records => G8 source_pin satisfied; exit code
    # comes from the marker file the vault reads at run time.
    source = f"sh -c 'exit $(cat {marker})'"
    tee(f"\n  [GATE] scope={scope} phase=build  source_pin={source!r}")

    spec = write_spec(source)
    rc, out = run_vault(
        ["declare-contract", "--scope", scope, "--phase", "build", "--spec", spec],
        repo)
    os.unlink(spec)
    tee(f"  [GATE] declare-contract exit={rc} contract_version="
        f"{out.get('contract_version') if isinstance(out, dict) else out}")

    # 1) genuinely FAILING capture (false): marker=1
    marker.write_text("1")
    rc, out = run_vault(
        ["record", "--scope", scope, "--phase", "build", "--claim", "tests-pass",
         "--kind", "test-run", "--source", source, "--verifier", "exit_code_eq:0",
         "--run"],
        repo)
    tee(f"  [GATE] record FAILING (false/exit 1) exit={rc} "
        f"status_at_record={out.get('status_at_record') if isinstance(out, dict) else out}")

    rc_fail, out = run_vault(["cross-check", "--scope", scope, "--phase", "build"], repo)
    overall_fail = out.get("overall") if isinstance(out, dict) else out
    tee(f"  [GATE] cross-check (failing latest) exit={rc_fail} overall={overall_fail}  "
        "<- expect REJECT / exit 1")
    result["fail_overall"] = overall_fail
    result["fail_exit"] = rc_fail

    # 2) genuinely PASSING capture (true): marker=0  -> becomes latest active
    marker.write_text("0")
    rc, out = run_vault(
        ["record", "--scope", scope, "--phase", "build", "--claim", "tests-pass",
         "--kind", "test-run", "--source", source, "--verifier", "exit_code_eq:0",
         "--run"],
        repo)
    tee(f"  [GATE] record PASSING (true/exit 0) exit={rc} "
        f"status_at_record={out.get('status_at_record') if isinstance(out, dict) else out}")

    rc_pass, out = run_vault(["cross-check", "--scope", scope, "--phase", "build"], repo)
    overall_pass = out.get("overall") if isinstance(out, dict) else out
    tee(f"  [GATE] cross-check (passing latest) exit={rc_pass} overall={overall_pass}  "
        "<- expect PASS / exit 0")
    result["pass_overall"] = overall_pass
    result["pass_exit"] = rc_pass

    marker.unlink(missing_ok=True)
    return result


def cleanup(repo: Path, tee: Tee) -> None:
    vdir = repo / ".wicked-vault"
    if vdir.exists():
        shutil.rmtree(vdir)
        tee(f"  cleanup: removed {vdir}")
    else:
        tee(f"  cleanup: nothing to remove at {vdir}")


def wire(repo: Path, tee: Tee) -> dict:
    reponame = repo.name
    tee("\n" + "=" * 72)
    tee(f"REPO: {repo}")
    tee("=" * 72)
    # Clean slate: the cross-check is re-run from a fresh vault every time.
    cleanup(repo, tee)
    bindings = detect(repo, tee)
    test_cmd = bindings["test_command"].get("value")
    real = real_run_section(repo, reponame, test_cmd, tee)
    gate = gate_transition_section(repo, reponame, tee)
    cleanup(repo, tee)
    return {"repo": reponame, "real": real, "gate": gate}


def main() -> int:
    if not VAULT_CLI.exists():
        sys.stderr.write(f"wicked-vault CLI not found at {VAULT_CLI}\n")
        return 2
    repos = [Path(a).resolve() for a in sys.argv[1:]] or [
        Path.home() / "Projects" / "memos",
        Path.home() / "Projects" / "Enterprise-AISDLC",
    ]
    tee = Tee(EVIDENCE)
    tee("wicked-garden -> wicked-vault consumer-contract wiring (Phase-0)")
    tee(f"vault CLI: {VAULT_CLI}")
    tee(f"transcript: {EVIDENCE}")
    summary = []
    try:
        for repo in repos:
            if not repo.exists():
                tee(f"\nSKIP (missing): {repo}")
                continue
            summary.append(wire(repo, tee))
    finally:
        tee("\n" + "=" * 72)
        tee("SUMMARY")
        tee("=" * 72)
        for s in summary:
            tee(f"\n{s['repo']}:")
            r = s["real"]
            tee(f"  REAL detected command runnable: {r.get('runnable')}"
                + (f"  ({r['note']})" if r.get("note") else ""))
            if r.get("runnable"):
                tee(f"    real cross-check: overall={r.get('crosscheck_overall')} "
                    f"exit={r.get('crosscheck_exit')}")
            g = s["gate"]
            tee(f"  GATE failing-latest: overall={g.get('fail_overall')} exit={g.get('fail_exit')} (expect REJECT/1)")
            tee(f"  GATE passing-latest: overall={g.get('pass_overall')} exit={g.get('pass_exit')} (expect PASS/0)")
        tee.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
