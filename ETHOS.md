# ETHOS

> **What this is.** A single-page identity for wicked-garden — what we believe, what we refuse, what we optimize for. `CLAUDE.md` tells you *how* the system works. This tells you *why*.

---

## What we believe

**Project shape determines ceremony.** A typo fix and a multi-repo schema migration are not the same project. Forcing one fixed sequence on both wastes the small one and under-protects the large one. Adaptive rigor is the point, not an optional setting.

**Quality pressure must be structural, not delegated to willpower.** Reviews skipped under deadline pressure are gates that didn't exist. Hard enforcement, signed dispatch logs, and append-only audit trails are not bureaucracy — they're how good intentions survive a Friday afternoon.

**Knowledge compounds across sessions or it isn't knowledge.** If a decision, gotcha, or pattern lives only in the current chat, it dies with the chat. Every memorable thing belongs in a tier-appropriate memory store with confidence and decay rules. The brain is the difference between learning once and learning every time.

**Native primitives over bespoke abstractions.** Claude Code's `TaskCreate`, `Skill`, `Agent`, hooks, and slash commands are the surface. We extend them — we don't replace them. A task with metadata is more durable than a custom kanban; an agent with a frontmatter description is more discoverable than a registry call.

**Local-first, graceful degradation, always works standalone.** Optional integrations enhance, they never gate. wicked-brain offline? The plugin still ships verdicts. wicked-bus down? The hooks still fire. If a feature requires an external dependency to function at all, it isn't a feature — it's a coupling bug.

**Cross-platform is non-negotiable.** macOS, Linux, Windows (Git Bash, WSL, native). Bare `python3` doesn't exist on Windows; bare `/tmp` doesn't exist on Windows; the shim and `${TMPDIR:-/tmp}` exist for a reason. If a contributor adds shell that breaks on Windows, the contribution is incomplete.

**Honest verdicts beat green dashboards.** A FAIL that surfaces a real bug is worth more than a PASS that masked it. Bot reviews catch what self-review can't. Independent reviewers exist because authors cannot review their own work credibly.

---

## What we refuse

**We do not require one fixed sequence of phases.** Other plugins ship a single rigid pipeline. The facilitator scores nine factors, detects one of seven archetypes, and picks phases per project. A typo and a migration get appropriately-scaled rigor — not the same rigor.

**We do not gate via heuristics that ignore project shape.** A 0.85 score threshold means nothing if the rubric reading the project is the same one used for a docs-only PR and a database refactor. Per-archetype score bands replace one-size-fits-all thresholds.

**We do not require a custom toolchain to install.** Stdlib Python, sh-shim, JSON state files, SQLite for FTS — all present on the platforms we target. No npm-only paths, no compiled extensions, no proprietary registries.

**We do not silently degrade quality signals.** When the semantic reviewer is unavailable we say so as an `info` finding — we don't pretend it ran clean. When a panel reviewer fails to respond, the gate stays `pending` — never silently approved.

**We do not let vendors land regressions in the name of cleanup.** Five legitimate skill rewrites bundled with three frontmatter regressions and a vendor-CI hook is not a contribution worth merging. Reject the bundle, salvage the wins in-house.

---

## What we optimize for

**Time to first useful gate verdict — minutes, not hours.** A reviewer who waits an hour for a verdict has lost flow before they read it. Targets: under 5 min for minimal rigor, under 30 min for full rigor, with parallel dispatch where the panel allows.

**Cross-platform install with zero compiled toolchain.** Anyone with `python3` (or `python`, or `py -3` on Windows) and `git` should have a working plugin in under 5 minutes. No build step, no vendor account, no API key required.

**Adaptive rigor: archetype-detected, factor-scored, project-shaped.** Every project starts with a 9-factor scoring pass and a 1-of-7 archetype detection. Both feed phase selection, specialist routing, gate evidence demands, and review depth. The output is rigor that fits, not rigor that defaults to maximum.

**Append-only audit trails that survive context resets.** Decisions, gate verdicts, dispatch records, and reeval addenda all land on disk in JSONL form. A new session can resume work without losing the chain of reasoning. State that lives only in chat history is state that doesn't exist.

**Honest measurement over vanity metrics.** PASS counts inflated by SKIPped scenarios are not coverage. MANUAL-ONLY is a distinct verdict from SKIP. A 70% real PASS rate beats a 95% inflated one because the second hides regressions.

---

## What this is not

**Not a prompt library.** Skills, agents, and commands are executable surfaces with frontmatter contracts and hard enforcement — not text snippets to copy.

**Not a fixed-sequence pipeline.** No two projects run the same phase chain. Phase selection is rubric-driven per project, not configured once per repo.

**Not a starter for learning Claude Code.** This is a working SDLC, not a tutorial. Bring some Claude Code fluency or expect a steep first hour.

**Not a single-language toolkit.** Cross-platform stdlib-only Python for the plumbing. Generators support Python, TypeScript, Java, Go, SQL out of the box; new languages plug in via wicked-patch's generator interface.

**Not closed.** Third-party plugins integrate via the [v9 drop-in contract](docs/v9/drop-in-plugin-contract.md). wicked-testing is the canonical example of a sibling plugin slotting into the unified workflow without forking.

---

## How to read the rest

- **`CLAUDE.md`** — operational guidance. How the surfaces compose, what the hooks enforce, where state lives.
- **`README.md`** — what to install, how to start, where to go next.
- **`docs/v9/`** — the contract surface for sibling plugins.
- **`scenarios/`** — acceptance tests; each scenario is an executable assertion of intended behavior.

If you can quote one sentence from this page after reading it once, the document worked. If you can quote three, we won.
