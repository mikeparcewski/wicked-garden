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
 * --claude-home / --dry-run belong to install/update/status only; given with any other
 * command (`--dry-run pack check`, `--version --dry-run`) they are a usage error rather
 * than being silently ignored while the command runs for real. Pack verbs own their flags.
 *
 * Exit codes: 0 ok · 1 install/status failure (refused symlink, copy error, uv sync failed)
 *             · 2 usage (unknown command/option, bad --claude-home value, CLAUDE_CONFIG_DIR
 *             set but naming no directory, install-only flag on another command).
 */
import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, realpathSync } from "node:fs";
import { join, dirname, resolve, sep } from "node:path";
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

// A value-taking flag never swallows the next option: `--claude-home --dry-run`
// is a missing value, not a directory called "--dry-run".
function claudeHomeValue(value, form) {
  if (value === undefined || value.trim() === "") {
    throw new UsageError(`${form} requires a directory`);
  }
  if (form === "--claude-home" && value.startsWith("-")) {
    throw new UsageError(`--claude-home requires a directory (got option "${value}"); use --claude-home=<dir> or an absolute path for a directory whose name starts with "-"`);
  }
  return value;
}

function parseArgs(argv) {
  const opts = { cmd: undefined, rest: [], claudeHomes: [], dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (opts.cmd === "pack") { opts.rest.push(arg); continue; }
    if (arg === "--dry-run") {
      opts.dryRun = true;
    } else if (arg === "--claude-home") {
      opts.claudeHomes.push(claudeHomeValue(argv[i + 1], "--claude-home"));
      i += 1;
    } else if (arg.startsWith("--claude-home=")) {
      opts.claudeHomes.push(claudeHomeValue(arg.slice("--claude-home=".length), "--claude-home="));
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
//      several dirs, split on the platform list separator + ','. Set but naming
//      no directory (e.g. ":,", blanks) is an error, never a silent ~/.claude;
//      the empty string counts as unset (the ${CLAUDE_CONFIG_DIR:-~/.claude}
//      convention the shipped Python already follows);
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
  let dirs;
  let origin;
  if (claudeHomes.length > 0) {
    dirs = claudeHomes;
    origin = "--claude-home";
  } else if (env.CLAUDE_CONFIG_DIR !== undefined && env.CLAUDE_CONFIG_DIR !== "") {
    dirs = splitConfigDirValue(env.CLAUDE_CONFIG_DIR);
    origin = "CLAUDE_CONFIG_DIR";
    if (dirs.length === 0) {
      throw new UsageError(`CLAUDE_CONFIG_DIR is set but names no directory (value: ${JSON.stringify(env.CLAUDE_CONFIG_DIR)}); unset it or point it at a config dir`);
    }
  } else {
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

// ---------------------------------------------------------------------------
// Symlink containment. The config dir itself may be a symlink (dotfiles-managed
// ~/.claude is common and we never create it when it exists); the components we
// OWN under it — plugins/, plugins/wicked-garden, .claude-plugin/, the manifest —
// are never followed: a symlink there is refused, and after a copy the
// destination's realpath must still resolve inside the config dir's realpath.
// ---------------------------------------------------------------------------

function isSymlink(p) {
  try { return lstatSync(p).isSymbolicLink(); } catch { return false; }
}

function ownedPaths(home, dest) {
  return [join(home, "plugins"), dest, join(dest, ".claude-plugin"), join(dest, ".claude-plugin", "plugin.json")];
}

function findSymlink(home, dest) {
  return ownedPaths(home, dest).find(isSymlink);
}

function assertContained(home, dest) {
  const realHome = realpathSync(home);
  const realDest = realpathSync(dest);
  if (realDest !== realHome && !realDest.startsWith(realHome + sep)) {
    throw new Error(`refusing: ${dest} resolves to ${realDest}, outside ${realHome}`);
  }
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
  const uvFailures = [];

  // Refuse up front, before anything is written anywhere.
  for (const { dir: home, dest } of homes) {
    const link = findSymlink(home, dest);
    if (link) throw new Error(`refusing to install: ${link} is a symlink (wicked-garden never follows symlinks under plugins/)`);
  }

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
    assertContained(home, dest);

    for (const dir of dirs) {
      process.stdout.write(`  ${dir}/... `);
      cpSync(join(__dirname, dir), join(dest, dir), { recursive: true, force: true, filter: (s) => !skip(s) });
      console.log("done");
    }
    for (const file of files) {
      cpSync(join(__dirname, file), join(dest, file), { force: true });
    }
    assertContained(home, dest);

    // Sync Python deps via uv if available. A failure is reported, never swallowed:
    // the copy stays usable and the wicked-garden-core setup action retries the sync,
    // but this run does not claim success.
    if (uv) {
      process.stdout.write("  Python deps (uv sync)... ");
      try {
        execSync(`"${uv}" sync --quiet`, { cwd: dest, stdio: "pipe" });
        console.log("done");
      } catch (err) {
        console.log("FAILED");
        const detail = String(err.stderr || err.message || "").trim().split("\n").slice(-3).join(" | ");
        console.error(`WARNING: uv sync failed in ${dest}${detail ? `: ${detail}` : ""}`);
        uvFailures.push(dest);
      }
    }

    console.log(`  ${REGISTER_NOTE}`);
  }

  const n = homes.length;
  const dirsWord = `${n} config dir${n === 1 ? "" : "s"}`;
  if (dryRun) {
    console.log(`\n[dry-run] Nothing was written. wicked-garden v${pkg.version} would be copied into ${dirsWord}.`);
    return;
  }
  if (uvFailures.length > 0) {
    console.error(`\nwicked-garden v${pkg.version} copied (unregistered) into ${dirsWord}, but Python deps FAILED to sync in ${uvFailures.length} of them — fix the uv error above and re-run install, or let the wicked-garden-core setup action retry.`);
    console.error("Registration is still the installer's job: `npx wicked-installer install wicked-garden`.");
    process.exitCode = 1;
    return;
  }
  console.log(`\nwicked-garden v${pkg.version} ${REGISTER_NOTE}`);
  console.log('Then, in Claude Code, ask for "wicked-garden setup" (the wicked-garden-core skill) to complete configuration.');
}

function cmdStatus(homes) {
  let refused = 0;
  for (const { dir: home, dest, origin } of homes) {
    console.log(`config dir: ${home} (${origin})`);
    const link = findSymlink(home, dest);
    if (link) {
      console.error(`  refused: ${link} is a symlink (wicked-garden never follows symlinks under plugins/)`);
      refused += 1;
      continue;
    }
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
  return refused > 0 ? 1 : 0;
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

const TARGETED = new Set(["install", "update", undefined, "status"]);

let opts;
let homes;
try {
  opts = parseArgs(process.argv.slice(2));
  if (!TARGETED.has(opts.cmd) && (opts.dryRun || opts.claudeHomes.length > 0)) {
    const given = [opts.dryRun && "--dry-run", opts.claudeHomes.length > 0 && "--claude-home"].filter(Boolean).join(" / ");
    throw new UsageError(`${given} applies to install/update/status only, not to \`${opts.cmd}\`${opts.cmd === "pack" ? " (pack verbs own their flags — place them after the verb)" : ""}`);
  }
  if (opts.cmd === "status" && opts.dryRun) {
    throw new UsageError("--dry-run applies to install/update only (status is read-only)");
  }
  if (TARGETED.has(opts.cmd)) homes = resolveClaudeHomes(opts.claudeHomes);
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
    cmdInstall(homes, { dryRun: opts.dryRun })
      .catch(err => { console.error("Error:", err.message); process.exit(1); });
    break;
  case "status":
    process.exitCode = cmdStatus(homes);
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
