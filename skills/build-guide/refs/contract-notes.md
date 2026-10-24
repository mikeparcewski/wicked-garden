# Contract v1: the schema, how this skill reads it, and what is still open

The contract is DES-BUILD-GUIDE's "Contract v1". Its machine form is wicked-core's
`schemas/build-guide.v1.json`, which garden vendors byte for byte as
`schemas/build-guide.v1.json`. The current copy is from wicked-core#1066's branch at 2ff7e37,
which is not merged yet. Re-vendor it when that branch merges; a test pins the copy to its git
blob. The core interpreter (`src/floor_guide.rs`) and probe (`src/floor_probe.rs`) are
authoritative, and `rehearse.py` mirrors them piece by piece. The skill never adds a field.

## What core's schema adds to the DES text (all optional)

| Field | Rule | Used for |
|---|---|---|
| `results.id`, `results.idJoin` | JUnit testcase attributes joined into an id (default `classname`,`name` joined by `::`); q is the enclosing testsuite's `name` | vitest: `["name"]`, so the ids match `vitest list` |
| `results.how.merge`, `list.merge` | stderr read into stdout, in order | cargo: libtest's `Running <binary>` lines go to stderr, and the section qualifier reads them |
| `probes.mutation2` | the same shape as `mutation`: a second failing test in another file | the `multi` probe |

## Pinned semantics

- **Matching.** Every regex applies to one line at a time, searched. The skill still writes
  `^…$`, and `check.py` warns on a rule without it.
- **Blocks.** A block's items are the contiguous item lines after its start. Blank lines are
  allowed, and any other line ends the block. At an end, the last block since the previous end
  (`last-before-end`, the default), or every one (`all`), is taken.
- **No shell.** Argv never passes through a shell. `{id}`/`{q}` values fill whole argv
  elements, so no escaping is needed for a shell. `{q}` is allowed in `alone` and `deselect`.
  `{files}` expands to one argv element per file.
- **Deselect composition.** Tokens before the first `{id}`/`{q}` token are added once (a leading
  `--` only when the argv has none). The tokens from the first through the last such token
  repeat per id, and the rest are added once. So a flag and its value are one token
  (`--skip={id}`). Deselect tokens also apply to `list.run`, because the `deselect` probe lists
  with one id deselected.
- **Argv order.** A results run is `run` + deselect tokens + `results.how.argvAppend`. Exit-only
  runs (a test run alone, during a mutation check) get no `argvAppend`.
- **Paths** (`results.how.path`, `probes.*.file`) are relative to `cwd`. **`invalidatedBy`**
  globs (`**`, `*`, `?`) are matched against the repo-relative files the change touched.
- **Ids.** Ids keep their qualifier only when `list` has a `section`; otherwise they compare by
  id alone. An empty id is dropped.
- **JUnit `<skipped/>`.** A skipped testcase neither passed nor failed.
- **Kinds.** The results kind is `text` or `junit`. `json-lines` and `tap` are reserved.
- **Probes and the floor.** `verified.results` keys are `list`, `run`, `ids`, `alone`,
  `deselect`, `mutation`, `multi`, and `affected` when the check has that piece. The floor
  relies on a check only when all of them pass. It also needs a non-empty `failedExit`, `alone`,
  `deselect`, a `list` (to compile) and a `text`/`junit` kind. `run` passes on a red base when
  its failures parse. A new failure that passes when run alone counts as the suite's flake and
  is set aside.
- **`verified`** is written by `floor probe` into the `--guide` file in place, including
  `runnerVersion`, which it records by running the check's `version` piece.

## Rulings, as core implements them at 2ff7e37 (round 16)

1. **Regex placeholders.** `{id:re}` is the id regex-escaped (Rust `regex::escape`), repeated
   per id like `{id}`. `{ids:re|}` is every id regex-escaped and joined with `|` in ONE token,
   never repeated. A guide that puts it among the per-id tokens is refused, and `check.py`
   errors on that too. Both are allowed in `deselect.append` and `alone.run`; in `alone.run`,
   `{ids:re|}` is the one test's id. The vitest seed deselects with
   `--testNamePattern=^(?!(?:{ids:re|})$)` and runs one test with
   `--testNamePattern=^{id:re}$`.
2. **Runner version.** An optional `version: {run: argv}` piece, for test checks only (the
   schema's `dependentRequired` makes `version` need `list`, and `list` need `results`). The
   probe runs it (stdout and stderr merged), records the first output line as `runnerVersion`
   and adds a required `version` probe. A different version makes the check stale. Nothing fills
   `runnerVersion` by hand.
3. **Green base, and retry.** The probes need a GREEN clean run. On a red one, `run` fails
   ("needs a green base: …"), and so do `ids`, `alone`, `deselect`, `mutation` and `multi`.
   Onboard from a green commit. When any probe fails (other than for a missing piece,
   `fail: no \`…\``), the WHOLE probe re-runs once on a fresh copy, and that retry's results are
   recorded, each marked ` (retried)`. `pass (retried)` counts as passed.
4. **Exit codes.** 0 passes. A `failedExit` code with parsed failures is tests failing. A
   `failedExit` code with no parsed failure is `base_red_unseparated` on the base and
   `new_failure` on the head. Any other non-zero code is `could_not_run`.
5. **The guide replaces detection.** When the base carries a usable guide, its checks ARE the
   floor's checks (argv, cwd, stage; an absent `stage` means both). So the skill declares EVERY
   step CI gates on: install, build, format, lint, typecheck and test. A check with no `list` is
   a gate: `name`, `cwd`, `run`, and a `failedExit` if it has one; no `results`, no `version`.
   The probe skips it, and its exit code alone decides it. `check.py --repo` warns for every CI
   step no check declares. A step counts as declared when a check's `run` equals its argv, or
   the argv of the recipe or npm script it runs (for an npm script, also with `npx` in front).
6. **`alone` covers both sides.** The mutated test run alone must fail, naming exactly it (JUnit:
   exactly one testcase ran). A passing test under the same qualifier, run alone, must be green
   (JUnit: exactly it ran). A runner whose qualifier is the test file (cargo) needs that passing
   test inside the mutation file.
7. **Composition around `--`.** For `results.how.argvAppend` and `deselect.append`, the tokens
   before the list's own `--` (all of them when it has none) go just before the argv's `--` (at
   the end when it has none). The tokens after it go last, behind ONE `--`; a second `--` is never
   emitted. A results run is `deselected(run, ids)` composed with `argvAppend`.
8. **`derivedFrom` holds git pathspecs.** Globs such as `crates/*/Cargo.toml` match, and
   `check.py --repo` errors on an entry that matches nothing.

9. **Load-time validation** (the floor and the probe alike). A guide with an empty `run`, a
   `stage` other than `creator`/`verify`, or a check with a `list` and no `failedExit` does not
   load, and detection is the whole floor. The schema says the same: `dependentRequired` makes
   `list` need `results` and `failedExit`, and `failedExit` has `minItems: 1`. `check.py` reports
   each in the floor's words.
10. **Coverage is per directory.** A guide replaces detection only in the directories its checks
    cover (their `cwd`s, at any stage). A detected package that no check covers keeps its
    detected checks, judged by exit code. The skill still declares every CI gate, sub-packages
    included, each with the step's `working-directory` as `cwd`. `check.py --repo` matches CI
    steps by argv and working directory. A job-level `defaults.run.working-directory` is not read.
    Expensive gates take `stage: ["verify"]`; wicked-core's own guide does this for `core-ts`.
11. **Deleted files.** A change that deletes a file, or renames one away, makes `affected` run the
    full check.
12. **JUnit per testcase.** Each `<testcase>` is judged on its own: two that share an id and both
    ran are both counted (no de-duplication), and a `<skipped/>` one neither passed nor failed.
    `multi` needs two DISTINCT failures (the second is not the first again), and `affected` must
    fail with a `failedExit` naming the mutated test.
13. **`results.how.env`** applies only to runs whose results are read (the run, the probes' runs).
    The `list` and `version` runs get the plain environment.
14. **Placeholders fill in one pass.** A value that itself contains `{q}` is not filled again.

## Why the pytest seed is text, not JUnit

pytest's `--collect-only -q` list and `--deselect` take node ids, and a class method's node id
carries its class: `tests/test_calc.py::TestGroup::test_x`. JUnit has no attribute that holds
the class alone:
- `classname` is `tests.test_calc.TestGroup`, dotted, with the module path in front;
- `name` is `test_x`;
- `file`, with `-o junit_family=xunit1`, is `tests/test_calc.py`.

`results.id` can only join whole attributes, so the closest it gets, `["file","name"]`, gives
`tests/test_calc.py::test_x`. That is right for module-level tests and wrong for every class
method, and the `ids` probe fails on it. Rebuilding the node id would need a transformation
(take the last dotted segment of `classname`) that the contract does not have, and should not
grow for one runner. pytest's own short test summary (`-rfE`, with `--force-short-summary` so
CI mode keeps one line per failure) prints the node id itself. So the seed is `text`, and it
passes every probe. `tests/build_guide/guides/pytest-junit.json` keeps the JUnit attempt as the
documented negative case.
