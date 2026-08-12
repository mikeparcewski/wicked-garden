#!/usr/bin/env node
/**
 * wicked-garden installer
 * Copies plugin files to ~/.claude/plugins/wicked-garden/ and optionally syncs Python deps.
 *
 * Usage:
 *   npx wicked-garden install         Install or update the plugin
 *   npx wicked-garden update          Same as install
 *   npx wicked-garden status          Show current install state
 *   npx wicked-garden pack <verb>     Third-party pack tooling (check/register/list/…)
 *   npx wicked-garden --version       Print version
 */
import { cpSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
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

async function cmdInstall() {
  const dest      = join(homedir(), ".claude", "plugins", "wicked-garden");
  const isUpdate  = existsSync(dest);

  console.log(isUpdate
    ? `Updating wicked-garden v${pkg.version} at ${dest}...`
    : `Installing wicked-garden v${pkg.version} to ${dest}...`
  );

  mkdirSync(dest, { recursive: true });

  for (const dir of PLUGIN_DIRS) {
    const src = join(__dirname, dir);
    if (!existsSync(src)) continue;
    process.stdout.write(`  ${dir}/... `);
    cpSync(src, join(dest, dir), { recursive: true, force: true, filter: (s) => !skip(s) });
    console.log("done");
  }

  for (const file of PLUGIN_FILES) {
    const src = join(__dirname, file);
    if (existsSync(src)) cpSync(src, join(dest, file), { force: true });
  }

  // Sync Python deps via uv if available (setup will retry if this is skipped)
  const uv = findBin("uv");
  if (uv) {
    process.stdout.write("  Python deps (uv sync)... ");
    try {
      execSync(`"${uv}" sync --quiet`, { cwd: dest, stdio: "pipe" });
      console.log("done");
    } catch {
      console.log("skipped — the wicked-garden-core setup action will retry");
    }
  }

  console.log(`\nwicked-garden v${pkg.version} ${isUpdate ? "updated" : "installed"}.`);
  console.log('Next: in Claude Code, ask for "wicked-garden setup" (the wicked-garden-core skill) to complete configuration.');
}

function cmdStatus() {
  const dest = join(homedir(), ".claude", "plugins", "wicked-garden");
  if (!existsSync(dest)) {
    console.log("wicked-garden: not installed");
    console.log(`  Run: npx wicked-garden@${pkg.version} install`);
    return;
  }
  try {
    const installed = JSON.parse(readFileSync(join(dest, ".claude-plugin", "plugin.json"), "utf8"));
    const upToDate  = installed.version === pkg.version;
    console.log(`wicked-garden: installed`);
    console.log(`  path:    ${dest}`);
    console.log(`  version: ${installed.version}${upToDate ? "" : ` (package: ${pkg.version} — run install to update)`}`);
  } catch {
    console.log(`wicked-garden: installed at ${dest} (plugin.json unreadable)`);
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

const cmd = process.argv[2];
switch (cmd) {
  case "install":
  case "update":
  case undefined:
    cmdInstall().catch(err => { console.error("Error:", err.message); process.exit(1); });
    break;
  case "status":
    cmdStatus();
    break;
  case "pack":
    process.exit(cmdPack(process.argv.slice(3)));
    break;
  case "--version":
  case "-v":
    console.log(pkg.version);
    break;
  default:
    console.log([
      `wicked-garden v${pkg.version}`,
      "",
      "Usage:",
      "  npx wicked-garden install         Install or update the plugin",
      "  npx wicked-garden status          Show current install state",
      "  npx wicked-garden pack <verb>     Third-party pack tooling (check/register/list/floors/install)",
      "  npx wicked-garden --version       Show version",
    ].join("\n"));
}
