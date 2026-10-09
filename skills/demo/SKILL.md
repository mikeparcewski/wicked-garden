---
name: wicked-garden-demo
description: |
  Product demo domain: plan, record and review a polished demo video.
  plan — frames the audience, builds the story, picks hero cases and fresh
  alternates, runs a live rehearsal with measured timings, and writes a
  presenter script with a chapter list ready for recording.
  record — records each chapter as its own captioned, chaptered segment via
  Playwright + ffmpeg (DevTools screencast encoded live to H.264, no frame
  files on disk, final CRF 17), then stitches them into one MP4 with chapters.
  review — generates labelled contact sheets of stills (at chapter slides,
  joins, and the end) and delivers a per-issue verdict: re-encode, re-record
  one segment, or fix the app.

  Use when: "plan a demo", "demo script", "presenter notes", "run of show",
  "rehearse a demo", "record a demo video", "walkthrough video", "feature
  tour", "re-record a segment", "stitch segments", "review the demo video",
  "QA the recording", "contact sheet", "demo workflow", "offline demo",
  "walkthrough storyline", "walkthrough lint", "walkthrough_plan".
metadata:
  role: router
  phases: "*"
  archetypes: "*"
---

# Demo

Plan a chapter-by-chapter demo story, record it chapter by chapter with captions
and callouts, then review with contact sheets — three actions, one domain.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## Routing

| Action | When | How |
|--------|------|-----|
| `plan` | No chapter list yet; first time or after a product change | Inline — follow § plan below |
| `record` | Chapter list and case bank exist; recording or re-recording | Script-backed — `wicked-garden run scripts/demo/record.mjs` |
| `review` | A recording exists and needs QA | Script-backed — `wicked-garden run scripts/demo/contact_sheet.py` |

## Action: plan

A good demo is a story the audience can follow, told with cases that behave the same
way every time, and numbers that were actually measured. **Do not write the script
before the rehearsal** — the script describes what the audience will actually see.

Produces: `<product>-demo-script.md` and a chapter list ready for the `record` action.

### 1. Frame it

Establish and write down:

- **Audience**: who watches, what they already know, what decision the demo should help them make.
- **Pitch**: one paragraph — the problem today, what the product does about it, and the guardrail.
- **Use case**: three sentences a listener could repeat (typical request → what the product does → outcome).
- **Capabilities**: a flat list of what the product can show. Each capability that matters to this audience becomes a chapter.

### 2. Build the story

One chapter per capability, ordered so each raises the stakes of the last:

| # | Chapter | Purpose |
|---|---------|---------|
| 1 | Triage / landing | "Here is my day": what needs attention, ranked |
| 2 | Core flow, end to end | One clean case from intake to done |
| 3-4 | Hard cases | Messy input, missing information, exceptions |
| 5 | Learning / governance | How the product gets smarter safely |
| 6 | Knowledge / trust | Where the rules come from, how results trace back |
| 7 | 360 view | Everything about one customer or entity |
| 8 | Wrap-up | Audit trail and measured numbers |

Keep chapters self-contained — each starts from a known page and uses its own cases.
Details and caption voice: `refs/storytelling.md`.

### 3. Choose the cases

- **Truth first**: use scenarios whose expected outcome you know in advance (the finding it
  should raise, the plan it should produce). Seeded or synthetic data with an answer key.
- **One hero case per chapter** plus **fresh alternates** (same story, different names and numbers).
- **Mark state-consuming chapters** (those that analyze, approve, upload, or teach). Prefer read-only.
- Record the case bank as a table: case, story, entity, what it demonstrates, fresh/used, alternates.

### 4. Make it repeatable

Before rehearsing, ensure the demo can be put back exactly as it was:

- A **per-case reset** command that rewinds only the named cases.
- A **fresh/used listing** so the presenter can check readiness in seconds.
- **Deterministic data** (seeded generation, cached model text).
- A **pre-flight checklist**: services and URLs, environment/dataset, business date, persona, fresh cases, files, tabs.
- **Pre-bake** slow steps for live sessions; say so in the script.

If a reset does not exist, build or request it first — it is the difference between a demo and a one-off.

### 5. Rehearse live

Run every chapter the way the UI does it against the real system and log as you go.
Full procedure: `refs/rehearsal.md`.

- **Time every step** (wall clock) and keep the raw numbers.
- **Capture what the audience sees**: exact labels, counts, the key sentence of each result.
- **Log rough edges** with the case key; triage each: fix it, script around it, or drop the chapter.
- **Reset afterwards** and confirm every case is fresh again.

### 6. Keep claims honest

- **Measured** means timed in a rehearsal or recording on this system; say where and when.
- **Estimate** means a manual-baseline guess; label it "estimate, team to validate" every time.
- Say plainly which systems are **simulated** and that the data is **synthetic**.
- Show the guardrail every time you show automation: who approved, what was refused and why.

### 7. Write the presenter script

Use the templates in `refs/templates.md`:
- The **presenter-script template** provides the overall document structure (pitch, setup, run of show,
  case bank, recovery tips, Q&A).
- The **segment block template** covers each chapter (case, click, say, audience sees, under the hood,
  speed-up, rough-edge note).

Style: skimmable. Tables and short bullets, exact UI labels in **bold**, quotes in *italics*, one idea per line.

### 8. Keep it in sync, then hand off to record

- **Keep the script in sync with rehearsal changes**: after any fix lands, update the affected segment and add a
  **Changes since the rehearsal** block at the top of the script — what changed, whether it was seen in a browser,
  and which timings predate it.
- Re-rehearse chapters whose behaviour changed; replace numbers only with new measurements.

For each chapter write:
- **Key**: `NN-slug` (`01-dashboard`) — stable, used for files and re-recording.
- **Title**: 2-6 words, sentence case.
- **Blurb**: one sentence that states what the chapter proves.
- **Tags**: 2-5 capability chips.
- **Resets**: the cases it changes.

That list becomes the `segments` array in the storyline file for the `record` action.

### Checklist (acceptance gate)

`plan` is done only when every item is checked:

- [ ] Audience, pitch, three-sentence use case written
- [ ] Capabilities listed; one chapter each, ordered as a story
- [ ] Hero case + fresh alternates per chapter; state-consuming chapters marked
- [ ] Per-case reset and fresh/used listing work; pre-flight written
- [ ] Every chapter rehearsed live; timings and audience-visible results logged; rough edges triaged
- [ ] Script written from the template; measured vs estimate labelled everywhere
- [ ] Cases reset and confirmed fresh after rehearsal
- [ ] Chapter list ready for recording (keys, titles, blurbs, tags, resets)

---

## Action: record

Turn the chapter list into a captioned, chaptered MP4 that looks produced rather than screen-grabbed.
Requires: Node.js ≥ 20, ffmpeg and ffprobe on PATH (or `FFMPEG=/path/to/ffmpeg`),
and the web app running and reachable.

### Install (once per machine)

```sh
wicked-garden run scripts/demo/setup.mjs
```

Confirm: `ffmpeg -version` and `ffprobe -version` both work.

### Write the storyline

Copy `assets/example-storyline.mjs` next to your project (e.g. `demo/storyline.mjs`) and
replace the segments. Keep each segment self-contained: it starts from `startPath`, resets its
own data in `beforeSegment`, and never relies on another segment's state.

Full module shape and the `ctx` API: `refs/storyline-api.md`.
Visual system (stage layout, captions, callouts, chapter slides, time-lapse): `refs/stage-design.md`.

### Walkthrough author (a crew run's `walkthrough_plan` step)

When a governed run hands you the `walkthrough_plan` step, the storyline is the proof the builder's work is
judged by, not a demo. Write exactly one file, `<author dir>/storyline.mjs` — the path your step prompt names
(`<evidence root>/author/<your step id>/`); write nothing in the worktree. The step's pinned validator lints it:

```sh
wicked-garden run scripts/demo/walkthrough.mjs lint --root <author dir> [--tree <worktree>] [--steps <plan step ids>]
```

Exit 0 means no finding; exit 1 prints `{ok, storyline, findings: [{rule, where, detail}]}` — fix each and lint
again until it exits 0. The rules, in short: `baseUrl: "fixture"`; `fixture.start` is an argv starting a script
the tree declares (no `-e`/`-c`, nothing outside the tree, no secret-shaped env name); every chapter `proves` plan
step ids and has a `locator` check, a `probe` or `artifact` check, and a `join` of the two; the walkthrough has a
`guard` check; every check carries `negative` samples its `jq_pred` verifier FAILS on. The record tool
(`walkthrough_review`) reads the same file through `WICKED_WALKTHROUGH_AUTHOR` and re-runs the lint first: a
finding refuses the recording (`storyline_refused`). Full rules and a passing
example: `refs/walkthrough-author.md`.

### Probe selectors (read-only)

Before writing `run()` bodies, load each page without clicking to confirm every locator:

```sh
wicked-garden run scripts/demo/probe.mjs <baseUrl> /page1 /page2
```

Saves a screenshot and lists headings, sections, buttons with ARIA roles, inputs and links.

### Record

```sh
wicked-garden run scripts/demo/record.mjs <storyline.mjs>              # record missing segments, then stitch
wicked-garden run scripts/demo/record.mjs <storyline.mjs> 03-search    # (re)record one segment, restitch
wicked-garden run scripts/demo/record.mjs <storyline.mjs> --all        # re-record everything
wicked-garden run scripts/demo/record.mjs <storyline.mjs> --stitch     # stitch existing segments only
wicked-garden run scripts/demo/record.mjs <storyline.mjs> --reencode   # re-cut from each segment's saved master, restitch
wicked-garden run scripts/demo/record.mjs <storyline.mjs> --list       # which segments are recorded
```

Options: `--out <dir>` (default `demo-video/` next to the storyline), `--fixture-origin <origin>` (see below).
Environment: `FFMPEG`, `DEMO_BASE_URL`, `DEMO_HEADFUL=1`, `DEMO_KEEP_FRAMES=1` (debugging only, see below).

**Encoded while it records; no frame files.** The screencast is fed to ffmpeg at 30 fps as the take runs and lands
as `segments/<key>/capture.mp4`, a near-lossless H.264 master (CRF 12, one-second fragments) whose frame k is the
picture at t0 + k/30; the segment video is a cut of that master (opening trim, time-lapsed waits, chapters, CRF 17).
A take leaves about two videos' worth of bytes, not a JPEG per frame (which was ~8 MB/s, ~5 GB per 10-minute take).
A take that is killed still leaves a master that plays up to its last complete second, and the timeline written so
far, so `--reencode` can cut it. `DEMO_KEEP_FRAMES=1` additionally writes every screencast frame to
`segments/<key>/frames/` (with timestamps in `timeline.json`) to look at what the screencast delivered — use it on a
short take only; the master is still what gets cut.

**Read-only by default.** While it records, the browser sends no writes: every request that is not
GET, HEAD or OPTIONS is aborted, and so is every WebSocket frame the page sends (frames the server pushes
still arrive). The segment fails `side_effect_blocked`, naming each request. Service workers are blocked
while recording. So a recording can never launch, approve, create or delete anything on the app it films.
Show a control without pressing it.

**The one door: `--fixture-origin`.** To film writes, start a disposable app for the demo (a fixture
server, a scratch database) on a loopback port and name its origin, e.g.
`--fixture-origin http://127.0.0.1:4310`. Writes and page WebSocket frames to exactly that origin (scheme,
host and port) pass; a write to any other origin is still aborted and listed. A non-loopback origin is
refused before recording. Never point it at a live system someone else uses. There is no environment
switch. `recording.json` records how each stitched segment was recorded (`read-only` or
`fixture-writable`), and each segment's `guard.json` names the origin.

**A failed take keeps its evidence.** When a take fails (an error, or a blocked write), its timeline,
a video cut from the master it has, and `failure.json` (the error, any blocked requests,
`failed_at_sec`) are kept in `segments/<key>/failed-<take>/`. Nothing of it is left where a stitch could
use it: the segment's old `segment.mp4` is deleted, and while any segment's last take failed, `--reencode`
and `--stitch` refuse to run (`failed_take`, or `side_effect_blocked` for a blocked write). Re-record it
(or remove its directory) first.

Record one segment first, review its stills with the `review` action, then record the rest.

### Restore the app

Reset whatever the recording consumed (run the per-case reset for every segment's `resets`) so the live demo
starts fresh, and confirm the cases list as fresh again.

Deliverable: `<out>/<slug>.mp4` (stitched), `chapters.md`, `timings.json`, `recording.json`, `segments/<key>/`.

Hard-won failure modes and fixes: `refs/gotchas.md`.

### Before you call it done (acceptance gate)

`record` is done only when every item is checked:

- [ ] Every segment probed read-only, then recorded without errors; `--list` shows all recorded.
- [ ] Stills reviewed: opening slides, each caption against its picture, callouts on target, joins, closing card.
- [ ] No caption claims something the video doesn't show; waits are badged; the closing card shows measured numbers.
- [ ] Simulated systems and synthetic data are labelled where the audience could mistake them for real.
- [ ] Recorded read-only (`recording.json` says `"readOnly": true`), unless the target is disposable.
- [ ] The app's data is reset afterwards; services you didn't start are still running.
- [ ] The MP4 plays from start to end with chapters (`ffprobe -show_chapters <file>`).

---

## Action: review

Review a recording by looking at stills, not by watching the whole video. A few targeted
contact sheets catch almost every defect in minutes and give exact timestamps to report.

### Contact sheets

```sh
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --chapters        # ~2 s into every chapter
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --chapters --offset 8  # first content of each chapter
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --joins           # just before + after every boundary
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --end             # last seconds: closing card held?
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --every 20 --cols 4    # survey
wicked-garden run scripts/demo/contact_sheet.py <video.mp4> --at 1:02,1:05   # zoom in on a moment
wicked-garden run scripts/demo/contact_sheet.py segments/05/segment.mp4 --every 8  # one segment alone
```

Options: `--offset` (seconds into each chapter, default 2), `--join-gap` (seconds either side of a boundary for
`--joins`, default 0.6), `--end-span` (seconds before the end for `--end`, default 6), `--cols` (tiles per row,
default 3), `--width` (tile width in px, default 640), `--out` (output PNG; default `<video>-sheet.png` next to the
video). Full list: `wicked-garden run scripts/demo/contact_sheet.py --help`.

Also check format: `ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -show_chapters <video.mp4>`.

### Review passes (in this order)

1. **Structure** (`--chapters`, ffprobe): every chapter present, in order, titled, 1920x1080 H.264.
2. **Joins** (`--joins`): plain background → next chapter slide, no setup flash.
3. **The end** (`--end`): closing card present and **held** for its full duration.
4. **Survey** (`--every 20`, then `--at` around anything odd): caption sync, callouts, cursor, waits, state.
5. **Numbers**: timings on the closing card match `timings.json` and what the app shows.

Full per-item checklist with causes and fixes: `refs/review-checklist.md`.

### Verdicts

Classify every finding before fixing anything:

| Verdict | When | Fix |
|---------|------|-----|
| **Re-encode** | Timing, trimming, speed-up, frame rate, chapter metadata, missing end hold | Rebuild from saved raw capture — no re-recording (`--reencode`) |
| **Re-record one segment** | Wrong caption, callout, stale data, wrong persona, unannotated wait | Fix the storyline for that segment, reset its data, record only it, restitch |
| **Fix the app** | Errors, crashes, stale UI, wrong numbers, confusing copy | Fix and rebuild, then re-record affected segments. Report to the product owner too |

Report findings as: `timestamp · chapter · what's wrong · verdict`.
Re-review only the changed segments plus the joins on either side, then run `--end` again.

Deliverable: contact-sheet PNGs + findings table with verdicts.

### Checklist (acceptance gate)

`review` is done only when every item is checked:

- [ ] All five review passes run, in order, on the final file.
- [ ] Every finding reported as `timestamp · chapter · what's wrong · verdict`.
- [ ] After fixes: changed segments and the joins on either side re-reviewed, and `--end` run again.

---

## References

- `refs/storytelling.md` — chapter design, ordering, metadata (keys, blurbs, tags), caption voice, honest claims
- `refs/rehearsal.md` — rehearsal procedure: how to drive it, what to log, rough-edge triage, post-rehearsal
- `refs/templates.md` — presenter-script template and per-segment block template
- `refs/stage-design.md` — the visual system: layout, typography, captions, callouts, chapter slides, time-lapse badge
- `refs/storyline-api.md` — storyline module shape, all `ctx` methods, rules of thumb
- `refs/walkthrough-author.md` — the `walkthrough_plan` author contract: where the storyline goes, every lint rule, a passing example
- `refs/gotchas.md` — failure modes and fixes: capture, clicking, scrolling, timing, environment
- `refs/review-checklist.md` — full QA checklist with symptom → cause → fix → verdict per item
