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

### WICKED_VAULT_BIN

**For offline CI and dev environments without the wicked-vault peer only.**

wicked-vault (npm, ≥0.3, install `npx wicked-vault-install`) is a required peer
alongside wicked-bus/brain/testing. The garden's produces-gates re-derive evidence
through it (`scripts/qe/vault_gate.py` → `wicked-vault cross-check`). The CLI is
resolved in order:

1. `WICKED_VAULT_BIN` env var
2. a config preference
3. a global `wicked-vault` on `PATH`
4. a local `node_modules/.bin/wicked-vault`
5. `npx --yes wicked-vault`

Setting `WICKED_VAULT_BIN=""` (set-but-empty) is the vault analogue of
`WG_SKIP_WICKED_TESTING_CHECK`:

```bash
export WICKED_VAULT_BIN=""
```

Effect:
- Vault resolution is disabled entirely — none of the fallbacks above are tried.
- The produces-gate fails closed (or, with `--no-require`, falls back to the
  doctrine-light claim-only path).
- A SessionStart bootstrap check warns (non-blocking) when the vault isn't
  resolvable.

**When to use**: CI pipelines or local sessions where the wicked-vault peer is
unavailable and you accept gates failing closed (or running claim-only).

**When NOT to use**: Production environments, or any session where produces-gates
must actually re-derive evidence — disabling resolution means there is no vault to
cross-check against.

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
