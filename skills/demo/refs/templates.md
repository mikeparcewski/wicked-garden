# Demo templates

## Presenter-script template

# <PRODUCT> demo script

For the presenter and <TEAM>. Rehearsed on <DATE> against <ENVIRONMENT> with <MODEL / VERSION>. Timings marked
**measured** come from that run; manual-effort figures are marked **estimate** and are starting points for the team to
validate, not measurements.

**Changes since the rehearsal.** <Leave empty until fixes land. Then list each change, whether it was seen in a
browser, and which timings predate it.>

---

## 1. Pitch

**Pitch (one paragraph).** <The problem today. What <PRODUCT> does about it. The guardrail that keeps a person in
control. What gets faster.>

**Use case (three sentences).** <The typical request.> <What <PRODUCT> does with it.> <The outcome.>

---

## 2. Setup and pre-flight checklist

| Item | Value / how to check |
|---|---|
| UI | <URL> |
| API / services | <URL or command to check health> |
| Background workers | <how to start; what breaks if not running> |
| Environment | <dataset / tenant selector value> |
| Business date | <what the header should show> |
| Persona | <who to act as, and when to switch> |
| Fresh cases | `<command to list fresh/used cases>` should show all fresh |
| Reset after a demo | `<command to reset all>` / `<command to reset named cases>`; <how long it takes> |
| Last resort | `<command to rebuild data>` (<what it wipes>) |
| Recorded demo | `<command to record the video>` (see the `wicked-garden-demo` `record` action) |

**Pre-flight, 10 minutes before:**
1. List cases; reset any that are not fresh.
2. Open the landing page as <PERSONA> and check it loads.
3. Pre-bake the slow steps marked below.
4. Open tabs: <list>.
5. Have ready: <files to upload, text to paste>.

---

## 3. Run of show: <N>-minute main path

Pre-bake: **<CASES>** (<which step>). Everything else runs live.

| Time | Segment | Case (fresh alternates) | Live calls / slow steps |
|---|---|---|---|
| 0:00 to <m:ss> | 1. <Title> | <case or page> | <none / 1 analysis (~<s> s)> |
| <m:ss> to <m:ss> | 2. <Title> | <case> (<alt>, <alt>) | <...> |

Short on time? <Which segments can be dropped and how the rest still flows.>

<!-- One block per segment, from the segment block template below -->

### Segment 1: <Title>

...

---

## 4. Run of show: <N>-minute short path

**Pre-bake:** <what to run beforehand, on alternates so the main-path cases stay fresh>.

| Time | Show | Case |
|---|---|---|
| 0:00 to <m:ss> | <what> | <case> |

---

## 5. Ways <PRODUCT> speeds up execution

| Accelerator | Manual work it replaces | Where it shows in the demo | Measured | Manual baseline (**estimate, team to validate**) |
|---|---|---|---|---|
| <Capability> | <task done by hand today> | Segment <N> | <seconds / counts, with source> | <range> |

---

## 6. Case bank

| Case | Story | Customer / entity | Demonstrates | State | Alternates |
|---|---|---|---|---|---|
| <KEY> | <one line> | <name> | <capability> | fresh | <KEY-B>, <KEY-C> |

---

## 7. Recovery tips

- **Slow step:** <what to say while it runs; where the pre-baked copy is>.
- **Result varies between runs:** <known variations and the line to use>.
- **Something went wrong mid-demo:** <switch to an alternate; reset command; how long it takes>.

---

## 8. Likely questions

| Question | Answer |
|---|---|
| Can it change records on its own? | <how human approval works, and where it is enforced> |
| Who can teach it new rules? | <proposal vs validation; separation of duties> |
| Is this real customer data? | <synthetic; what is simulated> |
| How do we know an answer is right? | <evidence, citations, deterministic checks> |

---

## Segment block template

### Segment <N>: <TITLE>

**Case:** <CASE-KEY>, <CUSTOMER / ENTITY>. Fresh alternates: **<ALT-1>**, **<ALT-2>**. Act as **<PERSONA>**.
<!-- Omit "Case" for read-only chapters and say "(read-only)" in the heading instead. -->

1. **Click:** <what to open or press, exact UI labels in bold>.
   **Say:** "<one or two sentences for the presenter>"
2. **Click:** **<Button>**. **Measured: <seconds> s** (<where measured: rehearsal / recording, date>).
3. **The audience sees:**
   - **<Section label>**: "<key sentence as shown on screen>"
   - **<Section label>**: <counts, statuses, what passed or failed>

- **What is happening under the hood:** <which parts are deterministic rules, which part the model does, what is
  written where, what is gated behind a person, what is audited>.
- **How this speeds up execution:** it replaces <manual work>. **Estimate:** <range> (team to validate).
  **Measured:** <seconds> s.

> <Optional rough-edge note: what may vary between runs and what to say if it does.>
