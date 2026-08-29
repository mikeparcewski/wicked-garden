# TH-6 DoD evidence — the S11 honest-deny leg flips to satisfied on real campaign evidence

**Date:** 2026-08-29 · **Lane:** th6-gate-wiring · **DoD (TASK-PLAN TH-6 / RECON-TEST-HARNESS test-R6):**
crew's `GET /runs/:id/acceptance` returns **satisfied** on real campaign evidence — the exact leg
campaign S11 proved missing (honest deny, "no QE ledger").

## Environment (isolated — never 7701 / real `~/.wicked-crew` / real bus)

- crew daemon: built from **wicked-crew main @ 0f6be40** (`#348` path-join fix + `#330` isolation
  fix + endpoint manifest), `serve --port 7906 --db <scratch>/th6-state/core.db
  --bus-db <scratch>/th6-state/bus-data/bus.db --qe-gate-events`, with
  `WICKED_CREW_PROJECT_GRAPH_ROOT` + `WICKED_BUS_DATA_DIR` pinned to scratch —
  ready line in `00-daemon-ready-line.txt` (`stub:false, auth:"off", qeGateEvents:true`).
  Bundled UI: wicked-studio **0.4.0** dist (`build:with-studio`).
- wicked-ledger: **local main @ `0c0f21b`** (`feat(manifest): evidence-manifest 2.1 —
  scenario_evidence block + claim_level enum (TH-5) (#7)`); MANIFEST_VERSION reported by the
  installed package: **2.1.0** (UNPUBLISHED — installed via
  `npm i --no-save file:<worktree of wicked-ledger origin/main>` into both the runner package and
  the fixture repo, per the program constraint; npm publish was NOT run).
- executor: garden `scripts/qe/runner` (merged TH-4 base + this lane's TH-6 wiring),
  playwright 1.62.x headless chromium, viewport 1440x700.
- fixture repo: scratch `th6-fixture-repo` (git repo; its `.wicked-qe/` is the ledger crew reads).
- host crew run: workflow `th6-campaign-dod` (2 Tool phases; phase `test` declares
  `verified_evidence: true` → the acceptance requirement), `repoRef: th6-fixture-repo`,
  run id `8295c087-f6a1-4d7f-afef-6f045368e22e`.

## Transcript (numbered files = captured wire responses, in order)

| # | File | What it proves |
|---|---|---|
| 00 | `00-daemon-ready-line.txt` | isolated daemon env (port 7906, scratch db/bus, stub off, qe gate events armed) |
| 01 | `01-acceptance-deny.jsonl` | **the S11 honest-deny leg**: `requirement.declared:true (phases:["test"])`, `gate.satisfied:false`, reason `no QE ledger at <fixture>/.wicked-qe — (missing ⇒ deny)`. Note the CLEAN absolute path — crew#348's fix visible (S11 showed a concatenated path) |
| 02 | `02-qe-run-1.json` | runner executes `specs/th6-acceptance-dod.spec.json` against the daemon: claim PASS 4/4, evidence + manifest written via wicked-ledger into the fixture repo, `scenario_evidence_emitted:true`, gate seam cmd printed |
| 03 | `03-qe-run-2.json` | second execution of the SAME spec — new run id, **same scenario row** |
| 04 | `04-flake-history.json` | TH-6 AC "flake history accrues per scenario_id": ONE `scenarios` row (`crew-acceptance-gate.th6-dod`), TWO `runs` rows under it |
| 05 | `05-manifest-run2.json` | manifest **2.1.0** with the full `scenario_evidence` block: 8-key campaign shape, `claim_level: machinery-verified`, legs (`studio-home-ui: certified`, `daemon-state-cross-check: machinery-verified`), honest-cap floor respected |
| 06 | `06-gate-pass.json` | `gate.mjs --verdict PASS` (exit 0): `manifest_validation {ran:true, ok:true}` (TH-5 validate-before-grade), `verdicts` row written, `wicked.qe.gate.passed` + `wicked.qe.deploy.completed` emitted to the ISOLATED bus |
| 07 | `07-acceptance-satisfied.jsonl` | **THE DoD**: same run id as 01 now returns `gate.satisfied:true`, `verdict:"PASS"`, reason cites the verdict row; `busEvent.eventType:"wicked.qe.gate.passed"` (4-segment grammar) observed by the daemon's opt-in subscription |
| 08 | `08-host-run-terminal.json` | host run brought to a terminal state (`cancelled` — see finding below) |
| 09 | `09-acceptance-after-terminal.jsonl` | acceptance still resolves satisfied for the terminal-state run — the ledger stays the system of record |
| 10 | `10-verdicts-rows.json` | the `verdicts` row as stored (reviewer `wicked-garden-qe-gate`, FK to the qe run) |
| — | `qe-evidence-bundle-8d49b3fe/` | the graded run's full redacted bundle: manifest.json (2.1), wire/console/steps/result.json, 1440x700 screenshot of studio home live against the isolated daemon. The spec's fake bearer credential appears NOWHERE (grep clean; `[REDACTED:field:Authorization]` marker present) |

## Honest caps / findings

- **Claim level of the DoD scenario: machinery-verified** (per its own legs — the acceptance
  endpoint is API-only by design, campaign S11; the deny→satisfied flip was captured over REST,
  not a studio surface). The studio-home leg itself ran as a real browser journey (certified leg).
- The GRADE was recorded by this lane operating the gate CLI after checking the bundle
  (manifest-contract validation ran twice: reviewer-side and gate-side). Routing grades through
  the full qe accept trio is TH-10 — out of this lane's scope by design.
- **Finding (for TH-9's scenario→Tool-phase mapping):** a Tool phase with
  `gate: { human_confirm_if: "verdict_not_pass" }` loops on approve (approve → re-execute tool →
  re-park; unit shows `rejected`) because a tool executor never produces the engine-visible
  verdict the condition wants. The host run was terminated by gate-reject (`cancelled`) after the
  DoD captures; acceptance is unaffected (09). Campaign workflows mapping deterministic scenarios
  to Tool phases should use `gate: "auto"` on the executor phase and hang the human gate on a
  review phase instead.
- wicked-ledger 2.1 is UNPUBLISHED; the run used the local main build (program constraint).
  crew read the 2.1-written store through its installed ledger 0.2.0 without error
  (cross-version read verified separately before the run) — the XC-4 floor bump remains the
  clean fix.
