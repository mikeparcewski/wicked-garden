#!/usr/bin/env node
/**
 * estate_mcp.mjs — start the wicked-estate MCP server over stdio for a host that loads garden as
 * a plugin (Codex: `.codex-plugin/mcp.json` runs `wicked-garden run scripts/estate_mcp.mjs`).
 *
 * The binary is found the way garden's own estate client finds it
 * (`scripts/_estate_client.py` `resolve_mcp_bin`), so the plugin and the skills talk to the same
 * binary and no install path is written into the manifest:
 *
 *   1. WICKED_ESTATE_MCP_BIN, when it names an existing file;
 *   2. `wicked-estate-mcp` on PATH — an executable file, as `shutil.which` requires (PATHEXT on
 *      Windows);
 *   3. ~/.local/bin/wicked-estate-mcp (or `.exe`).
 *
 * stdin/stdout/stderr are inherited (the MCP stream passes straight through), the caller's cwd is
 * kept (the binary resolves its store from it), and arguments after the script name are passed
 * on. The read-only and governed-unit rules of `_estate_client.py` apply here too: `--readonly`
 * is added when WICKED_ESTATE_READONLY / WICKED_GOVERNED is truthy or a run marker
 * (WICKED_RUN_ID, WICKED_GATE_SCOPE, WICKED_WRITE_ROOTS) is set — estate only honours the
 * literal flag — and a governed unit with no pinned store (--db, WICKED_ESTATE_DB, WICKED_HOME,
 * WICKED_MEMORY_DB) is refused rather than pointed at the operator's default stores. The exit code is the server's; SIGINT/SIGTERM/SIGHUP are forwarded. When no binary is found
 * it writes one JSON line on stderr — {"ok": false, "reason": …, "tried": […]} — and exits 1, so
 * the host reports a failed MCP server rather than a hung one.
 *
 * Pure helpers are exported for tests (tests/test_codex_plugin_manifest.py).
 */
import { accessSync, constants as fsConstants, realpathSync, statSync } from "node:fs";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const MCP_BIN_NAME = "wicked-estate-mcp";
export const OVERRIDE_ENV = "WICKED_ESTATE_MCP_BIN";

function isFile(p) {
  try {
    return statSync(p).isFile();
  } catch {
    return false;
  }
}

/** shutil.which's test: a regular file the user may execute (Windows has no execute bit). */
function isExecutableFile(p, platform = process.platform) {
  if (!isFile(p)) return false;
  if (platform === "win32") return true;
  try {
    accessSync(p, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the estate MCP binary. Returns { bin, tried } — `bin` is null when nothing qualifies.
 * `env`, `platform`, `home` and `fileExists` are seams for tests.
 */
export function resolveEstateMcpBin({
  env = process.env,
  platform = process.platform,
  home = homedir(),
  fileExists = isFile,
  isExecutable = (p) => isExecutableFile(p, platform),
} = {}) {
  const p = platform === "win32" ? path.win32 : path.posix;
  const tried = [];
  const override = env[OVERRIDE_ENV];
  if (override) {
    tried.push(`${OVERRIDE_ENV}=${override}`);
    if (fileExists(override)) return { bin: override, tried };
  }
  const exts = platform === "win32"
    ? ["", ...(env.PATHEXT || ".COM;.EXE;.BAT;.CMD").split(";").filter(Boolean).map((e) => e.toLowerCase())]
    : [""];
  const pathVar = env.PATH ?? env.Path ?? "";
  for (const dir of pathVar.split(platform === "win32" ? ";" : ":")) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = p.join(dir, MCP_BIN_NAME + ext);
      // PATH entries must be executable (as shutil.which requires); the override and
      // ~/.local/bin only need to be files, exactly as _estate_client.py checks them.
      if (isExecutable(candidate)) return { bin: candidate, tried: [...tried, "PATH"] };
    }
  }
  tried.push("PATH");
  const local = p.join(home, ".local", "bin");
  for (const name of [MCP_BIN_NAME, `${MCP_BIN_NAME}.exe`]) {
    const candidate = p.join(local, name);
    tried.push(candidate);
    if (fileExists(candidate)) return { bin: candidate, tried };
  }
  return { bin: null, tried };
}

const GOVERNED_MARKERS = ["WICKED_RUN_ID", "WICKED_GATE_SCOPE", "WICKED_WRITE_ROOTS"];
const STORE_PIN_ENV = ["WICKED_ESTATE_DB", "WICKED_HOME", "WICKED_MEMORY_DB"];
const truthy = (v) => !["", "0", "false", "no"].includes(String(v ?? "").trim().toLowerCase());

/**
 * The argv to hand estate, or the reason to refuse — `_estate_client.read_only()` /
 * `governed_refusal()` applied to the launcher's own argv and environment.
 */
export function estateArgv(argv, env = process.env) {
  const marker = truthy(env.WICKED_GOVERNED) ? "WICKED_GOVERNED" : GOVERNED_MARKERS.find((k) => String(env[k] ?? "").trim());
  const pinned = argv.includes("--db") || argv.some((a) => a.startsWith("--db=")) || STORE_PIN_ENV.some((k) => String(env[k] ?? "").trim());
  if (marker && !pinned) {
    return { refusal: `governed unit (${marker} is set) but no estate store is pinned: set ${STORE_PIN_ENV.join(" / ")} or pass --db; refusing to start wicked-estate-mcp against the operator's default stores` };
  }
  const readOnly = !!marker || truthy(env.WICKED_ESTATE_READONLY);
  return { argv: readOnly && !argv.includes("--readonly") ? ["--readonly", ...argv] : argv };
}

function main(argv) {
  const plan = estateArgv(argv);
  if (plan.refusal) {
    process.stderr.write(JSON.stringify({ ok: false, reason: plan.refusal, tried: [] }) + "\n");
    return process.exit(1);
  }
  argv = plan.argv;
  const { bin, tried } = resolveEstateMcpBin();
  if (!bin) {
    process.stderr.write(JSON.stringify({
      ok: false,
      reason: `${MCP_BIN_NAME} not found — install wicked-estate (npx wicked-installer install wicked-estate) or set ${OVERRIDE_ENV}`,
      tried,
    }) + "\n");
    return process.exit(1);
  }
  const child = spawn(bin, argv, { stdio: "inherit", shell: false });
  for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(sig, () => {
      try {
        child.kill(sig);
      } catch {
        /* already gone */
      }
    });
  }
  child.on("error", (err) => {
    process.stderr.write(JSON.stringify({ ok: false, reason: `could not start ${bin}: ${err.message}`, tried }) + "\n");
    process.exit(1);
  });
  child.on("exit", (code, signal) => {
    process.exit(code ?? (signal ? 128 + (signalNumber(signal) || 1) : 1));
  });
}

function signalNumber(name) {
  return { SIGHUP: 1, SIGINT: 2, SIGKILL: 9, SIGTERM: 15 }[name];
}

function invokedDirectly() {
  try {
    return Boolean(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}
if (invokedDirectly()) main(process.argv.slice(2));
