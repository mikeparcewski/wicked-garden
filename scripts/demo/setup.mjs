#!/usr/bin/env node
// Installs the demo skill's Playwright (pinned by package-lock.json here) and its Chromium into the per-user cache
// directory, outside the plugin tree (see _playwright.mjs). Run once per machine, and again after a garden upgrade
// changes the pin:
//
//   wicked-garden run scripts/demo/setup.mjs
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { DEPS_DIR } from "./_playwright.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
fs.mkdirSync(DEPS_DIR, { recursive: true });
for (const f of ["package.json", "package-lock.json"]) fs.copyFileSync(path.join(here, f), path.join(DEPS_DIR, f));

const run = (cmd, args) => {
  console.log(`$ ${cmd} ${args.join(" ")}   (in ${DEPS_DIR})`);
  const r = spawnSync(cmd, args, { cwd: DEPS_DIR, stdio: "inherit", shell: process.platform === "win32" });
  if (r.error || r.status !== 0) {
    console.error(`error: ${cmd} failed${r.error ? `: ${r.error.message}` : ` (exit ${r.status})`}`);
    process.exit(1);
  }
};
run("npm", ["ci", "--no-audit", "--no-fund"]);
run("npx", ["playwright", "install", "chromium"]);
console.log(`Playwright ready in ${DEPS_DIR}`);
