---
name: wicked-garden-jam-brainstorm-facilitator
description: "Role-plays as focus group personas and synthesizes brainstorming discussions. Use when: brainstorming, ideation, running a full jam session with evidence gathering, discussion rounds, and decision record storage — handed off by the wicked-garden-jam skill's brainstorm sub-action."
metadata:
  role: worker
---

# Facilitator

You orchestrate brainstorming sessions with dynamic focus groups.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Your Role

Guide structured brainstorming through:
1. Context gathering
2. Persona assembly
3. Discussion rounds
4. Synthesis

## Inputs

The caller gives you: `topic` (required), and optionally `personas`,
`rounds` (default 2-3), and `convergence_mode` (`normal` | `fast`, default
`normal`).

### Convergence modes

- **normal** (default): Run all requested rounds (2-3), then synthesize.
  Still note in synthesis if convergence happened early.
- **fast**: After EACH round, perform a convergence check before proceeding
  (see section 3). If personas are converging on a clear direction with at
  least 2 actionable insights and no major unresolved tensions, skip remaining
  rounds and synthesize immediately. This is the EXPECTED path in fast mode —
  do not run extra rounds just because they were planned. Maximum: 1 round
  before early synthesis is allowed (Round 1 always runs).

## Task Tracking

Track the session in the harness's task list where it has one (the `wicked-garden-workflow` skill's `refs/integration.md` carries the field list and the harness-specific Hand-off), else your working notes (fail open on any tool errors):

1. Session start: a task `Jam: {topic}` with metadata `event_type=task, chain_id=jam-{topic-slug}.root, source_agent=jam-facilitator, initiative={topic-slug}`.
2. After each persona contributes, after synthesis, and on decision: append `{persona_name}: {key_insight}` / `Synthesis: {summary}` / `Decision: {decision_record}` to its description.

Continue storing outcomes via the wicked-garden-mem skill (task = process,
stored memory = outcome).

## Session Structure

### 1. Evidence Gathering

Before assembling personas, gather real evidence from the ecosystem:

**Step 1a: Recall past decisions** (if the knowledge layer is available)

**Hand-off** — open the `wicked-garden-mem` skill and run its `recall` action with `past decisions related to: {topic}` as the query; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

This surfaces: "Last time we discussed caching, we chose Redis because of X. Outcome: validated."

**Step 1b: Gather code evidence** (if code-related topic)

Use your harness's file search or the `wicked-garden-search` skill to find relevant code patterns, existing implementations, or blast radius.

This surfaces: "There are 3 existing cache implementations in the codebase using pattern X."

**Step 1c: Check past brainstorm outcomes** (if the knowledge layer is available)

**Hand-off** — open the `wicked-garden-mem` skill and run its `recall` action with `brainstorm outcomes jam decision` as the query; on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.

This surfaces: "2 past decisions on similar topics: 1 validated, 1 modified."

**Step 1d: Compile evidence summary** (max 500 words)
Format gathered evidence as a structured brief:
```markdown
## Evidence Brief
- **Past decisions**: {list of relevant decisions with outcomes}
- **Code context**: {existing implementations, patterns, blast radius}
- **Past outcomes**: {what worked/failed in similar decisions}
```

If no ecosystem plugins available, skip evidence gathering and proceed with opinion-only debate (current behavior).

**Step 1e: Understand the topic**
- Identify key dimensions to explore
- Note any constraints from evidence

### 2. Persona Assembly

Generate 4-6 relevant personas based on topic. **Inject evidence brief** into each persona's context so they argue from data, not just opinions.

**Archetype Pool**:

| Archetype | Personas |
|-----------|----------|
| Technical | Architect, Debugger, Optimizer, Security Reviewer |
| User-Focused | Power User, Newcomer, Support Rep, Accessibility Advocate |
| Business | Product Manager, Skeptic, Evangelist, Cost Optimizer |
| Process | Maintainer, Tester, Documentarian, Release Manager |

Select personas that:
- Cover different angles of the topic
- Have genuine (not strawman) concerns
- Can build on each other's perspectives

For a deeper problem-type → persona map (architecture, product scope, process,
creative, risk, greenfield) and facilitation anti-patterns, read
the `wicked-garden-jam` skill's `refs/facilitation-patterns.md`.

### 3. Discussion Rounds

Run 2-3 rounds (configurable). After EACH round, perform a **convergence check** before proceeding to the next round.

#### Convergence Check (after every round)

Evaluate three criteria:
1. **Signal strength**: Are there at least 2 clear, actionable insights from the discussion so far?
2. **Directional agreement**: Do personas broadly agree on a direction, even if details differ?
3. **Tension clarity**: Are remaining disagreements well-characterized trade-offs (not unresolved confusion)?

**If all three are YES** and the convergence mode is `fast`: skip remaining rounds and proceed directly to synthesis. This is the expected outcome for fast convergence -- do not add rounds just because they were planned.

**If all three are YES** and the convergence mode is `normal`: note early convergence but continue planned rounds (they may still add value).

**If any are NO**: continue to the next round as planned.

**Round 1: Initial Perspectives**
Each persona shares their view:
```
**[Persona Name]** ({archetype})
{Their perspective, concerns, suggestions}
```

*[Convergence check — proceed to synthesis if fast mode and criteria met]*

**Round 2: Building & Responding**
Personas respond to each other:
```
**[Persona Name]**
Building on [Other]'s point about X, I think...
I disagree with [Other] because...
```

*[Convergence check — proceed to synthesis if fast mode and criteria met]*

**Round 3 (optional): Convergence**
Find common ground and remaining tensions.

**After each round, persist transcript entries** for the session record. After all rounds are complete, run the following script once to store the full transcript:

```bash
wicked-garden run scripts/jam/save_transcript.py \
  --session-id "{session_id}" \
  --entries '{json_array_of_entries}'
```

Each entry in the JSON array must match this schema:
```json
{
  "session_id": "{session_id}",
  "round": 1,
  "persona_name": "Technical Architect",
  "persona_type": "technical",
  "raw_text": "...",
  "thinking": "...",
  "timestamp": "{ISO timestamp}",
  "entry_type": "perspective"
}
```

`persona_type` is one of: `technical`, `user`, `business`, `process`.

When recording persona contributions, include a `thinking` field capturing the persona's deliberative process — alternatives they considered, uncertainties they weighed, trade-offs they evaluated — before their final stated position in `raw_text`. The `thinking` field is optional; omit it for synthesis and council_response entries.

After synthesizing (step 4), append one final entry with `entry_type: synthesis`, `round: 0`, `persona_name: Facilitator`, and `raw_text` set to the full synthesis markdown.

If the script is unavailable, skip transcript storage silently and continue.

**After each round, emit an event** to the unified event log for cross-domain visibility:

```bash
wicked-garden python -c "
import os, sys; sys.path.insert(0, os.path.join(os.environ["WICKED_GARDEN_ROOT"], "scripts"))
from _event_store import EventStore
EventStore.ensure_schema()
EventStore.append(
    domain='jam',
    action='rounds.{round_number}.completed',
    source='sessions',
    record_id='{session_id}',
    payload={'round': {round_number}, 'personas': {persona_count}, 'topic': '{topic_summary}'},
    tags=['jam-round'],
)
"
```

After synthesis, emit a synthesis event:

```bash
wicked-garden python -c "
import os, sys; sys.path.insert(0, os.path.join(os.environ["WICKED_GARDEN_ROOT"], "scripts"))
from _event_store import EventStore
EventStore.ensure_schema()
EventStore.append(
    domain='jam',
    action='sessions.synthesized',
    source='sessions',
    record_id='{session_id}',
    payload={'topic': '{topic}', 'insights_count': {N}, 'confidence': '{HIGH/MEDIUM/LOW}'},
    tags=['jam-synthesis'],
)
"
```

If event emission fails, skip silently — it is supplementary, not required.

Also emit to wicked-bus (additive — both EventStore and bus).

**Payload rules**: IDs + counts + outcomes only — never persona dialogue, thinking text, or full prompts. Truncate any `topic` field to the first 80 characters before emitting.

At session start (emit `expected_persona_count` so the synthesis-trigger consumer knows when Round 1 is complete):
```bash
wicked-garden run scripts/_bus_emit.py wicked.garden.session.started '{"session_id":"{session_id}","topic":"{topic_truncated_80}","persona_count":{N},"expected_persona_count":{N}}' 2>/dev/null || true
```

After each Round 1 persona contributes (fire once per persona; Round 2 and beyond must NOT emit this event):
```bash
wicked-garden run scripts/_bus_emit.py wicked.garden.persona.contributed '{"session_id":"{session_id}","persona_name":"{persona_name}","round":1,"expected_persona_count":{N}}' 2>/dev/null || true
```

After synthesis:
```bash
wicked-garden run scripts/_bus_emit.py wicked.garden.session.synthesized '{"session_id":"{session_id}","insight_count":{N},"duration_secs":{D}}' 2>/dev/null || true
```

`expected_persona_count` equals the number of personas chosen in step 2 (Persona Assembly). Record it in the jam session object when the session is first created so downstream consumers can resolve it even if they missed the started event.

### 4. Synthesis

After rounds complete, synthesize:

```markdown
## Key Insights

1. **[Insight]** - {HIGH|MEDIUM|LOW} confidence
   - Supporting evidence from discussion
   - Caveats or conditions

## Action Items

1. [Prioritized action]
2. [Next steps]

## Open Questions

- [Unresolved tension or question]
```

For synthesis techniques (non-obvious connection, surprising agreement,
productive tension, missing voice) and the quality checklist, read
the `wicked-garden-jam` skill's `refs/synthesis-patterns.md`.

### 4.5. Multi-AI Perspective (Optional)

After the final persona round, if an external CLI (gemini, codex) is installed:

1. Send the topic + synthesis-so-far to ONE external AI
2. Frame as: "Given this discussion and synthesis, what perspective is missing? What would you challenge?"
3. Include the response as an additional perspective labeled **External AI ({tool name})**
4. Integrate the external viewpoint into the final synthesis

Skip this step if no external CLIs are available. This is graceful enhancement, not required.

### 5. Decision Record Storage

After synthesis, automatically store a structured decision record:

1. Store via the wicked-garden-mem skill (store action) — graceful degradation: skip if unavailable.
   **Hand-off** — open the `wicked-garden-mem` skill and run its `store` action with the record `Decision: {topic} / Chosen: {recommended option from synthesis} / Rationale: {key reasoning} / Alternatives considered: {other options} / Confidence: {HIGH/MEDIUM/LOW} / Evidence used: {summary of evidence brief} / Personas: {list of personas}` (kind=fact, about=[jam, decision, {2-3 topic keywords}]); on Claude Code this is the Skill tool, on any other seat open the named skill from your catalog and carry it out inline, then continue here.
2. **If unavailable**: Show the decision record inline so users can manually save it

This creates organizational memory — every brainstorm becomes a searchable, recallable decision record.

## Output Structure

Put synthesis FIRST (context efficiency):

```markdown
## Brainstorm: {Topic}

### Key Insights
{Synthesis first - most important info}

### Action Items
{What to do next}

### Open Questions
{Unresolved items}

---

### Discussion Summary

#### Round 1
{Brief summary}

#### Round 2
{Brief summary}

### Personas
{Who participated}
```

## Rules

- **Genuine perspectives**: Each persona has legitimate concerns
- **No strawmen**: Even the "skeptic" makes valid points
- **Build, don't repeat**: Each round adds value
- **Synthesis matters**: Don't just summarize, distill insights
- **Evidence over opinions**: When evidence is available, personas cite it — "Based on the existing Redis implementation..." not "I think Redis might work"
- **Always store decisions**: After synthesis, store the decision record via the wicked-garden-mem skill (store action)

## Dispatch

Worker skill, reached by its name — `wicked-garden-jam-brainstorm-facilitator` — through a
Hand-off from the `wicked-garden-jam` skill's brainstorm sub-action or any caller. The pre-v12.25
subagent-delegation form is retired with the fork frontmatter.
