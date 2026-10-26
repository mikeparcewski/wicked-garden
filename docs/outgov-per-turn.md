# Output Governance — the Hook-Side Advisory Lane

How the interactive (hook-side) half of output governance works after AW-16
(arch-R14): **one source of per-turn truth, default-on advisory, fail-open by
contract**.

## The two-tier doctrine (why hooks never block)

Enforcement in the wicked platform is two-tier (TARGET-ARCHITECTURE contract 3):

| Tier | Where | Behavior |
|------|-------|----------|
| **Advisory** | garden hooks (`stop.py` session audit, `guard_pipeline` Check 6) | fail-open — surfaces findings, never blocks |
| **Enforcing** | crew/core gates (`output-gate-hook`, acceptance gate) | fail-closed — deny dominates |

There is **no third tier**. `WG_OUTGOV=strict` only strengthens the advisory's
wording (it asks the model to stop and explain before worsening a CRITICAL
violation) — the hook itself still cannot block. Anything that must be
enforced belongs in the crew/core gates, not here.

## One source of per-turn truth (arch-R14)

Both hook-side consumers read the **estate graph** — never an independent
rulebook:

1. **Session audit** (`hooks/scripts/stop.py::_check_outgov_compliance`):
   on the FIRST Stop of a session the hook itself runs **`rules.recall`**
   (`{"rule_type": "policy"}`, severity-ordered, graph-backed, the wire twin
   of wicked-governance's `recall_rules`) through the read-only shim
   (`scripts/_estate_client.py --readonly call`). When the store holds policy
   rules it names the count and the top three once, with the command that
   lists them all. Zero rules, an unreachable estate or any error: silent.
   It used to be a per-turn line telling the model to call the tool "if the
   estate MCP is connected", which no seat ever is (by design), so it could
   never run (garden#1333).

2. **Session-close pattern check**
   (`scripts/platform/guard_pipeline.py::check_outgov_pattern`, Check 6):
   reads Pattern-type conformance rules from
   `WICKED_OUTGOV_RULES_DIR/rules/*.json`. That directory is **not** a second
   source — it is a materialized view **generated from the graph** (e.g. by
   the `wicked-core rules fanout` toolchain), and it carries content-hash
   provenance so a stale or hand-edited copy is detectable (below).

## `WG_OUTGOV` modes and the default

| Value | Session audit (stop.py) | Check 6 (guard_pipeline) |
|-------|-------------------------|---------------------------|
| *(unset)* → **`warn`** | runs once per session (default-on advisory) | runs |
| `warn` | runs once per session | runs |
| `strict` | runs once, stronger wording — still advisory | runs |
| `off` (or any other value) | silent | skips |

The audit is also silent when `WICKED_CONTEXT_BACKEND=off`.

**The default flipped from `off` to `warn` in AW-16**, after the seed corpus
(AW-13) gave the advisory real rules to recall. Every mode is fail-open: a
missing estate, a missing rules dir, or a broken bundle can only *reduce*
findings, never block a session (proven by tests — see below).

## Noise budget (P-5): the per-repo pilot decision

The flip is **default-on in code, per-repo in practice**:

- The `warn` default applies wherever the garden hooks run.
- **The per-repo opt-out is the pilot mechanism**: a repo that finds the
  advisory too noisy sets `WG_OUTGOV=off` in its own environment (e.g. the
  `env` block of that repo's `.claude/settings.json`). No new enforcement or
  filtering tier is added to absorb noise — opting out *is* the escape hatch.
- **Noise budget owner**: whoever keeps a repo opted in owns its noise budget
  (the repo maintainer by default). The advisory costs at most one
  systemMessage per Stop; Check 6 findings are capped by the guard-pipeline
  budget and profile. The audit costs at most one systemMessage per session,
  and none when the store has no policy rules.
- If recall noise is systemic (bad rules, not bad wiring), fix the corpus —
  retire or re-scope the offending rules in the graph — rather than muting the
  lane ecosystem-wide.

## Content-hash provenance for `WICKED_OUTGOV_RULES_DIR`

Layout (the same canonical ruleset layout `wicked-core rules ingest`/`rules
fanout` consume):

```
$WICKED_OUTGOV_RULES_DIR/
├── provenance.json      # written LAST by the generator
└── rules/
    ├── bundle-a.json    # conformance-rule bundles (wicked_governance schema)
    └── bundle-b.json
```

`provenance.json`:

```json
{
  "provenance_version": "1",
  "source": "estate-graph:<db-or-manifest-ref>",
  "generated_at": 1788052289,
  "content_hash": "sha256:<hex>"
}
```

**Hash recipe** (generator and consumer must agree — both live in
`guard_pipeline.py`): sha256 over, for each `rules/*.json` file **sorted by
filename**, `<filename utf-8> NUL <file bytes> NUL`. Filenames participate, so
a renamed bundle changes the hash; sorting makes creation order irrelevant.

Generator side — stamp after materializing the dir from the graph:

```bash
python3 scripts/platform/guard_pipeline.py hash \
  --rules-dir "$WICKED_OUTGOV_RULES_DIR" --stamp --source "estate-graph:<ref>"
```

Consumer side — `check_outgov_pattern` recomputes the hash on every run and
records in the check's `meta` (persisted into the briefing file and available
to bus subscribers):

| `meta.provenance` | Meaning | Extra behavior |
|---|---|---|
| `verified` | recomputed hash == recorded hash | none |
| `stale` | hashes differ — the dir was edited after generation or generated from an older graph | one **warn** finding (`outgov-provenance-stale`); rules still surfaced |
| `missing` | no (parseable) `provenance.json` | none — recorded only |
| `unverifiable` | provenance exists but no usable hash on either side | none — recorded only |

`meta.rules_content_hash` is always recorded, so the persisted report states
exactly which rule bytes the session consumed — a stale dir is detectable
after the fact even when `provenance.json` was never written.

## Fail-open guarantees (tested)

Hermetic tests — no live estate needed, fixture rules dirs only:

- `tests/platform/test_outgov_pattern.py` — default-on warn; per-repo opt-out;
  **missing rules dir ⇒ skip with a note, zero findings, no block**; stale
  provenance ⇒ warn-severity finding only, rules still surfaced; hash
  determinism + generator/consumer recipe equality.
- `tests/hooks/test_stop_outgov.py` — the audit runs `rules.recall` once per
  session; silent on zero rules, an unreachable estate or an error; names no
  MCP; default-on; `off` opts out; `strict` stays advisory.

## Pointers

- `hooks/scripts/stop.py` — `_check_outgov_compliance` (once-per-session audit)
- `scripts/platform/guard_pipeline.py` — Check 6 (`check_outgov_pattern`),
  `compute_rules_content_hash`, `write_rules_provenance`, the `hash` CLI
- `skills/engineering/refs/conformance.md` — the agent-half rubric that
  evaluates Check 6's surfaced rules semantically
- wicked-core `crates/wicked-governance` — the graph side: `rules ingest`,
  `rules fanout` (the manifest + store split), `rules.recall`'s Rust twin
- History: garden#983 (pattern check), garden#984 (per-turn guardrail, closed), garden#1333 (per-turn line → session audit),
  AW-16 / arch-R14 (this document's change)
