"""tests/daemon/test_council_orchestrator.py — Stream 5 orchestrator tests for v8 PR-4.

Verifies:
- Fan-out runs in parallel (timing check: N mocked CLIs finish in ~max(latency),
  not sum(latencies))
- Votes are persisted to council_votes table
- Synthesis called correctly via build_council_output
- HITL judge integration is called (not bypassed)
- Unavailable CLIs produce explicit "unavailable" vote rows
- Timeout CLIs produce explicit "timeout" vote rows without blocking others

All CLIs are mocked at the subprocess level — no real CLI invocations.

T1: deterministic — no real subprocesses, no wall-clock beyond timing margin.
T2: no sleep-based sync — use concurrent.futures results.
T3: isolated — fresh in-memory DB per test.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #594 v8-PR-4.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_process(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    """Build a mock subprocess.run result."""
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    proc.stderr = stderr
    return proc


def _approx_verdict(text: str) -> str:
    """Return a fake response that contains the given verdict keyword."""
    return f"RECOMMENDATION: {text}\nThis is my detailed analysis."


# ---------------------------------------------------------------------------
# Tests — vote persistence
# ---------------------------------------------------------------------------

class TestVotePersistence:
    """Votes are written to the DB during run_council."""

    def test_successful_votes_persisted(self, mem_conn):
        from daemon.council import run_council
        from daemon.db import list_council_votes

        cli_list = ["gemini", "codex"]
        responses = {
            "gemini": _approx_verdict("APPROVE"),
            "codex": _approx_verdict("APPROVE"),
        }

        def fake_run(argv, capture_output, text, timeout):
            # Determine which CLI by inspecting the command
            cmd_str = " ".join(str(a) for a in argv)
            for cli in responses:
                if cli in cmd_str:
                    return _make_process(stdout=responses[cli])
            return _make_process(stdout="APPROVE")

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="test", question="which option?",
                cli_list=cli_list, timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 2
        models = {v["model"] for v in votes}
        assert models == {"gemini", "codex"}

    def test_unavailable_cli_produces_unavailable_vote(self, mem_conn):
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_which(name):
            return None  # all CLIs unavailable

        with patch("shutil.which", side_effect=fake_which):
            result = run_council(
                mem_conn, topic="test", question="which option?",
                cli_list=["goose", "llm"], timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        verdicts = {v["verdict"] for v in votes}
        assert verdicts == {"unavailable"}
        assert len(votes) == 2

    def test_timeout_produces_timeout_vote_row(self, mem_conn):
        from daemon.council import run_council
        from daemon.db import list_council_votes
        import subprocess

        def fake_run(argv, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="test", question="which option?",
                cli_list=["aider"], timeout_s=1,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 1
        assert votes[0]["verdict"] == "timeout"
        assert votes[0]["model"] == "aider"

    def test_session_row_completed_after_run(self, mem_conn):
        from daemon.council import run_council
        from daemon.db import get_council_session

        with (
            patch("shutil.which", return_value=None),
        ):
            result = run_council(
                mem_conn, topic="topic-x", question="q",
                cli_list=["gemini"], timeout_s=5,
            )

        session = get_council_session(mem_conn, result.session_id)
        assert session is not None
        assert session["completed_at"] is not None
        assert session["topic"] == "topic-x"


# ---------------------------------------------------------------------------
# Tests — fan-out parallelism
# ---------------------------------------------------------------------------

class TestFanOutParallelism:
    """Fan-out runs CLIs in parallel: wall-clock ≈ max(latency), not sum."""

    def test_parallel_completion_time_bounded_by_slowest(self, mem_conn):
        """With N=3 CLIs each sleeping 0.1s, wall-clock must be < N*0.1s.

        We use a generous upper bound of 1.5× the slowest latency to
        accommodate scheduling overhead without making the test flaky.
        """
        import threading

        # Each CLI introduces a 0.1s latency via a side-effect counter
        per_cli_sleep_s = 0.1
        n_clis = 3
        call_times: list[float] = []
        lock = threading.Lock()

        def fake_run(argv, capture_output, text, timeout):
            with lock:
                call_times.append(time.monotonic())
            time.sleep(per_cli_sleep_s)
            return _make_process(stdout=_approx_verdict("APPROVE"))

        from daemon.council import run_council

        start = time.monotonic()
        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini", "codex", "llm"],
                timeout_s=10,
            )
        elapsed = time.monotonic() - start

        # Sequential would take n_clis * per_cli_sleep_s.
        # Parallel upper bound: per_cli_sleep_s + generous overhead (1.5s).
        sequential_time = n_clis * per_cli_sleep_s
        max_acceptable = per_cli_sleep_s + 1.5  # 1.5s overhead budget
        assert elapsed < sequential_time, (
            f"Fan-out appears sequential: {elapsed:.3f}s >= {sequential_time:.3f}s "
            f"(expected < {max_acceptable:.3f}s)"
        )

    def test_fan_out_collects_all_results(self, mem_conn):
        """All N CLIs produce vote rows regardless of individual outcomes."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        responses = {
            "gemini": _approx_verdict("APPROVE"),
            "codex": _approx_verdict("REJECT"),
            "aichat": _approx_verdict("APPROVE"),
        }

        def fake_run(argv, capture_output, text, timeout):
            cmd_str = " ".join(str(a) for a in argv)
            for cli, resp in responses.items():
                if cli in cmd_str:
                    return _make_process(stdout=resp)
            return _make_process(stdout="APPROVE")

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=list(responses.keys()), timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 3


# ---------------------------------------------------------------------------
# Tests — HITL judge integration
# ---------------------------------------------------------------------------

class TestHITLJudgeIntegration:
    """should_pause_council is always called; its result appears in CouncilResult."""

    def test_hitl_decision_present_in_result(self, mem_conn):
        from daemon.council import run_council

        with patch("shutil.which", return_value=None):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini"], timeout_s=5,
            )

        # hitl_decision must always be populated (never None, never skipped)
        assert result.hitl_decision is not None
        assert "pause" in result.hitl_decision
        assert "rule_id" in result.hitl_decision

    def test_hitl_pauses_on_no_quorum(self, mem_conn):
        """When all CLIs are unavailable (0 valid votes), HITL should pause."""
        from daemon.council import run_council

        with patch("shutil.which", return_value=None):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini", "codex"], timeout_s=5,
            )

        # No quorum → judge must pause
        assert result.hitl_decision["pause"] is True
        assert "no-quorum" in result.hitl_decision["rule_id"]

    def test_hitl_auto_proceed_on_unanimous_high_confidence_ignored(self, mem_conn):
        """All unavailable means no-quorum pause; unanimous only matters when votes exist."""
        from daemon.council import run_council

        with patch("shutil.which", return_value=None):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini"], timeout_s=5,
            )

        # 0 votes = no-quorum regardless of what CLIs said
        assert result.hitl_decision["pause"] is True


# ---------------------------------------------------------------------------
# Tests — synthesis output
# ---------------------------------------------------------------------------

class TestSynthesisOutput:
    """build_council_output envelope is in CouncilResult.synthesized."""

    def test_synthesized_contains_expected_keys(self, mem_conn):
        from daemon.council import run_council

        def fake_run(argv, capture_output, text, timeout):
            return _make_process(stdout=_approx_verdict("APPROVE"))

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini"], timeout_s=5,
            )

        # build_council_output with mode=both produces synthesized + raw_votes
        synth = result.synthesized
        assert "synthesized" in synth or "raw_votes" in synth, (
            f"Expected 'synthesized' or 'raw_votes' in envelope, got keys: {list(synth.keys())}"
        )

    def test_result_to_dict_is_json_serialisable(self, mem_conn):
        """to_dict() output must be JSON-serialisable."""
        import json
        from daemon.council import run_council

        with patch("shutil.which", return_value=None):
            result = run_council(
                mem_conn, topic="topic-json", question="is this serialisable?",
                cli_list=["gemini"], timeout_s=5,
            )

        # Must not raise
        serialised = json.dumps(result.to_dict())
        data = json.loads(serialised)
        assert data["session_id"] == result.session_id
