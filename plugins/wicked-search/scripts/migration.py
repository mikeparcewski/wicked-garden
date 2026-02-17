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

    # Lineage paths table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lineage_paths (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            sink_id TEXT NOT NULL,
            path_length INTEGER NOT NULL,
            min_confidence TEXT NOT NULL,
            is_complete BOOLEAN NOT NULL DEFAULT 0,
            gaps TEXT,
            steps TEXT NOT NULL,
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

    # Schema version for compatibility gates
    cursor.execute("PRAGMA user_version = 200")

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

        # Derive domain from 'domain' or 'domains' column
        if has_domain:
            domain = row['domain'] or 'code'
        elif has_domains:
            domains_val = row['domains']
            if domains_val:
                # domains is JSON array like '["user"]' — take first
                try:
                    domains_list = json.loads(domains_val) if isinstance(domains_val, str) else domains_val
                    domain = domains_list[0] if isinstance(domains_list, list) and domains_list else 'code'
                except (json.JSONDecodeError, TypeError):
                    domain = 'code'
            else:
                domain = 'code'
        else:
            domain = 'code'

        content = row['content'] if has_content else ''
        # Use description as content fallback
        if not content and has_description:
            content = row['description'] or ''

        metadata = row['metadata'] if has_metadata else None

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

    # Import refs if table exists
    ref_count = 0
    graph_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbol_refs'")
    if graph_cursor.fetchone():
        graph_cursor.execute("SELECT source_id, target_id, ref_type FROM symbol_refs")
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
        graph_cursor.execute("SELECT * FROM lineage_paths")
        lineage_batch = []
        for row in graph_cursor.fetchall():
            lineage_batch.append((
                row['id'],
                row['source_id'],
                row['sink_id'],
                row['path_length'],
                row['min_confidence'],
                row['is_complete'],
                row['gaps'] if 'gaps' in row.keys() else None,
                row['steps']
            ))
            lineage_count += 1

            if len(lineage_batch) >= 10000:
                cursor.executemany("""
                    INSERT OR IGNORE INTO lineage_paths
                    (id, source_id, sink_id, path_length, min_confidence, is_complete, gaps, steps)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, lineage_batch)
                lineage_batch = []

        if lineage_batch:
            cursor.executemany("""
                INSERT OR IGNORE INTO lineage_paths
                (id, source_id, sink_id, path_length, min_confidence, is_complete, gaps, steps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
