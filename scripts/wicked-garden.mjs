#!/usr/bin/env node
/**
 * wicked-garden launcher — the ONE way skill text reaches the plugin's shared runtime.
 *
 * Skill bodies are installed into very different layouts: the whole plugin under
 * Claude Code, a flat skills-only copy under Codex / Pi / OpenCode / Antigravity
 * (no scripts/, no venv, siblings laid out by NAME), and wicked-crew's read-only
 * snapshot. `${CLAUDE_PLUGIN_ROOT}` is substituted by Claude Code only, so skill text
 * never spells a plugin path; it says `wicked-garden run scripts/<x>.py …` and this
 * launcher resolves the root and the interpreter wherever it runs.
 *
 * Verbs (node >= 20 — the package's `engines` floor — no dependencies):
 *   wicked-garden run <root-relative path> [args…]   run a file under the plugin root
 *                                                    (.py → python, .mjs/.js/.cjs → node,
 *                                                    .sh → sh); cwd is left untouched
 *   wicked-garden python <root-relative path|-|-c …> [args…]
 *                                                    force the python interpreter (stdin
 *                                                    `-` and `-c code` pass through)
 *   wicked-garden path <root-relative path>          print the absolute path (must exist)
 *   wicked-garden root                               print the resolved plugin root
 *   wicked-garden doctor                             JSON report: root, its source, python,
 *                                                    node, uv, what was tried
 *   wicked-garden --version | --help
 *
 * Root resolution order (the first that qualifies wins; a candidate qualifies when it
 * contains `.claude-plugin/plugin.json` naming `wicked-garden`):
 *   1. WICKED_GARDEN_ROOT  — set per seat by wicked-crew/wicked-core; when it is set but
 *                            does not qualify the launcher REFUSES (exit 2) instead of
 *                            guessing — a seat must never run a different garden's scripts;
 *   2. CLAUDE_PLUGIN_ROOT  — exported into Bash by the plugin's bootstrap hook on Claude
 *                            Code; skipped (and reported by `doctor`) when it names some
 *                            other plugin;
 *   3. the launcher's own package directory (`npm i -g wicked-garden`, `npx wicked-garden`,
 *                            a marketplace copy, a crew snapshot).
 *
 * Python interpreter ladder for `.py`:
 *   <root>/.venv/bin/python (Scripts\python.exe on Windows) when present — crew's synced
 *   venv, or the one `npx wicked-garden install` created →
 *   `uv run --project <root> --frozen --no-dev python` with UV_PROJECT_ENVIRONMENT under the
 *   user cache dir (never under the root; needs <root>/uv.lock, otherwise uv is skipped
 *   because it would write a lockfile into the root) →
 *   python3 → python → py -3 (the historical scripts/_python.sh ladder). On Windows only real
 *   `.exe` interpreters qualify — `.cmd`/`.bat` shims are skipped (reported by doctor).
 *
 * Invariants: the launcher never writes under the root; the child inherits the caller's
 * cwd (a worktree) and gets WICKED_GARDEN_ROOT and CLAUDE_PLUGIN_ROOT set to the resolved
 * root so the shipped scripts' own root resolvers keep working off-Claude. Every failure is
 * one JSON line on stderr — `{"ok": false, "reason": …, "tried": […]}` — naming what was
 * tried. Exit codes: the child's · 1 runtime failure · 2 usage / root refusal.
 *
 * The pure helpers below are exported for tests (tests/test_launcher.py drives them via
 * `node -e "import(...)"` to cover Windows path building without a Windows host).
 */
import { existsSync, readFileSync, realpathSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const VERBS = ["run", "python", "path", "root", "doctor"];
export const MANIFEST_REL = [".claude-plugin", "plugin.json"];
export const PLUGIN_NAME = "wicked-garden";

const NODE_EXTS = new Set([".mjs", ".js", ".cjs"]);

export class LauncherError extends Error {
  constructor(reason, { tried = [], exitCode = 1 } = {}) {
    super(reason);
    this.reason = reason;
    this.tried = tried;
    this.exitCode = exitCode;
  }
  toJSON() {
    return { ok: false, reason: this.reason, tried: this.tried };
  }
}

function pathModuleFor(platform) {
  return platform === "win32" ? path.win32 : path.posix;
}

/** The directory this launcher ships in is `<plugin root>/scripts/`. */
export function ownPackageRoot(moduleUrl = import.meta.url) {
  return path.dirname(path.dirname(fileURLToPath(moduleUrl)));
}

/** A plugin root is a directory whose `.claude-plugin/plugin.json` names wicked-garden. */
export function pluginManifestOf(dir, fs = { existsSync, readFileSync }) {
  const manifest = path.join(dir, ...MANIFEST_REL);
  if (!fs.existsSync(manifest)) return { ok: false, reason: `no ${MANIFEST_REL.join("/")}` };
  try {
    const parsed = JSON.parse(fs.readFileSync(manifest, "utf8"));
    if (parsed.name !== PLUGIN_NAME) {
      return { ok: false, reason: `plugin.json names "${parsed.name}", not "${PLUGIN_NAME}"` };
    }
    return { ok: true, version: parsed.version };
  } catch (err) {
    return { ok: false, reason: `unreadable plugin.json: ${err.message}` };
  }
}

/**
 * Resolve the plugin root. Returns { root, source, version, tried }. Throws a
 * LauncherError(exit 2) when WICKED_GARDEN_ROOT is set but does not qualify, or when
 * nothing qualifies.
 */
export function resolveRoot(env = process.env, ownRoot = ownPackageRoot(), probe = pluginManifestOf) {
  const tried = [];
  if (env.WICKED_GARDEN_ROOT !== undefined) {
    const raw = env.WICKED_GARDEN_ROOT;
    const candidate = raw.trim() === "" ? "" : path.resolve(raw);
    const check = candidate === "" ? { ok: false, reason: "empty value" } : probe(candidate);
    if (check.ok) return { root: candidate, source: "WICKED_GARDEN_ROOT", version: check.version, tried };
    tried.push({ source: "WICKED_GARDEN_ROOT", path: raw, reason: check.reason });
    throw new LauncherError(
      `WICKED_GARDEN_ROOT=${JSON.stringify(raw)} is not a wicked-garden plugin root (${check.reason}); ` +
        "refusing to fall back to another root — unset it or point it at the snapshot/plugin directory",
      { tried, exitCode: 2 },
    );
  }
  if (env.CLAUDE_PLUGIN_ROOT) {
    const candidate = path.resolve(env.CLAUDE_PLUGIN_ROOT);
    const check = probe(candidate);
    if (check.ok) return { root: candidate, source: "CLAUDE_PLUGIN_ROOT", version: check.version, tried };
    tried.push({ source: "CLAUDE_PLUGIN_ROOT", path: env.CLAUDE_PLUGIN_ROOT, reason: check.reason });
  }
  const own = probe(ownRoot);
  if (own.ok) return { root: ownRoot, source: "package", version: own.version, tried };
  tried.push({ source: "package", path: ownRoot, reason: own.reason });
  throw new LauncherError(
    "no wicked-garden plugin root found: set WICKED_GARDEN_ROOT to the plugin/snapshot directory, " +
      "or run the launcher from an installed wicked-garden package (npm i -g wicked-garden / npx wicked-garden)",
    { tried, exitCode: 2 },
  );
}

/** Python candidates inside a root's `.venv`, platform-aware (pure). */
export function venvPythonCandidates(root, platform = process.platform) {
  const p = pathModuleFor(platform);
  if (platform === "win32") return [p.join(root, ".venv", "Scripts", "python.exe")];
  return [p.join(root, ".venv", "bin", "python3"), p.join(root, ".venv", "bin", "python")];
}

/** Interpreter kind by extension (pure): python | node | sh. */
export function interpreterKindFor(rel) {
  const ext = path.posix.extname(rel.replace(/\\/g, "/")).toLowerCase();
  if (ext === ".py") return "python";
  if (NODE_EXTS.has(ext)) return "node";
  if (ext === ".sh") return "sh";
  return null;
}

/** Per-user cache dir for uv project environments (pure; never under the root). */
export function cacheDir(env = process.env, platform = process.platform, home = homedir()) {
  const p = pathModuleFor(platform);
  if (env.WICKED_GARDEN_CACHE_DIR) return env.WICKED_GARDEN_CACHE_DIR;
  if (platform === "win32") return p.join(env.LOCALAPPDATA || p.join(home, "AppData", "Local"), PLUGIN_NAME, "cache");
  return p.join(env.XDG_CACHE_HOME || p.join(home, ".cache"), PLUGIN_NAME);
}

/** Where uv materialises the env for a given root: <cache>/venvs/<hash-of-root> (pure). */
export function uvProjectEnvironment(root, cache, platform = process.platform) {
  const p = pathModuleFor(platform);
  const key = createHash("sha256").update(root).digest("hex").slice(0, 16);
  return p.join(cache, "venvs", key);
}

/**
 * Look an executable up on PATH without a shell. On Windows only real `.exe` files qualify:
 * `.cmd`/`.bat` shims (pyenv-win's `python.bat`, npm shims) cannot be spawned shell-less on
 * Node >= 20 (EINVAL, CVE-2024-27980) and running them through cmd.exe would mean building a
 * command line from environment-derived paths — so they are skipped, reported by `doctor`
 * via `tried`, and the ladder falls through to the next real interpreter (`py.exe -3`).
 */
export function findOnPath(name, env = process.env, platform = process.platform, fs = { existsSync, statSync }) {
  const sep = platform === "win32" ? ";" : ":";
  const exts = platform === "win32" ? [".exe"] : [""];
  const p = pathModuleFor(platform);
  for (const dir of (env.PATH || "").split(sep)) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = p.join(dir, name + ext);
      try {
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
      } catch {
        /* unreadable PATH entry — keep looking */
      }
    }
  }
  return null;
}

/** The `.cmd`/`.bat` shims findOnPath refused for `name` (win32 only; pure apart from stat). */
export function skippedShimsOnPath(name, env = process.env, platform = process.platform, fs = { existsSync, statSync }) {
  if (platform !== "win32") return [];
  const found = [];
  const p = pathModuleFor(platform);
  for (const dir of (env.PATH || "").split(";")) {
    if (!dir) continue;
    for (const ext of [".cmd", ".bat"]) {
      const candidate = p.join(dir, name + ext);
      try {
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) found.push(candidate);
      } catch {
        /* unreadable PATH entry */
      }
    }
  }
  return found;
}

/**
 * Pick the python for a root. Always returns { kind, argv, env, tried }; `kind` is null (and
 * argv empty) when no interpreter exists, `tried` says why each rung was skipped.
 * kinds: venv | uv | python3 | python | py.
 */
export function pickPython(root, env = process.env, platform = process.platform, fs = { existsSync, statSync }) {
  const tried = [];
  for (const candidate of venvPythonCandidates(root, platform)) {
    if (fs.existsSync(candidate)) return { kind: "venv", argv: [candidate], env: {}, tried };
    tried.push({ kind: "venv", path: candidate, reason: "absent" });
  }
  const uv = findOnPath("uv", env, platform, fs);
  if (uv) {
    const lock = path.join(root, "uv.lock");
    if (fs.existsSync(lock)) {
      const projectEnv = uvProjectEnvironment(root, cacheDir(env, platform), platform);
      return {
        kind: "uv",
        argv: [uv, "run", "--project", root, "--frozen", "--no-dev", "python"],
        env: { UV_PROJECT_ENVIRONMENT: projectEnv },
        tried,
      };
    }
    tried.push({ kind: "uv", path: uv, reason: `skipped: no ${lock} (uv would write a lockfile into the root)` });
  } else {
    tried.push({ kind: "uv", reason: "not on PATH" });
  }
  for (const name of ["python3", "python"]) {
    const found = findOnPath(name, env, platform, fs);
    if (found) return { kind: name, argv: [found], env: {}, tried };
    const shims = skippedShimsOnPath(name, env, platform, fs);
    tried.push(shims.length
      ? { kind: name, path: shims[0], reason: ".cmd/.bat shim skipped (not spawnable without a shell) — install a real interpreter or use py -3" }
      : { kind: name, reason: "not on PATH" });
  }
  const py = findOnPath("py", env, platform, fs);
  if (py) return { kind: "py", argv: [py, "-3"], env: {}, tried };
  tried.push({ kind: "py", reason: "not on PATH" });
  return { kind: null, argv: [], env: {}, tried };
}

/** Resolve a root-relative path, refusing absolute paths and escapes (pure apart from stat). */
export function resolveUnderRoot(root, rel, fs = { existsSync }) {
  if (typeof rel !== "string" || rel.trim() === "") {
    throw new LauncherError("a root-relative path is required", { exitCode: 2 });
  }
  if (path.isAbsolute(rel) || /^[A-Za-z]:[\\/]/.test(rel)) {
    throw new LauncherError(`${rel}: absolute paths are not allowed — give a path relative to the plugin root`, { exitCode: 2 });
  }
  const abs = path.resolve(root, rel);
  const relBack = path.relative(root, abs);
  if (relBack === "" || relBack.startsWith("..") || path.isAbsolute(relBack)) {
    throw new LauncherError(`${rel}: escapes the plugin root ${root}`, { exitCode: 2 });
  }
  if (!fs.existsSync(abs)) {
    throw new LauncherError(`${rel}: not found under the plugin root ${root}`, {
      tried: [{ path: abs, reason: "absent" }],
    });
  }
  return abs;
}

function childEnv(base, root, extra) {
  return { ...base, WICKED_GARDEN_ROOT: root, CLAUDE_PLUGIN_ROOT: root, ...extra };
}

function exec(argv, env, io) {
  // never a shell: argv[0] is a real executable (findOnPath refuses .cmd/.bat shims on Windows)
  const res = spawnSync(argv[0], argv.slice(1), { stdio: "inherit", env, shell: false, cwd: io.cwd });
  if (res.error) {
    throw new LauncherError(`failed to start ${argv[0]}: ${res.error.message}`, {
      tried: [{ argv }],
    });
  }
  if (res.status === null && res.signal) return 128 + (signalNumber(res.signal) || 1);
  return res.status ?? 1;
}

function signalNumber(name) {
  const table = { SIGHUP: 1, SIGINT: 2, SIGQUIT: 3, SIGKILL: 9, SIGTERM: 15, SIGSEGV: 11, SIGPIPE: 13 };
  return table[name];
}

function pythonOrThrow(root, env, platform) {
  const picked = pickPython(root, env, platform);
  if (picked.kind === null) {
    throw new LauncherError(
      "Python 3 not found: no <root>/.venv, no uv (with uv.lock), and none of python3 / python / py on PATH. " +
        "Install Python 3 (or uv) or run `npx wicked-garden install`; skill text: skip the script-backed step and follow the manual alternative.",
      { tried: [{ root }, ...picked.tried] },
    );
  }
  return picked;
}

export function usage() {
  return [
    "wicked-garden launcher — run the plugin's shared runtime from any skill install",
    "",
    "Usage:",
    "  wicked-garden run <root-relative path> [args…]    .py → python · .mjs/.js/.cjs → node · .sh → sh",
    "  wicked-garden python <path|-|-c code> [args…]     force the python interpreter",
    "  wicked-garden path <root-relative path>           print the absolute path under the plugin root",
    "  wicked-garden root                                print the resolved plugin root",
    "  wicked-garden doctor                              JSON: root, source, python, node, uv, tried",
    "  wicked-garden --version | --help",
    "",
    "Root: WICKED_GARDEN_ROOT (refused when it is not a garden root) → CLAUDE_PLUGIN_ROOT → this package.",
    "Python: <root>/.venv → uv run --project <root> (env under the user cache dir) → python3 → python → py -3.",
    "The launcher never writes under the root and keeps the caller's cwd.",
  ].join("\n");
}

function doctorReport(env, platform, ownRoot) {
  let resolved;
  try {
    resolved = resolveRoot(env, ownRoot);
  } catch (err) {
    if (err instanceof LauncherError) return { ok: false, reason: err.reason, tried: err.tried, node: process.version, launcher: fileURLToPath(import.meta.url) };
    throw err;
  }
  const python = pickPython(resolved.root, env, platform);
  let pythonVersion = null;
  if (python.kind !== null) {
    const res = spawnSync(python.argv[0], [...python.argv.slice(1), "--version"], {
      encoding: "utf8",
      env: childEnv(env, resolved.root, python.env),
      shell: false,
    });
    if (!res.error && res.status === 0) pythonVersion = `${res.stdout || ""}${res.stderr || ""}`.trim();
  }
  return {
    ok: python.kind !== null,
    version: resolved.version ?? null,
    root: resolved.root,
    root_source: resolved.source,
    launcher: fileURLToPath(import.meta.url),
    node: process.version,
    uv: findOnPath("uv", env, platform),
    venv: venvPythonCandidates(resolved.root, platform).some((p) => existsSync(p)),
    python: python.kind !== null
      ? { kind: python.kind, argv: python.argv, env: python.env, version: pythonVersion }
      : { kind: null, reason: "no Python 3 found (.venv / uv / python3 / python / py)" },
    tried: [...resolved.tried, ...python.tried],
  };
}

/**
 * Entry point. Returns the exit code; writes to io.stdout/io.stderr (default process streams).
 */
export function main(argv, io = {}) {
  const env = io.env ?? process.env;
  const platform = io.platform ?? process.platform;
  const ownRoot = io.ownRoot ?? ownPackageRoot();
  const out = io.stdout ?? ((s) => process.stdout.write(s));
  const err = io.stderr ?? ((s) => process.stderr.write(s));
  const cwd = io.cwd ?? process.cwd();

  try {
    const [verb, ...rest] = argv;
    if (verb === undefined || verb === "--help" || verb === "-h") {
      out(usage() + "\n");
      return verb === undefined ? 2 : 0;
    }
    if (verb === "--version" || verb === "-v") {
      const { version } = resolveRoot(env, ownRoot);
      out(`${version ?? "unknown"}\n`);
      return 0;
    }
    if (!VERBS.includes(verb)) {
      throw new LauncherError(`unknown verb: ${verb} (expected one of ${VERBS.join("|")})`, { exitCode: 2 });
    }
    if (verb === "doctor") {
      const report = doctorReport(env, platform, ownRoot);
      out(JSON.stringify(report, null, 2) + "\n");
      return report.ok ? 0 : 1;
    }
    const resolved = resolveRoot(env, ownRoot);
    const root = resolved.root;
    if (verb === "root") {
      out(root + "\n");
      return 0;
    }
    if (verb === "path") {
      if (rest.length !== 1) throw new LauncherError("usage: wicked-garden path <root-relative path>", { exitCode: 2 });
      out(resolveUnderRoot(root, rest[0]) + "\n");
      return 0;
    }
    if (verb === "python") {
      if (rest.length === 0) throw new LauncherError("usage: wicked-garden python <path|-|-c code> [args…]", { exitCode: 2 });
      const python = pythonOrThrow(root, env, platform);
      const passthrough = rest[0] === "-" || rest[0].startsWith("-");
      const target = passthrough ? [] : [resolveUnderRoot(root, rest[0])];
      const args = passthrough ? rest : rest.slice(1);
      return exec([...python.argv, ...target, ...args], childEnv(env, root, python.env), { cwd, platform });
    }
    // run
    if (rest.length === 0 || rest[0].startsWith("-")) {
      throw new LauncherError("usage: wicked-garden run <root-relative path> [args…] (run takes no options of its own)", { exitCode: 2 });
    }
    const abs = resolveUnderRoot(root, rest[0]);
    const kind = interpreterKindFor(rest[0]);
    if (kind === null) {
      throw new LauncherError(`${rest[0]}: unsupported extension (expected .py, .mjs, .js, .cjs or .sh)`, { exitCode: 2 });
    }
    if (kind === "python") {
      const python = pythonOrThrow(root, env, platform);
      return exec([...python.argv, abs, ...rest.slice(1)], childEnv(env, root, python.env), { cwd, platform });
    }
    if (kind === "node") {
      return exec([process.execPath, abs, ...rest.slice(1)], childEnv(env, root, {}), { cwd, platform });
    }
    const sh = findOnPath("sh", env, platform) || (platform === "win32" ? null : "/bin/sh");
    if (!sh) throw new LauncherError("sh not found on PATH (needed for .sh targets)", { tried: [{ kind: "sh" }] });
    return exec([sh, abs, ...rest.slice(1)], childEnv(env, root, {}), { cwd, platform });
  } catch (e) {
    if (e instanceof LauncherError) {
      err(JSON.stringify(e.toJSON()) + "\n");
      return e.exitCode;
    }
    throw e;
  }
}

function isMainModule() {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}

if (isMainModule()) {
  process.exit(main(process.argv.slice(2)));
}
