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

> **Historical note (Phase 6c):** the `WG_SKIP_WICKED_TESTING_CHECK` escape
> hatch and the SessionStart wicked-testing probe it bypassed were removed
> when wicked-testing retired — the qe domain ships in-catalog (the
> `wicked-garden-qe` router + specialists), so there is no peer package to
> probe. The acceptance gate concept now lives in wicked-crew's
> `/runs/:id/acceptance` route.

### WICKED_VAULT_BIN

**For offline CI and dev environments without the wicked-vault peer only.**

wicked-vault (npm, ≥ 0.5.0 <!-- vault-floor -->, install `npm i -g wicked-vault`)
is the one required peer (the loom engine is built into the garden; bus is an
opt-in layer). The garden's produces-gates re-derive
evidence through the built-in loom engine — `scripts/qe/vault_gate.py` runs
`loom gate` in-process (`scripts/_loom.py` → `scripts/loom/`), which shells
`wicked-vault cross-check`, so the vault is the backend loom re-runs the
verifier against. loom resolves the vault; the concrete-install
probe (`vault_available`) and the `WICKED_VAULT_BIN` kill-switch below still apply.
The vault CLI is resolved in order:

1. `WICKED_VAULT_BIN` env var
2. a config preference
3. a global `wicked-vault` on `PATH`
4. a local `node_modules/.bin/wicked-vault`
5. `npx --yes wicked-vault`

Setting `WICKED_VAULT_BIN=""` (set-but-empty) disables vault resolution:

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

SessionStart probes in `hooks/scripts/bootstrap.py` (vault / bus / loom
dependency checks) are fail-open: any exception is caught, logged to stderr
with actionable detail, and bootstrap continues. Gates that *enforce*
evidence are fail-closed at their own layer (`scripts/qe/vault_gate.py`),
never at the probe.
