# Demo video QA checklist

Each item is **symptom → likely cause → fix** and a verdict: **[encode]** re-encode from the raw capture,
**[segment]** re-record that one segment, **[app]** fix the application. Timestamps come from the contact sheet labels.

## File and structure

- [ ] **Chapters missing, out of order or untitled** → stitch list or chapter metadata built from the wrong set of
  segment files → rebuild the chapter metadata from the segment order and restitch. [encode]
- [ ] **"Chapter N of M" disagrees with the real count** → chapters were added or removed after some segments were
  recorded; the number is baked into each segment's slide and progress bar → re-record every segment whose slide shows
  the old count. [segment]
- [ ] **Duration far longer or shorter than expected** → time-lapse spans not applied, or frame durations inflated by
  bursts of near-identical frames → resample to a constant frame rate (pick the newest frame at each output tick),
  re-apply the speed factors. [encode]
- [ ] **Stutter, judder or variable frame rate** → frames encoded with their raw capture durations → resample to a
  constant 30 fps before encoding. [encode]
- [ ] **Blurry text** → a low-bitrate recorder (browser automation built-in video is often ~1 Mbps VP8) → capture frames
  as high-quality JPEG/PNG and encode H.264 at low CRF, `yuv420p`, `+faststart`. [encode]

## Openings, joins and the end

- [ ] **Setup visible before a chapter slide** (login, persona menu, dashboard flash) → the slide was shown after setup
  instead of covering it → show the slide first, do setup behind it, trim the fade-in. [segment]
- [ ] **Hard cut from app to next chapter** → segment did not end on the plain background → end each segment with a
  short fade to the empty stage. [segment]
- [ ] **Closing card missing or cut short; last seconds frozen on the previous screen** → screen-change-driven capture
  emits no frames during a static hold, and the encoder ended at the last captured frame → end each segment at the
  moment recording stopped, not at the last frame. [encode]
- [ ] **Intro shows the app before the title card** → intro ran setup before its card → give the intro no setup, or
  cover it. [segment]

## Captions

- [ ] **Caption describes the previous screen** → caption set after the navigation → set the caption first with a short
  read time, then navigate. [segment]
- [ ] **Caption flashes by or lingers** → read time not matched to text length → roughly 2 s plus 35-40 ms per
  character, capped; hold longer on dense screens. [segment]
- [ ] **Old and new captions overlap during the change** → cross-fade with both visible → fade the old one out fully,
  then fade the new one in. [segment]
- [ ] **Claim in a caption doesn't match the screen** (count, name, case ID, a check that "passes" but shows failed) →
  script written from assumptions, or the model behaved differently this run → rewrite from what the screen shows, or
  fix the app if the screen is wrong. [segment] / [app]
- [ ] **Estimate presented as a measurement** → copy mixes planning numbers with recorded ones → only measured values
  in the video; estimates belong in the presenter script, labelled. [segment]

## Callouts and cursor

- [ ] **Callout box spills outside the app window or covers the caption band** → element taller than the viewport →
  clip the box to the visible viewport; for tall sections scroll the top into view instead of centring. [segment]
- [ ] **Callout around the wrong element** → ambiguous locator (first match was hidden, or text also matched a longer
  key such as `ITEM-01` vs `ITEM-01C`) → match exact keys, prefer role + name, pick visible matches. [segment]
- [ ] **Callout animates in from a corner** → position transition starting from 0,0 → place it without a transition on
  first show. [encode] if post-only, else [segment]
- [ ] **No cursor where something was clicked** → headless capture shows no pointer → draw a stage cursor and ripple on
  every click. [segment]

## Waits and pacing

- [ ] **Frozen picture with no badge** (dead air) → a model call, job or page load not wrapped in a time-lapse → wrap it
  and show the factor plus real elapsed time. [segment]
- [ ] **Time-lapse badge covers app controls** → badge placed over the app → put it in the window's title bar, never
  over the product UI. [segment]
- [ ] **A step never finishes on screen** (Approve stays disabled, results never appear) → UI doesn't refresh after
  background work → wait on the network response, reload as a fallback; also report the missing refresh. [segment] /
  [app]

## State, persona and chrome

- [ ] **Wrong user in the header for the chapter** → persona not set per segment → set it behind the opening slide.
  [segment]
- [ ] **Leftovers from another chapter** (records it created, approvals, filters, toasts) → segments share state →
  reset the data a segment uses before recording it; keep each segment self-contained. [segment]
- [ ] **Case already analysed / "used" when the story needs it fresh** → reset not run → reset, then re-record. [segment]
- [ ] **Long or wrapped address bar** (query strings, IDs) → full URL shown → show the path only, on one line. [segment]
- [ ] **Error page, crash, dev badge, debug overlay** → app bug or dev build → fix the app, record against a
  production build. [app]
- [ ] **Cluttered panel that buries the point** (dozens of irrelevant rows) → UI shows everything by default → collapse
  the noise in the product, not in the video. [app]

## Numbers

- [ ] **Closing-card timings don't match the timings file** → card rendered before the last re-record → re-record the
  segment that renders the card after all others. [segment]
- [ ] **Counts on screen differ between chapters** (e.g. "11 awaiting" then "12") → an earlier segment changed data →
  expected if the story caused it (say so); otherwise reset. [segment]

## After fixes

- [ ] Re-sheet only the changed segments plus the joins either side, and the end of the final file.
- [ ] Record the final duration, chapter list and measured timings next to the video for whoever presents it.
