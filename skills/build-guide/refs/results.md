# Results: structured first, a text parser only when there is none

## The id round-trip test (decides structured vs text)

A result format is only usable if the ids it reports are the ids the other pieces take. Ids
from `results` must appear in `list`, and they must work as `{id}` in `alone` and `deselect`.
The floor filters base failures through the base `list` and deselects them by id, so an id that
does not round-trip means no exclusion. Prefer the structured format that passes this test. If
the runner's structured ids do not round-trip, use the runner's own text summary, whose ids do.

**Worked example (pytest, JUnit vs text).** pytest's `--collect-only -q` list and its
`--deselect` take node ids (`tests/test_calc.py::TestGroup::test_x`). The best JUnit reading,
`-o junit_family=xunit1` with `results.id: ["file","name"]`, gives `tests/test_calc.py::test_x`.
That equals the node id for module-level tests, but not for class methods, and the `ids` probe
fails on it. pytest's short test summary (`-rfE`) prints `FAILED <node id>`,
which round-trips for every test. So the pytest seed is `text` on that summary.

## Structured kinds

- **junit**: put the reporter flag in `results.how.argvAppend` and the file in
  `results.how.path` (relative to `cwd`, under a scratch-only directory such as `.wicked-floor/`).
  The id is the `results.id` attributes (default `classname`,`name`) joined by `results.idJoin`
  (default `::`). Choose the attributes and the join that make the id equal to what `list`
  prints and `alone`/`deselect` take. A testcase with `<failure>` or `<error>` has failed, and
  one with `<skipped/>` neither passed nor failed (a name filter left it out).
- **json-lines** / **tap**: reserved in v1, because the interpreter reads only `text` and
  `junit`. Use JUnit, or text on the runner's summary.

## Writing a text parser

Write it only when the runner has no structured output, or its structured ids fail the
round-trip test.

1. **Capture real output** of this repo's runner with the mutation probe in a scratch copy
   (`rehearse.py`, or run it yourself). Write the rules against that text.
2. **Use the runner's own final summary** (and check it with more than one failure: one item
   that wraps onto a second line ends the block). Most runners end with a block that lists the failed
   ids (libtest's second `failures:` list, pytest's `short test summary info`). Express it as a
   `blocks` rule: `start`, `item` with `(?P<id>…)`, `end`, and `use`. Avoid per-line `failed`
   rules on lines interleaved with test output, because a test that prints a look-alike line
   would forge a failure. Use `failed` only when the runner prints nothing else.
3. **`use: last-before-end`** when the runner prints the same `start` line more than once
   before the summary ends: libtest prints `failures:` before the captured output and again
   before the list. Only the items after the last `start` count. **`use: all`** when every
   block is a real list.
4. **`section`** (optional): a line that opens a qualifier scope, with `(?P<q>…)`, for example
   a test binary or file header, when ids repeat across scopes. Set `expectQ` to match. When
   the runner prints that line on stderr, set `results.how.merge` (and `list.merge`).
5. **RE2 only.** No lookaround, backreferences, atomic or possessive groups (the interpreter is
   Rust). Every regex starts with `^` and ends with `$`, so that a full-line match and an
   anchored search agree. `check.py` enforces both rules.
6. **The ids the parser names must be the ids `list` prints.** Write `list.item` against the
   same captured run.
7. **Deselect composition** (it also applies to `list.run`, since the `deselect` probe
   deselects on the list). Tokens before the first `{id}` token are appended once (a leading
   `--` only when the argv has none). The tokens from the first `{id}` token through the last
   one repeat per id, and the rest are appended once. So put a flag and its value in **one**
   token (`--skip={id}`, `--deselect={id}`). With `"--skip","{id}"`, only the value repeats,
   giving `--skip a b`.

## Worked examples (also in `assets/seeds/`)

- **cargo / libtest** (`cargo-libtest.json`, reconciled with wicked-core's own probed guide):
  stable cargo has no JUnit/JSON (`--format junit` is nightly-only), so the guide is text. With
  `results.how.merge` and `list.merge`, the `section` reads libtest's `Running <binary>` lines
  (on stderr), so ids are qualified by test binary. The block runs from `^failures:$` to
  `^test result: FAILED`, with item `^    (?P<id>\S+)$` and `use: last-before-end`. `run` is
  the CI command exactly (`cargo test --locked --workspace --no-fail-fast`; drop `--locked` if CI
  does not use it). `alone` is `-- {id} --exact`. `deselect.append: ["--","--skip={id}","--exact"]`
  adds the separator once, `--skip=<id>` per id, and `--exact` once; libtest rejects a repeated
  `--exact`. The mutations are new integration test files
  (`tests/zz_floor_probe_mutation.rs`, `…_two.rs`). wicked-core's own mutations also arm a
  `ctor` hook its test harness needs, so copy a repo's own test preamble when it has one.
- **pytest** (`pytest-short-summary.json`): text on `-rfE`. The block runs from
  `^=+ short test summary info =+$` to the final count line, with item
  `^(?:FAILED|ERROR) (?P<id>.+?)(?: - .*)?$`. `list` is `--collect-only -q`, `deselect` is
  `--deselect={id}`, and `-p no:cacheprovider` keeps the scratch copy clean. When `CI` is set,
  pytest prints each failure's full, multi-line message in the summary. A continuation line ends
  the block, so only the first failure would be named. `results.how.argvAppend:
  ["--force-short-summary"]` keeps one line per failure (check that `pytest --help` lists the
  flag).
- **vitest** (`vitest-junit.json`): JUnit through `--reporter=junit --outputFile=…`, with
  `results.id: ["name"]` (the full name, `suite > test`). That matches `vitest list`'s
  `file > name` line with item `^\S+ > (?P<id>.+)$`. The tests a name filter leaves out appear
  as `<skipped/>` testcases, which neither pass nor fail, so `alone` holds. vitest takes one name
  pattern only and rejects a repeated one, so `["--testNamePattern=^(?!{id}$)"]` passes the
  `mutation` probe but fails `multi` (two ids). Say so in the proposal: with two or more base
  failures, that check does not exclude. `{id}` also lands unescaped inside a regex.
- **A runner with no structured output** (the `tinyrun` fixture in the garden tests): a block
  from `^--- tinyrun summary ---$` to `^--- [0-9]+ failed, [0-9]+ passed ---$` with item
  `^FAIL (?P<id>\S+)$`. A per-line rule on `... FAIL` would be forged by test output that prints
  the same text.
