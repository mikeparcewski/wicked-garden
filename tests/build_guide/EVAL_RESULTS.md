# build-guide eval results

## 2026-10-23: creator-run, probe unavailable

**Who ran it.** The same agent that wrote the skill followed it on scratch copies of the five
fixtures. Grading was deterministic, with `eval_grade.py`. This is a smoke run of the skill's
path, **not an independent eval**: the creator ran it, and the drafts started from the seeds the
creator wrote. An independent run, with a different agent that has only the skill installed, is
still to do (see `eval_cases/README.md`).

**Schema.** `schemas/build-guide.v1.json` is vendored from wicked-core#1066's branch at 2ff7e37 (round 16; the earlier df67a95, f88a639, e2ad012 and 3fb9c86 runs also graded 5/5).

**Runs.** The five cases ran twice, once plain and once with `CI=true` (pytest changes its summary format in CI). Both runs graded 5/5.

**Host.** `wicked-core floor probe` is not available yet (it lands with wicked-core#1066), so
every run took the probe-unavailable path. The runners were cargo 1.99.0, pytest 9.1.1,
vitest 5.0.5 (after `npm install`) and python3 for tinyrun.

| Case | Attempts | Outcome | Grade |
|---|---|---|---|
| `cargo-text-parser` | 1 | a `build` gate for CI's `cargo build` step, and a test check reconciled with wicked-core's own probed guide (merged stderr, binary-qualified ids, two mutations with a passing `floor_probe_mutation_beside` test in the first, `version` `cargo --version`); every probe passes, `version` included; probe unavailable | 9/9 pass |
| `pytest-junit` | 2 | attempt 1 (JUnit, xunit1, `results.id: ["file","name"]`) failed `ids` on both attempts (the whole probe retried): a class method's JUnit id is not its node id. Attempt 2 (text on `-rfE` with `--force-short-summary`, plus an `install` gate) passed every probe. Probe unavailable | 9/9 pass |
| `vitest-junit` | 1 | an `npm install` gate, and JUnit with `results.id: ["name"]`; deselect takes every id in one `{ids:re\|}` token, so every probe passes, `multi` included; probe unavailable | 8/8 pass |
| `fake-runner-no-structured-output` | 1 | text parser generated from real output, anchored on tinyrun's summary block; CI's `make test` is declared through its recipe; every probe passes; probe unavailable | 9/9 pass |
| `no-tests` | n/a | no guide; reported in the exact words "no build/test guide: the floor will run this repo's checks exit-code only" | 2/2 pass |

**What this does not show.** It does not show that the core probe agrees with the rehearsal.
It cannot: the probe is not installed here. The rehearsal mirrors #1066's `src/floor_probe.rs` at 2ff7e37, read from source. Re-run every case once `floor probe` ships, and add a
`probe` expectation.
