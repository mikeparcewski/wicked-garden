/**
 * TypeScript type definitions for the wicked-search API responses.
 *
 * All responses follow the ApiResponse<T> envelope:
 *   { data: T, meta: ApiMeta }
 *
 * Usage via wicked-workbench data gateway:
 *   GET /api/v1/data/wicked-search/{source}/{verb}
 *
 * @see plugins/wicked-search/scripts/api.py
 * @see plugins/wicked-search/wicked.json
 */

// ---------------------------------------------------------------------------
// Standard envelope
// ---------------------------------------------------------------------------

/** Metadata block present on every wicked-search API response. */
export interface ApiMeta {
  /** Total number of matching items (may be approximate for large datasets). */
  total: number;
  /** Page size used for this request. */
  limit: number;
  /** Zero-based offset used for this request. */
  offset: number;
  /** Data source name (e.g. "graph", "symbols", "lineage"). */
  source: string;
  /** ISO-8601 UTC timestamp of when the response was generated. */
  timestamp: string;
  /** Optional warning message (e.g. outdated schema version). */
  warning?: string;
  /** Optional project name when --project was supplied. */
  project?: string;
}

/** Traverse-specific metadata — extends ApiMeta with graph traversal fields. */
export interface TraverseMeta {
  source: "graph";
  node_count: number;
  edge_count: number;
  /** Requested traversal depth. */
  depth: number;
  /** Actual maximum depth reached during traversal. */
  depth_reached: number;
  /** True when nodes at the depth boundary had unvisited neighbours. */
  truncated: boolean;
  /** Direction used: "both" | "in" | "out". */
  direction: "both" | "in" | "out";
}

/**
 * Generic API response envelope.
 * All wicked-search endpoints return this shape (except traverse which uses TraverseMeta).
 */
export interface ApiResponse<T> {
  data: T;
  meta: ApiMeta;
}

// ---------------------------------------------------------------------------
// Shared symbol shape
// ---------------------------------------------------------------------------

/**
 * A code or document symbol as stored in the unified.db symbols table.
 *
 * Returned by: graph/list, graph/get, graph/search, symbols/list,
 *              symbols/search, hotspots/graph, traverse nodes/root.
 */
export interface SymbolItem {
  /** Fully-qualified unique identifier: e.g. "src/api.py::MyClass.method". */
  id: string;
  /** Short symbol name: e.g. "method". */
  name: string;
  /**
   * Symbol kind: CLASS | METHOD | FUNCTION | INTERFACE | STRUCT |
   * ENUM | TRAIT | TYPE | IMPORT | FILE | DOC_SECTION | DOC_PAGE | unknown
   */
  type: string;
  /** Dotted qualified name including enclosing types/modules. */
  qualified_name: string;
  /** Absolute path to the source file. */
  file_path: string;
  line_start: number | null;
  line_end: number | null;
  /** Data domain: "code" or "doc". */
  domain: string;
  /** Architectural layer: "backend" | "frontend" | "database" | "view" | "unknown". */
  layer: string;
  /** Directory-level category (e.g. "portlets", "api", "service"). */
  category: string;
  /** Docstring or document section text; null when unavailable. */
  content: string | null;
  /** Free-form extensible metadata attached during indexing. */
  metadata: Record<string, unknown>;
}

/** SymbolItem returned from search endpoints — includes match provenance. */
export interface SymbolSearchItem extends SymbolItem {
  /** Relevance score: 100 = exact, 75 = prefix, 50–100 = FTS/qualified. */
  score: number;
  /** Tier that produced the match: "exact" | "prefix" | "fts" | "qualified_name". */
  match_type: "exact" | "prefix" | "fts" | "qualified_name";
}

// ---------------------------------------------------------------------------
// graph/stats
// ---------------------------------------------------------------------------

/** Response data for `stats graph`. */
export interface GraphStatsData {
  total_symbols: number;
  total_refs: number;
  /** Symbol counts keyed by type name (e.g. { "CLASS": 120, "METHOD": 450 }). */
  by_type: Record<string, number>;
  /** Reference counts keyed by ref_type (e.g. { "calls": 800, "imports": 200 }). */
  by_ref_type: Record<string, number>;
  /** Number of SQLite database files backing the index. */
  db_files: number;
}

export type GraphStatsResponse = ApiResponse<GraphStatsData>;

// ---------------------------------------------------------------------------
// graph/list and graph/search
// ---------------------------------------------------------------------------

export type GraphListResponse = ApiResponse<SymbolItem[]>;
export type GraphSearchResponse = ApiResponse<SymbolSearchItem[]>;

// ---------------------------------------------------------------------------
// graph/get (single symbol with dependencies/dependents)
// ---------------------------------------------------------------------------

/** A dependency or dependent reference attached to a graph/get result. */
export interface SymbolRef {
  /** Target symbol ID (for dependencies) or source symbol ID (for dependents). */
  target_id?: string;
  source_id?: string;
  ref_type: string;
  confidence: string | null;
}

/** Response data for `get graph <id>` — a symbol with its references. */
export interface GraphGetData extends SymbolItem {
  dependencies: SymbolRef[];
  dependents: SymbolRef[];
}

export type GraphGetResponse = ApiResponse<GraphGetData>;

// ---------------------------------------------------------------------------
// graph/traverse
// ---------------------------------------------------------------------------

/** A directed edge in the traversal result. */
export interface TraverseEdge {
  source_id: string;
  target_id: string;
  /** Reference type: "calls" | "imports" | "extends" | "implements" | "maps_to" | etc. */
  ref_type: string;
  /** Always 0 in current implementation (legacy compatibility field). */
  line: number;
}

/** Response data for `traverse graph <id>`. */
export interface TraverseData {
  /** The starting symbol for this traversal. */
  root: SymbolItem;
  /** All symbols reachable within the requested depth (includes root). */
  nodes: SymbolItem[];
  /** All edges observed during traversal. */
  edges: TraverseEdge[];
  /** Actual maximum depth reached (may be less than requested). */
  depth_reached: number;
  /** True when nodes at the depth boundary had unvisited neighbours. */
  truncated: boolean;
}

/** Full traverse response including graph-specific metadata. */
export interface TraverseResponse {
  data: TraverseData;
  meta: TraverseMeta;
}

// ---------------------------------------------------------------------------
// graph/hotspots
// ---------------------------------------------------------------------------

/** A hotspot symbol with connectivity counts. */
export interface HotspotItem extends SymbolItem {
  /** Number of incoming references (this symbol is a target). */
  in_count: number;
  /** Number of outgoing references (this symbol is a source). */
  out_count: number;
  /** in_count + out_count. */
  total_count: number;
}

export type HotspotsResponse = ApiResponse<HotspotItem[]>;

// ---------------------------------------------------------------------------
// graph/impact
// ---------------------------------------------------------------------------

/** A UI field affected by a database column change. */
export interface AffectedField {
  /** Symbol ID of the affected UI field. */
  ui_field_id: string;
  /** Dotted path of the field in the UI layer. */
  field_path: string;
  /** Source file containing the UI binding (e.g. JSP path). */
  jsp_file: string;
}

/** Response data for `impact graph <table.column>`. */
export interface ImpactData {
  table: string;
  column: string;
  total_affected: number;
  affected_fields: AffectedField[];
}

export type ImpactResponse = ApiResponse<ImpactData>;

// ---------------------------------------------------------------------------
// symbols/list, symbols/get, and symbols/search
// ---------------------------------------------------------------------------

export type SymbolsListResponse = ApiResponse<SymbolItem[]>;
export type SymbolsGetResponse = ApiResponse<SymbolItem>;
export type SymbolsSearchResponse = ApiResponse<SymbolSearchItem[]>;

// ---------------------------------------------------------------------------
// documents/list and documents/search
// ---------------------------------------------------------------------------

export type DocumentsListResponse = ApiResponse<SymbolItem[]>;
export type DocumentsSearchResponse = ApiResponse<SymbolSearchItem[]>;

// ---------------------------------------------------------------------------
// references/list and references/search
// ---------------------------------------------------------------------------

/** A symbol reference record (from symbol_refs table). */
export interface ReferenceItem {
  source_id: string;
  target_id: string;
  ref_type: string;
}

export type ReferencesListResponse = ApiResponse<ReferenceItem[]>;
export type ReferencesSearchResponse = ApiResponse<ReferenceItem[]>;

// ---------------------------------------------------------------------------
// symbols/stats
// ---------------------------------------------------------------------------

export interface SymbolsStatsData {
  total_symbols: number;
  by_type: Record<string, number>;
  by_layer: Record<string, number>;
}

export type SymbolsStatsResponse = ApiResponse<SymbolsStatsData>;

// ---------------------------------------------------------------------------
// symbols/categories
// ---------------------------------------------------------------------------

export interface TypeCount {
  type: string;
  count: number;
}

export interface LayerCount {
  layer: string;
  symbol_count: number;
}

export interface DirectoryCategory {
  category: string;
  symbol_count: number;
}

export interface CategoryRelationship {
  source: string;
  target: string;
  ref_type: string;
  count: number;
}

export interface SymbolsCategoriesData {
  by_type: TypeCount[];
  by_layer: LayerCount[];
  by_directory: DirectoryCategory[];
  relationships: {
    by_directory: CategoryRelationship[];
    by_layer: CategoryRelationship[];
  };
}

export type SymbolsCategoriesResponse = ApiResponse<SymbolsCategoriesData>;

// ---------------------------------------------------------------------------
// lineage/list and lineage/search
// ---------------------------------------------------------------------------

/** Source or sink endpoint of a lineage path. */
export interface LineageSide {
  name: string;
  qualified_name: string;
  /** Architectural layer of this endpoint. */
  layer: string;
}

/**
 * A single lineage path record connecting a data source to a data sink.
 *
 * Returned by: lineage/list, lineage/search
 */
export interface LineageRecord {
  id: string;
  source_id: string;
  sink_id: string;
  /** Number of hops from source to sink. */
  path_length: number;
  /** Minimum confidence level along the path: "high" | "medium" | "low". */
  min_confidence: string | null;
  /** True when the complete path from source to sink was resolved. */
  is_complete: boolean;
  source: LineageSide;
  sink: LineageSide;
}

export type LineageListResponse = ApiResponse<LineageRecord[]>;
export type LineageSearchResponse = ApiResponse<LineageRecord[]>;

// ---------------------------------------------------------------------------
// code/content
// ---------------------------------------------------------------------------

/**
 * Response data for `content code <file_path>`.
 *
 * Reads source file content, optionally restricted to a line range.
 * Supports --line-start and --line-end query parameters.
 *
 * Issue #60 — endpoint available via:
 *   GET /api/v1/data/wicked-search/code/content/{file_path}
 *                                   ?line_start=N&line_end=M
 */
export interface CodeContentData {
  /** Original path as supplied to the request. */
  path: string;
  /** Full text content of the requested line range. */
  content: string;
  /** First line returned (1-based, inclusive). */
  line_start: number;
  /** Last line returned (1-based, inclusive). */
  line_end: number;
  /**
   * Inferred programming language from file extension.
   * e.g. "python" | "typescript" | "java" | "javascript" | "text"
   */
  language: string;
}

export type CodeContentResponse = ApiResponse<CodeContentData>;

// ---------------------------------------------------------------------------
// code/ide-url
// ---------------------------------------------------------------------------

export interface IdeUrlData {
  /** Deep-link URL for the requested IDE (e.g. "vscode://file/path/to/file.py:42"). */
  url: string;
}

export type IdeUrlResponse = ApiResponse<IdeUrlData>;

// ---------------------------------------------------------------------------
// services/list and services/stats
// ---------------------------------------------------------------------------

export interface ServiceNode {
  id: string;
  name: string;
  type: string;
  metadata: Record<string, unknown>;
  outgoing_connections: number;
  incoming_connections: number;
}

export type ServicesListResponse = ApiResponse<ServiceNode[]>;

export interface ServicesStatsData {
  total_services: number;
  total_connections: number;
  by_type: Record<string, number>;
  by_technology: Record<string, number>;
}

export type ServicesStatsResponse = ApiResponse<ServicesStatsData>;

// ---------------------------------------------------------------------------
// projects/list
// ---------------------------------------------------------------------------

export interface ProjectItem {
  name: string;
  symbol_count: number;
  file_count: number;
  /** ISO-8601 UTC timestamp of last index run. */
  last_indexed: string;
}

export type ProjectsListResponse = ApiResponse<ProjectItem[]>;

// ---------------------------------------------------------------------------
// Error response
// ---------------------------------------------------------------------------

/**
 * Error response written to stderr when a wicked-search API call fails.
 * The process exits with a non-zero code.
 */
export interface ApiError {
  error: string;
  code: string;
  details?: Record<string, unknown>;
}
