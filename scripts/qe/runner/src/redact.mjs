/**
 * src/redact.mjs — evidence redaction (TH-19, MVP-hard).
 *
 * Every captured byte passes through here BEFORE it is written to any
 * artifact. Two layers, then a preflight:
 *
 *  1. Field-name scrub (`redactDeep`): any object key matching the deny
 *     list (Authorization, Cookie/Set-Cookie, *token*, *secret*, *key*,
 *     *passw*, *credential*, *session*, ...) has its VALUE replaced with
 *     `[REDACTED:field:<name>]`, recursively. Extensible per target via
 *     `target.redact.fields` in the spec.
 *  2. Value-shape scrub (`redactString`): strings anywhere in the capture
 *     are scanned for credential shapes (Bearer/Basic auth, JWTs, AWS
 *     access keys, GitHub/OpenAI/Slack token prefixes, `password=...`
 *     kv pairs, PEM private-key blocks) and each match is replaced with
 *     `[REDACTED:<pattern-id>]`. Extensible per target via
 *     `target.redact.patterns` (regex source strings).
 *
 *  3. Secret-scan preflight (`scanForSecrets`): runs over the FINAL
 *     serialized artifact text right before it is written. Any hit flags
 *     the run INCONCLUSIVE (deny-dominates — see runner.mjs). The scan
 *     reports pattern ids and offsets, NEVER the matched text.
 *
 * Ordering contract (TH-17): redaction runs before any ledger/vault write —
 * vault immutability makes a leaked credential permanent.
 *
 * Known MVP limitation (documented, phase 2): screenshots are pixel data
 * and are not scanned; a secret rendered on-screen is not caught here.
 * Per-target screenshot masking is future work.
 */

const REDACTED = (reason) => `[REDACTED:${reason}]`;

// --- Layer 1: field-name deny list -----------------------------------------

const FIELD_NAME_DENY = [
  /authorization/i, // Authorization, Proxy-Authorization, authorization_header…
  /cookie/i, // Cookie, Set-Cookie, set_cookie, cookies…
  /token/i,
  /secret/i,
  /passw/i, // password, passwd, passwort...
  /passphrase/i,
  /credential/i,
  /session/i,
  /apikey/i,
  // "key" as its own word segment: api-key, api_key, x-key, private.key —
  // but not "keyboard"/"monkey".
  /(^|[^a-z])key(s)?([^a-z]|$)/i,
];

export function isDeniedFieldName(name, extraFields = []) {
  const s = String(name);
  return (
    FIELD_NAME_DENY.some((re) => re.test(s)) ||
    extraFields.some((re) => re.test(s))
  );
}

// --- Layer 2: value-shape patterns ------------------------------------------

// Order matters only cosmetically (first match wins per region). All global.
export const VALUE_PATTERNS = [
  { id: "bearer", re: /\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/g },
  { id: "basic-auth", re: /\bBasic\s+[A-Za-z0-9+/=]{8,}/g },
  { id: "jwt", re: /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b/g },
  { id: "aws-access-key", re: /\bAKIA[0-9A-Z]{16}\b/g },
  { id: "github-token", re: /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b/g },
  { id: "github-pat", re: /\bgithub_pat_[A-Za-z0-9_]{20,}\b/g },
  { id: "openai-key", re: /\bsk-[A-Za-z0-9_-]{16,}\b/g },
  { id: "slack-token", re: /\bxox[abprs]-[A-Za-z0-9-]{10,}\b/g },
  {
    id: "kv-secret",
    re: /\b(token|secret|password|passwd|pwd|api[-_]?key|apikey|access[-_]?key|auth)=([^&\s"']{4,})/gi,
    // Keep the key visible; scrub only the value.
    replace: (_m, k) => `${k}=${REDACTED("kv")}`,
  },
  {
    id: "private-key-block",
    re: /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g,
  },
];

/** Compile per-target regex source strings (spec `target.redact.patterns`). */
export function compileExtraPatterns(sources = []) {
  return sources.map((src, i) => ({ id: `target-pattern-${i}`, re: new RegExp(src, "g") }));
}

/** Compile per-target extra field names (spec `target.redact.fields`). */
export function compileExtraFields(names = []) {
  return names.map((n) => new RegExp(`^${escapeRe(String(n))}$`, "i"));
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function redactString(value, extraPatterns = []) {
  let out = String(value);
  for (const { id, re, replace } of [...VALUE_PATTERNS, ...extraPatterns]) {
    re.lastIndex = 0;
    out = out.replace(re, replace ?? REDACTED(id));
  }
  return out;
}

/**
 * Deep-scrub any JSON-serializable value. Returns a NEW value; the input is
 * never mutated. `opts.extraFields` / `opts.extraPatterns` come from
 * compileExtraFields / compileExtraPatterns.
 */
export function redactDeep(value, opts = {}) {
  const extraFields = opts.extraFields ?? [];
  const extraPatterns = opts.extraPatterns ?? [];
  const walk = (v) => {
    if (typeof v === "string") return redactString(v, extraPatterns);
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === "object") {
      const out = {};
      for (const [k, inner] of Object.entries(v)) {
        out[k] = isDeniedFieldName(k, extraFields)
          ? REDACTED(`field:${k}`)
          : walk(inner);
      }
      return out;
    }
    return v;
  };
  return walk(value);
}

// --- Layer 3: secret-scan preflight ------------------------------------------

// Serialized-JSON detector: a denied-looking field name whose STRING value is
// not already a redaction marker. Catches anything layer 1 missed (e.g. a
// producer bypassing redactDeep).
const SERIALIZED_FIELD_LEAK = {
  id: "serialized-field-leak",
  re: /"((?:authorization|proxy-authorization|cookie|set-cookie)|[^"]*(?:token|secret|passw|credential|apikey)[^"]*)"\s*:\s*"(?!\[REDACTED)[^"]{4,}"/gi,
};

/**
 * Scan final artifact text for residual secrets. Returns hits as
 * `{ pattern, index }` — deliberately WITHOUT the matched text, so the scan
 * result itself can be persisted safely.
 */
export function scanForSecrets(text, extraPatterns = []) {
  const hits = [];
  const detectors = [...VALUE_PATTERNS, SERIALIZED_FIELD_LEAK, ...extraPatterns];
  for (const { id, re } of detectors) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      // A region already scrubbed to "[REDACTED:...]" is not a hit; the
      // kv-secret replacer leaves "key=[REDACTED:kv]" behind, which the
      // kv regex re-matches ("[REDACTED:kv]" has no & or quote — it DOES
      // match [^&\s"']). Skip matches whose value part is a marker.
      if (m[0].includes("[REDACTED:")) continue;
      hits.push({ pattern: id, index: m.index });
      if (hits.length >= 100) return hits; // enough to deny; don't spin
    }
  }
  return hits;
}
