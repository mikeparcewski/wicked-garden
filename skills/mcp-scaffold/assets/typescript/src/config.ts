// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

/** The server's root: the directory holding dist/ (installed copy) or src/ (checkout). */
export const SERVER_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const AuthSchema = z.object({
  scheme: z.enum(["bearer", "api-key", "basic", "oauth2-client-credentials"]),
  header: z.string().min(1),
  user: z.string().min(1).nullable().default(null),
  tokenUrl: z.url({ protocol: /^https?$/ }).nullable(),
  scopes: z.array(z.string().min(1)),
  clientId: z.string().min(1).nullable(),
});

const ConfigSchema = z
  .object({
    key: z.string().regex(/^[a-z][a-z0-9-]{0,63}$/, "lowercase letters, digits and '-', at most 64"),
    version: z.string().min(1),
    transport: z.enum(["stdio", "httpStream"]),
    // httpStream binds loopback unless the operator says otherwise (MCP_HOST).
    host: z.string().min(1).default("127.0.0.1"),
    port: z.number().int().min(1).max(65535).default(8080),
    endpoint: z.string().startsWith("/").default("/mcp"),
    baseUrl: z.url({ protocol: /^https?$/ }),
    auth: AuthSchema,
    rateLimitPerMin: z.number().int().positive(),
  })
  .superRefine((cfg, ctx) => {
    const u = new URL(cfg.baseUrl);
    if (u.username || u.password || u.search || u.hash) {
      ctx.addIssue({ code: "custom", path: ["baseUrl"], message: "no credentials, query or fragment" });
    }
    if (cfg.auth.scheme === "basic" && cfg.auth.user === null) {
      ctx.addIssue({ code: "custom", path: ["auth", "user"], message: "basic auth needs auth.user" });
    }
    if (cfg.auth.scheme === "oauth2-client-credentials" && (cfg.auth.tokenUrl === null || cfg.auth.clientId === null)) {
      ctx.addIssue({ code: "custom", path: ["auth", "tokenUrl"], message: "oauth2 needs auth.tokenUrl and auth.clientId" });
    }
    if (cfg.auth.tokenUrl !== null) {
      const t = new URL(cfg.auth.tokenUrl);
      // The client secret is sent there: https only, except to a loopback token endpoint.
      if (t.protocol !== "https:" && !["127.0.0.1", "localhost", "[::1]"].includes(t.hostname)) {
        ctx.addIssue({ code: "custom", path: ["auth", "tokenUrl"], message: "must be https (the client secret is sent there)" });
      }
    }
  });

export type ServerConfig = z.infer<typeof ConfigSchema>;

/** `acme-notes` → `ACME_NOTES`: the prefix of every environment variable this server reads. */
export function envPrefix(key: string): string {
  return key.toUpperCase().replace(/-/g, "_");
}

/** The ONE secret variable: wicked-crew's broker and registry inject exactly one into a stdio server. */
export function secretVar(key: string): string {
  return `${envPrefix(key)}_TOKEN`;
}

function originOf(url: string): string | null {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

/**
 * Load mcp-server.config.json, apply the env overrides (MCP_TRANSPORT, MCP_HOST, MCP_PORT,
 * <SERVER>_BASE_URL, same origin only) and validate. Fails naming the field — never a value.
 */
export function loadConfig(env: NodeJS.ProcessEnv = process.env, root: string = SERVER_ROOT): ServerConfig {
  const file = join(root, "mcp-server.config.json");
  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(readFileSync(file, "utf8")) as Record<string, unknown>;
  } catch (err) {
    throw new Error(`mcp-server.config.json: cannot read ${file}: ${(err as Error).message}`, { cause: err });
  }
  const key = typeof raw.key === "string" ? raw.key : "";
  if (env.MCP_TRANSPORT) raw.transport = env.MCP_TRANSPORT;
  if (env.MCP_PORT) raw.port = Number(env.MCP_PORT);
  if (env.MCP_HOST) raw.host = env.MCP_HOST;
  const baseOverride = key ? env[`${envPrefix(key)}_BASE_URL`] : undefined;
  if (baseOverride) {
    // The upstream credential follows baseUrl, so an override may change the path but never
    // the origin: repinning egress to another host is a reviewed edit to the committed config.
    const committed = typeof raw.baseUrl === "string" ? originOf(raw.baseUrl) : null;
    if (committed === null || originOf(baseOverride) !== committed) {
      throw new Error(`${envPrefix(key)}_BASE_URL must keep the committed baseUrl origin; edit mcp-server.config.json to change the host`);
    }
    raw.baseUrl = baseOverride;
  }
  const parsed = ConfigSchema.safeParse(raw);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    const field = issue && issue.path.length > 0 ? issue.path.join(".") : "(root)";
    throw new Error(`mcp-server.config.json: invalid field "${field}": ${issue?.message ?? "invalid"}`);
  }
  return parsed.data;
}
