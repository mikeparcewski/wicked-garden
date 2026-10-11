---
name: wicked-garden-mem-capture
description: "Session-teardown memory capture: sweep the conversation for durable learnings (decisions with a reason, patterns, gotchas, preferences), keep only what passes the durability test, classify each onto the estate kind/tier vocabulary, and batch-write them to wicked-estate memory. Use when: dispatched by the wicked-garden-mem skill's capture action, at session end, before /clear or exit, or when the user says 'capture what we learned' / 'remember this session'."
metadata:
  role: worker
---

# Mem Capture Worker (session teardown)

This skill is designed to run as an isolated worker; when your harness cannot fork, run it inline and keep its output separate from the caller's.

You capture session learnings as **wicked-estate memories** before the
session ends (FOLD-3, Phase 5-S7 — the port of brain's session-teardown).
You run in a fork context: review the conversation, distill, and persist
through the mem backend. Estate owns everything after the write (salience,
decay, consolidation) — your job is *selection and distillation*, not
lifecycle.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Step 1 — sweep the conversation for learnings

Look for things the session *learned*, not things it *did*:

- **Decisions with a reason**: "chose X over Y because…"
- **Patterns / conventions**: "this always…", "the convention is…"
- **Gotchas**: "this broke because…", "don't X because…"
- **Preferences** the user stated: "always use…", "never do…"

## Step 2 — the durability test (every candidate must pass)

> Would this help a fresh session, on a different task, three months from
> now? It states the rule, why it holds, and when it applies.

Reject, and do not rephrase into something that sneaks past:

- progress and status: what you did, are doing or will do ("I'll retry",
  "going to try again", "shipped", "merged", "now green");
- versions, commit SHAs, PR / issue / run ids, PIDs, ports picked by hand,
  and anything dated ("today", "this morning");
- anything the repo, its CHANGELOG or the tracker already records.

The backend refuses the mechanical cases (ids, versions, SHAs, PIDs, "today",
first-person narration, bodies under 40 characters) with
`not a durable learning`. A refusal means the candidate failed the test:
drop it, unless it holds a real rule you can state without the moment.
If nothing passes, store nothing and say so. An empty capture is a valid
result, and the usual one.

## Step 3 — distill and classify

Write each survivor as 1–3 sentences (the rule, why it holds, when it
applies), then map it onto the estate vocabulary
(full table: `skills/mem/refs/scopes.md`):

| Finding | `kind` | tier (default) |
|---------|--------|----------------|
| decision, preference, gotcha, stable fact | `fact` | `semantic` |
| pattern, convention, how-to | `skill` | `procedural` |

Events ("X happened when Y") are not memories. Keep only the rule the event
taught, as a `fact`.

Add 2–5 `about` tags per memory (systems, components, topics mentioned) so
recall has hooks. Scope: leave the default (`project:<cwd-basename>`)
unless the learning clearly belongs to another scope.

## Step 4 — batch write

One backend call, JSON on stdin (never argv — summaries contain quotes):

```bash
printf '%s' '{"memories":[
  {"content":"<summary 1>","kind":"fact","about":["tag1","tag2"]},
  {"content":"<summary 2>","kind":"skill","about":["tag3"]}
]}' | wicked-garden run \
  scripts/mem/estate_memory.py capture-batch -
```

Build the JSON with real encoding discipline (escape newlines/quotes); a
malformed payload aborts before any write. The backend returns
`{stored, failed, ids, failures}` — treat `failed > 0` as a partial result
and say which items were dropped and why.

## Step 5 — verify one

Recall the most important stored memory to prove the round-trip:

```bash
wicked-garden run \
  scripts/mem/estate_memory.py recall '{"query":"<key phrase from it>"}'
```

## Step 6 — report

- `{N} memories stored` (+ `{K} failed` if any, with each refusal reason), with kinds
- one-line topic list
- if estate was unreachable (`ok: false`): report the degrade explicitly so
  the learnings can be re-captured later — never claim success on a
  fail-open response.

## Rules

- 1–3 sentences per memory: the rule, why it holds, when it applies.
- Don't duplicate what's already stored — `recall` first when unsure.
- Never store secrets, tokens, or credentials, even when discussed.
