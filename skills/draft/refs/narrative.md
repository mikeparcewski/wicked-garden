# Kind: narrative

A narrative tells one story about the work: why it exists, what changed, and what it means for the
reader. The brief's `Kind: narrative.` line selects this ref. The three floors in the skill (readable,
sized to the brief, grounded) still apply; this ref adds what a narrative needs.

## Shape

1. **The point, first.** One or two sentences a reader could repeat: what happened or what we
   propose, and why it matters to them.
2. **Situation.** Where things stood, in facts the sources carry.
3. **Complication.** What made the situation untenable or the opportunity real, with evidence.
4. **Resolution.** What was done or is proposed, and how it addresses the complication.
5. **Proof.** What shows it works or will: measurements, shipped changes, a user's words, each
   cited. When there is no proof yet, say what would count as proof.
6. **The ask or the next step,** when the brief names an audience who must act.

## Rules

- **Name the audience** from the brief (executives, engineers, customers) and write for them: an
  executive narrative leads with the outcome and the cost; an engineering one with the mechanism.
  With no audience named, write for an informed outsider and say so in `notes.json`.
- **One story.** A second storyline is a second document; cut it or mention it in a line.
- **No claim without a source.** Adjectives are claims too: "fast", "secure", "loved" need a cited
  number or a quote, or they go. A story that the sources do not support is not told.
- **Plain words, short paragraphs** (three to five sentences), active voice, no jargon the audience
  would not use.
- **Sized:** one page unless the brief names a budget (self-check `--pages 1 --exact`). Cut
  sections, not the point.

## Never

- invent a customer, a quote, a date or a number to make the story land;
- pad with a history the reader does not need to follow the point;
- end without the point restated in the last paragraph, or without the ask when there is one.
