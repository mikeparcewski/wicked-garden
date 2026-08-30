---
phase_relevance: ["test", "review"]
archetype_relevance: ["ship", "review"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-23 / test-R19b,
     ADR 0006 "qe campaign"). Loaded on demand via Read() from the router's
     `campaign` action — not a skill. -->

# qe campaign CI — the GH Actions recipe (PR subset + governed nightly)

Phase-3 assembly: a campaign's persisted strategy (`campaign-recon.json` +
committed deterministic specs/scenarios) re-executes on a schedule, and the
diff against the prior run — not a green checkmark — is the regression
signal. Two lanes, deliberately different:

| Lane | Trigger | What runs | Cost | Verdicts |
|---|---|---|---|---|
| **PR** | `pull_request` | The **deterministic subset only**: committed runner specs (`scripts/qe/runner`) and Tool-phase scenarios. Zero LLM calls, zero seats. | CI minutes only | **Executor claims** (exit codes trip the job). No grades, no rerun diff — grading needs the isolated reviewer, and a token-free lane must not pretend otherwise. |
| **Nightly** | `schedule` (cron) | The **full governed campaign** through crew's `/api/v1/campaigns` — budget-capped (TH-20), flake-policied (TH-21), graded by the accept trio, gated via `gate.mjs`, then **`qe campaign rerun` diffs verdicts vs the prior nightly**. | Real seats, real tokens — which is exactly why every ceiling below is mandatory | Graded verdicts of record; `campaign-rerun.mjs` exits 1 on any regression |

Copy-paste starting points (edit for the target repo, they are recipes not
turnkey): [`docs/examples/qe-campaign-pr.yml`](../../../docs/examples/qe-campaign-pr.yml)
and [`docs/examples/qe-campaign-nightly.yml`](../../../docs/examples/qe-campaign-nightly.yml).

## Lane 1 — PR: deterministic subset

What belongs here: runner specs (`*.spec.json` — model-free by construction)
and campaign scenarios whose steps are plain deterministic commands (the
`tool` shape of TH-9's mapping). What does NOT: anything needing a seat, a
governed run, or a grade.

```yaml
# .github/workflows/qe-campaign-pr.yml (see docs/examples/ for the full file)
- run: cd scripts/qe/runner && npm ci && npx playwright install --with-deps chromium
- run: |
    for spec in .wicked-qe/campaigns/<name>/specs/*.spec.json; do
      node scripts/qe/runner/bin/qe-run.mjs "$spec" --lint-only
      node scripts/qe/runner/bin/qe-run.mjs "$spec"       # exit ≠ 0 fails the PR
    done
- uses: actions/upload-artifact@v4        # evidence bundle, always
  if: always()
  with: { name: qe-evidence, path: .wicked-qe/evidence/ }
```

Honesty rules for this lane:

- The job's verdict is the **executor claim** (exit code). Never write
  reviewer `verdicts` rows from a PR job — that is self-grading with extra
  steps (TH-10).
- Claims cap at `machinery-verified`. A PR lane certifies machinery, not
  user journeys.
- The subset must stay **isolated**: the job boots its own target instance
  (fresh state dirs, ephemeral port) per the environment-manifest preflight
  (TH-8) — never a shared/staging daemon, or PRs race each other.

## Lane 2 — nightly: governed, budget-capped, flake-policied

The nightly lane is a REAL campaign: crew schedules the ladder as a durable
DAG (`POST /api/v1/campaigns` — deterministic rungs as `tool` nodes running
their committed spec/scenario **by file path** — the 1022-byte rule — and
exploratory rungs as `agent` nodes), the accept trio grades evidence, the
gate records verdicts, and the rerun diff is the output that matters.

### Budget caps (TH-20 — mandatory, not optional)

Crew's campaign supervisor enforces these; the nightly job pins them
explicitly so a config drift can never mean "unbounded" (all knobs
documented in wicked-crew `docs/campaign-budgets.md`):

```yaml
env:
  WICKED_CAMPAIGN_BUDGET_SECS: "14400"        # campaign wall-clock ceiling (4 h)
  WICKED_CAMPAIGN_NODE_TIMEOUT_SECS: "1800"   # per-node ceiling (30 min)
  WICKED_UNIT_TIMEOUT_SECS: "900"             # engine per-unit pin (campaign-proven)
  WICKED_CAMPAIGN_MAX_NODES: "25"             # fail-closed nightly node cap
  WICKED_CAMPAIGN_MAX_COST_USD: "20"          # opt-in cost ceiling
  WICKED_CAMPAIGN_KILL_POLICY: "kill-running"
```

Also cap the *job itself* (`timeout-minutes` a notch above
`WICKED_CAMPAIGN_BUDGET_SECS`) — the runner must die even if the supervisor
cannot.

### Flake policy (TH-21 — always on at the gate)

- Assemble the scoreboard after grading:
  `node scripts/qe/lib/campaign-scoreboard.mjs --json --out scoreboard.json`
  — mixed graded outcomes are a `flake_signal` blocker; quarantine records
  (hunter-owned, owner + deadline) exclude WITH REASON, never silently.
- Record the gate verdict with the exclusions attached:
  `node scripts/qe/lib/gate.mjs … --exclusions-from scoreboard.json`.
- Diagnostic re-runs are bounded and BOTH verdicts land in the ledger —
  never retry-to-green ([refs/campaign-flake-policy.md](campaign-flake-policy.md)).

### Rerun diff (the actual regression signal)

```bash
node scripts/qe/lib/campaign-rerun.mjs \
  --strategy .wicked-qe/campaigns/<name> \
  --since "$LAST_NIGHTLY_ISO" --require-rerun --json --out rerun-diff.json
# exit 0 clean · 1 regression/ungraded/not-rerun blockers · 3 usage/system error
```

Per-scenario deltas: `regression` (PASS → deny — fails the job) · `fixed` ·
`still-failing` · `unchanged-pass` · `new` · `not-rerun` (listed loudly;
fails under `--require-rerun` — silently shrinking coverage is the classic
laundering move) · `ungraded-current` (blocks: grade it, never diff an
executor claim).

### Ledger continuity between nightlies

The diff consumes ledger **history** (runs + verdicts under stable scenario
ids, TH-6), and CI runners are ephemeral — persist the ledger root across
runs or every night is `new`. Two honest options:

1. `actions/cache` with a rolling key on `.wicked-qe/` (simple; eviction
   possible — an evicted cache degrades to a `new` baseline, visibly).
2. Download the previous nightly's uploaded `.wicked-qe` artifact as the
   seed (deterministic provenance; slightly more YAML).

Never commit `.wicked-qe/` to the repo from CI.

### Degradation rungs in the nightly

Degradation scenarios ([refs/campaign-degradation.md](campaign-degradation.md))
run in this lane — they carry `isolation: exclusive`, and the nightly's
isolated per-job daemon is precisely the environment where breaking a
dependency is safe. Keep them OUT of the PR lane until authored fully
deterministic (generated stubs `exit 1` by doctrine).

## Both lanes: non-negotiables

- **Isolated instance per job** — the job boots its own daemon on an
  ephemeral/79xx port with scratch state dirs and runs the environment-
  manifest preflight fail-closed (TH-8). CI must never point at a real or
  shared instance.
- **Redaction stays on** (TH-19) — evidence uploaded as CI artifacts is one
  `curl` away from public; the runner's allowlist scrub + secret preflight
  run before any manifest write, INCONCLUSIVE on a hit.
- **Evidence always uploads** (`if: always()`) — a failed run without its
  bundle is a claim, not a finding.

## References

- `${CLAUDE_PLUGIN_ROOT}/docs/examples/qe-campaign-pr.yml` ·
  `${CLAUDE_PLUGIN_ROOT}/docs/examples/qe-campaign-nightly.yml`
- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-rerun.mjs` — the diff tool
- [refs/campaign.md](campaign.md) · [refs/campaign-grading.md](campaign-grading.md) ·
  [refs/campaign-flake-policy.md](campaign-flake-policy.md) ·
  [refs/campaign-degradation.md](campaign-degradation.md)
- wicked-crew `docs/campaign-budgets.md` (TH-20 knobs) · wicked-crew
  `e2e/campaign/` (the first dogfood corpus)
