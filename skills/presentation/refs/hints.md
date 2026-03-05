# Hints — Contextual Hints & REVIEW Flagging

Two systems: **contextual hints** (surface during wizard flows) and **REVIEW flags** (embedded
in generated deck speaker notes when human judgment is needed).

---

## Contextual Hints

### When to fire
Hints are brief, friendly, and actionable. Fire them at the right moment in the flow — not all
at once. One hint at a time. Don't fire the same hint twice in a session.

### Hint catalog

**No style profile**
Condition: `presentation:profiles` is empty and no built-in selected yet
Moment: profile selection step
> *"No style profile found — using minimal light. Run style extraction on your existing decks to
> match your brand, or pick a built-in theme below."*

**Topic only, no content, research off**
Condition: user provided topic but no files, and `research` plugin unavailable or disabled
Moment: after Q5 (source content) in brainstorm or create flow
> *"This will be AI-generated without source material or research. The result will be reasonable
> but won't reflect your specific data or context. Consider: adding a file, enabling research,
> or at least pasting a few bullet points."*

**Slide count >> content volume**
Condition: requested slide count is more than 2× what content supports
Moment: after slide count question
> *"That's a lot of slides for the content available — I'd suggest [N] based on what you've
> shared. Want me to adjust, or keep your target?"*

**Index has relevant content**
Condition: content index contains chunks matching the deck topic
Moment: Q5 (source content) in any flow
> *"Found related content in your index — [N] items about '[topic]'. Want to include them?"*

**Brainstorm plugin unavailable**
Condition: `brainstorm` plugin not found in wicked-garden plugin list
Moment: mode selection, if user picks brainstorm
> *"Brainstorm plugin not available — starting in create mode instead. Install the brainstorm
> plugin to enable interactive idea development."*

**Research plugin unavailable**
Condition: `research` plugin not found
Moment: research question in wizard
> *"Research plugin not found — I'll work with what you provide. Install the research plugin
> to enable web-sourced content enrichment."*

**Nothing to work with**
Condition: no content + no research + topic is fewer than 5 words with no elaboration
Moment: after all content inputs collected in fast path or create flow
> *"Not much to work with yet. Try: providing a file or directory, enabling research, or
> describing the topic in more detail. Even a rough bullet list helps significantly."*

**Image/PDF provided without context**
Condition: user provides image or PDF files as first input with no explanation
Moment: immediately after input received
> *"Got it — should I use these for content, style reference, or both?"*

**Prior versions exist**
Condition: `presentation:versions` has records matching the derived slug
Moment: startup, before mode selection
> *"Found [N] prior versions of '[slug]'. Start fresh, or build from v[latest]?"*

**Registry not synced this session**
Condition: `presentation:registry-config.last_pulled` is not today and `auto_pull` is false
Moment: profile selection step
> *"Your design registry hasn't been synced this session — pull latest first? (yes / skip)"*

**Unsplash attribution not configured**
Condition: Unsplash mode selected, attribution preference not set in profile
Moment: after image mode selection
> *"Unsplash images require attribution — I'll add it to speaker notes by default. Want to
> change this? (notes / footer / none)"*

**No Unsplash API key**
Condition: Unsplash mode selected, no API key in plugin storage
Moment: after image mode selection
> *"Unsplash mode requires an API key. Get a free key at unsplash.com/developers and configure the Unsplash API key in presentation skill settings.*
> *Falling back to icon mode for this deck."*

**Format guidance — sharing as URL**
Condition: user mentions "sharing", "sending a link", "hosting", or "embedding" the deck
Moment: format selection step
> *"This sounds like something you'd share as a link — HTML output opens in any browser with no
> PowerPoint required. Want to use html format or both?"*

**Format guidance — needs post-editing**
Condition: user mentions "clean it up", "edit after", "polish in PowerPoint", or "hand off to client"
Moment: format selection step
> *"Sounds like you'll want to edit this after generation — pptx keeps it fully editable in
> PowerPoint. Request both formats if you also want an HTML version."*

**Format not set, no profile default**
Condition: no format specified, no profile default, format question skipped in fast path
Moment: silently default to pptx; note in summary
> (no hint — just note in post-gen summary: "Format: pptx (default). Request html format to get
> a browser-presentable version.")*

---

## REVIEW Flags

Embedded in speaker notes on slides that need human judgment before the deck is finalized.

### Format
```
[REVIEW: reason — brief description of what needs checking]
```

### When to flag

| Trigger | Flag text |
|---|---|
| Conflicting data across source files | `[REVIEW: conflicting figures — source A says X, source B says Y]` |
| Stat or claim without a clear source | `[REVIEW: unverified stat — confirm before presenting]` |
| Ambiguous direction (plugin made a judgment call) | `[REVIEW: assumed [direction] — verify this framing is correct]` |
| Content gap (slide topic referenced but no content found) | `[REVIEW: content gap — no source material found for this slide]` |
| Image placeholder (no Unsplash result, no icon match) | `[REVIEW: no image found — add manually or adjust keywords]` |
| Estimated/inferred data | `[REVIEW: estimated value — replace with actual data]` |
| Audience assumption | `[REVIEW: assumed executive audience — adjust tone if different]` |

### Flag summary slide

When flag count > 3, prepend a hidden summary slide (slide 0, marked "hidden" in notes):
```
REVIEW SUMMARY — [N] slides flagged

  Slide 3:  conflicting figures on cost estimate
  Slide 7:  content gap — migration timeline
  Slide 11: unverified stat — 40% efficiency claim
  Slide 14: no image found
  Slide 18: assumed recommendation — confirm direction

This slide is for internal review only. Delete before presenting.
```

### Strict mode

When strict mode is requested (e.g., "fast path, strict mode"), instead of flagging and continuing, the skill pauses at each conflict and asks the user to resolve inline. Best for high-stakes decks where accuracy is critical.

---

## Preview-to-Confirm

Fired when direction is genuinely ambiguous — not on every run. Use sparingly.

**Triggers:**
- Brainstorm returned two equally strong narrative structures
- Research returned conflicting framings of the same topic
- Create flow: more than 20% of slides have no clear source content
- Fast path: topic is ambiguous enough that structure could go multiple ways

**Format:**
> "Here's the structure I'm planning before I build it out:
>
> 1. Title — [proposed title]
> 2. The Challenge — [summary]
> 3. Our Approach — [summary]
> 4–6. [section name] — [brief]
> 7–9. [section name] — [brief]
> 10. Next Steps — [CTA framing]
>
> ⚠ Slides 7–9 are light on content — marked [GAP].
>
> Does this look right, or want to adjust before I build?"

Accept responses:
- "Yes" / "looks good" / "go" → build
- Redirect or adjustment → update outline, optionally re-confirm
- "Just go" → build without further confirmation
