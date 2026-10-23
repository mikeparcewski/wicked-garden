# Contract v1: the schema, how this skill reads it, and what is still open

The contract is DES-BUILD-GUIDE's "Contract v1". Its machine form is wicked-core's
`schemas/build-guide.v1.json`, which garden vendors byte for byte as
`schemas/build-guide.v1.json`. The current copy is from wicked-core#1066's branch at f88a639,
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

## Rulings (coordinator, 2026-10-23; core implements them)

1. **Regex placeholders.** `{id:re}` is the id regex-escaped, repeated per id like `{id}`.
   `{ids:re|}` is every id regex-escaped and joined with `|` into one token. A runner that
   takes a single exclusion pattern uses the second. The vitest seed deselects with
   `--testNamePattern=^(?!(?:{ids:re|})$)`.
2. **Runner version.** An optional `version: {run: argv}` piece. The probe records
   `runnerVersion` from it, and the floor treats a different version as stale. The skill writes
   the piece; nothing fills `runnerVersion` by hand.
3. **Flaky probes.** Core retries a failed probe once, and a probe that fails twice leaves the
   guide unverified. `rehearse.py` does the same, and names the retried probes.
4. **A `failedExit` code with no parsed failure** is `base_red_unseparated` on the base and
   `new_failure` on the head. Any other non-zero code is `could_not_run`.
5. **The guide replaces detection.** When a usable guide exists, its checks replace the floor's
   own check detection, and each runs at the `stage`s it declares.

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
