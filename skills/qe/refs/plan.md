---
phase_relevance: ["clarify", "design", "build"]
archetype_relevance: ["specify", "build"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     wicked-testing's `plan` orchestrator). Loaded on demand
     via Read() from the router's `plan` action — not a skill. -->


# qe plan — full playbook

One skill for everything before tests get written. Figures out what to test,
what can go wrong, and whether the design lets you test at all.

## Usage

```
wicked-garden-qe plan [target] [--project <name>] [--json]
```

- `target` — file path, directory, or feature description (optional; defaults to current dir)
- `--project <name>` — associate strategy with this project
- `--json` — emit JSON envelope

### Preflight: check config

Verify `.wicked-testing/config.json` exists. If not:

```
Config not found. Run wicked-garden-qe setup first.
Code: ERR_NO_CONFIG
```

## When to use

- Before the build phase of a feature
- When a PR's scope is unclear and you need to know what to test
- When acceptance criteria were just drafted (requirements-quality gate)
- When a design doc is ready but no code exists yet (testability gate)

## How it dispatches

Read the target first, then route:

| Target                                     | Dispatch                                          |
|--------------------------------------------|---------------------------------------------------|
| Acceptance criteria / clarify doc          | `wicked-garden-qe-requirements-quality-analyst`     |
| Design doc / architecture sketch           | `wicked-garden-qe-testability-reviewer`             |
| Feature description / user story           | `wicked-garden-qe-test-strategist`                  |
| Known-risky change (security, data, perf)  | `wicked-garden-qe-risk-assessor`                    |
| "Test everything" / broad review           | All four in parallel; merge findings              |

When multiple apply, dispatch in parallel. Merge results in the reply — no
unrelated raw outputs dumped in.

**Never dispatch `wicked-garden-qe-test-strategist` directly** — always enter planning through
this skill so the 4-way router above (strategist / risk / testability /
AC-quality) runs. Calling `wicked-garden-qe-test-strategist` directly bypasses the router
(wave-6 audit fix #63).

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context:

```
Skill(
  skill="wicked-garden-qe-test-strategist",
  args="""Generate a comprehensive test strategy for the target below.

## Target
{file path, directory, or feature description}

## Instructions
1. Classify the change type (UI, API, both, data, config).
2. Analyze the surface area (public APIs, functions, endpoints).
3. Generate positive + negative scenario pairs for every feature.
4. Identify risk areas and confidence level.
5. Flag any specification gaps discovered.

**MANDATORY**: Every scenario must have BOTH positive AND negative counterpart.
Return findings in the standard test-strategist format."""
)
```

Swap the `skill` id to the matching worker from the table above. For the
"test everything" path, dispatch all four in parallel (one `Skill(...)` call
per worker in the same turn) and merge the returned findings.

## Tier-2 specialists this skill may pull in

For domain-specific planning signals, dispatch a specialist and fold its
output into the strategy document. These don't render verdicts — they add
risk+scenario coverage where the generalist agents would miss signal:

| Trigger (anything in the target that matches)            | Specialist                              |
|----------------------------------------------------------|-----------------------------------------|
| React/Vue/Svelte component under test                    | `wicked-garden-qe-ui-component-test-engineer` |
| API / service boundary (REST, gRPC, GraphQL)             | `wicked-garden-qe-integration-test-engineer`  |
| Database migration or schema change                      | `wicked-garden-qe-data-quality-tester`        |
| Performance-sensitive path (heavy compute, I/O)          | `wicked-garden-qe-load-performance-engineer`  |
| Multi-step user journey                                  | `wicked-garden-qe-e2e-orchestrator`           |
| UI with visual regressions risk (CSS, theming)           | `wicked-garden-qe-visual-regression-engineer` |
| User-facing surface (WCAG 2.1 AA relevance)              | `wicked-garden-qe-a11y-test-engineer`         |
| Parser / serializer / round-trip / invariants            | `wicked-garden-qe-fuzz-property-engineer`     |
| Translated / RTL / pluralization-sensitive copy          | `wicked-garden-qe-localization-test-engineer` |
| Service with logs / metrics / traces / PII-in-signals    | `wicked-garden-qe-observability-test-engineer` |
| Test-suite effectiveness evaluation (kill rate)          | `wicked-garden-qe-mutation-test-engineer`     |
| Failure-mode / resilience planning                       | `wicked-garden-qe-chaos-test-engineer`        |
| Application-security scope (SAST/DAST/authz)             | `wicked-garden-qe-security-test-engineer`     |
| LLM / AI feature in the codebase                         | `wicked-garden-qe-ai-feature-test-engineer`   |
| Terraform / helm / k8s / IaC / policy-as-code            | `wicked-garden-qe-iac-test-engineer`          |
| Regulated industry (SOC2 / HIPAA / GDPR / PCI)           | `wicked-garden-qe-compliance-test-engineer`   |
| Test suite with snapshots (jest / syrupy / cassettes)    | `wicked-garden-qe-snapshot-hygiene-auditor`   |
| Test-suite quality itself (smells, dead tests)           | `wicked-garden-qe-test-code-quality-auditor`  |
| Prod incident -> regression scenario synthesis           | `wicked-garden-qe-incident-to-scenario-synthesizer` |

Every specialist above is an in-catalog garden fork worker — dispatch it with the Skill tool.

## Strategy record

The strategy is written to DomainStore by the dispatched agent via
`store.create('strategies', {...})`, which also fires
`wicked.test.strategy.generated` on the bus when present.

## Output

- A test strategy: scenarios (positive + negative), risk matrix, testability
  verdict, AC quality verdict
- Concrete next actions: which scenarios to author next, which ACs to rewrite,
  which design changes unblock testing
- A pointer to the ledger where this plan is recorded

Emits `wicked.test.strategy.generated` on the bus when present.

**With `--json`** — emit the JSON envelope (python3-with-python-fallback,
cross-platform):

```bash
python3 -c "import json,sys; sys.stdout.write(json.dumps({'ok': True, 'data': {'strategy_id': '...', 'scenario_count': N, 'project': '...'}, 'meta': {'command': 'wicked-garden-qe plan', 'duration_ms': 0, 'schema_version': 1, 'store_mode': '...'}}))" 2>/dev/null || python -c "import json,sys; sys.stdout.write(json.dumps({'ok': True, 'data': {'strategy_id': '...', 'scenario_count': N, 'project': '...'}, 'meta': {'command': 'wicked-garden-qe plan', 'duration_ms': 0, 'schema_version': 1, 'store_mode': '...'}}))"
```

## References

- `docs/INTEGRATION.md` (wicked-testing npm package)
- `docs/NAMESPACE.md` (wicked-testing npm package)
- `../../qe-test-strategist/SKILL.md`, `../../qe-risk-assessor/SKILL.md`,
  `../../qe-testability-reviewer/SKILL.md`, `../../qe-requirements-quality-analyst/SKILL.md`
