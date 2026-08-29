/**
 * src/lint.mjs — the spec lint (TH-4 non-configurable default #3).
 *
 * A spec that fails lint NEVER executes. The lint enforces the executor
 * doctrine mechanically:
 *
 *  - NO fixed sleeps. There is no sleep/delay/pause action in the runner
 *    vocabulary, and the lint rejects any attempt to smuggle one in
 *    (`sleep_ms`, `delay_ms`, `wait_ms` keys included). Waiting is always
 *    wait-on-condition (`waitFor`, `waitForText`, `expectWire`,
 *    `expectNewWire`) with a timeout CAP (`timeout_ms`), never a floor.
 *  - NO status-only assertions. An assertion that checks an HTTP status and
 *    nothing else proves reachability, not behavior. Every wire/readBack
 *    assertion carrying `status` must also carry a content check
 *    (`json_path` + equals/matches/contains, or `body_contains`), and the
 *    spec as a whole must contain at least one content-bearing assertion.
 *  - NO viewport override. 1440x700 is pinned in the runner.
 *  - Deterministic vocabulary only: unknown actions/assertion types are
 *    rejected (no free-form JS in specs — the runner is model-free AND
 *    eval-free).
 */

export const STEP_ACTIONS = new Set([
  "goto",
  "waitFor",
  "waitForText",
  "click",
  "fill",
  "press",
  "screenshot",
  "readBack",
  "expectWire",
  "expectNewWire",
]);

export const ASSERTION_TYPES = new Set([
  "wire",
  "ws",
  "readBack",
  "pageText",
  "console",
  "dbAssert",
  "cliCrossCheck",
]);

/**
 * Claim levels a spec may PLAN (TH-5/TH-6): mirrors wicked-ledger
 * lib/manifest.mjs CLAIM_LEVELS minus "skipped", which is outcome-only —
 * a plan that schedules a skipped leg is a plan not to test. Duplicated
 * deliberately: "./lint" is exported dependency-free.
 */
export const PLANNABLE_CLAIM_LEVELS = new Set(["certified", "machinery-verified"]);
const CLAIM_RANK = { certified: 2, "machinery-verified": 1 };

const FORBIDDEN_ACTIONS = new Set(["sleep", "delay", "pause", "wait", "waitForTimeout"]);
const FORBIDDEN_KEYS = /^(sleep|delay|wait|pause)_?ms$/i;

const CONTENT_KEYS = ["json_path", "equals", "matches", "contains", "not_contains", "body_contains"];

function hasContentCheck(a) {
  if (CONTENT_KEYS.some((k) => a[k] !== undefined)) return true;
  // Whole-table/value expectations are content checks too.
  if (a.type === "dbAssert" && a.expect && ("value" in a.expect || "rows" in a.expect || "min_rows" in a.expect)) return true;
  if (a.type === "cliCrossCheck" && (a.expect_equals !== undefined || a.expect_matches !== undefined || a.compare_to !== undefined)) return true;
  if (a.type === "ws" && a.first_frame_matches !== undefined) return true;
  return false;
}

/**
 * Lint a parsed spec. Returns `{ ok: boolean, errors: string[] }` — never
 * throws, so callers can render every violation at once.
 */
export function lintSpec(spec) {
  const errors = [];
  const err = (msg) => errors.push(msg);

  if (!spec || typeof spec !== "object") {
    return { ok: false, errors: ["spec must be a JSON object"] };
  }
  if (spec.spec_version !== "1.0") err(`spec_version must be "1.0" (got ${JSON.stringify(spec.spec_version)})`);
  if (!spec.scenario || typeof spec.scenario.id !== "string" || !spec.scenario.id) err("scenario.id is required");
  if (!spec.scenario || typeof spec.scenario.name !== "string" || !spec.scenario.name) err("scenario.name is required");
  if (!spec.scenario || typeof spec.scenario.project !== "string" || !spec.scenario.project) err("scenario.project is required");
  if (!spec.target || typeof spec.target.base_url !== "string" || !spec.target.base_url) err("target.base_url is required");

  // TH-6: planned claim ceilings for the manifest-2.1 scenario_evidence block.
  const claimLevel = spec.scenario?.claim_level;
  if (claimLevel !== undefined && !PLANNABLE_CLAIM_LEVELS.has(claimLevel)) {
    err(`scenario.claim_level must be one of ${[...PLANNABLE_CLAIM_LEVELS].join("|")} ("skipped" is outcome-only) — got ${JSON.stringify(claimLevel)}`);
  }
  const legs = spec.scenario?.legs;
  if (legs !== undefined) {
    if (!Array.isArray(legs) || legs.length === 0) {
      err("scenario.legs must be a non-empty array when present");
    } else {
      let weakest = Infinity;
      legs.forEach((l, i) => {
        const where = `scenario.legs[${i}]`;
        if (!l || typeof l !== "object" || typeof l.leg !== "string" || !l.leg) {
          err(`${where}: requires a non-empty "leg" name`);
          return;
        }
        if (!PLANNABLE_CLAIM_LEVELS.has(l.claim_level)) {
          err(`${where}: claim_level must be one of ${[...PLANNABLE_CLAIM_LEVELS].join("|")} — got ${JSON.stringify(l.claim_level)}`);
          return;
        }
        weakest = Math.min(weakest, CLAIM_RANK[l.claim_level]);
      });
      // Honest-cap invariant (certify the journey, not the proxy): the
      // scenario-level claim can never be STRONGER than its weakest leg.
      const overall = CLAIM_RANK[claimLevel ?? "machinery-verified"];
      if (Number.isFinite(weakest) && overall !== undefined && overall > weakest) {
        err(`scenario.claim_level "${claimLevel}" is stronger than the weakest leg — cap it at the legs' floor (certify the journey, not the proxy)`);
      }
    }
  }

  // Non-configurable defaults: reject configuration attempts loudly rather
  // than ignoring them (silent ignoring teaches specs to lie).
  if (spec.target?.viewport !== undefined) err("target.viewport is non-configurable — the runner pins 1440x700");
  if (spec.target?.headless !== undefined) err("target.headless is non-configurable — the runner is always headless");
  if (spec.console !== undefined) err("console capture is non-configurable — the ledger is always recorded");

  const steps = Array.isArray(spec.steps) ? spec.steps : [];
  if (steps.length === 0) err("steps must be a non-empty array");
  steps.forEach((s, i) => {
    const where = `steps[${i}]`;
    if (!s || typeof s !== "object") return err(`${where}: must be an object`);
    if (FORBIDDEN_ACTIONS.has(s.action)) {
      return err(`${where}: fixed sleeps are forbidden (action "${s.action}") — use waitFor/waitForText/expectWire with a timeout_ms CAP`);
    }
    if (!STEP_ACTIONS.has(s.action)) {
      return err(`${where}: unknown action "${s.action}" (deterministic vocabulary: ${[...STEP_ACTIONS].join(", ")})`);
    }
    for (const k of Object.keys(s)) {
      if (FORBIDDEN_KEYS.test(k)) err(`${where}: "${k}" is a fixed sleep in disguise — forbidden`);
    }
    if (s.timeout_ms !== undefined && (!Number.isInteger(s.timeout_ms) || s.timeout_ms <= 0)) {
      err(`${where}: timeout_ms must be a positive integer cap`);
    }
    if (["waitFor", "waitForText", "click", "fill"].includes(s.action) && typeof s.selector !== "string") {
      err(`${where}: "${s.action}" requires a selector`);
    }
    if (s.action === "waitForText" && s.contains === undefined && s.not_contains === undefined) {
      err(`${where}: waitForText requires contains and/or not_contains`);
    }
    if (s.action === "screenshot" && (typeof s.name !== "string" || !s.name)) {
      err(`${where}: screenshot requires a name`);
    }
    if (s.action === "readBack" && (typeof s.id !== "string" || typeof s.path !== "string")) {
      err(`${where}: readBack requires id and path`);
    }
    if ((s.action === "expectWire" || s.action === "expectNewWire") && typeof s.capture !== "string") {
      err(`${where}: ${s.action} requires a capture id`);
    }
  });

  const assertions = Array.isArray(spec.assertions) ? spec.assertions : [];
  if (assertions.length === 0) err("assertions must be a non-empty array — a run that asserts nothing proves nothing");
  let contentBearing = 0;
  assertions.forEach((a, i) => {
    const where = `assertions[${i}]${a?.id ? ` (${a.id})` : ""}`;
    if (!a || typeof a !== "object") return err(`${where}: must be an object`);
    if (typeof a.id !== "string" || !a.id) err(`${where}: id is required`);
    if (!ASSERTION_TYPES.has(a.type)) {
      return err(`${where}: unknown type "${a.type}" (known: ${[...ASSERTION_TYPES].join(", ")})`);
    }
    const content = hasContentCheck(a);
    if (content) contentBearing++;
    // THE status-only lint: status with no content check is rejected.
    if ((a.type === "wire" || a.type === "readBack") && a.status !== undefined && !content) {
      err(`${where}: status-only assertion — a ${a.status} alone proves reachability, not behavior; add json_path/equals/matches/contains or body_contains`);
    }
    if (a.type === "wire" && typeof a.capture !== "string") err(`${where}: wire assertion requires a capture id`);
    if (a.type === "readBack" && typeof a.capture !== "string") err(`${where}: readBack assertion requires the readBack step's id as capture`);
    if (a.type === "dbAssert" && (typeof a.db !== "string" || typeof a.sql !== "string" || !a.expect)) {
      err(`${where}: dbAssert requires db, sql, expect`);
    }
    if (a.type === "dbAssert" && typeof a.sql === "string" && !/^\s*select\b/i.test(a.sql)) {
      err(`${where}: dbAssert is read-only — SQL must be a SELECT`);
    }
    if (a.type === "cliCrossCheck" && (!Array.isArray(a.cmd) || a.cmd.length === 0)) {
      err(`${where}: cliCrossCheck requires cmd as an argv array (no shell strings)`);
    }
    if (a.type === "console" && a.max_errors === undefined) err(`${where}: console assertion requires max_errors`);
  });
  if (assertions.length > 0 && contentBearing === 0) {
    err("no content-bearing assertion in the spec — at least one assertion must check content (json_path/equals/matches/contains/body_contains), not just status or presence");
  }

  return { ok: errors.length === 0, errors };
}
