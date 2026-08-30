# @wicked-garden/qe-runner — the qe campaign executor runtime

The **model-free executor** of the qe campaign plane (ADR 0006, TH-4). It is
the productized form of the executor layer the 2026-08 studio campaign proved
(87 rescued scripts in `estate-review/review-artifacts/campaign-exec/`), owned
by wicked-garden's qe domain — **never** a dependency on wicked-interactive
(archive track); Playwright is vendored directly by this package.

## The doctrine (from wicked-interactive's demo.js)

> **The agent AUTHORS a deterministic spec file. A model-free runner EXECUTES
> it and records evidence.** The runner never decides WHAT to click — it only
> runs the script.

Concretely:

- **Zero LLM calls inside the runner.** Nothing in `src/` or `bin/` talks to
  a model, and the spec vocabulary is closed — there is no `evaluate`/free-form
  JS escape hatch, so a spec cannot smuggle agency in either.
- **Authoring is the agent's job.** When a selector drifts, the run FAILS;
  the agent re-authors the spec against the live DOM and the substitution
  lands in the spec's diff (TH-13). The runner never "figures it out".
- **Regression re-runs are agent-free.** A committed spec re-executes
  deterministically in CI or from the CLI with no model in the loop —
  video/trace become flags, not features.

## Usage

```sh
cd scripts/qe/runner && npm install     # vendors playwright + wicked-ledger
node bin/qe-run.mjs <spec.json> [--repo-root <dir>] [--video] [--trace]
node bin/qe-run.mjs <spec.json> --lint-only
```

Exit codes: `0` claim PASS · `1` claim FAIL · `2` INCONCLUSIVE (run error or
secret-preflight hit) · `3` runner error · `4` spec rejected by lint.

The printed `claim` is an **executor claim, not a graded verdict** — grading
belongs to the qe accept trio (TH-10), and the acceptance gate re-derives
"done" from the ledger rows (TH-6).

## Non-configurable defaults

These are pinned in the runner and **lint-rejected** if a spec tries to
configure them:

| Default | Value | Why |
|---|---|---|
| Viewport | **1440x700** (headless) | evidence screenshots comparable across every campaign (the campaign standard; 1440x900 hides fold bugs) |
| Console ledger | always captured (all message types + pageerror) | selector drift and deprecations surface as warnings first |
| Waiting | **wait-on-condition only** — `waitFor`, `waitForText`, `expectWire`, `expectNewWire`, each with a `timeout_ms` CAP | fixed sleeps are flake generators; the lint rejects `sleep`/`delay`/`pause`/`*_ms` smuggling |
| Assertions | **no status-only assertions** — `status` requires a content check (`json_path` + `equals`/`matches`/`contains`, or `body_contains`); ≥1 content-bearing assertion per spec | a 200 proves reachability, not behavior |
| Redaction | always on, before any write (see below) | TH-19 is MVP-hard |

## Spec format v1 (deterministic JSON)

```jsonc
{
  "spec_version": "1.0",
  "scenario": { "id": "studio-s1-smoke", "name": "…", "project": "wicked-crew-studio" },
  "target": {
    "kind": "browser",
    "base_url": "${env:QE_SMOKE_BASE_URL:-http://127.0.0.1:7899}",
    "redact": { "fields": ["x-tenant-badge"], "patterns": ["acme-cred-[a-z0-9]{8}"] }
  },
  "capture": {
    "websocket": true,
    "wire": [ { "id": "health", "match": { "url_suffix": "/api/v1/health" }, "body": true } ]
  },
  "steps": [ /* goto · waitFor · waitForText · click · fill · press ·
                screenshot · readBack · expectWire · expectNewWire */ ],
  "assertions": [ /* wire · ws · readBack · pageText · console ·
                     dbAssert · cliCrossCheck */ ]
}
```

`${env:NAME}` / `${env:NAME:-fallback}` interpolation keeps committed specs
portable across isolated daemons; an unset variable without a fallback is a
fail-closed lint error (exception: `QE_FIXTURE_NS`, which the runner
defaults — see below). See `specs/s1-smoke.spec.json` — the rescued campaign
S1 rewritten onto this package — for a complete example.

### Fixture namespacing — the parallel-isolation default (TH-22)

Campaign scenarios historically mutate ONE shared daemon's state (projects,
repos, runs accumulate — the reason the proven studio ladder was
dependency-ordered). The moment a campaign scheduler runs nodes in
parallel, unnamespaced fixtures race. The runner's default:

- **`QE_FIXTURE_NS`** is always available to spec interpolation. A
  caller-set value wins (the campaign mapper sets one per node); otherwise
  the runner generates a per-run unique value (`qe-<seed>-<time>-<entropy>`)
  and prints it in the CLI result as `fixture_ns`.
- **The convention:** every fixture a spec creates embeds it in the name —
  `"name": "proj-${env:QE_FIXTURE_NS}"`. That is what lets a scenario
  declare `isolation: stateless` (scenario-format v1.1) and run in parallel
  with other stateless nodes against the same instance.
- The isolation classes (`shares-state` — the default when absent —
  `exclusive`, `stateless`) live on the scenario frontmatter AND the
  campaign-plan rung (`campaign-recon.schema.json` format v2); the PLAN
  rung is what the crew-side scenario→CampaignNode mapping consumes.
  `exclusive` nodes need DAG serialization edges or a per-node isolated
  profile (fresh `WICKED_HOME` / `--db` / `--bus-db`). **Until that mapping
  consumes the annotation, campaigns MUST run `max_concurrency: 1`** —
  correct, just slow; the constraint is explicit, never accidental.
- The namespace value feeds fixture NAMES only — it never changes what the
  runner does; the runner stays model-free and deterministic.

### The four generalized helpers (importable from `src/index.mjs`)

- **`wireCapture(page, spec)`** — fetch/XHR/WebSocket/console capture via
  `page.on('response'/'websocket'/'console')`, the campaign's proven idiom.
- **`readBack(baseUrl, step)`** — assert-by-read-back: re-fetch the state the
  UI claims to have changed and assert on its content.
- **`dbAssert(assertion)`** — read-only SQL SELECT against a SQLite file via
  `node:sqlite` (no native build; macOS/Linux/Windows). Row counts and value
  comparisons.
- **`cliCrossCheck(assertion, captures)`** — run a CLI (argv array, no shell)
  and diff its output against an expectation or a captured readBack/wire
  value: the same fact through a second, independent channel.

## Evidence output (wicked-ledger shape)

Evidence lands under `<repo-root>/.wicked-qe/` through the **wicked-ledger**
package (`WICKED_QE_LEDGER_DIR` pins the dirname, mirroring crew's TH-2
semantics):

```
.wicked-qe/
  projects/ scenarios/ runs/      # DomainStore rows (dual-write JSON+SQLite)
  evidence/<run-id>/
    manifest.json                 # ledger manifest (2.0.0; 2.1 with scenario_evidence
                                  #   + claim_level once the ledger floor is >= 2.1 — XC-4)
    wire.json console.json steps.json result.json
    <name>.png                    # 1440x700 screenshots
    [video, trace.zip]            # only with --video / --trace
```

The runner writes **evidence, never verdicts of record**: no `verdicts` row
is created, and the manifest's verdict block carries the executor claim under
`reviewer: "qe-runner/executor-claim"`.

## TH-6: verdicts, gate events, and the crew acceptance gate

The wiring that makes the evidence COUNT (proven end-to-end in the lane's
`evidence/th6-dod/` transcript — the S11 honest-deny leg flipping to
satisfied on real campaign evidence):

1. **Stable scenario_ids.** The `scenarios` row is looked up by
   (project, `scenario.id`) and reused across re-runs — every re-run appends
   a `runs` row under the SAME scenario_id, so flake history and impact
   selection accrue per scenario (qe-flaky-test-hunter's 14d windows come
   free). Name scenario ids `<capability-id>.<slug>` (e.g.
   `crew-acceptance-gate.th6-dod`) and never rename them casually.
2. **Grading** is the qe accept trio's job (TH-10) — the runner's claim is
   input, never the verdict.
3. **Recording + announcing**: the graded verdict goes through
   `scripts/qe/lib/gate.mjs` (same cwd / `WICKED_QE_LEDGER_DIR` as the run —
   the gate resolves the SAME ledger root as this writer, TH-2 semantics):
   it validates the bundle's manifest against the ledger contract first
   (nonconforming ⇒ recorded as INCONCLUSIVE, deny-dominates, TH-5), writes
   the `verdicts` row keyed by this runner's run_id, and emits the
   `wicked.qe.gate.passed|failed|conditional` bus events (stable 8-field
   wire contract). The CLI result's `gate.cmd` field prints the exact
   command.
4. **Acceptance**: crew's `GET /runs/:id/acceptance` re-derives the gate from
   the newest `verdicts` row in the repo's ledger — deny-dominates; a clean
   PASS row flips it to `satisfied: true`, citing the verdict.

When the installed wicked-ledger supports manifest 2.1 (TH-5), the bundle
also carries the campaign `scenario_evidence` block: the proven 8-key shape
plus first-class `claim_level` (`certified | machinery-verified | skipped`).
The spec plans the ceiling — optional `scenario.claim_level` (default
`machinery-verified`, the conservative floor) and `scenario.legs` for
disclosed per-leg caps; the lint enforces the honest-cap invariant (the
scenario claim is never stronger than its weakest leg) and rejects `skipped`
as a planned level (outcome-only). On a pre-2.1 ledger floor the block is
withheld and the CLI result says so (`scenario_evidence_emitted: false`) —
never silently mangled.

The ledger emits fire-and-forget `wicked.test.*` bus events on row writes;
set `WICKED_BUS_DATA_DIR` (and point any daemon at `--bus-db`) when running
against an isolated profile so nothing touches the real bus.

## Redaction (TH-19 — MVP-hard)

Runs inside the executor **before any manifest/artifact write** (and therefore
before any future vault `record` — vault immutability makes leaks permanent,
TH-17):

1. **Field-name scrub** — any captured header/field matching
   `authorization`, `cookie` (incl. Set-Cookie), `token`, `secret`, `passw*`,
   `credential`, `session`, `*key*` is replaced with `[REDACTED:field:<name>]`.
   Extensible per target via `target.redact.fields`.
2. **Value-shape scrub** — Bearer/Basic values, JWTs, AWS access keys,
   GitHub/OpenAI/Slack token prefixes, `password=…` kv pairs, PEM private-key
   blocks, plus per-target `target.redact.patterns` regexes.
3. **Secret-scan preflight** — the final serialized artifact text is scanned
   again; ANY hit flips the claim to **INCONCLUSIVE** (deny-dominates) and the
   offending artifact is **quarantined** (content withheld; only pattern ids +
   offsets are persisted — never the matched text).

Assertions evaluate against RAW captured values (they need real content);
only persisted artifacts are scrubbed.

**Known limitation (phase 2):** screenshots are pixel data — a secret rendered
on-screen is not caught by the scrub. Prefer unauthenticated/demo targets or
mask on the target side until per-target screenshot masking exists.

## Tests

```sh
node --test 'test/*.test.mjs'
```

Covers: the redaction layers + preflight quarantine (a captured bearer token
never reaches a written artifact), the status-only/no-sleep lint, dbAssert /
cliCrossCheck / jsonPath, and the CLI lint exit path. The headless smoke is
`specs/s1-smoke.spec.json` run against an **isolated** crew daemon:

```sh
S=$(mktemp -d)
WICKED_CREW_PROJECT_GRAPH_ROOT=$S/graph-root WICKED_BUS_DATA_DIR=$S/bus-data \
  npx -y wicked-crew serve --port 7899 --db $S/crew.db --bus-db $S/bus.db &
QE_SMOKE_CREW_DB=$S/crew.db WICKED_BUS_DATA_DIR=$S/bus-data \
  node bin/qe-run.mjs specs/s1-smoke.spec.json --repo-root $S/smoke-repo
kill %1
```

Never point a campaign at the real daemon (7701) or real `~/.wicked-crew`
state.

## Platform support (honest declaration, per test-R8)

- macOS / Linux: exercised (the smoke above ran on macOS).
- Windows: the runner is pure Node + vendored Playwright + `node:sqlite`
  (no bash, no native builds), so it is *expected* to work, but it is
  **unverified** until a Windows leg runs in CI. Requires Node >= 22.5.
