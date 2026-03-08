# Visual Analysis: Technical Design

This reference is for extracting structured technical and architectural details from a visual asset, such as a UI mockup, a system diagram, or a technical sketch.

## Core Objectives
- Identify functional components (buttons, inputs, containers).
- Map spatial relationships and alignment.
- Detect technical constraints or intended interactivity.

## Extraction Workflow
1. **Component Inventory:** List all distinct UI/UX elements or diagram nodes.
2. **Hierarchy Mapping:** Identify parent-child relationships (e.g., "The 'Submit' button is nested within the 'Auth' card").
3. **Spacing & Grid:** Determine if a specific grid system (e.g., 8px grid) or layout engine (Flexbox/Grid) is implied.

## Tooling

Use Claude's native Read tool to analyze the image directly — no external CLI needed:
```
Read(file_path="./mockup.png")
```
Then apply the extraction workflow above to identify components, hierarchy, and layout.

## Review Criteria
- Is the component list exhaustive?
- Are the spatial relationships accurately described for a developer to implement?
- Are interactive states (hover, active, disabled) accounted for?
