# Garden gate — LIVE validation (peers present)

**Date:** 2026-06-17 · **Repo:** wicked-garden @ v12.25.0 (`334dec95`)
**Question:** Does the produces-gate actually re-derive evidence through wicked-loom → wicked-vault
(NOT a self-grade), now that the peers are installed? Does it fail closed when they aren't?

**VERDICT: PASS — the gate is real, not ceremony.** loom + vault resolve; a true claim re-derives to
PASS, a false/tampered claim REJECTs, the hard gate enforces evaluator≠creator by exact identity and
fails closed on weak/ambient identity, and the gate fails closed (`gate:"unavailable"`, never a vacuous
pass) when loom is disabled. The `modernize` archetype is detectable and its `cutover` hard gate is wired.

---

## 1. Peer availability

| Peer | Resolves? | How | Version |
|------|-----------|-----|---------|
| wicked-loom | YES | PATH `/opt/homebrew/bin/wicked-loom` → `/opt/homebrew/lib/node_modules/wicked-loom/bin/loom.mjs` | **0.2.3** (npm global) |
| wicked-vault | YES | PATH `/opt/homebrew/bin/wicked-vault`; `npx wicked-vault --version` | **0.4.0** ✅ ≥ 0.4.0 hard-gate floor |

loom has no `--version` subcommand (`commands: resolve/doctor/compose/gate/flow`); version via `npm ls -g`.

```
$ wicked-loom doctor
{"peers": [{"peer": "vault", "status": "ok", "installed": "0.4.0", "pin": "0.3"},
           {"peer": "testing", "status": "ok", "installed": "0.4.2", "pin": "0.3"},
           {"peer": "brain", "status": "ok", "installed": "0.15.2", "pin": "0.14"},
           {"peer": "bus", "status": "error", "detail": "", "pin": "2.0"}]}

$ wicked-loom resolve vault
{"peer": "vault", "command": ["/opt/homebrew/bin/wicked-vault"]}

$ .venv/bin/python scripts/qe/vault_gate.py resolve
{"resolvable": true, "installed": true, "argv_prefix": ["/opt/homebrew/bin/wicked-vault"], "loom_shim_loaded": true}
```

The `_loom` shim imports (`loom_shim_loaded: true`) — the #891 CLI sys.path regression is NOT present;
the gate is genuinely live, not silently failing closed.

---

## 2. Gate re-derivation — exercised live via `scripts/qe/prove.py`

`prove.py` is the front door for `/wicked-garden:prove`: it RUNS the command, freezes the real exit
code/stdout as vault evidence, then re-derives the verdict via `vault_gate.gate_satisfied()` →
`wicked-loom gate` → `wicked-vault cross-check`. All runs used a throwaway temp `--project-dir`.

### (a) TRUE claim → re-derives to PASS
```
$ prove.py tests-pass --by "true"
{ "satisfied": true, "re_derived": true, "gate": "vault-cross-check", "overall": "PASS",
  "claims": [{"claim_id":"tests-pass","hash_ok":true,"verifier_status":"pass","result":"PASS","detail":"exit_code=0"}] }
EXIT=0
```

### (b) FALSE claim → REJECT (on the REAL exit code, not the assertion)
```
$ prove.py tests-pass --by "false"        # command exits 1; verifier exit_code_eq:0
{ "satisfied": false, "re_derived": true, "gate": "vault-cross-check", "overall": "REJECT",
  "claims": [{"hash_ok":true,"verifier_status":"fail","result":"FAIL","detail":"exit_code=1 != 0"}] }
EXIT=1
```

### (b2) Output-tamper → REJECT (verifier re-runs against frozen stdout)
```
$ prove.py grep-clean --by "echo CONTAINS_TODO_HERE" --verifier not_contains:TODO
{ "satisfied": false, "re_derived": true, "overall": "REJECT",
  "claims": [{"verifier_status":"fail","detail":"forbidden /TODO/ is present"}] }
EXIT=1
```

`re_derived:true` + `hash_ok:true` on every run = evidence was re-hashed and the verifier re-run, never
a cached/claimed status. **A claimed-but-false "tests pass" is rejected.**

### (c) HARD GATE — `--with-attestations` enforces evaluator≠creator

Recording path uses explicit actor → `created_by="garden-prove", created_by_source="explicit"` (strong).

**c-0. Doer's own evidence cannot satisfy a hard gate** (even though the command passed):
```
$ prove.py deploy-ok --by "true" --with-attestations
{ "satisfied": false, "overall": "REJECT",
  "claims": [{"verifier_status":"pass","result":"UNATTESTED","detail":"require_attestation: no independent opinion recorded"}] }
EXIT=1   # prove.py exit; gate fails until an INDEPENDENT party attests
```

**c-i. SELF-GRADE rejected** (evaluator == creator), by exact identity:
```
$ wicked-vault attest <ART> --opinion pass --evaluator garden-prove
{"error": "attest refused (G10/D4): evaluator 'garden-prove' equals the artifact creator 'garden-prove'
           — a judgment must be independent of the worker"}   exit=1
```

**c-ii. INDEPENDENT attestation recorded** (evaluator reviewer-bot ≠ creator):
```
$ wicked-vault attest <ART> --opinion pass --rationale "independent review..." --evaluator reviewer-bot
{"attestation_id":"019ED8663A...","opinion":"pass"}   exit=0
```

**c-iii. Re-gate now PASSES** (attestation embedded in the re-derived verdict):
```
$ vault_gate.py gate <PD> --scope prove --phase verify --with-attestations
{ "satisfied": true, "re_derived": true, "overall": "PASS",
  "claims": [{"result":"PASS","attestation":{"opinion":"pass","evaluator":"reviewer-bot","stale":false}}] }
EXIT=0
```

**c-iv. WEAK/AMBIENT identity fails closed** (the vault ≥ 0.4.0 breaking-change floor). Evidence recorded
without `--actor`/`WICKED_VAULT_ACTOR` → `created_by_source="env-user"` (ambient `$USER`):
```
$ wicked-vault attest <ART> --opinion pass --evaluator reviewer-bot
{"error": "attest refused (G10/D4): the artifact was recorded under a weak/ambient worker identity
           (created_by_source='env-user'), so 'evaluator != created_by' is not a trustworthy
           independence signal. Re-record with an explicit --actor ... or pass --allow-weak-worker-identity ..."}
exit=1
# with the audited escape hatch:
$ wicked-vault attest <ART> --opinion pass --evaluator reviewer-bot --allow-weak-worker-identity
{"attestation_id":"019ED866...","opinion":"pass"}   exit=0   (weakness stamped for audit)
```
This is exactly why `prove.py::_prove_actor` records under explicit `garden-prove`.

---

## 3. Fail-closed when loom is absent (the I2 invariant)

Simulated loom-absent via `WICKED_LOOM_CUTOVER=off` (loom disabled = unresolvable resolver).

```
$ WICKED_LOOM_CUTOVER=off prove.py tests-pass --by "true"
{ "satisfied": false, "gate": "unavailable", "re_derived": false,
  "error": "evidence backend (wicked-loom/wicked-vault) not resolvable — fails closed, never a vacuous pass" }
EXIT=3    # prove.py: 3==fail-closed, distinct from 1==REJECT

$ WICKED_LOOM_CUTOVER=off vault_gate.py gate <PD> --scope prove --phase verify
{ "satisfied": false, "re_derived": false, "gate": "unavailable",
  "reason": "wicked-vault is a required evidence backend but is not resolvable. Install it
             (`npm i -g wicked-vault` ...) and re-run /wicked-garden:setup. Gate fails closed ..." }
EXIT=1

$ WICKED_LOOM_CUTOVER=off vault_gate.py resolve
{"resolvable": false, "installed": true, "argv_prefix": null, "loom_shim_loaded": true}
```

**Even with a TRUE claim and a concrete vault still installed, the gate refuses to PASS when loom is
disabled.** `satisfied:false / gate:"unavailable" / re_derived:false` — never a vacuous pass. ✅

---

## 4. `modernize` archetype detectable + cutover hard-gate wired

- Catalog `.claude-plugin/archetypes.json`: `modernize` present (10 archetypes total). Phases
  `discover→extract→blueprint→transform→parity→cutover`; produces `modernization-blueprint`,
  `parity-proof`; `hitl: "hard:cutover-gate"`; `cost_band: high`; `maturity: research`.
- Classifier `scripts/crew/archetypes_v11.detect_archetypes()` (data-driven from the catalog — hence
  no literal "modernize" string in the .py):
  ```
  prompt="Modernize this legacy COBOL codebase by porting it to a new Java stack and prove parity before cutover."
  → [('modernize', 0.75, ['modernize','cobol']), ('migrate', 0.55, ['cutover']), ('triage', 1.0, [...])]
  ```
  (v11 LLM classifier lives at `skills/classify/SKILL.md`; no `commands/classify.md` — invoked via the skill.)
- Playbook `skills/archetype/refs/modernize.md`: `cutover` documented as a **hard gate** that re-derives
  `parity-proof` via `wicked-loom gate` → `wicked-vault cross-check`, demands an **independent attestation**
  (evaluator ≠ modernizer), and mandates `--actor "${WICKED_VAULT_ACTOR:-garden-prove}"` because vault ≥ 0.4.0
  refuses attest on weak identity — matching the live behavior in §2c.

---

## Findings / bugs

- **No gate bug found.** Re-derivation, REJECT-on-false, hard-gate identity, and fail-closed all behave
  per the v12 doctrine in `.claude/CLAUDE.md` ("Evidence is re-derived").
- **Doc nit (not a code bug):** `wicked-vault --help` (v0.4.0) documents a `--cwd <dir>` global, but the
  installed binary rejects it (`{"error":"unknown command: --cwd"}`). attest/list were exercised via
  walk-up discovery (run from inside the project dir) instead. Belongs to wicked-vault, not garden; flag
  upstream if `--cwd` is meant to be supported. Did not affect any garden gate result.

## Repro environment
- loom 0.2.3, vault 0.4.0, testing 0.4.2, brain 0.15.2 (bus: error) per `wicked-loom doctor`.
- Python: repo `.venv/bin/python`. All `prove.py`/`vault_gate.py` runs used throwaway `mktemp -d` project dirs.
