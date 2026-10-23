# Contract v1: the schema, how this skill reads it, and what is still open

The contract is DES-BUILD-GUIDE's "Contract v1". Its machine form is wicked-core's
`schemas/build-guide.v1.json`, which garden vendors byte for byte as
`schemas/build-guide.v1.json`. The current copy is from wicked-core#1066's branch at df67a95,
which is not merged yet. Re-vendor it when that branch merges; a test pins the copy to its git
blob. The core interpreter (`src/floor_guide.rs`) and probe (`src/floor_probe.rs`) are
authoritative. `rehearse.py` mirrors them piece by piece, and adds two checks the core probes
do not make. The skill never adds a field to work around an open question.

## What core's schema and interpreter add to the DES text

These are in core's schema or code but not in the DES "Contract v1" block. The skill uses them
where a runner needs them.

| Addition | Rule | Used for |
|---|---|---|
| `results.id`, `results.idJoin` | JUnit testcase attributes joined into an id (default `classname`,`name` joined by `::`); q is the enclosing testsuite's `name` | vitest: `["name"]`, so that ids match `vitest list` |
| `results.how.merge`, `list.merge` | read stderr into the same stream, in order | runners that name their test binaries on stderr (cargo's `Running …`) |
| `{q}` in `alone` / `deselect` | the qualifier, next to `{id}` | targeting a scope, when the runner has a flag for it |
| deselect composition | tokens before the first `{id}`/`{q}` token once (a leading `--` only when the argv has none), the tokens through the last such token once per id, the rest once | `["--","--exact","--skip={id}"]` for cargo; a flag and its value go in **one** token |
| argv order | a results run is `run` + deselect tokens + `results.how.argvAppend`; exit-only runs (the mutation run alone) get no `argvAppend` | — |
| keyed ids | ids keep their qualifier only when `list` has a `section`; otherwise they compare by id alone | — |
| line matching | every rule is searched in each line (not anchored for you) | the skill still writes `^…$`, and `check.py` warns on a rule without it |
| blocks | a block is the contiguous item lines (blank lines allowed) after a start; any other line ends it; at an end, the last block since the previous end (`last-before-end`, the default) or every one (`all`) | libtest's second `failures:` list |
| probes | `list`, `run` (a red base passes when its failures are parsed), `mutation` (exactly one NEW failure; deselecting it restores the clean failures; alone it fails), `alone` (the first listed passing id), `deselect` (the **list** with that id deselected lists exactly the rest), `affected` | `verified` is written into the `--guide` file in place |
| required fields | the schema requires only `version`, `name`, `run` and `results.kind`, but the interpreter needs `list` (and a `parser` for text) to compile | the skill always writes every piece |

So deselect tokens must also work on the **list** command: the `deselect` probe deselects on
`list.run`.

## Found while rehearsing against core (for wicked-core; not settled here)

1. **The JUnit reader counts `<skipped/>` testcases.** vitest's JUnit reports the tests a name
   filter left out as skipped testcases. Core's `alone` probe requires every reported testcase
   to be the one id, so it fails for vitest. Reading a `<skipped/>` testcase as not run would
   fix it.
2. **The probes check one passing id and the mutation.** A JUnit id that is wrong for some
   tests passes them. pytest's xunit1 `file`+`name` is the node id of a module-level test but
   not of a class method (`…::TestGroup::x`). Such a failure is never in the base list, so it
   is never excluded: the floor fails safe, but the guide is "verified" and does nothing for
   those tests. `rehearse.py`'s `round-trip` check sees it.
3. **One id cannot show that per-id deselect works for two.** vitest rejects a repeated name
   pattern. A flag split from its value (`"--skip","{id}"`) repeats only the value. pytest's
   `-k` keeps only the last value. Each passes the one-id probes. `rehearse.py`'s
   `deselect-many` catches it. A two-id mutation probe would too.
4. **No escaping for placeholders.** `{id}` is substituted raw. When the token is a regex
   (vitest `--testNamePattern=^(?!{id}$)`), an id with metacharacters changes its meaning.
5. **`failedExit` vs could-not-run.** cargo exits 101 on a compile error and on a libtest usage
   error, and vitest exits 1 on a config error. The `run` probe requires parsed failures for a
   non-zero exit, but a floor run that crashes with a failedExit code and names no failure is
   not described.
6. **`run` must equal the floor's declared check.** The guide is the allowlist (`check_for`
   matches argv and cwd exactly). The cargo seed keeps `run` equal to the CI command, and puts
   `--` in the deselect prefix.
7. **A block cannot hold a multi-line item.** Any non-item line ends a block, so a summary
   whose entries wrap loses every failure after the first. pytest does this when `CI` is set,
   and the seed avoids it with `--force-short-summary`. The one-mutation probe cannot see it;
   `deselect-many` (two mutations) does.
8. **`json-lines` and `tap`** are reserved in v1. `check.py` refuses them until the
   interpreter reads them.
