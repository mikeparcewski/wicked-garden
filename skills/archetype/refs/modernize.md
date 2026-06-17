# modernize — discover / extract / blueprint / transform / parity / cutover

For porting a **legacy codebase to a new stack** (a language/framework/runtime
jump, a rehost/replatform, a rewrite from the working code as the spec). This is
NOT `migrate` — `migrate` is in-place expand-contract shape change on a *running*
system. `modernize` reverse-engineers an estate, blueprints a target, transforms
with leverage, and proves parity before cutting over.

This archetype is a **general modernization steering shape**. It is self-contained
and **composes the general `code-modernization` skills** for the heavy lifting —
it does not own a parallel lifecycle, and it routes the same rigor/gate discipline
garden already preaches into those skills.

## Phase shape

| Phase     | Goal                                                              |
|-----------|-------------------------------------------------------------------|
| discover  | Map the estate; resolve the legacy **stack class** via the registry. |
| extract   | Pull out the testable business rules (what it does, not how).     |
| blueprint | Decide the target-state architecture. Decision matrix, not prose. |
| transform | Codemod / regenerate with leverage. Deterministic before AI.      |
| parity    | Prove old ≡ new on identical inputs. Differential equivalence.    |
| cutover   | Switch to the new stack. **Hard gate** — staged, parity-proved.   |

## Produces

- **Modernization blueprint**: the target-state architecture (target stack,
  package/module structure, API surface, data model) + the recorded technique
  choice per transform wave.
- **Parity proof**: an executable, re-derivable equivalence check — old vs new
  on identical seeded inputs assert identical outputs (the trust, not review).

The cutover gate **re-derives** these via `wicked-loom` (`scripts/qe/vault_gate.py`
shells `wicked-loom gate`, which shells `wicked-vault cross-check`): the parity
harness is re-run and the blueprint post-condition re-checked, never trusting a
self-asserted "ported fine". wicked-loom (the gate engine) and wicked-vault (the
evidence backend) are **required** peers (installed by `/wicked-garden:setup`); if
loom is unresolvable — or the vault behind it absent — the gate **fails closed**
(`gate: "unavailable"`, `satisfied: false`) rather than self-asserting a PASS.
Because `cutover` is a HARD gate, the gate also demands an **independent
attestation**: an evaluator who is **not** the modernizer confirms the parity proof
and blueprint are adequate (recorded via `wicked-vault:analyze-evidence`), and the
gate fails closed on a self-grade.

## HITL

`hard:cutover-gate` — cutover is a hard gate. Don't cut over to the new stack
without explicit user approval AND a green pre-cutover checklist (parity proved on
real seeded data, rollback path to the legacy system tested, traffic plan staged).

## Ground in the repo's method first

Before you discover, check for **wicked-understanding** repo playbooks (the opt-in
"how to work in THIS repo" layer). A modernization lives or dies on repo-specific
wiring — the build/run command, where the seam between old and new lives, the
deploy/rollback command. If its skills are present, **load the matching playbook**
and let it name those points instead of rediscovering them mid-cutover. Absent?
Discover it the usual way — and consider
`npx skills add mikeparcewski/wicked-understanding --all`.

## How to run

### discover

1. Survey the legacy estate: entry points, modules, data stores, external
   contracts. Use `code-modernization:modernize-assess` for the structural read
   and `code-modernization:modernize-brief` to frame scope + risk.
2. **Resolve the stack class — DO NOT fabricate a playbook.** Read the dispatch
   truth in `.claude-plugin/stack-registry.json` via the reader:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
     "${CLAUDE_PLUGIN_ROOT}/scripts/crew/stack_registry.py" \
     resolve --stack <stack-id>
   ```
   - `status: wired` (exit 0) → the printed `dispatch` names the `blueprint`,
     `transform`, and `validate` skills/gate to use in the phases below.
   - unknown / `planned` / `none` (exit 3) → the reader returns a **capability-gap
     task** and emits `wicked.modernize.stack_gap`. **STOP.** Create that task
     (`TaskCreate`) and surface the gap to the user — never invent a transform for a
     stack the system can't actually handle. This is the fail-closed ETHOS as
     dispatch data: an honest "we don't handle this yet" beats a fabricated port.
   - When the legacy stack genuinely is not in the registry but IS general
     (any language → modern target), use the `generic-cross-stack` entry, which is
     wired to the general `code-modernization` skills.

### extract

1. Mine the domain logic — calculations, validations, policies — into testable
   Given/When/Then specs with `code-modernization:modernize-extract-rules`.
   Separate *what the business requires* from *how the old code happened to do it*.
2. These extracted rules become the parity oracle: the new stack must satisfy the
   same rules. Pin each rule so the parity phase has a bar to check.

### blueprint

1. Decide the **target-state architecture** with `code-modernization:modernize-reimagine`
   (the registry `blueprint` field names this for the resolved stack). Capture it
   as a **decision matrix, not a narrative**: target stack + version (pin, don't
   "latest"), module/package structure, API surface, data model, the engines/tools.
2. Write the blueprint to `docs/modernization/{slug}-blueprint.md` and declare the
   re-derivable contract early so the cutover gate has a bar. If a vault is
   resolvable (`scripts/qe/vault_gate.py resolve` → `available: true`):
   `wicked-vault init` then
   `wicked-vault declare-contract --scope <scope> --phase modernize --spec contract.json`.
   `required_evidence` must pin `parity-proof` to a deterministic verifier
   (`exit_code_eq:0` on the differential harness). Skip silently if no vault.

### transform

1. Transform **with leverage, not an agent-grind** — follow
   `wicked-garden:engineering:large-scale-migration` (MAP → TRANSFORM → GATE) and
   its ranked techniques menu: **prefer the lowest-numbered technique that fully
   covers the task** (deterministic recipe/codemod before AI-assisted waves), and
   **record the chosen technique** per wave. Drive the bulk through a deterministic
   codemod/codegen; touch only the self-flagged residue by hand.
2. Run the resolved `transform` skills (`code-modernization:modernize-map` then
   `code-modernization:modernize-transform`) over the estate.
3. **Don't grandfather.** No exemptions, no "left raw with a TODO" — an exemption
   preserves the exact legacy case the modernization exists to remove.

### parity

1. Prove **old ≡ new** on identical seeded inputs (differential equivalence) — the
   parity proof is the trust, not a diff review. Seed broadly; an empty fixture
   passes trivially and lies.
2. Harden the result with `code-modernization:modernize-harden` (security/CVEs,
   error handling) before it carries traffic.
3. Record the parity proof as re-derivable evidence (vault present; **wicked-vault
   ≥ 0.4.0**):
   `wicked-vault record --scope <scope> --phase modernize --claim parity-proof
   --kind differential --source "<the differential harness command>"
   --criteria "old(input) == new(input) on seeded data" --verifier exit_code_eq:0
   --actor "${WICKED_VAULT_ACTOR:-garden-prove}" --run`. The **`--actor`** is
   mandatory because `cutover` is a hard gate: vault ≥ 0.4.0 refuses an `attest`
   over weak/ambient-identity evidence, so without an explicit actor the
   independent attestation fails closed and cutover can never be gated PASS. The
   `--run` captures the real exit code now and the gate re-runs it later — a claim
   you can't re-derive is not evidence. No vault → fall back to
   `evidence_tracker.py claim`.

### cutover

1. **Pre-cutover checklist**:
   - Parity proved on real seeded data. (`✓` or block.)
   - Rollback path to the legacy system tested.
   - Traffic plan staged (canary first, not big-bang).
   - Monitoring + alerts cover the new stack.
2. **Gate before any switch** — don't self-assert the checklist. Run the
   produces-gate WITH judgment:
   `scripts/qe/prove.py parity-proof --by "<command>" --scope <scope> --phase modernize --with-attestations`
   (frictionless, single claim — re-derive, don't assert) — or the full multi-claim
   contract via
   `scripts/qe/vault_gate.py gate <project_dir> --scope <scope> --phase modernize --with-attestations`.
   `--with-attestations` keeps this gate `UNATTESTED`/`REJECT` until an INDEPENDENT
   evaluator (not the doer) runs `wicked-vault attest <artifact-id> --opinion pass`
   — find it via `wicked-vault list --scope <scope> --phase modernize`. The doer's
   own evidence cannot satisfy a hard gate. (exit 0 = satisfied.) A REJECT means the
   parity proof doesn't clear its contract — fix the work, not the claim. An
   `unavailable` verdict means the required vault isn't installed — run
   `/wicked-garden:setup`. **No cutover on a fail-closed verdict.**
3. **Cutover staged**: canary the new stack, watch, ramp. Hand the rollout tail to
   the `ship` archetype if blast radius warrants.
4. The cutover gate is HARD — explicit user "go" before each ramp step.
5. If anything looks off post-cutover: **roll back to the legacy system first,
   debug second.**

## When to stop

Cutover may only proceed when the produces-gate is satisfied — check it, don't
self-assert it (see the cutover step). Modernize is done when traffic is on the new
stack, parity has soaked, and the blueprint matches what shipped. Hand off to
`review` for a post-modernization audit when the change touched compliance or
revenue surface.

## Anti-patterns

- **Don't fabricate a playbook for an unhandled stack.** If the registry says
  `planned`/`none`/unknown, emit the gap task and stop. A fabricated port is the
  exact failure the fail-closed ETHOS exists to prevent.
- **Don't hand-edit the bulk.** Modernization is MAP → TRANSFORM → GATE, not "fan
  out N agents to rewrite each file." Deterministic transform first; AI only for the
  residue, eval-gated.
- **Don't trust build-green as parity.** Build/test green ≠ behavior preserved —
  *especially* for any LLM/agent surface. Prove `old ≡ new` on real inputs.
- **Don't big-bang the cutover.** Canary, ramp, soak — same discipline as `migrate`.
- **Don't skip rollback testing.** A path back to the legacy system you haven't
  exercised is not a rollback path.
