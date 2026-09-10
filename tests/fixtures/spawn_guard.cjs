// Preload (`node --require tests/fixtures/spawn_guard.cjs install.mjs …`) that intercepts
// EVERY child-process entry point: each attempt is appended to $SPAWN_GUARD_LOG (one name
// per line, so a test can count them) and then throws. A code path that spawns nothing
// leaves the log file absent. install.mjs imports `execSync` as an ESM named import of the
// builtin; those bindings are snapshots, so after patching module.exports we must
// syncBuiltinESMExports() for the ESM side to see the patched functions.
"use strict";
const cp = require("node:child_process");
const fs = require("node:fs");
const log = process.env.SPAWN_GUARD_LOG;
for (const name of ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"]) {
  cp[name] = function spawnGuard() {
    if (log) fs.appendFileSync(log, `${name}\n`);
    throw new Error(`spawn-guard: child_process.${name} called`);
  };
}
require("node:module").syncBuiltinESMExports();
