# Seat sandbox limits, by role

What a governed seat can and cannot do, so a seat plans around it instead of rediscovering it and
filing it as a memory (governed-worker rule A7 sends such a finding here). This is the one list; the
seat image build itself is documented in wicked-crew (`docs/seats.md`, "Seat images") and wicked-core
(`CLAUDE.md` and `containers/seats/seat.Dockerfile`).

A limit is a property of the seat, not of the change under review. Report it separately from any
assertion failure, name the floor record you rely on instead, and never claim a local run that did
not happen.

## Limits every role shares

| Limit | What you see | What to do |
|-------|--------------|------------|
| Loopback listen denied | `listen EACCES 127.0.0.1` (also a dev server's HMR port). Tests that bind a real TCP or HTTP listener fail or time out in their fixture setup. | Run the tests that use injected routes or pure logic. Leave real-listener tests to the floor or a socket-capable lane. Do not retry listener variants. |
| Write fence | Writes are allowed only inside the worktree and the unit's own notes, ledger and scratch directories. A write outside them (`/tmp` included) is denied. A write whose target the fence cannot resolve to a literal path is also denied: a shell variable (`$F`, an unset notes root), a glob or brace, a `sed -i` through a variable. | Spell every write target as a literal path. Put scratch files under the worktree's gitignored scratch directory, or under the unit's own directory. |
| No reading outside the worktree | Reads of other runs' worktrees, sibling units' notes (the parent of the notes directory), the home toolchain directories and browser caches are denied. | Use only the notes directory and the prior-phase outputs you were handed. Treat the denial as final and say which record you could not inspect. |
| No SAST or secrets scanners | `semgrep`, `codeql`, `njsscan`, `gitleaks`, `trufflehog` and `detect-secrets` are not on PATH. | Check with `command -v` before planning automated security coverage. Read the code, and say that no scanner ran. |
| No browser | No Playwright package for Python, no browser binary, and a download has failed in seats (the engine installs dependencies without lifecycle scripts, so no postinstall fetch runs, and the egress allowlist can be narrower than the host's). | The end-to-end journeys and screenshots cannot run in a seat. Say the screen check was not done. CI or a seat with browsers does it. |
| Estate broker is read-only | The shim relays a fixed read set (search, retrieve, traverse, path, blast radius, lineage, hotspots, communities, rules, recalls, proposal submit). `FetchContent` is refused as "not relayed". | Read source from the worktree. Where graph content is empty, say that content grounding was unavailable. |
| Hand-built artifacts are absent | A compiled CLI (`dist/`) is not provisioned, so suites that launch it fail with MODULE_NOT_FOUND. | Do not build into a guarded checkout. Cite the floor record for those suites. |
| Cache writes can fail | A test runner may not be able to create its cache under `node_modules`. | A warning alone is not a failure. Turn the cache off in a scratch config if the run errors on it. |

## Per role

| Role | Writes | Cargo | Other limits |
|------|--------|-------|--------------|
| Creator (build seat) | The worktree and its own scratch directory, by literal path. | See "Cargo" below. Plan as if absent: the hand-off floor compiles and tests the code. | The worktree has no `origin` remote, so a git helper that needs one fails. Hand-check formatting (line width, trailing whitespace) when you cannot run a formatter. |
| Reviewer (read-only) | None in the checkout. Notes only, in the unit's notes directory. | Often absent. Do not run or claim a Rust check. Cite the floor record for the exact tree. | A prior phase's evidence directory may be missing. Keep supplied command records as attributed evidence. A second build target directory is not available. |
| Evaluator (read-only) | None in the checkout. Notes only, by literal path. | Often absent, same as the reviewer. | Records-only runs: do not rerun the build or write build output into a write-back root. Keep the floor result apart from the builders' summaries. |
| QE evidence unit | Its ledger directory and notes, by literal path. | Not needed. | The ledger package is the copy the unit is handed through `WICKED_LEDGER_PKG_DIR`; import its `lib/index.mjs` entry. A ledger run needs a run record, and a scenario needs `format_version`. Never install it in the seat. |
| Chat seat | Nothing in the worktree; a file write is denied. | Not applicable. | Put the answer in the reply. |

## Cargo

The statements disagree on the surface, and both are right about different things.

- The seat image Dockerfile is built on the checks floor image, which links the pinned Rust toolchain
  into `/usr/local/bin`. An image the engine builds with its default recipe therefore has cargo.
- That holds only for that recipe. The Dockerfile's own default base is a plain Node image, so an
  image built by hand from it has no Rust, and an operator override of the base image (a project
  toolchain image) has Rust only if that image brings it.
- Review, evaluator and creator seats have repeatedly reported no `cargo`, `rustc` or `rustup` on
  PATH, a `CARGO_HOME` that does not exist, and a fence that denies reading the home toolchain
  directory. The floor runs Rust checks in its own container, outside the seat.

The rule for a seat: do not assume cargo. Check `command -v cargo`. When it is missing, do not
install it, and do not report a Rust command as run. Record the command as unavailable and rely on
the floor record for the exact tree. Where a seat does have cargo, its `CARGO_HOME` lives in the
unit's per-run replica and is never written back, and a fenced unit's target directory is its
per-unit scratch directory, removed at settle.

Whether the engine-built default image's cargo is reaching a given seat is for wicked-core to
confirm by inspecting the built image. This list does not decide it.

## Not in this list

These are not seat limits and are not memories either: a verdict or ruling on one run, a test that is
red on both the base and the change (cite a base-tree run before calling it pre-existing), and a
repository's own script that fails for the repository's own setup (that is an A7 memory).
