# ETHOS

> **What this is.** A single-page identity for wicked-garden — what we believe, what we refuse, what we optimize for.
>
> Coding agents have become *harnesses* — they plan and execute well, and each has an opinionated way it wants to work. wicked-garden fills the gaps the harness can't fill on its own — proof instead of claims, relationships grep can't see, deterministic refactor, memory across sessions, a second opinion that isn't itself — without fighting how it already works. It reads the *shape* of the work to apply the right rigor, then gets out of the way. **Done is not claimed; done is re-derived.**
>
> `CLAUDE.md` tells you *how* the system works. This tells you *why*.

---

## What we believe

**Don't fight the harness; fill its gaps.** Modern coding agents already plan, parallelize, and execute — and each has a prescriptive way it wants to work. The worst thing a plugin can do is wrestle that. We add only what a planner-executor genuinely can't do on its own: re-derive "done" from evidence, surface relationships grep can't see, refactor deterministically across files, remember across sessions, and get a second opinion that isn't the same model arguing with itself. Everything the harness already does well, we leave to the harness.

**Project shape determines ceremony.** A typo fix and a multi-repo schema migration are not the same project. Each prompt classifies into one or more of nine **work-shape archetypes** — `triage`, `explore`, `specify`, `decide`, `build`, `review`, `ship`, `incident`, `migrate` — and each owns its own phase shape, produces contract, and human-in-the-loop (HITL) discipline. A typo and a migration get appropriately-scaled rigor — not the same rigor, and not the same shape.

**"Done" is re-derived, not asserted.** A gate does not go green because someone said so. Evidence is re-hashed and its verifier re-run through wicked-loom every time — which re-runs the verifier via wicked-vault underneath — a claimed-but-false "tests pass" is REJECTED, and a missing backend fails closed rather than passing on a self-assertion. The cheapest lie in software is a green checkmark with nothing behind it; we refuse to accept it.

**Quality pressure must be structural, not delegated to willpower.** Reviews skipped under deadline pressure are gates that didn't exist. So enforcement lives in code, not prose: hard gates refuse to advance at runtime, produces re-derive through wicked-loom (which re-runs the verifier via the vault), and the audit trail is append-only. Good intentions don't have to survive a Friday afternoon — the gates do.

**Knowledge compounds across sessions or it isn't knowledge.** If a decision, gotcha, or pattern lives only in the current chat, it dies with the chat. Every memorable thing belongs in a tier-appropriate memory store with confidence and decay rules. wicked-brain is the difference between learning once and learning every time.

**Native primitives over bespoke abstractions.** Claude Code's `TaskCreate`, `Skill`, `Agent`, hooks, and slash commands are the surface. We extend them — we don't replace them. A task with metadata is more durable than a custom kanban; an agent with a frontmatter description is more discoverable than a registry call.

**Required infrastructure, resilient at runtime.** wicked-garden stands on five siblings: **wicked-testing** (proves behavior), **wicked-vault** (the evidence backend that makes "done" re-derivable), **wicked-brain** (carries knowledge across sessions), **wicked-bus** (carries the audit trail), **wicked-loom** (the gate engine that re-derives produces through the vault). These are *required infrastructure*, not optional add-ons — the honest-evidence model does not work if any of them is merely nice-to-have, so `/wicked-garden:setup` verifies all five and blocks without them. But required-at-install is not brittle-at-runtime: a transient outage — brain server down, bus momentarily unavailable — degrades gracefully and never bricks a session. Graceful degradation means a session continues where it's *safe* to; it never means a gate pretends missing evidence is a pass — that path **fails closed**. We depend on our infrastructure; we don't crash with it.

**Cross-platform is non-negotiable.** macOS, Linux, Windows (Git Bash, WSL, native). Bare `python3` doesn't exist on Windows; bare `/tmp` doesn't exist on Windows; the shim and `${TMPDIR:-/tmp}` exist for a reason. If a contributor adds shell that breaks on Windows, the contribution is incomplete.

**Honest verdicts beat green dashboards.** A FAIL that surfaces a real bug is worth more than a PASS that masked it. Hard gates demand an *independent* judgment — the evaluator is not the agent that did the work — because authors cannot review their own work credibly.

---

## What we refuse

**We do not require one fixed sequence of phases.** No universal pipeline. A prompt routes to a *set* of work-shape archetypes, and each runs its own phases. We deliberately do not factor "common phases" — that's how the old universal pipeline emerged, and it forced every kind of work into the same shape.

**We do not let work grade its own "done".** Self-assessment is not evidence. A produces-gate re-derives the claim; a hard gate's verdict comes from an evaluator who is not the worker, recorded as a tamper-evident attestation. A "done" with no re-derivable backing is a fabrication, not a verdict.

**We do not silently degrade quality signals.** When the evidence backend isn't resolvable, the gate **fails closed** and says so — it never invents a pass. When a signal is missing, we surface it as a finding; we don't paper over it to keep a dashboard green.

**We do not hide our dependencies.** The five required peers are named, pinned, and checked at setup — not silent transitive surprises. If wicked-garden needs something to function, it says so up front and verifies it, rather than failing mysteriously three commands in.

**We do not let vendors land regressions in the name of cleanup.** Five legitimate skill rewrites bundled with three frontmatter regressions and a vendor-CI hook is not a contribution worth merging. Reject the bundle, salvage the wins in-house.

---

## What we optimize for

**A verdict you can trust on the first read.** A reviewer who can't trust the gate re-reads everything by hand, and flow is gone. We optimize for verdicts that are *re-derived* (recomputed, not cached) and *independent* (not self-graded) — trustworthy enough that the green means green.

**Archetype-shaped rigor.** The detector classifies *work shape*, and rigor follows the shape — not a global dial that defaults to maximum. A `triage` is negligible; a `migrate` cutover is a hard gate with a rollback proof. The output is rigor that fits the work, applied where it matters.

**Enforcement that travels.** `/wicked-garden:compile` emits a self-contained, vault-backed gate into any repo — one that re-derives the build's claims with **no wicked-garden runtime present**. We compile the *trigger* and the *enforcement*; we never compile the *tool*. The guarantee outlives the session that created it.

**Append-only audit trails that survive context resets.** Decisions, gate verdicts, and evidence all land on disk in append-only form. A new session resumes work without losing the chain of reasoning. State that lives only in chat history is state that doesn't exist.

**Honest measurement over vanity metrics.** PASS counts inflated by SKIPped scenarios are not coverage. MANUAL-ONLY is a distinct verdict from SKIP. A 70% real PASS rate beats a 95% inflated one, because the second hides regressions.

---

## What this is not

**Not a prompt library.** Skills, agents, and commands are executable surfaces with frontmatter contracts and runtime enforcement — not text snippets to copy.

**Not a fixed-sequence pipeline.** No two prompts run the same phase chain. Work shape is detected per prompt, not configured once per repo.

**Not a starter for learning Claude Code.** This is a working toolkit that rides on a real harness, not a beginner tutorial. Basic harness fluency makes the first hour productive rather than steep.

**Not a single-language toolkit.** Cross-platform stdlib-only Python for the plumbing. wicked-patch's generators support Python, TypeScript, Java, Go, SQL, Rust, Kotlin, C#, PHP, Ruby out of the box; new languages plug in via the generator interface.

**Not closed.** The five siblings (testing, vault, brain, bus, loom) are required peers, not forks — and the compiler emits a vault-backed harness any repo can adopt **without installing wicked-garden at all**. The plugin's relationship to other tools is "stand on, and hand off," not "absorb."

---

## How to read the rest

- **`CLAUDE.md`** — operational guidance. How the surfaces compose, what the gates enforce, where state lives.
- **`README.md`** — what to install, how to start, where to go next.
- **`docs/v11/archetypes.md`** — the design note: why the universal pipeline went away and what replaced it.
- **`docs/required-peers.md`** · **`docs/compiler.md`** — the five required siblings, and the compiler.
- **`scenarios/`** — acceptance tests; each scenario is an executable assertion of intended behavior.

If you can quote one sentence from this page after reading it once, the document worked. If you can quote three, we won.
