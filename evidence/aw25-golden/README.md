# AW-25 golden path — the wiki pipeline's own evidence-gated proof

**Date:** 2026-08-30 · **Lane:** aw25-golden · **Source:** TASK-PLAN AW-25 / RECON-ARCH-WIKI arch-R21.
**Claim:** the seed→ingest→recall→deny→acceptance chain works END TO END, proven by captured
evidence and re-derived by an evaluator that did not run the pipeline — never asserted.
**Re-run:** `scenarios/qe/aw25-golden-path.md` (scenario-format v1.1) → `run.sh` here.
**Plan artifact:** `campaign-recon.aw25.json` (campaign-recon schema spec 2, validated by
`scripts/qe/campaign_plan.py validate`).

## The chain

| Hop | Mechanism | Proof |
|---|---|---|
| 1. seed doc | `ruleset/aw25-golden.md` — frontmattered rule doc; `POL-2500` (critical) bans the canary token `AW25-GOLDEN-DENY-ME`; paired deny Policy `ruleset/policies/POL-2500.json` (same id — the doc↔gate pairing from `wicked-core/governance/packs/README.md`) | committed here |
| 2. ingest + fan-out | `wicked-core rules ingest` into an isolated store; `wicked-core rules fanout` across the AW-5 store split: enforcement (crew-api transport), discovery graph, knowledge chunks | `chain/01-ingest.txt`, `chain/02-fanout-manifest.json` (+ emitted `…crew-payload.json`), `chain/03-enforcement-post.json` (POST receipts + `rules/preview` read-back) |
| 3. recall with citation | `rules.recall` over the **installed** `wicked-estate-mcp` 0.15.1 (stdio JSON-RPC) against the fan-out's discovery db | `chain/04-rules-recall.json` — POL-2500 with `provenance.ref: aw25-golden.md@<git blob sha>#POL-2500` and the wiki URI in the statement |
| 4. governed run trips the trigger | isolated crew daemon (`:7907`, scratch `--db`/`--bus-db`), workflow `chat`, claude seat pinned; the run **intent** carries the token, so the unit's evaluated governance context matches the `contains` trigger deterministically — no reliance on the worker model echoing anything | `chain/05-run-terminal.json` — run `d8a3da04…` terminal `failed`, unit 1 `rejected` |
| 5. denial cites rule id + wiki URI | engine gate (`decide`, deny-dominates) + `attach_recalled_rules` obligations | `chain/05-run-terminal.json` `denial_reason` ("… decision=deny, policies: [POL-2500], criteria: … wiki URI: wiki://aw25-golden#POL-2500 …"); `chain/06-governance-claims.json` — the run-scoped deny claim: `policy_ids: ["POL-2500"]`, criteria + `conform:` obligations both citing the URI |
| 6. ConformanceClaim in acceptance | `GET /runs/:id/acceptance` conformance section (AW-14) | `chain/07-acceptance.json` — `denied: true`, deny claim with parsed rule citations (POL-2500 statement carrying the wiki URI), `guardrailed: false`, `enforcement.status: "enforced"`, summary "1 governance denial(s) stand against this run (rules cited: POL-2500, PAT-2501) — deny-dominates" |

## Environment of the recorded run (isolated — never 7701 / real `~/.wicked-crew`)

- crew daemon: built from **wicked-crew main @ 8f816f3** (includes #359, the acceptance
  conformance section — npm 0.7.1 predates it), `serve --port 7907 --db <scratch>/state/core.db
  --bus-db <scratch>/state/bus-data/bus.db`, `WICKED_CREW_PROJECT_GRAPH_ROOT` +
  `WICKED_ESTATE_REPO_GRAPH_ROOT` + `WICKED_BUS_DATA_DIR` pinned to scratch
  (`chain/00-daemon-ready.txt`).
- rules CLI: **wicked-core main @ a4d3f85** (`rules ingest/fanout/recall`, merged #310/#313/#319 —
  the installed binary predates the `rules` subcommands; `run.sh` preflights this and names the fix).
- recall surface: **installed `wicked-estate-mcp` 0.15.1** (`~/.cargo/bin`) — the XC-3 release
  carrying `rules.recall`.
- worker seat: claude (pinned via `AW25_SEAT`; the denial is evaluator-side, the pin only
  removes roster variance).
- wiki lifecycle events (AW-22) from the rules CLIs: `WICKED_ESTATE_DB` pinned to a scratch
  events store — nothing spools to the operator's home outbox.

## Evaluator≠creator

The verdict of record is hop 6: crew's acceptance view re-derives the conformance section from
the daemon's durable store (claims + event log) — the same read any operator/CI would do. The
lane that authored the ruleset asserted nothing; the committed proof is the acceptance payload,
plus the independent claim wire (`chain/06`), each captured verbatim from the API.

## Honest caps / findings

- **Claim level: machinery-verified** (the plan's rung ceiling). The chain is CLI + MCP + REST
  machinery by design — the acceptance endpoint is API-only (campaign S11 precedent); no user
  journey is claimed.
- **Substance-gate interplay (finding):** a governed unit whose reply is under 200 trimmed chars
  is substance-rejected BEFORE the governance gate runs (`actor.rs` PHASE SUBSTANCE GATE), so a
  too-terse canary run records NO claim — the scenario intent explicitly asks the worker for a
  ≥250-char paragraph, and `run.sh` documents why. First trip of this scenario found exactly that
  (claude replied 104 chars and the run failed with `substanceRejected`, zero claims).
- **`enforcement.armedUnits` is empty** on the recorded run even though `status: "enforced"`:
  the ACP carrier records governance activity (`unitOutputCaptured.governed: true`,
  hook-fired signals) without the wrapped-CLI path's `governanceContextArmed` event. The
  positive verification holds; the per-unit armed list is a wrapped-CLI-path detail.
- The denial's **criteria** cites the wiki URI because the paired Policy authored it so
  (doctrine-twin convention); the **obligations** cite it because `attach_recalled_rules`
  surfaces the recalled rule statements — the statement itself carries
  `wiki://aw25-golden#POL-2500`, and the recall response carries the digest-bearing
  `aw25-golden.md@<blob sha>#POL-2500` ref. Two independent citation paths, one doc.
- `chain/02-fanout-manifest.json` records the enforcement lane as `verified: false`
  ("PENDING (crew API)") by design — a daemon-held store is never CLI-written; the POST receipts
  and the `rules/preview` read-back in `chain/03-enforcement-post.json` are the delivery proof.

## Re-running

```sh
WICKED_CORE_BIN=<wicked-core main build> \
CREW_CLI="node <wicked-crew main>/packages/crew/dist/cli/index.js" \
ESTATE_MCP_BIN=wicked-estate-mcp \
AW25_EVIDENCE_DIR=$TMPDIR/aw25-evidence \
bash evidence/aw25-golden/run.sh
```

Exit 0 = full chain PASS (the script asserts every hop, fail-loud, and kills the isolated daemon
on exit). Re-run this scenario after ANY change to `rules ingest`, fan-out, `rules.recall`, the
gate hook, or the acceptance conformance section (rule `PAT-2501` in the seed doc says exactly
this, recallably).
