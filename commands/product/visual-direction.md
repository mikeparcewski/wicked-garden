---
description: |
  Reason from content structure to visual form before proposing any treatment. Answers
  five structured questions (content type, audience mental model, desired action, physical
  artifact metaphor, stupid-question test) and produces a one-paragraph visual brief.

  Use when designing or evaluating a section's visual treatment. NOT for accessibility
  audits, visual consistency review, or wireframing.
argument-hint: "<section-name-or-description> [--skip-to <question-number>]"
phase_relevance: ["clarify", "design", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:visual-direction

Stop before proposing any visual form. Reason from what the content *is* to what it
should look like — not from what the nearest project used.

## Run it inline (no dispatch)

1. Parse `<section-name-or-description>`. Read any file path given. `--skip-to <N>` starts at that question.

2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/visual-direction/SKILL.md")` — five questions, anti-patterns, visual brief format.

3. Answer all five questions out loud before proposing any treatment:
   - **Q1** What IS this content? (intrinsic structure, not appearance)
   - **Q2** What does the audience already think in? (mental model)
   - **Q3** What action do we want the user to take?
   - **Q4** If this content were a physical artifact, what form would it take?
   - **Q5** Stupid-question test: would the proposed form feel obviously wrong?

4. Emit the **visual brief**: content type · audience mental model · proposed metaphor · animation role · nearest-neighbor risk named.

Do not skip to wireframe or implementation without completing step 3.
