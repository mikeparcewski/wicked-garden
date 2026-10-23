# build-guide eval cases (agent runs, user-triggered; graded deterministically)

These cases measure whether an agent that follows the `wicked-garden-build-guide` skill
produces the right guide for five kinds of repo. The deterministic suite
(`tests/build_guide/test_build_guide_*.py`) checks that the scripts, seeds and fixtures behave.
These cases check that **an agent following the skill text** makes the right choices: structured
or text results, a summary-anchored parser, an honest "probe unavailable" or "no guide".

| Case | Fixture | What it proves |
|---|---|---|
| `cargo-text-parser` | `cargo-repo` | no structured output on stable cargo, so a text parser on libtest's own summary |
| `pytest-junit` | `pytest-repo` | JUnit is tried, its ids do not round-trip under contract v1, and the agent falls back to the short summary and says why |
| `vitest-junit` | `vitest-repo` | JUnit with round-tripping ids; the two-id deselect limit is reported |
| `fake-runner-no-structured-output` | `tinyrun-repo` | a parser generated from real output, anchored on the runner's summary, not forged by test output |
| `no-tests` | `no-tests-repo` | no guide and a plain statement of it; no invented test command |

## Running one

1. Copy the fixture to a scratch directory. For `vitest-repo`, run `npm install` there.
2. Give an agent with the skill installed the case's `prompt`, with the copy as its working
   directory. Today `host.floor_probe` is `unavailable`, because `wicked-core floor probe` lands
   with wicked-core#1066. Keep the guide it proposes (`.wicked/build-guide.json`, or the draft it
   shows) and its final message.
3. Grade it: `python3 tests/build_guide/eval_grade.py --case <case> --repo <copy> --message <file> [--guide <file>]`.

The grader re-derives every expectation. It runs `check.py --draft` and `rehearse.py` on the
produced guide against the copy, and it matches the message literally. It takes nothing from the
agent's claims. A case passes when every assertion passes. Once the probe exists, add a
`probe` expectation and re-run.

`tests/build_guide/test_build_guide_eval_cases.py` validates every case's shape and grades each
case's **reference outputs** (the seeds and test guides with a reference message). That proves
the grader and the expectations agree. It does not grade an agent.
