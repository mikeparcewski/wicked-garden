/**
 * src/spec.mjs — spec loading: JSON parse + `${env:NAME}` interpolation +
 * lint. The spec is the ONLY input the runner takes; it is data, never code.
 *
 * Interpolation forms (applied to every string value in the spec):
 *   ${env:NAME}            → process.env.NAME (error when unset)
 *   ${env:NAME:-fallback}  → process.env.NAME or the literal fallback
 *
 * This keeps committed specs portable (isolated daemons get fresh ports and
 * scratch paths per run) while staying deterministic — the environment is
 * pinned by whoever launches the run, not decided by the runner.
 */

import { readFileSync } from "node:fs";
import { lintSpec } from "./lint.mjs";

const ENV_OPEN = "${env:";
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

/**
 * Linear scan for `${env:NAME}` / `${env:NAME:-fallback}`. An index-based
 * scanner instead of a regex: the fallback is arbitrary spec text, and a
 * backtracking quantifier over uncontrolled input is a ReDoS surface
 * (CodeQL js/polynomial-redos on the regex this replaces).
 */
function interpolateString(str, env, missing) {
  let out = "";
  let i = 0;
  for (;;) {
    const open = str.indexOf(ENV_OPEN, i);
    if (open === -1) { out += str.slice(i); return out; }
    const close = str.indexOf("}", open + ENV_OPEN.length);
    if (close === -1) { out += str.slice(i); return out; }
    const body = str.slice(open + ENV_OPEN.length, close);
    const sep = body.indexOf(":-");
    const name = sep === -1 ? body : body.slice(0, sep);
    const fallback = sep === -1 ? undefined : body.slice(sep + 2);
    if (!NAME_RE.test(name)) { out += str.slice(i, close + 1); i = close + 1; continue; }
    out += str.slice(i, open);
    const got = env[name];
    if (got !== undefined && got !== "") out += got;
    else if (fallback !== undefined) out += fallback;
    else missing.push(name);
    i = close + 1;
  }
}

export function interpolate(value, env = process.env, missing = []) {
  const walk = (v) => {
    if (typeof v === "string") {
      return interpolateString(v, env, missing);
    }
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === "object") {
      const out = {};
      for (const [k, inner] of Object.entries(v)) out[k] = walk(inner);
      return out;
    }
    return v;
  };
  return walk(value);
}

/**
 * Load, interpolate, and lint a spec file.
 * Returns { spec } or throws SpecError with `.errors` listing every problem.
 */
export class SpecError extends Error {
  constructor(errors) {
    super(`spec rejected:\n  - ${errors.join("\n  - ")}`);
    this.errors = errors;
  }
}

export function loadSpec(path, env = process.env) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    throw new SpecError([`cannot read/parse spec ${path}: ${e.message}`]);
  }
  const missing = [];
  const spec = interpolate(raw, env, missing);
  if (missing.length > 0) {
    throw new SpecError(missing.map((n) => `required env var ${n} is unset (and the spec gives no fallback)`));
  }
  const lint = lintSpec(spec);
  if (!lint.ok) throw new SpecError(lint.errors);
  return spec;
}
