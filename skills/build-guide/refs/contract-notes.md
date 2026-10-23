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
- **`verified`** is written by `floor probe` into the `--guide` file in place. The probe leaves
  `runnerVersion` blank, and the skill fills it from `<runner> --version` (`probe.py
  --version-argv`) before it proposes the guide.

## Still open (for wicked-core)

1. **`{id}` inside a regex token.** No escaping is needed for a shell, but when the token is a
   regex for the runner (vitest `--testNamePattern=^(?!{id}$)`), an id with metacharacters
   still changes its meaning. The contract has no regex-escape form.
2. **`runnerVersion` and staleness.** The DES calls a guide stale when the runner version
   changes. The floor's `usable()` checks `derivedFrom` and `invalidatedBy`, but not
   `runnerVersion`, and the probe leaves the field blank. As it stands, the field is a record,
   not a staleness check.
3. **A flake that fails the deselected run.** With a clean base, the mutation and `multi`
   checks require the deselected run to exit 0. A new failure that passes alone is set aside
   from the failure list, but it still turns that exit non-zero, so the check fails.
4. **`failedExit` vs could-not-run.** cargo exits 101 on a compile error and on a libtest usage
   error, and vitest exits 1 on a config error. A floor run that exits with a `failedExit` code
   but names no failure is not described.
5. **`run` must equal the floor's declared check.** The guide is the allowlist (`check_for`
   matches argv and cwd exactly). How crew declares the floor's check argv, so that it can
   match `run`, is not stated.
