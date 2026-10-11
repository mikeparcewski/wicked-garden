/**
 * The ONE wicked-ledger resolver of garden's QE pipeline (accept, the gate, the campaign
 * scoreboard). wicked-ledger is resolved for the TARGET repo — the plugin ships no node_modules —
 * in this order:
 *
 *   1. `$WICKED_LEDGER_PKG_DIR` — an explicit package dir. wicked-crew exports its OWN bundled
 *      wicked-ledger here (wicked-crew#951), so a governed run's QE unit records its verdict with
 *      the very package crew's acceptance check reads it with, and needs no install in the
 *      worktree (a fenced governed seat cannot `npm i`, and an install would change the tree).
 *      Set but unusable ⇒ `null` (an explicit pin never falls back to a different package).
 *   2. a bare `import("wicked-ledger")` (a global / hoisted install);
 *   3. a walk up from the target repo for `node_modules/wicked-ledger`.
 *
 * `null` when none resolves; callers say so (never a silent no-op).
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

export const LEDGER_PKG_ENV = "WICKED_LEDGER_PKG_DIR";

/** The ESM entry file of a package dir (its `exports["."]` import/default, else module/main). */
export function esmEntryForPackageDir(pkgDir) {
  const pj = join(pkgDir, "package.json");
  if (!existsSync(pj)) return null;
  let pkg;
  try {
    pkg = JSON.parse(readFileSync(pj, "utf8"));
  } catch {
    return null;
  }
  const dot = pkg.exports && pkg.exports["."] !== undefined ? pkg.exports["."] : pkg.exports;
  const rel =
    (dot && typeof dot === "object" && (dot.import || dot.default)) ||
    (typeof dot === "string" ? dot : null) ||
    pkg.module ||
    pkg.main ||
    "index.js";
  return join(pkgDir, rel);
}

/** The resolved wicked-ledger module for `repoRoot`, or `null`. */
export async function resolveLedgerModule(repoRoot = process.cwd(), env = process.env) {
  const pinned = env[LEDGER_PKG_ENV]?.trim();
  if (pinned) {
    const entry = esmEntryForPackageDir(pinned);
    if (!entry || !existsSync(entry)) return null;
    try {
      return await import(pathToFileURL(entry).href);
    } catch {
      return null;
    }
  }
  try {
    return await import("wicked-ledger");
  } catch {
    /* fall through */
  }
  let dir = resolve(repoRoot);
  for (let i = 0; i < 10; i++) {
    const entry = esmEntryForPackageDir(join(dir, "node_modules", "wicked-ledger"));
    if (entry && existsSync(entry)) {
      try {
        return await import(pathToFileURL(entry).href);
      } catch {
        return null;
      }
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}
