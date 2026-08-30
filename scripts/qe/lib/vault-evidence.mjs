#!/usr/bin/env node
/**
 * scripts/qe/lib/vault-evidence.mjs — vault-backed campaign evidence
 * integrity (TH-17, ADR 0006 "qe campaign"; RECON-TEST-HARNESS test-R16).
 *
 * Turns a campaign evidence bundle into a tamper-evident, content-addressed
 * wicked-vault record, and the reviewer's grade into an APPEND-ONLY opinion
 * attestation — so a campaign PASS is re-derivable months later instead of
 * being a mutable JSON field someone once wrote.
 *
 * What gets vaulted: the bundle's `manifest.json` bytes. The manifest embeds
 * a sha256 for EVERY other artifact in the bundle (wicked-ledger
 * `collectArtifacts`), so vaulting the manifest binds the whole bundle
 * Merkle-style: `vault verify` re-derives the manifest payload hash (G2),
 * and `rederive` below re-hashes every artifact on disk against the
 * manifest the vault froze. Any byte of any artifact changing — months
 * later — diverges.
 *
 * ORDERING LAW (TH-19 → TH-17, enforced IN CODE, not in docs):
 * vault payloads are immutable and content-addressed — an unscrubbed
 * credential that reaches a vault write is PERMANENT. Therefore the ONLY
 * exported vault-write path in the qe pipeline, `recordEvidenceBundle`,
 * structurally cannot reach `vault.record` without first passing
 * `assertRedactionBeforeVault`, which requires:
 *   1. the executor's redaction marker — `result.json` carries
 *      `redaction.applied === true` (written by the runner's TH-19 seam,
 *      scripts/qe/runner/src/evidence.mjs) or is a TH-19 quarantine stub
 *      (`quarantined: true`, content already withheld). A bundle that did
 *      not go through the redacting executor is REFUSED — fail closed.
 *   2. a clean secret-scan re-run (the runner's own `scanForSecrets`
 *      detectors, scripts/qe/runner/src/redact.mjs) over every text
 *      artifact in the bundle, manifest included — belt and braces against
 *      a forged marker or a producer that bypassed `redactDeep`. Any hit
 *      REFUSES the vault write entirely (deny-dominates; the hit report
 *      carries pattern ids + offsets, never matched text).
 * Screenshots are pixel data and are not scanned — the same documented
 * TH-19 MVP limitation as the executor's own preflight.
 *
 * Reviewer grade → opinion attestation (vault G10): after grading, the
 * verdict is appended with `attestGrade` (PASS→pass, FAIL→reject,
 * everything else→unclear). The vault's independence check applies: the
 * evaluator identity must be deliberately asserted and differ from the
 * recording actor (the executor), so a self-grade is refused mechanically.
 *
 * RELEASE DEPENDENCY (documented, enforced by `resolveVaultModule`):
 * this flow needs the wicked-vault manifest-2.1 twin (`validateManifest` +
 * `CLAIM_LEVELS` exports — on wicked-vault main, UNRELEASED as of
 * 2026-08-30; npm wicked-vault 0.6.0 predates it and its vendored schema
 * rejects every 2.1 bundle). Until the next wicked-vault release, point
 * `WICKED_QE_VAULT_PKG` at a local checkout of wicked-vault main (or
 * `npm link` it); a pre-2.1 vault is refused fail-closed, never silently
 * degraded.
 *
 * CLI (from the target repo's root):
 *   node vault-evidence.mjs record   --evidence-dir <dir> [--repo-root <dir>]
 *        [--actor <id>] [--criteria <text>] [--extra-pattern <regex>]... [--json]
 *   node vault-evidence.mjs attest   --entry <id> --verdict <PASS|FAIL|...>
 *        [--evaluator <id>] [--rationale <text>] [--repo-root <dir>] [--json]
 *   node vault-evidence.mjs rederive --entry <id> [--evidence-dir <dir>]
 *        [--repo-root <dir>] [--json]
 *
 * Exit codes: 0 ok · 1 rederive divergence (tamper — deny) · 3 refusal /
 * usage / system error (incl. the ordering refusals above). Never a
 * vacuous pass: `rederive` on a missing bundle or entry is 3, not 0.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, isAbsolute, relative } from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

import { scanForSecrets, compileExtraPatterns } from "../runner/src/redact.mjs";

/** The one-line release dependency, stamped on every pre-2.1 refusal. */
export const VAULT_RELEASE_REQUIREMENT =
  "wicked-vault with the manifest-2.1 twin (validateManifest + CLAIM_LEVELS) is required — " +
  "on wicked-vault main but UNRELEASED (npm 0.6.0 predates it and rejects 2.1 bundles). " +
  "Until the next wicked-vault release: set WICKED_QE_VAULT_PKG to a local checkout of " +
  "wicked-vault main, or `npm link wicked-vault` from one.";

/** Typed refusal so callers (gate.mjs, tests) can tell WHY the write was refused. */
export class VaultEvidenceError extends Error {
  constructor(code, message, detail = {}) {
    super(message);
    this.name = "VaultEvidenceError";
    this.code = code; // REDACTION_ORDERING | SECRET_SCAN_HIT | MANIFEST_INVALID |
                      // BUNDLE_INCONSISTENT | VAULT_UNAVAILABLE | ENTRY_NOT_FOUND | USAGE
    this.detail = detail;
  }
}

// --- wicked-vault resolution (mirrors gate.mjs's wicked-ledger ladder) --------

function esmEntryForPackage(resolvedFile) {
  let dir = dirname(resolvedFile);
  for (let i = 0; i < 10; i++) {
    const pj = join(dir, "package.json");
    if (existsSync(pj)) {
      let pkg;
      try { pkg = JSON.parse(readFileSync(pj, "utf8")); } catch { return null; }
      const dot = pkg.exports && pkg.exports["."] !== undefined ? pkg.exports["."] : pkg.exports;
      const rel =
        (dot && typeof dot === "object" && (dot.import || dot.default)) ||
        (typeof dot === "string" ? dot : null) ||
        pkg.module || pkg.main || "index.js";
      return join(dir, rel);
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/**
 * Capability gate: is this module a wicked-vault WITH the manifest-2.1 twin?
 * npm 0.6.0 has record/attest/verify but NOT validateManifest/CLAIM_LEVELS —
 * that is the unreleased seam this flow depends on (see
 * VAULT_RELEASE_REQUIREMENT). Exported for tests.
 */
export function checkVaultCapability(mod) {
  if (!mod || typeof mod !== "object") return { ok: false, reason: "not a module" };
  const core = ["record", "verify", "attest", "findRoot", "listEntries", "listAttestations"];
  const missing = core.filter((f) => typeof mod[f] !== "function");
  if (missing.length > 0) {
    return { ok: false, reason: `resolved module is not wicked-vault (missing ${missing.join(", ")})` };
  }
  if (typeof mod.validateManifest !== "function" || !Array.isArray(mod.CLAIM_LEVELS)) {
    return { ok: false, pre21: true, reason: `resolved wicked-vault predates the manifest-2.1 twin. ${VAULT_RELEASE_REQUIREMENT}` };
  }
  return { ok: true };
}

/**
 * Resolve the wicked-vault module, fail-closed on capability:
 *   1. `WICKED_QE_VAULT_PKG` env — path to a wicked-vault package dir (or its
 *      entry file). The documented bridge until the next vault release.
 *   2. bare `import("wicked-vault")` (global / hoisted install).
 *   3. the target repo's node_modules (cwd-anchored resolution).
 * A resolved-but-pre-2.1 vault is a refusal, not a fallback.
 */
export async function resolveVaultModule({ cwd = process.cwd(), env = process.env } = {}) {
  const tried = [];

  const pinned = env.WICKED_QE_VAULT_PKG?.trim();
  if (pinned) {
    try {
      let entry = pinned;
      if (statSync(pinned).isDirectory()) entry = esmEntryForPackage(join(pinned, "package.json")) ?? join(pinned, "index.mjs");
      const mod = await import(pathToFileURL(entry).href);
      const cap = checkVaultCapability(mod);
      if (cap.ok) return { ok: true, vault: mod, source: `WICKED_QE_VAULT_PKG=${pinned}` };
      return { ok: false, reason: `WICKED_QE_VAULT_PKG=${pinned}: ${cap.reason}`, pre21: cap.pre21 };
    } catch (e) {
      // An explicit pin that doesn't load is an error, not a fall-through —
      // silently ignoring it could substitute an older ambient install.
      return { ok: false, reason: `WICKED_QE_VAULT_PKG=${pinned} failed to load: ${e.message}` };
    }
  }

  try {
    const mod = await import("wicked-vault");
    const cap = checkVaultCapability(mod);
    if (cap.ok) return { ok: true, vault: mod, source: "import:wicked-vault" };
    tried.push(`bare import: ${cap.reason}`);
    if (cap.pre21) return { ok: false, reason: cap.reason, pre21: true };
  } catch { tried.push("bare import: unresolvable"); }

  try {
    const require = createRequire(join(cwd, "__qe_vault_anchor__.js"));
    const located = require.resolve("wicked-vault");
    const esm = esmEntryForPackage(located) || located;
    const mod = await import(pathToFileURL(esm).href);
    const cap = checkVaultCapability(mod);
    if (cap.ok) return { ok: true, vault: mod, source: `cwd:${cwd}` };
    tried.push(`cwd resolution: ${cap.reason}`);
    if (cap.pre21) return { ok: false, reason: cap.reason, pre21: true };
  } catch { tried.push("cwd resolution: unresolvable"); }

  return { ok: false, reason: `wicked-vault unresolvable (${tried.join("; ")}). ${VAULT_RELEASE_REQUIREMENT}` };
}

// --- The TH-19 → TH-17 ordering gate ------------------------------------------

// Extensions treated as binary (not text-scannable — the documented TH-19
// pixel-data limitation). Everything else in the bundle is scanned as text.
const BINARY_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".webm", ".mp4", ".zip", ".pdf", ".woff", ".woff2"]);

function isBinaryName(name) {
  const dot = name.lastIndexOf(".");
  return dot !== -1 && BINARY_EXTS.has(name.slice(dot).toLowerCase());
}

/**
 * THE ordering assertion (TH-17 AC: "redaction runs before any vault write —
 * assert it in code"). Throws VaultEvidenceError on any violation; returns a
 * redaction proof `{ ok: true, marker, scanned }` on success. The proof
 * object is what unlocks the internal vault write below — there is no
 * exported path to `vault.record` that skips this function.
 *
 * @param {object} opts
 * @param {string} opts.evidenceDir  the bundle directory
 * @param {Array}  [opts.extraPatterns] compiled per-target patterns
 *                 (compileExtraPatterns) to scan IN ADDITION to the built-ins
 */
export function assertRedactionBeforeVault({ evidenceDir, extraPatterns = [] }) {
  if (!existsSync(evidenceDir)) {
    throw new VaultEvidenceError("REDACTION_ORDERING", `evidence dir not found: ${evidenceDir}`);
  }

  // 1. The executor's redaction marker. result.json is written by the
  //    runner's TH-19 seam AFTER redactDeep + the secret-scan preflight;
  //    its absence means this bundle never went through the redacting
  //    executor — refuse (fail closed), do not guess.
  const resultPath = join(evidenceDir, "result.json");
  if (!existsSync(resultPath)) {
    throw new VaultEvidenceError(
      "REDACTION_ORDERING",
      "result.json missing — bundle did not come from the redacting executor (TH-19); refusing the vault write (vault immutability makes leaks permanent)",
      { evidenceDir },
    );
  }
  let result;
  try {
    result = JSON.parse(readFileSync(resultPath, "utf8"));
  } catch (e) {
    throw new VaultEvidenceError("REDACTION_ORDERING", `result.json unparseable (${e.message}) — cannot prove redaction ran; refusing the vault write`, { evidenceDir });
  }
  const marker =
    result?.redaction?.applied === true ? "redaction.applied"
    : result?.quarantined === true ? "quarantined"
    : null;
  if (!marker) {
    throw new VaultEvidenceError(
      "REDACTION_ORDERING",
      "result.json carries no redaction marker (redaction.applied !== true and not a TH-19 quarantine stub) — redaction cannot be shown to have run before this vault write; refusing",
      { evidenceDir },
    );
  }

  // 2. Belt and braces: re-run the secret scan over every TEXT artifact in
  //    the bundle (manifest included). A forged marker or a producer that
  //    bypassed redactDeep is caught here. Hits carry pattern ids + offsets
  //    only — never matched text (safe to persist in error output).
  const scanned = [];
  const hits = [];
  for (const name of readdirSync(evidenceDir).sort()) {
    const full = join(evidenceDir, name);
    let st;
    try { st = statSync(full); } catch { continue; }
    if (!st.isFile() || isBinaryName(name)) continue;
    const text = readFileSync(full, "utf8");
    scanned.push(name);
    for (const h of scanForSecrets(text, extraPatterns)) {
      hits.push({ artifact: name, ...h });
    }
  }
  if (hits.length > 0) {
    throw new VaultEvidenceError(
      "SECRET_SCAN_HIT",
      `secret-scan re-run hit ${hits.length} pattern(s) in ${[...new Set(hits.map((h) => h.artifact))].join(", ")} — an unscrubbed credential must NEVER reach the immutable vault; refusing the write (deny-dominates)`,
      { hits },
    );
  }

  return { ok: true, marker, scanned };
}

// --- Bundle consistency + record ----------------------------------------------

function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

/**
 * Re-derive every manifest `artifacts[]` sha256 against the files on disk.
 * Pure read; returns `{ mismatches, checked }`. Used both before the record
 * (never freeze an inconsistent bundle) and by `rederiveBundle` months later.
 */
export function checkArtifactHashes(manifest, evidenceDir) {
  const mismatches = [];
  const artifacts = Array.isArray(manifest.artifacts) ? manifest.artifacts : [];
  for (const a of artifacts) {
    const p = join(evidenceDir, a.path ?? a.name);
    if (!existsSync(p)) {
      mismatches.push({ artifact: a.name, problem: "missing", expected_sha256: a.sha256 });
      continue;
    }
    const got = sha256File(p);
    if (got !== a.sha256) {
      mismatches.push({ artifact: a.name, problem: "sha256 mismatch", expected_sha256: a.sha256, actual_sha256: got });
    }
  }
  return { mismatches, checked: artifacts.length };
}

/** Deterministic default acceptance criteria for the vault entry (G10/D1). */
export function defaultCriteria(manifest) {
  return (
    `Evidence bundle for scenario '${manifest.scenario_name}' (run ${manifest.run_id}, ` +
    `project ${manifest.project_id}) re-derives: manifest.json conforms to ` +
    `evidence-manifest ${manifest.manifest_version}; every artifacts[] sha256 matches its ` +
    `file on disk; redaction ran before this record (TH-19 before TH-17).`
  );
}

/**
 * Record a campaign evidence bundle into wicked-vault — content-addressed,
 * criteria-frozen, tamper-evident. THE ONLY vault-write seam in the qe
 * pipeline; the redaction ordering gate runs FIRST, unconditionally.
 *
 * @param {object} opts
 * @param {object} opts.vault       resolved wicked-vault module (2.1 twin —
 *                                  resolveVaultModule enforces the capability)
 * @param {string} opts.evidenceDir bundle directory (contains manifest.json)
 * @param {string} [opts.repoRoot]  vault root anchor (default: cwd). The
 *                                  vault store is `.wicked-vault/` at (or
 *                                  above) this path; created when absent.
 * @param {string} [opts.actor]     recording identity (default "qe-runner" —
 *                                  the executor produced the evidence). Must
 *                                  differ from the attest evaluator (G10/D4).
 * @param {string} [opts.criteria]  acceptance criteria override
 * @param {Array}  [opts.extraPatterns] compiled per-target scan patterns
 * @returns {{ entryId, payloadSha256, envelopeHash, vaultRoot, criteria,
 *             redactionProof, artifactsChecked }}
 */
export function recordEvidenceBundle(opts) {
  const { vault, evidenceDir } = opts;
  if (!vault) throw new VaultEvidenceError("VAULT_UNAVAILABLE", "no vault module supplied");

  // 1. ORDERING GATE — redaction before any vault write (TH-19 → TH-17).
  //    Throws on violation; the proof token is required by the writer below.
  const redactionProof = assertRedactionBeforeVault({
    evidenceDir,
    extraPatterns: opts.extraPatterns ?? [],
  });

  return vaultWriteAfterRedaction(opts, redactionProof);
}

// NOT exported: the vault write is lexically unreachable from outside this
// module except through recordEvidenceBundle's ordering gate above.
function vaultWriteAfterRedaction(opts, redactionProof) {
  if (redactionProof?.ok !== true) {
    throw new VaultEvidenceError("REDACTION_ORDERING", "vault write attempted without a redaction proof — ordering violation");
  }
  const { vault, evidenceDir } = opts;
  const repoRoot = opts.repoRoot ?? process.cwd();

  // 2. The manifest is the payload — parse + validate against the VAULT's
  //    own manifest-2.1 twin (the evidence authority must accept what it
  //    freezes; a schema-fail bundle is never vaulted).
  const manifestPath = join(evidenceDir, "manifest.json");
  if (!existsSync(manifestPath)) {
    throw new VaultEvidenceError("MANIFEST_INVALID", `manifest.json not found in ${evidenceDir} — only manifest-bearing bundles are vaultable`);
  }
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch (e) {
    throw new VaultEvidenceError("MANIFEST_INVALID", `manifest.json unparseable: ${e.message}`);
  }
  const validation = vault.validateManifest(manifest);
  if (!validation.ok) {
    const detail = (validation.violations ?? []).map((v) => `${v.field}: ${v.message}`).join("; ");
    throw new VaultEvidenceError("MANIFEST_INVALID", `bundle fails the vault's manifest-2.1 contract (${detail}) — refusing to freeze a nonconforming bundle`, { violations: validation.violations });
  }

  // 3. Never freeze an inconsistent bundle: every artifacts[] sha256 must
  //    re-derive from disk RIGHT NOW, or the frozen manifest would attest
  //    to bytes that were never there.
  const { mismatches, checked } = checkArtifactHashes(manifest, evidenceDir);
  if (mismatches.length > 0) {
    throw new VaultEvidenceError("BUNDLE_INCONSISTENT", `bundle inconsistent at record time: ${mismatches.length} artifact(s) diverge from manifest.artifacts[]`, { mismatches });
  }

  // 4. The write. Content-addressed payload = manifest.json bytes; criteria
  //    frozen to the evidence (G10/D1); explicit worker identity so the
  //    later attestation's independence check has something real to test.
  const vaultRoot = vault.findRoot(repoRoot, { create: true });
  const res = vault.record(vaultRoot, {
    artifact: manifestPath,
    criteria: opts.criteria ?? defaultCriteria(manifest),
    scope: `qe-campaign/${manifest.project_id}`,
    phase: "campaign",
    claim: `run:${manifest.run_id}`,
    kind: "evidence-bundle",
    source: relative(repoRoot, manifestPath) || manifestPath,
    actor: opts.actor ?? "qe-runner",
  });

  return {
    entryId: res.id,
    payloadSha256: res.payload_sha256,
    envelopeHash: res.envelope_hash,
    vaultRoot,
    criteria: opts.criteria ?? defaultCriteria(manifest),
    redactionProof,
    artifactsChecked: checked,
  };
}

// --- Reviewer grade → opinion attestation (G10) --------------------------------

/** Verdict-of-record → vault opinion. Deny-shaped verdicts map to reject;
 *  anything not clearly PASS/FAIL is `unclear` (never inflated to pass). */
export function verdictToOpinion(verdict) {
  if (verdict === "PASS") return "pass";
  if (verdict === "FAIL") return "reject";
  return "unclear"; // CONDITIONAL, SYSTEM_ERROR, INCONCLUSIVE, PARTIAL, …
}

/**
 * Append the reviewer's grade as an opinion attestation on the vaulted
 * bundle. The vault enforces independence (evaluator ≠ recording actor,
 * deliberately asserted identity) and refuses a tampered artifact —
 * fail-closed, append-only, hash-bound to the exact payload graded.
 *
 * The attestation is itself a vault write, so the same law applies: the
 * rationale text is secret-scanned before it is frozen (a reviewer pasting
 * a captured header into a verdict summary must not make it permanent).
 */
export function attestGrade({ vault, vaultRoot, entryId, verdict, evaluator, rationale, model, extraPatterns = [] }) {
  const hits = scanForSecrets(rationale ?? "", extraPatterns);
  if (hits.length > 0) {
    throw new VaultEvidenceError(
      "SECRET_SCAN_HIT",
      `attestation rationale hit ${hits.length} secret pattern(s) — refusing the vault write (immutability makes leaks permanent)`,
      { hits: hits.map((h) => ({ artifact: "(rationale)", ...h })) },
    );
  }
  const res = vault.attest(vaultRoot, entryId, {
    opinion: verdictToOpinion(verdict),
    evaluator,
    rationale: rationale ?? "",
    ...(model ? { model } : {}),
  });
  return { attestationId: res.attestation_id, attestationHash: res.attestation_hash, opinion: res.opinion };
}

/**
 * The gate-side composition (TH-17 glue for gate.mjs): freeze the bundle
 * (or link an already-frozen entry, re-verified fail-closed), then append
 * the FINAL verdict as the reviewer's opinion attestation. Returns what the
 * verdicts row needs: `vault_payload_sha` + the entry/attestation ids.
 * Throws VaultEvidenceError on any refusal — the caller must treat that as
 * SYSTEM_ERROR and record nothing.
 */
export function applyVaultIntegrity({ vault, evidenceDir, repoRoot, vaultEntry = null, verdict, verdictSummary, actor, evaluator, extraPatterns = [] }) {
  let entryId, payloadSha256, vaultRoot;

  if (vaultEntry) {
    // Link an entry recorded earlier in the pipeline — but never trust it
    // blind: re-derive its hashes NOW (G2/G3); a tampered or missing entry
    // refuses the whole gate write.
    vaultRoot = vault.findRoot(repoRoot ?? process.cwd());
    if (!vaultRoot) {
      throw new VaultEvidenceError("VAULT_UNAVAILABLE", `--vault-entry given but no .wicked-vault found at or above ${repoRoot ?? process.cwd()}`);
    }
    const v = vault.verify(vaultRoot, vaultEntry);
    if (!v.rederived || !v.hash_ok) {
      throw new VaultEvidenceError("ENTRY_TAMPERED", `vault entry ${vaultEntry} failed re-derivation (${v.detail}) — refusing to grade over untrustworthy evidence`, { verify: v });
    }
    const entry = (vault.listEntries(vaultRoot) ?? []).find((e) => e.id === vaultEntry);
    if (!entry) throw new VaultEvidenceError("ENTRY_NOT_FOUND", `vault entry ${vaultEntry} not found`);
    entryId = vaultEntry;
    payloadSha256 = entry.payload_sha256;
  } else {
    const r = recordEvidenceBundle({ vault, evidenceDir, repoRoot, actor, extraPatterns });
    entryId = r.entryId;
    payloadSha256 = r.payloadSha256;
    vaultRoot = r.vaultRoot;
  }

  const att = attestGrade({ vault, vaultRoot, entryId, verdict, evaluator, rationale: verdictSummary, extraPatterns });
  return { entryId, payloadSha256, vaultRoot, attestationId: att.attestationId, opinion: att.opinion };
}

// --- Months-later re-derivation -------------------------------------------------

/**
 * Re-derive a vaulted campaign bundle: vault `verify` (payload + criteria +
 * envelope hashes recomputed — G2/G3, never a cached status) AND every
 * artifact re-hashed on disk against the manifest the vault froze. The
 * on-disk manifest.json must byte-match the vaulted payload (a drifted
 * manifest is a divergence, not a refresh).
 *
 * @returns {{ ok, verify, mismatches, artifactsChecked, latestAttestation }}
 */
export function rederiveBundle({ vault, vaultRoot, entryId, evidenceDir }) {
  const v = vault.verify(vaultRoot, entryId);
  if (!v.rederived || !v.hash_ok) {
    return { ok: false, verify: v, mismatches: [], artifactsChecked: 0, latestAttestation: v.latest_attestation ?? null };
  }

  // The frozen manifest — read back from the vault's content-addressed
  // payload store via inspect (never from the evidence dir).
  const frozen = vault.inspect(vaultRoot, entryId);
  const manifest = frozen?.evidence?.json;
  if (!manifest || typeof manifest !== "object") {
    return {
      ok: false, verify: v,
      mismatches: [{ artifact: "manifest.json", problem: "vaulted payload is not a parseable manifest" }],
      artifactsChecked: 0, latestAttestation: v.latest_attestation ?? null,
    };
  }

  const mismatches = [];

  // On-disk manifest must equal the frozen one, byte for byte (compare the
  // content address: the entry's payload_sha256 IS the manifest's sha256).
  const entry = (vault.listEntries(vaultRoot) ?? []).find((e) => e.id === entryId);
  const diskManifestPath = join(evidenceDir, "manifest.json");
  if (!existsSync(diskManifestPath)) {
    mismatches.push({ artifact: "manifest.json", problem: "missing on disk" });
  } else if (entry) {
    const diskSha = sha256File(diskManifestPath);
    if (diskSha !== entry.payload_sha256) {
      mismatches.push({ artifact: "manifest.json", problem: "on-disk manifest drifted from the vaulted payload", expected_sha256: entry.payload_sha256, actual_sha256: diskSha });
    }
  }

  const arts = checkArtifactHashes(manifest, evidenceDir);
  mismatches.push(...arts.mismatches);

  return {
    ok: mismatches.length === 0,
    verify: v,
    mismatches,
    artifactsChecked: arts.checked,
    latestAttestation: v.latest_attestation ?? null,
  };
}

// --- CLI -------------------------------------------------------------------------

const HELP = `\
qe vault-evidence — vault-backed campaign evidence integrity (TH-17)

Subcommands:
  record    --evidence-dir <dir> [--repo-root <dir>] [--actor <id>]
            [--criteria <text>] [--extra-pattern <regex>]... [--json]
            Freeze a redacted evidence bundle into wicked-vault
            (content-addressed; REFUSES unredacted bundles — TH-19 ordering).
  attest    --entry <id> --verdict <PASS|FAIL|CONDITIONAL|SYSTEM_ERROR|INCONCLUSIVE>
            [--evaluator <id>] [--rationale <text>] [--repo-root <dir>] [--json]
            Append the reviewer grade as an opinion attestation.
  rederive  --entry <id> [--evidence-dir <dir>] [--repo-root <dir>] [--json]
            Re-derive the bundle months later: vault hashes + every artifact
            re-hashed on disk. Exit 1 on ANY divergence.

wicked-vault resolution: WICKED_QE_VAULT_PKG (local checkout — required until
the next wicked-vault release ships the manifest-2.1 twin) → global install →
the repo's node_modules. A pre-2.1 vault is refused fail-closed.

Exit codes: 0 ok · 1 rederive divergence · 3 refusal / usage / system error.
`;

function isMain() {
  try { return import.meta.url === pathToFileURL(process.argv[1]).href; } catch { return false; }
}

function fail(obj, code = 3) {
  process.stderr.write(JSON.stringify(obj) + "\n");
  process.exit(code);
}

if (isMain()) {
  const sub = process.argv[2];
  if (!sub || sub === "--help" || sub === "-h") {
    process.stdout.write(HELP);
    process.exit(sub ? 0 : 3);
  }

  let values;
  try {
    ({ values } = parseArgs({
      args: process.argv.slice(3),
      options: {
        "evidence-dir": { type: "string" },
        "repo-root": { type: "string" },
        "actor": { type: "string" },
        "criteria": { type: "string" },
        "extra-pattern": { type: "string", multiple: true },
        "entry": { type: "string" },
        "verdict": { type: "string" },
        "evaluator": { type: "string" },
        "rationale": { type: "string" },
        "model": { type: "string" },
        "json": { type: "boolean" },
      },
      strict: true,
    }));
  } catch (e) {
    fail({ error: "USAGE", detail: e.message });
  }

  const repoRoot = values["repo-root"]
    ? (isAbsolute(values["repo-root"]) ? values["repo-root"] : join(process.cwd(), values["repo-root"]))
    : process.cwd();

  const resolved = await resolveVaultModule({ cwd: repoRoot });
  if (!resolved.ok) fail({ error: "VAULT_UNAVAILABLE", detail: resolved.reason });
  const vault = resolved.vault;

  const out = (obj) => process.stdout.write(JSON.stringify(obj, null, values.json ? 0 : 2) + "\n");

  try {
    if (sub === "record") {
      if (!values["evidence-dir"]) fail({ error: "USAGE", detail: "record requires --evidence-dir" });
      const evidenceDir = isAbsolute(values["evidence-dir"]) ? values["evidence-dir"] : join(process.cwd(), values["evidence-dir"]);
      const r = recordEvidenceBundle({
        vault,
        evidenceDir,
        repoRoot,
        actor: values.actor,
        criteria: values.criteria,
        extraPatterns: compileExtraPatterns(values["extra-pattern"] ?? []),
      });
      out({ entry_id: r.entryId, payload_sha256: r.payloadSha256, envelope_hash: r.envelopeHash, vault_root: r.vaultRoot, redaction_marker: r.redactionProof.marker, artifacts_checked: r.artifactsChecked, vault_source: resolved.source });
      process.exit(0);
    } else if (sub === "attest") {
      if (!values.entry || !values.verdict) fail({ error: "USAGE", detail: "attest requires --entry and --verdict" });
      const vaultRoot = vault.findRoot(repoRoot);
      if (!vaultRoot) fail({ error: "VAULT_UNAVAILABLE", detail: `no .wicked-vault at or above ${repoRoot}` });
      const r = attestGrade({
        vault, vaultRoot,
        entryId: values.entry,
        verdict: values.verdict,
        evaluator: values.evaluator ?? "wicked-garden-qe-gate",
        rationale: values.rationale,
        model: values.model,
      });
      out({ attestation_id: r.attestationId, attestation_hash: r.attestationHash, opinion: r.opinion });
      process.exit(0);
    } else if (sub === "rederive") {
      if (!values.entry) fail({ error: "USAGE", detail: "rederive requires --entry" });
      const vaultRoot = vault.findRoot(repoRoot);
      if (!vaultRoot) fail({ error: "VAULT_UNAVAILABLE", detail: `no .wicked-vault at or above ${repoRoot}` });
      let evidenceDir = values["evidence-dir"];
      if (!evidenceDir) {
        // derive from the frozen manifest: <ledger-root>/evidence/<run_id>
        const frozen = vault.inspect(vaultRoot, values.entry);
        const runId = frozen?.evidence?.json?.run_id;
        if (!runId) fail({ error: "ENTRY_NOT_FOUND", detail: "cannot derive --evidence-dir from the vaulted payload; pass it explicitly" });
        const envRoot = process.env.WICKED_QE_LEDGER_DIR?.trim();
        const ledgerRoot = envRoot ? (isAbsolute(envRoot) ? envRoot : join(repoRoot, envRoot)) : join(repoRoot, ".wicked-qe");
        evidenceDir = join(ledgerRoot, "evidence", runId);
      } else if (!isAbsolute(evidenceDir)) {
        evidenceDir = join(process.cwd(), evidenceDir);
      }
      const r = rederiveBundle({ vault, vaultRoot, entryId: values.entry, evidenceDir });
      out({ ok: r.ok, verify: { hash_ok: r.verify.hash_ok, status: r.verify.status, detail: r.verify.detail }, mismatches: r.mismatches, artifacts_checked: r.artifactsChecked, latest_attestation: r.latestAttestation });
      process.exit(r.ok ? 0 : 1);
    } else {
      fail({ error: "USAGE", detail: `unknown subcommand '${sub}'` });
    }
  } catch (e) {
    if (e instanceof VaultEvidenceError) fail({ error: e.code, detail: e.message, ...(e.detail?.hits ? { hits: e.detail.hits } : {}), ...(e.detail?.mismatches ? { mismatches: e.detail.mismatches } : {}) });
    fail({ error: "SYSTEM_ERROR", detail: e.message });
  }
}
