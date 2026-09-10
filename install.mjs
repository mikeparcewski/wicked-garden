#!/usr/bin/env node
/**
 * wicked-garden installer
 * Copies plugin files to <config-dir>/plugins/wicked-garden/ and optionally syncs Python deps.
 *
 * The copy is UNREGISTERED: Claude Code loads plugins through its marketplace
 * registry, and registration is wicked-installer's job — run
 * `npx wicked-installer install wicked-garden` afterwards (wicked-installer#18).
 *
 * Usage:
 *   npx wicked-garden install [options]   Install or update the plugin copy
 *   npx wicked-garden update  [options]   Same as install
 *   npx wicked-garden status  [options]   Show the install state per config dir
 *   npx wicked-garden pack <verb>         Third-party pack tooling (check/register/list/…)
 *   npx wicked-garden --version           Print version
 *   npx wicked-garden --help              Print usage
 *
 * Options:
 *   --claude-home <dir>   Config dir to target (repeatable; default: $CLAUDE_CONFIG_DIR or ~/.claude)
 *                         — install/update/status
 *   --dry-run             Print what would be copied/synced, write nothing, never run uv
 *                         — install/update only (status is read-only and rejects it)
 *
 * Unknown commands, unknown options and stray arguments exit 2 with usage on stderr.
 */
import { cpSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import { execSync, spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(__dirname, "package.json"), "utf8"));

const PLUGIN_DIRS  = [".claude-plugin", "hooks", "scripts", "skills", "schemas"];
const PLUGIN_FILES = ["ETHOS.md", "CHANGELOG.md", "README.md", "WICKED_GARDEN_BUS_EVENTS.md", "pyproject.toml"];
const SKIP         = [/__pycache__/, /\.pyc$/, /\.pyo$/, /\.DS_Store$/];
// Dev-only subdirs within scripts/ — not needed at runtime
const SCRIPTS_DEV  = ["ci", "wg"];

const REGISTER_NOTE =
  "copied (unregistered). Claude Code loads plugins through its marketplace registry — " +
  "run `npx wicked-installer install wicked-garden` to register it in the active config dir.";

function skip(src) {
  if (SKIP.some(p => p.test(src))) return true;
  // Strip dev-only scripts/ subdirs — they exist in the npm package but serve no runtime purpose
  const m = src.match(/[/\\]scripts[/\\]([^/\\]+)/);
  if (m && SCRIPTS_DEV.includes(m[1])) return true;
  return false;
}

function findBin(name) {
  try {
    const out = execSync(
      process.platform === "win32" ? `where ${name}` : `command -v ${name}`,
      { stdio: ["ignore", "pipe", "ignore"], timeout: 2000, encoding: "utf8" }
    ).trim().split("\n")[0];
    return out || undefined;
  } catch {
    return undefined;
  }
}

// ---------------------------------------------------------------------------
// Argument parsing. Flags are accepted before or after the command
// (`npx wicked-garden --dry-run`, `npx wicked-garden install --dry-run`);
// `pack` verbs own their flags, so everything after `pack` passes through verbatim.
// ---------------------------------------------------------------------------

class UsageError extends Error {}

function parseArgs(argv) {
  const opts = { cmd: undefined, rest: [], claudeHomes: [], dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (opts.cmd === "pack") { opts.rest.push(arg); continue; }
    if (arg === "--dry-run") {
      opts.dryRun = true;
    } else if (arg === "--claude-home") {
      const value = argv[i + 1];
      if (value === undefined || value === "") throw new UsageError("--claude-home requires a directory");
      opts.claudeHomes.push(value);
      i += 1;
    } else if (arg.startsWith("--claude-home=")) {
      const value = arg.slice("--claude-home=".length);
      if (!value) throw new UsageError("--claude-home requires a directory");
      opts.claudeHomes.push(value);
    } else if (opts.cmd === undefined) {
      opts.cmd = arg; // includes --version / -v / --help / -h, dispatched below
    } else if (arg.startsWith("-")) {
      throw new UsageError(`unknown option: ${arg}`);
    } else {
      throw new UsageError(`unexpected argument: ${arg}`);
    }
  }
  return opts;
}

// ---------------------------------------------------------------------------
// Target resolution — the same rule as wicked-installer (install-claude.ts) so
// both tools land in the same config dirs:
//   1. --claude-home flags are the full set (trusted; created if absent);
//   2. CLAUDE_CONFIG_DIR is authoritative and exclusive when set — it may list
//      several dirs, split on the platform list separator + ',';
//   3. otherwise ~/.claude.
// ---------------------------------------------------------------------------

function expandHome(value) {
  return value.replace(/^~(?=$|[/\\])/, () => homedir());
}

// ';'+',' on Windows so a bare ':' can never shatter a C:\ path; ':'+',' elsewhere.
function splitConfigDirValue(value) {
  return value.split(process.platform === "win32" ? /[;,]/ : /[:,]/).map(p => p.trim()).filter(Boolean);
}

function resolveClaudeHomes(claudeHomes, env = process.env) {
  let dirs = [];
  let origin = "default";
  if (claudeHomes.length > 0) {
    dirs = claudeHomes;
    origin = "--claude-home";
  } else if (env.CLAUDE_CONFIG_DIR && env.CLAUDE_CONFIG_DIR.trim()) {
    dirs = splitConfigDirValue(env.CLAUDE_CONFIG_DIR);
    origin = "CLAUDE_CONFIG_DIR";
  }
  if (dirs.length === 0) {
    dirs = [join(homedir(), ".claude")];
    origin = "default";
  }
  const out = [];
  const seen = new Set();
  for (const raw of dirs) {
    const dir = resolve(expandHome(raw));
    if (seen.has(dir)) continue;
    seen.add(dir);
    out.push({ dir, dest: join(dir, "plugins", "wicked-garden"), origin });
  }
  return out;
}

function planCopies() {
  return {
    dirs:  PLUGIN_DIRS.filter(d => existsSync(join(__dirname, d))),
    files: PLUGIN_FILES.filter(f => existsSync(join(__dirname, f))),
  };
}

async function cmdInstall(homes, { dryRun }) {
  const uv = findBin("uv");
  const { dirs, files } = planCopies();
  const tag = dryRun ? "[dry-run] " : "";

  for (const { dir: home, dest, origin } of homes) {
    const isUpdate = existsSync(dest);
    console.log(`${tag}${isUpdate ? "Updating" : "Installing"} wicked-garden v${pkg.version} ${isUpdate ? "at" : "to"} ${dest}`);
    console.log(`  config dir: ${home} (${origin})`);

    if (dryRun) {
      for (const dir of dirs)   console.log(`  would copy ${dir}/ -> ${join(dest, dir)}`);
      for (const file of files) console.log(`  would copy ${file} -> ${join(dest, file)}`);
      console.log(uv
        ? `  would run: uv sync --quiet (cwd ${dest})`
        : "  uv not found — would skip Python deps (the wicked-garden-core setup action retries)");
      continue;
    }

    mkdirSync(dest, { recursive: true });

    for (const dir of dirs) {
      process.stdout.write(`  ${dir}/... `);
      cpSync(join(__dirname, dir), join(dest, dir), { recursive: true, force: true, filter: (s) => !skip(s) });
      console.log("done");
    }
    for (const file of files) {
      cpSync(join(__dirname, file), join(dest, file), { force: true });
    }

    // Sync Python deps via uv if available (setup will retry if this is skipped)
    if (uv) {
      process.stdout.write("  Python deps (uv sync)... ");
      try {
        execSync(`"${uv}" sync --quiet`, { cwd: dest, stdio: "pipe" });
        console.log("done");
      } catch {
        console.log("skipped — the wicked-garden-core setup action will retry");
      }
    }

    console.log(`  ${REGISTER_NOTE}`);
  }

  const n = homes.length;
  if (dryRun) {
    console.log(`\n[dry-run] Nothing was written. wicked-garden v${pkg.version} would be copied into ${n} config dir${n === 1 ? "" : "s"}.`);
    return;
  }
  console.log(`\nwicked-garden v${pkg.version} ${REGISTER_NOTE}`);
  console.log('Then, in Claude Code, ask for "wicked-garden setup" (the wicked-garden-core skill) to complete configuration.');
}

function cmdStatus(homes) {
  for (const { dir: home, dest, origin } of homes) {
    console.log(`config dir: ${home} (${origin})`);
    if (!existsSync(dest)) {
      console.log("  wicked-garden: not installed");
      const hint = origin === "--claude-home" ? ` --claude-home "${home}"` : "";
      console.log(`  Run: npx wicked-garden@${pkg.version} install${hint}`);
      continue;
    }
    try {
      const installed = JSON.parse(readFileSync(join(dest, ".claude-plugin", "plugin.json"), "utf8"));
      const upToDate  = installed.version === pkg.version;
      console.log("  wicked-garden: installed (copy)");
      console.log(`  path:    ${dest}`);
      console.log(`  version: ${installed.version}${upToDate ? "" : ` (package: ${pkg.version} — run install to update)`}`);
    } catch {
      console.log(`  wicked-garden: installed at ${dest} (plugin.json unreadable)`);
    }
    console.log("  registration: owned by wicked-installer — `npx wicked-installer status` reports Claude Code's registry state");
  }
}

// ---------------------------------------------------------------------------
// Pack tooling (extension contract). One implementation rule:
//   * validation + registration = the shipped Python (scripts/pack/check.py,
//     scripts/_pack_registry.py) — invoked here so `npx wicked-garden pack
//     check` works without installing anything else;
//   * acquisition + cross-CLI staging = wicked-installer (`pack install`
//     DELEGATES — garden never grows a second installer code path).
// ---------------------------------------------------------------------------

function findPython() {
  for (const candidate of ["python3", "python"]) {
    const bin = findBin(candidate);
    if (bin) return bin;
  }
  return undefined;
}

function runPython(scriptRel, args) {
  const python = findPython();
  if (!python) {
    console.error("Error: python3 (or python) is required for pack tooling — install Python >= 3.10.");
    return 1;
  }
  const script = join(__dirname, ...scriptRel);
  if (!existsSync(script)) {
    console.error(`Error: bundled script missing: ${script}`);
    return 1;
  }
  const res = spawnSync(python, [script, ...args], { stdio: "inherit" });
  return res.status ?? 1;
}

function delegateToInstaller(args) {
  // WICKED_INSTALLER_BIN → PATH → npx (the loom/vault resolution pattern).
  const override = process.env.WICKED_INSTALLER_BIN;
  let argv;
  if (override) argv = [override, ...args];
  else if (findBin("wicked-installer")) argv = ["wicked-installer", ...args];
  else argv = [findBin("npx") ?? "npx", "-y", "wicked-installer@latest", ...args];
  const res = spawnSync(argv[0], argv.slice(1), {
    stdio: "inherit",
    shell: process.platform === "win32", // npx/.cmd shims need a shell on Windows
  });
  return res.status ?? 1;
}

function cmdPack(argv) {
  const verb = argv[0];
  const rest = argv.slice(1);
  switch (verb) {
    case "check":
      return runPython(["scripts", "pack", "check.py"], rest);
    case "register":
    case "unregister":
    case "list":
    case "floors":
      return runPython(["scripts", "_pack_registry.py"], [verb, ...rest]);
    case "install":
      // Acquisition/staging is wicked-installer's job — same code path
      // third parties use directly (`npx wicked-installer pack add …`).
      return delegateToInstaller(["pack", "add", ...rest]);
    default:
      console.log([
        "Usage: npx wicked-garden pack <verb>",
        "",
        "  pack check <dir>                  Conformance-check a pack (the shipped gate)",
        "  pack register <dir> [--source u]  Register an on-disk pack with the runtime",
        "  pack unregister <name>            Remove a registered pack",
        "  pack list [--json]                Show discovered packs (the catalog view)",
        "  pack floors [--json]              Check declared peer version floors (fail-open)",
        "  pack install <source>             Acquire + install a pack (delegates to wicked-installer)",
        "",
        "Pack authoring guide: docs/extending.md (schema: schemas/wicked-pack.schema.json)",
      ].join("\n"));
      return verb ? 1 : 0;
  }
}

function usage() {
  return [
    `wicked-garden v${pkg.version}`,
    "",
    "Usage:",
    "  npx wicked-garden install [options]   Install or update the plugin copy (`update` is an alias)",
    "  npx wicked-garden status  [options]   Show the install state per config dir (read-only)",
    "  npx wicked-garden pack <verb>         Third-party pack tooling (check/register/list/floors/install)",
    "  npx wicked-garden --version           Show version",
    "  npx wicked-garden --help              Show this usage",
    "",
    "Options:",
    "  --claude-home <dir>   Config dir to target (repeatable; default: $CLAUDE_CONFIG_DIR or ~/.claude) — install/update/status",
    "  --dry-run             Print what would be copied/synced, write nothing, never run uv — install/update only",
    "",
    "The copy is unregistered — `npx wicked-installer install wicked-garden` registers it with Claude Code.",
  ].join("\n");
}

let opts;
try {
  opts = parseArgs(process.argv.slice(2));
  if (opts.cmd === "status" && opts.dryRun) {
    throw new UsageError("--dry-run applies to install/update only (status is read-only)");
  }
} catch (err) {
  if (!(err instanceof UsageError)) throw err;
  console.error(`Error: ${err.message}\n`);
  console.error(usage());
  process.exit(2);
}

switch (opts.cmd) {
  case "install":
  case "update":
  case undefined:
    cmdInstall(resolveClaudeHomes(opts.claudeHomes), { dryRun: opts.dryRun })
      .catch(err => { console.error("Error:", err.message); process.exit(1); });
    break;
  case "status":
    cmdStatus(resolveClaudeHomes(opts.claudeHomes));
    break;
  case "pack":
    process.exit(cmdPack(opts.rest));
    break;
  case "--version":
  case "-v":
    console.log(pkg.version);
    break;
  case "--help":
  case "-h":
    console.log(usage());
    break;
  default: {
    const what = opts.cmd.startsWith("-") ? "unknown option" : "unknown command";
    console.error(`Error: ${what}: ${opts.cmd}\n`);
    console.error(usage());
    process.exit(2);
  }
}
