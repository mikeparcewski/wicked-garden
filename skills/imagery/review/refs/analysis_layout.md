# Visual Analysis: Layout & Composition

This reference is for analyzing the arrangement of elements within a frame, focusing on visual balance, focal points, and the "Rule of Thirds."

## Core Objectives
- Identify the primary focal point.
- Map the "Z-pattern" or "F-pattern" for eye movement.
- Analyze visual weight and balance (Symmetrical vs. Asymmetrical).

## Extraction Workflow
1. **Focal Point Detection:** What is the first thing the viewer sees?
2. **Compositional Guides:** Identify the use of leading lines, framing, or the rule of thirds.
3. **Negative Space Analysis:** How is "white space" used to separate or emphasize elements?

## Tooling

Use Claude's native Read tool to analyze the image directly — no external CLI needed:
```
Read(file_path="./hero.png")
```
Then apply the extraction workflow above to identify focal points, composition, and balance.

## Review Criteria
- Is the focal point correctly identified?
- Does the analysis explain *why* the layout feels balanced (or intentionally unbalanced)?
- Is the use of negative space quantified?
