---
phase_relevance: ["build", "test", "review"]
archetype_relevance: ["build", "ship", "review"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     wicked-testing's `execution` orchestrator). Loaded on demand
     via Read() from the router's `execute` action — not a skill. -->


# qe execute — full playbook

The doer. Takes a scenario or test command, runs it, captures everything,
writes the ledger entry. Evidence lives under
`.wicked-testing/evidence/<run-id>/`.

## Usage

```
wicked-garden-qe execute [target] [--project <name>] [--suite] [--json]
```

- `target` — scenario file path, scenario name, or a test command
- `--project` — associate the run with a named project
- `--suite` — run the project's full test suite instead of a scenario
- `--json` — emit JSON envelope

## When to use

- You have a scenario ready and need a real run with evidence
- You want to run the existing test suite and record the verdict in the ledger
- You're in a crew test phase and need all scenarios executed

## How it dispatches

| Input                                                    | Dispatch                                                                                                 |
|----------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| A scenario file                                          | `wicked-garden-qe-scenario-executor`                                                                       |
| Scenario + "give me a verdict" (acceptance-grade)        | Route to `wicked-garden-qe accept` — the 3-role isolated pipeline (writer → executor → reviewer). |
| Scenario + "give me a verdict" (dev-loop, explicit)      | `wicked-garden-qe-test-designer` ONLY if the caller explicitly asks for the fast-path / self-graded loop.  |
| Pre-written plan, "just execute"                         | `wicked-garden-qe-acceptance-test-executor`                                                                |
| "run the suite" (no scenario)                            | Project's native runner; record result                                                                   |
| Contract verification                                    | `wicked-garden-qe-contract-testing-engineer`                                                               |
| "wire CI" / "bootstrap CI for tests"                     | Emit CI trigger (pre-push / GH Actions step); record nothing until a real run executes                   |

**Default posture:** verdict requests go to the 3-role pipeline. `wicked-garden-qe-test-designer`
is the dev-loop fast path with known self-grading risk; it is never the default
and never used for audit / CI / crew-phase sign-off evidence. See the warning
in `../../qe-test-designer/SKILL.md`.

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context:

```
Skill(
  skill="wicked-garden-qe-scenario-executor",
  args="""Execute the scenario file at the path below and capture evidence.

## Scenario Path
{path to scenarios/<name>.md}

## Evidence Directory
.wicked-testing/evidence/{RUN_ID}/

## Instructions
1. Read the scenario via the Read tool.
2. For each step, run the command via Bash with the scenario's timeout
   (enforce via {WT_LIB}/exec-with-timeout.mjs when available — the shell
   fallback chain is `timeout || gtimeout || bare` with a warning log).
3. Capture stdout, stderr, exit code, wall-clock duration per step.
4. Write step-N.json + evidence.json + artifact files into EVIDENCE_DIR.
5. Determine per-step outcome: exit 0 = PASS, non-zero = FAIL, CLI missing = SKIPPED.

Do NOT self-grade qualitative outcomes. For acceptance-grade verdicts
route to wicked-garden-qe accept instead."""
)
```

Swap the `skill` id per the table above. For a scenario that also needs
contract verification, dispatch `wicked-garden-qe-scenario-executor` and
`wicked-garden-qe-contract-testing-engineer` in parallel (one `Skill(...)` call each in the
same turn) and merge results.

## Tier-2 specialists this skill routes to

For specialized execution paths — chaos experiments, load generators, visual
baselines, etc. — dispatch the specialist. Each writes its own artifacts to
`EVIDENCE_DIR` and returns an evidence report the skill includes in the run
summary:

| Trigger                                                | Specialist                                  |
|--------------------------------------------------------|---------------------------------------------|
| Chaos experiment (Toxiproxy / Chaos Mesh / AWS FIS)    | `wicked-garden-qe-chaos-test-engineer`        |
| Load / perf run (k6 / locust / hey)                    | `wicked-garden-qe-load-performance-engineer`  |
| Visual regression run (Playwright + pixelmatch)        | `wicked-garden-qe-visual-regression-engineer` |
| Full user-journey E2E (multi-context Playwright)       | `wicked-garden-qe-e2e-orchestrator`           |
| Component run (RTL + user-event)                       | `wicked-garden-qe-ui-component-test-engineer` |
| Integration run (real services via testcontainers)    | `wicked-garden-qe-integration-test-engineer`  |
| Fuzz / property run (Hypothesis / fast-check / AFL++)  | `wicked-garden-qe-fuzz-property-engineer`     |
| Security run (SAST scan / DAST scan / secrets check)   | `wicked-garden-qe-security-test-engineer`     |
| AI-feature test (prompt-injection / eval harness)      | `wicked-garden-qe-ai-feature-test-engineer`   |
| IaC validation run (terraform validate / opa / checkov)| `wicked-garden-qe-iac-test-engineer`          |
| Compliance evidence collection (SOC2 / HIPAA controls) | `wicked-garden-qe-compliance-test-engineer`   |
| Selective-execution — "which tests for this diff"      | `wicked-garden-qe-test-impact-analyzer`       |

Chaos / load / security-DAST specialists MUST respect the scenario's `trust_level` frontmatter
field. Production-impacting runs require `trust_level: production-authorized`
AND a `change-ticket:` reference; otherwise the specialist refuses and records
SKIP with reason `trust-level-insufficient`.

## Evidence & ledger

- Every run produces a `run_id` (UUID v4 from DomainStore)
- Artifacts land in `.wicked-testing/evidence/<run-id>/`
- `manifest.json` is written per `docs/EVIDENCE.md` (produced by `wicked-ledger`'s `buildManifest`)
- The run + verdict are written to the SQLite ledger
- Bus events emitted (when bus present): `wicked.testrun.started`,
  `wicked.test.run.completed`, `wicked.evidence.captured`, and finally
  `wicked.test.verdict.created`. These names are the wicked-ledger
  emitter's existing wire contract; the 3-segment stragglers get the
  4-segment `wicked.qe.*` rebrand at the bus-emit seam in Phase 6c —
  do not rename them in this playbook first

## Output

- The run_id + path to `manifest.json`
- Verdict (PASS / FAIL / N-A / SKIP)
- One-line summary — never a wall of tool output

## Legacy invocations (absorbed in 0.4.0)

| Old command    | Ask execution instead |
|----------------|-----------------------|
| `run`          | "run scenario <path>" — execution dispatches `wicked-garden-qe-scenario-executor` and records the run |
| `ci-bootstrap` | "wire CI to run these tests" — execution emits the CI trigger; for the portable evidence gate use wicked-garden's `compile` |

## References

- `docs/INTEGRATION.md` (wicked-testing npm package)
- `docs/EVIDENCE.md` (wicked-testing npm package)
- `../../qe-scenario-executor/SKILL.md`, `../../qe-test-designer/SKILL.md`,
  `../../qe-acceptance-test-executor/SKILL.md`

## Helper resolution (`{WT_LIB}`)

`{WT_LIB}` is the wicked-testing npm package's `lib/` directory — the helper
modules stay in that package until the 6c extraction. Resolve it (cross-platform):

```bash
WT_LIB="$(npm root -g 2>/dev/null)/wicked-testing/lib"
[ -d "$WT_LIB" ] || WT_LIB="$(npm root 2>/dev/null)/wicked-testing/lib"
```
