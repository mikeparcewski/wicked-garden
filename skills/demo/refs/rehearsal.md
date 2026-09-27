# Rehearsal: measure, observe, triage

The rehearsal is where the script's facts come from. Run it against the real system, the way the UI runs it, and
write everything down as you go.

## Before you start

- Services up, correct environment/dataset selected, business date as expected.
- Every case you plan to use lists as **fresh**. If not, reset it first.
- Know which persona each chapter acts as (specialist, lead, account manager) and switch the same way the UI does.
- Open a log file (Markdown or JSON lines) next to the script. One entry per step.

## How to drive it

Prefer the UI's own path: the same endpoints the buttons call, the same headers (acting person, dataset), the same
order. Read the front-end client code to find them. Two options, both fine:

- **Through the UI** with a browser automation tool: most faithful, also catches visual bugs.
- **Through the API** with a small script that calls exactly what the buttons call: faster, easy to time precisely.

Do not seed shortcuts the audience would never see (writing rows directly, skipping approvals). If a step is slow in
real life, it is slow in the rehearsal.

## What to log for each step

| Field | Example |
|---|---|
| Chapter / case | `02` / CASE-1 |
| Action | Click **Analyze** |
| Wall-clock time | 64.2 s (start at the click, stop when the result is on screen) |
| What the audience sees | "Nothing needs your attention"; 7 checks passed, 4 did not apply; plan of 8 steps |
| Exact labels quoted | **Analysis complete**, **View plan**, **Needs your approval** |
| Surprises | Toast says "1 thing needs attention", page says none |

Collect several runs of slow steps and report a range and median (for example "25-92 s, median 64 s over 13 runs"),
not a single lucky number.

## Rough-edge triage

For every surprise, decide explicitly:

| Decision | When | What the script says |
|---|---|---|
| **Fix** | It would confuse the audience or contradict the story (wrong counts, a crash, a misleading label) | Nothing, once fixed and re-rehearsed |
| **Script around** | Real but minor, or a known model variability | A short note in the segment: what may happen and what to say |
| **Drop / swap** | The chapter can't be made reliable in time | Use a fresh alternate or a different hero case |

Things worth fixing before any audience sees them: dashboards that recommend an action the product would refuse,
counts that disagree between two places, stale panels after background work, menus that error, captions or copy that
over-promise ("usually under a minute" when runs take 90 s).

## After the rehearsal

- Reset every case you used and confirm the fresh/used listing is clean. This proves the reset works.
- Write the script from the log, not from memory.
- Keep the raw log with the script; it is the evidence behind every "measured" number.
- If fixes land later, re-rehearse the affected chapters and record which numbers predate the change.
