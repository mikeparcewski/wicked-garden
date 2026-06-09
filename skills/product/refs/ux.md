# UX Flow Design + Analysis Rubric

Apply this inline. Design (`create`) or evaluate (`analyze`) user flows, interaction
patterns, and information architecture — in-chat, no design tool. For research
synthesis / journey maps grounded in study data, see the `ux-flow` skill
(`skills/product/ux-flow/`).

## Mode

- **create** — generate flows from a requirement/description.
- **analyze** — evaluate existing flows in code or a document.
- Auto-detect: description string (no path) -> create; file/dir path -> analyze.

## Create mode

1. **Extract user goals** — what is the user accomplishing?
2. **Identify entry points** — how do they arrive?
3. **Map the happy path** — minimum steps to goal (<=7, Miller's Law).
4. **Define decision points** — where flows branch.
5. **Handle edge cases** — empty, error, loading, cancel states.
6. **Document IA** — where this fits in the broader navigation.

## Analyze mode

1. **Trace the happy path** — is it clear and short?
2. **Find dead ends** — any branch with no recovery?
3. **Check error handling** — every failure has a user-facing message?
4. **Validate back navigation** — can users always go back?
5. **Assess cognitive load** — too many decisions at once?
6. Score against the flow checklist + Nielsen heuristics.

## Flow checklist

- [ ] Happy path <=7 steps
- [ ] Every decision has all outcomes mapped
- [ ] Error states have recovery paths (not dead ends)
- [ ] Back navigation available at every step
- [ ] Confirmation on destructive actions
- [ ] Progress indicators on 3+ step flows
- [ ] Empty + loading states defined

## Nielsen's 10 heuristics (audit)

1. Visibility of system status · 2. Match system ↔ real world · 3. User control
and freedom · 4. Consistency and standards · 5. Error prevention · 6. Recognition
over recall · 7. Flexibility and efficiency · 8. Aesthetic and minimalist design ·
9. Help users recognize/diagnose/recover from errors · 10. Help and documentation.

## Interaction pattern guidance

| Pattern | Use when |
|---------|----------|
| Modal | Focused action without losing page context |
| Slide-over | Editing a list item |
| Inline edit | Single-field quick edit |
| Wizard | Complex multi-step with dependencies |
| Accordion | Progressive disclosure for dense content |
| Tab | Peer-level content switching |

## Diagram formats

ASCII (quick) or Mermaid `flowchart TD`. IA as a tree (`App / Public / Authenticated`).

```
[Entry] -> [Step 1] -> {Decision?}
                        /         \
                      Yes          No
                       v            v
                   [Step 2]    [Alt Path]
                       v
                   [Success]
```

## Output

```markdown
## UX {Flow | Review}: {feature or component}

### Information Architecture
{IA tree}

### User Flow
{ASCII or Mermaid diagram}

### Step-by-Step Walkthrough
1. {step} -> {system response}

### Edge Cases
- Empty: {what shows}  · Error: {what shows + recovery}  · Loading: {feedback}

### Issues Found
#### Critical — {issue} — Impact: {who} — Recommendation: {fix}
#### Major — {friction} — Recommendation: {improvement}
#### Minor — {polish}

### Open Questions
- {question for product/stakeholder}

### Recommendations
1. {priority action}  2. {pattern suggestion}
```
