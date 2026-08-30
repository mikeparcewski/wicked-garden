---
name: aw25-golden-path
description: |
  The wiki pipeline's own evidence-gated proof (AW-25 / arch-R21): seed doc →
  wicked-core rules ingest + fanout into ISOLATED stores → rules.recall over the
  INSTALLED estate MCP returns the rule with its provenance citation → an ISOLATED
  crew daemon runs a governed run whose intent trips the deterministic canary
  trigger → the gate denial cites the rule id + wiki URI → the ConformanceClaim
  surfaces in GET /runs/:id/acceptance (deny-dominates, never guardrailed).
version: "1.1"
category: cli
tags: [governance, wiki, acceptance, golden-path]
isolation: exclusive
tools:
  required: [bash, curl, python3]
  optional: []
timeout: 900
assertions:
  - id: A1
    description: rules ingest + fanout succeed against isolated stores; the fanout manifest records all three lanes (enforcement crew-api PENDING→delivered, discovery VERIFIED, knowledge VERIFIED)
  - id: A2
    description: rules.recall over the installed wicked-estate-mcp (>= 0.15.1) returns POL-2500 with its digest-bearing provenance citation (aw25-golden.md@<blob sha>#POL-2500) and the wiki URI in the statement
  - id: A3
    description: the governed run reaches a TERMINAL state and a run-scoped deny ConformanceClaim names policy POL-2500, its text citing wiki://aw25-golden#POL-2500
  - id: A4
    description: GET /runs/:id/acceptance carries the conformance section with the deny claim visible, denied=true, guardrailed=false, and the summary citing POL-2500
---

# AW-25 golden path — the wiki pipeline proves itself

The ecosystem's doctrine is "done is re-derived from evidence, never asserted".
This scenario applies that doctrine to the wiki/governance pipeline itself
(TASK-PLAN AW-25, RECON-ARCH-WIKI arch-R21): every hop of the seed→ingest→recall→
deny→acceptance chain is executed for real against ISOLATED state and captured as
a numbered evidence file. The verdict is re-derived by crew's acceptance view —
an evaluator that did not run the pipeline (evaluator≠creator).

The deterministic trigger is a canary token (`AW25-GOLDEN-DENY-ME`) banned by
`evidence/aw25-golden/ruleset/aw25-golden.md` (rule `POL-2500`) and enforced by
the paired `wicked-governance` Policy of the same id. The run's intent carries
the token, so the unit's evaluated governance context trips the `contains`
trigger with no reliance on any worker model's choice.

Environment (all overridable — see `evidence/aw25-golden/run.sh` header):

- `WICKED_CORE_BIN` — wicked-core with the `rules` subcommands (main ≥ #310)
- `CREW_CLI` — crew daemon entry (installed `wicked-crew` ≥ 0.7.2, or
  `node <wicked-crew>/packages/crew/dist/cli/index.js` from main ≥ #359)
- `ESTATE_MCP_BIN` — installed `wicked-estate-mcp` ≥ 0.15.1
- `AW25_PORT` (default 7907, never 7701), `AW25_WORK` (scratch; never
  `~/.wicked-crew`), `AW25_EVIDENCE_DIR` (where the numbered chain lands)

## Steps

### Step 1: Run the full golden-path chain (bash)

```bash
AW25_EVIDENCE_DIR="${AW25_EVIDENCE_DIR:-${TMPDIR:-/tmp}/aw25-evidence-$$}" \
  bash "$(git rev-parse --show-toplevel)/evidence/aw25-golden/run.sh"
```

**Expect**: Exit code 0 and the final line `AW25 GOLDEN PATH: PASS`. The script
fails loud (exit 1) at the FIRST broken hop — ingest refusal, missing recall
citation, no run-scoped denial, or an acceptance payload without the
ConformanceClaim — and exit 2 for environment failures. The isolated daemon is
killed on exit either way.

### Step 2: Re-verify the recall citation from the recorded evidence (python3)

```bash
EV="${AW25_EVIDENCE_DIR:?set AW25_EVIDENCE_DIR to the dir used in Step 1}"
python3 - "$EV/04-rules-recall.json" <<'PYEOF'
import json, sys
body = json.load(open(sys.argv[1]))
rules = {r["id"]: r for r in body["rules"]}
r = rules["POL-2500"]
assert r["provenance"]["ref"].startswith("aw25-golden.md@") and r["provenance"]["ref"].endswith("#POL-2500")
assert "wiki://aw25-golden#POL-2500" in r["statement"]
print("A2 ok:", r["provenance"]["ref"])
PYEOF
```

**Expect**: Exit code 0, the digest-bearing provenance ref printed.

### Step 3: Re-verify the denial + acceptance payload from the recorded evidence (python3)

```bash
EV="${AW25_EVIDENCE_DIR:?set AW25_EVIDENCE_DIR to the dir used in Step 1}"
python3 - "$EV/06-governance-claims.json" "$EV/07-acceptance.json" <<'PYEOF'
import json, sys
claims = json.load(open(sys.argv[1]))["claims"]
denies = [c for c in claims if c["decision"] == "deny" and "POL-2500" in c["policy_ids"]]
assert denies and "wiki://aw25-golden#POL-2500" in json.dumps(denies[0])
a = json.load(open(sys.argv[2]))["conformance"]
assert a["denied"] is True and a["guardrailed"] is False and "POL-2500" in a["summary"]
cited = [cl for cl in a["claims"] if cl["decision"] == "deny" and "POL-2500" in cl["policyIds"]]
assert cited and any("wiki://aw25-golden#POL-2500" in r["statement"] for r in cited[0]["rules"])
print("A3+A4 ok: denial and acceptance both cite POL-2500 + wiki URI")
PYEOF
```

**Expect**: Exit code 0 — the denial and the acceptance payload independently
cite the rule id and the wiki URI.

## Cleanup

```bash
# The runner's trap already stopped the isolated daemon. Scratch state under
# AW25_WORK is left for inspection; remove it if disk pressure matters:
# rm -rf "$AW25_WORK"
true
```
