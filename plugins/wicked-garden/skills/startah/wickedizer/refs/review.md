# Review: Quality Validation

How do you know writing is done? This reference provides review criteria and checklists for validating writing quality.

## The Readback Test

**Read your output as if you received it, not as if you wrote it.**

Questions to ask:
- Do I know what this wants from me?
- Can I find what I need in 30 seconds?
- Would I trust this text?
- Does anything feel off?

If you can't answer yes to all four, revise.

---

## Layered Review Process

### Pass 1: Structural Review (30 seconds)

Scan without reading deeply.

| Check | Question |
|-------|----------|
| Title | Does it tell me what this is? |
| Length | Is it right-sized for the type? |
| Headings | Can I understand the doc from headings alone? |
| Scannable | Are key points visible (bold, bullets)? |
| Organization | Is the point near the top? |

**Stop here if structure fails.** Fix structure before wordsmithing.

### Pass 2: Content Review (2-3 minutes)

Read the content.

| Check | Question |
|-------|----------|
| Point clear | Can I state the main point in one sentence? |
| Complete | Is anything missing that I'd ask about? |
| Accurate | Are facts, dates, names correct? |
| Scoped | Is it clear what's in and out of scope? |
| Actionable | Do I know what happens next? |

### Pass 3: Trust Review (1 minute)

Check for credibility killers.

| Check | Question |
|-------|----------|
| Claims supported | Every claim has evidence or is marked as opinion? |
| No inventions | No made-up stats, quotes, names? |
| Hedging appropriate | Confident where certain, hedged only where uncertain? |
| Attribution clear | Sources named or explicitly removed? |
| AI tells removed | No chatbot artifacts or promotional language? |

### Pass 4: Voice Review (1 minute)

Check for team voice alignment.

| Check | Question |
|-------|----------|
| Opening strong | First sentence states the point? |
| Tone appropriate | Matches the medium and audience? |
| Consistent terms | Same concept = same word throughout? |
| Ending strong | Closes with action, decision, or next step? |
| No fluff | Every sentence earns its place? |

---

## Type-Specific Checklists

### Exec Summary Checklist

- [ ] 5-12 lines maximum
- [ ] Point in first sentence
- [ ] Decision/ask explicit
- [ ] No background section (context integrated)
- [ ] Numbers over adjectives

### Technical Doc Checklist

- [ ] Context section explains why
- [ ] Decision stated unambiguously
- [ ] Alternatives considered (real ones, not straw men)
- [ ] Tradeoffs explicit
- [ ] Migration/rollout addressed
- [ ] Risks identified

### PRD/Requirements Checklist

- [ ] Problem clearly stated
- [ ] Success criteria measurable
- [ ] Scope boundaries explicit
- [ ] Acceptance criteria testable
- [ ] MUST/SHOULD/MAY used precisely
- [ ] No marketing language

### Work Item Checklist

- [ ] Title is action + object
- [ ] One sentence explains what this accomplishes
- [ ] Scope explicitly lists in/out
- [ ] Acceptance criteria are checkboxes
- [ ] Dependencies linked, not just named
- [ ] Scannable in 10 seconds

### Email/Comms Checklist

- [ ] Subject line has action + topic
- [ ] First line explains why you're writing
- [ ] Ask is explicit and visible
- [ ] One topic per email
- [ ] Respects reader's time

### Code Comments Checklist

- [ ] Explains why, not what
- [ ] Doesn't restate the code
- [ ] Links to issues/decisions if relevant
- [ ] Terse but complete
- [ ] No commented-out code

---

## Red Flags

### Immediate Rewrites Needed

| Red Flag | Why It's Bad |
|----------|--------------|
| "Hope this helps" | Chatbot artifact |
| "It's important to note" | Just note it |
| "Comprehensive solution" | Prove it or cut it |
| 3+ hedges in a sentence | You're not sure; cut the claim |
| No ask/action/decision | Why does this exist? |
| Point in last paragraph | Buried lede |

### Yellow Flags (Check Carefully)

| Yellow Flag | Might Be Fine If... |
|-------------|---------------------|
| Longer than expected | Complexity is essential |
| Technical jargon | Audience is technical |
| Formal tone | Context requires it |
| Multiple sections | Each has distinct purpose |

---

## Peer Review Guide

### What to Look For

When reviewing someone else's writing:

1. **Can you state the point?** If not, ask them to clarify.
2. **What's missing?** What questions would you ask after reading?
3. **What's unnecessary?** What could be cut without losing meaning?
4. **Does it match the type?** Is this the right structure for the purpose?
5. **Would you trust it?** Any credibility concerns?

### How to Give Feedback

```
// BAD: Vague
"This is confusing."
"Needs work."
"I don't get it."

// GOOD: Specific and actionable
"I can't tell what decision you need from me."
"The point seems to be in paragraph 3—can you move it up?"
"The claim about 40% improvement needs a source."
```

### How to Receive Feedback

- Assume good intent
- "Confusing" means confusing to that reader—don't argue
- Ask for specifics if feedback is vague
- Not all feedback requires action—use judgment

---

## Definition of Done

### Minimum Bar (All Types)

- [ ] Point is clear and near the top
- [ ] Structure matches the content type
- [ ] No facts were invented
- [ ] Meaning from source is preserved
- [ ] Contains action, decision, or next step

### Higher Bar (Important Documents)

- [ ] Reviewed by someone else
- [ ] All red flags addressed
- [ ] Passes type-specific checklist
- [ ] Could be understood by someone outside your team

---

## Quick Reference

| Review Type | Time | Focus |
|-------------|------|-------|
| Structural | 30 sec | Can I navigate this? |
| Content | 2-3 min | Is it complete and correct? |
| Trust | 1 min | Would I believe this? |
| Voice | 1 min | Does it sound right? |

Total: ~5 minutes for a thorough review.

**If you don't have 5 minutes, do Pass 1 only.** Structural problems matter more than word choice.
