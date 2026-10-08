// Walkthrough storyline lint (DES-walkthrough-proof §4.5; wicked-garden#1231).
//
//   wicked-garden run scripts/demo/walkthrough.mjs lint --root <author dir> [--storyline <path>]
//                                                       [--tree <dir>] [--steps <id,id,...>]
//
// The `walkthrough_plan` step's pinned validator runs this against the author dir the engine hands it
// (wicked-core `WALKTHROUGH_LINT_SCRIPT`: `--root "${WICKED_EVIDENCE_ROOT}"`, where that root is
// `<evidence root>/author/<plan step>`). It reads `<root>/storyline.mjs`, prints one JSON object
// `{ok, storyline, chapters, checks, findings: [{rule, where, detail}]}` on stdout and exits 0 only when
// there is no finding; 1 when there is at least one; 2 on a usage error.
//
// A check's `kind` is the record tool's collector (`runCollector` in walkthrough.mjs). The DES's check
// classes map onto them: locator = on_screen, probe/artifact = saved_state/events/side_effects/output,
// guard = must_not_happen, join = cross_check.

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

export const CHECK_CLASS = {
  locator: "on_screen",
  probe: "state",
  artifact: "state",
  guard: "must_not_happen",
  join: "cross_check",
};

/** The verifier the record tool hands the vault for a check (kept in step with walkthrough.mjs verifierForCheck). */
export function defaultVerifier(kind) {
  switch (kind) {
    case "locator": return { kind: "jq_pred", params: { expr: ".inner_text != null" } };
    case "probe": return { kind: "jq_pred", params: { expr: ".raw.exit_code == 0" } };
    case "artifact": return { kind: "jq_pred", params: { expr: ".sha256 != null" } };
    case "guard": return { kind: "jq_pred", params: { expr: "(.foreign_writes | length) == 0 and ((.console_errors // []) | length) == 0" } };
    case "join": return { kind: "jq_pred", params: { expr: ".joined | to_entries | all(.value != null)" } };
    default: return null;
  }
}

const SEGMENT_KEY = /^[a-z0-9][a-z0-9-]*$/;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const PLAIN_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
// Env names a storyline may not hand the fixture: credentials never reach the jailed app (§7).
const SECRET_ENV = /(SECRET|TOKEN|PASSWORD|PASSWD|PASSPHRASE|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIAL|AUTH)/i;
// Inline-code flags: `node -e`, `python -c`, `sh -c`, ... — the fixture must be a script the tree declares.
const INLINE_FLAGS = new Set(["-e", "-c", "--eval", "-p", "--print", "--command"]);
const SCRIPT_LIKE = /\.(?:m?js|cjs|ts|mts|py|sh|rb|pl)$/i;

function hasDotDot(p) { return /(?:^|[\\/])\.\.(?:[\\/]|$)/.test(p); }

/**
 * Lint a loaded storyline object. Pure apart from running `jq` for the negative samples.
 * @param {object} story the storyline's default export
 * @param {{tree?: string|null, steps?: string[]|null, jq?: string}} opts
 * @returns {{findings: {rule: string, where: string, detail: string}[], chapters: number, checks: number}}
 */
export function lintStoryline(story, { tree = null, steps = null, jq = "jq" } = {}) {
  const findings = [];
  const add = (rule, where, detail) => findings.push({ rule, where, detail });

  if (!story || typeof story !== "object") {
    add("storyline_shape", "default export", "the storyline's default export must be an object");
    return { findings, chapters: 0, checks: 0 };
  }

  // ---- baseUrl + fixture ------------------------------------------------------------------------------
  if (story.baseUrl !== "fixture") {
    add("base_url", "baseUrl", `baseUrl must be "fixture" (the record tool films the fixture it starts), got ${JSON.stringify(story.baseUrl)}`);
  }
  const fixture = story.fixture;
  if (!fixture || typeof fixture !== "object") {
    add("fixture_start", "fixture", "fixture is required: { start: [argv], ready, probes?, env? }");
  } else {
    const start = fixture.start;
    if (!Array.isArray(start) || start.length === 0 || !start.every((a) => typeof a === "string" && a.length > 0)) {
      add("fixture_start", "fixture.start", "fixture.start must be a non-empty argv array of strings (no shell)");
    } else {
      for (const arg of start.slice(1)) {
        if (INLINE_FLAGS.has(arg)) add("fixture_start", "fixture.start", `inline code (${arg}) is refused: start a script the tree declares`);
      }
      for (const arg of start) {
        if (path.isAbsolute(arg) || /^[A-Za-z]:[\\/]/.test(arg)) add("fixture_start", "fixture.start", `${JSON.stringify(arg)} is an absolute path; the fixture runs from app/ (the tree)`);
        else if (hasDotDot(arg)) add("fixture_start", "fixture.start", `${JSON.stringify(arg)} leaves app/ (the tree)`);
      }
      if (tree) {
        for (const arg of start.slice(1)) {
          if (arg.startsWith("-") || path.isAbsolute(arg) || hasDotDot(arg)) continue;
          if (!(arg.includes("/") || SCRIPT_LIKE.test(arg))) continue;
          if (!fs.existsSync(path.join(tree, arg))) add("fixture_start", "fixture.start", `${JSON.stringify(arg)} is not in the tree (${tree})`);
        }
      }
    }
    if (fixture.env !== undefined) {
      if (!fixture.env || typeof fixture.env !== "object" || Array.isArray(fixture.env)) {
        add("fixture_env", "fixture.env", "fixture.env must be an object of name: value");
      } else {
        for (const name of Object.keys(fixture.env)) {
          if (SECRET_ENV.test(name)) add("secret_env", `fixture.env.${name}`, "a secret-shaped env name is refused: no credential reaches the jailed app");
        }
      }
    }
    if (fixture.probes !== undefined && (!fixture.probes || typeof fixture.probes !== "object" || Array.isArray(fixture.probes))) {
      add("fixture_probes", "fixture.probes", "fixture.probes must be an object of name: argv");
    }
  }
  const probes = fixture && typeof fixture.probes === "object" && fixture.probes ? fixture.probes : {};

  // ---- segments ---------------------------------------------------------------------------------------
  const segments = Array.isArray(story.segments) ? story.segments : null;
  if (!segments) {
    add("segments", "segments", "segments must be an array");
    return { findings, chapters: 0, checks: 0 };
  }
  const chapters = segments.filter((s) => s && !s.intro);
  if (chapters.length === 0) add("segments", "segments", "the storyline has no chapter (an empty plan proves nothing)");

  const seenKeys = new Set();
  let checkCount = 0;
  let mustNotHappen = 0;

  segments.forEach((seg, i) => {
    const where = `segments[${i}]${seg && typeof seg.key === "string" ? ` (${seg.key})` : ""}`;
    if (!seg || typeof seg !== "object") { add("segment_shape", where, "a segment must be an object"); return; }
    if (!SEGMENT_KEY.test(String(seg.key ?? ""))) add("segment_key", where, `key ${JSON.stringify(seg.key)}: lowercase letters, digits and hyphens only`);
    else if (seenKeys.has(seg.key)) add("segment_key", where, `key ${JSON.stringify(seg.key)} is used twice`);
    seenKeys.add(seg.key);
    if (typeof seg.run !== "function") add("segment_run", where, "run(ctx) must be a function");
    if (seg.intro) return;

    // proves: plan step ids
    if (!Array.isArray(seg.proves) || seg.proves.length === 0) {
      add("proves", where, "proves[] must name at least one plan step id");
    } else {
      for (const id of seg.proves) {
        if (typeof id !== "string" || !PLAIN_ID.test(id)) add("proves", where, `proves id ${JSON.stringify(id)} is not a plain step id`);
        else if (steps && !steps.includes(id)) add("proves", where, `proves id ${JSON.stringify(id)} is not a step of the plan (${steps.join(", ")})`);
      }
    }

    const checks = Array.isArray(seg.checks) ? seg.checks : null;
    if (!checks || checks.length === 0) { add("chapter_checks", where, "a chapter needs checks[]"); return; }
    const byId = new Map();
    const classes = { on_screen: [], state: [], must_not_happen: [], cross_check: [] };

    checks.forEach((c, j) => {
      const cw = `${where}.checks[${j}]${c && typeof c.id === "string" ? ` (${c.id})` : ""}`;
      if (!c || typeof c !== "object") { add("check_shape", cw, "a check must be an object"); return; }
      checkCount += 1;
      if (!SAFE_ID.test(String(c.id ?? ""))) add("check_id", cw, `id ${JSON.stringify(c.id)}: letters, digits, '.', '_' and '-' only`);
      else if (byId.has(c.id)) add("check_id", cw, `id ${JSON.stringify(c.id)} is used twice in this chapter`);
      const cls = CHECK_CLASS[c.kind];
      if (!cls) { add("check_kind", cw, `kind ${JSON.stringify(c.kind)} is not one of ${Object.keys(CHECK_CLASS).join(", ")}`); return; }
      classes[cls].push(c.id);
      if (cls === "must_not_happen") mustNotHappen += 1;

      // Collector inputs
      if (c.kind === "locator" && (typeof c.selector !== "string" || !c.selector.trim())) add("check_selector", cw, "a locator check needs a selector");
      if (c.kind === "probe") {
        if (typeof c.name !== "string" || !c.name) add("check_probe", cw, "a probe check needs name (a key of fixture.probes)");
        else if (!Object.prototype.hasOwnProperty.call(probes, c.name)) add("check_probe", cw, `probe ${JSON.stringify(c.name)} is not in fixture.probes`);
        if (c.parse !== undefined && !["json", "jsonl", "sqlite-json", "text"].includes(c.parse)) add("check_probe", cw, `parse ${JSON.stringify(c.parse)} is not json | jsonl | sqlite-json | text`);
      }
      if (c.kind === "artifact") {
        const p = c.path;
        if (typeof p !== "string" || !p) add("check_artifact", cw, "an artifact check needs path (relative to DATA_DIR)");
        else if (path.isAbsolute(p) || hasDotDot(p)) add("check_artifact", cw, `artifact path ${JSON.stringify(p)} escapes DATA_DIR`);
      }
      if (c.kind === "join") {
        const src = Array.isArray(c.sources) ? c.sources : [];
        if (src.length < 2) add("check_join", cw, "a join needs sources[] naming at least two earlier checks");
        for (const s of src) if (!byId.has(s)) add("check_join", cw, `source ${JSON.stringify(s)} is not an earlier check of this chapter`);
      }

      // Verifier + negative samples (S3): the verifier must FAIL on every sample.
      const verifier = c.verify === undefined ? defaultVerifier(c.kind) : c.verify;
      const expr = verifier?.params?.expr;
      if (!verifier || verifier.kind !== "jq_pred" || typeof expr !== "string" || !expr.trim()) {
        add("check_verify", cw, "verify must be { kind: \"jq_pred\", params: { expr } } — the one verifier the record tool hands the vault");
      } else {
        const negs = c.negative;
        if (!Array.isArray(negs) || negs.length === 0) {
          add("negative_missing", cw, "every check needs at least one negative sample (a capture its verifier must FAIL)");
        } else {
          negs.forEach((sample, k) => {
            const r = spawnSync(jq, ["-e", expr], { input: JSON.stringify(sample), encoding: "utf8", timeout: 10_000 });
            if (r.error) add("negative_unverified", `${cw}.negative[${k}]`, `jq could not run (${r.error.code ?? r.error.message}); the lint fails closed`);
            else if (r.status === 0) add("negative_passes", `${cw}.negative[${k}]`, `the verifier \`${expr}\` PASSES this sample, so the check cannot fail (a tautology)`);
            else if (r.status !== 1 && r.status !== 4) add("check_verify", cw, `jq rejected \`${expr}\` (exit ${r.status}): ${(r.stderr || "").trim().slice(0, 200)}`);
          });
        }
      }
      byId.set(c.id, c);
    });

    if (classes.on_screen.length === 0) add("chapter_on_screen", where, "a chapter needs at least one on_screen check (kind: locator)");
    if (classes.state.length === 0) add("chapter_state", where, "a chapter needs at least one saved_state/events/side_effects/output check (kind: probe or artifact)");
    if (classes.on_screen.length && classes.state.length) {
      const joined = checks.some((c) => c?.kind === "join" && Array.isArray(c.sources)
        && c.sources.some((s) => classes.on_screen.includes(s)) && c.sources.some((s) => classes.state.includes(s)));
      if (!joined) add("chapter_cross_check", where, "a chapter with on_screen and state checks needs a join (cross_check) whose sources include one of each");
    }
  });

  if (chapters.length && mustNotHappen === 0) add("must_not_happen", "segments", "the walkthrough needs at least one must_not_happen check (kind: guard)");

  return { findings, chapters: chapters.length, checks: checkCount };
}

/** The `lint` action: resolve, import and lint the storyline; print the report; return the exit code. */
export async function lintAction({ root, storyline, tree, steps }) {
  const storyPath = storyline ? path.resolve(storyline) : root ? path.join(path.resolve(root), "storyline.mjs") : null;
  const report = (findings, extra = {}) => {
    const out = { ok: findings.length === 0, storyline: storyPath, chapters: 0, checks: 0, ...extra, findings };
    process.stdout.write(JSON.stringify(out) + "\n");
    for (const f of findings) process.stderr.write(`lint: ${f.rule} at ${f.where}: ${f.detail}\n`);
    return findings.length === 0 ? 0 : 1;
  };
  if (!storyPath) {
    process.stderr.write("usage: walkthrough.mjs lint --root <author dir> [--storyline <path>] [--tree <dir>] [--steps <id,...>]\n");
    return 2;
  }
  let st;
  try { st = fs.statSync(storyPath); } catch {
    return report([{ rule: "storyline_missing", where: storyPath, detail: "no storyline here: the walkthrough_plan author writes <author dir>/storyline.mjs" }]);
  }
  if (!st.isFile()) return report([{ rule: "storyline_missing", where: storyPath, detail: "not a regular file" }]);
  let story;
  try {
    story = (await import(pathToFileURL(storyPath).href)).default;
  } catch (e) {
    return report([{ rule: "storyline_unloadable", where: storyPath, detail: String(e?.message ?? e).split("\n")[0] }]);
  }
  const { findings, chapters, checks } = lintStoryline(story, { tree: tree ? path.resolve(tree) : null, steps });
  return report(findings, { chapters, checks });
}
