/**
 * lib/context-md-validator.mjs — pre-dispatch validator for reviewer context.md.
 *
 * The 3-agent acceptance pipeline's reviewer isolation depends on context.md
 * containing ONLY non-prejudicial cold knowledge (domain rules, tool quirks)
 * and NEVER prior verdicts, historical outcomes, or cross-run references.
 * Prose-level enforcement in the reviewer agent body is not enough — a buggy
 * orchestrator that drops `SELECT * FROM verdicts WHERE scenario_id = ?`
 * output into context.md would feed the reviewer prior verdicts, and the
 * reviewer might not notice.
 *
 * This module is the code-enforced boundary. `buildReviewerContext` is the
 * only sanctioned way to materialize a `context.md` — it runs
 * `validateContextMd` first and refuses to write on any match, so the reviewer
 * can never be fed contaminated context through normal code paths.
 *
 * Patterns are intentionally narrow to avoid false-positives on legitimate
 * cold knowledge (e.g. "the WCAG AA pass criterion" must not match just
 * because it contains the word "pass").
 */

import { writeFileSync, existsSync } from "node:fs";

// Patterns that indicate prejudicial content. Each entry names the risk so
// failure messages can be actionable.
const PREJUDICIAL_PATTERNS = [
  { name: "verdict_assignment",
    re: /\bverdict\s*[:=]\s*["']?(PASS|FAIL|PARTIAL|CONDITIONAL|INCONCLUSIVE|N-A|SKIP)\b/i },
  { name: "standalone_verdict_line",
    re: /^\s*(verdict|status|outcome)\s*[:=]\s*["']?(PASS|FAIL|PARTIAL|CONDITIONAL|INCONCLUSIVE|N-A|SKIP)\b/im },
  { name: "run_id_reference",
    re: /\brun_id\s*[:=]/i },
  { name: "historical_reference",
    re: /\b(previous|prior|last)\s+(run|verdict|outcome|result)\b/i },
  { name: "historical_verb",
    re: /\bhistor(ical|y)\s+(verdict|outcome|pass|fail|result)/i },
  { name: "pass_fail_rate",
    re: /\b(pass|fail)\s+rate\b/i },
  { name: "pass_fail_count",
    re: /\b(pass|fail)\s+count\b/i },
  { name: "scenario_cross_reference",
    re: /\bscenario\s+[a-z0-9_-]+\s+(passed|failed|errored|skipped)\b/i },
  { name: "executor_reasoning_leak",
    re: /\b(executor|runner)\s+(thought|expected|believed|reasoned|said)\b/i },
  { name: "this_run_outcome",
    re: /\bthis\s+run\s+(passed|failed|errored|skipped)\b/i },
  { name: "counted_history",
    re: /\b(passed|failed|errored)\s+\d+\s+times?\b/i },
  { name: "consecutive_history",
    re: /\b\d+\s+(consecutive|successive|prior)\s+(pass|fail|run)/i },
];

/**
 * Validate a proposed context.md body.
 *
 * @param {string} content      Proposed context.md text.
 * @param {object} [opts]
 * @param {string[]} [opts.extraForbidden]  Additional substrings to reject
 *   (e.g. current run_id to catch dynamic leaks).
 * @returns {{ ok: boolean, reasons: Array<{pattern: string, match: string}> }}
 */
export function validateContextMd(content, opts = {}) {
  const reasons = [];
  if (typeof content !== "string" || content.length === 0) {
    // Empty context.md is trivially non-prejudicial — just don't write it.
    return { ok: true, reasons };
  }
  for (const { name, re } of PREJUDICIAL_PATTERNS) {
    const m = re.exec(content);
    if (m) reasons.push({ pattern: name, match: m[0] });
  }
  for (const needle of opts.extraForbidden || []) {
    if (needle && content.includes(needle)) {
      reasons.push({ pattern: "extra_forbidden", match: needle });
    }
  }
  return { ok: reasons.length === 0, reasons };
}

export class ContextContaminationError extends Error {
  constructor(reasons) {
    const summary = reasons.map(r => `${r.pattern}(${JSON.stringify(r.match)})`).join("; ");
    super(`CONTEXT_CONTAMINATION: ${summary}`);
    this.code = "ERR_CONTEXT_CONTAMINATION";
    this.reasons = reasons;
  }
}

/**
 * Write context.md only if validation passes. Throws ContextContaminationError
 * on any prejudicial pattern. Callers should prefer this over
 * `writeFileSync(..., "context.md")`.
 *
 * @param {string} path       Absolute file path ending in `context.md`.
 * @param {string} content    Proposed body.
 * @param {object} [opts]     See validateContextMd.
 */
export function writeContextMd(path, content, opts = {}) {
  const { ok, reasons } = validateContextMd(content, opts);
  if (!ok) throw new ContextContaminationError(reasons);
  writeFileSync(path, content);
}

/**
 * Assemble a reviewer context.md from non-prejudicial sources and write it
 * iff the content is clean. Used by the acceptance-testing skill when
 * wicked-brain (or any other upstream knowledge source) contributes cold
 * domain knowledge before reviewer dispatch.
 *
 * If `brainKnowledge` is empty / undefined, no context.md is written and the
 * function returns `{ written: false }` — the reviewer still has scenario +
 * plan + evidence and runs unchanged.
 *
 * If validation fails, the function does NOT write context.md and returns
 * `{ written: false, rejected: true, reasons }`. The caller should log this
 * and proceed — a rejected context.md is a safer outcome than a contaminated
 * one.
 *
 * @param {object} opts
 * @param {string} opts.evidenceDir       Absolute evidence dir path.
 * @param {string} opts.brainKnowledge    Proposed cold-knowledge body.
 * @param {string} [opts.runId]           Current run UUID, added to extraForbidden.
 * @returns {{ written: boolean, rejected?: boolean, reasons?: Array, path?: string }}
 */
export function buildReviewerContext({ evidenceDir, brainKnowledge, runId }) {
  if (!brainKnowledge || !brainKnowledge.trim()) return { written: false };
  if (!existsSync(evidenceDir)) {
    throw new Error(`buildReviewerContext: evidenceDir does not exist: ${evidenceDir}`);
  }
  const extraForbidden = [];
  if (runId) extraForbidden.push(runId);
  const { ok, reasons } = validateContextMd(brainKnowledge, { extraForbidden });
  if (!ok) return { written: false, rejected: true, reasons };
  const path = evidenceDir.endsWith("/") ? evidenceDir + "context.md" : evidenceDir + "/context.md";
  writeFileSync(path, brainKnowledge);
  return { written: true, path };
}
