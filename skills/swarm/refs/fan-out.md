# Fan-out — the parallel implementer wave

Dispatch **N independent subagents in parallel**, one per unit of work
(repo / module / file / service). One message, multiple `Task` calls — that
is what makes it a swarm and not a loop.

Use `agents/crew/implementer.md` as the agent. It already encodes the rules
that matter here: parallel-when-independent dispatch, structured evidence in
every `TaskUpdate`, and the guardrails (never auto-proceed on deploys / deletes /
schema migrations). This ref adds the **per-unit brief** that scopes each one.

## When a unit is independent

A unit is safe to fan out in parallel when it:
- touches disjoint files from the other units,
- shares no mutable state with them, and
- has no producer→consumer ordering against them.

If two units edit the same file or one's output feeds another, either serialize
those two (and record a `serial_reason`) or merge them into one unit. Everything
else runs concurrently.

## The implementer brief template

Each subagent gets a **tight, self-contained** brief. It must not need the
orchestrator's context to do its job — everything it needs is in the brief or
discoverable from the unit itself.

```
You are the swarm implementer for unit: <unit-name> (<path / repo URL>).
You run in parallel with sibling implementers on other units. You share no
state with them. Do not touch anything outside this unit.

SCRATCH DIR: <scratch>/<unit-name>/   (create it; write all detail here)

1. GROUND IN THE UNIT'S OWN RULES FIRST.
   Read this unit's own conventions before changing anything: its
   AGENTS.md / CLAUDE.md / CONTRIBUTING, lint+test config, and any
   wicked-understanding repo playbook (add-feature / fix-bug / write-tests).
   Follow THIS unit's method, not a generic one.

2. IMPACT ANALYSIS (blast radius) BEFORE you change anything.
   What does this change touch? What depends on it? Use
   /wicked-garden:search:blast-radius (or grep the call sites) and the
   deliberate lens ("map the blast radius: what else shares this root cause").
   Write blast-radius.md to your scratch dir. The blast radius SETS YOUR
   TEST BAR (step 4) — a wide radius demands more verification.

3. IMPLEMENT — in scope only.
   - Make the smallest change that satisfies the goal.
   - In-scope tech-debt cleanup ONLY: fix debt you are already editing.
     NO opportunistic refactor sprawl — drift is the #1 cause of inflated
     cycles (same rule as the build archetype's implement phase).
   - Fix ROOT causes, not symptoms.

4. FUNCTIONALLY TEST, proportional to blast radius.
   | blast radius | test bar |
   |--------------|----------|
   | low (leaf, reversible) | one targeted test that exercises the change |
   | medium | unit tests + 1-2 integration |
   | high (shared code, many callers) | unit + integration + an acceptance check |
   Run the unit's REAL test command. Capture exact command + output + exit code.

5. WRITE DETAILED ARTIFACTS TO DISK (not to your reply):
   <scratch>/<unit-name>/blast-radius.md, plan.md, diff.patch (or commit SHA),
   test-output.txt (verbatim, with exit code), assumptions.md.

6. RETURN A CONCISE SUMMARY (~150 words MAX). Include:
   - what changed (1-2 sentences) and the scope you held to,
   - the blast-radius verdict (low/medium/high),
   - the test command + PASS/FAIL + exit code,
   - the artifact paths,
   - the base commit SHA you started from (the verifier needs it),
   - anything you deferred (so it lands in the deferred log, not silently dropped).
   Do NOT paste diffs or raw logs into the summary — those are on disk.
```

## Why the brief is shaped this way

- **Self-contained** → the orchestrator's context stays lean; the subagent can
  run in an isolated worktree without back-and-forth.
- **Rules-first** → a unit's own conventions win over a generic house style;
  this is the difference between a change that merges and one that bounces.
- **Impact analysis before code** → you cannot pick the right test bar until you
  know the blast radius. This is the hinge that makes verification proportional.
- **In-scope cleanup only** → bounded debt repair without scope creep.
- **Detail to disk, ~150 words back** → the receipts are auditable and the
  verify wave reads the artifacts, not the implementer's prose.

## Isolation + commit hygiene

When implementers commit (each on its own branch — see `refs/ship-discipline.md`),
follow `wicked-garden:worktrees`: a subagent's "Commit SHA: abc1234" can be a
**dangling commit** that `git gc` will collect once its worktree is removed.
**Trust-but-verify every reported SHA** with the ancestry check before you treat
the work as landed. This matters double in a swarm because many agents commit
concurrently.

## Hand-off

When the wave returns, you have N concise summaries in context and N detailed
artifact sets on disk. Do **not** start verifying inline — dispatch the
**separate** verify wave (`refs/independent-verification.md`), handing each
verifier the unit's scratch dir + base commit SHA.
