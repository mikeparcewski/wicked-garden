# Kind: status update

A periodic report on where the work stands: what got done, what is next, and what needs help. The
brief's `Kind: status update.` line selects this ref. The skill's three floors still apply.

## Shape

1. **Header:** the project, the period it covers (absolute dates, `2026-11-02 to 2026-11-06`), and
   the author or team.
2. **In three lines:** the overall state, the most important thing that happened, and the most
   important thing needed from the reader.
3. **Done:** each item with its evidence (a merged pull request, a release, a closed issue, a
   finished run), cited.
4. **In progress:** each item with what is left and the expected date, if the sources give one.
5. **Next:** the planned items for the next period.
6. **Risks and blocked:** each with its impact, the owner, and the specific ask (who, what, by when).
7. **Numbers,** only when the sources carry them, with their period.

## Rules

- **Evidence or it did not happen.** A done item cites the change or record that shows it; an item
  you cannot cite is "in progress" or left out.
- **A red/amber/green status only with its rule.** Use one only when the brief or the sources state
  what each colour means; otherwise describe the state in words.
- **Dates are absolute.** Never "yesterday" or "next week"; a reader opens this later.
- **Bad news is in the first three lines,** not buried under Done.
- **Sized:** one page unless the brief names a budget (self-check `--pages 1`).

## Never

- invent progress, a percentage complete, or a date the sources do not give;
- list activity as achievement ("worked on X") without saying what changed;
- leave a blocker without an owner and an ask.
