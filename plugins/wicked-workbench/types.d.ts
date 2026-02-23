/**
 * TypeScript type definitions for the wicked-workbench data gateway API.
 *
 * The gateway wraps every plugin's data API response in the GatewayResponse<T>
 * envelope before forwarding it to clients. These types mirror the Pydantic
 * models defined in:
 *   plugins/wicked-workbench/server/src/wicked_workbench_server/data_gateway/models.py
 *
 * Usage:
 *   const res = await fetch('/api/v1/data/wicked-search/graph/stats');
 *   const body: GatewayResponse<GraphStatsData> = await res.json();
 *   const total = body.data.total_symbols;
 *   const plugin = body.meta.plugin;  // "wicked-search"
 *
 * @see plugins/wicked-workbench/server/src/wicked_workbench_server/data_gateway/router.py
 */

// ---------------------------------------------------------------------------
// Gateway response envelope
// ---------------------------------------------------------------------------

/**
 * Metadata block added by the gateway to every proxied plugin response.
 *
 * Fields inherited from the plugin's own meta are preserved and extended
 * with gateway-level routing information (plugin, verb, item_id).
 */
export interface ResponseMeta {
  /** Total number of matching items reported by the underlying plugin. */
  total: number | null;
  /** Page size used for this request. */
  limit: number | null;
  /** Zero-based page offset used for this request. */
  offset: number | null;
  /** Data source name within the plugin (e.g. "graph", "symbols", "lineage"). */
  source: string;
  /** Plugin name that handled this request (e.g. "wicked-search"). */
  plugin: string;
  /** ISO-8601 UTC timestamp from the plugin response. */
  timestamp: string;
  /** Read verb used for this request (e.g. "list", "search", "stats", "traverse"). */
  verb?: string | null;
  /** Item ID used for get/traverse/impact/content requests. */
  item_id?: string | null;
}

/**
 * Standard response envelope returned by all wicked-workbench data gateway endpoints.
 *
 * Every successful GET to /api/v1/data/{plugin}/{source}/{verb} returns this shape.
 *
 * @template T - The plugin-specific data payload type (array or object).
 *
 * @example
 * import type { GatewayResponse } from 'wicked-workbench/types';
 * import type { GraphStatsData } from 'wicked-search/types';
 *
 * const res = await fetch('/api/v1/data/wicked-search/graph/stats');
 * const body: GatewayResponse<GraphStatsData> = await res.json();
 */
export interface GatewayResponse<T> {
  /** Plugin-specific payload — shape depends on the requested source and verb. */
  data: T;
  /** Gateway metadata envelope with routing and pagination information. */
  meta: ResponseMeta;
}

// ---------------------------------------------------------------------------
// Error response
// ---------------------------------------------------------------------------

/**
 * Error response returned by the gateway when a request fails.
 *
 * HTTP status codes:
 *   400 — invalid verb, missing ID, capability not supported
 *   404 — plugin or source not found
 *   504 — plugin API subprocess timed out (10 s)
 *   500 — unexpected gateway error
 */
export interface GatewayError {
  error: string;
  /** Machine-readable error code (e.g. "PLUGIN_NOT_FOUND", "MISSING_ID", "TIMEOUT"). */
  code: string;
  /** Additional context about the error. */
  details?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Plugin discovery
// ---------------------------------------------------------------------------

/** A data source exposed by a plugin. */
export interface PluginDataSource {
  name: string;
  description: string;
  /** Available verbs for this source (e.g. ["list", "search", "stats"]). */
  capabilities: string[];
}

/** A plugin registered in the gateway's discovery registry. */
export interface PluginInfo {
  name: string;
  schema_version: string;
  sources: PluginDataSource[];
}

/** Response from GET /api/v1/data/plugins. */
export interface PluginsListResponse {
  plugins: PluginInfo[];
  meta: {
    total_plugins: number;
    total_sources: number;
    schema_version: string;
  };
}

/** Response from GET /api/v1/data/plugins/{plugin}. */
export interface PluginDetailResponse {
  plugin: string;
  schema_version: string;
  sources: PluginDataSource[];
}

// ---------------------------------------------------------------------------
// Write operation responses
// ---------------------------------------------------------------------------

/** Response shape for POST /api/v1/data/{plugin}/{source}/create. */
export type CreateResponse<T = Record<string, unknown>> = GatewayResponse<T>;

/** Response shape for PUT /api/v1/data/{plugin}/{source}/update/{id}. */
export type UpdateResponse<T = Record<string, unknown>> = GatewayResponse<T>;

/** Response shape for DELETE /api/v1/data/{plugin}/{source}/delete/{id}. */
export type DeleteResponse<T = Record<string, unknown>> = GatewayResponse<T>;
