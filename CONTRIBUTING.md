# Contributing to wicked-garden

## Development Setup

Clone the repo and install with `uv`:

```bash
git clone https://github.com/mikeparcewski/wicked-garden.git
cd wicked-garden
uv sync
```

Run the test suite:

```bash
uv run pytest tests/ -x
```

## Escape Hatches

### WG_SKIP_WICKED_TESTING_CHECK

**For offline CI and dev environments without npm access only.**

When set to `1`, the SessionStart wicked-testing probe is bypassed:

```bash
export WG_SKIP_WICKED_TESTING_CHECK=1
```

Effect:
- `wicked_testing_missing` is set to `false` — crew commands proceed normally.
- The probe subprocess (`npx wicked-testing --version`) is never invoked.
- A single warning is emitted to **stderr** (not to the Claude session briefing):
  `WG_SKIP_WICKED_TESTING_CHECK is set — wicked-testing version check bypassed (offline dev mode). Do not use in production.`

**When to use**: CI pipelines where npm is unavailable; local development on
machines without Node.js installed; offline development sessions.

**When NOT to use**: Production environments, any session where crew QE gates
will actually run (the bypass skips the version check but wicked-testing agents
will still fail if the package is absent).

This escape hatch is a developer override. It does NOT appear in user-facing help,
setup wizard output, or the README. It is not a supported production configuration.

### Fail-open boundary

The wicked-testing probe (`_wicked_testing_probe.probe()`) is called by
`_probe_wicked_testing()` in `hooks/scripts/bootstrap.py` at SessionStart.
Any exception that escapes the probe is caught by `_probe_wicked_testing()`
which logs actionable detail to stderr and continues bootstrap (fail-open).

**CH-02 close**: `crew_command_gate()` in `scripts/crew/_prerequisites.py`
is fail-closed: if `session_state.extras["wicked_testing_probe"]` is absent
(probe exception path), the gate treats this as missing rather than passing.
This prevents silent unblocked crew runs when the probe fails silently.
