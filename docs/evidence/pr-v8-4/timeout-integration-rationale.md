# Why a real-subprocess timeout test was needed

The existing unit tests in `test_council_timeout.py` mock `subprocess.run` to raise
`subprocess.TimeoutExpired` immediately.  This validates that `_invoke_cli` handles
the exception correctly and writes the right vote row — but it cannot prove that
the underlying `subprocess.run(timeout=N)` call actually terminates a real blocking
process within N seconds under OS scheduler pressure.  A mock that raises instantly
bypasses the `ThreadPoolExecutor`, the `concurrent.futures.as_completed` fan-out,
and the real Python/OS timeout machinery entirely.

The integration test in `test_council_timeout_integration.py` fills that gap by
launching two genuine Python subprocesses: one that calls `time.sleep(3.0)` (longer
than the 1s timeout budget), and one that writes a fast reply and exits.  The test
asserts three things under real wall-clock time: (1) the total elapsed time is less
than 3s, proving the hang was killed and the two CLIs ran concurrently rather than
serially; (2) the hanging CLI's vote row carries `verdict="timeout"` and a non-empty
rationale, proving no silent drops; and (3) the fast CLI's vote row carries a real
verdict, proving the timeout of one CLI does not contaminate others.  Together these
assertions confirm that R5 (no unbounded operations) holds not just in mocked unit
tests but under actual OS process and scheduler pressure — the gap that council
feedback #615 identified.
