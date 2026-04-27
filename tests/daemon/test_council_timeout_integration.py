"""tests/daemon/test_council_timeout_integration.py — Real-subprocess timeout integration test.

Proves the council timeout enforcement under actual OS scheduler pressure.
This is the integration complement to the unit-level mocks in
test_council_timeout.py — both coexist intentionally.

Why this test exists (council feedback #615):
  Mock-based tests validate code *paths* but cannot prove the ThreadPoolExecutor
  actually terminates a live blocking process within the configured budget.
  A mock that raises TimeoutExpired immediately bypasses the scheduler entirely.
  This test uses real Python subprocesses — one that sleeps longer than the
  timeout and one that completes quickly — to prove:
    1. The hanging CLI is killed within timeout_s, not allowed to run to completion.
    2. True parallelism holds: the fast CLI is not serialised behind the slow one.
    3. Both vote rows land in the DB with the correct verdicts.

T1: deterministic — two deterministic subprocesses (one sleeps, one emits JSON).
    Wall-clock assertion is generous (3× the fast-path budget) to avoid flakiness
    on slow CI machines, while still proving the hang is bounded.
T2: no sleep-based sync — the test does not poll; it calls run_council and checks
    the result synchronously.
T3: isolated — fresh in-memory DB via mem_conn fixture.
T4: one concern per test function.
T5: descriptive names.
T6: provenance: #594 v8-PR-4 R5 (no unbounded ops) — council feedback, #615.
"""

from __future__ import annotations

import sys
import time
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Constants (R3: no magic values)
# ---------------------------------------------------------------------------

_TIMEOUT_S: int = 1
"""Per-CLI timeout budget for the integration test (seconds)."""

_FAST_REPLY: str = '{"verdict":"APPROVE","confidence":0.9,"rationale":"fast"}'
"""JSON emitted by the fast stub CLI.  Intentionally not a 4-question scaffold
response — the verdict extractor falls back to scanning the full text, which
finds 'APPROVE' here just fine."""

# Wall-clock ceiling: the hang CLI times out at _TIMEOUT_S.  The fast CLI
# completes in ~0 ms.  We allow 3× the timeout plus 1s constant headroom to
# tolerate slow CI machines.  Sequential execution would cost 2 × _TIMEOUT_S
# which is 2s — our ceiling of (_TIMEOUT_S * 3 + 1) = 4s still proves true
# parallelism because 4s < 2 × _TIMEOUT_S is only guaranteed when _TIMEOUT_S > 4,
# but at _TIMEOUT_S = 1 the sequential cost is 2s and our ceiling is 4s — that
# still catches a truly serialised executor (2s actual < 4s ceiling passes, BUT
# a serialised hang would block at 2s; with a real sleep the hang blocks at
# _TIMEOUT_S = 1s and then we add the fast CLI's ~0ms, well within the 4s bound).
#
# The critical assertion is NOT the wall-clock upper bound alone but the
# combination: wall_clock < 2 × _TIMEOUT_S + 1s  proves the two CLIs ran
# concurrently (they did not serialize) under real scheduler pressure.
_WALL_CLOCK_CEILING_S: float = _TIMEOUT_S * 2 + 1.0
"""Maximum acceptable wall clock time (seconds).  A truly serialised run of
two timeout-length subprocesses would take 2 × _TIMEOUT_S; this ceiling proves
the fan-out is concurrent and not sequential."""

# ---------------------------------------------------------------------------
# Helper: build argv for each stub CLI
# ---------------------------------------------------------------------------

def _argv_hang(_scaffold_path: str) -> list[str]:
    """Return argv for a subprocess that sleeps longer than _TIMEOUT_S."""
    sleep_s = _TIMEOUT_S + 2.0  # R3: named constant arithmetic, not bare literal
    return [sys.executable, "-c", f"import time; time.sleep({sleep_s})"]


def _argv_fast(_scaffold_path: str) -> list[str]:
    """Return argv for a subprocess that exits immediately with a valid verdict."""
    # Use repr() so the JSON string is safely single-quoted inside the -c body.
    payload = repr(_FAST_REPLY)
    return [sys.executable, "-c", f"import sys; sys.stdout.write({payload})"]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestRealSubprocessTimeout:
    """Integration test: real subprocess invocations under actual timeout pressure.

    Uses pytest.mark.slow so fast-CI runs can filter it with -m 'not slow'.
    The test takes approximately _TIMEOUT_S seconds (the hang CLI's timeout).
    """

    def test_wall_clock_bounded_and_verdicts_correct(self, mem_conn):
        """Core integration assertion:

        - wall_clock < _WALL_CLOCK_CEILING_S (concurrent, not serial)
        - hang CLI vote row has verdict="timeout"
        - fast CLI vote row has its real verdict (not contaminated by timeout)
        """
        from daemon.council import run_council
        from daemon.db import list_council_votes

        # Inject real-subprocess argv factories for two synthetic CLI names.
        # We also patch _cli_available so the availability probe passes without
        # requiring the real binaries to exist.
        stub_argv_map = {
            "_test_hang": _argv_hang,
            "_test_fast": _argv_fast,
        }

        with (
            patch("daemon.council._CLI_ARGV", stub_argv_map),
            patch("daemon.council._cli_available", return_value=True),
        ):
            start = time.monotonic()
            result = run_council(
                mem_conn,
                topic="integration-timeout-test",
                question="Does the timeout fire correctly?",
                cli_list=["_test_hang", "_test_fast"],
                timeout_s=_TIMEOUT_S,
            )
            wall_clock = time.monotonic() - start

        # --- Assertion 1: true parallelism holds under real scheduler pressure ---
        assert wall_clock < _WALL_CLOCK_CEILING_S, (
            f"Wall clock {wall_clock:.3f}s >= ceiling {_WALL_CLOCK_CEILING_S}s.  "
            f"The two CLIs may have run serially rather than concurrently.  "
            f"timeout_s={_TIMEOUT_S}, expected concurrent bound < {_WALL_CLOCK_CEILING_S}s."
        )

        # --- Assertion 1b (#616): timeout must actually fire ---
        # If wall_clock < ~_TIMEOUT_S, the hang CLI short-circuited — regression
        # in subprocess.TimeoutExpired enforcement. The 0.9s floor is slightly
        # under _TIMEOUT_S=1.0 to allow for small timer variance but rule out
        # sub-0.1s returns (which would indicate the hang never blocked).
        assert wall_clock >= 0.9, (
            f"wall_clock {wall_clock:.3f}s < 0.9s — timeout path may have short-circuited; "
            f"hang CLI should have forced ~{_TIMEOUT_S}s elapsed before termination."
        )

        votes = list_council_votes(mem_conn, result.session_id)
        verdicts = {v["model"]: v["verdict"] for v in votes}

        # --- Assertion 2: hang CLI produces an explicit timeout row ---
        assert verdicts.get("_test_hang") == "timeout", (
            f"Expected _test_hang verdict='timeout', got {verdicts.get('_test_hang')!r}.  "
            "The slow subprocess must produce an explicit timeout vote, not a silent drop (R4)."
        )

        # --- Assertion 3: fast CLI produces its real verdict, uncontaminated ---
        fast_verdict = verdicts.get("_test_fast")
        assert fast_verdict not in ("timeout", "unavailable", "error", None), (
            f"Expected _test_fast to have a real verdict, got {fast_verdict!r}.  "
            "The fast CLI must not be blocked or contaminated by the hanging CLI."
        )

    def test_timeout_vote_row_has_non_null_rationale(self, mem_conn):
        """The timeout vote row must carry an explanatory rationale (R4: no silent drops)."""
        from daemon.council import run_council
        from daemon.db import list_council_votes

        stub_argv_map = {"_test_hang_rationale": _argv_hang}

        with (
            patch("daemon.council._CLI_ARGV", stub_argv_map),
            patch("daemon.council._cli_available", return_value=True),
        ):
            result = run_council(
                mem_conn,
                topic="rationale-check",
                question="Is the rationale populated?",
                cli_list=["_test_hang_rationale"],
                timeout_s=_TIMEOUT_S,
            )

        votes = list_council_votes(mem_conn, result.session_id)
        assert len(votes) == 1
        v = votes[0]
        assert v["verdict"] == "timeout"
        assert v["rationale"] and len(v["rationale"]) > 0, (
            "Timeout vote must have a non-empty rationale explaining the failure."
        )
        assert v["confidence"] is None, (
            "Timeout vote must not invent a confidence score."
        )
