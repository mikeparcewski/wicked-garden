// Credential-shaped fixtures below are SYNTHETIC and assembled at runtime so
// secret scanners (GitGuardian) never match a committed literal.
import test from "node:test";
import assert from "node:assert/strict";
import {
  redactDeep,
  redactString,
  scanForSecrets,
  isDeniedFieldName,
  compileExtraFields,
  compileExtraPatterns,
} from "../src/redact.mjs";

test("field-name deny: auth headers and secret-shaped names", () => {
  for (const name of [
    "Authorization", "authorization", "Cookie", "Set-Cookie", "proxy-authorization",
    "x-api-key", "api_key", "apiKey", "access_token", "refreshToken", "client_secret",
    "password", "passwd", "db_password", "credentials", "session_id", "private_key",
  ]) {
    assert.ok(isDeniedFieldName(name), `${name} should be denied`);
  }
});

test("field-name deny: legit fields survive", () => {
  for (const name of ["content-type", "status", "keyboard", "monkey", "version", "url", "body", "user-agent"]) {
    assert.ok(!isDeniedFieldName(name), `${name} should NOT be denied`);
  }
});

test("redactDeep scrubs denied fields recursively without mutating input", () => {
  const input = {
    request_headers: { Authorization: "Bearer abc123def456ghi789", "Content-Type": "application/json" },
    nested: [{ set_cookie: "sid=deadbeef", ok: true }],
  };
  const out = redactDeep(input);
  assert.equal(out.request_headers.Authorization, "[REDACTED:field:Authorization]");
  assert.equal(out.request_headers["Content-Type"], "application/json");
  assert.equal(out.nested[0].set_cookie, "[REDACTED:field:set_cookie]");
  assert.equal(out.nested[0].ok, true);
  // input untouched
  assert.match(input.request_headers.Authorization, /^Bearer abc/);
});

test("value-shape scrub: bearer, jwt, github, aws, kv, pem", () => {
  const s = redactString(
    [
      `auth: Bearer ${["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiIx", "abcd1234efgh"].join(".")}`,
      `gh: ${"ghp" + "_" + "abcdefghijklmnopqrstuvwxyz012345"}`,
      "aws: AKIAIOSFODNN7EXAMPLE",
      "url: https://x?token=supersecretvalue&next=1",
      "-----BEGIN RSA PRIVATE KEY-----\nMII...\n-----END RSA PRIVATE KEY-----",
    ].join("\n"),
  );
  assert.ok(!s.includes("eyJhbGciOiJIUzI1NiJ9"), "jwt/bearer scrubbed");
  assert.ok(!s.includes("ghp" + "_" + "abcdefghijklmnopqrstuvwxyz012345"), "github token scrubbed");
  assert.ok(!s.includes("AKIAIOSFODNN7EXAMPLE"), "aws key scrubbed");
  assert.ok(!s.includes("supersecretvalue"), "kv secret scrubbed");
  assert.ok(s.includes("token=[REDACTED:kv]"), "kv keeps the key name");
  assert.ok(!s.includes("BEGIN RSA PRIVATE KEY"), "pem block scrubbed");
});

test("per-target extra fields and patterns", () => {
  const extraFields = compileExtraFields(["x-tenant-badge"]);
  const extraPatterns = compileExtraPatterns(["demo-cred-[a-z0-9]{8}"]);
  const out = redactDeep(
    { "X-Tenant-Badge": "hunter2hunter2", note: "cred is demo-cred-a1b2c3d4 ok" },
    { extraFields, extraPatterns },
  );
  assert.equal(out["X-Tenant-Badge"], "[REDACTED:field:X-Tenant-Badge]");
  assert.ok(!out.note.includes("demo-cred-a1b2c3d4"));
});

test("preflight scan finds residual secrets, reports pattern+offset only", () => {
  const text = JSON.stringify({ smuggled: "Bearer abcdef123456789012345" });
  const hits = scanForSecrets(text);
  assert.ok(hits.length >= 1);
  assert.equal(hits[0].pattern, "bearer");
  assert.equal(typeof hits[0].index, "number");
  assert.ok(!JSON.stringify(hits).includes("abcdef123456789012345"), "scan output never carries the secret");
});

test("preflight scan: clean redacted text has zero hits", () => {
  const text = JSON.stringify({
    Authorization: "[REDACTED:field:Authorization]",
    note: "token=[REDACTED:kv]",
    body: { status: "ok", version: "0.7.0" },
  });
  assert.deepEqual(scanForSecrets(text), []);
});

test("preflight scan catches a raw serialized field leak that bypassed redactDeep", () => {
  const text = '{"authorization":"Basic dXNlcjpwYXNz","x":1}';
  const hits = scanForSecrets(text);
  assert.ok(hits.some((h) => h.pattern === "serialized-field-leak" || h.pattern === "basic-auth"));
});
