#!/usr/bin/env python3
"""Grade one build-guide eval run deterministically.

    python3 tests/build_guide/eval_grade.py --case <eval_cases/x.json> --repo <the repo the skill ran on>
        --message <file with the skill's final message> [--guide <produced .wicked/build-guide.json>]

An eval run is: give an agent the case's ``prompt`` on a scratch copy of the case's ``fixture``, with
the skill installed, and keep the guide it proposed (if any) and its final message. This grader then
re-derives every expectation from those artifacts: the guide is checked with check.py --draft and
rehearsed with rehearse.py against ``--repo`` (for vitest, a copy with ``npm install`` done). Nothing
is taken from the agent's own claims except the message text, which is matched literally.

Prints {"case_id", "assertions": {name: "pass" | "fail: why"}, "ok"} and exits 0 iff every
assertion passes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "build_guide"


def _script(name: str, *args: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), *args], capture_output=True, text=True,
                          timeout=1800)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except ValueError:
        return proc.returncode, {"_stdout": proc.stdout[-500:], "_stderr": proc.stderr[-500:]}


def grade(case: dict, repo: Path, message: str, guide_path: Path | None) -> dict:
    expect = case["expect"]
    out: dict[str, str] = {}
    present = guide_path is not None and guide_path.is_file()
    want = expect["guide"]
    out["guide"] = "pass" if present == (want == "present") else f"fail: guide is {'present' if present else 'absent'}"
    for needle in expect.get("message_includes", []):
        out[f"message: {needle[:40]}"] = "pass" if needle in message else "fail: not in the final message"
    for group in expect.get("message_includes_any", []):
        hit = any(n.lower() in message.lower() for n in group)
        out[f"message any of {group}"] = "pass" if hit else "fail: none in the final message"
    if not present or want != "present":
        return {"case_id": case["case_id"], "assertions": out, "ok": all(v == "pass" for v in out.values())}
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    check = guide["checks"][0]
    if expect.get("check_draft_ok"):
        code, report = _script("check", "--guide", str(guide_path), "--repo", str(repo), "--draft")
        out["check --draft"] = "pass" if code == 0 else f"fail: {report.get('errors')}"
    if "results_kind" in expect:
        kind = check["results"]["kind"]
        out["results kind"] = "pass" if kind == expect["results_kind"] else f"fail: kind is {kind}"
    if expect.get("parser_uses") == "blocks":
        out["parser uses blocks"] = "pass" if check.get("parser", {}).get("blocks") else "fail: no summary blocks"
    for rel in expect.get("derivedFrom_includes", []):
        out[f"derivedFrom {rel}"] = "pass" if rel in guide.get("derivedFrom", []) else "fail: missing"
    if expect.get("no_verified"):
        hand = [c["name"] for c in guide["checks"] if "verified" in c]
        out["no hand-written verified"] = "pass" if not hand else f"fail: verified in {hand}"
    if "rehearsal" in expect:
        _code, report = _script("rehearse", "--repo", str(repo), "--guide", str(guide_path))
        got = (report.get("checks") or [{}])[0].get("results", {})
        wanted = expect["rehearsal"]
        if wanted == "all-pass":
            bad = {k: v for k, v in got.items() if v != "pass"}
            out["rehearsal"] = "pass" if got and not bad else f"fail: {bad or report}"
        else:
            bad = {k: got.get(k) for k, v in wanted.items() if not str(got.get(k, "")).startswith(v)}
            out["rehearsal"] = "pass" if not bad else f"fail: {bad}"
    return {"case_id": case["case_id"], "assertions": out, "ok": all(v == "pass" for v in out.values())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--case", required=True, type=Path)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--message", required=True, type=Path)
    ap.add_argument("--guide", type=Path)
    args = ap.parse_args(argv)
    result = grade(json.loads(args.case.read_text(encoding="utf-8")), args.repo,
                   args.message.read_text(encoding="utf-8"), args.guide)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
