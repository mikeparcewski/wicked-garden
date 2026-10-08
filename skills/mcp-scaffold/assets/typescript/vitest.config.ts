// SPDX-License-Identifier: MIT
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    // The conformance smoke runs the BUILT server (dist/server.js), so the suite builds first.
    globalSetup: ["test/global-setup.ts"],
    testTimeout: 90_000,
  },
});
