// A storyline as DATA (DES-DEMO-RECORD-001 §3.3, wicked-core#1249): the form the engine-run demo recorder accepts.
//
// The recorder runs on the host, inside the engine's jail, with one loopback port open: the app under demo. A
// storyline written as a module (storyline.mjs) is code, and running a seat's code there would hand it the app's
// origin, which may be the crew daemon itself. So the demo_record Tool takes only storyline.json: a closed set of
// steps over the recorder's ctx verbs, checked here and compiled into the `story` object makeSegmentRecorder takes.
// storyline.mjs stays for recording by hand outside crew.
//
//   storyline.json  {title, ready, intro?, hide?, segments:[{key, title, blurb?, tags?, steps:[...]}], closing?}
//   chapters.json   [{key, title, ...}]  — the approved chapter plan; its keys must equal the segments' keys
//
// Every string is plain text (escaped at every sink). Every navigation path resolves against the app origin and
// stays under the launch path. Anything else is refused, naming the field.

/** The longest key: crew's and interactive's import limit (crew recording.ts IMPORT_KEY, interactive demo-cut.js IMPORT_ID). */
export const KEY_MAX = 48;
export const KEY_RE = new RegExp(`^[a-z0-9][a-z0-9-]{0,${KEY_MAX - 1}}$`);
export const LIMITS = Object.freeze({
  chapters: 12, steps: 60, ms: 30_000, text: 500, fileBytes: 64 * 1024, factorMin: 2, factorMax: 16, nth: 50,
  introMinMs: 1500, hide: 12,
  // The most a take may spend on its own fixed timing (holds, captions, cards and each step's own motion), well
  // under the engine's 20-minute deadline: a storyline that could never finish is refused here (a verdict on the
  // storyline). Waits on the app are bounded by their timeouts and by that deadline (a slow app is the host's).
  fixedSeconds: 12 * 60,
});
/** How long one wait may take (seconds): `waitVisible`, `waitForPath`, `ready`, a `go`'s load; `fast` waits longer. */
export const WAIT_S = 30;
export const FAST_WAIT_S = 120;
/** How long a chapter may take to get ready behind its card, per target (seconds): its `ready`, then its first one. */
export const PREPARE_WAIT_S = 60;
/** How long an `optional` step waits for its target before it is skipped (seconds). */
export const OPTIONAL_WAIT_S = 5;
/** The verbs a step may mark `optional` (DES-DEMO-RECORD-001 §13 A1.3): cosmetic ones, never a measured one. */
export const OPTIONAL_VERBS = Object.freeze(["click", "point", "waitVisible"]);
// A `hide` entry is one CSS selector: nothing that could end it and start another rule, an at-rule or a comment.
const HIDE_CSS_BAD = /[{};@\\<>]|\/\*/;
const PATH_RE = LAUNCH_PATH_RE;
const LABEL_RE = /^[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}$/;
const TARGET_KINDS = ["role", "text", "section", "button", "testId", "css"];

import { LAUNCH_PATH_RE, underPath as underBase } from "./readonly.mjs";

class StorylineError extends Error {
  constructor(where, detail) {
    super(`${where}: ${detail}`);
    this.code = "storyline_refused";
    this.where = where;
  }
}
const refuse = (where, detail) => { throw new StorylineError(where, detail); };

function obj(v, where) {
  if (v === null || typeof v !== "object" || Array.isArray(v)) refuse(where, "must be an object");
  return v;
}
function only(o, keys, where) {
  for (const k of Object.keys(o)) if (!keys.includes(k)) refuse(`${where}.${k}`, "is not a field this storyline form takes");
}
function str(v, where, { optional = false, max = LIMITS.text, oneLine = false } = {}) {
  if (v === undefined && optional) return undefined;
  if (typeof v !== "string") refuse(where, "must be a string");
  if (oneLine && /[\r\n]/.test(v)) refuse(where, "must be one line (a chapter title becomes the video's chapter name)");
  if (v.length > max) refuse(where, `is longer than ${max} characters`);
  // Control characters never reach a caption, a card or the address bar.
  if (/[\u0000-\u0008\u000b-\u001f\u007f]/.test(v)) refuse(where, "contains a control character");
  return v;
}
function int(v, where, min, max, { optional = false } = {}) {
  if (v === undefined && optional) return undefined;
  if (!Number.isInteger(v) || v < min || v > max) refuse(where, `must be a whole number from ${min} to ${max}`);
  return v;
}

/**
 * The launch path a navigation must stay under, normalised to end without a trailing slash (`/` stays `/`).
 * `launchPath` is the path of the URL the person typed at launch, which the engine hands in; never the storyline's.
 */
export function normaliseLaunchPath(launchPath) {
  const p = String(launchPath || "/");
  if (!PATH_RE.test(p) || p.startsWith("//")) throw new Error(`the launch path is not a plain path: ${p}`);
  const pathOnly = p.split(/[?#]/)[0];
  return pathOnly.length > 1 ? pathOnly.replace(/\/+$/, "") || "/" : "/";
}

/** Whether `pathname` is the launch path or below it (segment boundary: `/apps/esc` is not under `/apps/e`). */
export function underLaunchPath(pathname, launchPath) {
  return underBase(pathname, normaliseLaunchPath(launchPath));
}

/** A path-prefix matcher (linear: the prefix is escaped, never a seat-written pattern) for `waitForPath`/`fast`. */
export function pathPrefixRegExp(prefix) {
  // `/` matches every path; `/app/` and `/app` both match `/app` and below.
  const base = String(prefix).length > 1 ? String(prefix).replace(/\/+$/, "") : "/";
  if (base === "/") return /^\//;
  const escaped = base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${escaped}(?:[/?#]|$)`);
}

/** A navigation field: a plain path, resolved with the URL API against the app origin, under the launch path. */
export function resolveNav(p, where, { appOrigin, launchPath }) {
  str(p, where, { max: 2048 });
  if (!PATH_RE.test(p) || p.startsWith("//")) refuse(where, "must be a path starting with one / (letters, digits and ._~%/?&=+- only)");
  const u = new URL(p, appOrigin);
  if (u.origin !== new URL(appOrigin).origin) refuse(where, "must stay on the app's origin");
  if (!underLaunchPath(u.pathname, launchPath)) refuse(where, `must stay under the launch path ${normaliseLaunchPath(launchPath)}`);
  return u.pathname + u.search;
}

function target(t, where, nav) {
  obj(t, where);
  only(t, [...TARGET_KINDS, "name", "nth", "exact", "in"], where);
  const kinds = TARGET_KINDS.filter((k) => t[k] !== undefined);
  if (kinds.length !== 1) refuse(where, `must name exactly one of ${TARGET_KINDS.join(", ")}`);
  const kind = kinds[0];
  const out = { kind, value: str(t[kind], `${where}.${kind}`, { max: 200 }) };
  if (t.name !== undefined) {
    if (kind !== "role") refuse(`${where}.name`, "only a role target takes a name");
    out.name = str(t.name, `${where}.name`, { max: 200 });
  }
  if (t.exact !== undefined) {
    if (typeof t.exact !== "boolean") refuse(`${where}.exact`, "must be true or false");
    out.exact = t.exact;
  }
  out.nth = int(t.nth, `${where}.nth`, 0, LIMITS.nth, { optional: true });
  if (t.in !== undefined) {
    if (t.in !== "content") refuse(`${where}.in`, 'must be "content" (the app\'s own frame inside the page) or absent');
    out.in = "content";
  }
  // A crew app's take shows only the app's own frame (§13 A1.2): studio's page around it is hidden, so a target
  // there could never be seen.
  if (nav?.contentOnly && out.in !== "content") {
    refuse(`${where}.in`, 'must be "content": a crew app is recorded in its own frame only, and studio\'s page around it is hidden');
  }
  return out;
}

const STEP_FIELDS = {
  go: ["path"],
  caption: ["kicker", "title", "body", "readMs"],
  point: ["target", "label"],
  unpoint: [],
  click: ["target"],
  type: ["target", "text"],
  hold: ["ms"],
  card: ["title", "body", "ms"],
  waitVisible: ["target"],
  waitForPath: ["path"],
  fast: ["label", "factor", "until"],
  time: ["label", "steps"],
};

function step(s, where, nav, depth) {
  obj(s, where);
  const verbs = Object.keys(s).filter((k) => k !== "optional");
  if (verbs.length !== 1 || !Object.hasOwn(STEP_FIELDS, verbs[0])) refuse(where, `must be one of ${Object.keys(STEP_FIELDS).join(", ")}`);
  const verb = verbs[0];
  const w = `${where}.${verb}`;
  if (s.optional !== undefined) {
    if (typeof s.optional !== "boolean") refuse(`${where}.optional`, "must be true or false");
    if (s.optional && !OPTIONAL_VERBS.includes(verb)) refuse(`${where}.optional`, `only ${OPTIONAL_VERBS.join(", ")} may be optional`);
    if (s.optional && depth > 0) refuse(`${where}.optional`, "a step inside a time step is never optional (a measured interaction is whole)");
  }
  const checked = stepBody(verb, s, w, nav, depth, where);
  checked.at = where;
  if (s.optional) checked.optional = true;
  return checked;
}

function stepBody(verb, s, w, nav, depth, where) {
  const a = verb === "unpoint" ? (s[verb] === null || s[verb] === true ? {} : obj(s[verb], w)) : obj(s[verb], w);
  only(a, STEP_FIELDS[verb], w);
  switch (verb) {
    case "go": return { verb, path: resolveNav(a.path, `${w}.path`, nav) };
    case "caption": return { verb, kicker: str(a.kicker, `${w}.kicker`, { max: 80 }), title: str(a.title, `${w}.title`, { max: 200 }),
      body: str(a.body, `${w}.body`, { optional: true }), readMs: int(a.readMs, `${w}.readMs`, 0, LIMITS.ms, { optional: true }) };
    case "point": return { verb, target: target(a.target, `${w}.target`, nav), label: str(a.label, `${w}.label`, { max: 120 }) };
    case "unpoint": return { verb };
    case "click": return { verb, target: target(a.target, `${w}.target`, nav) };
    case "type": return { verb, target: target(a.target, `${w}.target`, nav), text: str(a.text, `${w}.text`) };
    case "hold": return { verb, ms: int(a.ms, `${w}.ms`, 0, LIMITS.ms) };
    case "card": return { verb, title: str(a.title, `${w}.title`, { max: 200 }), body: str(a.body, `${w}.body`, { optional: true }),
      ms: int(a.ms, `${w}.ms`, 0, LIMITS.ms) };
    case "waitVisible": return { verb, target: target(a.target, `${w}.target`, nav) };
    case "waitForPath": return { verb, path: resolveNav(a.path, `${w}.path`, nav) };
    case "fast": {
      const until = obj(a.until, `${w}.until`);
      only(until, ["target", "path"], `${w}.until`);
      if ((until.target === undefined) === (until.path === undefined)) refuse(`${w}.until`, "must name exactly one of target, path");
      const u = until.target !== undefined ? { target: target(until.target, `${w}.until.target`, nav) } : { path: resolveNav(until.path, `${w}.until.path`, nav) };
      return { verb, label: str(a.label, `${w}.label`, { max: 80 }), factor: int(a.factor, `${w}.factor`, LIMITS.factorMin, LIMITS.factorMax), until: u };
    }
    case "time": {
      if (depth > 0) refuse(w, "cannot be nested inside another time step");
      if (!Array.isArray(a.steps) || a.steps.length === 0) refuse(`${w}.steps`, "must be a non-empty list");
      const label = str(a.label, `${w}.label`, { max: 40 });
      if (!LABEL_RE.test(label)) refuse(`${w}.label`, "must be letters, digits, spaces and ._- (it names a timing)");
      return { verb, label, steps: a.steps.map((x, i) => step(x, `${w}.steps[${i}]`, nav, depth + 1)) };
    }
  }
  return refuse(where, "unknown step");
}

function countSteps(steps) {
  return steps.reduce((n, s) => n + 1 + (s.verb === "time" ? countSteps(s.steps) : 0), 0);
}

/** The steps' own fixed timing (seconds): holds, captions, cards, and each step's motion (a wait counts its
 *  minimum, never its timeout: a wait that times out ends the take). */
export function fixedSeconds(steps) {
  return steps.reduce((t, s) => {
    switch (s.verb) {
      case "go": return t + 3;
      case "caption": return t + (s.readMs ?? 9000) / 1000 + 0.5;
      case "point": case "click": return t + 3;
      case "type": return t + 3 + (s.text.length * 0.03);
      case "hold": return t + s.ms / 1000;
      case "card": return t + s.ms / 1000 + 1;
      case "waitVisible": case "waitForPath": return t + 1;
      case "fast": return t + 2;
      case "time": return t + fixedSeconds(s.steps);
      default: return t + 1;
    }
  }, 0);
}

/**
 * Check a storyline.json value against the approved chapter plan. Returns the normalised storyline; throws a
 * `storyline_refused` error naming the first field it refuses.
 *
 * @param {unknown} raw         the parsed storyline.json
 * @param {unknown} chapters    the parsed chapters.json (the approved plan)
 * @param {{appOrigin: string, launchPath: string}} nav  from the engine, never from the storyline
 */
export function checkStoryline(raw, chapters, nav) {
  try {
    return checkStorylineInner(raw, chapters, nav);
  } catch (e) {
    if (e instanceof StorylineError) throw e;
    // Any other failure on seat-written data is still a refusal of that data, never an engine fault.
    throw new StorylineError("storyline", `could not be read (${String(e?.message ?? e).split("\n")[0]})`);
  }
}

function checkStorylineInner(raw, chapters, nav) {
  const s = obj(raw, "storyline");
  only(s, ["title", "ready", "intro", "segments", "closing", "brand", "hide"], "storyline");
  const out = {
    title: str(s.title, "storyline.title", { max: 200, oneLine: true }),
    ready: target(s.ready, "storyline.ready", nav),
    hide: [],
  };
  if (s.hide !== undefined) {
    if (!Array.isArray(s.hide) || s.hide.length > LIMITS.hide) refuse("storyline.hide", `must be a list of at most ${LIMITS.hide} entries`);
    out.hide = s.hide.map((h, i) => {
      const w = `storyline.hide[${i}]`;
      obj(h, w);
      only(h, ["css", "in"], w);
      const css = str(h.css, `${w}.css`, { max: 200, oneLine: true });
      if (!css.trim()) refuse(`${w}.css`, "must not be empty");
      if (HIDE_CSS_BAD.test(css)) refuse(`${w}.css`, "must be one CSS selector (no { } ; @ \\ < > or comments)");
      if (h.in !== undefined && h.in !== "content") refuse(`${w}.in`, 'must be "content" (the app\'s own frame inside the page) or absent');
      return h.in === "content" ? { css, in: "content" } : { css };
    });
  }
  if (s.brand !== undefined) {
    const b = obj(s.brand, "storyline.brand");
    only(b, ["name", "accent"], "storyline.brand");
    out.brand = { name: str(b.name, "storyline.brand.name", { optional: true, max: 80 }) };
    if (b.accent !== undefined) {
      if (typeof b.accent !== "string" || !/^#[0-9a-f]{6}$/i.test(b.accent)) refuse("storyline.brand.accent", "must be a #rrggbb colour");
      out.brand.accent = b.accent;
    }
  }
  if (s.intro !== undefined) {
    const i = obj(s.intro, "storyline.intro");
    only(i, ["title", "body", "ms"], "storyline.intro");
    out.intro = { title: str(i.title, "storyline.intro.title", { max: 200 }), body: str(i.body, "storyline.intro.body", { optional: true }),
      ms: int(i.ms, "storyline.intro.ms", LIMITS.introMinMs, LIMITS.ms) };
  }
  if (s.closing !== undefined) {
    const c = obj(s.closing, "storyline.closing");
    only(c, ["title", "body", "ms"], "storyline.closing");
    out.closing = { title: str(c.title, "storyline.closing.title", { max: 200 }), body: str(c.body, "storyline.closing.body", { optional: true }),
      ms: int(c.ms, "storyline.closing.ms", 0, LIMITS.ms, { optional: true }) };
  }
  if (!Array.isArray(s.segments) || s.segments.length === 0) refuse("storyline.segments", "must be a non-empty list");
  if (s.segments.length > LIMITS.chapters) refuse("storyline.segments", `has more than ${LIMITS.chapters} chapters`);
  const seen = new Set();
  out.segments = s.segments.map((raw, i) => {
    const w = `storyline.segments[${i}]`;
    const g = obj(raw, w);
    only(g, ["key", "title", "blurb", "tags", "steps"], w);
    const key = str(g.key, `${w}.key`, { max: KEY_MAX });
    if (!KEY_RE.test(key)) refuse(`${w}.key`, `must be lowercase letters, digits and hyphens, at most ${KEY_MAX} characters`);
    if (key === "intro") refuse(`${w}.key`, "`intro` is the storyline's intro field, not a chapter key");
    if (seen.has(key)) refuse(`${w}.key`, `repeats the key ${key}`);
    seen.add(key);
    if (g.tags !== undefined && (!Array.isArray(g.tags) || g.tags.length > 8)) refuse(`${w}.tags`, "must be a list of at most 8 strings");
    if (!Array.isArray(g.steps) || g.steps.length === 0) refuse(`${w}.steps`, "must be a non-empty list");
    const steps = g.steps.map((x, j) => step(x, `${w}.steps[${j}]`, nav, 0));
    if (countSteps(steps) > LIMITS.steps) refuse(`${w}.steps`, `has more than ${LIMITS.steps} steps`);
    return {
      key, title: str(g.title, `${w}.title`, { max: 200, oneLine: true }), blurb: str(g.blurb, `${w}.blurb`, { optional: true }),
      tags: (g.tags ?? []).map((t, j) => str(t, `${w}.tags[${j}]`, { max: 40 })), steps,
    };
  });
  // A storyline whose own fixed timing could outlast the engine's deadline is refused here, naming it. (Each chapter
  // also opens on its card and the launch page, and proves its app ready: about 12 s.)
  const fixed = out.segments.reduce((t, g) => t + 12 + fixedSeconds(g.steps), (out.intro?.ms ?? 0) / 1000 + (out.closing?.ms ?? 0) / 1000);
  if (fixed > LIMITS.fixedSeconds) {
    refuse("storyline.segments", `spends ${Math.round(fixed / 60)} min on holds, captions, cards and motion; the most is ${LIMITS.fixedSeconds / 60} min (shorter holds or fewer chapters)`);
  }
  // The approved chapter plan and the storyline name the same chapters, in the same order.
  if (!Array.isArray(chapters)) refuse("chapters.json", "must be a list of chapters");
  const planKeys = chapters.map((c, i) => (c && typeof c === "object" ? c.key : refuse(`chapters.json[${i}]`, "must be an object")));
  const storyKeys = out.segments.map((g) => g.key);
  if (planKeys.length !== storyKeys.length || planKeys.some((k, i) => k !== storyKeys[i])) {
    refuse("storyline.segments", `keys [${storyKeys.join(", ")}] must equal chapters.json's keys in order [${planKeys.join(", ")}]`);
  }
  return out;
}

/** Parse and check the two files' bytes (each at most LIMITS.fileBytes). */
export function parseStoryline(storylineText, chaptersText, nav) {
  for (const [name, text] of [["storyline.json", storylineText], ["chapters.json", chaptersText]]) {
    if (typeof text !== "string") refuse(name, "is missing");
    if (Buffer.byteLength(text, "utf8") > LIMITS.fileBytes) refuse(name, `is larger than ${LIMITS.fileBytes} bytes`);
  }
  let raw, chapters;
  try { raw = JSON.parse(storylineText); } catch (e) { refuse("storyline.json", `is not JSON (${e.message})`); }
  try { chapters = JSON.parse(chaptersText); } catch (e) { refuse("chapters.json", `is not JSON (${e.message})`); }
  return checkStoryline(raw, chapters, nav);
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** The innermost `<section>` in `base` holding a heading named `title` (or that exact text), as ctx.section does. */
function sectionIn(base, title) {
  const reEsc = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const innermost = (inner) => base.locator("section").filter({ has: inner }).filter({ hasNot: base.locator("section").filter({ has: inner }) });
  const heading = base.getByRole("heading", { name: new RegExp(`^${reEsc(title)}(\\s*\\d+)?$`) });
  return innermost(heading).or(innermost(base.getByText(title, { exact: true }))).first();
}

/** A Playwright locator for a checked target: in the app frame, or (`in: "content"`) the first frame inside it. */
export function locate(ctx, t) {
  const app = t.in === "content" ? ctx.app.frameLocator("iframe").first() : ctx.app;
  let loc;
  switch (t.kind) {
    case "role": loc = app.getByRole(t.value, t.name !== undefined ? { name: t.name, exact: t.exact ?? false } : {}); break;
    case "text": loc = app.getByText(t.value, { exact: t.exact ?? false }); break;
    case "section": loc = t.in === "content" ? sectionIn(app, t.value) : ctx.section(t.value); break;
    case "button": loc = app.locator("button").filter({ hasText: t.value }); break;
    case "testId": loc = app.getByTestId(t.value); break;
    case "css": loc = app.locator(t.value); break;
    default: throw new Error(`unknown target kind ${t.kind}`);
  }
  return t.nth !== undefined ? loc.nth(t.nth) : loc;
}

/** Fill `{{timings.<key>.<label>}}` from measured timings; an unknown one reads "n/a". Plain text in, plain text out. */
export function fillTimings(text, all) {
  return String(text ?? "").replace(/\{\{timings\.([a-z0-9-]+)\.([^}]{1,80})\}\}/g, (_, k, l) => {
    const v = all?.[k]?.[l];
    return typeof v === "number" ? `${v} s` : "n/a";
  });
}

function cardHtml(title, body) {
  return `<div data-logo></div><h1>${esc(title)}</h1>${body ? `<p>${esc(body)}</p>` : ""}`;
}

/** A step, as a failure or a skip names it: its place in the storyline, its verb and its target. */
export function describeStep(s) {
  const t = s.target ?? s.until?.target;
  const what = t ? ` ${t.kind} ${JSON.stringify(t.value)}${t.name !== undefined ? ` ${JSON.stringify(t.name)}` : ""}${t.in ? " in content" : ""}` : "";
  return `${s.at ?? "a step"} (${s.verb}${what})`;
}

/**
 * The chapter's first target (§13 A1.1): the first required `waitVisible`, `point`, `click` or `type` target before
 * anything that changes or measures the page (`go`, `waitForPath`, `fast`, `time`). Null when there is none.
 */
export function firstTarget(steps) {
  for (const s of steps) {
    if (["go", "waitForPath", "fast", "time"].includes(s.verb)) return null;
    if (s.target && !s.optional) return s.target;
  }
  return null;
}

async function runStep(ctx, s) {
  switch (s.verb) {
    case "go": await ctx.go(s.path); await ctx.checkpoint("go"); break;
    case "caption": await ctx.caption(esc(s.kicker), esc(s.title), esc(s.body ?? ""), s.readMs); break;
    case "point": await ctx.point(locate(ctx, s.target), s.label); break; // a text sink: plain
    case "unpoint": await ctx.unpoint(); break;
    case "click": await ctx.click(locate(ctx, s.target)); await ctx.checkpoint("click"); break;
    case "type": await ctx.type(locate(ctx, s.target), s.text); await ctx.checkpoint("type"); break;
    case "hold": await ctx.hold(s.ms); break;
    case "card": await ctx.card(cardHtml(s.title, s.body), s.ms); await ctx.uncard(); await ctx.checkpoint("uncard"); break;
    case "waitVisible": await ctx.waitVisible(locate(ctx, s.target), (s.optional ? OPTIONAL_WAIT_S : WAIT_S) * 1000); break;
    case "waitForPath": await ctx.waitForPath(pathPrefixRegExp(s.path.split("?")[0]), WAIT_S * 1000); break;
    case "fast": await ctx.fast(s.label, s.factor, () => (s.until.target // the badge is a text sink: plain
      ? ctx.waitVisible(locate(ctx, s.until.target), FAST_WAIT_S * 1000)
      : ctx.waitForPath(pathPrefixRegExp(s.until.path.split("?")[0]), FAST_WAIT_S * 1000))); break;
    case "time": await ctx.time(s.label, () => runSteps(ctx, s.steps)); break;
    default: throw new Error(`unknown step ${s.verb}`);
  }
}

async function runSteps(ctx, steps) {
  for (const s of steps) {
    if (s.optional) {
      // An optional step (§13 A1.3) whose target is not there within OPTIONAL_WAIT_S, or whose action fails, is
      // skipped and said so; a failure the recorder itself raised (a refused request, leaving the app, a stalled
      // capture: each carries a code) is never swallowed.
      try {
        await ctx.waitVisible(locate(ctx, s.target), OPTIONAL_WAIT_S * 1000);
        await runStep(ctx, s);
      } catch (e) {
        if (e?.code) throw named(e, s);
        await ctx.skipped({ step: s.at ?? null, verb: s.verb, what: describeStep(s), reason: String(e?.message ?? e).split("\n")[0].slice(0, 200) });
      }
      continue;
    }
    try {
      await runStep(ctx, s);
    } catch (e) {
      throw named(e, s);
    }
  }
}

/** A failed step's error names the step (once: a time step's inner step names itself). */
function named(e, s) {
  if (e && typeof e === "object" && e.step === undefined) {
    e.step = describeStep(s);
    if (typeof e.message === "string") e.message = `${e.step}: ${e.message}`;
  }
  return e;
}

/**
 * Compile a checked storyline into the `story` makeSegmentRecorder takes (record.mjs). Each chapter gets ready
 * behind its chapter card (`prepare`, §13 A1.1): the page goes network-quiet, then the storyline's `ready` target
 * and the chapter's first target are visible. Once the card lifts, `run` marks the `ready` checkpoint and runs the
 * chapter's steps.
 */
export function compileStoryline(checked, { launchPath }) {
  const waitFor = async (ctx, t, what) => {
    try {
      await ctx.waitVisible(locate(ctx, t), PREPARE_WAIT_S * 1000);
    } catch (e) {
      if (e?.code) throw e;
      const err = new Error(`app_not_ready: the app never showed ${what} (${t.kind} ${JSON.stringify(t.value)}${t.in ? " in content" : ""}): ${String(e.message).split("\n")[0]}`);
      err.code = "app_not_ready";
      throw err;
    }
  };
  const segments = [];
  if (checked.intro) {
    const i = checked.intro;
    segments.push({ key: "intro", intro: true, title: "Introduction", async run(ctx) { await ctx.card(cardHtml(i.title, i.body), i.ms); } });
  }
  for (const g of checked.segments) {
    const first = firstTarget(g.steps);
    segments.push({
      key: g.key, title: g.title, blurb: g.blurb, tags: g.tags,
      async prepare(ctx) {
        await ctx.settle();
        await waitFor(ctx, checked.ready, "its ready target");
        if (first) await waitFor(ctx, first, "the chapter's first target");
      },
      async run(ctx) {
        // Ready already (behind the card); proven again on screen, now that the card is gone.
        await waitFor(ctx, checked.ready, "its ready target");
        await ctx.checkpoint("ready");
        await runSteps(ctx, g.steps);
      },
    });
  }
  return {
    title: checked.title,
    // The exact path (and query) the person launched: a server may serve `/app/` and redirect `/app`.
    startPath: launchPath,
    brand: checked.brand ? { name: checked.brand.name, accent: checked.brand.accent } : undefined,
    hide: checked.hide ?? [],
    segments,
    ...(checked.closing ? {
      closing: (all) => cardHtml(fillTimings(checked.closing.title, all), fillTimings(checked.closing.body, all)),
      closingMs: checked.closing.ms ?? 10_000,
    } : {}),
  };
}
