---
name: visual-direction
description: |
  Figure out what a section of content *should be* visually before reaching for any
  implementation pattern. Answers five structured questions — content structure,
  audience mental model, desired action, physical artifact metaphor, and the stupid-question
  test — then produces a one-paragraph visual brief for the implementer.

  Use when: designing a new section, evaluating a proposed visual treatment, or catching
  the nearest-neighbor trap (copying the adjacent project's pattern without asking if it fits).

  NOT for: accessibility audits (use product:a11y), visual consistency review (use product:ux-review),
  or wireframing (use product:mockup).
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# Visual Direction Skill

Reason from content structure to visual form — not from available patterns to first fit.

## The Problem This Solves

The nearest-neighbor trap: when Project B is being designed and Project A nearby used a
pattern that worked (sidebar + sticky stage + crawling tick), the agent reaches for that
pattern without asking whether Project B's content warrants it. A pattern that was right
for A's content may be actively wrong for B's.

**Real example:** A marketing site redesign for wicked-garden kept applying the
wicked-interactive conveyor pattern (sticky stage, left sidebar ledger, yellow tick) to
sections where it didn't fit. The "No cloud / No black box" refusals are philosophical
statements — they want to be big typographic text, not a scroll-pinned station list. The
tools section is a pipeline — it wants to be a session log showing the system working, not
a sidebar tour. It took three rounds of user pushback before the agent stopped copying and
started reasoning from the content itself.

## The Five Questions (answer in order)

### Q1 — What IS this content?
Not "what should it look like" — what is its intrinsic structure?

| Content type | Examples |
|---|---|
| Timeline | Steps, stages, history, before/after |
| Principles / manifesto | Philosophical statements, refusals, beliefs |
| Pipeline | Tools in sequence, data flow, system working |
| Comparison | Options side by side, trade-offs |
| Catalog | Items browsed, filtered, selected |
| Narrative | A story with a beginning, tension, resolution |
| Metric / dashboard | Numbers, status, health |

Name the type before doing anything else.

### Q2 — What does the audience already think in?
Match the metaphor to their mental model, not yours.

| Audience | Natural mental models |
|---|---|
| Developers | Logs, diffs, terminal output, config files |
| Executives | Dashboards, summaries, traffic lights |
| Designers | Grids, layers, component libraries |
| End users | Shopping, browsing, reading |
| Ops / SRE | Alerts, runbooks, timelines |

If the proposed visual form would feel alien to the intended audience, it's wrong.

### Q3 — What action do we want the user to take?
The visual treatment — including motion — should serve the action, not decorate the section.

| Desired action | Visual implication |
|---|---|
| Trust it | Calm, credible, evidence-based — not flashy |
| Install it | Clear path, no obstacles, quick scan |
| Understand it | Progressive disclosure, not all at once |
| Feel it | Emotion first, detail second |
| Choose it | Comparison-friendly, scannable differences |

Animation that doesn't serve the desired action is noise.

### Q4 — If this content were a physical artifact, what form would it take?
Bypass the pattern library entirely. Name the physical object.

Examples: a receipt, a log printout, a map, a library shelf, a garden, a contract, a
command-line session, a newspaper front page, a sticky note wall, a timeline on a wall,
a warning label.

The physical artifact test often surfaces the right visual form faster than any pattern catalog.

### Q5 — The Stupid-Question Test
Would presenting this content in the proposed form feel obviously wrong to someone who
just read it carefully?

Run the test explicitly: "If someone read all of [content] and then saw it rendered as
[proposed form], would they laugh or wince?"

Examples of failing the stupid-question test:
- Four philosophical "No X" manifestos rendered as fake browser tabs
- A system pipeline tour rendered as a customer testimonial carousel
- A comparison of two tools rendered as a hero animation
- A timeline of events rendered as a card grid

## Output: The Visual Brief

After answering all five questions, produce a one-paragraph visual brief in this form:

```
Visual Brief — [Section Name]

Content type: [name from Q1]. Audience mental model: [from Q2]. The section wants the
user to [action from Q3]. Physical artifact: [from Q4]. Proposed treatment: [one sentence
on form + motion]. Nearest-neighbor risk: [name the pattern being avoided and why it
doesn't fit]. Animation role: [one sentence on what motion does or "no animation — the
content is static"].
```

This brief is the handoff to the implementer. Do not skip to implementation without it.

## Anti-Patterns to Name Explicitly

- **Conveyor misuse**: Sticky stage + sidebar ledger is a navigation pattern for sequential
  steps a user progresses through. Don't apply it to content that isn't a progression.
- **Tab misuse**: Tabs imply interchangeable peers. Don't use them for content that has
  an inherent order or a single message.
- **Carousel misuse**: Carousels hide content. Only use when content is genuinely optional
  and browsable, not when you want to make a list of items look impressive.
- **Animation decoration**: Motion that fires on scroll without serving a conceptual purpose
  (showing assembly, revealing sequence, indicating change) is decoration. Name it as such
  and remove it.

## Integration

- **After this skill**: hand the visual brief to `product:mockup` for a wireframe, or
  directly to an implementer with the brief as the spec.
- **Before this skill**: `product:ux` to establish user flows, or `product:strategy` to
  establish what the section is trying to accomplish.
- **If the stupid-question test fails**: return to Q1. The content type is probably
  misidentified.
