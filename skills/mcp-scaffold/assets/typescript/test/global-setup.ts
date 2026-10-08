// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

/** Build dist/ once before the suite: the conformance smoke speaks to the built server. */
export default function setup(): void {
  const tsc = createRequire(import.meta.url).resolve("typescript/bin/tsc");
  execFileSync(process.execPath, [tsc], { stdio: "inherit" });
}
