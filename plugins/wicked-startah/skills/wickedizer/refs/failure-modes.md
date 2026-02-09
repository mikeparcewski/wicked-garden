# Failure Modes: What to Watch For

This reference catalogs common failure modes in rewritten content. Use it as a checklist or debugging guide when output doesn't feel right.

## Language & Tone Failures

### Transition Word Spam

**Symptoms:**
- "Additionally", "Furthermore", "Moreover" appear multiple times
- Every paragraph starts with a connector
- Text feels like a list pretending to be prose

**Fix:** Delete most transitions. Good structure doesn't need signposting.

**Before:**
> Additionally, the system supports caching. Furthermore, it includes retry logic. Moreover, there's built-in monitoring.

**After:**
> The system supports caching, retry logic, and built-in monitoring.

---

### Significance Inflation

**Symptoms:**
- "Testament to", "pivotal", "transformative", "game-changing"
- Everything sounds like a press release
- Claims don't match evidence

**Fix:** Delete the inflation. State what happened, let reader judge significance.

**Before:**
> This pivotal achievement represents a transformative milestone that serves as a testament to the team's dedication.

**After:**
> The team shipped the feature on schedule.

---

### Rhetorical Scaffolding

**Symptoms:**
- "Not just X, but Y"
- "While X is important, Y is even more critical"
- Contrast patterns that add words but not meaning

**Fix:** State the point directly.

**Before:**
> This isn't just about improving performance. It's about fundamentally reimagining how we approach the problem.

**After:**
> This improves performance by rethinking our cache strategy.

---

### Synonym Cycling

**Symptoms:**
- Same concept called different names in same document
- "Users", "customers", "clients", "stakeholders" used interchangeably
- Reader unsure if terms mean different things

**Fix:** Pick one term, use it consistently. Repetition is fine.

---

### Cadence Uniformity

**Symptoms:**
- Every sentence is the same length
- Same subject-verb-object structure repeats
- Text feels robotic despite correct grammar

**Fix:** Vary sentence length. Mix simple and compound. Short sentence. Then a longer one that develops the idea further.

---

## Content & Credibility Failures

### Fake Specificity

**Symptoms:**
- "Studies show" without citation
- Invented metrics ("reduces costs by 40%")
- Named experts who don't exist
- Quotes that seem too perfect

**Fix:** Delete unsupported claims. If the input doesn't have the data, the output can't either.

---

### Vague Attribution

**Symptoms:**
- "Experts agree"
- "Industry leaders believe"
- "It is widely accepted"
- "Research indicates"

**Fix:** Name the source or remove the attribution. "Research indicates" without citation is worse than no citation.

---

### Scope Fog

**Symptoms:**
- No owners named
- No dates or deadlines
- No explicit scope boundaries
- No success criteria

**Fix:** If input has this info, surface it. If input lacks it, note the gap or remove claims that depend on it.

---

### Empty Conclusions

**Symptoms:**
- "The future looks bright"
- "We're excited about what's ahead"
- "This is just the beginning"
- Generic optimism that applies to anything

**Fix:** End with substance: decision needed, next step, open question, or measurable outcome.

---

## Structure Failures

### Headers That Restate Bullets

**Symptoms:**
- Header: "Benefits"
- Bullet 1: "Benefit: Faster performance"
- The word "benefit" appears three times

**Fix:** Let bullets speak for themselves or make headers more specific.

---

### Bullets Without Verbs

**Symptoms:**
- Bullets that are just noun phrases
- "Improved efficiency"
- "Enhanced collaboration"
- "Streamlined processes"

**Fix:** Add verbs or delete the bullet. "Improved efficiency" becomes "Processing time dropped from 4s to 1s."

---

### Excessive Nesting

**Symptoms:**
- Sub-bullets under sub-bullets
- More than 2 levels of indentation
- Lists inside lists inside lists

**Fix:** Flatten. If content needs that much structure, it's probably multiple sections.

---

### Rule of Three Addiction

**Symptoms:**
- Everything comes in threes
- Two items become three with filler
- Four items squeezed to three

**Fix:** Use the real count. Two is fine. Four is fine. Forced three is obvious.

---

### Decorative Elements

**Symptoms:**
- Emojis in professional docs
- Unnecessary horizontal rules
- Forced symmetry between sections
- Headers for single-paragraph sections

**Fix:** Remove decoration. Let content carry itself.

---

## Process Failures

### Meaning Drift

**Symptoms:**
- Constraints from input are softened
- Decisions become suggestions
- Scope expands or contracts unintentionally

**Fix:** Compare input and output side by side. Immutables must survive.

---

### Over-Compression

**Symptoms:**
- Important details lost
- Context removed that reader needs
- Output is shorter but less useful

**Fix:** Compression should remove fluff, not substance. Re-read input for what matters.

---

### Under-Compression

**Symptoms:**
- Output is same length or longer
- Added words without added meaning
- "Improvements" that are actually additions

**Fix:** Every added word needs justification. Default is shorter.

---

### Format Mismatch

**Symptoms:**
- Exec summary that's a full doc
- Work item that's a paragraph
- Code comment that's a tutorial

**Fix:** Re-classify the artifact and apply appropriate constraints.

---

## Quick Self-Check

Before finalizing output, ask:

1. **Did I add any facts?** (Should be: No)
2. **Did I change any decisions or constraints?** (Should be: No)
3. **Can the reader answer: What? Why? Who owns it? What's next?**
4. **Would I trust this text if I received it?**
5. **Is the structure appropriate for the medium?**

If any answer is wrong, go back.
