// sync-plugin-version.mjs — make the plugin manifests match package.json's version.
// Runs as the npm `version` lifecycle hook, so `npm version <x>` (including the one the
// shared release workflow runs from the tag) bumps every anchor at once:
//   package.json  +  .claude-plugin/plugin.json  +  .claude-plugin/marketplace.json
//                 +  .codex-plugin/plugin.json (the Codex plugin manifest)
//                 +  .claude-plugin/release-marketplace.json (the published catalog)
// The published catalog's entry installs the release TAG (#1413): its github source's `"ref"`
// moves with the version (`v<version>`), so a Claude Code user who adds that catalog by URL gets
// exactly what npm ships under that version. marketplace.json keeps `"./"` (a local add installs
// the checkout it names) and only its version keys move.
// marketplace.json carries TWO version fields (plugins[0].version and a top-level version),
// and plugin.json also carries peer-version keys (wicked_testing_version, …) that must NOT
// move — so we replace only the exact `"version":` key, format-preserving, never the peers.
import { readFileSync, writeFileSync } from "node:fs";

const version = JSON.parse(readFileSync("package.json", "utf8")).version;

function bump(path, { tag = false } = {}) {
  const before = readFileSync(path, "utf8");
  // `"version"` (quote-delimited key) never matches inside `"wicked_*_version"`, whose
  // char before `version` is `_`, not `"` — so peer versions are left untouched.
  let after = before.replace(/("version"\s*:\s*)"[^"]*"/g, `$1"${version}"`);
  if (tag) after = after.replace(/("ref"\s*:\s*)"v[^"]*"/g, `$1"v${version}"`);
  writeFileSync(path, after);
  console.log(`  ${path} -> ${version}`);
}

console.log(`Syncing plugin manifests to ${version}`);
bump(".claude-plugin/plugin.json");
bump(".claude-plugin/marketplace.json");
bump(".claude-plugin/release-marketplace.json", { tag: true });
bump(".codex-plugin/plugin.json");
