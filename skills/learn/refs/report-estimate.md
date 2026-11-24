# Lens: estimate

**Brief line:** `Lens: estimate.` **Card:** Estimate and price. **Documents:** optional (a statement of
work, a rate card, a backlog). The scope comes from the intent when no document is staged: copy that
text into the packet's `brief` and cite each scope item from it.

## What the person gets

Effort ranges per item, rates from the documents, every assumption named, and the price as effort × rate.

## Shape

1. **Scope**: the items to estimate, each cited to the document or the intent.
2. **Assumptions**, numbered A1..An: everything the estimate rests on that no source states (team size,
   availability, what "done" means). An assumption is not a claim and carries no claim id, but every
   estimate line names the assumptions it uses.
3. **Effort table**: one row per item, a low, likely and high effort with its unit, the basis (a cited
   comparable, a cited rate of delivery, or named assumptions), and its confidence.
4. **Rates**: from the documents (cited) or stated as an assumption. Never invent a rate.
5. **Price**: per item and in total, as effort × rate for low, likely and high. Show the arithmetic.
6. **What moves the number most**: the two or three assumptions with the largest effect.
7. `## Sources`.

## Rules

- Ranges, never a single point.
- A repository in scope may be read for size and complexity (files, modules, tests); cite it with code
  records (refs/report-claims.md).
- Recompute every total before you finish.
