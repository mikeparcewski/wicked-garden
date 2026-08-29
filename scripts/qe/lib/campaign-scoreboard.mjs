#!/usr/bin/env node
/**
 * scripts/qe/lib/campaign-scoreboard.mjs — deterministic campaign scoreboard
 * assembly with a structural no-self-grading guard (TH-10, ADR 0006
 * "qe campaign"; RECON-TEST-HARNESS test-R10).
 *
 * Emits scoreboard rows in the shape the 2026-08 studio E2E campaign proved
 * (VERBATIM from studio-campaign-results.json — do not add or rename keys):
 *
 *   { "id": "S1", "grade": "PASS", "executor_claim": "…", "evidence_ok": true }
 *
 * Row semantics (validated against wicked-ledger evidence-manifest 2.1 —
 * docs/SCHEMA-CONTRACT.md in wicked-ledger):
 *
 *   id             stable scenario identity (the ledger `scenarios.name`)
 *   grade          the verdict OF RECORD — an isolated reviewer's verdicts
 *                  row, NEVER the executor's claim. `UNGRADED` when no
 *                  reviewer verdict exists yet.
 *   executor_claim the executor's own claim as TEXT beside the grade —
 *                  manifest 2.1 `scenario_evidence.status` (the field the
 *                  contract marks "the EXECUTOR'S CLAIM … never the verdict
 *                  of record"), falling back to the runner's claim parked in
 *                  the manifest verdict block (`reviewer:
 *                  "qe-runner/executor-claim"`, TH-4) or result.json.
 *   evidence_ok    wicked-ledger `validateManifest()` — the reviewer-side
 *                  validate-before-grading entry point (manifest 2.1) plus
 *                  the major-version floor. When the resolved wicked-ledger
 *                  predates `validateManifest` (published 0.3.0 does; the
 *                  manifest-2.1 release rides the XC-4 wave), evidence_ok is
 *                  FALSE — fail closed, never assume.
 *
 * Structural no-self-grading:
 *   - verdict rows whose reviewer is an executor identity
 *     ('qe-runner/executor-claim', anything matching /executor/i or
 *     /test-designer/i, or 'self') are never accepted as grades — each one
 *     is reported as a `self_grade_attempt` violation instead;
 *   - a non-INCONCLUSIVE grade on a bundle that fails validation is reported
 *     as `graded_invalid_bundle` (the SCHEMA-CONTRACT rule: schema-fail
 *     grades INCONCLUSIVE, never PASS/FAIL).
 *
 * The scenario-defect vs product-finding fork (campaign anti-expansion rule):
 * every non-PASS grade must carry a classification tag as the FIRST token of
 * the reviewer's verdict reason — `[scenario-defect]` (spawns a fix lane;
 * re-author + re-run) or `[product-finding]` (mirrors out to a GH issue and a
 * ledger `tasks` row; the campaign itself does NOT expand). Untagged non-PASS
 * rows land in `findings.unclassified` and block certification.
 *
 * Certification terminates: `certification.disposition` is always
 * 'certified' or 'not-certified' — never pending. See
 * skills/qe/refs/campaign-grading.md for the full playbook.
 *
 * Usage (from the target repo's root):
 *   node campaign-scoreboard.mjs [--repo-root <dir>] [--ledger-root <dir>]
 *        [--runs id,id,…] [--scenario-prefix <p>] [--json] [--out <file>]
 *        [--mirror-tasks]
 *   node campaign-scoreboard.mjs --validate-only <evidence-dir>
 *
 * Exit codes: 0 assembled (or validate-only OK) · 3 usage/system error ·
 *   5 validate-only: bundle fails the manifest contract ·
 *   6 validate-only: validator unavailable (wicked-ledger < manifest 2.1) ·
 *   7 --mirror-tasks could not write ledger tasks rows.
 *
 * wicked-ledger is resolved from the TARGET repo (like gate.mjs — the plugin
 * ships no node_modules): $WICKED_LEDGER_PKG_DIR override → bare import →
 * walk-up node_modules lookup from --repo-root. Ledger ROWS (runs/scenarios/
 * verdicts) are read straight from the DomainStore's canonical JSON files
 * (`<root>/<table>/<id>.json`), so scoreboard assembly itself needs no
 * package at all — only `evidence_ok` and `--mirror-tasks` do.
 */

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname, resolve, isAbsolute } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

// --- constants ---------------------------------------------------------------

/** Executor-identity deny-list: these NEVER source a grade (deny-dominates). */
const EXECUTOR_CLAIM_REVIEWER = "qe-runner/executor-claim";
const SELF_GRADE_PATTERNS = [/executor/i, /test-designer/i];

const NON_PASS_NEEDING_CLASSIFICATION = new Set([
  "FAIL",
  "PARTIAL",
  "CONDITIONAL",
  "INCONCLUSIVE",
]);

const CLASSIFICATION_RE = /^\s*\[(scenario-defect|product-finding)\]\s*/i;

// --- small helpers -----------------------------------------------------------

function readJsonSafe(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function loadRows(ledgerRoot, table) {
  const dir = join(ledgerRoot, table);
  if (!existsSync(dir)) return [];
  const rows = [];
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    const row = readJsonSafe(join(dir, f));
    if (row && row.deleted !== 1) rows.push(row);
  }
  return rows;
}

function isExecutorIdentity(reviewer) {
  const rev = String(reviewer ?? "").trim();
  if (!rev) return true; // an anonymous verdict never sources a grade
  if (rev === EXECUTOR_CLAIM_REVIEWER) return true;
  if (rev.toLowerCase() === "self") return true;
  return SELF_GRADE_PATTERNS.some((re) => re.test(rev));
}

function firstLine(text) {
  return String(text ?? "").split(/\r?\n/, 1)[0].trim();
}

/** Dual-read ledger-root resolution (mirrors wicked-ledger resolveLedgerRoot
 *  + crew's TH-2 WICKED_QE_LEDGER_DIR semantics: absolute wins, relative
 *  joins the repo root). */
export function resolveLedgerRootLocal(repoRoot, env = process.env) {
  const pinned = env.WICKED_QE_LEDGER_DIR;
  if (pinned) return isAbsolute(pinned) ? pinned : join(repoRoot, pinned);
  const current = join(repoRoot, ".wicked-qe");
  if (existsSync(current)) return current;
  const legacy = join(repoRoot, ".wicked-testing");
  if (existsSync(legacy)) return legacy;
  return current;
}

// --- wicked-ledger resolution (target-repo-anchored, like gate.mjs) ----------

function esmEntryForPackageDir(pkgDir) {
  const pj = join(pkgDir, "package.json");
  if (!existsSync(pj)) return null;
  const pkg = readJsonSafe(pj);
  if (!pkg) return null;
  const dot = pkg.exports && pkg.exports["."] !== undefined ? pkg.exports["."] : pkg.exports;
  const rel =
    (dot && typeof dot === "object" && (dot.import || dot.default)) ||
    (typeof dot === "string" ? dot : null) ||
    pkg.module ||
    pkg.main ||
    "index.js";
  return join(pkgDir, rel);
}

export async function resolveLedgerModule(repoRoot, env = process.env) {
  // 1. explicit override (tests, TH-6 wiring, unpublished-floor installs)
  if (env.WICKED_LEDGER_PKG_DIR) {
    const entry = esmEntryForPackageDir(env.WICKED_LEDGER_PKG_DIR);
    if (entry && existsSync(entry)) return await import(pathToFileURL(entry).href);
    return null;
  }
  // 2. bare import (global / hoisted install)
  try {
    return await import("wicked-ledger");
  } catch {
    /* fall through */
  }
  // 3. walk up from the target repo root
  let dir = resolve(repoRoot);
  for (let i = 0; i < 10; i++) {
    const cand = join(dir, "node_modules", "wicked-ledger");
    const entry = esmEntryForPackageDir(cand);
    if (entry && existsSync(entry)) {
      try {
        return await import(pathToFileURL(entry).href);
      } catch {
        return null;
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

// --- evidence extraction ------------------------------------------------------

/** The executor's claim as text — never a grade. Order: manifest-2.1
 *  scenario_evidence.status → the runner's claim parked in the manifest
 *  verdict block (TH-4) → result.json executor_claim → honest unknown. */
export function extractExecutorClaim(manifest, evidenceDir) {
  const se = manifest?.scenario_evidence;
  if (se && typeof se === "object" && se.status) {
    const notes = Array.isArray(se.notes) ? se.notes.join("; ") : se.notes;
    const cap = se.claim_level ? ` [${se.claim_level}]` : "";
    return `${se.status}${cap}${notes ? ` — ${notes}` : ""}`;
  }
  const v = manifest?.verdict;
  if (v && v.reviewer === EXECUTOR_CLAIM_REVIEWER) {
    return `${v.value}${v.reason ? ` — ${v.reason}` : ""}`;
  }
  const result = evidenceDir ? readJsonSafe(join(evidenceDir, "result.json")) : null;
  const rc = result?.executor_claim;
  if (rc && rc.value) return `${rc.value}${rc.reason ? ` — ${rc.reason}` : ""}`;
  return "unknown (no executor-claim artifact)";
}

/** evidence_ok: full validateManifest (manifest 2.1) + major floor.
 *  Validator missing → { ok:false } — fail closed. */
export function validateBundle(manifest, ledgerMod) {
  if (!manifest) {
    return { ok: false, violations: [{ field: "$", message: "manifest.json missing or unreadable" }] };
  }
  if (typeof ledgerMod?.validateManifest !== "function") {
    return {
      ok: false,
      validator: "unavailable",
      violations: [
        {
          field: "$",
          message:
            "validateManifest unavailable — resolved wicked-ledger predates the manifest-2.1 contract; " +
            "install the release carrying it (validate-before-grading is mandatory, fail closed)",
        },
      ],
    };
  }
  const res = ledgerMod.validateManifest(manifest);
  const violations = Array.isArray(res?.violations) ? [...res.violations] : [];
  const major = String(manifest.manifest_version ?? "").split(".")[0];
  if (major !== "2") {
    violations.push({
      field: "manifest_version",
      message: `manifest major '${major}' outside the supported floor (major == 2)`,
    });
  }
  return { ok: Boolean(res?.ok) && major === "2", validator: "wicked-ledger", violations };
}

// --- scoreboard assembly -------------------------------------------------------

export async function buildScoreboard({
  repoRoot = process.cwd(),
  ledgerRoot = null,
  runIds = null,
  scenarioPrefix = null,
  env = process.env,
} = {}) {
  const root = ledgerRoot ?? resolveLedgerRootLocal(repoRoot, env);
  const runs = loadRows(root, "runs");
  const scenarios = new Map(loadRows(root, "scenarios").map((s) => [s.id, s]));
  const verdictsByRun = new Map();
  for (const v of loadRows(root, "verdicts")) {
    if (!verdictsByRun.has(v.run_id)) verdictsByRun.set(v.run_id, []);
    verdictsByRun.get(v.run_id).push(v);
  }
  const ledgerMod = await resolveLedgerModule(repoRoot, env);
  const validatorAvailable = typeof ledgerMod?.validateManifest === "function";

  const rows = [];
  const violations = [];
  const findings = { scenario_defects: [], product_findings: [], unclassified: [] };
  const detail = []; // per-row provenance (kept OUTSIDE the 4-key rows)

  let selectedRuns = runs;
  if (Array.isArray(runIds) && runIds.length) {
    const want = new Set(runIds);
    selectedRuns = runs.filter((r) => want.has(r.id));
  }

  // deterministic order: by scenario name then started_at
  const named = selectedRuns.map((run) => {
    const scenario = scenarios.get(run.scenario_id);
    return { run, id: scenario?.name ?? run.scenario_id };
  });
  if (scenarioPrefix) {
    const p = String(scenarioPrefix);
    for (let i = named.length - 1; i >= 0; i--) {
      if (!named[i].id.startsWith(p)) named.splice(i, 1);
    }
  }
  named.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : String(a.run.started_at).localeCompare(String(b.run.started_at))));

  for (const { run, id } of named) {
    const evidenceDir = run.evidence_path
      ? isAbsolute(run.evidence_path)
        ? run.evidence_path
        : join(repoRoot, run.evidence_path)
      : join(root, "evidence", run.id);
    const manifest = readJsonSafe(join(evidenceDir, "manifest.json"));

    // grade: isolated-reviewer verdict rows only, newest first
    const rowVerdicts = (verdictsByRun.get(run.id) ?? []).sort((a, b) =>
      String(b.created_at ?? "").localeCompare(String(a.created_at ?? ""))
    );
    for (const v of rowVerdicts) {
      if (isExecutorIdentity(v.reviewer)) {
        violations.push({
          kind: "self_grade_attempt",
          id,
          run_id: run.id,
          detail: `verdicts row ${v.id ?? "?"} by executor identity '${v.reviewer}' refused as a grade source`,
        });
      }
    }
    const graded = rowVerdicts.find((v) => !isExecutorIdentity(v.reviewer)) ?? null;
    let grade = graded?.verdict ?? null;
    let gradeSource = graded ? "verdicts-row" : null;
    if (!grade && manifest?.verdict && !isExecutorIdentity(manifest.verdict.reviewer)) {
      grade = manifest.verdict.value;
      gradeSource = "manifest";
    }
    if (!grade) {
      grade = "UNGRADED";
      gradeSource = "none";
    }

    const validation = validateBundle(manifest, ledgerMod);
    const evidence_ok = validation.ok === true;

    if (!evidence_ok && grade !== "UNGRADED" && grade !== "INCONCLUSIVE") {
      violations.push({
        kind: "graded_invalid_bundle",
        id,
        run_id: run.id,
        detail:
          `grade '${grade}' rendered on a bundle that fails the manifest contract — ` +
          "schema-fail must grade INCONCLUSIVE (wicked-ledger SCHEMA-CONTRACT)",
      });
    }

    // the fork: classify every graded non-PASS
    const reason = graded?.reason ?? "";
    if (NON_PASS_NEEDING_CLASSIFICATION.has(grade)) {
      const m = CLASSIFICATION_RE.exec(reason);
      const rest = reason.replace(CLASSIFICATION_RE, "").trim();
      if (m && m[1].toLowerCase() === "scenario-defect") {
        findings.scenario_defects.push({
          id,
          run_id: run.id,
          grade,
          reason: rest,
          next: "fix lane: re-author the scenario/spec against the live target, re-run until PASS (bounded — see refs/campaign-grading.md)",
        });
      } else if (m && m[1].toLowerCase() === "product-finding") {
        findings.product_findings.push({
          id,
          run_id: run.id,
          grade,
          reason: rest,
          mirror: {
            project_id: run.project_id,
            title: `[product-finding] ${id}: ${firstLine(rest) || grade}`.slice(0, 200),
            body:
              `Campaign product finding (qe campaign, TH-10 fork).\n\n` +
              `- scoreboard id: ${id}\n- run_id: ${run.id}\n- grade: ${grade}\n` +
              `- evidence: ${evidenceDir}\n\n${rest}\n\n` +
              `Mirror to a GitHub issue in the PRODUCT repo and record the URL here; ` +
              `the campaign does not expand to chase this (anti-expansion rule).`,
            status: "open",
            assignee_skill: null,
          },
        });
      } else {
        findings.unclassified.push({
          id,
          run_id: run.id,
          grade,
          reason,
          detail:
            "non-PASS grade without a [scenario-defect]/[product-finding] tag — " +
            "the reviewer must classify it; blocks certification",
        });
      }
    }

    rows.push({ id, grade, executor_claim: extractExecutorClaim(manifest, evidenceDir), evidence_ok });
    detail.push({
      id,
      run_id: run.id,
      evidence_dir: evidenceDir,
      grade_source: gradeSource,
      reviewer: graded?.reviewer ?? null,
      validator: validation.validator ?? (validatorAvailable ? "wicked-ledger" : "unavailable"),
      validation_violations: validation.violations ?? [],
    });
  }

  const summary = { total: rows.length, PASS: 0, FAIL: 0, PARTIAL: 0, CONDITIONAL: 0, INCONCLUSIVE: 0, UNGRADED: 0, other: 0, evidence_ok: 0 };
  for (const r of rows) {
    if (r.grade in summary) summary[r.grade] += 1;
    else summary.other += 1;
    if (r.evidence_ok) summary.evidence_ok += 1;
  }

  // Certification TERMINATES: exactly one of two dispositions, derived, never pending.
  const blockers = [];
  if (rows.length === 0) blockers.push("no scoreboard rows (nothing executed)");
  if (summary.UNGRADED > 0) blockers.push(`${summary.UNGRADED} row(s) UNGRADED (no isolated-reviewer verdict)`);
  const nonPass = rows.filter((r) => r.grade !== "PASS" && r.grade !== "UNGRADED").length;
  if (nonPass > 0) blockers.push(`${nonPass} row(s) graded non-PASS`);
  const badEvidence = rows.filter((r) => !r.evidence_ok).length;
  if (badEvidence > 0) blockers.push(`${badEvidence} row(s) with evidence_ok=false`);
  if (violations.length > 0) blockers.push(`${violations.length} violation(s): ${[...new Set(violations.map((v) => v.kind))].join(", ")}`);
  if (findings.unclassified.length > 0) blockers.push(`${findings.unclassified.length} unclassified non-PASS row(s)`);

  return {
    scoreboard: rows,
    summary,
    findings,
    violations,
    certification: {
      disposition: blockers.length === 0 ? "certified" : "not-certified",
      blockers,
    },
    validator: validatorAvailable ? "wicked-ledger" : "unavailable",
    manifest_floor: "2.1",
    ledger_root: root,
    generated_at: new Date().toISOString(),
    detail,
  };
}

// --- product-finding mirror (ledger tasks rows) --------------------------------

export async function mirrorProductFindings(envelope, { repoRoot = process.cwd(), env = process.env } = {}) {
  const mod = await resolveLedgerModule(repoRoot, env);
  if (typeof mod?.createDomainStore !== "function") {
    return { ok: false, mirrored: 0, reason: "wicked-ledger not resolvable — cannot write tasks rows" };
  }
  const store = mod.createDomainStore({ root: envelope.ledger_root });
  const existingTitles = new Set(
    loadRows(envelope.ledger_root, "tasks")
      .filter((t) => t.status !== "closed")
      .map((t) => t.title)
  );
  let mirrored = 0;
  const created = [];
  for (const f of envelope.findings.product_findings) {
    if (existingTitles.has(f.mirror.title)) continue; // idempotent re-runs
    const row = store.create("tasks", f.mirror);
    created.push({ task_id: row.id, title: row.title });
    mirrored += 1;
  }
  return { ok: true, mirrored, created };
}

// --- CLI -----------------------------------------------------------------------

const IS_MAIN = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (IS_MAIN) {
  const { values } = parseArgs({
    options: {
      "repo-root": { type: "string" },
      "ledger-root": { type: "string" },
      runs: { type: "string" },
      "scenario-prefix": { type: "string" },
      json: { type: "boolean", default: false },
      out: { type: "string" },
      "validate-only": { type: "string" },
      "mirror-tasks": { type: "boolean", default: false },
    },
  });

  const repoRoot = values["repo-root"] ? resolve(values["repo-root"]) : process.cwd();

  try {
    if (values["validate-only"]) {
      const dir = resolve(values["validate-only"]);
      const manifest = readJsonSafe(join(dir, "manifest.json"));
      const mod = await resolveLedgerModule(repoRoot);
      const res = validateBundle(manifest, mod);
      process.stdout.write(JSON.stringify({ ok: res.ok, validator: res.validator ?? null, violations: res.violations }, null, 2) + "\n");
      process.exit(res.ok ? 0 : res.validator === "unavailable" ? 6 : 5);
    }

    const envelope = await buildScoreboard({
      repoRoot,
      ledgerRoot: values["ledger-root"] ? resolve(values["ledger-root"]) : null,
      runIds: values.runs ? values.runs.split(",").map((s) => s.trim()).filter(Boolean) : null,
      scenarioPrefix: values["scenario-prefix"] ?? null,
    });

    if (values["mirror-tasks"]) {
      const mirror = await mirrorProductFindings(envelope, { repoRoot });
      envelope.mirror = mirror;
      if (!mirror.ok) {
        process.stderr.write(`mirror-tasks failed: ${mirror.reason}\n`);
        process.stdout.write(JSON.stringify(envelope, null, 2) + "\n");
        process.exit(7);
      }
    }

    const text = values.json
      ? JSON.stringify(envelope, null, 2)
      : [
          `qe campaign scoreboard — ${envelope.ledger_root}`,
          ...envelope.scoreboard.map(
            (r) => `  ${r.id.padEnd(24)} ${r.grade.padEnd(12)} evidence_ok=${r.evidence_ok} :: ${r.executor_claim}`
          ),
          `  certification: ${envelope.certification.disposition}` +
            (envelope.certification.blockers.length ? ` (${envelope.certification.blockers.join(" · ")})` : ""),
        ].join("\n");
    if (values.out) writeFileSync(values.out, JSON.stringify(envelope, null, 2) + "\n", "utf8");
    process.stdout.write(text + "\n");
    process.exit(0);
  } catch (err) {
    process.stderr.write(`campaign-scoreboard error: ${err?.stack ?? err}\n`);
    process.exit(3);
  }
}
