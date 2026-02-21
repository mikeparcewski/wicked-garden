#!/usr/bin/env python3
"""
Migration script to convert JSONL index to unified SQLite database.

Reads JSONL files and creates a normalized SQLite database with:
- symbols table with materialized layer and category
- relationship tables (calls, imports, bases, dependents, imported_names)
- symbol_refs table for bidirectional references
- FTS5 index for fast text search
- metadata tables for provenance

Usage:
    python3 migration.py --jsonl-dir DIR --output DB_PATH [--dry-run] [--existing-db GRAPH_DB]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Layer mapping (matches api.py)
TYPE_TO_LAYER = {
    'class': 'backend', 'interface': 'backend', 'method': 'backend', 'function': 'backend',
    'entity': 'backend', 'entity_field': 'backend', 'trait': 'backend', 'type': 'backend',
    'controller': 'backend', 'controller_method': 'backend', 'service': 'backend', 'dao': 'backend',
    'table': 'database', 'column': 'database',
    'import': 'frontend', 'component': 'frontend', 'component_prop': 'frontend',
    'route': 'frontend', 'form_field': 'frontend', 'event_handler': 'frontend', 'data_binding': 'frontend',
    'jsp_page': 'view', 'el_expression': 'view', 'jstl_variable': 'view', 'form_binding': 'view',
    'file': 'unknown', 'module': 'unknown', 'variable': 'unknown', 'constant': 'unknown',
    'document': 'unknown', 'section': 'unknown', 'heading': 'unknown', 'doc_page': 'unknown', 'doc_section': 'unknown',
}


def create_schema(conn: sqlite3.Connection):
    """Create unified schema with all tables and indexes."""
    cursor = conn.cursor()

    # Symbols table
    cursor.execute("""
        CREATE TABLE symbols (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            qualified_name TEXT,
            file_path TEXT NOT NULL,
            line_start INTEGER NOT NULL,
            line_end INTEGER,
            domain TEXT NOT NULL DEFAULT 'code',
            layer TEXT NOT NULL,
            category TEXT,
            content TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT (datetime('now', 'utc')),
            updated_at TEXT DEFAULT (datetime('now', 'utc'))
        )
    """)

    # Relationship tables
    cursor.execute("""
        CREATE TABLE symbol_calls (
            symbol_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id),
            PRIMARY KEY (symbol_id, target_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE symbol_imports (
            symbol_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id),
            PRIMARY KEY (symbol_id, target_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE symbol_imported_names (
            symbol_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id),
            PRIMARY KEY (symbol_id, target_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE symbol_bases (
            symbol_id TEXT NOT NULL,
            base_id TEXT NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id),
            PRIMARY KEY (symbol_id, base_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE symbol_dependents (
            symbol_id TEXT NOT NULL,
            dependent_id TEXT NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id),
            PRIMARY KEY (symbol_id, dependent_id)
        )
    """)

    # Unified references table for bidirectional lookups
    cursor.execute("""
        CREATE TABLE symbol_refs (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            ref_type TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES symbols(id),
            FOREIGN KEY (target_id) REFERENCES symbols(id),
            PRIMARY KEY (source_id, target_id, ref_type)
        )
    """)

    # Metadata tables
    cursor.execute("""
        CREATE TABLE file_metadata (
            file_path TEXT PRIMARY KEY,
            language TEXT,
            size_bytes INTEGER,
            line_count INTEGER,
            indexed_at TEXT DEFAULT (datetime('now', 'utc'))
        )
    """)

    cursor.execute("""
        CREATE TABLE index_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now', 'utc'))
        )
    """)

    # Indexes for performance
    cursor.execute("CREATE INDEX idx_symbols_name ON symbols(name)")
    cursor.execute("CREATE INDEX idx_symbols_type ON symbols(type)")
    cursor.execute("CREATE INDEX idx_symbols_layer ON symbols(layer)")
    cursor.execute("CREATE INDEX idx_symbols_category ON symbols(category)")
    cursor.execute("CREATE INDEX idx_symbols_domain ON symbols(domain)")
    cursor.execute("CREATE INDEX idx_symbols_file ON symbols(file_path)")
    cursor.execute("CREATE INDEX idx_symbol_refs_source ON symbol_refs(source_id)")
    cursor.execute("CREATE INDEX idx_symbol_refs_target ON symbol_refs(target_id)")
    cursor.execute("CREATE INDEX idx_symbol_refs_type ON symbol_refs(ref_type)")

    # FTS5 virtual table
    cursor.execute("""
        CREATE VIRTUAL TABLE symbols_fts USING fts5(
            id UNINDEXED,
            name,
            content,
            content=symbols,
            content_rowid=rowid
        )
    """)

    # FTS sync triggers
    cursor.execute("""
        CREATE TRIGGER symbols_fts_insert AFTER INSERT ON symbols BEGIN
            INSERT INTO symbols_fts(rowid, id, name, content)
            VALUES (new.rowid, new.id, new.name, new.content);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER symbols_fts_delete AFTER DELETE ON symbols BEGIN
            INSERT INTO symbols_fts(symbols_fts, rowid, id, name, content)
            VALUES ('delete', old.rowid, old.id, old.name, old.content);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER symbols_fts_update AFTER UPDATE ON symbols BEGIN
            INSERT INTO symbols_fts(symbols_fts, rowid, id, name, content)
            VALUES ('delete', old.rowid, old.id, old.name, old.content);
            INSERT INTO symbols_fts(rowid, id, name, content)
            VALUES (new.rowid, new.id, new.name, new.content);
        END
    """)

    # Lineage paths table (matches symbol_graph.py + lineage_tracer.py schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lineage_paths (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            sink_id TEXT NOT NULL,
            path_nodes TEXT,
            path_length INTEGER,
            min_confidence TEXT,
            is_complete INTEGER DEFAULT 0,
            gaps TEXT,
            computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES symbols(id),
            FOREIGN KEY (sink_id) REFERENCES symbols(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage_paths(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineage_sink ON lineage_paths(sink_id)")

    # Service nodes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_nodes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            technology TEXT,
            metadata TEXT,
            inferred_from TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_name ON service_nodes(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_type ON service_nodes(type)")

    # Service connections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_service_id TEXT NOT NULL,
            target_service_id TEXT NOT NULL,
            connection_type TEXT NOT NULL,
            protocol TEXT,
            evidence TEXT,
            confidence TEXT NOT NULL DEFAULT 'medium',
            FOREIGN KEY (source_service_id) REFERENCES service_nodes(id),
            FOREIGN KEY (target_service_id) REFERENCES service_nodes(id),
            UNIQUE(source_service_id, target_service_id, connection_type)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_conn_source ON service_connections(source_service_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_conn_target ON service_connections(target_service_id)")

    # Pre-aggregated categories cache (populated after migration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symbol_categories_cache (
            category TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT 'code',
            symbol_count INTEGER NOT NULL,
            layers TEXT NOT NULL,
            PRIMARY KEY (category, domain)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_relationships_cache (
            from_category TEXT NOT NULL,
            to_category TEXT NOT NULL,
            ref_count INTEGER NOT NULL,
            PRIMARY KEY (from_category, to_category)
        )
    """)

    # Schema version for compatibility gates (bump on schema changes; users reindex)
    cursor.execute("PRAGMA user_version = 202")

    conn.commit()


def extract_category(file_path: str) -> str:
    """Derive a category from file path using the first meaningful directory.

    Matches the logic in api.py's _derive_directory_category().
    """
    parts = file_path.replace("\\", "/").split("/")

    # Known framework markers to skip past
    skip_markers = {"src", "main", "java", "kotlin", "scala", "python", "lib",
                    "WEB-INF", "META-INF", "resources", "static", "public",
                    "app", "internal", "pkg", "cmd"}
    view_markers = {"pages", "jsp", "jsp-client", "views", "templates", "webapp"}

    # Strategy 1: Skip past known markers to find first meaningful dir
    for i, part in enumerate(parts):
        if part in view_markers:
            remaining = parts[i + 1:]
            if remaining and remaining[0] in ("WEB-INF",):
                remaining = remaining[1:]
            if remaining and remaining[0] in view_markers:
                remaining = remaining[1:]
            if len(remaining) > 1:
                return remaining[0]
            return "root"

    # Strategy 2: Find first dir after src/main/... pattern
    for i, part in enumerate(parts):
        if part == "src" and i + 2 < len(parts):
            rest = parts[i + 1:]
            meaningful = [p for p in rest[:-1] if p not in skip_markers]
            if meaningful:
                return meaningful[0]

    # Strategy 3: Use top-level directory (skip common roots)
    meaningful = [p for p in parts[:-1] if p and p not in skip_markers and not p.startswith(".")]
    if meaningful:
        return meaningful[0]

    return 'root'


def compute_layer(symbol_type: str) -> str:
    """Map symbol type to architectural layer."""
    return TYPE_TO_LAYER.get(symbol_type, 'unknown')


def _extract_ref_id(entry) -> str:
    """Extract a string ID from a relationship entry.

    JSONL entries can have refs as plain strings or as dicts with target_id/name.
    """
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get('target_id') or entry.get('name') or entry.get('id', '')
    return str(entry)


def import_jsonl_symbols(conn: sqlite3.Connection, jsonl_dir: Path) -> Tuple[int, int]:
    """Import symbols from JSONL files. Returns (symbol_count, ref_count)."""
    cursor = conn.cursor()

    symbol_batch = []
    ref_batch = []
    symbol_count = 0
    ref_count = 0

    BATCH_SIZE = 10000

    # Find all JSONL files
    jsonl_files = list(jsonl_dir.glob('**/*.jsonl'))

    for jsonl_file in jsonl_files:
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    symbol = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Extract core fields
                symbol_id = symbol.get('id')
                if not symbol_id:
                    continue

                name = symbol.get('name', '')
                symbol_type = symbol.get('type', 'unknown')
                file_path = symbol.get('file') or symbol.get('file_path', '')
                line_start = symbol.get('line_start', 0)
                line_end = symbol.get('line_end', line_start)
                domain = symbol.get('domain', 'code')
                content = symbol.get('content') or ''

                # Compute derived fields
                layer = compute_layer(symbol_type)
                category = extract_category(file_path)
                qualified_name = symbol.get('qualified_name')

                # Metadata as JSON string
                metadata_val = symbol.get('metadata', {})
                if isinstance(metadata_val, dict):
                    metadata_json = json.dumps(metadata_val) if metadata_val else None
                elif isinstance(metadata_val, str):
                    metadata_json = metadata_val if metadata_val else None
                else:
                    metadata_json = json.dumps(metadata_val) if metadata_val else None

                # Add to batch
                symbol_batch.append((
                    symbol_id, name, symbol_type, qualified_name,
                    file_path, line_start, line_end, domain,
                    layer, category, content, metadata_json
                ))

                # Extract relationships (handle both string IDs and dict entries)
                for entry in symbol.get('calls', []):
                    ref_id = _extract_ref_id(entry)
                    if ref_id:
                        ref_batch.append((symbol_id, ref_id, 'calls'))

                for entry in symbol.get('imports', []):
                    ref_id = _extract_ref_id(entry)
                    if ref_id:
                        ref_batch.append((symbol_id, ref_id, 'imports'))

                for entry in symbol.get('bases', []):
                    ref_id = _extract_ref_id(entry)
                    if ref_id:
                        ref_batch.append((symbol_id, ref_id, 'extends'))

                for entry in symbol.get('imported_names', []):
                    ref_id = _extract_ref_id(entry)
                    if ref_id:
                        ref_batch.append((symbol_id, ref_id, 'imports'))

                for entry in symbol.get('dependents', []):
                    ref_id = _extract_ref_id(entry)
                    if ref_id:
                        ref_batch.append((ref_id, symbol_id, 'depends_on'))

                symbol_count += 1

                # Batch insert
                if len(symbol_batch) >= BATCH_SIZE:
                    cursor.executemany("""
                        INSERT OR REPLACE INTO symbols
                        (id, name, type, qualified_name, file_path, line_start, line_end,
                         domain, layer, category, content, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, symbol_batch)
                    symbol_batch = []

                if len(ref_batch) >= BATCH_SIZE:
                    cursor.executemany("""
                        INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
                        VALUES (?, ?, ?)
                    """, ref_batch)
                    ref_batch = []
                    conn.commit()

    # Insert remaining
    if symbol_batch:
        cursor.executemany("""
            INSERT OR REPLACE INTO symbols
            (id, name, type, qualified_name, file_path, line_start, line_end,
             domain, layer, category, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, symbol_batch)

    if ref_batch:
        cursor.executemany("""
            INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
            VALUES (?, ?, ?)
        """, ref_batch)

    conn.commit()

    # Count actual refs inserted
    cursor.execute("SELECT COUNT(*) FROM symbol_refs")
    ref_count = cursor.fetchone()[0]

    return (symbol_count, ref_count)


def _detect_graph_columns(graph_cursor) -> Dict[str, bool]:
    """Detect which columns exist in the graph DB symbols table."""
    graph_cursor.execute("PRAGMA table_info(symbols)")
    columns = {row[1] for row in graph_cursor.fetchall()}
    return columns


def import_graph_db(conn: sqlite3.Connection, graph_db_path: Path) -> Tuple[int, int]:
    """Import symbols and refs from existing graph database. Returns (symbol_count, ref_count)."""
    if not graph_db_path.exists():
        return (0, 0)

    graph_conn = sqlite3.connect(str(graph_db_path))
    graph_conn.row_factory = sqlite3.Row
    graph_cursor = graph_conn.cursor()
    cursor = conn.cursor()

    # Snapshot ref count before graph import for accurate delta reporting
    cursor.execute("SELECT COUNT(*) FROM symbol_refs")
    refs_before = cursor.fetchone()[0]

    # Check if graph DB has symbols table
    graph_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbols'")
    if not graph_cursor.fetchone():
        graph_conn.close()
        return (0, 0)

    # Detect actual columns in graph DB
    columns = _detect_graph_columns(graph_cursor)

    # Build SELECT dynamically based on available columns
    # Required: id, name, type, file_path, line_start
    # Optional: qualified_name, line_end, domain/domains, content, metadata, layer, label, description
    has_qualified_name = 'qualified_name' in columns
    has_file_path = 'file_path' in columns
    has_line_start = 'line_start' in columns
    has_line_end = 'line_end' in columns
    has_domain = 'domain' in columns
    has_domains = 'domains' in columns
    has_content = 'content' in columns
    has_metadata = 'metadata' in columns
    has_layer = 'layer' in columns
    has_description = 'description' in columns
    has_label = 'label' in columns
    has_inferred_type = 'inferred_type' in columns

    graph_cursor.execute("SELECT * FROM symbols LIMIT 0")
    col_names = [desc[0] for desc in graph_cursor.description]

    # Fetch all rows - quote identifiers for safety
    quoted_cols = [f'"{c}"' for c in col_names]
    graph_cursor.execute(f"SELECT {','.join(quoted_cols)} FROM symbols")

    symbol_count = 0
    symbol_batch = []

    for row in graph_cursor:
        symbol_id = row['id']
        name = row['name']
        symbol_type = row['type']
        qualified_name = row['qualified_name'] if has_qualified_name else None
        file_path = row['file_path'] if has_file_path else ''
        line_start = row['line_start'] if has_line_start else 0
        line_end = row['line_end'] if has_line_end else line_start

        content = row['content'] if has_content else ''
        # Use description as content fallback
        if not content and has_description:
            content = row['description'] or ''

        metadata = row['metadata'] if has_metadata else None

        # Graph DB symbols are always code-domain; preserve app-level domains as metadata
        original_domain = None
        if has_domain:
            original_domain = row['domain']
        elif has_domains:
            domains_val = row['domains']
            if domains_val:
                try:
                    domains_list = json.loads(domains_val) if isinstance(domains_val, str) else domains_val
                    original_domain = domains_list[0] if isinstance(domains_list, list) and domains_list else None
                except (json.JSONDecodeError, TypeError):
                    pass

        domain = 'code'  # All graph symbols are code

        # Preserve non-standard app domains in metadata
        if original_domain and original_domain not in ('code', 'doc'):
            try:
                existing_meta = json.loads(metadata) if metadata else {}
                if not isinstance(existing_meta, dict):
                    existing_meta = {'_original_metadata': existing_meta}
            except (json.JSONDecodeError, TypeError):
                existing_meta = {}
            existing_meta['app_domain'] = original_domain
            metadata = json.dumps(existing_meta)

        # R4: Merge graph DB enrichment fields into metadata JSON
        enrichment = {}
        if has_label and row['label']:
            enrichment['label'] = row['label']
        if has_inferred_type and row['inferred_type']:
            enrichment['inferred_type'] = row['inferred_type']
        if has_description and row['description']:
            enrichment['description'] = row['description']
        if has_domains and row['domains']:
            enrichment['domains'] = row['domains']
        if enrichment:
            try:
                existing_meta = json.loads(metadata) if metadata else {}
                if not isinstance(existing_meta, dict):
                    existing_meta = {'_original_metadata': existing_meta}
            except (json.JSONDecodeError, TypeError):
                existing_meta = {}
            existing_meta.update(enrichment)
            metadata = json.dumps(existing_meta)

        # Compute layer: use existing layer column or derive from type
        if has_layer and row['layer']:
            layer = row['layer']
        else:
            layer = compute_layer(symbol_type)

        category = extract_category(file_path) if file_path else 'root'

        symbol_batch.append((
            symbol_id, name, symbol_type, qualified_name,
            file_path, line_start, line_end, domain,
            layer, category, content, metadata
        ))
        symbol_count += 1

        if len(symbol_batch) >= 10000:
            cursor.executemany("""
                INSERT OR IGNORE INTO symbols
                (id, name, type, qualified_name, file_path, line_start, line_end,
                 domain, layer, category, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, symbol_batch)
            symbol_batch = []

    if symbol_batch:
        cursor.executemany("""
            INSERT OR IGNORE INTO symbols
            (id, name, type, qualified_name, file_path, line_start, line_end,
             domain, layer, category, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, symbol_batch)

    # Import refs from graph DB tables: 'refs' and 'derived_refs' (ohio_graph.db),
    # plus 'symbol_refs' for backward compatibility with older graph DBs
    ref_count = 0
    for ref_table in ('refs', 'derived_refs', 'symbol_refs'):
        graph_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (ref_table,)
        )
        if not graph_cursor.fetchone():
            continue

        graph_cursor.execute(
            f"SELECT source_id, target_id, ref_type FROM {ref_table}"
        )
        ref_batch = []
        for row in graph_cursor.fetchall():
            ref_batch.append((row['source_id'], row['target_id'], row['ref_type']))
            if len(ref_batch) >= 10000:
                cursor.executemany("""
                    INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
                    VALUES (?, ?, ?)
                """, ref_batch)
                ref_batch = []

        if ref_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
                VALUES (?, ?, ?)
            """, ref_batch)

    conn.commit()
    graph_conn.close()

    # Count refs added by graph import (delta from before)
    cursor.execute("SELECT COUNT(*) FROM symbol_refs")
    ref_count = cursor.fetchone()[0] - refs_before

    return (symbol_count, ref_count)


def import_graph_extras(conn: sqlite3.Connection, graph_db_path: Path) -> Tuple[int, int, int]:
    """Import lineage_paths, service_nodes, and service_connections from graph DB.

    Returns (lineage_count, service_nodes_count, service_connections_count).
    """
    if not graph_db_path.exists():
        return (0, 0, 0)

    graph_conn = sqlite3.connect(str(graph_db_path))
    graph_conn.row_factory = sqlite3.Row
    graph_cursor = graph_conn.cursor()
    cursor = conn.cursor()

    lineage_count = 0
    service_nodes_count = 0
    service_connections_count = 0

    # Import lineage_paths if it exists
    graph_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lineage_paths'")
    if graph_cursor.fetchone():
        # Detect column names in source graph DB (may have path_nodes or steps)
        graph_cursor.execute("PRAGMA table_info(lineage_paths)")
        graph_cols = {r[1] for r in graph_cursor.fetchall()}
        path_col = 'path_nodes' if 'path_nodes' in graph_cols else 'steps'
        has_computed_at = 'computed_at' in graph_cols

        graph_cursor.execute("SELECT * FROM lineage_paths")
        lineage_batch = []
        for row in graph_cursor.fetchall():
            lineage_batch.append((
                row['id'],
                row['source_id'],
                row['sink_id'],
                row[path_col] if path_col in row.keys() else None,
                row['path_length'],
                row['min_confidence'],
                row['is_complete'],
                row['gaps'] if 'gaps' in row.keys() else None,
                row['computed_at'] if has_computed_at and 'computed_at' in row.keys() else None,
            ))
            lineage_count += 1

            if len(lineage_batch) >= 10000:
                cursor.executemany("""
                    INSERT OR IGNORE INTO lineage_paths
                    (id, source_id, sink_id, path_nodes, path_length, min_confidence, is_complete, gaps, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, lineage_batch)
                lineage_batch = []

        if lineage_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO lineage_paths
                (id, source_id, sink_id, path_nodes, path_length, min_confidence, is_complete, gaps, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, lineage_batch)

    # Import service_nodes if it exists
    graph_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_nodes'")
    if graph_cursor.fetchone():
        graph_cursor.execute("SELECT * FROM service_nodes")
        service_batch = []
        for row in graph_cursor.fetchall():
            service_batch.append((
                row['id'],
                row['name'],
                row['type'],
                row['technology'] if 'technology' in row.keys() else None,
                row['metadata'] if 'metadata' in row.keys() else None,
                row['inferred_from'] if 'inferred_from' in row.keys() else None
            ))
            service_nodes_count += 1

            if len(service_batch) >= 10000:
                cursor.executemany("""
                    INSERT OR IGNORE INTO service_nodes
                    (id, name, type, technology, metadata, inferred_from)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, service_batch)
                service_batch = []

        if service_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO service_nodes
                (id, name, type, technology, metadata, inferred_from)
                VALUES (?, ?, ?, ?, ?, ?)
            """, service_batch)

    # Import service_connections if it exists
    graph_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_connections'")
    if graph_cursor.fetchone():
        graph_cursor.execute("SELECT * FROM service_connections")
        conn_batch = []
        for row in graph_cursor.fetchall():
            # Note: Skip 'id' column since it's AUTOINCREMENT in destination
            conn_batch.append((
                row['source_service_id'],
                row['target_service_id'],
                row['connection_type'],
                row['protocol'] if 'protocol' in row.keys() else None,
                row['evidence'] if 'evidence' in row.keys() else None,
                row['confidence'] if 'confidence' in row.keys() else 'medium'
            ))
            service_connections_count += 1

            if len(conn_batch) >= 10000:
                cursor.executemany("""
                    INSERT OR IGNORE INTO service_connections
                    (source_service_id, target_service_id, connection_type, protocol, evidence, confidence)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, conn_batch)
                conn_batch = []

        if conn_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO service_connections
                (source_service_id, target_service_id, connection_type, protocol, evidence, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, conn_batch)

    conn.commit()
    graph_conn.close()

    return (lineage_count, service_nodes_count, service_connections_count)


def _find_symbol_by_name(cursor, name: str, source_file: str = None):
    """Find a symbol by name with fallback strategies.

    Tries exact name match first, then extracts the short name from dotted
    import paths (e.g., 'com.app.models.User' -> 'User').

    When multiple candidates match, prefers symbols in the same project directory
    as the source file (same top-level path prefix).

    Returns:
        The matched symbol row (id, type, domain, file_path), or None.
    """
    # Build the ORDER BY clause with optional project-local preference
    # If source_file is available, prefer symbols sharing the same project root
    order_clause = """
        ORDER BY
            CASE WHEN domain = 'code' THEN 0 ELSE 1 END,
            CASE WHEN type IN ('class', 'interface', 'struct') THEN 0
                 WHEN type IN ('function', 'method') THEN 1
                 ELSE 2 END
    """

    def _query_and_pick(query_name: str):
        cursor.execute(f"""
            SELECT id, type, domain, file_path FROM symbols
            WHERE name = ? AND type NOT IN ('file', 'import')
            {order_clause}
        """, (query_name,))
        candidates = cursor.fetchall()
        if not candidates:
            return None
        if source_file and len(candidates) > 1:
            local = _pick_local_candidate(candidates, source_file)
            if local:
                return local
        return candidates[0]

    # Strategy 1: Exact name match
    match = _query_and_pick(name)
    if match:
        return match

    # Strategy 2: Dotted import name — extract last segment
    # e.g., 'com.app.models.User' -> 'User'
    if '.' in name:
        short_name = name.rsplit('.', 1)[-1]
        match = _query_and_pick(short_name)
        if match:
            return match

    return None


def _pick_local_candidate(candidates, source_file: str):
    """From a list of candidate symbols, pick one sharing the same project root.

    Compares path prefixes (up to 4 components, excluding filename) to find
    symbols in the same project tree as the source file.
    """
    # Extract project prefix (up to 4 path components for project-local matching)
    parts = source_file.replace("\\", "/").split("/")
    prefix = "/".join(parts[:min(4, len(parts) - 1)])

    for candidate in candidates:
        if candidate["file_path"] and candidate["file_path"].startswith(prefix):
            return candidate
    return None


def resolve_orphan_refs(conn: sqlite3.Connection) -> int:
    """Resolve symbol_refs where target_id is an unqualified name (not a real symbol ID).

    During JSONL import, imported_names and some call refs use plain symbol names
    (e.g., 'DatabaseConnection' or 'com.app.models.User') as target_id instead
    of qualified IDs (e.g., '/path/to/file.py::DatabaseConnection'). This function
    resolves them by matching against actual symbol names in the symbols table.

    Handles:
    - Simple names: 'User' -> matched by symbols.name
    - Dotted imports: 'com.app.models.User' -> extract 'User', match by name
    - Project-local preference: when multiple symbols match, prefer same-project
    - UNIQUE conflicts: gracefully handles cases where resolution would create
      duplicate (source_id, target_id, ref_type) rows

    Returns:
        Number of refs resolved.
    """
    cursor = conn.cursor()

    # Find orphan refs: target_id doesn't match any symbol ID
    # Also fetch source_id so we can use project-local matching
    cursor.execute("""
        SELECT DISTINCT sr.target_id
        FROM symbol_refs sr
        LEFT JOIN symbols s ON sr.target_id = s.id
        WHERE s.id IS NULL
    """)
    orphan_targets = [row[0] for row in cursor.fetchall()]

    if not orphan_targets:
        return 0

    resolved = 0

    for orphan_name in orphan_targets:
        if not orphan_name or '::' in orphan_name:
            # Already qualified or empty — skip
            continue

        # Get a representative source file for project-local matching
        cursor.execute("""
            SELECT s.file_path FROM symbol_refs sr
            JOIN symbols s ON sr.source_id = s.id
            WHERE sr.target_id = ?
            LIMIT 1
        """, (orphan_name,))
        source_row = cursor.fetchone()
        source_file = source_row[0] if source_row else None

        match = _find_symbol_by_name(cursor, orphan_name, source_file)

        if match:
            resolved_id = match[0]
            # Use INSERT OR IGNORE + DELETE to handle UNIQUE constraint conflicts.
            # If updating target_id would create a duplicate (source_id, resolved_id, ref_type),
            # the INSERT is silently skipped and the old row is deleted.
            cursor.execute("""
                INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
                SELECT source_id, ?, ref_type
                FROM symbol_refs
                WHERE target_id = ?
            """, (resolved_id, orphan_name))
            inserted = cursor.rowcount

            cursor.execute("""
                DELETE FROM symbol_refs WHERE target_id = ?
            """, (orphan_name,))
            resolved += inserted

    # Also resolve orphan source_ids (less common but possible)
    cursor.execute("""
        SELECT DISTINCT sr.source_id
        FROM symbol_refs sr
        LEFT JOIN symbols s ON sr.source_id = s.id
        WHERE s.id IS NULL
    """)
    orphan_sources = [row[0] for row in cursor.fetchall()]

    for orphan_name in orphan_sources:
        if not orphan_name or '::' in orphan_name:
            continue

        match = _find_symbol_by_name(cursor, orphan_name)

        if match:
            cursor.execute("""
                INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
                SELECT ?, target_id, ref_type
                FROM symbol_refs
                WHERE source_id = ?
            """, (match[0], orphan_name))
            inserted = cursor.rowcount

            cursor.execute("""
                DELETE FROM symbol_refs WHERE source_id = ?
            """, (orphan_name,))
            resolved += inserted

    # Clean up any remaining refs that still point to non-existent symbols
    # (external library refs like EasyMock, List, etc. that have no local definition)
    cursor.execute("""
        DELETE FROM symbol_refs
        WHERE target_id NOT IN (SELECT id FROM symbols)
           OR source_id NOT IN (SELECT id FROM symbols)
    """)

    conn.commit()
    return resolved


def create_doc_code_crossrefs(conn: sqlite3.Connection) -> int:
    """Create cross-references between doc sections and code symbols they mention.

    Scans doc section names and content for mentions of code symbol names,
    creating 'documents' refs from doc sections to the code symbols they reference.

    Returns:
        Number of cross-references created.
    """
    cursor = conn.cursor()

    # Get all code symbols (classes, functions, methods — not files or imports)
    cursor.execute("""
        SELECT id, name FROM symbols
        WHERE domain = 'code' AND type NOT IN ('file', 'import')
        AND LENGTH(name) >= 3
        ORDER BY
            CASE WHEN type IN ('class', 'interface', 'struct') THEN 0
                 WHEN type IN ('function', 'method') THEN 1
                 ELSE 2 END
    """)
    code_symbols = cursor.fetchall()

    if not code_symbols:
        return 0

    # Build a lookup: name -> id (prefer classes/interfaces over methods/functions)
    name_to_id = {}
    for row in code_symbols:
        name = row['name']
        if name not in name_to_id:
            name_to_id[name] = row['id']

    # Get all doc sections with their names (which often contain symbol references)
    cursor.execute("""
        SELECT id, name, content FROM symbols
        WHERE domain = 'doc' AND type != 'file'
    """)
    doc_sections = cursor.fetchall()

    if not doc_sections:
        return 0

    ref_batch = []
    seen = set()

    for doc in doc_sections:
        doc_id = doc['id']
        doc_name = doc['name'] or ''
        doc_content = doc['content'] or ''
        # Combine name and content for matching
        searchable = f"{doc_name} {doc_content}"

        # Tokenize once per doc — splitting on non-word chars also strips backticks
        # so `ClassName` yields "ClassName" as a token
        tokens = set(t for t in re.split(r'\W+', searchable) if len(t) >= 3)

        for token in tokens:
            sym_id = name_to_id.get(token)
            if sym_id is not None:
                ref_key = (doc_id, sym_id)
                if ref_key not in seen:
                    seen.add(ref_key)
                    ref_batch.append((doc_id, sym_id, 'documents'))

    if ref_batch:
        cursor.executemany("""
            INSERT OR IGNORE INTO symbol_refs (source_id, target_id, ref_type)
            VALUES (?, ?, ?)
        """, ref_batch)

    conn.commit()
    return len(ref_batch)


def populate_categories_cache(conn: sqlite3.Connection):
    """Pre-aggregate category stats and cross-category relationships into cache tables."""
    cursor = conn.cursor()

    # Clear existing cache
    cursor.execute("DELETE FROM symbol_categories_cache")
    cursor.execute("DELETE FROM category_relationships_cache")

    # Aggregate categories with layer distribution per domain
    cursor.execute("""
        SELECT category, domain, layer, COUNT(*) as cnt
        FROM symbols
        WHERE category IS NOT NULL
        GROUP BY category, domain, layer
    """)

    # Build nested dict: {(category, domain): {layer: count}}
    cat_layers = {}
    cat_counts = {}
    for row in cursor.fetchall():
        key = (row['category'], row['domain'])
        if key not in cat_layers:
            cat_layers[key] = {}
            cat_counts[key] = 0
        cat_layers[key][row['layer']] = row['cnt']
        cat_counts[key] += row['cnt']

    # Insert into cache
    cache_rows = []
    for (category, domain), layers in cat_layers.items():
        cache_rows.append((
            category, domain, cat_counts[(category, domain)],
            json.dumps(layers)
        ))

    cursor.executemany("""
        INSERT INTO symbol_categories_cache (category, domain, symbol_count, layers)
        VALUES (?, ?, ?, ?)
    """, cache_rows)

    # Aggregate cross-category relationships
    cursor.execute("""
        INSERT INTO category_relationships_cache (from_category, to_category, ref_count)
        SELECT s1.category, s2.category, COUNT(*)
        FROM symbol_refs r
        JOIN symbols s1 ON r.source_id = s1.id
        JOIN symbols s2 ON r.target_id = s2.id
        WHERE s1.category IS NOT NULL
          AND s2.category IS NOT NULL
          AND s1.category != s2.category
        GROUP BY s1.category, s2.category
        HAVING COUNT(*) > 2
    """)

    conn.commit()


def verify_migration(conn: sqlite3.Connection) -> Dict:
    """Verify migration integrity and return stats."""
    cursor = conn.cursor()

    stats = {}

    # Count symbols
    cursor.execute("SELECT COUNT(*) FROM symbols")
    stats['symbols_total'] = cursor.fetchone()[0]

    # Count by domain
    cursor.execute("SELECT domain, COUNT(*) FROM symbols GROUP BY domain")
    stats['by_domain'] = dict(cursor.fetchall())

    # Count by layer
    cursor.execute("SELECT layer, COUNT(*) FROM symbols GROUP BY layer")
    stats['by_layer'] = dict(cursor.fetchall())

    # Count by type
    cursor.execute("SELECT type, COUNT(*) FROM symbols GROUP BY type")
    stats['by_type'] = dict(cursor.fetchall())

    # Count refs
    cursor.execute("SELECT COUNT(*) FROM symbol_refs")
    stats['refs_total'] = cursor.fetchone()[0]

    # Count refs by type
    cursor.execute("SELECT ref_type, COUNT(*) FROM symbol_refs GROUP BY ref_type")
    stats['by_ref_type'] = dict(cursor.fetchall())

    # FTS row count
    cursor.execute("SELECT COUNT(*) FROM symbols_fts")
    stats['fts_rows'] = cursor.fetchone()[0]

    # Lineage paths count
    cursor.execute("SELECT COUNT(*) FROM lineage_paths")
    stats['lineage_paths'] = cursor.fetchone()[0]

    # Service nodes count
    cursor.execute("SELECT COUNT(*) FROM service_nodes")
    stats['service_nodes'] = cursor.fetchone()[0]

    # Service connections count
    cursor.execute("SELECT COUNT(*) FROM service_connections")
    stats['service_connections'] = cursor.fetchone()[0]

    # Categories cache stats
    cursor.execute("SELECT COUNT(*) FROM symbol_categories_cache")
    stats['categories_cached'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM category_relationships_cache")
    stats['category_relationships_cached'] = cursor.fetchone()[0]

    return stats


def main():
    parser = argparse.ArgumentParser(description='Migrate JSONL index to unified SQLite database')
    parser.add_argument('--jsonl-dir', type=Path, required=True, help='Directory containing JSONL files')
    parser.add_argument('--output', type=Path, required=True, help='Output SQLite database path')
    parser.add_argument('--existing-db', type=Path, help='Existing graph database to import')
    parser.add_argument('--dry-run', action='store_true', help='Validate without writing')

    args = parser.parse_args()

    if not args.jsonl_dir.exists():
        print(json.dumps({'ok': False, 'error': f'JSONL directory not found: {args.jsonl_dir}'}))
        sys.exit(1)

    # Create temp database
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    try:
        conn = sqlite3.connect(temp_path)
        conn.row_factory = sqlite3.Row

        # Create schema
        create_schema(conn)

        # Import JSONL
        jsonl_symbols, jsonl_refs = import_jsonl_symbols(conn, args.jsonl_dir)

        # Import existing graph DB if provided
        graph_symbols, graph_refs = (0, 0)
        graph_lineage, graph_services, graph_connections = (0, 0, 0)
        if args.existing_db:
            graph_symbols, graph_refs = import_graph_db(conn, args.existing_db)
            graph_lineage, graph_services, graph_connections = import_graph_extras(conn, args.existing_db)

        # Resolve orphan refs (imported_names with plain names instead of IDs)
        orphan_resolved = resolve_orphan_refs(conn)

        # Create doc-to-code cross-references
        doc_code_refs = create_doc_code_crossrefs(conn)

        # Populate categories cache (after all symbols + refs imported)
        populate_categories_cache(conn)

        # Verify
        stats = verify_migration(conn)

        # Store metadata
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO index_metadata (key, value)
            VALUES ('migration_date', ?)
        """, (datetime.now(timezone.utc).isoformat(),))
        cursor.execute("""
            INSERT INTO index_metadata (key, value)
            VALUES ('source_jsonl_dir', ?)
        """, (str(args.jsonl_dir),))
        if args.existing_db:
            cursor.execute("""
                INSERT INTO index_metadata (key, value)
                VALUES ('source_graph_db', ?)
            """, (str(args.existing_db),))
        conn.commit()

        conn.close()

        # Move to final location if not dry-run
        if not args.dry_run:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # os.replace is atomic on POSIX — no separate unlink needed
            os.replace(temp_path, str(args.output))
        else:
            # Clean up temp file on dry-run
            os.unlink(temp_path)

        # Report
        report = {
            'ok': True,
            'output': str(args.output),
            'dry_run': args.dry_run,
            'jsonl_symbols': jsonl_symbols,
            'jsonl_refs': jsonl_refs,
            'graph_symbols': graph_symbols,
            'graph_refs': graph_refs,
            'graph_lineage': graph_lineage,
            'graph_services': graph_services,
            'graph_connections': graph_connections,
            'orphan_refs_resolved': orphan_resolved,
            'doc_code_crossrefs': doc_code_refs,
            'stats': stats
        }

        print(json.dumps(report, indent=2))

    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        print(json.dumps({'ok': False, 'error': str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
