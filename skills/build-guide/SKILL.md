---
name: wicked-garden-build-guide
description: |
  Discover how a repo builds and tests, and write its build/test guide
  (`.wicked/build-guide.json`, contract v1): the data the wicked-core floor
  interprets instead of hardcoding runners. Reads CI config first, then the
  manifests, then each runner's own --version and --help. Prefers structured
  results (JUnit, JSON lines, TAP) and writes a text parser, learned from this
  repo's real output, only when none exists. Writes a deliberately failing
  mutation probe, validates with `wicked-core floor probe` (only the probe
  writes `verified`), and proposes the file as a PR or governed change, never
  silently.

  Use when: "build guide", "write the build/test guide", "how does this repo
  test", "onboard this repo's tests for the floor", "re-onboard the build
  guide", "the build guide is stale", the onboarding step of the
  wicked-garden-core setup action, or a wicked-crew onboarding run dispatched
  because the floor found no guide, a stale one, or a failed probe.
metadata:
  role: router
  phases: "*"
  archetypes: "build"
---

# Build/test guide

The floor decides by exit codes and excludes only the base's own failures. To do that for any
runner without runner names in engine code, it reads a per-repo guide that says how this repo
runs its tests, how to read their results, and how to list, run one or deselect a test. The floor
reads `.wicked/build-guide.json` **from the base tree**, so a head edit never applies to its own
run. Every piece is checked against reality by `wicked-core floor probe`. A piece whose probe did
not pass is not used, and that check runs exit-code only.

This skill discovers, drafts, validates and proposes the guide. It never decides "verified".

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Actions

| Action | When | How |
|--------|------|-----|
| `discover` (default) | the repo has no guide | steps 1 to 6 below |
| `refresh` | the guide is stale (a `derivedFrom` file or the runner version changed), a probe failed, or crew dispatched re-onboarding | start from the committed guide; if a `derivedFrom` file changed, redo step 1; otherwise revise only the failing piece; then steps 4 to 6 |
| `check` | validate a guide file someone wrote | `wicked-garden run scripts/build_guide/check.py --guide <file> --repo <dir> [--schema <file>]`. It flags what the floor needs before it will use a check: a non-empty `failedExit`, `alone`, `deselect`, a `list`, and a `text` or `junit` results kind. On a probed guide it also flags any required probe that did not pass, and a blank `runnerVersion`. |

The contract is fixed (DES-BUILD-GUIDE, "Contract v1"). Its schema is wicked-core's
`schemas/build-guide.v1.json`, which the scripts carry as a vendored copy. Produce exactly that
shape, and add no fields. `refs/contract-notes.md` lists what core's schema adds to the DES text,
how this skill reads it, and the open questions. To check against a newer core schema, pass it
as `--schema`.

**Pinned semantics** (core's interpreter):
- Regexes apply per line. A block's items are the contiguous item lines after its start (blank
  lines are allowed), and any other line ends the block.
- No argv goes through a shell. `{id}`/`{q}` fill whole argv elements, so no quoting is needed;
  `{q}` is allowed in `alone` and `deselect`. `{files}` expands to one argv element per file.
- Deselect tokens before the first `{id}`/`{q}` token are added once (a leading `--` only when
  the argv has none). The tokens through the last one repeat per id, and the rest are added once.
  So a flag and its value are one token (`--skip={id}`).
- Paths (`results.how.path`, the mutation files) are relative to `cwd`. `invalidatedBy` globs
  are matched against the files the change touched.
- A JUnit `<skipped/>` testcase neither passed nor failed. The results kind is `text` or
  `junit`; `json-lines` and `tap` are reserved.

## 1. Discover what the repo already declares

```
wicked-garden run scripts/build_guide/discover.py --repo <dir>
```

It reads CI config first (`.github/workflows/*`, `.gitlab-ci.yml`, `Makefile`, `justfile`), then
the manifests (Cargo.toml, package.json scripts, pyproject/setup.cfg/tox.ini, go.mod,
gradle/maven). It follows `make test`, `just test` and `npm test` one level into what they run,
and lists every test candidate with its `file:line`. It runs nothing. **Manual alternative:**
read those files yourself, in that order.

Then interrogate each candidate's runner: run its `--version` and `--help`, and any sub-help it
points to (for example `cargo test -- --help`). From the runner's own words, learn its result
formats, how it lists tests, how it runs one test, how it deselects exact tests, and which exit
code means "tests failed". `refs/discover.md` has the checklist. Record every file you derived
the guide from in `derivedFrom`.

`verdict: no-test-command` → go to step 6.

## 2. Results: structured first

Use JUnit if the runner already emits it through a flag, a reporter or a plugin it has (JSON
lines and TAP are reserved in v1). Set `results.id`/`idJoin` so the ids are the ones the list
prints, and set `results.how.merge`/`list.merge` when the runner names scopes on stderr. Put the flag in `results.how.argvAppend` and the file in `results.how.path`. Only
when none exists, write a `text` parser: line regexes, an optional section qualifier and summary
blocks. Learn them from **real output of this repo's runner**, captured by running it on a
scratch copy with the mutation probe in it. Base the parser on the runner's own final summary
where one exists, not on per-test lines interleaved with test output. `refs/results.md` has the
rules (RE2 only, every regex `^…$`), the id round-trip test, and worked examples. The starting
points in `assets/seeds/` (cargo, pytest, vitest) are drafts too: probe them like anything else.

## 3. Write the two mutation probes

`probes.mutation` and `probes.mutation2` are two minimal, deliberately failing tests in the
repo's own language and test framework. Each goes in its own **new** file that the runner's
normal discovery picks up, with a different id, and each carries the id the parser must name
(`expectId`, plus `expectQ` when ids are qualified). One proves that the parser, the ids and
deselect agree. Both together prove that two failures are both parsed and both deselected.
Never edit an existing test file.

## 4. Validate: rehearse, then probe (at most 3 attempts per check)

```
wicked-garden run scripts/build_guide/check.py --guide <draft> --repo <dir> --draft
wicked-garden run scripts/build_guide/rehearse.py --repo <dir> --guide <draft>
wicked-garden run scripts/build_guide/probe.py --repo <dir> --guide <draft>
```

- `check --draft` validates the shape and refuses a draft that carries `verified`.
- `rehearse` mirrors the core probes (`list`, `run`, `mutation`, `ids`, `alone`, `deselect`,
  `multi`, and `affected` when present) in a scratch copy, so you can iterate quickly. It is not
  evidence and writes nothing.
- `probe` runs `wicked-core floor probe --repo <dir> --guide <file>`. Only that command writes
  `verified`. **Never hand-write `verified`**, and never edit what the probe wrote. The one
  exception: the probe leaves `runnerVersion` blank. Add `--version-argv '["<runner>","--version"]'`
  (a JSON argv) and `probe.py` fills that blank field from the runner's own output before you
  propose.

A failed probe names a piece. Revise that piece's argv, parser or template and probe again. Stop
after **3 probe attempts** for a check, and report each attempt's results. Do not keep tuning.

**Probe unavailable** (`probe.py` exits 3, because wicked-core is missing or has no
`floor probe`): say exactly *"probe unavailable: the guide is unverified, so the floor will not
use it for exclusion"*. You may still propose the draft, labelled unverified, with the rehearsal
results. It is not verified, and the floor will run that check exit-code only until a probe
passes it.

## 5. Propose, never write silently

The guide lands through the approve queue, never as a silent write. `refs/propose.md` has the
steps and the PR body template.

- **Inside a wicked-crew run**, write `.wicked/build-guide.json` in the run's worktree. The run's
  deliver gate is the proposal. Do not open a second PR.
- **Otherwise**, create a branch (`wicked/build-guide`) and commit only the guide. Open a PR
  (draft when any probe failed or was unavailable). Its description holds the probe results:
  the `markdown` table that `probe.py` prints, or the rehearsal results labelled "rehearsal,
  unverified". Also give the runner version and the `derivedFrom` list.
- **Never** push to the default branch, and never commit the scratch copy or result files.
- Before you open the PR, show the user the guide and the probe table, and ask whether to open
  it. Use your harness's question prompt where it has one; otherwise ask in plain text and wait.
  In a headless run, do not ask: the deliver gate asks.

## 6. No guide possible

If the repo has no tests, or no candidate survives step 4 within the attempts, say so plainly:
*"no build/test guide: the floor will run this repo's checks exit-code only"*, and give the reason
(no test command; a runner that names no failures; ids that do not round-trip). Propose no file.

## Report

Give the check names with their `run` argv, the result kind (and why text, if text), the
per-probe results with attempt count, any known limit (for example, `multi` failed because the
runner rejects a repeated deselect flag), the `runnerVersion`, and the PR link or "no guide". Report a failure exactly as it happened.
