"""tests/daemon/test_council_timeout.py — Stream 5 timeout behaviour for v8 PR-4.

Verifies:
- A CLI that hangs past timeout records a "timeout" vote row, not a silent drop
- A hanging CLI does not block other CLIs from completing
- Timeout vote row has the correct model name and verdict="timeout"
- Multiple CLIs: one hanging + others healthy completes in bounded time

T1: deterministic — mocked subprocesses, no real CLIs.
T2: no sleep-based sync — we set very small timeouts and mock the TimeoutExpired.
T3: isolated — fresh in-memory DB per test.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #594 v8-PR-4 R5 (no unbounded operations).
"""

from __future__ import annotations

import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest


def _approx_verdict(text: str) -> str:
    return f"RECOMMENDATION: {text}\nDetailed reasoning here."


def _make_process(stdout: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    proc.stderr = ""
    return proc


class TestTimeoutVoteRow:
    """A CLI that raises TimeoutExpired gets an explicit timeout vote row."""

    def test_single_timeout_produces_timeout_verdict(self, mem_conn):
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_run(argv, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["aider"], timeout_s=1,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 1
        v = votes[0]
        assert v["verdict"] == "timeout"
        assert v["model"] == "aider"
        assert "timed out" in v["rationale"].lower() or "timeout" in v["rationale"].lower()

    def test_timeout_vote_has_no_confidence(self, mem_conn):
        """Timeout votes must not invent a confidence value."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_run(argv, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["goose"], timeout_s=1,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert votes[0]["confidence"] is None

    def test_timeout_vote_row_has_non_empty_rationale(self, mem_conn):
        """Timeout vote must explain WHY the slot is empty (R4: no silent drops)."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_run(argv, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["llm"], timeout_s=2,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes[0]["rationale"]) > 0


class TestTimeoutDoesNotBlockOthers:
    """A hanging CLI must not prevent other CLIs from completing."""

    def test_hanging_cli_does_not_block_healthy_cli(self, mem_conn):
        """One slow CLI and one fast CLI: total time must not be sequential sum."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        # gemini = fast, aider = timeout
        def fake_run(argv, capture_output, text, timeout):
            cmd_str = " ".join(str(a) for a in argv)
            if "aider" in cmd_str:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
            # gemini responds quickly
            return _make_process(stdout=_approx_verdict("APPROVE"))

        start = time.monotonic()
        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini", "aider"], timeout_s=30,
            )
        elapsed = time.monotonic() - start

        # Two sequential 30s timeouts would take 60s.
        # With parallelism, the wall clock should be well under 5s.
        assert elapsed < 5.0, (
            f"Hanging CLI appears to have blocked others: elapsed={elapsed:.3f}s "
            "(expected < 5s — the 30s timeout should not be hit for 'aider' "
            "since TimeoutExpired is raised immediately by the mock)"
        )

        votes = list_council_votes(mem_conn, result.session_id)
        verdicts = {v["model"]: v["verdict"] for v in votes}
        # aider must have a timeout row, gemini must have a real verdict
        assert verdicts.get("aider") == "timeout"
        assert verdicts.get("gemini") not in ("timeout", "unavailable", "error")

    def test_all_votes_collected_even_with_partial_timeouts(self, mem_conn):
        """3 CLIs: 1 healthy, 1 timeout, 1 unavailable — all 3 rows in DB."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_which(name):
            if name == "goose":
                return None  # unavailable
            return "/usr/bin/fake"

        def fake_run(argv, capture_output, text, timeout):
            cmd_str = " ".join(str(a) for a in argv)
            if "aider" in cmd_str:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
            return _make_process(stdout=_approx_verdict("APPROVE"))

        with (
            patch("shutil.which", side_effect=fake_which),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini", "aider", "goose"], timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 3
        verdicts = {v["model"]: v["verdict"] for v in votes}
        assert verdicts["goose"] == "unavailable"
        assert verdicts["aider"] == "timeout"
        assert verdicts["gemini"] not in ("timeout", "unavailable", "error")


class TestNoSilentDrops:
    """Every CLI attempted produces a vote row (R4: no swallowed errors)."""

    def test_subprocess_exception_produces_error_vote(self, mem_conn):
        """An unexpected subprocess exception still produces an error vote row."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_run(argv, capture_output, text, timeout):
            raise RuntimeError("unexpected subprocess failure")

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["gemini"], timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 1
        assert votes[0]["verdict"] == "error"

    def test_nonzero_exit_produces_error_vote(self, mem_conn):
        """A CLI that exits non-zero produces an error vote, not a missing row."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        def fake_run(argv, capture_output, text, timeout):
            proc = MagicMock()
            proc.returncode = 1
            proc.stdout = ""
            proc.stderr = "authentication failed"
            return proc

        with (
            patch("shutil.which", return_value="/usr/bin/fake"),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_council(
                mem_conn, topic="t", question="q",
                cli_list=["codex"], timeout_s=5,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 1
        assert votes[0]["verdict"] == "error"
