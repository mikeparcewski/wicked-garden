// Part of the wicked-garden-demo skill. Playwright lives in a per-user cache directory, outside the plugin tree:
// an install inside the plugin leaves node_modules symlinks the garden installer refuses, and a garden upgrade
// would drop it. Default: <garden cache dir>/demo-deps — the launcher's per-user cache (~/.cache/wicked-garden,
// %LOCALAPPDATA%\wicked-garden\cache on Windows, or WICKED_GARDEN_CACHE_DIR). Override with WICKED_DEMO_DEPS.
// Install it once with `wicked-garden run scripts/demo/setup.mjs`.
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { cacheDir } from "../wicked-garden.mjs";

export const DEPS_DIR = path.resolve(
  process.env.WICKED_DEMO_DEPS || path.join(cacheDir(), "demo-deps"),
);

/** Playwright's chromium, loaded from DEPS_DIR on first use. */
export async function loadChromium() {
  let entry;
  try {
    entry = createRequire(path.join(DEPS_DIR, "package.json")).resolve("playwright");
  } catch {
    throw new Error(`Playwright is not installed in ${DEPS_DIR}; run: wicked-garden run scripts/demo/setup.mjs`);
  }
  const pw = await import(pathToFileURL(entry).href);
  return pw.chromium ?? pw.default.chromium;
}
