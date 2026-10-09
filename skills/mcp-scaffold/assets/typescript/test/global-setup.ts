// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

/**
 * Build dist/ once before the suite: the conformance smoke speaks to the built server.
 * The compiler is TypeScript 7, installed as `@typescript/native`; `typescript` is aliased to the
 * TS 6 API package because typescript-eslint does not support TS 7 yet. TS 7 does not export
 * `./bin/tsc`, so the bin is resolved through its manifest.
 */
export default function setup(): void {
  const require = createRequire(import.meta.url);
  const manifest = require.resolve("@typescript/native/package.json");
  const { bin } = require(manifest) as { bin: { tsc: string } };
  execFileSync(process.execPath, [join(dirname(manifest), bin.tsc)], { stdio: "inherit" });
}
