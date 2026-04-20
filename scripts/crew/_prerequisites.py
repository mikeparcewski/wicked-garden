#!/usr/bin/env python3
"""
_prerequisites.py — Crew command entry-gate checks.

crew_command_gate() must be called at the top of:
  - /wicked-garden:crew:start    (commands/crew/start.md)
  - /wicked-garden:crew:execute  (commands/crew/execute.md)
  - /wicked-garden:crew:just-finish (commands/crew/just-finish.md)
  - gate_dispatch (before dispatching any reviewer)

Raises PrerequisiteError (subclass of RuntimeError) on failure.
The caller catches PrerequisiteError and returns it to the user as a
structured refusal message — no stack trace.

CH-02 hardening (challenge-resolution requirement):
  - If session_state.extras does NOT contain the "wicked_testing_probe" key
    (probe silently failed during bootstrap), treat as missing — fail-closed.
    This closes the fail-open gap: a SessionStart probe exception that left
    no cached result must not allow crew to proceed unchecked.
  - The gate pointer message is intentionally short (AC-2): the full blocking
    notice was emitted once by bootstrap, so repeat is suppressed here.
  - Document the fail-open boundary in CONTRIBUTING.md.
"""


class PrerequisiteError(RuntimeError):
    """Raised when a crew command prerequisite check fails.

    Callers catch this and return it as a user-facing refusal with
    no stack trace — the message is the entire user output.
    """
    pass  # intentional: no additional fields needed; inherits RuntimeError.__init__


def crew_command_gate(session_state) -> None:
    """Gate check for crew command entry points.

    Raises PrerequisiteError when wicked-testing is missing or out-of-range,
    or when the probe was never cached (bootstrap exception path — fail-closed
    per CH-02 hardening).

    Called at the top of crew:start, crew:execute, crew:just-finish, and
    gate_dispatch. Returns None silently when all checks pass.

    Args:
        session_state: A SessionState instance (or any object with
            ``wicked_testing_missing`` and ``extras`` attributes).
            Passing None is safe — treated as "probe not run" → missing.
    """
    if session_state is None:
        # No session state at all — cannot determine probe result.
        # Fail-closed per CH-02: treat as missing.
        raise PrerequisiteError(
            "wicked-testing required — run: npx wicked-testing install"
        )

    extras = getattr(session_state, "extras", None) or {}

    # CH-02: probe key absent means bootstrap exception silently left no result.
    # Treat as missing (fail-closed), not as passing (fail-open).
    if "wicked_testing_probe" not in extras:
        wt_missing = getattr(session_state, "wicked_testing_missing", None)
        if wt_missing is True:
            # Flag was set even though probe result is absent — respect it.
            raise PrerequisiteError(
                "wicked-testing required — run: npx wicked-testing install"
            )
        # CH-02 fail-closed: absent probe key → treat as missing regardless of
        # wicked_testing_missing value (which may be False from fail-open path).
        if wt_missing is None:
            # probe was never cached (very early exit or bootstrap crash)
            raise PrerequisiteError(
                "wicked-testing required — run: npx wicked-testing install"
            )
        # wt_missing is False but probe key absent: CH-02 requires fail-closed.
        # The only safe exception is when the escape hatch was used — in that
        # case wt_missing=False AND extras has the probe key (set by bootstrap).
        # We're in the branch where the key is ABSENT, so block.
        raise PrerequisiteError(
            "wicked-testing required — run: npx wicked-testing install"
        )

    # Probe result is present — check its status.
    probe = extras["wicked_testing_probe"]
    status = probe.get("status", "missing") if isinstance(probe, dict) else "missing"

    if status == "ok":
        return  # All good — crew may proceed.

    # Generate a pointer message (short — full notice was shown at SessionStart).
    if status == "out-of-range":
        ver = probe.get("version", "unknown") if isinstance(probe, dict) else "unknown"
        pin = probe.get("pin", "unknown") if isinstance(probe, dict) else "unknown"
        raise PrerequisiteError(
            f"wicked-testing {ver} does not satisfy required range {pin}. "
            "Run: npx wicked-testing install"
        )

    # "missing", "error", or any other non-ok status.
    raise PrerequisiteError(
        "wicked-testing required — run: npx wicked-testing install"
    )
