# Inputs — priors fetch and session-state reads

The facilitator runs inside a Claude session with access to:

- `wicked-brain:search` and `wicked-brain:query` — prior projects, decisions, gotchas.
- `wicked-garden:mem:recall` — domain memory (cross-session learnings).
- `wicked-garden:smaht:briefing` — what happened in the most recent session.
- `Glob` / `Read` — agent frontmatter roster, existing code, existing priors.
- `SessionState` — active_chain_id, current_phase, user preferences.

---

## Default prior fetch

Before factor scoring (Step 3), run at least ONE of:

```
wicked-brain:search "<3-4 salient nouns from the description>" limit=8 depth=1
```

If the description names a surface area (e.g. "auth", "export", "dashboard"), add a
second search focused on that surface:

```
wicked-brain:search "<surface>" limit=5 depth=1
```

When the description asks "how do we usually X?" or is clearly a follow-up to an
earlier project, use:

```
wicked-brain:query "how did we previously handle <X>?" limit=5 depth=1
```

---

## Prior triage (what to keep)

From search results:

1. **Prefer `source_type: memory`** — prior decisions are gold for planning.
2. Accept `source_type: wiki` only if the excerpt clearly applies.
3. Usually skip `source_type: chunk` unless it cites a specific rule, gotcha, or the
   scope description is ambiguous.

Keep up to 3 priors. For each, write one sentence: "This prior says X, which changes
the plan by Y."

If the search returns 0 results:

1. Log it with the brain (the server does this automatically on 0-hit).
2. Treat novelty as HIGH in the factor scoring.
3. Consider adding an `ideate` phase.

---

## Session-state reads

Read `SessionState` via the smaht briefing OR direct session check for:

- `active_chain_id` — if set, this facilitator call may be a re-evaluation, not a new
  plan. Switch to `re-evaluate` mode if the description looks like a continuation.
- `user_preferences.rigor_default` — may set floor for rigor_tier.
- `user_preferences.yolo_blocked_surfaces` — surfaces where yolo is forbidden
  regardless of rigor tier.

---

## Mem recall (optional)

For domain-specific priors (e.g. "we moved away from Redis last year"), use:

```
/wicked-garden:mem:recall query="<topic>" limit=3
```

Mem recall is slower than brain search and has less coverage, but it's the
persistence layer for team decisions that the user explicitly stored.

---

## Roster discovery

Before Step 4 (specialist selection):

```
Glob "agents/**/*.md"
```

Read frontmatter for each file to get `name`, `description`, and the "Use when" line.
Do NOT assume the roster from this ref — the ref is a map, the glob is the territory.
If an agent listed in `specialist-selection.md` is missing from the glob, follow the
Fallback Resolution rules.
