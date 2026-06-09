# ADR 0002 — Major cleanup: keep only what the agent actually uses

- **Status:** Proposed (dead-command removal executed; the rest awaits greenlight)
- **Date:** 2026-06-09

## The test

The customer is the AI coding agent. A feature **stays only if it does at least one of:**
1. **makes the agent's life easier** (a capability/ergonomic the agent lacks natively), or
2. **greatly reduces tokens** (vs. the agent's native Read/Grep/Bash/subagent path), or
3. **improves the quality of the final output** (catches errors, enforces evidence, adds a perspective the agent can't produce alone).

If a feature is a checklist the agent already applies, wrapped in a `Task(subagent)` hop that costs *more* tokens and latency for the *same* output — it fails all three. Cut it. (Rubrics worth keeping become inline `refs/` the agent loads on demand — no dispatch hop.)

This is grounded in a full hands-on pass: every domain was invoked and judged against native tools.

## KEEP (earns its place)

| Feature | Why (criterion) |
|---|---|
| `prove` + the produces-gate (vault/loom, outputs + attestation + semantic) | **output** — stops false "done"; no native equivalent |
| `/compile` | **easier** — emits a self-contained gate into any repo |
| code-graph (codegraph + injected-edge extractors) → `search:blast-radius`, `search:lineage` | **output + tokens** — finds injected relationships grep can't; impact in one query vs. reading many files |
| wicked-patch (`rename`/`add-field`/`remove`/`apply`) — once wired to the graph DB | **easier + output** — deterministic multi-file refactor |
| `jam:council` / multi-model | **output** — real external-model perspective the agent can't produce alone |
| `jam:brainstorm` / `revisit` (the wicked-brain decision-memory loop) | **output** — longitudinal decision/outcome memory |
| `smaht:briefing` | **tokens** — one event-store query replaces stitching git+memory+tasks |
| `data:ontology` | **output** — real RDF-vocabulary engine (beats free-recall) |
| `persona:as` (built-in personas) + `persona:list` | **output** — hand-authored constraints/memories measurably steer; cheap discovery |
| `platform:security` (now drives real `gitleaks`/`semgrep`) | **output** — real SAST/secrets, not grep-guessing |
| `platform:toolchain` | **tokens/easier** — fast deterministic CLI inventory |
| wicked-testing integration (`acceptance`/`run`/`plan`/`review`) | **output** — evidence-gated testing backbone |
| archetype **gate** + actionable steering (emits the `prove` one-liner) | **output** — turns the principle into a reflex |
| Core plumbing: `setup`, `where-am-i`, `help`, `intent`, `reset`, `classify`, hooks | load-bearing |

## CUT (fails all three — better native tool, more tokens, same output)

These are `Task(subagent)` rubric-wrappers: a checklist the agent already applies, behind a hop that costs more tokens for the same result. **~42 commands + the agents that exist only as their dispatch targets.**

| Domain | Cut | Note |
|---|---|---|
| engineering | `debug`, `plan`, `arch`, `review`, `docs` | `debug` duplicates `superpowers:systematic-debugging`; rest are rubric hops. Rescue R1–R6 as an optional skill-ref. |
| platform | `compliance`, `audit`, `incident`, `health`, `traces`, `actions`, `gh`, `infra` | keep `security` + `toolchain`. Rescue the SOC2/HIPAA audit checklist as a skill-ref. |
| product | **all 12** (`a11y`,`ux`,`ux-review`,`elicit`,`strategy`,`mockup`,`screenshot`,`analyze`,`synthesize`,`listen`,`align`,`acceptance`) | pure prompt-scaffolds, no engine, no UI target. Cleanest cut. Rescue `acceptance --scenarios` only if the wicked-testing tie-in is wanted. |
| data | `analyze`, `data`, `pipeline`, `ml` | keep `ontology`. |
| delivery | `experiment`, `report`, `rollout`, `setup` | document templates; `process-health` already deleted. Domain effectively retired. |
| agentic | `review`, `audit`, `design`, `frameworks` | scripts emit false signals; rubrics good but native. Rescue the T&S 8-layer as a skill-ref. |
| jam | `quick`, `perspectives` (single-model role-play); `thinking`/`transcript`/`persona` (retrieval utils) | keep `council`/`brainstorm`/`revisit`. |
| persona | `define`, `submit` | thin (define can't set the rich fields). Keep `as`/`list`. |
| smaht | `propose-skills` (weak), `state` (half-dead) | keep `briefing`; `events-import` is a one-time util (keep or archive). |

**Agents:** the domain agents (56 total) that exist *only* to back a cut command go with it. Keep the agents behind KEEP features (`qe:semantic-reviewer`, the jam facilitators/council, the persona built-ins, `crew:{implementer,researcher,reviewer}` as generic, the security/data-ontology backers).

## Rubric rescue (before deleting)

A few rubrics are genuinely good and worth keeping — but as **inline `refs/` loaded on demand**, not as dispatch commands: security CWE table, the agentic T&S 8-layer, the SOC2/HIPAA audit checklist, engineering R1–R6. One small "rescue" step moves these to `skills/*/refs/` so the knowledge survives the command's deletion.

## Estimated impact

- Commands: **94 → ~45** (cut ~42 + 2 already removed).
- Agents: **56 → ~20** (cut the dispatch-only targets).
- Net: the first **net-negative** pass — likely **thousands of lines + dozens of files removed**, and the surface finally matches the "thin, high-value toolkit" the agent actually reaches for.

## Phased execution (each phase = one worktree PR, parallelizable, suite-gated)

0. ✅ Remove dead commands (`crew:archive`, `delivery:process-health`).
1. **Rubric rescue** — move the ~4 keepable rubrics to `skills/*/refs/` (so nothing valuable is lost in the cut).
2. **product** domain cut (12 commands + agents) — the cleanest, do first as the pattern.
3. **delivery** + **agentic** cuts.
4. **engineering** + **platform** rubric-wrapper cuts (keep security/toolchain).
5. **data** (keep ontology) + **jam**/`persona`/`smaht` trims.
6. Agent sweep — delete now-orphaned dispatch-only agents; update `help.md`/`components.json`/`docs/domains.md`.
7. Update CLAUDE.md/README to reflect the leaner surface.

Each phase is reversible (git), suite-gated, and PR'd for review before the next.
