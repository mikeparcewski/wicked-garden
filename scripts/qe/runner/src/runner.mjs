/**
 * src/runner.mjs — the model-free executor (TH-4).
 *
 * Doctrine (from wicked-interactive's demo.js, ADR 0006): the agent AUTHORS
 * a deterministic spec; this runner EXECUTES it. The runner makes zero LLM
 * calls, evaluates zero free-form code, and decides nothing the spec did not
 * spell out. A drifted selector FAILS the step — re-authoring the spec is the
 * agent's job (TH-13), never the runner's.
 *
 * Non-configurable defaults (TH-4 item 3):
 *   - headless Chromium, viewport pinned 1440x700
 *   - console-message ledger always captured
 *   - waiting is wait-on-condition with timeout CAPS — no fixed sleeps exist
 *     in this file or in the spec vocabulary (lint-enforced)
 *   - evidence is redacted + secret-scanned before any write (TH-19)
 *
 * Flags (evidence baseline stays screenshots; heavier capture is opt-in):
 *   video: record video into the evidence dir
 *   trace: record a Playwright trace into the evidence dir
 */

import { join } from "node:path";
import { mkdirSync } from "node:fs";
import { wireCapture } from "./wire-capture.mjs";
import { evaluateAssertions, readBack } from "./asserts.mjs";
import { writeEvidence, resolveLedgerRoot } from "./evidence.mjs";
import { randomUUID } from "node:crypto";

export const VIEWPORT = Object.freeze({ width: 1440, height: 700 });
const DEFAULT_STEP_TIMEOUT_MS = 15_000;

async function executeStep(page, step, captures, spec) {
  const timeout = step.timeout_ms ?? DEFAULT_STEP_TIMEOUT_MS;
  switch (step.action) {
    case "goto":
      await page.goto(new URL(step.path ?? "/", spec.target.base_url).toString(), {
        waitUntil: step.wait_until ?? "domcontentloaded",
        timeout,
      });
      return {};
    case "waitFor":
      await page.waitForSelector(step.selector, { state: step.state ?? "visible", timeout });
      return {};
    case "waitForText":
      // Wait-on-condition: poll the selector's text for the expected content.
      await page.waitForFunction(
        ({ selector, contains, notContains }) => {
          const el = document.querySelector(selector);
          if (!el) return false;
          const text = el.textContent ?? "";
          if (contains !== null && !text.includes(contains)) return false;
          if (notContains !== null && text.includes(notContains)) return false;
          return true;
        },
        { selector: step.selector, contains: step.contains ?? null, notContains: step.not_contains ?? null },
        { timeout },
      );
      return {};
    case "click":
      await page.click(step.selector, { timeout });
      return {};
    case "fill":
      await page.fill(step.selector, String(step.value ?? ""), { timeout });
      return {};
    case "press":
      if (step.selector) await page.press(step.selector, step.key, { timeout });
      else await page.keyboard.press(step.key);
      return {};
    case "screenshot": {
      // Streamed straight into the evidence dir (pixel data — not scannable;
      // see redact.mjs limitation note).
      const file = join(step._evidenceDir, `${step.name}.png`);
      await page.screenshot({ path: file });
      return { screenshot: `${step.name}.png` };
    }
    case "readBack": {
      const record = await readBack(spec.target.base_url, step);
      captures.readbacks[step.id] = record;
      return { status: record.status };
    }
    case "expectWire": {
      // Wait until a declared wire capture has >= min_count entries.
      const min = step.min_count ?? 1;
      await waitOnCondition(
        () => (captures.wire[step.capture]?.responses.length ?? 0) >= min,
        timeout,
        `expectWire ${step.capture} >= ${min}`,
      );
      return { count: captures.wire[step.capture].responses.length };
    }
    case "expectNewWire": {
      // Wait until the capture grows past its count from BEFORE the
      // triggering step (baseline_steps_back, default 1 = the step right
      // before this one). Snapshotting at the previous step's start closes
      // the race where the response lands before this step begins — the
      // condition-based replacement for the campaign's waitForTimeout(1500).
      const back = step.baseline_steps_back ?? 1;
      const snapIndex = Math.max(0, step._stepIndex - back);
      const before = step._wireCounts[snapIndex]?.[step.capture] ?? 0;
      await waitOnCondition(
        () => (captures.wire[step.capture]?.responses.length ?? 0) > before,
        timeout,
        `expectNewWire ${step.capture} > ${before} (baseline: start of step ${snapIndex})`,
      );
      return { before, after: captures.wire[step.capture].responses.length };
    }
    default:
      throw new Error(`unreachable: lint admits no action "${step.action}"`);
  }
}

/** Poll a condition every 100ms up to a timeout CAP. Never a fixed floor. */
async function waitOnCondition(cond, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (cond()) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`timed out after ${timeoutMs}ms waiting on: ${label}`);
}

/**
 * Execute a linted spec. Always writes an evidence bundle — even a crashed
 * run leaves redacted evidence behind (status: errored).
 *
 * @returns {{ claim, runId, evidenceDir, manifestPath, exitCode }}
 */
export async function runSpec(spec, opts = {}) {
  const repoRoot = opts.repoRoot ?? process.cwd();
  const startedAt = new Date().toISOString();
  const runId = randomUUID();
  const evidenceDir = join(resolveLedgerRoot(repoRoot), "evidence", runId);
  mkdirSync(evidenceDir, { recursive: true });

  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    ...(opts.video ? { recordVideo: { dir: evidenceDir, size: VIEWPORT } } : {}),
  });
  if (opts.trace) await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();
  const captures = wireCapture(page, spec);

  const stepLog = [];
  const wireCounts = []; // per-step-start snapshot of each wire capture's count
  let runError;
  let assertionResults = [];
  try {
    for (const [i, step] of spec.steps.entries()) {
      wireCounts[i] = Object.fromEntries(
        Object.entries(captures.wire).map(([id, c]) => [id, c.responses.length]),
      );
      const entry = { index: i, action: step.action, started_at: new Date().toISOString() };
      try {
        const detail = await executeStep(
          page,
          { ...step, _evidenceDir: evidenceDir, _stepIndex: i, _wireCounts: wireCounts },
          captures,
          spec,
        );
        entry.ok = true;
        entry.detail = detail;
      } catch (e) {
        entry.ok = false;
        entry.error = String(e?.message ?? e).slice(0, 500);
        stepLog.push({ ...entry, finished_at: new Date().toISOString() });
        throw new Error(`step ${i} (${step.action}) failed: ${entry.error}`);
      }
      entry.finished_at = new Date().toISOString();
      stepLog.push(entry);
    }
    assertionResults = await evaluateAssertions(spec, captures, page);
  } catch (e) {
    runError = String(e?.message ?? e).slice(0, 1000);
  } finally {
    try {
      if (opts.trace) await context.tracing.stop({ path: join(evidenceDir, "trace.zip") });
    } catch { /* trace stop best-effort */ }
    await browser.close();
  }

  const failed = assertionResults.filter((r) => !r.ok);
  let claim, claimReason;
  if (runError !== undefined) {
    claim = "INCONCLUSIVE";
    claimReason = `run errored before assertions completed: ${runError.slice(0, 200)}`;
  } else if (failed.length > 0) {
    claim = "FAIL";
    claimReason = `${failed.length}/${assertionResults.length} assertions failed: ${failed.map((f) => f.id).join(", ")}`;
  } else {
    claim = "PASS";
    claimReason = `${assertionResults.length}/${assertionResults.length} assertions passed`;
  }

  // Redaction + preflight + ledger write (TH-19 ordering lives inside).
  const evidence = writeEvidence({
    spec,
    captures,
    assertionResults,
    stepLog,
    repoRoot,
    claim,
    claimReason,
    runId,
    startedAt,
    finishedAt: new Date().toISOString(),
    runError,
    specPath: opts.specPath,
  });

  const exitCode =
    evidence.claim === "PASS" ? 0 : evidence.claim === "FAIL" ? 1 : 2;
  return { ...evidence, exitCode };
}
