# Wizard — Creation Flows

Four modes. Each has a distinct question sequence. Read the relevant section only.

---

## Mode Selection (all flows start here)

```
What would you like to do?

  [brainstorm]  Develop the ideas together — interactive content creation
  [create]      Build from content — files, PDFs, images, topics, or all of it
  [fast]        Just make it — one input, minimal questions, maximum output
  [overview]    Quick structure only — skeleton deck for human completion
```

If the user's initial intent already implies a mode (e.g., they said "just make a fast deck on topic"), skip
selection and go directly to that flow.

---

## BRAINSTORM FLOW

Best for: new topics, unfamiliar territory, when the user doesn't yet know what they want to say.

### Questions (in order)

**Q1 — Topic**
> "What's the topic or core message? (Even a rough idea is fine.)"

Accept: free text, a sentence, a few words. If extremely vague, ask one follow-up:
> "Can you say a bit more? What's the context — a client meeting, internal review, conference talk?"

**Q2 — Brainstorm**
Call the `brainstorm` plugin with the topic. Return 2–3 candidate narrative structures:
- Structure A: [title + 3-line arc summary]
- Structure B: [title + 3-line arc summary]
- Structure C: [title + 3-line arc summary]

> "Which direction resonates? Pick one, mix elements, or tell me to adjust."

Iterate until the user commits. Maximum 3 rounds before offering: *"Want me to just pick the strongest and go?"*

**Q3 — Audience & Outcome**
> "Who's the audience, and what should they feel or do after seeing this?"

Accept: brief description. Use this to calibrate tone, density, and CTA slide content.

**Q4 — Slide Count**
> "Rough slide count? (Or I can estimate based on the scope.)"

If user says "estimate" or skips: derive from topic complexity and audience type:
- Executive audience → lean (8–12 slides)
- Workshop/training → moderate (15–25)
- Conference talk → moderate (15–20)
- Internal review → match content volume

**Q5 — Source Content**
> "Any source content to draw from? Files, PDFs, images, a directory — or leave blank to work from the brainstorm."

If blank: proceed AI-generated. Fire hint if no research either.
If provided: index it, surface relevant chunks during generation.

**Q6 — Research**
> "Should I do additional research to enrich the content? (yes / no)"

If `research` plugin unavailable: skip this question, note the gap.

**Q7 — Style Profile**
> "Which style profile? Here's what's available:"
[list: learned profiles / imported profiles / registry profiles / built-in themes]
> "Or describe a vibe and I'll find the closest match."

See [profiles.md](profiles.md) for selection logic.

**Q8 — Image Mode**
> "For images: Unsplash photos, icon/UI illustrations, or no images?"

Set as deck default. Can be overridden per slide during generation.

**Q9 — Output Format**
> "Output format: pptx / html / both?"

Skip if the user specified format in their request or profile has a default set. Guide if unsure:
- Will you share this as a link or host it online? → html
- Does the recipient need to edit it in PowerPoint? → pptx
- Not sure, or want both options? → both

**Q10 — Layout Fidelity**
> "Layout fidelity: best / draft / rough?"

Skip if the user specified fidelity in their request or profile has a default. Present with brief context:
- **best** — Multiple render passes. Verifies copy fits, spacing is consistent, nothing overflows.
  Takes longer. Use for client-ready or high-stakes presentations.
- **draft** — Single clean pass. Good layout, minor imperfections possible. Easy to fix in
  PowerPoint or HTML. Default for most flows.
- **rough** — Content placed, structure correct, layout intentionally unpolished. Use when
  you need the text and structure now and will rework design yourself.

**Q11 — Preview Confirm (conditional)**
Only ask if: content had ambiguities, research returned conflicting data, or brainstorm direction
required a judgment call.
> "Here's the structure I'm planning before I build it out: [outline]. Does this look right, or want to adjust?"

Accept: confirm / redirect / "just go"

**→ Generate**
Generate Deck Spec → render to selected format(s). Apply REVIEW flags. Write version record.
Store spec in `presentation:specs:{slug}:{version}` for future re-renders.

---

## CREATE FLOW

Best for: existing content that needs structure, when the user knows what they want to say.

### Questions (in order)

**Q1 — Content**
> "Point me to your content — files, directory, PDFs, images, or paste text directly."

If nothing provided:
> *"Tip: I work best with at least a rough outline. Even a bullet list works. Want to paste something,
> or should I help you develop the content first?"*
→ If user still has nothing: offer to switch to brainstorm flow.

Check content index for related material. Fire hint if relevant content found.

**Q2 — Core Message**
> "What's the core message or goal of this deck?"

**Q3 — Audience**
> "Who's the audience?"

**Q4 — Slide Count**
> "Approximate slide count? Or I can derive it from the content volume."

**Q5 — Research**
> "Should I do research to supplement this content, or stay strictly with what you've provided?"

**Q6 — Style Profile**
Same as brainstorm Q7.

**Q7 — Emphasis / Avoidance**
> "Anything specific to emphasize or avoid?" (optional — skip if user says nothing)

**Q8 — Output Format**
> "Output format: pptx / html / both?"

Skip if the user specified format in their request or profile has a default. Same guidance as brainstorm Q9.

**Q9 — Layout Fidelity**
> "Layout fidelity: best / draft / rough?"

Skip if the user specified fidelity in their request or profile has a default. Same options as brainstorm Q10.

**Q10 — Preview Confirm (conditional)**
Fire if: content had gaps, conflicting data across sources, or more than 20% of slides have no
clear source material.
> "Here's the structure I'm planning: [outline]. A few slides are light on content — marked with [GAP].
> Does this look right, or want to adjust before I build?"

**→ Generate**
Generate Deck Spec → render to selected format(s). Content fidelity mode: stay close to source,
don't invent facts. Apply REVIEW flags. Store spec. Write version record.

---

## FAST PATH FLOW

Best for: repeat use, quick drafts, users who know the tool well.

### Input
If the user chooses fast path or says "just make it", prompt for a single topic or path input.
Or at mode selection, choose [fast] → prompt for single input.

### Behavior
- Apply last-used profile from session storage, or default profile, silently
- Apply last-used fidelity, or `draft` if not set (fast path never defaults to `best` — too slow)
- Check content index — include relevant content automatically
- Call `research` silently if research plugin available and topic has < 3 source files
- Derive slide count from content volume (executive default: 10–12)
- Select templates automatically per content type
- Default image mode from profile, or no images if not set
- Flags unresolvable conflicts as REVIEW notes rather than asking
- No preview confirm — build and output

### Output
- Versioned deck in selected format(s) (profile default or user-specified format)
- Deck Spec stored in plugin storage for future re-renders
- One-line decision summary appended to first slide's speaker notes:
  > *"Fast path: used [profile], [N] slides, [format], [fidelity], [image mode], research [on/off], [N] REVIEW flags"*

### Edge cases
- No content + shallow topic + research unavailable → pause, fire "nothing to work with" hint, ask for input
- No style profile at all → use minimal light, note it in summary

---

## OVERVIEW FLOW

Best for: planning sessions, deck scaffolding before a full create run, getting structure right first.

### Questions

**Q1**
> "What's the topic and rough scope?"

**Q2**
> "How many sections and approximately how many slides?"

### Output
Skeleton deck:
- Title slide (topic + placeholder subtitle)
- One section-divider slide per section
- 2–4 content placeholder slides per section with:
  - Slide title
  - Content type hint in body: `[stat]`, `[chart]`, `[3-point list]`, `[quote]`, `[image]`
  - Speaker note: question the presenter should answer with this slide
- Closing/CTA placeholder

No filler content. No research. No style required (use minimal light).
Designed for human editing or as structured input to a subsequent `create` run.

---

## Shared Behaviors (all flows)

### Version naming
Every output gets a versioned filename. See [versioning.md](versioning.md).

### REVIEW flagging
Slides with unresolved questions, conflicts, or gaps get `[REVIEW: reason]` in speaker notes.
A summary of all flagged slides is prepended as slide 0 (hidden) when flag count > 3.

### Profile fallback order
1. User-selected in wizard
2. Last-used profile from session storage
3. Default profile from plugin storage
4. Built-in: minimal light

### Post-generation summary
Always output a brief summary after generation:
```
✓ Deck created: deck-name_v2.pptx + deck-name_v2.html (18 slides)
  Format:   both (pptx + reveal.js html)
  Fidelity: draft (1 render pass)
  Profile:  corporate-blue
  Content:  3 source files + research
  Images:   Unsplash (attribution in notes)
  REVIEW flags: 2 slides (see slide 0)
  Templates used: stat-callout ×3, two-column ×5, timeline ×1, section-divider ×3
  Re-render: request "re-render deck-name_v2 as <format>"
  Re-render at higher fidelity: request "re-render deck-name_v2 at best fidelity"
```
