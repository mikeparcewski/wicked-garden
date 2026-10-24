# Discover: from what the repo declares to a draft check

## Reading order (most reliable first)

1. **CI config** says how the repo really tests. Look in `.github/workflows/*.yml`
   (`run:` steps, including `run: |` blocks), `.gitlab-ci.yml` (`script:`), and `Makefile` or
   `justfile` recipes that CI calls. Note any setup the test step depends on (a toolchain
   version, an install step, environment variables). The floor runs the check in a prepared
   tree, so put only environment variables that change **result output** into
   `results.how.env`.
2. **Manifests** say what the CI command resolves to: `package.json` `scripts`, the
   `[tool.pytest.ini_options]` in `pyproject.toml`, `setup.cfg`/`tox.ini`, `Cargo.toml` workspace
   members, `go.mod`, gradle/maven test tasks.
3. **The runner itself.** Run `<runner> --version` and `<runner> --help`, plus the sub-help it
   points to. What the runner prints decides the guide; this skill carries no runner table.

`discover.py` does 1 and 2 mechanically: every command whose text says `test`, with
`file:line`, followed one level through `make`, `just` and `npm|pnpm|yarn run`. It also marks
npm's `no test specified` placeholder, which declares that the repo has no tests.

## Choosing the check(s)

- **Every CI step is a check, with its `cwd`.** In the directories a usable guide's checks cover,
  the guide replaces the floor's own detection, so a CI step the guide leaves out there stops
  gating. Use the step's `working-directory` as the check's `cwd` (`ciSteps` carries it), and give
  expensive gates `stage: ["verify"]`. Declare each `ciSteps` entry. Install, build, format, lint
  and typecheck are gates: `name`, `cwd`, `run`, and a `failedExit` where the tool documents
  one. Gates have no `list`, `results` or `version`, and are not probed.
  `check.py --repo` warns for any step left out.
- One test check per distinct test command CI runs, for example a Rust workspace and a JS package in
  the same repo. Give each a short `name` (`test`, `test-web`) and its own `cwd`.
- `run` is the exact argv, not a shell string. The floor excludes failures only for a check
  whose argv equals `run` exactly, so the guide is the allowlist. Use the CI command's own
  argv. Put a separator that the deselect tokens need (libtest's `--`) at the start of
  `deselect.append`: the interpreter adds it only when the argv has none.
- `stage`: `["creator","verify"]` unless the repo marks a suite as slow or verify-only.
- `failedExit`: the exit code(s) the runner documents for "tests failed", as distinct from
  usage, collection or crash codes (pytest: 1; cargo: 101; vitest: 1). When the runner uses
  the same code for "could not run", say so in the report. The parser then has to name a
  failure, or the run counts as could-not-run.
- `invalidatedBy`: globs for files that change how the suite runs (the manifest, the lockfile,
  runner config, the CI file, toolchain pins). A head change matching one disables exclusion
  for that check.

## Interrogating the runner (`--help` checklist)

For each question, find the runner's own flag. If there is none, write "none", and do not
invent one.

| Question | Where it lands | Example of what to look for |
|---|---|---|
| Can it write JUnit / JSON lines / TAP? | `results` | a `--reporter`, `--format`, `--junitxml` or `--outputFile` flag |
| Is that format stable on this version? | `results` | cargo's `--format junit` is nightly-only on stable toolchains |
| How does it list tests without running them? | `list.run`, `list.item` | `--list`, `--collect-only -q`, a `list` subcommand |
| How does it run exactly one test? | `alone.run` with `{id}` | an exact-match flag, or a positional node id |
| How does it skip exact tests, repeatably? | `deselect.append` with `{id}` | a skip flag that may be repeated per id, written as one token (`--skip={id}`) |
| Which exit code means "tests failed"? | `failedExit` | the exit status section of the help or man page |
| Can it run only tests touched by files? | `affected.run` with `{files}` (optional) | a related-files or changed-files mode |

The deselect tokens are also appended to `list.run`. The probe checks that the list, with one
id deselected, lists exactly the rest. So the list command must honour the same skip flag.

Check repeatability for real. A flag that takes one value (the last one wins) or rejects
repeats cannot deselect two ids, even when the one-id `mutation` probe passes. The `multi` probe
(two mutations, `probes.mutation2`) tests two ids.

## Learn from real output, in a scratch copy

Never run probes in the operator's tree. Copy the base to a scratch directory, inject the
mutation probe there, run the check, and keep what the runner printed (stdout, and the result
file if there is one). That output is what the parser or the JUnit reading is written against.
`rehearse.py` does exactly this, and removes the copy afterwards.
