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
 *   --dry-run             Print what would be copied/synced, write nothing, spawn nothing
 *                         — install/update only (status is read-only and rejects it)
 *
 * --claude-home / --dry-run belong to install/update/status only; given with any other
 * command (`--dry-run pack check`, `--version --dry-run`) they are a usage error rather
 * than being silently ignored while the command runs for real. Pack verbs own their flags.
 *
 * How a copy lands (stage → verify → atomic swap): the plugin is copied into a staging
 * directory this run creates — `plugins/.staging-wicked-garden-<pid>-<hex>` — so no
 * pre-existing symlink can ever be written through; the staged tree is lstat-walked
 * (no symlinks, realpath-contained), then swapped into `plugins/wicked-garden` with
 * rename(2); a previous copy is moved to `plugins/.old-wicked-garden-<pid>-<hex>` and is
 * removed ONLY after the installed tree passed post-swap verification (walk, containment,
 * manifest parse, version) — if that fails, the failed tree goes to
 * `plugins/.failed-wicked-garden-<pid>-<hex>`, the previous copy is renamed back and
 * re-verified, and the run exits 1 naming the failed check. Those three transient names
 * are NOT plugins — a leftover after an interrupted install is safe to delete (status lists them).
 *
 * Exit codes: 0 ok · 1 install/status failure (refused symlink, copy/swap error, failed
 *             verification with the previous copy restored, unreadable manifest, uv sync
 *             failed) · 2 usage (unknown command/option, bad --claude-home value,
 *             CLAUDE_CONFIG_DIR set but naming no directory, install-only flag on another
 *             command) · 3 ROLLBACK FAILED (a previous copy could not be put back — the
 *             diagnostic names where the previous and the failed trees were left).
 */
import {
  closeSync, constants, cpSync, existsSync, fstatSync, lstatSync, mkdirSync, openSync,
  readdirSync, readFileSync, realpathSync, renameSync, rmSync,
} from "node:fs";
import { join, dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";
import { execSync, spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(__dirname, "package.json"), "utf8"));

const PLUGIN_DIRS  = [".claude-plugin", "hooks", "scripts", "skills", "schemas"];
const PLUGIN_FILES = ["ETHOS.md", "CHANGELOG.md", "README.md", "WICKED_GARDEN_BUS_EVENTS.md", "pyproject.toml"];
const SKIP         = [/__pycache__/, /\.pyc$/, /\.pyo$/, /\.DS_Store$/];
// Dev-only subdirs within scripts/ — not needed at runtime
const SCRIPTS_DEV  = ["ci", "wg"];

// Transient names used during a swap. Never treated as plugins; safe to delete if left over.
const STAGING_PREFIX = ".staging-wicked-garden-";
const OLD_PREFIX     = ".old-wicked-garden-";
const FAILED_PREFIX  = ".failed-wicked-garden-";
const TRANSIENT_PREFIXES = [STAGING_PREFIX, OLD_PREFIX, FAILED_PREFIX];

// Test-only fault injection (tests/test_install_mjs.py): `rollback-restore` makes the
// rename that puts a previous copy back fail, to prove the ROLLBACK FAILED path. The
// variable is never set in production and no other value has any effect.
const INSTALL_FAULT = process.env.WICKED_GARDEN_INSTALL_FAULT;

class RollbackFailed extends Error {
  constructor(message) { super(message); this.exitCode = 3; }
}

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

// A value-taking flag never swallows an option, in either form: `--claude-home --dry-run`,
// `--claude-home=--dry-run` and `--claude-home=-x` are errors, as are empty/blank values.
// A directory whose name really starts with "-" is written `./-x` or as an absolute path.
// The value is trimmed once and the TRIMMED value is what gets validated and used.
function claudeHomeValue(raw, form) {
  const value = raw === undefined ? "" : raw.trim();
  if (value === "") {
    throw new UsageError(`${form} requires a directory`);
  }
  if (value.startsWith("-")) {
    throw new UsageError(`${form} requires a directory (got option-like value "${value}"); write ./${value} or an absolute path for a directory whose name starts with "-"`);
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
//   2. CLAUDE_CONFIG_DIR is authoritative and exclusive when PRESENT in the
//      environment — it may list several dirs, split on the platform list
//      separator + ','. Present but naming no directory ("" / ":,", blanks) is an
//      error, never a silent ~/.claude;
//   3. only when the key is absent: ~/.claude.
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
  } else if ("CLAUDE_CONFIG_DIR" in env) {
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
    out.push({ dir, pluginsDir: join(dir, "plugins"), dest: join(dir, "plugins", "wicked-garden"), origin });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Symlink containment. The config dir itself may be a symlink (dotfiles-managed
// ~/.claude is common and we never create it when it exists). Under it we never
// write into a pre-existing tree: the copy goes into a staging dir THIS run
// created (nothing can be planted inside it), is lstat-walked, and is swapped in
// with rename(2). plugins/ and plugins/wicked-garden themselves are refused when
// symlinked, and manifests are opened O_NOFOLLOW. Residual (documented, same
// discipline as crew's v3.5): a parent directory swapped between our verify and
// our use — the window between lstat/realpath and the following syscall.
// ---------------------------------------------------------------------------

function lstatOrNull(p) {
  try { return lstatSync(p); } catch (err) { if (err.code === "ENOENT") return null; throw err; }
}

function isSymlink(p) {
  const st = lstatOrNull(p);
  return st !== null && st.isSymbolicLink();
}

// Both sides are realpaths. path.relative() must neither climb out nor be absolute;
// Windows paths are case-insensitive and realpath may re-case the drive letter.
function isContained(rootReal, targetReal) {
  const norm = (p) => (process.platform === "win32" ? p.toLowerCase() : p);
  const rel = relative(norm(rootReal), norm(targetReal));
  return rel === "" || (rel !== ".." && !rel.startsWith(".." + sep) && !isAbsolute(rel));
}

function assertContained(root, target, what) {
  const rootReal = realpathSync(root);
  const targetReal = realpathSync(target);
  if (!isContained(rootReal, targetReal)) {
    throw new Error(`refusing: ${what} ${target} resolves to ${targetReal}, outside ${rootReal}`);
  }
}

// Walk a tree with lstat: no symlink anywhere, every directory realpath-contained in root.
function verifyTree(root) {
  const rootReal = realpathSync(root);
  const stack = [root];
  let entries = 0;
  while (stack.length > 0) {
    const dir = stack.pop();
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      const st = lstatSync(p);
      if (st.isSymbolicLink()) throw new Error(`refusing: ${p} is a symlink (wicked-garden never follows symlinks under plugins/)`);
      entries += 1;
      if (st.isDirectory()) {
        if (!isContained(rootReal, realpathSync(p))) throw new Error(`refusing: ${p} escapes ${rootReal}`);
        stack.push(p);
      }
    }
  }
  return entries;
}

// Read a file without following a symlink at the final component: O_NOFOLLOW where
// the platform has it (POSIX), lstat-then-read on win32 (TOCTOU residual, see above).
function readNoFollow(p) {
  if (constants.O_NOFOLLOW !== undefined) {
    const fd = openSync(p, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      if (!fstatSync(fd).isFile()) throw new Error(`${p} is not a regular file`);
      return readFileSync(fd, "utf8");
    } finally {
      closeSync(fd);
    }
  }
  const st = lstatSync(p);
  if (st.isSymbolicLink()) throw new Error(`${p} is a symlink`);
  if (!st.isFile()) throw new Error(`${p} is not a regular file`);
  return readFileSync(p, "utf8");
}

function transientName(prefix) {
  return `${prefix}${process.pid}-${randomBytes(4).toString("hex")}`;
}

function leftoverTransients(pluginsDir) {
  try {
    return readdirSync(pluginsDir).filter(n => TRANSIENT_PREFIXES.some(p => n.startsWith(p))).map(n => join(pluginsDir, n));
  } catch {
    return [];
  }
}

// The four post-swap checks, each named in its failure so a diagnostic can cite it.
// `expectVersion === null` verifies a restored (possibly older) copy without pinning it.
function verifyInstalledTree(home, dest, expectVersion) {
  try { verifyTree(dest); } catch (err) { throw new Error(`tree walk: ${err.message}`); }
  try { assertContained(home, dest, "plugin dir"); } catch (err) { throw new Error(`containment: ${err.message}`); }
  let installed;
  try {
    installed = JSON.parse(readNoFollow(join(dest, ".claude-plugin", "plugin.json")));
  } catch (err) {
    throw new Error(`manifest parse: ${join(dest, ".claude-plugin", "plugin.json")}: ${err.message}`);
  }
  if (expectVersion !== null && installed.version !== expectVersion) {
    throw new Error(`version check: ${dest} reports ${installed.version}, expected ${expectVersion}`);
  }
  return installed;
}

// Post-swap verification failed: move the failed tree aside, put the previous copy back,
// verify it, and report. Anything going wrong in here is a ROLLBACK FAILED — printed with
// both locations, never swallowed.
function rollback(home, pluginsDir, dest, old, cause) {
  const failed = join(pluginsDir, transientName(FAILED_PREFIX));
  let failedAt = dest;
  let previousAt = old;
  try {
    renameSync(dest, failed);
    failedAt = failed;
    if (old) {
      if (INSTALL_FAULT === "rollback-restore") throw new Error("injected fault: rollback-restore");
      renameSync(old, dest);
      previousAt = dest;
      verifyInstalledTree(home, dest, null);
    }
    rmSync(failed, { recursive: true, force: true });
    failedAt = null;
  } catch (rbErr) {
    throw new RollbackFailed(
      `ROLLBACK FAILED: previous install left at ${previousAt ?? "(none existed)"}, failed install at ${failedAt ?? "(removed)"}` +
      ` — verification failure: ${cause.message}; rollback error: ${rbErr.message}`);
  }
  throw new Error(`post-install verification failed (${cause.message}); ${old ? `previous install restored at ${dest}` : `no previous install existed, so ${dest} is now absent`}`);
}

function planCopies() {
  return {
    dirs:  PLUGIN_DIRS.filter(d => existsSync(join(__dirname, d))),
    files: PLUGIN_FILES.filter(f => existsSync(join(__dirname, f))),
  };
}

// Stage → verify → swap → verify → discard old, for one config dir. The previous copy is
// discarded only after the installed tree passed verification; on any failure before that
// the staging dir is removed and the previous copy is left (or put back) where it was.
function stageAndSwap({ dir: home, pluginsDir, dest }, { dirs, files }) {
  mkdirSync(pluginsDir, { recursive: true });
  assertContained(home, pluginsDir, "plugins dir");
  const staging = join(pluginsDir, transientName(STAGING_PREFIX));
  mkdirSync(staging); // not recursive: must not pre-exist (EEXIST is a failure, not a reuse)
  console.log(`  staging: ${staging}`);
  let old;
  try {
    for (const d of dirs) {
      process.stdout.write(`  ${d}/... `);
      cpSync(join(__dirname, d), join(staging, d), { recursive: true, force: true, filter: (s) => !skip(s) });
      console.log("done");
    }
    for (const f of files) {
      cpSync(join(__dirname, f), join(staging, f), { force: true });
    }
    const entries = verifyTree(staging);
    assertContained(home, staging, "staging dir");

    const finalSt = lstatOrNull(dest);
    if (finalSt && finalSt.isSymbolicLink()) {
      throw new Error(`refusing to install: ${dest} is a symlink (wicked-garden never follows symlinks under plugins/)`);
    }
    if (finalSt) {
      old = join(pluginsDir, transientName(OLD_PREFIX));
      renameSync(dest, old);
    }
    try {
      renameSync(staging, dest);
    } catch (err) {
      if (old) {
        try {
          renameSync(old, dest);
        } catch (rbErr) {
          throw new RollbackFailed(`ROLLBACK FAILED: previous install left at ${old}, ${dest} is absent — swap error: ${err.message}; rollback error: ${rbErr.message}`);
        }
      }
      throw err;
    }
    console.log(`  swapped ${entries} entries into ${dest}`);
  } catch (err) {
    rmSync(staging, { recursive: true, force: true });
    throw err;
  }

  // Post-swap verification of the tree we just installed, in place (see the residual note
  // above) — BEFORE the previous copy is discarded, so a failure can still be rolled back.
  try {
    verifyInstalledTree(home, dest, pkg.version);
  } catch (verifyErr) {
    rollback(home, pluginsDir, dest, old, verifyErr); // always throws
  }
  if (old) rmSync(old, { recursive: true, force: true });
  console.log(`  verified${old ? " (previous copy replaced)" : ""}`);
}

async function cmdInstall(homes, { dryRun }) {
  const plan = planCopies();
  const tag = dryRun ? "[dry-run] " : "";
  const uvFailures = [];

  // Refuse up front, before anything is written anywhere.
  for (const { pluginsDir, dest } of homes) {
    const link = [pluginsDir, dest].find(isSymlink);
    if (link) throw new Error(`refusing to install: ${link} is a symlink (wicked-garden never follows symlinks under plugins/)`);
  }

  // Dry-run spawns nothing — not even the `command -v uv` probe — so uv is resolved
  // only once we are actually going to sync.
  const uv = dryRun ? undefined : findBin("uv");

  for (const home of homes) {
    const { dir, pluginsDir, dest, origin } = home;
    const isUpdate = existsSync(dest);
    console.log(`${tag}${isUpdate ? "Updating" : "Installing"} wicked-garden v${pkg.version} ${isUpdate ? "at" : "to"} ${dest}`);
    console.log(`  config dir: ${dir} (${origin})`);

    if (dryRun) {
      console.log(`  would stage into ${join(pluginsDir, `${STAGING_PREFIX}<pid>-<hex>`)} and swap it into ${dest}`);
      for (const d of plan.dirs)  console.log(`  would copy ${d}/ -> ${join(dest, d)}`);
      for (const f of plan.files) console.log(`  would copy ${f} -> ${join(dest, f)}`);
      console.log(`  would run: uv sync --quiet (cwd ${dest}) if uv is on PATH — not probed in dry-run`);
      continue;
    }

    stageAndSwap(home, plan);

    // Sync Python deps via uv if available. A failure is reported, never swallowed:
    // the copy stays usable and the wicked-garden-core setup action retries the sync,
    // but this run does not claim success.
    if (uv) {
      process.stdout.write("  Python deps (uv sync)... ");
      // argv array, no shell: the resolved uv path is never re-parsed by a shell.
      const res = spawnSync(uv, ["sync", "--quiet"], { cwd: dest, stdio: "pipe", encoding: "utf8" });
      if (!res.error && res.status === 0) {
        console.log("done");
      } else {
        console.log("FAILED");
        const raw = res.error ? res.error.message : `${res.stderr || ""}${res.status === null ? ` (signal ${res.signal})` : ` (exit ${res.status})`}`;
        const detail = raw.trim().split("\n").slice(-3).join(" | ");
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
  let failures = 0;
  for (const { dir: home, pluginsDir, dest, origin } of homes) {
    console.log(`config dir: ${home} (${origin})`);
    const manifest = join(dest, ".claude-plugin", "plugin.json");
    const link = [pluginsDir, dest, join(dest, ".claude-plugin"), manifest].find(isSymlink);
    if (link) {
      console.error(`  refused: ${link} is a symlink (wicked-garden never follows symlinks under plugins/)`);
      failures += 1;
      continue;
    }
    for (const t of leftoverTransients(pluginsDir)) {
      console.log(`  leftover transient dir from an interrupted install (not a plugin; safe to delete): ${t}`);
    }
    if (!existsSync(dest)) {
      console.log("  wicked-garden: not installed");
      const hint = origin === "--claude-home" ? ` --claude-home "${home}"` : "";
      console.log(`  Run: npx wicked-garden@${pkg.version} install${hint}`);
      continue;
    }
    let installed;
    try {
      installed = JSON.parse(readNoFollow(manifest));
    } catch (err) {
      console.error(`  error: cannot read ${manifest}: ${err.code ? `${err.code}: ` : ""}${err.message} — re-run install to repair the copy`);
      failures += 1;
      continue;
    }
    const upToDate = installed.version === pkg.version;
    console.log("  wicked-garden: installed (copy)");
    console.log(`  path:    ${dest}`);
    console.log(`  version: ${installed.version}${upToDate ? "" : ` (package: ${pkg.version} — run install to update)`}`);
    console.log("  registration: owned by wicked-installer — `npx wicked-installer status` reports Claude Code's registry state");
  }
  return failures > 0 ? 1 : 0;
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
    "  --dry-run             Print what would be copied/synced, write nothing, spawn nothing — install/update only",
    "",
    "The copy is staged in plugins/.staging-wicked-garden-<pid>-<hex> and swapped in atomically; a previous",
    "copy passes through plugins/.old-wicked-garden-<pid>-<hex> (a tree that fails verification through",
    "plugins/.failed-wicked-garden-<pid>-<hex>). None of the three is a plugin; leftovers are safe to delete.",
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
      .catch(err => { console.error("Error:", err.message); process.exit(err.exitCode ?? 1); });
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
