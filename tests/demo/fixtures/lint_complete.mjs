// Test helper (wicked-garden#1240): make a recorder-test storyline pass the walkthrough lint.
//
// `record` re-runs the lint (DES-walkthrough-proof §4.4 step 1) and refuses a storyline with any
// finding, so a recorder test that wants to exercise ONE collector or verdict path still has to hand it
// a complete storyline. `lintComplete(story)` fills in only what the test does not care about, after
// the test's own checks so their order and timing are untouched:
//
//   - every check without `negative` gets one sample its verifier must fail (NEGATIVE[kind]; a custom
//     verify expr keeps the kind's sample, which the test then has to choose so it fails);
//   - every chapter without a check of a class gets a passing one (pad_screen locator on #status,
//     pad_state probe, and pad_join over one of each), checked after the chapter's own run();
//   - a walkthrough without a guard gets pad_guard on its first chapter;
//   - an empty `proves` becomes ["p1"]; a missing `baseUrl` becomes "fixture" (record films the
//     fixture it starts whatever the storyline says).
//
// The pad checks pass on the fixture app (tests/demo/fixtures/app.mjs + probe.mjs), so a chapter's
// verdict stays the one its own checks earn.

export const NEGATIVE = Object.freeze({
  locator: { inner_text: null },
  probe: { raw: { exit_code: 1 } },
  artifact: { sha256: null },
  guard: { foreign_writes: ["POST http://elsewhere.invalid/"], console_errors: [] },
  join: { joined: { missing: null } },
});

const SCREEN = new Set(["locator"]);
const STATE = new Set(["probe", "artifact"]);

export function lintComplete(story) {
  if (story.baseUrl === undefined) story.baseUrl = "fixture";
  const fixture = story.fixture ?? {};
  story.fixture = fixture;
  const segments = Array.isArray(story.segments) ? story.segments : [];
  let guarded = segments.some((s) => !s?.intro && (s?.checks ?? []).some((c) => c?.kind === "guard"));

  for (const seg of segments) {
    if (!seg || seg.intro) continue;
    if (!Array.isArray(seg.proves) || seg.proves.length === 0) seg.proves = ["p1"];
    const checks = Array.isArray(seg.checks) ? seg.checks : (seg.checks = []);
    const pads = [];
    let screen = checks.find((c) => SCREEN.has(c?.kind))?.id;
    // The join's state source is the chapter's own probe or artifact (an artifact joins as its
    // sha256 since garden#1246).
    let state = checks.find((c) => STATE.has(c?.kind))?.id;
    if (!screen) { screen = "pad_screen"; pads.push({ id: screen, kind: "locator", selector: "#status" }); }
    if (!state) {
      state = "pad_state";
      fixture.probes = { ...(fixture.probes ?? {}), pad_probe: ["node", "probe.mjs"] };
      pads.push({ id: state, kind: "probe", name: "pad_probe" });
    }
    const joined = checks.some((c) => c?.kind === "join" && Array.isArray(c.sources)
      && c.sources.some((s) => checks.some((k) => k.id === s && SCREEN.has(k.kind)))
      && c.sources.some((s) => checks.some((k) => k.id === s && STATE.has(k.kind))));
    if (!joined) pads.push({ id: "pad_join", kind: "join", sources: [screen, state] });
    if (!guarded) { pads.push({ id: "pad_guard", kind: "guard" }); guarded = true; }

    checks.push(...pads);
    for (const c of checks) if (c && typeof c === "object" && c.negative === undefined) c.negative = [NEGATIVE[c.kind] ?? {}];

    if (pads.length && typeof seg.run === "function") {
      const run = seg.run;
      seg.run = async function padded(ctx) {
        await run.call(this, ctx);
        for (const p of pads) await ctx.check(p.id);
      };
    }
  }
  return story;
}
