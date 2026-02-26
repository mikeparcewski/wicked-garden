/**
 * TypeScript type definitions for the wicked-observability data API.
 *
 * All responses follow the GatewayResponse<T> envelope defined in
 * wicked-workbench. These types mirror the Python data models defined in:
 *   plugins/wicked-observability/scripts/api.py
 *
 * Usage via wicked-workbench data gateway:
 *   const res = await fetch('/api/v1/data/wicked-observability/traces/list');
 *   const body: TraceListResponse = await res.json();
 *   const traces = body.data;
 *   const plugin = body.meta.plugin;  // "wicked-observability"
 *
 * @see plugins/wicked-observability/scripts/api.py
 * @see plugins/wicked-workbench/types.d.ts
 */

// ---------------------------------------------------------------------------
// Gateway response envelope (re-exported for consumers of this plugin)
// ---------------------------------------------------------------------------

/**
 * Metadata block added by the gateway to every proxied plugin response.
 *
 * Fields inherited from the plugin's own meta are preserved and extended
 * with gateway-level routing information (plugin, verb, item_id).
 */
export interface ResponseMeta {
  /** Total number of matching items reported by the underlying plugin. Absent for single-item gets. */
  total?: number | null;
  /** Page size used for this request. Absent for single-item gets. */
  limit?: number | null;
  /** Zero-based page offset used for this request. Absent for single-item gets. */
  offset?: number | null;
  /** Data source name within the plugin (e.g. "traces", "assertions", "health"). */
  source: string;
  /** Plugin name that handled this request (always "wicked-observability"). */
  plugin: string;
  /** ISO-8601 UTC timestamp from the plugin response. */
  timestamp?: string;
  /** Read verb used for this request (e.g. "list", "search", "stats", "get"). */
  verb?: string | null;
  /** Item ID used for get requests. */
  item_id?: string | null;
}

/**
 * Standard response envelope returned by all wicked-observability data endpoints.
 *
 * Every successful GET to /api/v1/data/wicked-observability/{source}/{verb} returns this shape.
 *
 * @template T - The plugin-specific data payload type (array or object).
 *
 * @example
 * import type { GatewayResponse } from 'wicked-workbench/types';
 * import type { TraceRecord } from 'wicked-observability/types';
 *
 * const res = await fetch('/api/v1/data/wicked-observability/traces/list');
 * const body: GatewayResponse<TraceRecord[]> = await res.json();
 */
export interface GatewayResponse<T> {
  /** Plugin-specific payload — shape depends on the requested source and verb. */
  data: T;
  /** Gateway metadata envelope with routing and pagination information. */
  meta: ResponseMeta;
}

// ---------------------------------------------------------------------------
// Trace records
// ---------------------------------------------------------------------------

/**
 * A single trace record emitted by a hook invocation or tool use event.
 *
 * Returned by: traces/list, traces/search, traces/get
 */
export interface TraceRecord {
  /** Schema version of this record format (e.g. "1.0"). */
  schema_version: string;
  /** ISO-8601 UTC timestamp of when the event occurred. */
  ts: string;
  /** Unique identifier for the Claude Code session that produced this event. */
  session_id: string;
  /** Monotonically increasing sequence number within the session. */
  seq: number;
  /** Discriminator: whether this record describes a hook invocation or a tool use. */
  event_type: 'hook_invocation' | 'tool_use';
  /** Name of the tool or hook script that was invoked. */
  tool_name: string;
  /** Wall-clock execution time in milliseconds; null when timing was unavailable. */
  duration_ms: number | null;
  /** Process exit code; null when not applicable (e.g. async hooks). */
  exit_code: number | null;
  /** Captured stderr output from the hook or tool process. */
  stderr: string;
  /**
   * True when the hook or tool exited with a non-zero code but the failure
   * was swallowed rather than surfaced to the user.
   */
  silent_failure: boolean;
  /** Plugin that owns the hook script; null for tool_use events. */
  hook_plugin: string | null;
  /** Relative path to the hook script within the plugin; null for tool_use events. */
  hook_script: string | null;
  /** Claude Code hook event name (e.g. "PreToolUse"); null for tool_use events. */
  hook_event: string | null;
  /** First 120 characters of the shell command for Bash tool events; null otherwise. */
  command_summary: string | null;
}

// ---------------------------------------------------------------------------
// Assertion records
// ---------------------------------------------------------------------------

/**
 * A single field-level assertion violation found during a contract check.
 *
 * Returned as part of AssertionRecord.violations.
 */
export interface AssertionViolation {
  /** Name of the field or property that failed validation. */
  field: string;
  /** Human-readable description of the violation. */
  message: string;
  /** Description of what value or shape was expected. */
  expected: string;
  /** Description of what value or shape was actually observed. */
  actual: string;
}

/**
 * A single assertion run result for one plugin script contract check.
 *
 * Returned by: assertions/list, assertions/search
 */
export interface AssertionRecord {
  /** ISO-8601 UTC timestamp of when the assertion was evaluated. */
  ts: string;
  /** Plugin whose script was under assertion (e.g. "wicked-mem"). */
  plugin: string;
  /** Relative path to the script within the plugin that was checked. */
  script: string;
  /**
   * Outcome of the assertion run:
   *   pass      — all contracts satisfied
   *   timeout   — script did not respond within the deadline
   *   empty     — script returned no output
   *   malformed — output could not be parsed as expected JSON
   */
  result: 'pass' | 'timeout' | 'empty' | 'malformed';
  /** Individual field violations found; empty array when result is "pass". */
  violations: AssertionViolation[];
  /** Wall-clock time spent running the assertion in milliseconds. */
  duration_ms: number;
}

// ---------------------------------------------------------------------------
// Health probe
// ---------------------------------------------------------------------------

/**
 * A single health violation found while probing an installed plugin.
 *
 * Returned as part of HealthResponse.violations.
 */
export interface HealthViolation {
  /** Plugin in which the violation was detected. */
  plugin: string;
  /**
   * Machine-readable violation category:
   *   invalid_event     — hooks.json references an unknown Claude Code event
   *   missing_script    — hooks.json or plugin.json points to a script that does not exist
   *   ghost_reference   — an agent or command references a plugin/agent that is not installed
   *   ghost_specialist  — specialist.json references a role or signal that is not registered
   *   missing_field     — a required field is absent from plugin.json or specialist.json
   */
  type: 'invalid_event' | 'missing_script' | 'ghost_reference' | 'ghost_specialist' | 'missing_field';
  /** Severity level of the violation. */
  severity: 'error' | 'warning';
  /** Human-readable description of what is wrong and where. */
  message: string;
  /** Path to the file in which the violation was detected. */
  file: string;
  /** Line number within file where the issue was found; null when not applicable. */
  line: number | null;
}

/**
 * Aggregate counts for a health probe run.
 *
 * Returned as part of HealthResponse.summary.
 */
export interface HealthSummary {
  /** Total number of error-severity violations across all plugins. */
  errors: number;
  /** Total number of warning-severity violations across all plugins. */
  warnings: number;
  /** Number of plugins with zero violations. */
  plugins_healthy: number;
  /** Number of plugins with warnings but no errors. */
  plugins_degraded: number;
  /** Number of plugins with at least one error-severity violation. */
  plugins_unhealthy: number;
}

/**
 * Per-plugin health record returned by the data gateway.
 *
 * The API normalizes the raw health_probe.py report into per-plugin records.
 * Special IDs: "_summary" for the overall report, "_healthy_plugins" for
 * the aggregate healthy count.
 *
 * Returned by: health/list, health/get
 */
export interface HealthResponse {
  /** Plugin identifier (e.g. "wicked-kanban") or meta-ID ("_summary", "_healthy_plugins"). */
  id: string;
  /** Plugin health status. */
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  /** ISO-8601 UTC timestamp of when the probe was executed. */
  checked_at: string;
  /** Violations for this plugin; empty array when healthy. */
  violations?: HealthViolation[];
  /** Only present on _summary: total plugins probed. */
  plugins_checked?: number;
  /** Only present on _summary: aggregated counts. */
  summary?: HealthSummary;
  /** Only present on _healthy_plugins: count of clean plugins. */
  count?: number;
}

// ---------------------------------------------------------------------------
// traces/stats data shape
// ---------------------------------------------------------------------------

/**
 * Aggregate statistics derived from the trace log.
 *
 * Returned by: traces/stats
 */
export interface TraceStatsData {
  /** Total number of trace records in the store. */
  total: number;
  /** Counts keyed by event_type (e.g. { "hook_invocation": 120, "tool_use": 340 }). */
  by_event_type: Record<string, number>;
  /** Counts keyed by tool_name (e.g. { "Bash": 100, "Read": 50 }). */
  by_tool_name: Record<string, number>;
  /** Total number of records where silent_failure is true. */
  silent_failures: number;
  /** Total hook invocation records. */
  hook_invocations: number;
  /** Counts keyed by hook_plugin (e.g. { "wicked-mem": 45, "wicked-kanban": 20 }). */
  by_hook_plugin: Record<string, number>;
}

// ---------------------------------------------------------------------------
// assertions/stats data shape
// ---------------------------------------------------------------------------

/**
 * NOTE: assertions/stats endpoint is not yet implemented.
 * When added, this type will be used. Currently assertions only
 * supports list and search verbs.
 */
export interface AssertionStatsData {
  /** Total number of assertion records in the store. */
  total_assertions: number;
  /** Counts keyed by result value (e.g. { "pass": 200, "timeout": 3, "malformed": 1 }). */
  by_result: Record<string, number>;
  /** Counts keyed by plugin name (e.g. { "wicked-mem": 50, "wicked-search": 30 }). */
  by_plugin: Record<string, number>;
  /** Mean duration_ms across all assertion records. */
  avg_duration_ms: number;
}

// ---------------------------------------------------------------------------
// health/stats data shape
// ---------------------------------------------------------------------------

/**
 * Aggregate statistics from the latest health probe.
 *
 * Returned by: health/stats
 */
export interface HealthStatsData {
  /** Total number of plugins reflected in the stats (healthy + degraded + unhealthy + unknown). */
  total_plugins: number;
  /** Counts keyed by status string (e.g. { "healthy": 15, "unhealthy": 1, "degraded": 2 }). */
  by_status: Record<string, number>;
  /** Number of plugins with no violations. */
  healthy: number;
  /** Number of plugins with warnings but no errors. */
  degraded: number;
  /** Number of plugins with at least one error-severity violation. */
  unhealthy: number;
  /** Number of plugins with unrecognised status. */
  unknown: number;
  /** Overall ecosystem status from the probe. */
  overall_status?: string;
  /** Total plugins the probe checked (from probe summary). */
  plugins_checked?: number;
  /** Raw probe summary object with error/warning counts. */
  probe_summary?: HealthSummary;
}

// ---------------------------------------------------------------------------
// Named type aliases for each endpoint
// ---------------------------------------------------------------------------

/** Response from traces/list — paginated array of trace records. */
export type TraceListResponse = GatewayResponse<TraceRecord[]>;

/** Response from traces/search — filtered array of trace records. */
export type TraceSearchResponse = GatewayResponse<TraceRecord[]>;

/** Response from traces/stats — aggregate statistics for the trace log. */
export type TraceStatsResponse = GatewayResponse<TraceStatsData>;

/** Response from assertions/list — paginated array of assertion records. */
export type AssertionListResponse = GatewayResponse<AssertionRecord[]>;

/** Response from assertions/search — filtered array of assertion records. */
export type AssertionSearchResponse = GatewayResponse<AssertionRecord[]>;

/** Response from health/list — paginated array of health probe results. */
export type HealthListResponse = GatewayResponse<HealthResponse[]>;

/** Response from health/get — single most-recent health probe result. */
export type HealthGetResponse = GatewayResponse<HealthResponse>;

/** Response from health/stats — aggregate statistics from health probe history. */
export type HealthStatsResponse = GatewayResponse<HealthStatsData>;
