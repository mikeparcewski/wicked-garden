#!/usr/bin/env node
// Walkthrough record tool (WT-G2, DES-walkthrough-proof §4.4-4.7).
//
//   wicked-garden run scripts/demo/walkthrough.mjs record [--storyline <path>]
//   wicked-garden run scripts/demo/walkthrough.mjs seal   --root <dir>
//
// Required env for record: WICKED_EVIDENCE_ROOT, WICKED_RUN_ID, WICKED_RUN_UNIT, WICKED_TREE
// Safety: WICKED_WALKTHROUGH_JAIL must be set; without it writes INCONCLUSIVE(unjailed_host) and exits 0.
//
// Runtime: wicked-garden run scripts/demo/walkthrough.mjs <action> [args]
//   Manual alternative: node scripts/demo/walkthrough.mjs <action> [args]

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import net from "node:net";
import { spawnSync, spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";

import { makeSegmentRecorder, failedAtInVideo, SEGMENT_TRIM_START } from "./record.mjs";
import { fixtureOrigin } from "./readonly.mjs";
import { crewRunStamp } from "../qe/lib/crew-run.mjs";

// ---- arg parsing ---------------------------------------------------------------
const [action, ...rawArgs] = process.argv.slice(2);

function argVal(flag) {
  const i = rawArgs.indexOf(flag);
  return i >= 0 ? rawArgs[i + 1] ?? null : null;
}

if (action !== "record" && action !== "seal") {
  process.stderr.write("usage: walkthrough.mjs <record|seal> [--storyline <path>] [--root <dir>]\n");
  process.exit(2);
}

// ---- seal action (standalone, no env required) ---------------------------------
if (action === "seal") {
  const sealRoot = argVal("--root") ?? process.env.WICKED_EVIDENCE_ROOT;
  if (!sealRoot) { process.stderr.write("seal: --root <dir> required\n"); process.exit(2); }
  const sha = computeBundleSha(path.resolve(sealRoot));
  process.stdout.write(JSON.stringify({ bundle_sha: sha }) + "\n");
  process.exit(0);
}

// ---- require WICKED_EVIDENCE_ROOT before any writes ----------------------------
if (!process.env.WICKED_EVIDENCE_ROOT) {
  process.stderr.write("record: WICKED_EVIDENCE_ROOT is required\n");
  process.exit(2);
}

const ROOT = path.resolve(process.env.WICKED_EVIDENCE_ROOT);
const RUN_ID = process.env.WICKED_RUN_ID ?? "";
const STEP_ID = process.env.WICKED_RUN_UNIT ?? "";
const TREE = process.env.WICKED_TREE ?? "";

// Static helper: extract { key, verdict }[] from a storyline file without executing it.
// Falls back to [] only when the file cannot be read — callers must not pass empty chapters
// to a global cause unless the file is genuinely unreadable.
function tryStaticSegmentKeys(filePath) {
  try {
    const src = fs.readFileSync(filePath, "utf8");
    const keys = [];
    const re = /\bkey\s*:\s*["']([^"']+)["']/g;
    let m;
    while ((m = re.exec(src)) !== null) keys.push(m[1]);
    return keys.map((k) => ({ key: k, verdict: "INCONCLUSIVE" }));
  } catch { return []; }
}

// Resolve storyline path early so the jail check can enumerate chapters.
const _earlyStoryPath = (() => {
  const arg = argVal("--storyline");
  if (arg) return path.resolve(arg);
  return path.join(path.dirname(ROOT), "author", STEP_ID, "storyline.mjs");
})();

// ---- jail check ----------------------------------------------------------------
if (!process.env.WICKED_WALKTHROUGH_JAIL) {
  fs.mkdirSync(ROOT, { recursive: true });
  const unjailedChapters = tryStaticSegmentKeys(_earlyStoryPath);
  writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "unjailed_host", chapters: unjailedChapters });
  writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "unjailed_host" });
  const sha = computeBundleSha(ROOT);
  process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({
    tree: TREE, storyline_sha: null, contract_shas: {}, bundle_sha: sha,
    overall: "INCONCLUSIVE", cause: "unjailed_host", chapters: unjailedChapters,
  }) + "\n");
  process.exit(0);
}

if (!RUN_ID || !STEP_ID || !TREE) {
  process.stderr.write("record: WICKED_RUN_ID, WICKED_RUN_UNIT, WICKED_TREE are required\n");
  process.exit(2);
}

// ---- resolve wicked-ledger (via NODE_PATH or target-repo node_modules) ---------
const _req = createRequire(import.meta.url);
let ledger = null;
try { ledger = _req("wicked-ledger"); } catch { /* degrade gracefully */ }

// ---- helpers -------------------------------------------------------------------

function sha256Buf(buf) { return crypto.createHash("sha256").update(buf).digest("hex"); }
function sha256File(p) { return sha256Buf(fs.readFileSync(p)); }
function sha256Str(s) { return sha256Buf(Buffer.from(s, "utf8")); }

function writeResult(root, obj) {
  fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, "result.json"), JSON.stringify(obj, null, 2) + "\n");
}

function writeProgress(root, obj) {
  fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, "progress.json"), JSON.stringify(obj, null, 2) + "\n");
}

/** sha256 over sorted (rel:sha\n) of every file under root except app/ and data/. */
function computeBundleSha(root) {
  const pairs = [];
  walkForSeal(root, root, pairs);
  pairs.sort((a, b) => a[0].localeCompare(b[0]));
  const h = crypto.createHash("sha256");
  for (const [rel, sha] of pairs) h.update(`${rel}:${sha}\n`);
  return h.digest("hex");
}

function walkForSeal(root, dir, out) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    const rel = path.relative(root, full);
    const top = rel.split(path.sep)[0];
    if (top === "app" || top === "data") continue;
    if (e.isDirectory()) { walkForSeal(root, full, out); }
    else if (e.isFile()) { try { out.push([rel, sha256File(full)]); } catch { /* skip unreadable */ } }
  }
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => { const { port } = srv.address(); srv.close(() => resolve(port)); });
    srv.on("error", reject);
  });
}

async function gitArchive(tree, appDir) {
  fs.mkdirSync(appDir, { recursive: true });
  const archive = spawnSync("git", ["archive", "--format=tar", tree], { cwd: process.cwd(), maxBuffer: 512 * 1024 * 1024 });
  if (archive.error || archive.status !== 0) throw new Error(`git archive failed: ${archive.stderr?.toString()?.slice(-500)}`);
  const tar = spawnSync("tar", ["-x", "-C", appDir], { input: archive.stdout, maxBuffer: 512 * 1024 * 1024 });
  if (tar.error || tar.status !== 0) throw new Error(`tar -x failed: ${tar.stderr?.toString()?.slice(-500)}`);
}

async function pollFixtureReady(fixtureCfg, origin, timeout = 30_000) {
  if (typeof fixtureCfg.ready === "function") return fixtureCfg.ready(origin);
  const url = typeof fixtureCfg.ready === "string" ? origin + fixtureCfg.ready : origin + "/";
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* not ready */ }
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`fixture not ready within ${timeout}ms at ${url}`);
}

/** Total size in bytes of all files under dir. */
function dirSizeBytes(dir) {
  let total = 0;
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) total += dirSizeBytes(full);
      else if (e.isFile()) { try { total += fs.statSync(full).size; } catch { /* skip */ } }
    }
  } catch { /* skip unreadable */ }
  return total;
}

// ---- vault resolution ----------------------------------------------------------

/** Resolve wicked-vault JS module. Mirrors scripts/qe/lib/vault-evidence.mjs resolution ladder. */
async function resolveWalkthroughVault() {
  const pinned = process.env.WICKED_QE_VAULT_PKG?.trim();
  if (pinned) {
    try {
      let entry = pinned;
      if (fs.statSync(pinned).isDirectory()) {
        // Find ESM entry from package.json
        const pj = path.join(pinned, "package.json");
        if (fs.existsSync(pj)) {
          const pkg = JSON.parse(fs.readFileSync(pj, "utf8"));
          const dot = pkg.exports && pkg.exports["."] !== undefined ? pkg.exports["."] : pkg.exports;
          const rel = (dot && typeof dot === "object" && (dot.import || dot.default))
            || (typeof dot === "string" ? dot : null) || pkg.module || pkg.main || "index.js";
          entry = path.join(pinned, rel);
        } else {
          entry = path.join(pinned, "index.mjs");
        }
      }
      const mod = await import(pathToFileURL(entry).href);
      if (typeof mod.record === "function" && typeof mod.findRoot === "function") return mod;
    } catch { return null; }
  }
  try {
    const mod = await import("wicked-vault");
    if (typeof mod.record === "function" && typeof mod.findRoot === "function") return mod;
  } catch { /* continue */ }
  try {
    const req2 = createRequire(path.join(process.cwd(), "__wt_anchor__.js"));
    const located = req2.resolve("wicked-vault");
    const esm = located.endsWith(".mjs") || located.endsWith(".js") ? located : located;
    const mod = await import(pathToFileURL(esm).href);
    if (typeof mod.record === "function" && typeof mod.findRoot === "function") return mod;
  } catch { /* unavailable */ }
  return null;
}

/** Resolve the wicked-vault CLI binary for cross-check. */
function findVaultBin() {
  const envBin = process.env.WICKED_VAULT_BIN;
  if (envBin !== undefined) return envBin || null; // empty = kill-switch
  for (const candidate of ["wicked-vault", path.join(process.cwd(), "node_modules/.bin", "wicked-vault")]) {
    const r = spawnSync(candidate, ["--version"], { encoding: "utf8", timeout: 5_000 });
    if (r.status === 0) return candidate;
  }
  return null;
}

/** Shell wicked-vault cross-check for scope/phase. Returns {available, overall, claims}.
 *  FAIL and ERROR exit non-zero — parse JSON anyway; only return unavailable when the binary can't spawn. */
function runVaultCrossCheck(scope, phase, vaultBin, vaultDir) {
  if (!vaultBin) return { available: false };
  const prefix = vaultBin.endsWith(".mjs") || vaultBin.endsWith(".js")
    ? ["node", vaultBin] : [vaultBin];
  const argv = [...prefix, "cross-check", "--scope", scope, "--phase", phase];
  const res = spawnSync(argv[0], argv.slice(1), {
    cwd: vaultDir, encoding: "utf8", timeout: 30_000,
  });
  if (res.error) return { available: false }; // binary could not spawn
  try {
    const data = JSON.parse(res.stdout);
    const gate = data.gate ?? data;
    if (typeof gate.overall !== "string") return { available: false };
    return { available: true, overall: gate.overall, claims: Array.isArray(gate.claims) ? gate.claims : [] };
  } catch {
    return { available: false }; // unparseable output → treat as unavailable
  }
}

/** Shell wicked-vault declare-contract for scope/phase. The spec path is the contract.json written by writeContract. */
function runVaultDeclareContract(scope, phase, contractPath, vaultBin, vaultDir) {
  if (!vaultBin) return false;
  const prefix = vaultBin.endsWith(".mjs") || vaultBin.endsWith(".js")
    ? ["node", vaultBin] : [vaultBin];
  const argv = [...prefix, "declare-contract", "--scope", scope, "--phase", phase, "--spec", contractPath];
  const res = spawnSync(argv[0], argv.slice(1), { cwd: vaultDir, encoding: "utf8", timeout: 30_000 });
  return !res.error && res.status === 0;
}

/** Shell wicked-vault record for a captured check. Returns the artifact id or null. */
function runVaultRecord(scope, phase, claimId, kind, capturePath, verifier, actor, vaultBin, vaultDir) {
  if (!vaultBin) return null;
  const prefix = vaultBin.endsWith(".mjs") || vaultBin.endsWith(".js")
    ? ["node", vaultBin] : [vaultBin];
  const verifierArg = verifier?.kind === "jq_pred" && verifier.params?.expr
    ? `jq_pred:${verifier.params.expr}` : null;
  const argv = [
    ...prefix, "record",
    "--scope", scope, "--phase", phase,
    "--claim", claimId, "--kind", kind,
    "--criteria", `walkthrough check ${claimId} (${kind})`,
    "--artifact", capturePath,
    "--actor", actor,
    ...(verifierArg ? ["--verifier", verifierArg] : []),
  ];
  const res = spawnSync(argv[0], argv.slice(1), { cwd: vaultDir, encoding: "utf8", timeout: 30_000 });
  if (res.error || res.status !== 0) return null;
  try { return JSON.parse(res.stdout).id ?? null; } catch { return null; }
}

// ---- contract + evidence recording ---------------------------------------------

/** Canonical verifier shape for vault contract (no invented strings). */
function verifierForCheck(def) {
  if (def.verify && typeof def.verify === "object") return def.verify;
  switch (def.kind) {
    case "locator":  return { kind: "jq_pred", params: { expr: ".inner_text != null" } };
    case "probe":    return { kind: "jq_pred", params: { expr: ".raw.exit_code == 0" } };
    case "artifact": return { kind: "jq_pred", params: { expr: ".sha256 != null" } };
    case "guard":    return { kind: "jq_pred", params: { expr: "(.foreign_writes | length) == 0 and ((.console_errors // []) | length) == 0" } };
    case "join":     return { kind: "jq_pred", params: { expr: ".joined | to_entries | all(.value != null)" } };
    default:         return { kind: "jq_pred", params: { expr: "false" } };
  }
}

function writeContract(root, chapterKey, checkDefs) {
  const dir = path.join(root, "vault", chapterKey);
  fs.mkdirSync(dir, { recursive: true });
  const contract = {
    required_evidence: checkDefs.map((c) => ({
      claim_id: c.id,
      kind: c.kind,
      verifier: verifierForCheck(c),
      required: true,
    })),
  };
  const contractPath = path.join(dir, "contract.json");
  fs.writeFileSync(contractPath, JSON.stringify(contract, null, 2) + "\n");
  return sha256File(contractPath);
}

function evidenceListForCapture(capture, def) {
  const ev = [];
  if (!capture) return ev;
  switch (def.kind) {
    case "locator":
      if (capture.inner_text !== undefined) ev.push({ type: "text", value: capture.inner_text });
      if (capture.frame) ev.push({ type: "screenshot", path: capture.frame });
      break;
    case "probe":
      if (capture.parsed_path) ev.push({ type: "json", path: capture.parsed_path });
      break;
    case "artifact":
      if (capture.path && capture.sha256) ev.push({ type: "file", path: capture.path, sha256: capture.sha256 });
      break;
    case "guard":
      ev.push({ type: "foreign_writes", count: (capture.foreign_writes ?? []).length });
      ev.push({ type: "console_errors", count: (capture.console_errors ?? []).length });
      break;
    case "join":
      ev.push({ type: "joined", keys: Object.keys(capture.joined ?? {}) });
      break;
  }
  return ev;
}

// ---- collector -----------------------------------------------------------------

async function runCollector(def, { stage, root, dataDir, seg, id, priorCaptures, consoleErrors }) {
  const captureDir = path.join(root, "capture");
  fs.mkdirSync(captureDir, { recursive: true });

  switch (def.kind) {
    case "locator": {
      let innerText = null, ariaSnap = null, framePath = null;
      try { innerText = await stage.app.locator(def.selector).first().innerText({ timeout: 5000 }); } catch { /* absent */ }
      try { ariaSnap = await stage.page.accessibility?.snapshot?.() ?? null; } catch { /* absent */ }
      const fp = path.join(captureDir, `${id}.png`);
      try { await stage.page.screenshot({ path: fp }); framePath = path.relative(root, fp); } catch { /* skip */ }
      return { inner_text: innerText, aria_snapshot: ariaSnap, frame: framePath };
    }

    case "probe": {
      const probeName = def.name;
      const probeArgv = seg._fixture?.probes?.[probeName];
      if (!probeArgv) {
        return { _verifier_error: `probe '${probeName}' not in fixture.probes`, raw: null, parsed: null };
      }
      let result;
      try {
        result = spawnSync(probeArgv[0], probeArgv.slice(1), {
          cwd: path.join(root, "app"),
          env: { ...process.env, DATA_DIR: dataDir },
          encoding: "utf8",
          timeout: 15_000,
        });
      } catch (e) {
        return { _verifier_error: `probe spawn error: ${e.message}`, raw: null, parsed: null };
      }
      if (result.error) {
        return { _verifier_error: `probe spawn error: ${result.error.message}`, raw: null, parsed: null };
      }
      const raw = { argv: probeArgv, exit_code: result.status, stdout: result.stdout ?? "", stderr: result.stderr ?? "" };
      let parsed = null;
      const fmt = def.parse ?? "json";
      if (fmt === "json" || fmt === "sqlite-json") {
        try { parsed = JSON.parse(raw.stdout); } catch { /* non-JSON output is fine */ }
      } else if (fmt === "jsonl") {
        parsed = raw.stdout.split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return l; } });
      } else if (fmt === "text") {
        parsed = raw.stdout;
      }
      const parsedPath = path.join(captureDir, `${id}.parsed.json`);
      fs.writeFileSync(parsedPath, JSON.stringify(parsed, null, 2) + "\n");
      return { raw, parsed, parsed_path: path.relative(root, parsedPath) };
    }

    case "artifact": {
      const artRelPath = def.path ?? "";
      // Reject absolute paths and any ../ traversal with either separator (catches Windows forward-slash too)
      if (path.isAbsolute(artRelPath) || /(?:^|[\\/])\.\.(?:[\\/]|$)/.test(artRelPath)) {
        const e = new Error(`artifact path escapes DATA_DIR: ${artRelPath}`);
        e.code = "artifact_path_escape";
        throw e;
      }
      const artFull = path.join(dataDir, artRelPath);
      if (!fs.existsSync(artFull)) {
        return { _verifier_error: `artifact not found: ${artRelPath}`, path: artRelPath, sha256: null };
      }
      // Resolve symlinks and verify the target stays within DATA_DIR
      let realArt, realData;
      try {
        realArt = fs.realpathSync(artFull);
        realData = fs.realpathSync(dataDir);
      } catch {
        const e = new Error(`artifact path escapes DATA_DIR: ${artRelPath}`);
        e.code = "artifact_path_escape";
        throw e;
      }
      if (realArt !== realData && !realArt.startsWith(realData + path.sep)) {
        const e = new Error(`artifact path escapes DATA_DIR via symlink: ${artRelPath}`);
        e.code = "artifact_path_escape";
        throw e;
      }
      return { path: artRelPath, sha256: sha256File(artFull) };
    }

    case "guard": {
      return {
        foreign_writes: [...(stage.blocked ?? [])],
        console_errors: [...(consoleErrors ?? [])].map((m) => (typeof m === "string" ? m : m.text ?? String(m))),
      };
    }

    case "join": {
      const joined = {};
      for (const srcId of (def.sources ?? [])) {
        const cap = (priorCaptures ?? {})[srcId];
        joined[srcId] = cap?.parsed ?? cap?.inner_text ?? null;
      }
      return { joined };
    }

    default:
      throw new Error(`unknown collector kind: ${def.kind}`);
  }
}

// ---- judgment ------------------------------------------------------------------

/**
 * Judge a chapter's outcome.
 * A chapter is PASS only from a vault cross-check result — no local verifier fallback.
 * Vault unavailable (null crossCheck or !available) → every claim and chapter INCONCLUSIVE.
 *
 * @param {object} opts.crossCheck - vault cross-check result {available, overall, claims}
 * @param {object} opts.vaultEntries - {[checkId]: vaultEntryId | null}
 */
function judgeChapter(seg, captures, failedAtSec, { crossCheck = null, vaultEntries = {}, declared = true } = {}) {
  const defs = seg.checks ?? [];
  const claims = [];
  let verdict = "PASS";

  const vaultAvailable = crossCheck?.available === true;
  // Vault overall ERROR → every claim INCONCLUSIVE
  const vaultError = vaultAvailable && crossCheck.overall === "ERROR";

  // Build vault claim map for fast lookup
  const vaultClaimsMap = {};
  if (vaultAvailable && Array.isArray(crossCheck.claims)) {
    for (const c of crossCheck.claims) {
      vaultClaimsMap[c.claim_id ?? c.id] = c;
    }
  }

  for (const def of defs) {
    const cap = captures[def.id];
    let claimVerdict;

    if (!vaultAvailable || vaultError) {
      // Vault unavailable or errored → fail closed
      claimVerdict = "INCONCLUSIVE";
    } else {
      // Judge from vault verifier_status (vault available and non-error)
      const vc = vaultClaimsMap[def.id];
      if (!vc) {
        // Claim not recorded in vault (never reached)
        claimVerdict = "FAIL";
      } else {
        // result field (vault ≥0.7.0): "PASS"|"MISSING"|"FAIL"|"ERROR" (uppercase)
        // verifier_status (older vault): "pass"|"fail"|"error" (lowercase)
        const res = vc.result?.toUpperCase();
        const vs = vc.verifier_status?.toUpperCase();
        const r = res ?? vs;
        claimVerdict = r === "PASS" ? "PASS"
          : r === "MISSING" || r === "FAIL" ? "FAIL"
          : "INCONCLUSIVE";
        // A PASS must rest on evidence THIS run recorded; if our record call failed the vault's
        // PASS is not ours to claim.
        if (claimVerdict === "PASS" && !vaultEntries[def.id]) claimVerdict = "INCONCLUSIVE";
      }
    }

    if (claimVerdict === "FAIL") verdict = "FAIL";
    else if (claimVerdict === "INCONCLUSIVE" && verdict !== "FAIL") verdict = "INCONCLUSIVE";

    claims.push({
      id: def.id,
      kind: def.kind,
      verdict: claimVerdict,
      at_sec: cap?.at_sec ?? null,
      evidence: cap ? evidenceListForCapture(cap, def) : [],
      vault_entry: vaultEntries[def.id] ?? null,
    });
  }

  // Vault unavailable or errored → chapter INCONCLUSIVE regardless of check count. A PASS also
  // needs the vault's own overall PASS and a contract this run declared; anything else is not proven.
  if (!vaultAvailable || vaultError) verdict = "INCONCLUSIVE";
  else if (verdict === "PASS" && (crossCheck.overall !== "PASS" || !declared)) verdict = "INCONCLUSIVE";

  return { verdict, claims, failed_at_sec: failedAtSec ?? null, proves: seg.proves ?? [] };
}

// ---- manifest writing ----------------------------------------------------------

/**
 * Build (and optionally only validate) a chapter's 2.1 manifest.
 *
 * Every return carries the same key set — {ok, skipped, violations, manifest, manifestPath} —
 * so a caller can never read a missing manifest as a written one.
 *
 * Without wicked-ledger neither buildManifest nor validateManifest exists, so no 2.1 manifest
 * can be produced or checked. Only PASS needs that audit to be certain; FAIL/INCONCLUSIVE are
 * already certain from the vault cross-check, so they report an explicit `skipped` rather than
 * a bare `ok: true` that looks like the write succeeded.
 */
function buildWalkthroughManifest(seg, chapterResult, runId, projectId, scenarioId, evidenceDir, take, validateOnly = false) {
  if (!ledger) {
    if (chapterResult?.verdict === "PASS") {
      // Ledger absence must not silently pass: a PASS has no audit behind it.
      return { ok: false, skipped: false, violations: [{ field: "$", message: "ledger_unavailable" }], manifest: null, manifestPath: null };
    }
    return { ok: true, skipped: true, violations: [], manifest: null, manifestPath: null, reason: "ledger_unavailable" };
  }
  const { buildManifest, validateManifest } = ledger;
  const seKey = seg.key;

  const runRecord = {
    id: `${runId}:${seKey}`,
    project_id: projectId,
    scenario_id: scenarioId,
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
    status: chapterResult.verdict === "PASS" ? "passed" : chapterResult.verdict === "FAIL" ? "failed" : "inconclusive",
    evidence_path: evidenceDir,
    ...(RUN_ID ? { crew_run_id: RUN_ID } : {}),
  };
  const scenarioRecord = { id: scenarioId, name: `walkthrough:${seKey}` };
  const verdictRecord = {
    verdict: chapterResult.verdict,
    reviewer: "walkthrough/executor-claim",
    reason: `walkthrough chapter ${seKey}: ${chapterResult.verdict.toLowerCase()}`,
    created_at: new Date().toISOString(),
  };

  const scenarioEvidence = {
    scenario: `walkthrough:${seKey}`,
    status: chapterResult.verdict,
    claim_level: "machinery-verified",
    walkthrough: {
      crew_run_id: RUN_ID || null,
      step_id: STEP_ID || null,
      tree: TREE,
      take,
      failed_at_sec: chapterResult.failed_at_sec,
      proves: chapterResult.proves,
      checks: chapterResult.claims.map((c) => ({
        id: c.id,
        kind: c.kind,
        at_sec: c.at_sec,
        evidence: c.evidence,
        vault_entry: c.vault_entry,
      })),
    },
  };

  // Validate against the real wicked-ledger before writing.
  const checkManifest = {
    manifest_version: "2.1.0",
    run_id: runRecord.id,
    project_id: projectId,
    scenario_id: scenarioId,
    scenario_name: `walkthrough:${seKey}`,
    started_at: runRecord.started_at,
    finished_at: runRecord.finished_at,
    duration_ms: 0,
    status: runRecord.status,
    verdict: { value: chapterResult.verdict, reviewer: "walkthrough/executor-claim", recorded_at: new Date().toISOString() },
    environment: {},
    artifacts: [],
    scenario_evidence: scenarioEvidence,
  };
  let valResult;
  try { valResult = validateManifest(checkManifest); } catch (e) {
    return { ok: false, skipped: false, violations: [{ field: "$", message: e.message }], manifest: null, manifestPath: null };
  }
  if (!valResult?.ok) {
    return { ok: false, skipped: false, violations: valResult.violations, manifest: null, manifestPath: null };
  }
  if (validateOnly) return { ok: true, skipped: false, violations: [], manifest: null, manifestPath: null };

  try {
    fs.mkdirSync(evidenceDir, { recursive: true });
    const { manifest, path: manifestPath } = buildManifest({
      runRecord,
      scenarioRecord,
      verdictRecord,
      evidenceDir,
      qeVersion: "walkthrough/0.1",
      cli: "walkthrough",
      scenarioEvidence,
    });
    return { ok: true, skipped: false, violations: [], manifest, manifestPath };
  } catch (e) {
    return { ok: false, skipped: false, violations: [{ field: "$", message: e.message }], manifest: null, manifestPath: null };
  }
}

// ---- ledger rows ---------------------------------------------------------------

/**
 * Write one run row + one verdict row per chapter into <root>/.wicked-qe/.
 *
 * Returns {projectId, scenarioIds, unavailable, failedKeys}. `unavailable` means wicked-ledger
 * could not be resolved at all; `failedKeys` lists every chapter whose rows were NOT written
 * (all chapters when the store or the project cannot be opened). The caller fails closed on
 * both: a PASS without its ledger rows is not a proven PASS.
 */
function writeLedgerRows(root, overall, chapterResults, story, takeMap) {
  const allKeys = Object.keys(chapterResults);
  if (!ledger) return { projectId: null, scenarioIds: {}, unavailable: true, failedKeys: allKeys };
  const { createDomainStore } = ledger;
  const ledgerRoot = path.join(root, ".wicked-qe");
  let store;
  try { store = createDomainStore({ root: ledgerRoot }); } catch {
    return { projectId: null, scenarioIds: {}, unavailable: false, failedKeys: allKeys };
  }
  const projectName = `walkthrough:${story.title || "demo"}`;
  let project;
  try {
    project = store.list("projects", { name: projectName })[0] ?? store.create("projects", { name: projectName });
  } catch {
    try { store.close?.(); } catch { /* ok */ }
    return { projectId: null, scenarioIds: {}, unavailable: false, failedKeys: allKeys };
  }

  const scenarioIds = {};
  const failedKeys = [];
  for (const [key, result] of Object.entries(chapterResults)) {
    const scenarioName = `walkthrough:${key}`;
    const take = takeMap[key] ?? 1;
    try {
      const scenario = store.list("scenarios", { project_id: project.id, name: scenarioName })[0]
        ?? store.create("scenarios", { project_id: project.id, name: scenarioName, format_version: "1.0", body: scenarioName });
      scenarioIds[key] = scenario.id;
      const status = result.verdict === "PASS" ? "passed" : result.verdict === "FAIL" ? "failed" : "inconclusive";
      store.create("runs", {
        id: `${RUN_ID}-${key}`,
        project_id: project.id,
        scenario_id: scenario.id,
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
        status,
        evidence_path: path.join(root, "vault", key),
        ...crewRunStamp(),
        step_id: STEP_ID || null,
        tree: TREE,
        take,
      });
      store.create("verdicts", {
        run_id: `${RUN_ID}-${key}`,
        verdict: result.verdict,
        reviewer: "walkthrough/executor-claim",
        reason: `walkthrough ${key}: ${result.verdict}`,
        created_at: new Date().toISOString(),
        ...crewRunStamp(),
        step_id: STEP_ID || null,
        tree: TREE,
        take,
      });
    } catch {
      failedKeys.push(key);
    }
  }
  try { store.close?.(); } catch { /* optional */ }
  return { projectId: project.id, scenarioIds, unavailable: false, failedKeys };
}

// ---- read guard.json for real take number -------------------------------------

function readGuardTake(segmentsDir, key) {
  try {
    const g = JSON.parse(fs.readFileSync(path.join(segmentsDir, key, "guard.json"), "utf8"));
    return typeof g.take === "number" ? g.take : 1;
  } catch { return 1; }
}

// ---- main record flow ----------------------------------------------------------

async function main() {
  fs.mkdirSync(ROOT, { recursive: true });

  // Resolve vault + vault bin (fail-open — only used for recording claims).
  // All vault operations land in ROOT/vault/; pin the root with an anchor BEFORE any call.
  // --cwd starts the upward search — without an anchor in ROOT/vault/, it resolves to the
  // repo's ancestor .wicked-vault and writes evidence into the checked-out tree.
  const _vaultDir = path.join(ROOT, "vault");
  fs.mkdirSync(_vaultDir, { recursive: true });
  const _vaultAnchorDir = path.join(_vaultDir, ".wicked-vault");
  if (!fs.existsSync(path.join(_vaultAnchorDir, "vault.json"))) {
    fs.mkdirSync(_vaultAnchorDir, { recursive: true });
    fs.writeFileSync(
      path.join(_vaultAnchorDir, "vault.json"),
      JSON.stringify({ schema_version: 1, store_mode: "in-repo", payload_max_bytes: 1048576 }, null, 2) + "\n",
    );
  }
  // vault 0.7.0 does not auto-create its subdirs; create them so record succeeds.
  for (const sub of ["payloads", "entries"]) {
    fs.mkdirSync(path.join(_vaultAnchorDir, sub), { recursive: true });
  }
  const _vault = await resolveWalkthroughVault();
  let _vaultRoot = null;
  if (_vault) {
    try { _vaultRoot = _vault.findRoot(_vaultDir, { create: true }); } catch { /* vault root creation failed */ }
  }
  const _vaultBin = findVaultBin();

  // Disk cap (bytes; 0 = no cap)
  const DISK_CAP = process.env.WICKED_WALKTHROUGH_DISK_CAP
    ? parseInt(process.env.WICKED_WALKTHROUGH_DISK_CAP, 10) : 0;

  // Locate storyline
  const storyArgPath = argVal("--storyline");
  let storyPath;
  if (storyArgPath) {
    storyPath = path.resolve(storyArgPath);
  } else {
    const authorDir = path.join(path.dirname(ROOT), "author", STEP_ID);
    const autoPath = path.join(authorDir, "storyline.mjs");
    storyPath = autoPath;
  }

  if (!fs.existsSync(storyPath)) {
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused", reason: `storyline not found: ${storyPath}`, chapters: [] });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: null, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "storyline_refused", chapters: [] }) + "\n");
    process.exit(0);
  }

  // 1. Copy storyline, record sha256
  const storyDest = path.join(ROOT, "storyline.mjs");
  fs.copyFileSync(storyPath, storyDest);
  const storySha = sha256File(storyPath);

  // Load the storyline
  let story;
  try {
    story = (await import(pathToFileURL(storyPath).href)).default;
  } catch (e) {
    const refusedChapters = tryStaticSegmentKeys(storyPath);
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused", reason: e.message, chapters: refusedChapters });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: storySha, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "storyline_refused", chapters: refusedChapters }) + "\n");
    process.exit(0);
  }

  if (!story?.fixture?.start || !Array.isArray(story?.segments)) {
    const chapters = Array.isArray(story?.segments)
      ? story.segments.filter((s) => !s.intro).map((s) => ({ key: s.key, verdict: "INCONCLUSIVE" }))
      : [];
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused", reason: "storyline missing fixture.start or segments[]", chapters });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: storySha, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "storyline_refused", chapters }) + "\n");
    process.exit(0);
  }

  // Chapter keys and check ids become path segments under <root>; refuse anything that could escape.
  const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
  const badIds = [];
  for (const s of story.segments) {
    if (!s.intro && !SAFE_ID.test(String(s.key ?? ""))) badIds.push(`segment key ${JSON.stringify(s.key)}`);
    for (const c of s.checks ?? []) if (!SAFE_ID.test(String(c.id ?? ""))) badIds.push(`check id ${JSON.stringify(c.id)}`);
  }
  if (badIds.length) {
    const chapters = story.segments.filter((s) => !s.intro).map((s) => ({ key: s.key, verdict: "INCONCLUSIVE" }));
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused", reason: `unsafe identifiers: ${badIds.join(", ")}`, chapters });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "storyline_refused" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: storySha, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "storyline_refused", chapters }) + "\n");
    process.exit(0);
  }

  // 2. Git archive WICKED_TREE into <root>/app/
  const appDir = path.join(ROOT, "app");
  const allChapters = story.segments.filter((s) => !s.intro).map((s) => ({ key: s.key, verdict: "INCONCLUSIVE" }));
  try {
    await gitArchive(TREE, appDir);
  } catch (e) {
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "fixture_unavailable", reason: `git archive failed: ${e.message}`, chapters: allChapters });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "fixture_unavailable" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: storySha, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "fixture_unavailable", chapters: allChapters }) + "\n");
    process.exit(0);
  }

  // Symlink fixture.reuse dirs
  for (const dir of (story.fixture?.reuse ?? [])) {
    const src = path.resolve(process.cwd(), dir);
    const dst = path.join(appDir, dir);
    if (fs.existsSync(src) && !fs.existsSync(dst)) {
      try { fs.symlinkSync(src, dst); } catch { /* non-fatal */ }
    }
  }

  // 3. Spawn fixture, poll ready
  const dataDir = path.join(ROOT, "data");
  fs.mkdirSync(dataDir, { recursive: true });
  let fixturePort;
  try { fixturePort = await freePort(); } catch (e) {
    fixturePort = 0;
  }
  const fixtureOriginStr = `http://127.0.0.1:${fixturePort}`;
  const startArgv = story.fixture.start;
  const fixtureEnv = { ...process.env, PORT: String(fixturePort), DATA_DIR: dataDir };

  const fixtureProc = spawn(startArgv[0], startArgv.slice(1), {
    cwd: appDir,
    env: fixtureEnv,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  fixtureProc.unref();
  // Drain stdout/stderr so a noisy fixture never blocks the pipe buffer.
  fixtureProc.stdout?.resume();
  fixtureProc.stderr?.resume();

  // Capture spawn errors (missing executable) so they fail fast instead of waiting for the ready timeout.
  let _fixtureSpawnErr = null;
  const _spawnErrPromise = new Promise((_, reject) => {
    fixtureProc.on("error", (err) => { _fixtureSpawnErr = err; reject(err); });
  });

  // Always kill the fixture's whole process group. SIGKILL: the recorder exits right after,
  // so there is no time to wait out a SIGTERM the fixture might ignore.
  const killFixture = () => {
    try { process.kill(-fixtureProc.pid, "SIGKILL"); } catch { /* already gone */ }
    try { fixtureProc.kill("SIGKILL"); } catch { /* already gone */ }
  };
  process.on("exit", killFixture);
  for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(sig, () => { killFixture(); process.exit(130); });
  }

  try {
    await Promise.race([pollFixtureReady(story.fixture, fixtureOriginStr), _spawnErrPromise]);
  } catch (e) {
    killFixture();
    const chapters = story.segments.filter((s) => !s.intro).map((s) => ({ key: s.key, verdict: "INCONCLUSIVE" }));
    writeResult(ROOT, { overall: "INCONCLUSIVE", cause: "fixture_unavailable", reason: e.message, chapters });
    writeProgress(ROOT, { overall: "INCONCLUSIVE", cause: "fixture_unavailable" });
    const sha = computeBundleSha(ROOT);
    process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({ tree: TREE, storyline_sha: storySha, contract_shas: {}, bundle_sha: sha, overall: "INCONCLUSIVE", cause: "fixture_unavailable", chapters }) + "\n");
    process.exit(0);
  }

  const writableOrigin = fixtureOrigin(fixtureOriginStr);
  const segmentsDir = path.join(ROOT, "segments");
  const brand = { name: story.title || "Walkthrough", accent: story.brand?.accent ?? "#ee0000", logoSvg: story.brand?.logoSvg ?? "" };

  // 4-5. Record each segment with check capture
  const chapterCaptures = {}; // { [segKey]: { [checkId]: captureResult } }
  const chapterVaultEntries = {}; // { [segKey]: { [checkId]: entryId | null } }
  const consoleErrBuf = { current: [] };

  const recorder = makeSegmentRecorder({
    story,
    baseUrl: fixtureOriginStr,
    fixture: writableOrigin,
    ffmpeg: process.env.FFMPEG || "ffmpeg",
    brand,
    segmentsDir,
    consoleHandler: (msg) => {
      if (msg.type() === "error" || msg.type() === "warning") {
        consoleErrBuf.current.push({ type: msg.type(), text: msg.text() });
      }
    },
    extendCtx: (baseCtx, seg, stage) => {
      const checkDefs = Object.fromEntries((seg.checks ?? []).map((c) => [c.id, c]));
      const segCaptures = {};
      const segVaultEntries = {};
      chapterCaptures[seg.key] = segCaptures;
      chapterVaultEntries[seg.key] = segVaultEntries;
      seg._fixture = story.fixture;
      return {
        check: async (id) => {
          const def = checkDefs[id];
          if (!def) throw new Error(`walkthrough: unknown check id '${id}' in segment ${seg.key}`);
          // Record the raw wall-clock instant; at_sec is mapped through the timeline clock after recording completes.
          const _wall_instant = stage.now();
          let capture;
          try {
            capture = await runCollector(def, {
              stage, root: ROOT, dataDir, seg, id,
              priorCaptures: segCaptures,
              consoleErrors: consoleErrBuf.current,
            });
          } catch (e) {
            capture = { _verifier_error: e.message };
          }
          segCaptures[id] = { ...capture, _wall_instant };

          // Write capture file for vault recording (without internal bookkeeping fields)
          const claimsDir = path.join(ROOT, "vault", seg.key, "claims");
          fs.mkdirSync(claimsDir, { recursive: true });
          const capturePath = path.join(claimsDir, `${id}.json`);
          const captureFileData = { ...capture };
          delete captureFileData._wall_instant;
          fs.writeFileSync(capturePath, JSON.stringify(captureFileData, null, 2) + "\n");

          // Record in vault — prefer CLI (matches contract verifier, avoids G8 pin violation)
          if (_vaultBin) {
            segVaultEntries[id] = runVaultRecord(
              `run:${RUN_ID}/step:${STEP_ID}`, `chapter:${seg.key}`,
              id, def.kind, capturePath, verifierForCheck(def),
              process.env.WICKED_VAULT_ACTOR || "garden-prove", _vaultBin, _vaultDir,
            );
          } else if (_vault && _vaultRoot) {
            try {
              const res = _vault.record(_vaultRoot, {
                artifact: capturePath,
                scope: `run:${RUN_ID}/step:${STEP_ID}`,
                phase: `chapter:${seg.key}`,
                claim: id,
                kind: def.kind,
                source: path.relative(ROOT, capturePath),
                actor: process.env.WICKED_VAULT_ACTOR || "garden-prove",
                criteria: `walkthrough check ${id} (${def.kind}) in chapter ${seg.key}`,
              });
              segVaultEntries[id] = res.id ?? null;
            } catch { segVaultEntries[id] = null; }
          }
        },
      };
    },
  });

  const chapterResults = {};
  const contractShas = {};
  const contractDeclared = {};
  const takeMap = {};
  let diskCapHit = false;

  /** Override ALL story chapters to INCONCLUSIVE with a global cause. */
  function setAllChaptersInconclusive(cause) {
    diskCapHit = cause === "disk_cap";
    for (const s of story.segments.filter((x) => !x.intro)) {
      chapterResults[s.key] = {
        verdict: "INCONCLUSIVE",
        claims: chapterResults[s.key]?.claims ?? [],
        failed_at_sec: chapterResults[s.key]?.failed_at_sec ?? null,
        proves: s.proves ?? [],
        _cause: cause,
      };
      if (!(s.key in contractShas)) {
        contractShas[s.key] = writeContract(ROOT, s.key, s.checks ?? []);
      }
    }
  }

  for (const seg of story.segments) {
    if (seg.intro) continue;
    consoleErrBuf.current = [];
    if (!chapterCaptures[seg.key]) chapterCaptures[seg.key] = {};

    // Check disk cap before each chapter — a global cause that makes EVERY chapter INCONCLUSIVE
    if (DISK_CAP > 0 && dirSizeBytes(ROOT) > DISK_CAP) {
      setAllChaptersInconclusive("disk_cap");
      break;
    }

    // Write the vault contract before recording, then declare it with the vault CLI
    const checkDefs = seg.checks ?? [];
    contractShas[seg.key] = writeContract(ROOT, seg.key, checkDefs);
    contractDeclared[seg.key] = false;
    if (_vaultBin) {
      contractDeclared[seg.key] = runVaultDeclareContract(
        `run:${RUN_ID}/step:${STEP_ID}`, `chapter:${seg.key}`,
        path.join(ROOT, "vault", seg.key, "contract.json"), _vaultBin, _vaultDir,
      );
    }

    let segErr = null;
    let failedAtSec = null;
    try {
      await recorder(seg);
    } catch (e) {
      segErr = e;
      // Try to read failed_at_sec from the failure.json the recorder wrote
      try {
        const guardPath = path.join(segmentsDir, seg.key, "guard.json");
        const guard = JSON.parse(fs.readFileSync(guardPath, "utf8"));
        const failedDir = path.join(segmentsDir, seg.key, `failed-${guard.take}`);
        const failureJson = JSON.parse(fs.readFileSync(path.join(failedDir, "failure.json"), "utf8"));
        failedAtSec = failureJson.failed_at_sec;
      } catch { /* not available */ }
    }

    // Read real take from guard.json (written by recorder on success or failure)
    const take = readGuardTake(segmentsDir, seg.key);
    takeMap[seg.key] = take;

    // Post-process: map each capture's wall instant through the recorder's timeline clock to get at_sec.
    // For a successful take the timeline stays at segmentsDir/<key>/timeline.json.
    // For a failed take the recorder moves it to segmentsDir/<key>/failed-<take>/timeline.json.
    const tlDir = segErr
      ? path.join(segmentsDir, seg.key, `failed-${take}`)
      : path.join(segmentsDir, seg.key);
    for (const cap of Object.values(chapterCaptures[seg.key] ?? {})) {
      if (cap._wall_instant !== undefined) {
        cap.at_sec = failedAtInVideo(tlDir, cap._wall_instant) ?? null;
        delete cap._wall_instant;
      }
    }

    // Run vault cross-check for this chapter
    const crossCheck = _vaultBin
      ? runVaultCrossCheck(`run:${RUN_ID}/step:${STEP_ID}`, `chapter:${seg.key}`, _vaultBin, _vaultDir)
      : null;

    chapterResults[seg.key] = judgeChapter(
      seg,
      chapterCaptures[seg.key] ?? {},
      failedAtSec,
      { crossCheck, vaultEntries: chapterVaultEntries[seg.key] ?? {}, declared: contractDeclared[seg.key] === true },
    );
  }

  // 6. Validate per-chapter manifests BEFORE writing ledger rows.
  //    Any manifest violation makes the chapter INCONCLUSIVE — including FAIL chapters.
  for (const seg of story.segments.filter((s) => !s.intro)) {
    const chResult = chapterResults[seg.key];
    const valResult = buildWalkthroughManifest(
      seg, chResult, RUN_ID, "walkthrough", `walkthrough:${seg.key}`,
      null, takeMap[seg.key] ?? 1, true /* validateOnly */,
    );
    if (valResult && !valResult.ok) {
      chapterResults[seg.key] = {
        ...chapterResults[seg.key], verdict: "INCONCLUSIVE",
        _manifest_violation: valResult.violations?.map((v) => `${v.field}: ${v.message}`).join("; "),
      };
    }
  }

  // Re-judge overall after manifest validation + disk cap
  const finalVerdicts = Object.values(chapterResults).map((r) => r.verdict);
  let finalOverall = diskCapHit ? "INCONCLUSIVE"
    : finalVerdicts.every((v) => v === "PASS") ? "PASS"
    : finalVerdicts.some((v) => v === "FAIL") ? "FAIL"
    : "INCONCLUSIVE";

  // Write ledger rows with final verdicts (after manifest validation has settled verdicts)
  const { projectId, scenarioIds, unavailable: ledgerUnavailable, failedKeys: ledgerFailedKeys } =
    writeLedgerRows(ROOT, finalOverall, chapterResults, story, takeMap);
  // Fail closed on the ledger: a chapter whose run/verdict rows were not written has no ledger
  // evidence, so a PASS there is not proven -> INCONCLUSIVE. A vault-verified FAIL stays FAIL
  // (it is already certain). When the module is missing entirely the validation pass above has
  // already downgraded every PASS; this also covers a store/project/row write that throws.
  const ledgerCause = ledgerUnavailable ? "ledger_unavailable" : "ledger_write_failed";
  let ledgerDowngrade = false;
  for (const key of ledgerFailedKeys ?? []) {
    const r = chapterResults[key];
    if (!r) continue;
    if (r.verdict === "PASS") {
      chapterResults[key] = { ...r, verdict: "INCONCLUSIVE", _cause: r._cause ?? ledgerCause };
      ledgerDowngrade = true;
    } else {
      chapterResults[key] = { ...r, _cause: r._cause ?? ledgerCause };
    }
  }
  if (ledgerDowngrade) {
    const lv = Object.values(chapterResults).map((r) => r.verdict);
    finalOverall = diskCapHit ? "INCONCLUSIVE"
      : lv.every((v) => v === "PASS") ? "PASS"
      : lv.some((v) => v === "FAIL") ? "FAIL"
      : "INCONCLUSIVE";
  }

  // Write per-chapter manifests with the real projectId/scenarioId from the ledger.
  // If a manifest write fails, downgrade the chapter to INCONCLUSIVE and re-judge overall.
  let manifestWriteViolation = false;
  for (const seg of story.segments.filter((s) => !s.intro)) {
    const evidenceDir = path.join(ROOT, "vault", seg.key, "evidence");
    const pid = projectId ?? "walkthrough";
    const sid = scenarioIds?.[seg.key] ?? `${pid}:${seg.key}`;
    const mResult = buildWalkthroughManifest(seg, chapterResults[seg.key], RUN_ID, pid, sid, evidenceDir, takeMap[seg.key] ?? 1);
    if (mResult && !mResult.ok) {
      chapterResults[seg.key] = {
        ...chapterResults[seg.key], verdict: "INCONCLUSIVE",
        _manifest_write_violation: mResult.violations?.map((v) => `${v.field}: ${v.message}`).join("; "),
      };
      manifestWriteViolation = true;
    } else if (mResult?.skipped) {
      // No ledger, so no 2.1 manifest could be built. Record that the artifact is absent
      // rather than leaving a silently missing manifest behind a "validation passed" branch.
      chapterResults[seg.key] = { ...chapterResults[seg.key], _manifest_skipped: mResult.reason ?? "skipped" };
    }
  }
  if (manifestWriteViolation) {
    const v2 = Object.values(chapterResults).map((r) => r.verdict);
    finalOverall = diskCapHit ? "INCONCLUSIVE"
      : v2.every((v) => v === "PASS") ? "PASS"
      : v2.some((v) => v === "FAIL") ? "FAIL"
      : "INCONCLUSIVE";
  }

  // 7. Write result.json + progress.json
  const resultChapters = Object.entries(chapterResults).map(([key, r]) => ({ key, verdict: r.verdict, failed_at_sec: r.failed_at_sec }));
  const resultObj = { overall: finalOverall, chapters: resultChapters };
  if (diskCapHit) resultObj.cause = "disk_cap";
  writeResult(ROOT, resultObj);
  writeProgress(ROOT, { overall: finalOverall, chapters: resultChapters });

  // 8. Print WALKTHROUGH-SEAL
  const bundleSha = computeBundleSha(ROOT);
  process.stdout.write("WALKTHROUGH-SEAL " + JSON.stringify({
    tree: TREE,
    storyline_sha: storySha,
    contract_shas: contractShas,
    bundle_sha: bundleSha,
    overall: finalOverall,
    chapters: resultChapters.map(({ key, verdict }) => ({ key, verdict })),
  }) + "\n");

  killFixture();
  process.exit(0);
}

main().catch((e) => {
  process.stderr.write(`walkthrough: fatal: ${e.message}\n${e.stack ?? ""}\n`);
  process.exit(1);
});
