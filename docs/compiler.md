# The Compiler

`/wicked-garden:compile` takes any repo and emits a **self-contained,
vault-backed build gate** into `<repo>/.wicked/` — a gate that proves the
build's claims and runs with **no wicked-garden runtime present**.

The compiler is in `scripts/compiler/compile.py`. The detection pass is
`scripts/compiler/phase0/detect.py`.

## What it does

The compiler reads a repo and works out how to gate it:

1. **Detect the bindings** (`phase0/detect.py`) — test / lint / build
   commands, the ecosystem, any structured `claims:` docs, and the repo's
   risk surfaces.
2. **Derive a contract** — a multi-claim wicked-vault contract built from
   what it found.
3. **Emit a harness** into `<repo>/.wicked/` (see below).

## What it emits

Everything lands in `<repo>/.wicked/`:

| File | What it is |
|------|------------|
| `bindings.json` | The detected test/lint/build commands + ecosystem |
| `contract.json` | The derived multi-claim vault contract |
| `gate.py` | A **stdlib-only** gate — imports nothing from wicked-garden |
| `claims_lint.py` | Emitted only when the repo has structured `claims:` docs |
| `README.md` | How to run and wire up the emitted gate |

## Runs with no wicked-garden present

This is the property that makes the compiler worth having: the emitted
`gate.py` carries **no dependency on the wicked-garden runtime**. It
resolves the vault via `npx` and re-derives the build's claims itself —
records the test/lint/build commands, then cross-checks. A
claimed-but-false "tests pass" gets **REJECTED**; a missing vault **fails
closed** rather than waving the build through.

You compile once; the gate then lives in the target repo and runs on its
own, in CI or on a developer's machine, with nothing of the garden
installed.

> **Why vault-direct, not loom?** Inside wicked-garden the produces-gate
> re-derives through **wicked-loom** (which shells the vault). The *emitted*
> gate deliberately does **not** — it shells **wicked-vault** directly via
> `npx`. It has to run in a foreign repo with neither wicked-garden nor
> wicked-loom present, so it depends only on the one public re-derivation
> utility (the vault). This split is intentional, not drift: the garden gate
> assumes loom is installed; the emitted gate cannot.

## The on-switch rule

Compile the **trigger** and the **enforcement**; never compile the
**tool**.

The vault is a runtime-resolved utility — resolved via `npx`, skippable,
and not something the compiler bakes into the repo. The *trigger* that
fires the gate, on the other hand, is exactly what the compiler installs.
You don't ship a copy of the tool; you ship the on-switch and the rule it
enforces.

## Triggers

Optionally, the compiler installs what actually fires the gate:

- **Git pre-push hook** — idempotent, never clobbers a foreign hook, and
  resolves the gitdir pointer so it works inside worktrees.
- **GitHub Actions workflow** — its toolchain setup is derived from the
  detected ecosystem.

Pass `--trigger hook,ci` (or `all`) to install them.

## Usage

```bash
# Detect + emit the harness into the repo's .wicked/
/wicked-garden:compile ~/path/to/repo

# Also install the triggers that fire the gate
/wicked-garden:compile ~/path/to/repo --trigger hook,ci
/wicked-garden:compile ~/path/to/repo --trigger all

# Run the emitted gate (exit 0 = PASS)
python3 .wicked/gate.py
python3 .wicked/gate.py --check      # don't kick off a new run
python3 .wicked/gate.py --dry-run    # show what would run
```

## Proven

The compiler was tested on an unseen repo (memos) and self-hosted on
wicked-garden itself.
