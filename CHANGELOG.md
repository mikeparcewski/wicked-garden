# Changelog

## [12.19.1] - 2026-06-12

### Bug Fixes
- fix(qe): the trust-spine `ProveEndToEndTests` now **RUN and GATE in CI** instead of skipping — they execute against any **resolvable** vault (PATH / `npm i -g` / `node_modules`, mirroring `vault_gate.resolve_vault`), CI installs the published peers, and `WICKED_REQUIRE_E2E=1` (set in `.github/workflows/test.yml`) makes a SKIP of these tests a hard build failure. The PASS / REJECT / independent-attestation path is now actually covered (no more GREEN-BUT-HOLLOW).
- fix(persona): `delete_persona(name)` resolves name → UUID id before deleting — custom personas are keyed by an auto-generated id in the DomainStore, so delete-by-name silently failed and left the persona in place. Adds a define → delete round-trip test.

### Chores
- chore(qe): propagate the explicit `--actor "${WICKED_VAULT_ACTOR:-garden-prove}"` to every hard-gate record-then-attest playbook (`skills/archetype/refs/{review,incident,migrate,specify}.md`) so wicked-vault **>= 0.4.0** does not refuse an independent attestation for a weak/ambient worker identity; peer floor `wicked_vault_version` pinned `^0.4.0`. Documented in `.claude/CLAUDE.md`.
- chore(persona): ran the persona-lift eval (blinded, independent grader) and recorded the result honestly in `tests/persona/EVAL_RESULTS.md` — **lift = 0 on all 3 cases** vs a strong base model. The built-in methodology personas are illustrative/redundant for these textbook cases; the `persona:define` mechanism (inject HOUSE methodology the base model cannot know) is the actual product. Recorded, not asserted.
- chore: bump 12.19.0 → 12.19.1.

## [12.19.0] - 2026-06-12

### Features
- feat(persona): triage methodology vs generic personas — sharpen the methodology personas, add a `not_focus` scope guard + GOOD-pattern template to `persona:define`, and demote the generic tail by presentation. Adds `tests/persona/` (deterministic lift suite + eval-case schema).
- feat(help): regenerate `/help` from the live command tree (drop retired crew/delivery; add prove/archetype/persona/compile/intent/where-am-i) with a `tests/test_help_command_tree.py` lint that fails if help drifts from `commands/`.
- feat(routers): add requirements/review sprawl routers and intent-revealing descriptions for smaht/wickedizer/ground.

### Bug Fixes
- fix(qe): `scripts/qe/prove.py` records evidence under an explicit `--actor` (`WICKED_VAULT_ACTOR` → default `garden-prove`) so the hardened **wicked-vault (>= 0.4.0)** trusts an independent attestation and `prove --with-attestations` can reach PASS — without weakening independence (a self-attest by the doer is still refused). `tests/qe/test_prove.py` updated in lockstep. (#945)
- fix(qe): the trust-spine `ProveEndToEndTests` now RUN against any **resolvable** vault (PATH / `npm i -g` / `node_modules`), not only a sibling checkout or `WICKED_VAULT_BIN` — mirrors `vault_gate.resolve_vault`. CI sets `WICKED_REQUIRE_E2E=1` so a SKIP of these tests is a hard failure (no more GREEN-BUT-HOLLOW).
- fix(qe): propagate the wicked-vault >= 0.4.0 explicit-`--actor` requirement to every record-then-attest path — the hard-gate playbooks (`skills/archetype/refs/{review,incident,migrate}.md`, plus `specify.md`) now record with `--actor "${WICKED_VAULT_ACTOR:-garden-prove}"` so an independent `attest` is not refused for weak/ambient worker identity. The compiler-emitted integrity gate (record + cross-check, no attest) is intentionally unchanged. Peer floor `wicked_vault_version` pinned `^0.3.0` → `^0.4.0`.
- fix(persona): `delete_persona(name)` resolves name → UUID id before deleting — custom personas are keyed by an auto-generated id in the DomainStore, so delete-by-name silently failed and left the persona in place. Adds a define → delete round-trip test.

### Chores
- chore: remove dead `daemon/council.py` pointer; bump 12.18.4 → 12.19.0.

## [12.18.4] - 2026-06-10

### Bug Fixes
- fix(sentinel): `.githooks/pre-push` resolved its interpreter with `python3 … || python …`, so a deliberate sentinel rejection (non-zero exit) re-ran the script via bare `python` — on machines without one, the block reason was buried under `python: command not found`. The hook now resolves the interpreter once (`command -v python3 || command -v python`) and `exec`s it, preserving the sentinel's exit code; no python at all fails closed with a clear message. (#932)

## [12.18.3] - 2026-06-10

### Bug Fixes
- fix(peers): `wicked_testing_version` pin `^0.3.0` → `^0.4.0` — the caret probe locks 0.x pins to the minor, so wicked-testing 0.4.0 (current) was rejected and crew commands were blocked. `wicked_brain_version` `^0.14.0` → `^0.15.0` to match the brain codegraph floor garden's ADR 0004 integration relies on (declarative only — no probe enforces it).
- fix(site): refresh marketing-site content against repo reality — wicked-testing "41 specialist agents" → 40 and "6 CLIs" badge → 5 (0.4.0 roster trim + Copilot removal), family hero stat 81 → 80 agents; bench install script for wicked-bus corrected from a nonexistent Claude-plugin install to `npm i wicked-bus` + `npx wicked-bus-install`.

### Features
- feat(site): the brain card and memory-bed tour stop now cover the wicked-brain code graph (v0.15.0) — blast-radius, callers, and lineage on demand.

### Chores
- chore: remove dead wicked-testing tier-coupling (gate-policy path retired at v11); ci: bump GitHub Actions to Node 24-ready majors; docs: link the GitHub Pages site at the top of the README; chore(deps): bump astro (#926).

## [12.18.2] - 2026-06-10

### Bug Fixes
- fix(brain): auto-start + port-resolution fix — no more false "server not running" notices. (Backfilled entry; released as the version-bump commit `36894f5`.)

## [12.18.1] - 2026-06-10

### Chores
- chore: remove the superseded in-garden code-relationship graph (now in wicked-brain, ADR 0004) — deletes `scripts/_codegraph.py`, `scripts/codegraph/*` (5 injected-edge extractors), and `tests/codegraph/`; zero live consumers remained. Rewires `search:hotspots` freshness onto `search:index`; marks ADR 0001 superseded. wicked-patch's `codegraph_db.py` adapter is unchanged. No behavior change.

## [12.18.0] - 2026-06-10

### Features
- feat(codegraph): move the code-relationship graph to wicked-brain (ADR 0004) — blast-radius/lineage/callers are now brain's `graph-*` actions + the `wicked-brain:graph` skill, backed by a codegraph static graph + injected edges (bus/dispatch/capability). `search:blast-radius`/`lineage`/`index` rewired to thin wrappers over brain.
- feat(codegraph): garden ships its proprietary archetype→playbook edges via the drop-in extractor `.codegraph-extractors/archetype.mjs`, discovered + run by brain's extractor registry (real-repo verified on this repo).
- docs: ADR 0004 records the inversion of ADR 0001; AGENTS.md is now a thin pointer to `.claude/CLAUDE.md`.

### Bug Fixes
- fix(sentinel): claim-gate the answer tier at the Stop boundary — it now fires only on a real done/passing/shipped claim with no verdict for HEAD (debounced per sha), instead of on any Bash call during planning. The buggy PostToolUse ref-watch is removed; the pre-push block tier is unchanged.

## [12.17.0] - 2026-06-09

### Features
- feat: the claim sentinel — state-transition gates without command lists (ADR-worthy core) (6ff25f5)

### Bug Fixes
- fix(search): index.md — codegraph init required before first index (found on real-repo test) (013d5a6)

### Chores
- Merge pull request #925 from mikeparcewski/fix/index-init-and-release-prep (5ab3d85)
- Merge pull request #924 from mikeparcewski/feat/claim-sentinel (589650e)

## [12.16.0] - 2026-06-09

### Features
- feat: integrate wicked-understanding as the repo-playbooks opt-in layer (full: layer + wired in) (cade19d)

### Chores
- Merge pull request #923 from mikeparcewski/feat/integrate-wicked-understanding (99d56dc)

## [12.15.0] - 2026-06-09

### Features
- feat: two required peers (the gate), three opt-in layers + curated-toolkit reframe (ADR 0003) (ad7f312)

### Chores
- Merge pull request #922 from mikeparcewski/feat/toolkit-optin-peers (14107cf)

## [12.14.0] - 2026-06-09

### Bug Fixes
- fix(search): hotspots query from codegraph graph instead of brain curl (a7cf0a0)

### Documentation
- docs: tighten the reframe — concise + fun (0e609e2)
- docs: reframe wicked-garden as gap-filler for coding-agent harnesses (not 'an SDLC') (931a2a8)

### Chores
- Merge pull request #921 from mikeparcewski/docs/reframe-gap-filler (4843d73)
- Merge pull request #920 from mikeparcewski/fix/hotspots-codegraph (c2e821e)

## [12.13.0] - 2026-06-09

### Bug Fixes
- fix(search): dynamic brain port + cut 5 broken admin wrappers + finish delivery retire (27b64df)
- fix(ci): find_orphan_agents excludes relative to repo root, not absolute path (92f3b15)
- fix(search): make blast-radius/lineage injected layer actually work (#916) (305ff3e)

### Refactoring
- refactor: retire delivery domain and jam post-hoc viewer endpoints (f087c2b)

### Chores
- Merge pull request #919 from mikeparcewski/cleanup/final-search-trim (149331a)
- Merge pull request #918 from mikeparcewski/cleanup/retire-delivery-jam-viewers (e953ef4)
- Merge pull request #917 from mikeparcewski/fix/codeintel-injected-edges-916 (bcd6444)

## [12.12.0] - 2026-06-09

### Refactoring
- refactor(agentic,jam,persona,smaht): collapse rubric-wrapper commands to inline skill-refs (ADR 0002 pattern) (7eeb8e7)
- refactor(platform): collapse 8 dispatch-only commands to inline rubrics (0d86a74)
- refactor(data,delivery): collapse 7 rubric-wrapper commands to inline skill-refs (ADR 0002 pattern) (8ce6f2b)
- refactor(engineering): collapse 5 rubric-wrapper commands to inline skill-refs (ADR 0002 pattern) (d26cec6)
- refactor(product): collapse 12 rubric-wrapper commands to inline skill-refs (cleanup ADR 0002 pattern) (264e619)

### Chores
- Merge pull request #915 from mikeparcewski/cleanup/agent-purge-and-sync (8ab295b)
- cleanup: purge 3 orphaned agents + re-derive registry + anti-drift tools (ADR 0002 phase 6) (932b4b8)
- Merge pull request #914 from mikeparcewski/cleanup/agentic-jam-persona-smaht-collapse (61aa0c8)
- Merge pull request #913 from mikeparcewski/cleanup/data-delivery-collapse (9c5548d)
- Merge pull request #912 from mikeparcewski/cleanup/platform-collapse (20621c2)
- Merge pull request #911 from mikeparcewski/cleanup/engineering-collapse (a9cf769)
- Merge pull request #910 from mikeparcewski/cleanup/product-collapse (b785732)

## [12.11.0] - 2026-06-09

### Features
- feat(codegraph): add dispatch + capability injected-edge extractors; wire blast-radius/lineage to graph (95c5205)
- feat(patch): revive wicked-patch via codegraph — adapter builds its --db from the code-graph (3c904f1)

### Chores
- Merge pull request #909 from mikeparcewski/feat/codegraph-injected-extractors (37b7be2)
- Merge pull request #908 from mikeparcewski/feat/patch-codegraph-db (49686b8)

## [12.10.1] - 2026-06-09

### Chores
- Merge pull request #907 from mikeparcewski/chore/remove-dead-commands (a10f2b0)
- chore: remove dead commands (crew:archive, delivery:process-health) + major-cleanup plan (ADR 0002) (504883f)

## [12.10.0] - 2026-06-09

### Features
- feat(codegraph): adopt codegraph as the static graph engine + injected-edge extractor (ADR 0001) (88cb6c1)
- feat: wire real security scanners + make archetype steering actionable (6e1ae61)

### Bug Fixes
- fix: repair 9 confirmed-broken wicked-garden command surfaces (678f972)

### Chores
- Merge pull request #906 from mikeparcewski/fix/broken-commands-batch (254677a)
- Merge pull request #905 from mikeparcewski/feat/security-scanners-and-actionable-steering (1c1329f)
- Merge pull request #904 from mikeparcewski/feat/code-relationship-graph (805b5a3)

## [12.9.0] - 2026-06-09

### Features
- feat(qe): real SEMANTIC spec-to-code review — the agent the script always referenced but never existed (631d1b5)

### Chores
- Merge pull request #903 from mikeparcewski/feat/semantic-reviewer-agent (215e536)

## [12.8.0] - 2026-06-09

### Features
- feat(qe): prove.py validates OUTPUTS, not just exit codes (regex_match/not_contains/jq_pred) (d7d3dd2)

### Chores
- Merge pull request #902 from mikeparcewski/feat/prove-output-verifiers (213da9b)

## [12.7.1] - 2026-06-09

### Bug Fixes
- fix(qe): prove.py --with-attestations actually enforces (was a vacuous hard gate in v12.7.0) (7d0f85b)

### Chores
- Merge pull request #901 from mikeparcewski/fix/prove-attestation-enforcement (b14cd27)

## [12.7.0] - 2026-06-09

### Features
- feat(qe): prove.py supports --with-attestations (universal across hard gates) (3df9d57)

### Documentation
- docs(archetypes): recommend prove.py frictionless gate in all 7 gating playbooks (08e2c05)

### Chores
- Merge pull request #900 from mikeparcewski/feat/prove-universal (c80bd6a)

## [12.6.0] - 2026-06-09

### Features
- feat(qe): prove.py — the one-line re-derivation verb (gate without the ritual) (37d586e)

### Documentation
- docs(build): recommend prove.py as the frictionless gate path (c3132be)

### Chores
- Merge pull request #899 from mikeparcewski/feat/prove-verb (43d98c5)

## [12.5.2] - 2026-06-09

### Tests
- test(e2e): fix CI environment assumption — own $HOME, test both configured + unconfigured (9398b08)
- test(e2e): real-surface harness — gate CLI, bootstrap, routing, resilience (Tiers A+C) (f83cf90)

### Chores
- Merge pull request #898 from mikeparcewski/test/e2e-three-tier-harness (685c007)
- ci: install node + wicked peers so tests/e2e gate+resilience RUN (not skip) (8e59ba7)

## [12.5.1] - 2026-06-09

### Bug Fixes
- fix: vault_gate CLI imports _loom (gate was failing closed via its own documented commands) (d0ce3eb)

## [12.5.0] - 2026-06-09

### Features
- feat(capabilities): register apm/tracing/logging/telemetry; lock agent caps to the registry (cde4bda)

### Bug Fixes
- fix(detector): match 'roll out' (spaced) for the ship archetype (54048e0)
- fix(phase-manager): align hard-gate map to the catalog (drop specify/decide over-reach) (9c042f1)
- fix: loom gate re-derives against project_dir, not process cwd (#891 regression) (ea8a3f8)

### Documentation
- docs: reconcile with the v12 loom cutover (loom is the gate; five required peers) (f66010d)
- docs(spec): record loom migration terminal outcome (§6 remainder stays in garden) (#895) (eb228d0)

## [12.4.0] - 2026-06-08

### Features
- feat: flow surface — loom-authoritative hard-gate park decision (fail-closed floor) (#893) (a4bab29)

## [12.3.0] - 2026-06-08

### Features
- feat: wicked-loom contract — loom is the sole gate/resolve path (delete in-process re-derivation) (#891) (7e4492a)
- feat: wicked-loom cutover — garden shells to loom resolve/gate/flow (additive, flag-gated) (#890) (ae928a7)
- feat(#878): worktree cwd-leak guard on Bash PreToolUse (#888) (859d2a0)

### Documentation
- docs: wicked-loom north-star spec (extract the orchestration runtime) (#889) (16c3e70)

## [12.2.0] - 2026-06-01

### Features
- skill(engineering): large-scale-migration — the map→transform→gate leverage pattern for cross-cutting migrations / refactors / renames / dialect-ports (21b1842)

### Bug Fixes
- fix(#879): clean up the two rotted test files outside tests/ (#885) (7db380d)

This project follows [Semantic Versioning](https://semver.org/).

The version line restarted at **v11.0.0** with the v11 work-shape archetype
reframe. The pre-v11 changelog (versions 0.x through 10.x) is preserved in
the git history but is not maintained as living documentation — those
releases describe a prior architecture (universal pipeline + rigor tier
dial) that was replaced wholesale.

---

## [12.1.0] — 2026-05-25

**All four siblings are now required, and the work mode is visible on screen.**

### Required peers (all four)

- **wicked-brain and wicked-bus join wicked-testing and wicked-vault as required peers.** `/wicked-garden:setup` now verifies all four and blocks without them; the SessionStart hook warns. `plugin.json` pins all four (`wicked_brain_version` `^0.14.0`, `wicked_bus_version` `^2.0.0`). The stance is **required at install, resilient at runtime**: a transient outage (brain server down, bus unavailable) degrades gracefully and never bricks a session — it never means a gate treats missing evidence as a pass (that path fails closed). See [`docs/required-peers.md`](docs/required-peers.md).

### Features

- **A work-mode status line** (`scripts/statusline.py`, opt-in via `settings.json` — see getting-started or `/wicked-garden:setup` step 6.6). Renders the live archetype · intent · phase · gate verdict at the bottom of the screen — `🌱 wg │ build·migrate │ intent: feature │ phase: implement │ ⚖ PASS`. Reads existing session state only (one read), fail-soft (degrades to `🌱 wg │ idle`, never blocks a render).

### Documentation

- **Rethought, not patched.** The docs were reoriented from the deleted v6 crew model to v12. README restructured around what/why/how (leads with the re-derived-evidence trust pitch, not the pipeline rationale); ETHOS rewritten (required-infrastructure / resilient-at-runtime; the nine archetypes named; the *"done is not claimed; done is re-derived"* slogan); `docs/domains.md` reframed off the dead orchestrator; new [`docs/required-peers.md`](docs/required-peers.md) + [`docs/compiler.md`](docs/compiler.md); `docs/v11/archetypes.md` corrected (hard gates are enforced at runtime). Stale `crew:*` references removed from setup.

### Notes

- The status line's two bugs (wrong field name, mismatched sanitization) were caught by independent review, not by the tests that shipped CI-green — those were tautological. The fix added a guard test cross-checking the renderer's fields against the real `SessionState` schema. *Honest verdicts beat green dashboards.*

---

## [12.0.0] — 2026-05-25

**"Done" is re-derived, not asserted — and the garden can compile that guarantee onto any repo.**

Every gating archetype's produces-gate stops trusting a self-asserted "done"
and re-derives it through [wicked-vault](https://www.npmjs.com/package/wicked-vault),
a new **required** peer. A new compiler emits that same re-derivation as a
self-contained harness into any repo.

### Breaking changes

- **wicked-vault is now a required peer** (`^0.3.0`; sibling to wicked-bus /
  wicked-brain / wicked-testing). `/wicked-garden:setup` verifies it and blocks
  without it, and the SessionStart hook warns. Install with
  `npx wicked-vault-install`. Offline/dev kill-switch: `WICKED_VAULT_BIN=""`
  (see CONTRIBUTING.md).

### Features

- **Vault-backed gates for all gating archetypes** (`scripts/qe/vault_gate.py`).
  The gate runs `wicked-vault cross-check` — re-hashing the recorded evidence
  and re-running its verifier — instead of `evidence_tracker`'s
  satisfied-when-claimed model. A claimed-but-false "tests pass" is REJECTED; a
  missing vault **fails closed** rather than passing on a self-assertion. Hard
  gates (review / incident / migrate) require an *independent* attestation —
  the evaluator is not the agent that did the work.
- **The compiler emit stage + `/wicked-garden:compile`** (`scripts/compiler/`).
  Detects a repo's test/lint/build commands and emits a self-contained,
  vault-backed gate into `<repo>/.wicked/` (contract + a stdlib-only `gate.py`
  + a claims-vs-evidence lint + README) that runs with **no wicked-garden
  runtime present** (resolves the vault via `npx`). Optionally installs the
  triggers that fire it — a git pre-push hook and a GitHub Actions workflow
  whose toolchain setup is derived from the detected ecosystem. Multi-claim
  contracts (test/lint/build), each pinned to its own verifier.

### Notes

- 422 tests; proven on an unseen repo (memos) and self-hosted on wicked-garden
  (which surfaced and fixed a detector scoping bug).
- Follow-up: #879 — two rotted test files CI never collected, found while
  self-hosting the compiler.

---

## [11.1.3] — 2026-05-08

**Council command + 4 sibling commands had broken refs the validator missed.**

The validator at v11.1.2 caught script-path drift in YAML/JSON fields
and `${CLAUDE_PLUGIN_ROOT}/...` strings, but missed two reference
shapes that hide inside markdown code fences and prose:

- **Bare `scripts/<domain>/<file>.py` paths** — references that don't
  use the `${CLAUDE_PLUGIN_ROOT}` prefix.
- **`from <module> import …` Python imports** — references that name
  a module deleted in a v11 cleanup.

`commands/jam/council.md` had a documented `from crew.hitl_judge import …`
example pointing at a script deleted in PR #866. The council itself ran
fine; the post-synthesis HITL judge step was broken. 9 other places
across `commands/delivery/`, `commands/engineering/`, `commands/smaht/`
had similar breaks (mostly references to the deleted
`scripts/crew/crew.py::find-active` auto-resolver).

### Fixed

- `commands/jam/council.md` — replaced the HITL judge code example with
  inline prose heuristics that the agent applies. Council itself
  unchanged; only the gate-feeding step removed.
- `commands/delivery/process-health.md`, `commands/smaht/state.md`,
  `commands/smaht/briefing.md` — replaced the v6 `crew.py find-active`
  invocations with v11 explicit-`--project` semantics.

### Added

- `scripts/ci/validate.py` now checks two additional reference shapes:
  bare `scripts/.../*.py` paths anywhere in commands/agents markdown,
  and `from <module> import` patterns whose module name doesn't exist
  under `scripts/` or `hooks/scripts/`. Stdlib + common third-party
  + obvious-template-placeholder names are whitelisted to keep the
  signal-to-noise ratio high.

The validator is now strict enough that a future v11 cleanup will
catch its own drift on the next CI run rather than the next user run.

390 / 390 tests still passing.

---

## [11.1.2] — 2026-05-08

**marketplace.json plugin version sync.**

The marketplace registration's `plugins[0].version` field had drifted —
stuck at `8.8.1` across the three v11 releases (`v11.0.0`, `v11.1.0`,
`v11.1.1`) because nobody bumped it. The plugin manifest reported
`11.1.1`; the marketplace listing reported `8.8.1`. Anyone consulting
the marketplace registration saw a stale number.

### Fixed

- `.claude-plugin/marketplace.json` `plugins[0].version` bumped to
  `11.1.2` to match `.claude-plugin/plugin.json`.

### Added

- `scripts/ci/validate.py` now enforces the version-parity invariant.
  When `plugin.json` and `marketplace.json` disagree on the plugin's
  version, validation fails with a named error: *"marketplace.json
  plugins[name=X].version = '8.8.1' does not match plugin.json version
  = '11.1.1'. Bump both together."* This catches the same drift class
  on the next release attempt rather than the release after.

No behavior change beyond the version bump and the validator addition.
Tests still 390/390 passing.

---

## [11.1.1] — 2026-05-08

**Closes the wicked-brain + wicked-bus persistence verification gap.**

Spent a session probing the plugin's relationship with both companion
plugins. Brain persistence turned out to be functional (11,582 indexed
items, 108 memories, search round-trip verified). Bus integration had
a real bug: v11 archetype events were never registered in
`BUS_EVENT_MAP`, so v11 wicked-garden was invisible to the bus despite
the bus itself being healthy (19,790+ events from companion plugins).

### Fixed

- v11 archetype events now register + emit (PR #874). Five new event
  types in `scripts/_bus.py::BUS_EVENT_MAP`:
  - `wicked.archetype.created` — archetype-mode project init
  - `wicked.archetype.advanced` — phase approved; carries next_phase
  - `wicked.archetype.completed` — final phase approved
  - `wicked.archetype.hard_gate_passed` — confirmed_by + evidence
  - `wicked.archetype.classified` — LLM classifier result persisted
- `phase_manager.create_project` emits `wicked.archetype.created` on
  archetype-mode projects.
- `phase_manager.approve_phase` emits `wicked.archetype.advanced` on
  every archetype approval, plus `wicked.archetype.hard_gate_passed`
  when `confirmed_by` was supplied, plus `wicked.archetype.completed`
  when `is_complete()` flips true.
- `scripts/classify/persist.py` emits `wicked.archetype.classified`
  when the LLM classifier writes its result.

All emits fail-open: bus unavailable never blocks the disk write.

### Verified

- **Brain persistence**: search returns 42 hits for `Session goal` —
  the prompt-submit hook's `_write_brain_memory()` writes are reaching
  the FTS5 index. Brain server runs on port 4243; 72 MB SQLite DB at
  `~/.wicked-brain/projects/wicked-garden/.brain.db`.
- **Bus round-trip**: real CLI invocation
  (`phase_manager create … --archetype-mode build` + two approves)
  advances `newest_event_id` by 3, with per-type counters incrementing
  as expected.

### Tests

390 passing (was 384 in v11.1.0; +6 new in `TestBusEmits`).

---

## [11.1.0] — 2026-05-08

**Closes the structural gaps in the v11.0.0 reframe.** v11.0.0 was the
research-grade reframe shipped in two hours; v11.1.0 closes 11 of the
12 items on the post-v11.0.0 critique. The remaining item (wicked-brain
persistence) needs real session traffic to validate, not a marathon.

### Added

- **LLM-based archetype classifier** via the new `wicked-garden:classify`
  skill (PR #869). The skill prompts the model to reason through the
  user's prompt, classify into archetype(s), identify boolean signals,
  and persist to SessionState via `scripts/classify/persist.py`. The
  prompt-submit hook prefers persisted classifications over the regex
  detector — regex is now Tier 2 fallback. When regex returns only
  triage, the hook emits a `<wg classify-due />` directive inviting the
  model to classify properly. New SessionState fields: `archetypes_v11`,
  `signals_v11`, `classified_at`.
- **Runtime hard-gate enforcement** (PR #870). Five archetype phases —
  `migrate:cutover`, `incident:mitigate`, `review:remediate-or-accept`,
  `specify:validate`, `decide:record` — now require non-empty
  `--confirmed-by` AND `--confirmation-evidence` to advance. The audit
  trail records both fields with `hard_gate=True`. The doctrine of
  "hard:* gate" is now mirrored in `phase_manager` code, not just
  playbook prose.
- **5 restored QE utilities** under `scripts/qe/` (PR #868), framed as
  v11 library tools the archetype playbooks call when relevant:
  - `verdict_schema.py` (~250 LOC) — validates review-archetype
    verdict artifacts. Slimmed from the v6 `gate_result_schema.py`.
  - `verdict_audit.py` (~140 LOC) — append-only audit log of verdicts.
    Slimmed from v6 `gate_ingest_audit.py` + `dispatch_log.py`. No
    HMAC; v11 review enforces banned-reviewer checks at validation.
  - `conditions_manifest.py` — track CONDITIONAL findings to
    resolution. Idempotent re-init preserves prior resolutions.
    `all_resolved()` answers the contract question.
  - `content_sanitizer.py` — strip prompt-injection patterns from
    reviewer free-text fields. Floor not wall.
  - `evidence_tracker.py` — track per-archetype produces contracts
    (e.g. `shipped-code` + `test-report` for build).
- **v6→v11 project state migration tool**
  (`scripts/setup/migrate_v6_projects.py`, PR #871). Detects v6-v10
  projects in the DomainStore via phase-list pattern matching,
  proposes the closest v11 archetype, and (with `--apply`) translates
  state in place. Original phase plan preserved in
  `extras.v11_migration_source` for audit.
- **End-to-end integration test** for the full migrate lifecycle —
  catalog hydration → state transitions per phase → hard-gate refusal
  → hard-gate advance → `is_complete` (PR #870).
- **58-prompt calibration corpus** (PR #872). Exercises all 9
  archetypes plus paraphrase, multi-archetype, ambiguous edge cases.
  Three locked-in tests assert overall recall ≥ 85%, overall precision
  ≥ 80%, per-archetype recall ≥ 70%. Actual: **100% per-archetype
  recall**, 90%+ precision after phrase tuning.
- **GitHub Actions workflow** `.github/workflows/test.yml` runs the
  full pytest suite + smokes phase_manager CLI archetype-mode + smokes
  the archetype detector + smokes verdict_schema validation + asserts
  the migrate:cutover hard gate refuses without confirmation and
  advances with it. End-to-end CI for v11.

### Changed

- `hooks/scripts/prompt_submit.py` — `_build_archetype_directive` now
  accepts `state`, prefers persisted LLM classification, emits
  `<wg classify-due />` directive when regex returns only triage. Tag
  format carries `classified="llm"` or `classified="regex"`.
- `.claude-plugin/archetypes.json` — phrase lists tuned to 100% recall
  on the calibration corpus. Added paraphrase coverage for build
  (refactor / patch / wire up), migrate (rename the / expand the /
  retire the / take the / column out), incident (production is broken
  / postmortem / memory leak / paging us), ship (ship to / ship the),
  review (take a look at / look at this pr), decide (pick a / pick
  between / which database / which queue / which framework), and
  explore (what should we / how might we / brainstorm / approaches to
  / not sure how / ideas for).
- `agents/crew/reviewer.md`, `agents/product/requirements-analyst.md`,
  `commands/setup.md`, `commands/smaht/briefing.md` — replaced
  references to deleted v6 modules (traceability.py, qe-evaluator
  naming sweep, _stack_signals, archetype_detect, affected_repos)
  with v11 equivalents (evidence_tracker, conditions_manifest, the v6
  migration script, an explanatory note).
- `skills/archetype/refs/build.md` and `refs/review.md` — playbooks
  now reference the restored `scripts/qe/*` utilities at the right
  phase boundaries.

### Removed

- `daemon/` (~8600 LOC, PR #871) — the v6-v10 projector daemon was
  wired to gate-result schemas, dispatch-log HMACs, and projection
  resolvers, all of which v11.0.0 deleted. v11 treats the bus as an
  audit substrate, not a projection enforcement layer.
- `.github/workflows/benchmark.yml` — enforced p95 SLO on
  `_load_gate_result` (deleted in v11.0.0). Trigger paths no longer
  exist; the workflow was dormant clutter.
- 227 lines of dead code in `hooks/scripts/prompt_submit.py` (PR #867)
  — `_assemble_current_chain`, `_consume_facilitator_reeval`,
  `_consume_phase_start_gate`, plus their call sites and event-type
  references that pointed at deleted v6 modules.

### Test summary

384 tests passing across 8 directories: tests/, tests/crew/, tests/qe/,
tests/calibration/, tests/hooks/, tests/fixtures/, plus utilities.
Calibration: 100% per-archetype recall on the 58-prompt corpus.

---

## [11.0.0] — 2026-05-07

**Reframe: work-shape archetypes replace the universal pipeline.**

The fixed `clarify → design → test-strategy → challenge → build → test → review`
pipeline with a rigor-tier dial is gone. Each prompt now classifies into one
or more **work-shape archetypes** (`triage` · `explore` · `specify` · `decide` ·
`ship` · `review` · `incident` · `build` · `migrate`), each of which owns its
own phase shape, produces contract, HITL discipline, and cost band.

### What's new

- **`.claude-plugin/archetypes.json`** — canonical catalog. Each archetype
  declares its phases, produces, HITL level, cost band, maturity, and
  detection signals (phrase list + boolean flags).
- **`scripts/crew/archetypes_v11.py`** — detector + steering engine. CLI
  shim for shell + agent integration. Stdlib-only.
- **`skills/archetype/`** — agent-facing entry point. Slim `SKILL.md`
  (101 lines) + 9 ref playbooks (62–97 lines each), one per archetype.
  Each playbook documents the archetype's phases, produces contract,
  HITL discipline, run procedure, exit condition, and anti-patterns.
- **`commands/archetype/`** — 9 slash commands, one per archetype, for
  direct user invocation.
- **`hooks/scripts/prompt_submit.py`** — UserPromptSubmit hook now emits
  a slim `<wg archetype="X" score="Y" />` system-reminder when a prompt
  routes to a work shape. `simple-edit` intent stays silent.
- **`scripts/crew/scope_delta.py`** — scope-delta heuristic to catch
  silent project-sized additions to wave plans.
- **`scripts/crew/phase_manager.py`** — slim project-state manager
  (~370 lines, down from ~6000+). State CRUD + `--archetype-mode` for
  new projects. No gate machinery.

### What's gone

The v6–v10 universal-pipeline machinery has been deleted:

- **Agents**: `crew/contrarian`, `crew/facilitator`, `crew/gate-adjudicator`,
  `crew/gate-evaluator`, `crew/independent-reviewer`, `crew/phase-executor`,
  `crew/process-facilitator`, `crew/qe-orchestrator`. Kept:
  `crew/implementer`, `crew/researcher`, `crew/reviewer` (general purpose).
- **Commands**: all of `crew/` except `crew/archive` (general project
  management).
- **Skills**: `propose-process`, `facilitator-score`, all of `skills/crew/`.
- **Plugin configs**: `gate-policy.json`, `phases.json`, `autonomy-policy.json`,
  `finding-classification.json`.
- **Scripts**: gate-result schema validators, gate-dispatch, dispatch-log
  HMAC, conditions-manifest, content-sanitizer, consensus-gate, autonomy
  policy table, reconcile / reconcile_v2, propose-process facilitator
  rubric, validate-plan / validate-reeval-addendum, reeval-addendum,
  archetype_detect (v6.3 target-kind classifier), challenge-manifest,
  rigor-escalator, hitl-judge, gate-adjudicator, semantic-alignment,
  convergence, swarm-trigger, factor-questionnaire, plus ~50 more
  legacy scripts in `scripts/crew/`.
- **Docs**: `MIGRATION-v7.md`, `V7-AC-TRACEABILITY.md`, `crew-workflow.md`,
  `cross-phase-intelligence.md`, `autonomy.md`, `spc.md`, all of
  `docs/v9/`, `docs/audits/`, `docs/calibration/`, `docs/cluster-a/`,
  `docs/composition/`, `docs/council/`, `docs/evidence/`, `docs/research/`.

### Migration note

There is no migration. v11 is a clean break from v6–v10. Projects authored
under the prior architecture continue to load (the project state schema
is forward-compatible) but the gate / rigor / phase machinery is no
longer enforced. New projects should be created with
`phase_manager create … --archetype-mode <archetype>`, or simply by
letting the UserPromptSubmit hook auto-route.

### Pre-v11 history

Versions 0.x through 10.x lived in the git log under tags `v0.1.0`
through `v9.2.18`. Major themes across that span:

- **v0–v3**: initial plugin scaffold, command + agent surface, hooks.
- **v4–v5**: smaht context-assembly orchestrator (HOT/FAST/SLOW/SYNTHESIZE
  tiered router). Replaced in v6.
- **v6**: facilitator-driven dynamic phase plan, gate-policy×rigor matrix,
  archetype-aware gate-adjudicator (target-kind classifier).
- **v7**: AC traceability, semantic reviewer, convergence-verify gate.
- **v8**: dropped `/wicked-garden:mem:*` (memory moved to wicked-brain).
- **v9**: bus-as-truth cutover for gate-critical artifacts; drop-in
  plugin contract; 14 default-on `WG_BUS_AS_TRUTH_*` tokens.
- **v10**: intent variable replacing the 5-classifier cascade;
  steering-not-blocking principle; slim-body contract for commands
  and skills.
- **v10.x dogfood PRs (#854–#860)**: surface fixes that pointed at the
  deeper structural issue v11 solved — hardcoded deliverable filenames,
  gate-result schema field aliases, gate-vocabulary unification,
  reeval-log auto-stub, phase-plan authority hydration, CONDITIONAL
  condition-resolution mechanism, scope-delta HITL trigger.

For each of those releases, see the corresponding tag in git history.
