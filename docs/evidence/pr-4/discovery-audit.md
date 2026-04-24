# Discovery Audit — `wicked-garden:ground` passes its own conventions

**Skill audited**: `skills/ground/SKILL.md`
**Conventions applied**: `docs/v9/discovery-conventions.md`
**Date**: 2026-04-23

Self-application discipline: the keystone skill must pass the rules it
exemplifies. This doc is the proof.

---

## Rule 1: Trigger language ("Use when X")

**Check**: Does the description contain explicit trigger phrases matching how
Claude frames problems internally?

Frontmatter text:
```
Use when: getting mixed signals from the codebase, about to commit to a
non-obvious decision, prior decisions might exist for this exact problem,
or you want to verify an assumption before action.
```

Body `## When to use` section adds six concrete scenarios:
- "two things contradict each other"
- "want to know if it's been tried before"
- "avoid re-deriving what was deliberated"
- "gut feel needs grounding"
- "let me get my bearings"
- "wait, did we already decide this?"

**PASS** — Trigger language is in both the frontmatter (discovery surface) and
the body (execution context). The phrases match natural Claude internal
phrasing at the moment of uncertainty.

---

## Rule 2: Anti-trigger language ("NOT for Z")

**Check**: Does the description declare what the skill is NOT for, with named
alternatives?

Frontmatter text:
```
NOT for: routine "what does this code do" questions (use Read or Grep), broad
codebase exploration (use Agent(Explore)), or fetching specific symbols (use
wicked-brain:search directly).
```

Body `## When NOT to use` section mirrors and extends:
- "Routine 'what does this code do' questions — use Read or Grep, they're faster"
- "Broad codebase exploration without a specific question — use Agent(Explore)"
- "Fetching a specific symbol you already know exists — use wicked-brain:search directly"
- "During flow when you already have enough context — don't interrupt to re-ground"

**PASS** — Three anti-triggers in frontmatter, four in body. Each names the
alternative tool. The fourth body anti-trigger ("don't interrupt to re-ground")
is a behavioral guard against over-use — important for a "steer yourself" skill.

---

## Rule 3: No-wrapper test

**Check**: Does Bash + Grep + Read in three calls solve the same problem?

What `ground` does that native tools cannot in three calls:
1. **Parallel fan-out to brain + bus simultaneously** — a single Claude turn
   with three Skill calls is not achievable with three Read/Grep calls, which
   are serial
2. **Cross-source ranked synthesis** with a hard cap (5-10 signals) — Grep
   returns raw matches; brain:search returns a list; bus returns events. Ground
   synthesizes and caps
3. **Source-type annotation** — brain/memory vs brain/wiki vs bus/event is
   invisible to native tools; Ground surfaces it to steer follow-up depth
4. **Graceful degradation contract** — if brain is down, continue with bus;
   if both down, emit explicit fallback message rather than a tool error

Native path comparison:
- 3 native calls: Read(brain memory) + Grep(codebase) + Read(bus log)
- Result: 3 unranked, un-synthesized outputs with no cross-source deduplication
- Gap: no cap, no relevance ranking, no source-type annotation, no degradation contract

**PASS** — Ground provides value the native three-call path cannot replicate.

---

## Rule 4: Single-purpose, verb-first, scoped

**Check**: Single purpose? Verb-first description? Scoped (not a junk drawer)?

Name: `ground` — single noun, clear semantic (to ground oneself = to orient
before acting). Not `context-and-memory-and-bus-and-synthesis-helper`.

Description first line: "Pull deeper context from brain + bus when uncertain."
Verb: Pull. One sentence, one action.

Body sections: `When to use`, `When NOT to use`, `Mechanism`, `Implementation`,
`Graceful degradation`, `After grounding`. Each section has one job. There is
no branching based on args to three different workflows.

**PASS** — Single purpose (pull + rank + cap uncertain-state context). Verb-first.
Not a junk drawer.

---

## Rule 5: Progressive disclosure (SKILL.md ≤200 lines)

**Check**: Is SKILL.md under 200 lines? Does it leave depth for refs/?

Line count: **126 lines**.

The SKILL.md contains: frontmatter, header, When to use, When NOT to use,
Mechanism (6 steps), Implementation (5 steps with code blocks), Graceful
degradation, After grounding.

No refs/ directory needed: the protocol is simple enough that the full
implementation fits in 126 lines without exceeding the size limit. If the
tool call shapes change (e.g., bus query params evolve), `refs/` would be the
right place to expand — the SKILL.md body would stay stable.

**PASS** — 126 lines. Under the 200-line hard limit enforced by `/wg-check`.

---

## Unique-value test

**Question**: Does `ground` provide value Claude can't get from native tools or
another well-positioned skill?

| Alternative | Why `ground` is distinct |
|---|---|
| `wicked-brain:search` directly | ground adds bus fan-out, cross-source ranking, cap, and degradation contract. brain:search is one of the tools ground calls — not a substitute |
| `wicked-brain:query` directly | same as above — query is one call; ground is the orchestration layer that includes bus + synthesis |
| `wicked-bus:query` directly | bus-only; no brain context |
| `smaht:context` | context assembly for briefing a new subagent; different trigger (start of session vs moment of uncertainty mid-flow) |
| Grep + Read (3 calls) | no cross-source synthesis, no ranked cap, no bus events, no degradation contract |

**PASS** — Unique value confirmed.

---

## Overall verdict

| Rule | Result |
|---|---|
| R1: Trigger language | PASS |
| R2: Anti-trigger language | PASS |
| R3: No-wrapper test | PASS |
| R4: Single-purpose, verb-first, scoped | PASS |
| R5: Progressive disclosure ≤200 lines | PASS (126 lines) |
| Unique-value test | PASS |

**`wicked-garden:ground` passes all v9 discovery conventions.**

Self-application discipline confirmed. This skill can be cited as the canonical
exemplar in `docs/v9/discovery-conventions.md`.
