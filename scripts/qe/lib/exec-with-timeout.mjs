/**
 * lib/exec-with-timeout.mjs — Node-enforced step timeout.
 *
 * Replaces the previous "shell out to `timeout ${N}`" pattern that assumed
 * GNU coreutils. Stock macOS ships BSD userland with no `/usr/bin/timeout`;
 * Windows Git Bash depends on the MSYS2 package set. On either host the
 * scenario's `timeout` frontmatter field used to silently fail to enforce.
 *
 * This wrapper spawns the command, arms an AbortController-driven kill
 * timer, and returns a structured result (stdout, stderr, exitCode, timed
 * out yes/no, wall-clock ms). Everything runs through Node, so portability
 * is the same as Node itself — macOS, Linux, Windows all equivalent.
 *
 * Skills/agents that used to write:
 *
 *     timeout ${TIMEOUT:-120} bash -c '{step_command}'
 *
 * should now invoke the caller via Node (directly or through the dev
 * `scripts/_python.sh` shim if Node isn't available), or emit a shell
 * fallback chain `timeout || gtimeout || bare` with a loud log noting
 * enforcement is disabled.
 */

import { spawn } from "node:child_process";

/**
 * Default timeout for scenario steps (2 minutes) — matches SCENARIO-FORMAT.md.
 */
export const DEFAULT_TIMEOUT_MS = 120_000;

/**
 * Execute a single command with a hard Node-side kill timer.
 *
 * @param {object} opts
 * @param {string|string[]} opts.command  Shell string (run via shell:true)
 *   OR argv array (run directly, safer — no shell expansion).
 * @param {string[]} [opts.args]          argv when `command` is an executable
 *   path and `args` is the parameter list. Mutually exclusive with using
 *   `command` as a shell string.
 * @param {number} [opts.timeoutMs]       Max wall-clock ms before kill.
 *   Defaults to DEFAULT_TIMEOUT_MS. Pass 0 or Infinity to disable.
 * @param {string} [opts.cwd]             Working directory. Defaults to
 *   process.cwd().
 * @param {object} [opts.env]             Environment overrides.
 * @param {string} [opts.stdin]           Optional stdin text to feed the child.
 * @param {string} [opts.killSignal]      Signal to send on timeout.
 *   Defaults to "SIGKILL" (SIGTERM is often ignored by stuck scripts).
 * @returns {Promise<{
 *   stdout: string,
 *   stderr: string,
 *   exitCode: number|null,
 *   signal: string|null,
 *   timedOut: boolean,
 *   durationMs: number,
 *   command: string,
 * }>}
 */
export function execWithTimeout(opts) {
  const {
    command,
    args,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    cwd,
    env,
    stdin,
    killSignal = "SIGKILL",
  } = opts;

  if (!command) throw new Error("execWithTimeout: `command` is required");

  // Three supported call shapes:
  //   1. { command: "echo hello" }                          — shell-string
  //   2. { command: "node", args: ["-e", "..."] }           — argv (opts.args)
  //   3. { command: ["node", "-e", "..."] }                 — argv (array)
  // When `command` is an array we split it into exe + args and run without
  // a shell (same safety posture as (2)). The previous implementation
  // advertised shape #3 in the JSDoc but spawn()'d the whole array as the
  // executable path, which failed.
  const useShell = typeof command === "string" && !Array.isArray(args);
  const spawnCmd = Array.isArray(command) ? command[0] : command;
  const spawnArgs = Array.isArray(command)
    ? command.slice(1)
    : (useShell ? [] : (args || []));

  return new Promise((resolve, reject) => {
    const started = Date.now();
    let stdout = "";
    let stderr = "";
    let killed = false;
    let timer = null;

    let child;
    try {
      child = spawn(spawnCmd, spawnArgs, {
        cwd,
        env: env ? { ...process.env, ...env } : process.env,
        shell: useShell,
        stdio: stdin != null ? ["pipe", "pipe", "pipe"] : ["ignore", "pipe", "pipe"],
      });
    } catch (err) {
      reject(err);
      return;
    }

    if (stdin != null && child.stdin) {
      child.stdin.end(stdin);
    }

    if (timeoutMs && timeoutMs !== Infinity && timeoutMs > 0) {
      timer = setTimeout(() => {
        killed = true;
        try { child.kill(killSignal); } catch { /* already exited */ }
      }, timeoutMs);
    }

    child.stdout?.on("data", (chunk) => { stdout += chunk.toString("utf8"); });
    child.stderr?.on("data", (chunk) => { stderr += chunk.toString("utf8"); });

    child.on("error", (err) => {
      if (timer) clearTimeout(timer);
      // ENOENT etc. — the command wasn't spawnable at all. Report as a
      // structured failure so callers see the same shape regardless.
      resolve({
        stdout,
        stderr: stderr + (stderr && !stderr.endsWith("\n") ? "\n" : "") + String(err?.message ?? err),
        exitCode: null,
        signal: null,
        timedOut: false,
        durationMs: Date.now() - started,
        command: renderCommand(spawnCmd, spawnArgs),
      });
    });

    child.on("close", (exitCode, signal) => {
      if (timer) clearTimeout(timer);
      resolve({
        stdout,
        stderr,
        exitCode: exitCode ?? null,
        signal: signal ?? null,
        timedOut: killed,
        durationMs: Date.now() - started,
        command: renderCommand(spawnCmd, spawnArgs),
      });
    });
  });
}

function renderCommand(cmd, args) {
  if (!args || args.length === 0) return String(cmd);
  return [cmd, ...args].map(a => /\s/.test(String(a)) ? `"${a}"` : String(a)).join(" ");
}

/**
 * Convenience: execute and return a shaped result that looks like the
 * existing evidence step record. Skills/agents that used to write:
 *
 *     {
 *       "stdout": "...",
 *       "stderr": "...",
 *       "exit_code": 0
 *     }
 *
 * can build that shape directly from this wrapper's output.
 *
 * @returns {Promise<{stdout: string, stderr: string, exit_code: number|null, timed_out: boolean, duration_ms: number}>}
 */
export async function runStep(opts) {
  const r = await execWithTimeout(opts);
  return {
    stdout: r.stdout,
    stderr: r.stderr,
    exit_code: r.exitCode,
    timed_out: r.timedOut,
    duration_ms: r.durationMs,
    command: r.command,
  };
}
