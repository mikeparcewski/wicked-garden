# Visual Analysis Lenses

Four complementary lenses for comprehensive image analysis. Apply one or more depending on the task.

---

## Lens 1: General Description

Provides a high-level, human-readable summary of what is in the image.

### Objectives
- Provide a concise summary of the subject matter
- Identify the primary actors or objects in the scene
- Summarize the setting and context

### Extraction Workflow
1. **Subject Identification:** "What is this an image of?"
2. **Contextual Summary:** "Where and when is this taking place?"
3. **Action/State:** "What is happening or what is the state of the objects?"

### Quality Criteria
- Is the summary accurate but concise?
- Does it avoid overly technical jargon unless requested?
- Is it sufficient for a non-technical stakeholder to understand the content?

### Example Output
```markdown
**Subject:** Product mockup of a mobile banking app on an iPhone 15
**Setting:** Neutral studio background, angled at ~30° to show depth
**State:** Login screen displayed with biometric prompt active
```

---

## Lens 2: Technical Design

Extracts structured technical and architectural details from UI mockups, system diagrams, or technical sketches.

### Objectives
- Identify functional components (buttons, inputs, containers)
- Map spatial relationships and alignment
- Detect technical constraints or intended interactivity

### Extraction Workflow
1. **Component Inventory:** List all distinct UI/UX elements or diagram nodes
2. **Hierarchy Mapping:** Identify parent-child relationships (e.g., "The 'Submit' button is nested within the 'Auth' card")
3. **Spacing & Grid:** Determine if a specific grid system (e.g., 8px grid) or layout engine (Flexbox/Grid) is implied

### Quality Criteria
- Is the component list exhaustive?
- Are the spatial relationships accurately described for a developer to implement?
- Are interactive states (hover, active, disabled) accounted for?

### Decision Tree
```
Is it a UI mockup? → Full component inventory + hierarchy + grid analysis
Is it a system diagram? → Node inventory + connection mapping + data flow
Is it a technical sketch? → Element identification + annotations + constraints
```

---

## Lens 3: Style & Aesthetics

Focuses on the "look and feel" — artistic style, color theory, lighting, and mood.

### Objectives
- Define the artistic movement or medium (e.g., Minimalist, Cyberpunk, Watercolor)
- Extract the color palette (primary, secondary, accent colors)
- Analyze lighting direction, intensity, and shadows

### Extraction Workflow
1. **Mood Identification:** Use keywords to describe the atmosphere (e.g., "clinical," "ethereal," "gritty")
2. **Palette Extraction:** Identify hex codes or descriptive color names used across the asset
3. **Texture & Finish:** Note if the asset is matte, glossy, grainy, or has specific brushstrokes

### Quality Criteria
- Does the description capture the *feeling* of the asset?
- Is the palette specific enough to be used in a CSS theme?
- Are the lighting and shadows described in a way that informs generation?

### Palette Output Format
```markdown
| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary | Deep Navy | #1a2744 | Background, headers |
| Secondary | Warm Cream | #f5f0e8 | Card backgrounds |
| Accent | Electric Blue | #3d8bfd | CTAs, links |
| Danger | Coral Red | #e8534a | Error states |
```

---

## Lens 4: Layout & Composition

Analyzes the arrangement of elements within a frame — visual balance, focal points, and compositional guides.

### Objectives
- Identify the primary focal point
- Map the "Z-pattern" or "F-pattern" for eye movement
- Analyze visual weight and balance (Symmetrical vs. Asymmetrical)

### Extraction Workflow
1. **Focal Point Detection:** What is the first thing the viewer sees?
2. **Compositional Guides:** Identify the use of leading lines, framing, or the rule of thirds
3. **Negative Space Analysis:** How is "white space" used to separate or emphasize elements?

### Quality Criteria
- Is the focal point correctly identified?
- Does the analysis explain *why* the layout feels balanced (or intentionally unbalanced)?
- Is the use of negative space quantified?

### Composition Checklist
- [ ] Focal point identified and justified
- [ ] Eye flow pattern mapped (Z, F, circular, diagonal)
- [ ] Rule of thirds alignment checked
- [ ] Visual weight distribution assessed
- [ ] Leading lines identified (if present)
- [ ] Negative space usage evaluated
- [ ] Hierarchy of information confirmed (primary → secondary → tertiary)

---

## Combining Lenses

| Task Type | Recommended Lenses |
|-----------|-------------------|
| "What is this image?" | General only |
| UI mockup review | General + Technical + Layout |
| Creative asset evaluation | General + Style + Layout |
| Marketing material review | All four lenses |
| Reference image analysis | General + Style |
