---
name: demo-planning
description: Plans a product demo end to end and writes the presenter script. Turns a product into a story of chapters (one per capability), picks hero cases with known expected outcomes and fresh alternates, makes the demo repeatable (per-case reset, fresh/used check, pre-flight), rehearses the real flows live to measure timings and find rough edges, and produces a skimmable presenter script with a run of show, per-segment click/say/sees/under-the-hood/speed-up notes, an accelerator table, a case bank, recovery tips and likely Q&A. Keeps measured numbers separate from labelled estimates. Use when asked to plan or script a product demo, write a demo script, run of show or presenter notes, prepare a live demo or rehearsal, choose demo cases, or plan a walkthrough or demo video before recording it.
license: MIT
metadata:
  version: "1.0"
---

# Demo planning

A good demo is a story the audience can follow, told with cases that behave the same way every time, and numbers
that were actually measured. This skill produces two things:

1. A **presenter script** (Markdown) that someone can run live or hand to a teammate.
2. A **chapter list** that maps 1:1 to recording segments, if a video follows (see the `demo-video-recording` skill).

Work in the order below. Do not write the script before the rehearsal: the script describes what the audience will
actually see, not what the product is supposed to do.

## 1. Frame it

Ask the user (or infer from the repo and docs) and write down:

- **Audience**: who watches, what they already know, what decision the demo should help them make.
- **Pitch**: one paragraph. The problem today, what the product does about it, and the guardrail that makes it safe
  (for example "a person approves every change").
- **Use case**: three sentences a listener could repeat: the typical request, what the product does with it, the outcome.
- **Capabilities**: a flat list of what the product can show (read, check, plan, act, learn, search, explain...).
  Each capability that matters to this audience becomes a chapter.

## 2. Build the story

One chapter per capability, ordered so each one raises the stakes of the last. A shape that works for most workflow
products:

| # | Chapter | Purpose |
|---|---|---|
| 1 | Triage / landing | "Here is my day": what needs attention, ranked |
| 2 | Core flow, end to end | One clean case from intake to done; proves the product works |
| 3-4 | Hard cases | Messy input, missing information, exceptions: where manual work goes wrong |
| 5 | Learning / governance | How the product gets smarter safely (review, separation of duties, scope) |
| 6 | Knowledge / trust | Where the rules come from and how every result traces back to them |
| 7 | 360 view | Everything about one customer or entity, plus an assistant over it |
| 8 | Wrap-up | Audit trail and the measured numbers |

Keep chapters self-contained (each starts from a known page and uses its own cases) so any one can be dropped for a
short path or re-recorded alone. Details, tags and caption voice: [references/storytelling.md](references/storytelling.md).

## 3. Choose the cases (case bank)

- **Truth first.** Use scenarios whose expected outcome you know in advance (the finding it should raise, the plan it
  should produce). Seeded or synthetic data with an answer key is ideal.
- **One hero case per chapter**, plus **fresh alternates** (variants with different names and numbers, same story) so the
  demo can run several times without resetting, and so repeat viewers don't see identical data.
- **Mark what each chapter consumes.** Read-only chapters (tours, search, dashboards) are free; chapters that analyze,
  approve, upload or teach change state. Prefer read-only where the story allows.
- Record the case bank as a table: case, story, entity/customer, what it demonstrates, fresh/used, alternates.

## 4. Make it repeatable

Before rehearsing, make sure the demo can be put back exactly as it was:

- A **per-case reset** command that rewinds only the named cases (and anything that depended on them). Avoid
  "regenerate everything" as the normal path: it is slow and wipes unrelated state.
- A **fresh/used listing** so the presenter can check readiness in seconds.
- **Deterministic data** (seeded generation, cached model text) so a rebuild gives the same cases.
- A **pre-flight checklist**: services and URLs, environment/dataset, business date, persona to act as, fresh cases,
  files to upload, tabs to open.
- **Pre-bake** slow steps for live sessions (run the one-minute analysis before the audience arrives) and say so in the
  script; the recorded video can show them live with a time-lapse.

If a reset does not exist, build or request it first. It is the difference between a demo and a one-off.

## 5. Rehearse live, then write

Run every chapter the way the UI does it (same buttons, same endpoints, same personas), against the real system,
and log as you go. Full procedure: [references/rehearsal.md](references/rehearsal.md).

- **Time every step** (wall clock) and keep the raw numbers.
- **Capture what the audience sees**: exact labels, counts, the key sentence of each result.
- **Log rough edges** with the case key: wrong labels, inconsistent counts, slow steps, confusing states.
- **Triage** each rough edge: fix it (and re-rehearse that chapter), script around it honestly, or drop the chapter.
- **Reset afterwards** and confirm every case is fresh again. This also tests the reset.

## 6. Keep claims honest

- **Measured** means timed in a rehearsal or recording on this system; say where and when.
- **Estimate** means a manual-baseline guess; label it "estimate, team to validate" every time. Never present an
  estimate as a measurement, and never average estimates into measured numbers.
- Say plainly which systems are **simulated** (e-signature, CRM writes) and that the data is **synthetic**.
- "How this speeds up execution" = the manual work replaced + measured time + labelled estimate of the manual baseline.

## 7. Write the presenter script

Start from [assets/presenter-script-template.md](assets/presenter-script-template.md). Each segment uses the block in
[assets/segment-template.md](assets/segment-template.md):

- **Case** (and fresh alternates), **Click**, **Say**, **Audience sees** (from the rehearsal), **What is happening under
  the hood**, **How this speeds up execution**, and any rough-edge note.

Around the segments: pitch and use case, setup and pre-flight, a run-of-show table with times (main path plus a short
path), an accelerator table (manual work replaced, where it shows, measured vs estimate), the case bank, recovery tips
(model variability, slow steps, reset) and likely Q&A (safety, human control, data, what is simulated).

Style: skimmable. Tables and short bullets, exact UI labels in **bold**, quotes in *italics*, one idea per line.

## 8. Keep it in sync, then hand off

- After any fix lands, update the affected segment and add a **Changes since the rehearsal** block at the top: what
  changed, whether it was seen in a browser, and which timings predate it.
- Re-rehearse chapters whose behaviour changed; replace numbers only with new measurements.
- For a video: each chapter becomes one recording segment with a key (`01-triage`, `02-core-flow`...), a title, a
  one-sentence blurb, 2-5 capability tags and the cases it resets. Hand that list to the `demo-video-recording` skill.

## Checklist

- [ ] Audience, pitch, three-sentence use case written
- [ ] Capabilities listed; one chapter each, ordered as a story
- [ ] Hero case + fresh alternates per chapter; state-consuming chapters marked
- [ ] Per-case reset and fresh/used listing work; pre-flight written
- [ ] Every chapter rehearsed live; timings and audience-visible results logged; rough edges triaged
- [ ] Script written from the template; measured vs estimate labelled everywhere
- [ ] Cases reset and confirmed fresh after rehearsal
- [ ] Chapter list ready for recording (keys, titles, blurbs, tags, resets)
