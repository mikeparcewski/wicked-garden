"""The governed-worker floor carries the rules runs were lost without (garden#1229, #1223).

Text-presence pins: the floor is the one brief every seat reads before every turn, so a rule
that silently drops out of it is a regression even when no code changes.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FLOOR = Path(__file__).resolve().parents[1] / "skills" / "governed-worker" / "SKILL.md"


def _rule(rule_id: str) -> str:
    body = FLOOR.read_text(encoding="utf-8")
    m = re.search(rf"^- \*\*{rule_id} — (.*?)(?=^- \*\*|^\S|\Z)", body, re.M | re.S)
    assert m, f"{rule_id} is missing from the governed-worker floor"
    return " ".join(m.group(1).split())


def test_c7_keeps_tool_debris_under_the_notes_root():  # garden#1229
    rule = _rule("C7")
    assert "notes root" in rule and "$WICKED_NOTES_ROOT" in rule
    for kind in ("Reporter output", "coverage", "screenshots", "logs", "scratch files"):
        assert kind in rule, kind
    assert "never in the repository" in rule
    assert "--outputFile" in rule and "delete the file before the turn ends" in rule


def test_c6_no_turn_ends_with_tasks_pending():  # garden#1223
    rule = _rule("C6")
    assert "foreground" in rule and "exit code" in rule
    assert '"Running in the background" is never a closing line' in rule


def test_c2_pre_existing_cites_the_base_run_or_is_a_failure():  # garden#1223
    rule = _rule("C2")
    assert "base tree" in rule and "exit code" in rule and "or it is a failure" in rule


def test_e3_verdict_items_stay_in_scope_unless_a_human_strikes_them():  # garden#1223
    rule = _rule("E3")
    assert "human ruling strikes it by name" in rule


def test_e4_parity_items_are_judged_on_values_from_both_sides():  # garden#1253
    rule = _rule("E4")
    assert "derive the value X actually produces" in rule
    assert "quote it with `file:line`" in rule and "compare the two" in rule
    assert "a test the creator wrote pinning a value is never the evidence" in rule
    assert "Values that differ are a Critical" in rule
    # The corpus case rides the rule: a creator-pinned `before:1` against the form's `before:2` FAILs.
    assert "Example (FAIL)" in rule and "`before:1`" in rule and "`before:2`" in rule and "the item FAILs" in rule


def test_review_archetype_points_parity_items_at_e4():  # garden#1253
    review = (FLOOR.parents[1] / "archetype" / "refs" / "review.md").read_text(encoding="utf-8")
    assert "Parity items compare values (garden#1253)" in review and "rule E4" in review


def test_c8_checks_the_chosen_stack_before_writing_code():  # operator ruling 2026-10-12, POL-2101
    rule = _rule("C8")
    assert "The user and the steering policies choose the framework or library" in rule
    assert "POL-2101" in rule and "never swap in another" in rule
    assert "at the version the repo pins" in rule
    assert "Record the check in your output" in rule
    assert "say why the built-in does not fit" in rule
    assert "fastmcp" in rule


def test_e5_evaluators_flag_every_duplicate_of_a_built_in():  # operator ruling 2026-10-12, POL-2101
    rule = _rule("E5")
    assert "even when the creator gave a reason" in rule and "`file:line`" in rule
    assert "judge the creator's reason" in rule
    assert "An unjustified duplicate is at least a Concern" in rule
    assert "records no built-in check (C8)" in rule


def test_engineering_review_and_plan_carry_the_built_in_check():  # POL-2101
    eng = FLOOR.parents[1] / "engineering"
    review = (eng / "refs" / "review.md").read_text(encoding="utf-8")
    assert "## Duplicates of a built-in — always flag" in review
    assert "### Duplicates of a Built-in" in review and "POL-2101" in review
    plan = (eng / "refs" / "plan.md").read_text(encoding="utf-8")
    assert "### Built-ins Checked" in plan and "POL-2101" in plan
    archetype = FLOOR.parents[1] / "archetype" / "refs"
    assert "POL-2101" in (archetype / "build.md").read_text(encoding="utf-8")
    assert "Duplicates of a built-in are findings (POL-2101)" in (archetype / "review.md").read_text(
        encoding="utf-8"
    )


def test_e6_delivery_only_criteria_are_deferred_not_failed():  # operator-approved fix, 2026-10-19
    rule = _rule("E6")
    for artifact in ("CI results on the opened pull request", "the pull request's title or body", "a merge"):
        assert artifact in rule, artifact
    assert "is DEFERRED: neither PASS nor FAIL" in rule
    assert "Judge every part you can check before delivery" in rule
    # Deny-dominates: a failing in-run part is never lifted by the deferral.
    assert "FAILs when its in-run part fails; a deferral never lifts a failing in-run part" in rule
    assert "`ITEM <n>: DEFERRED — <the artifact it waits for>`" in rule
    assert "A deferred item never fails the unit by itself" in rule
    assert "a promise that CI will pass is never a PASS" in rule
    assert "The deliver gate shows each deferred check to the operator" in rule
    assert "not a creator's deferral (E3)" in rule
    body = " ".join(FLOOR.read_text(encoding="utf-8").split())
    assert "a DEFERRED item (E6) is neither, so it never makes the verdict FAIL" in body


def test_new_rules_have_provenance_rows():
    body = FLOOR.read_text(encoding="utf-8")
    for rule_id in ("A7", "C6", "C7", "C8", "E3", "E4", "E5", "E6"):
        assert re.search(rf"^\| {rule_id} \|", body, re.M), rule_id


def test_a7_every_role_proposes_what_it_witnessed():  # operator report 2026-10-31: only pi proposed memories
    rule = _rule("A7")
    assert "whatever your role" in rule
    # A fixed moment to check, power mode included: a soft "when you learn something" was read and skipped
    # by both a power-mode claude orchestrator and a codex evaluator on the rig (run e0ba4073).
    assert "Before your final message (in power mode, before each `CHECKPOINT:` or `HANDOFF:` line)" in rule
    for what in ("failed because of the toolchain, the environment or the repository's setup",
                 "and what made it pass", "a trap in a tool", "a ruling or steer the operator gave"):
        assert what in rule, what
    # A reviewer's finding with an environmental cause is a memory too (the codex evaluator's miss).
    assert "A finding you report is a memory as well" in rule and "so an evaluator proposes it too" in rule
    assert "`wicked-garden run scripts/mem/estate_memory.py --readonly propose '" in rule
    assert "never pass provenance" in rule
    assert "Not a memory: what the code does" in rule and "the change you made" in rule
    assert "At most three per unit in all, across every turn" in rule
    # A power-mode unit checks at every checkpoint, and recall never returns a pending proposal, so the
    # rule itself must stop a re-proposal (xreview r2 P2).
    assert "Propose each learning once" in rule and "covers only what happened since the last one" in rule
    assert "never re-proposes what this unit already proposed or recorded" in rule
    assert "never a pending proposal" in rule
    assert "an evaluator or a neutral unit proposes too" in rule
    assert "when N is 0 say what you checked" in rule
    assert "an evaluator's VERDICT line is still last" in rule
    # The manual alternative covers a missing launcher too (Copilot on #1372), recorded once (A5).
    assert "When the launcher or Python is missing, the shim answers" in rule
    assert "`memory (not proposed: <reason>): <text>` in your output once and go on (A5)" in rule
    # The capture-report line stays a capture-phase contract, so an evaluator's VERDICT stays last.
    assert "A unit of a declared capture phase also ends with the machine-readable line" in _rule("A4")
    body = " ".join(FLOOR.read_text(encoding="utf-8").split())
    assert "memories proposed N (A7), with what you checked when N is 0" in body
    assert "every role proposes a memory for what it witnessed" in body


def _a7_propose_argv(text: str) -> list:
    """A7's own propose command, as a seat would run it, with the launcher resolved to this checkout."""
    m = re.search(r"`wicked-garden run (scripts/mem/estate_memory\.py --readonly propose) '[^`]*'`", _rule("A7"))
    assert m, "A7 names no propose command"
    script, *args = shlex.split(m.group(1))
    return [sys.executable, str(FLOOR.parents[2] / script), *args, text]


class _Broker:
    """crew's broker (`POST /api/v1/mcp/call`), answering a proposal with an id."""

    def __init__(self):
        self.seen = []
        seen = self.seen

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
                seen.append((self.path, body))
                out = {"outcome": "ok", "subject": body.get("subject"), "callId": "c1", "ruleIds": [],
                       "result": {"content": [{"type": "text", "text": json.dumps({"id": "prop-7"})}],
                                  "isError": False}}
                raw = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def test_a7_command_lands_a_codex_seats_memory_in_the_queue(tmp_path):
    """A non-pi seat (codex, an evaluator unit on the container floor) runs A7's command: one
    `proposal.submit` of kind memory reaches crew's broker, scoped to the run's project, with no
    caller provenance (crew stamps run_id / run_unit / run_agent from the unit the token is bound to)."""
    broker = _Broker()
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith("WICKED_")}
        env.update({
            "WICKED_RUN_ID": "run-7", "WICKED_RUN_UNIT": "3", "WICKED_RUN_AGENT": "codex",
            "WICKED_RUN_PROJECT": "tiny-math", "WICKED_ESTATE_BROKER": "1",
            "WICKED_CREW_URL": broker.url, "WICKED_MCP_TOKEN": "wmt_unit3",
            "WICKED_ESTATE_READONLY": "1", "WICKED_ESTATE_PERSISTENT": "0",
        })
        text = ("In tiny-math, `npm test` runs `node --test test/`, which newer Node treats as a module path "
                "and fails with MODULE_NOT_FOUND; run `node --test test/*.test.js` to run the suite.")
        res = subprocess.run(_a7_propose_argv(text), env=env, cwd=tmp_path, capture_output=True, text=True,
                             timeout=60)
        assert res.returncode == 0, res.stderr
        out = json.loads(res.stdout)
        assert out["ok"] is True and out["id"] == "prop-7", out
        calls = [b for path, b in broker.seen if path == "/api/v1/mcp/call"]
        assert len(calls) == 1, broker.seen
        call = calls[0]
        assert call["token"] == "wmt_unit3"
        assert call["subject"] == "mcp:estate/proposal.submit"
        assert call["args"]["kind_type"] == "memory"
        assert call["args"]["payload"]["content"] == text
        assert call["args"]["facets"]["project"] == "tiny-math"
        assert "provenance" not in call["args"]
    finally:
        broker.server.shutdown()
        broker.server.server_close()
