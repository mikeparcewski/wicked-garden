// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config.js";
import { ERROR_BODY_MAX, upstreamError } from "../src/tools/generated.js";

const BASE_VAR = "__SERVER_ENV___BASE_URL";

describe("upstream error text", () => {
  it("scrubs every credential the server sent, whole or after its scheme", () => {
    const text = upstreamError(401, "bad header: Bearer tok-1234 (tok-1234)", { Authorization: "Bearer tok-1234" });
    expect(text).toBe("HTTP 401: bad header: [redacted] ([redacted])");
  });

  it("bounds the body a caller sees", () => {
    const text = upstreamError(500, "x".repeat(ERROR_BODY_MAX * 3), {});
    expect(text.length).toBeLessThan(ERROR_BODY_MAX + 40);
    expect(text).toContain("(truncated)");
  });
});

describe("base URL override", () => {
  const committed = new URL(loadConfig({}).baseUrl);

  it("may move the path on the committed origin", () => {
    const moved = `${committed.origin}/v2`;
    expect(loadConfig({ [BASE_VAR]: moved }).baseUrl).toBe(moved);
  });

  it("refuses another origin: the credential would follow it", () => {
    expect(() => loadConfig({ [BASE_VAR]: "https://elsewhere.invalid/v1" })).toThrow(/committed baseUrl origin/);
  });
});
