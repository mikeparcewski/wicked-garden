# jam composition map

Structured brainstorming and multi-model evaluation — from quick gut-check to council verdict.

## Surface inventory

| Type | Name | One-line purpose |
|---|---|---|
| command | /wicked-garden:jam:brainstorm | Full multi-round session with evidence-backed personas |
| command | /wicked-garden:jam:council | Structured evaluation using external LLM CLIs for a verdict |
| command | /wicked-garden:jam:persona | Retrieve one persona's contributions across all rounds |
| command | /wicked-garden:jam:perspectives | Raw viewpoints from 4-6 personas, no synthesis |
| command | /wicked-garden:jam:quick | 60-second, 4-persona, 1-round gut-check |
| command | /wicked-garden:jam:revisit | Record outcome of a past brainstorm decision |
| command | /wicked-garden:jam:thinking | Show pre-synthesis perspectives (minority views, dissents) |
| command | /wicked-garden:jam:transcript | Full chronological session record |
| agent | wicked-garden:jam:brainstorm-facilitator | Role-plays focus-group personas and synthesizes discussion |
| agent | wicked-garden:jam:council | Runs multi-model council evaluations via external LLM CLIs |
| skill | wicked-garden:jam | Brainstorming orchestration — session tracking + brain storage |

## Workflow patterns

### 1. Quick idea sanity-check
User wants a rapid gut-check before investing in a full session.

```
/jam:quick "<idea>"
```

One command, one dispatch to `brainstorm-facilitator`, result in ~60s. Use when you just need a temperature read.

### 2. Full brainstorm
User wants deep exploration with evidence-backed personas and synthesis.

```
/jam:brainstorm "<topic>" [--personas list] [--rounds n]
→ /jam:thinking          # inspect pre-synthesis dissents if synthesis feels flat
→ /jam:transcript        # audit full record
```

`brainstorm` delegates to `brainstorm-facilitator`. Outputs stored via `wicked-brain:memory`. Use `thinking` to surface what synthesis compressed.

### 3. Decision evaluation with external LLMs
User has defined options and needs an independent verdict, not ideation.

```
/jam:council "<topic>" --options "A, B, C" [--criteria "perf, cost, risk"]
```

`council` agent queries real external LLM CLIs (Codex, Gemini, etc.) independently, then synthesizes. Distinct from `brainstorm` — no persona role-play, just structured verdict.

### 4. Perspective gathering without synthesis
User wants raw expert viewpoints for their own reasoning or a discussion.

```
/jam:perspectives "<decision or question>"
```

No synthesis step. Returns position + key concern + what would change their mind per persona. Good for prep before a human conversation.

### 5. Decision hygiene loop
Track whether past decisions held up.

```
/jam:revisit "<topic keyword>"   # find + record outcome
/jam:persona "<name>"            # trace how one voice evolved
```

Pulls from `wicked-brain:memory`. Closes the feedback loop on past sessions.

## When to add a new surface

- **New command** — when there is a user-facing workflow step that is not addressable by composing existing commands. The `quick → brainstorm → council` progression is the core; new commands extend it at the edges (new entry points, new retrieval modes).
- **New agent** — when a new facilitation mode is fundamentally different in execution from `brainstorm-facilitator` (persona role-play) or `council` (structured multi-model). Do not add agents for minor variations in round count or persona set — drive those through command arguments.
- **New skill** — jam has a single SKILL.md with two refs (`facilitation-patterns.md`, `synthesis-patterns.md`). Add a ref if synthesis or facilitation logic grows past ~200 lines. Do not add a top-level skill entry for jam sub-topics.

## Cross-domain dependencies

```
jam
  calls →  wicked-brain:memory   (store session outcomes, recall past decisions)
  calls →  wicked-brain:search   (surface evidence during brainstorm rounds)

crew
  calls →  jam:council           (challenge phase at complexity >= 4)
  calls →  jam:brainstorm        (ideation during design phase, optional)

smaht
  reads ←  jam session events    (events adapter surfaces recent sessions in context)
```

## Anti-patterns

- **Using `brainstorm` when you need a verdict.** `brainstorm` is generative/exploratory; use `council` when you have defined options and need a decision.
- **Adding a new agent per persona set.** Persona selection is a command argument (`--personas`), not an agent concern. One facilitator agent handles all persona configurations.
- **Skipping `revisit` at the end of a project.** Decisions that are never revisited don't feed back into `wicked-brain:memory`, which degrades future session quality.
- **Reading brain files directly.** Past session data lives in `wicked-brain:memory`. Use `jam:revisit`, `jam:transcript`, or `wicked-brain:memory` recall — never grep the brain store directly.
