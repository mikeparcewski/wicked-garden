#!/usr/bin/env python3
"""
Unified query builder for SQLite-backed code search.

Provides multi-tier search, reference tracking, blast radius analysis,
and category aggregation. Replaces JsonlSearcher with SQL-based queries.

Usage:
    from query_builder import UnifiedQueryEngine

    engine = UnifiedQueryEngine(db_path)
    results = engine.search_all("findUser", limit=10)
    refs = engine.find_references("symbol-id-123")
    radius = engine.blast_radius("symbol-id-123", max_depth=3)
"""

import json
import sqlite3
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class UnifiedQueryEngine:
    """Unified query engine for SQLite-backed symbol search."""

    def __init__(self, db_path: str, config_path: Optional[str] = None):
        """
        Initialize query engine.

        Args:
            db_path: Path to SQLite database
            config_path: Optional path to config.json for rollback settings
        """
        self.db_path = Path(db_path)

        # Check for rollback flag
        if config_path:
            config = self._load_config(config_path)
            if config.get('fallback_to_jsonl', False):
                raise NotImplementedError("Config specifies fallback_to_jsonl=true")

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def _load_config(self, config_path: str) -> Dict:
        """Load config.json."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _parse_metadata(raw) -> Dict:
        """Parse metadata field, handling non-JSON strings gracefully."""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert SQLite row to dict with standard shape."""
        return {
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'qualified_name': row['qualified_name'],
            'file_path': row['file_path'],
            'line_start': row['line_start'],
            'line_end': row['line_end'],
            'domain': row['domain'],
            'layer': row['layer'],
            'category': row['category'],
            'content': row['content'],
            'metadata': self._parse_metadata(row['metadata'])
        }

    @staticmethod
    def _orphan_ref_dict(peer_id: str) -> Dict:
        """Build a minimal symbol dict for refs whose peer is not in the symbols table."""
        return {
            'id': peer_id, 'name': peer_id, 'type': 'unknown',
            'qualified_name': '', 'file_path': '', 'line_start': None, 'line_end': None,
            'domain': 'unknown', 'layer': 'unknown', 'category': '', 'content': '', 'metadata': {}
        }

    @staticmethod
    def _exclusion_clause(seen_ids: Set[str], col: str = "id") -> Tuple[str, tuple]:
        """Build NOT IN clause that handles empty sets correctly.

        SQLite's `id NOT IN (NULL)` returns 0 rows — NOT what we want.
        When seen_ids is empty, return a no-op condition instead.
        """
        if not seen_ids:
            return "1=1", ()
        placeholders = ','.join('?' * len(seen_ids))
        return f"{col} NOT IN ({placeholders})", tuple(seen_ids)

    def search_all(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Multi-tier search: exact -> prefix -> FTS5 -> qualified_name LIKE.

        Returns ranked results with provenance. Each tier fetches up to
        (limit + offset) candidates so that later pages are correct.
        """
        target = limit + offset
        results = []
        seen_ids: Set[str] = set()

        cursor = self.conn.cursor()

        # Tier 1: Exact match (score=100)
        cursor.execute("""
            SELECT * FROM symbols
            WHERE name = ?
            LIMIT ?
        """, (query, target))

        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['score'] = 100
            result['match_type'] = 'exact'
            results.append(result)
            seen_ids.add(row['id'])

        # Tier 2: Prefix match (score=75)
        if len(results) < target:
            excl, excl_params = self._exclusion_clause(seen_ids)
            cursor.execute(f"""
                SELECT * FROM symbols
                WHERE name LIKE ? || '%' AND {excl}
                LIMIT ?
            """, (query, *excl_params, target - len(results)))

            for row in cursor.fetchall():
                result = self._row_to_dict(row)
                result['score'] = 75
                result['match_type'] = 'prefix'
                results.append(result)
                seen_ids.add(row['id'])

        # Tier 3: FTS5 match (score=50+rank)
        if len(results) < target:
            excl, excl_params = self._exclusion_clause(seen_ids, col="s.id")
            try:
                cursor.execute(f"""
                    SELECT s.*, rank AS fts_rank FROM symbols s
                    JOIN symbols_fts ON symbols_fts.id = s.id
                    WHERE symbols_fts MATCH ?
                      AND {excl}
                    ORDER BY rank
                    LIMIT ?
                """, (query, *excl_params, target - len(results)))

                for row in cursor.fetchall():
                    result = self._row_to_dict(row)
                    fts_rank = row['fts_rank'] if 'fts_rank' in row.keys() else 0
                    result['score'] = 50 + min(abs(fts_rank), 50)
                    result['match_type'] = 'fts'
                    results.append(result)
                    seen_ids.add(row['id'])
            except sqlite3.OperationalError:
                pass  # Malformed FTS query — skip this tier

        # Tier 4: Qualified name LIKE (score=50)
        if len(results) < target:
            excl, excl_params = self._exclusion_clause(seen_ids)
            cursor.execute(f"""
                SELECT * FROM symbols
                WHERE qualified_name LIKE '%' || ? || '%'
                  AND {excl}
                LIMIT ?
            """, (query, *excl_params, target - len(results)))

            for row in cursor.fetchall():
                result = self._row_to_dict(row)
                result['score'] = 50
                result['match_type'] = 'qualified_name'
                results.append(result)
                seen_ids.add(row['id'])

        return results[offset:offset + limit]

    def search_code(self, query: str, limit: int = 20) -> List[Dict]:
        """Search code domain only."""
        cursor = self.conn.cursor()

        results = []
        seen_ids: Set[str] = set()

        # Exact
        cursor.execute("""
            SELECT * FROM symbols
            WHERE name = ? AND domain = 'code'
            LIMIT ?
        """, (query, limit))

        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['score'] = 100
            result['match_type'] = 'exact'
            results.append(result)
            seen_ids.add(row['id'])

        # Prefix
        if len(results) < limit:
            excl, excl_params = self._exclusion_clause(seen_ids)
            cursor.execute(f"""
                SELECT * FROM symbols
                WHERE name LIKE ? || '%' AND domain = 'code'
                  AND {excl}
                LIMIT ?
            """, (query, *excl_params, limit - len(results)))

            for row in cursor.fetchall():
                result = self._row_to_dict(row)
                result['score'] = 75
                result['match_type'] = 'prefix'
                results.append(result)
                seen_ids.add(row['id'])

        # FTS
        if len(results) < limit:
            excl, excl_params = self._exclusion_clause(seen_ids, col="s.id")
            try:
                cursor.execute(f"""
                    SELECT s.*, rank AS fts_rank FROM symbols s
                    JOIN symbols_fts ON symbols_fts.id = s.id
                    WHERE symbols_fts MATCH ? AND s.domain = 'code'
                      AND {excl}
                    ORDER BY rank
                    LIMIT ?
                """, (query, *excl_params, limit - len(results)))

                for row in cursor.fetchall():
                    result = self._row_to_dict(row)
                    fts_rank = row['fts_rank'] if 'fts_rank' in row.keys() else 0
                    result['score'] = 50 + min(abs(fts_rank), 50)
                    result['match_type'] = 'fts'
                    results.append(result)
                    seen_ids.add(row['id'])
            except sqlite3.OperationalError:
                pass

        return results

    def search_docs(self, query: str, limit: int = 20) -> List[Dict]:
        """Search doc domain only."""
        cursor = self.conn.cursor()

        results = []
        seen_ids: Set[str] = set()

        # Exact
        cursor.execute("""
            SELECT * FROM symbols
            WHERE name = ? AND domain = 'doc'
            LIMIT ?
        """, (query, limit))

        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['score'] = 100
            result['match_type'] = 'exact'
            results.append(result)
            seen_ids.add(row['id'])

        # FTS (more important for docs than prefix)
        if len(results) < limit:
            excl, excl_params = self._exclusion_clause(seen_ids, col="s.id")
            try:
                cursor.execute(f"""
                    SELECT s.*, rank AS fts_rank FROM symbols s
                    JOIN symbols_fts ON symbols_fts.id = s.id
                    WHERE symbols_fts MATCH ? AND s.domain = 'doc'
                      AND {excl}
                    ORDER BY rank
                    LIMIT ?
                """, (query, *excl_params, limit - len(results)))

                for row in cursor.fetchall():
                    result = self._row_to_dict(row)
                    fts_rank = row['fts_rank'] if 'fts_rank' in row.keys() else 0
                    result['score'] = 50 + min(abs(fts_rank), 50)
                    result['match_type'] = 'fts'
                    results.append(result)
                    seen_ids.add(row['id'])
            except sqlite3.OperationalError:
                pass

        # Prefix
        if len(results) < limit:
            excl, excl_params = self._exclusion_clause(seen_ids)
            cursor.execute(f"""
                SELECT * FROM symbols
                WHERE name LIKE ? || '%' AND domain = 'doc'
                  AND {excl}
                LIMIT ?
            """, (query, *excl_params, limit - len(results)))

            for row in cursor.fetchall():
                result = self._row_to_dict(row)
                result['score'] = 75
                result['match_type'] = 'prefix'
                results.append(result)
                seen_ids.add(row['id'])

        return results

    def find_references(self, symbol_id: str) -> Dict:
        """Find bidirectional references for a symbol."""
        cursor = self.conn.cursor()

        # Outgoing refs (this symbol references others)
        # LEFT JOIN so orphan refs (target not in symbols) are still returned
        cursor.execute("""
            SELECT s.*, r.ref_type, r.target_id as _ref_peer_id, 'outgoing' as direction
            FROM symbol_refs r
            LEFT JOIN symbols s ON r.target_id = s.id
            WHERE r.source_id = ?
        """, (symbol_id,))

        outgoing = []
        for row in cursor.fetchall():
            if row['id'] is not None:
                result = self._row_to_dict(row)
            else:
                result = self._orphan_ref_dict(row['_ref_peer_id'])
            result['ref_type'] = row['ref_type']
            result['direction'] = 'outgoing'
            outgoing.append(result)

        # Incoming refs (others reference this symbol)
        # LEFT JOIN so orphan refs (source not in symbols) are still returned
        cursor.execute("""
            SELECT s.*, r.ref_type, r.source_id as _ref_peer_id, 'incoming' as direction
            FROM symbol_refs r
            LEFT JOIN symbols s ON r.source_id = s.id
            WHERE r.target_id = ?
        """, (symbol_id,))

        incoming = []
        for row in cursor.fetchall():
            if row['id'] is not None:
                result = self._row_to_dict(row)
            else:
                result = self._orphan_ref_dict(row['_ref_peer_id'])
            result['ref_type'] = row['ref_type']
            result['direction'] = 'incoming'
            incoming.append(result)

        return {'outgoing': outgoing, 'incoming': incoming}

    def list_refs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List reference edges with source and target symbol info."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.source_id, r.target_id, r.ref_type,
                   s1.name as source_name, s1.type as source_type, s1.file_path as source_file,
                   s2.name as target_name, s2.type as target_type, s2.file_path as target_file
            FROM symbol_refs r
            LEFT JOIN symbols s1 ON r.source_id = s1.id
            LEFT JOIN symbols s2 ON r.target_id = s2.id
            ORDER BY r.rowid
            LIMIT ? OFFSET ?
        """, (limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'source_id': row['source_id'],
                'target_id': row['target_id'],
                'ref_type': row['ref_type'],
                'source': {'name': row['source_name'] or row['source_id'], 'type': row['source_type'] or 'unknown', 'file_path': row['source_file'] or ''},
                'target': {'name': row['target_name'] or row['target_id'], 'type': row['target_type'] or 'unknown', 'file_path': row['target_file'] or ''}
            })
        return results

    def search_refs(self, query: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Search reference edges by symbol name or ref_type."""
        cursor = self.conn.cursor()
        pattern = f"%{query}%"
        cursor.execute("""
            SELECT r.source_id, r.target_id, r.ref_type,
                   s1.name as source_name, s1.type as source_type, s1.file_path as source_file,
                   s2.name as target_name, s2.type as target_type, s2.file_path as target_file
            FROM symbol_refs r
            LEFT JOIN symbols s1 ON r.source_id = s1.id
            LEFT JOIN symbols s2 ON r.target_id = s2.id
            WHERE COALESCE(s1.name, r.source_id) LIKE ? OR COALESCE(s2.name, r.target_id) LIKE ? OR r.ref_type LIKE ?
            ORDER BY r.rowid
            LIMIT ? OFFSET ?
        """, (pattern, pattern, pattern, limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'source_id': row['source_id'],
                'target_id': row['target_id'],
                'ref_type': row['ref_type'],
                'source': {'name': row['source_name'] or row['source_id'], 'type': row['source_type'] or 'unknown', 'file_path': row['source_file'] or ''},
                'target': {'name': row['target_name'] or row['target_id'], 'type': row['target_type'] or 'unknown', 'file_path': row['target_file'] or ''}
            })
        return results

    def blast_radius(self, symbol_id: str, max_depth: int = 3) -> Dict:
        """BFS traversal to find all downstream dependents."""
        cursor = self.conn.cursor()

        visited = set()
        by_depth = defaultdict(list)
        queue = deque([(symbol_id, 0)])

        while queue:
            current_id, depth = queue.popleft()

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)

            # Get symbol details
            cursor.execute("SELECT * FROM symbols WHERE id = ?", (current_id,))
            row = cursor.fetchone()
            if row:
                symbol = self._row_to_dict(row)
                by_depth[depth].append(symbol)

            # Find dependents (incoming refs)
            if depth < max_depth:
                cursor.execute("""
                    SELECT DISTINCT source_id FROM symbol_refs
                    WHERE target_id = ?
                """, (current_id,))

                for dep_row in cursor.fetchall():
                    dep_id = dep_row['source_id']
                    if dep_id not in visited:
                        queue.append((dep_id, depth + 1))

        return {
            'root_id': symbol_id,
            'max_depth': max_depth,
            'total_affected': len(visited),
            'by_depth': dict(by_depth)
        }

    def list_symbols(
        self,
        limit: int = 100,
        offset: int = 0,
        type_filter: Optional[str] = None,
        layer_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        domain_filter: Optional[str] = None
    ) -> List[Dict]:
        """List symbols with optional filters."""
        cursor = self.conn.cursor()

        conditions = []
        params = []

        if type_filter:
            conditions.append("type = ?")
            params.append(type_filter)

        if layer_filter:
            conditions.append("layer = ?")
            params.append(layer_filter)

        if category_filter:
            conditions.append("category = ?")
            params.append(category_filter)

        if domain_filter:
            conditions.append("domain = ?")
            params.append(domain_filter)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT * FROM symbols
            WHERE {where_clause}
            ORDER BY name
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append(self._row_to_dict(row))

        return results

    def get_symbol(self, symbol_id: str) -> Optional[Dict]:
        """Get symbol by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def update_symbol_metadata(self, symbol_id: str, updates: dict):
        """Merge updates into a symbol's metadata JSON blob."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT metadata FROM symbols WHERE id = ?", (symbol_id,))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            existing = json.loads(row['metadata'] or '{}')
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, TypeError):
            existing = {}
        existing.update(updates)
        cursor.execute("UPDATE symbols SET metadata = ?, updated_at = ? WHERE id = ?",
                       (json.dumps(existing), datetime.utcnow().isoformat(), symbol_id))
        self.conn.commit()
        return existing

    def get_categories(self) -> Dict:
        """
        Get category statistics with cross-category relationships.

        Uses pre-aggregated cache tables if available (populated during migration),
        falling back to live queries for older databases.

        Returns:
            {
                "categories": [{"name": "auth", "count": 45, "layers": {...}}, ...],
                "relationships": [{"from": "auth", "to": "user", "count": 12}, ...]
            }
        """
        cursor = self.conn.cursor()

        # Check if both cache tables exist
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name IN ('symbol_categories_cache', 'category_relationships_cache')
        """)
        has_cache = cursor.fetchone()[0] == 2

        if has_cache:
            return self._get_categories_cached(cursor)
        return self._get_categories_live(cursor)

    def _get_categories_cached(self, cursor) -> Dict:
        """Read from pre-aggregated cache tables, aggregating across domains."""
        cursor.execute("""
            SELECT category, symbol_count, layers
            FROM symbol_categories_cache
        """)

        # Aggregate across domains to match live behavior (which has no domain filter)
        cat_map = {}
        for row in cursor.fetchall():
            cat_name = row['category']
            try:
                row_layers = json.loads(row['layers']) if row['layers'] else {}
            except (json.JSONDecodeError, TypeError):
                row_layers = {}
            if cat_name not in cat_map:
                cat_map[cat_name] = {'count': 0, 'layers': {}}
            cat_map[cat_name]['count'] += row['symbol_count']
            for layer, cnt in row_layers.items():
                cat_map[cat_name]['layers'][layer] = cat_map[cat_name]['layers'].get(layer, 0) + cnt

        categories = sorted(
            [{'name': k, 'count': v['count'], 'layers': v['layers']} for k, v in cat_map.items()],
            key=lambda x: x['count'],
            reverse=True
        )

        # Cross-category relationships from cache
        cursor.execute("""
            SELECT from_category, to_category, ref_count
            FROM category_relationships_cache
            ORDER BY ref_count DESC
        """)

        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                'from': row['from_category'],
                'to': row['to_category'],
                'count': row['ref_count']
            })

        return {
            'categories': categories,
            'relationships': relationships
        }

    def _get_categories_live(self, cursor) -> Dict:
        """Fallback: live aggregation for databases without cache tables."""
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM symbols
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)

        categories = []
        for row in cursor.fetchall():
            cat_name = row['category']
            cat_count = row['count']

            # Get layer distribution for this category
            cursor.execute("""
                SELECT layer, COUNT(*) as count
                FROM symbols
                WHERE category = ?
                GROUP BY layer
            """, (cat_name,))

            layers = {layer_row['layer']: layer_row['count'] for layer_row in cursor.fetchall()}

            categories.append({
                'name': cat_name,
                'count': cat_count,
                'layers': layers
            })

        # Cross-category relationships
        cursor.execute("""
            SELECT
                s1.category as from_category,
                s2.category as to_category,
                COUNT(*) as count
            FROM symbol_refs r
            JOIN symbols s1 ON r.source_id = s1.id
            JOIN symbols s2 ON r.target_id = s2.id
            WHERE s1.category IS NOT NULL
              AND s2.category IS NOT NULL
              AND s1.category != s2.category
            GROUP BY s1.category, s2.category
            HAVING count > 2
            ORDER BY count DESC
        """)

        relationships = []
        for row in cursor.fetchall():
            relationships.append({
                'from': row['from_category'],
                'to': row['to_category'],
                'count': row['count']
            })

        return {
            'categories': categories,
            'relationships': relationships
        }

    def traverse(
        self,
        symbol_id: str,
        depth: int = 3,
        direction: str = 'both'
    ) -> Dict:
        """
        BFS graph traversal from a symbol.

        Args:
            symbol_id: Starting symbol ID
            depth: Maximum hops (default 3)
            direction: 'outgoing' (source→target), 'incoming' (target→source), 'both'

        Returns:
            {
                "root": {...symbol dict...},
                "nodes": [...symbol dicts...],
                "edges": [...ref dicts with source_id, target_id, ref_type...],
                "depth_reached": int,   # max depth actually visited
                "truncated": bool       # True if nodes at max_depth had unvisited neighbors
            }
        """
        if direction not in ('outgoing', 'incoming', 'both'):
            raise ValueError(f"Invalid direction: {direction}")

        cursor = self.conn.cursor()

        # Get root symbol
        cursor.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        root_row = cursor.fetchone()
        if not root_row:
            return {'root': None, 'nodes': [], 'edges': [], 'depth_reached': 0, 'truncated': False}

        root = self._row_to_dict(root_row)

        visited = set()
        nodes = []
        edges = []
        queue = deque([(symbol_id, 0)])
        depth_reached = 0
        truncated = False

        while queue:
            current_id, current_depth = queue.popleft()

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            if current_depth > depth_reached:
                depth_reached = current_depth

            # Get symbol details
            cursor.execute("SELECT * FROM symbols WHERE id = ?", (current_id,))
            row = cursor.fetchone()
            if row:
                nodes.append(self._row_to_dict(row))

            # Traverse based on direction
            if current_depth < depth:
                if direction in ('outgoing', 'both'):
                    cursor.execute("""
                        SELECT target_id, ref_type
                        FROM symbol_refs
                        WHERE source_id = ?
                    """, (current_id,))

                    for ref_row in cursor.fetchall():
                        target_id = ref_row['target_id']
                        edges.append({
                            'source_id': current_id,
                            'target_id': target_id,
                            'ref_type': ref_row['ref_type']
                        })
                        if target_id not in visited:
                            queue.append((target_id, current_depth + 1))

                if direction in ('incoming', 'both'):
                    cursor.execute("""
                        SELECT source_id, ref_type
                        FROM symbol_refs
                        WHERE target_id = ?
                    """, (current_id,))

                    for ref_row in cursor.fetchall():
                        source_id = ref_row['source_id']
                        edges.append({
                            'source_id': source_id,
                            'target_id': current_id,
                            'ref_type': ref_row['ref_type']
                        })
                        if source_id not in visited:
                            queue.append((source_id, current_depth + 1))

            elif current_depth == depth:
                # At the depth boundary: check if this node has unvisited neighbors
                if direction in ('outgoing', 'both'):
                    cursor.execute("""
                        SELECT target_id FROM symbol_refs WHERE source_id = ?
                    """, (current_id,))
                    if any(r['target_id'] not in visited for r in cursor.fetchall()):
                        truncated = True

                if direction in ('incoming', 'both'):
                    cursor.execute("""
                        SELECT source_id FROM symbol_refs WHERE target_id = ?
                    """, (current_id,))
                    if any(r['source_id'] not in visited for r in cursor.fetchall()):
                        truncated = True

        return {
            'root': root,
            'nodes': nodes,
            'edges': edges,
            'depth_reached': depth_reached,
            'truncated': truncated
        }

    def hotspots(
        self,
        limit: int = 20,
        offset: int = 0,
        layer_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        category_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Most-referenced symbols.

        Returns list of symbols with in_count, out_count, total_count.
        Sorted by total_count DESC.
        """
        cursor = self.conn.cursor()

        conditions = []
        params = []

        if layer_filter:
            conditions.append("s.layer = ?")
            params.append(layer_filter)

        if type_filter:
            conditions.append("s.type = ?")
            params.append(type_filter)

        if category_filter:
            conditions.append("s.category = ?")
            params.append(category_filter)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT
                s.*,
                COALESCE(incoming.count, 0) as in_count,
                COALESCE(outgoing.count, 0) as out_count,
                COALESCE(incoming.count, 0) + COALESCE(outgoing.count, 0) as total_count
            FROM symbols s
            LEFT JOIN (
                SELECT target_id, COUNT(*) as count
                FROM symbol_refs
                GROUP BY target_id
            ) incoming ON s.id = incoming.target_id
            LEFT JOIN (
                SELECT source_id, COUNT(*) as count
                FROM symbol_refs
                GROUP BY source_id
            ) outgoing ON s.id = outgoing.source_id
            WHERE {where_clause}
            ORDER BY total_count DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))

        results = []
        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['in_count'] = row['in_count']
            result['out_count'] = row['out_count']
            result['total_count'] = row['total_count']
            results.append(result)

        return results

    def impact_analysis(self, symbol_id: str) -> Dict:
        """
        Reverse lineage from a symbol (typically DB column) up to UI.

        Follows ref_type='maps_to' and 'binds_to' chains.

        Returns:
            {
                "root": {...symbol dict...},
                "layers": [{"layer": "data", "symbols": [...]}, ...],
                "paths": [[symbol_id1, symbol_id2, ...], ...]
            }
        """
        cursor = self.conn.cursor()

        # Get root symbol
        cursor.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        root_row = cursor.fetchone()
        if not root_row:
            return {'root': None, 'layers': [], 'paths': []}

        root = self._row_to_dict(root_row)

        # BFS traversal following maps_to and binds_to
        visited = set()
        by_layer = defaultdict(list)
        paths = []
        queue = deque([([symbol_id], symbol_id)])

        while queue:
            path, current_id = queue.popleft()

            if current_id in visited:
                continue

            visited.add(current_id)

            # Get symbol details
            cursor.execute("SELECT * FROM symbols WHERE id = ?", (current_id,))
            row = cursor.fetchone()
            if row:
                symbol = self._row_to_dict(row)
                by_layer[symbol['layer']].append(symbol)

            # Find upward references (incoming maps_to and binds_to)
            cursor.execute("""
                SELECT source_id, ref_type
                FROM symbol_refs
                WHERE target_id = ?
                  AND ref_type IN ('maps_to', 'binds_to')
            """, (current_id,))

            has_upstream = False
            for ref_row in cursor.fetchall():
                source_id = ref_row['source_id']
                if source_id not in visited:
                    new_path = path + [source_id]
                    queue.append((new_path, source_id))
                    has_upstream = True

            # If no upstream refs, this is a terminal path
            if not has_upstream and len(path) > 1:
                paths.append(path)

        # Convert by_layer to sorted list
        layers = []
        for layer_name in sorted(by_layer.keys()):
            layers.append({
                'layer': layer_name,
                'symbols': by_layer[layer_name]
            })

        return {
            'root': root,
            'layers': layers,
            'paths': paths
        }

    def list_lineage(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        List lineage paths from lineage_paths table.

        Joins with symbols for source/sink details.
        """
        cursor = self.conn.cursor()

        # Check if lineage_paths table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='lineage_paths'
        """)

        if not cursor.fetchone():
            return []

        cursor.execute("""
            SELECT
                lp.id,
                lp.source_id,
                lp.sink_id,
                lp.path_length,
                lp.min_confidence,
                lp.is_complete,
                s1.name as source_name,
                s1.qualified_name as source_qualified_name,
                s1.layer as source_layer,
                s2.name as sink_name,
                s2.qualified_name as sink_qualified_name,
                s2.layer as sink_layer
            FROM lineage_paths lp
            JOIN symbols s1 ON lp.source_id = s1.id
            JOIN symbols s2 ON lp.sink_id = s2.id
            ORDER BY lp.path_length DESC, lp.id
            LIMIT ? OFFSET ?
        """, (limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'source_id': row['source_id'],
                'sink_id': row['sink_id'],
                'path_length': row['path_length'],
                'min_confidence': row['min_confidence'],
                'is_complete': bool(row['is_complete']),
                'source': {
                    'name': row['source_name'],
                    'qualified_name': row['source_qualified_name'],
                    'layer': row['source_layer']
                },
                'sink': {
                    'name': row['sink_name'],
                    'qualified_name': row['sink_qualified_name'],
                    'layer': row['sink_layer']
                }
            })

        return results

    def search_lineage(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Search lineage paths by source/sink symbol names.

        WHERE source symbol name LIKE query OR sink symbol name LIKE query
        """
        cursor = self.conn.cursor()

        # Check if lineage_paths table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='lineage_paths'
        """)

        if not cursor.fetchone():
            return []

        cursor.execute("""
            SELECT
                lp.id,
                lp.source_id,
                lp.sink_id,
                lp.path_length,
                lp.min_confidence,
                lp.is_complete,
                s1.name as source_name,
                s1.qualified_name as source_qualified_name,
                s1.layer as source_layer,
                s2.name as sink_name,
                s2.qualified_name as sink_qualified_name,
                s2.layer as sink_layer
            FROM lineage_paths lp
            JOIN symbols s1 ON lp.source_id = s1.id
            JOIN symbols s2 ON lp.sink_id = s2.id
            WHERE s1.name LIKE '%' || ? || '%'
               OR s2.name LIKE '%' || ? || '%'
            ORDER BY lp.path_length DESC, lp.id
            LIMIT ? OFFSET ?
        """, (query, query, limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'source_id': row['source_id'],
                'sink_id': row['sink_id'],
                'path_length': row['path_length'],
                'min_confidence': row['min_confidence'],
                'is_complete': bool(row['is_complete']),
                'source': {
                    'name': row['source_name'],
                    'qualified_name': row['source_qualified_name'],
                    'layer': row['source_layer']
                },
                'sink': {
                    'name': row['sink_name'],
                    'qualified_name': row['sink_qualified_name'],
                    'layer': row['sink_layer']
                }
            })

        return results

    def list_services(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        List service nodes enriched with connection counts.

        Joins with service_connections for connection stats.
        """
        cursor = self.conn.cursor()

        # Check if service_nodes table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='service_nodes'
        """)

        if not cursor.fetchone():
            return []

        cursor.execute("""
            SELECT
                sn.id,
                sn.name,
                sn.type,
                sn.metadata,
                COUNT(DISTINCT sc_out.id) as outgoing_connections,
                COUNT(DISTINCT sc_in.id) as incoming_connections
            FROM service_nodes sn
            LEFT JOIN service_connections sc_out ON sn.id = sc_out.source_service_id
            LEFT JOIN service_connections sc_in ON sn.id = sc_in.target_service_id
            GROUP BY sn.id, sn.name, sn.type, sn.metadata
            ORDER BY sn.name
            LIMIT ? OFFSET ?
        """, (limit, offset))

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'name': row['name'],
                'type': row['type'],
                'metadata': self._parse_metadata(row['metadata']),
                'outgoing_connections': row['outgoing_connections'],
                'incoming_connections': row['incoming_connections']
            })

        return results

    def get_stats(self) -> Dict:
        """
        Aggregate statistics about the unified DB.

        Returns:
            {
                "total_symbols": int,
                "total_refs": int,
                "by_type": {...},
                "by_layer": {...},
                "by_domain": {...},
                "by_ref_type": {...},
                "lineage_paths": int,
                "services": int
            }
        """
        cursor = self.conn.cursor()

        stats = {}

        # Total symbols
        cursor.execute("SELECT COUNT(*) as count FROM symbols")
        stats['total_symbols'] = cursor.fetchone()['count']

        # Total refs
        cursor.execute("SELECT COUNT(*) as count FROM symbol_refs")
        stats['total_refs'] = cursor.fetchone()['count']

        # By type
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM symbols
            GROUP BY type
            ORDER BY count DESC
        """)
        stats['by_type'] = {row['type']: row['count'] for row in cursor.fetchall()}

        # By layer
        cursor.execute("""
            SELECT layer, COUNT(*) as count
            FROM symbols
            GROUP BY layer
            ORDER BY count DESC
        """)
        stats['by_layer'] = {row['layer']: row['count'] for row in cursor.fetchall()}

        # By domain
        cursor.execute("""
            SELECT domain, COUNT(*) as count
            FROM symbols
            GROUP BY domain
            ORDER BY count DESC
        """)
        stats['by_domain'] = {row['domain']: row['count'] for row in cursor.fetchall()}

        # By ref_type
        cursor.execute("""
            SELECT ref_type, COUNT(*) as count
            FROM symbol_refs
            GROUP BY ref_type
            ORDER BY count DESC
        """)
        stats['by_ref_type'] = {row['ref_type']: row['count'] for row in cursor.fetchall()}

        # Lineage paths count (if table exists)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='lineage_paths'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM lineage_paths")
            stats['lineage_paths'] = cursor.fetchone()['count']
        else:
            stats['lineage_paths'] = 0

        # Services count (if table exists)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='service_nodes'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) as count FROM service_nodes")
            stats['services'] = cursor.fetchone()['count']
        else:
            stats['services'] = 0

        return stats

    def get_symbol_with_refs(self, symbol_id: str) -> Optional[Dict]:
        """
        Get a single symbol enriched with dependencies and dependents.

        Queries symbol_refs for outgoing (dependencies) and incoming (dependents).

        Returns symbol dict with:
            - dependencies: list of {symbol, ref_type}
            - dependents: list of {symbol, ref_type}
        """
        cursor = self.conn.cursor()

        # Get base symbol
        cursor.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        row = cursor.fetchone()
        if not row:
            return None

        symbol = self._row_to_dict(row)

        # Get dependencies (outgoing refs)
        # LEFT JOIN so orphan refs (target not in symbols) are still returned
        cursor.execute("""
            SELECT s.*, r.ref_type, r.target_id as _ref_peer_id
            FROM symbol_refs r
            LEFT JOIN symbols s ON r.target_id = s.id
            WHERE r.source_id = ?
        """, (symbol_id,))

        dependencies = []
        for dep_row in cursor.fetchall():
            dep = self._row_to_dict(dep_row) if dep_row['id'] is not None else self._orphan_ref_dict(dep_row['_ref_peer_id'])
            dependencies.append({
                'symbol': dep,
                'ref_type': dep_row['ref_type']
            })

        # Get dependents (incoming refs)
        # LEFT JOIN so orphan refs (source not in symbols) are still returned
        cursor.execute("""
            SELECT s.*, r.ref_type, r.source_id as _ref_peer_id
            FROM symbol_refs r
            LEFT JOIN symbols s ON r.source_id = s.id
            WHERE r.target_id = ?
        """, (symbol_id,))

        dependents = []
        for dep_row in cursor.fetchall():
            dep = self._row_to_dict(dep_row) if dep_row['id'] is not None else self._orphan_ref_dict(dep_row['_ref_peer_id'])
            dependents.append({
                'symbol': dep,
                'ref_type': dep_row['ref_type']
            })

        symbol['dependencies'] = dependencies
        symbol['dependents'] = dependents

        return symbol

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """CLI for testing query engine."""
    import argparse

    parser = argparse.ArgumentParser(description='Query unified SQLite index')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--search', help='Search query')
    parser.add_argument('--refs', help='Find references for symbol ID')
    parser.add_argument('--blast-radius', help='Blast radius for symbol ID')
    parser.add_argument('--categories', action='store_true', help='Get category stats')
    parser.add_argument('--limit', type=int, default=20, help='Result limit')

    args = parser.parse_args()

    with UnifiedQueryEngine(args.db) as engine:
        if args.search:
            results = engine.search_all(args.search, limit=args.limit)
            print(json.dumps(results, indent=2))

        elif args.refs:
            refs = engine.find_references(args.refs)
            print(json.dumps(refs, indent=2))

        elif args.blast_radius:
            radius = engine.blast_radius(args.blast_radius)
            print(json.dumps(radius, indent=2))

        elif args.categories:
            categories = engine.get_categories()
            print(json.dumps(categories, indent=2))

        else:
            print("Specify --search, --refs, --blast-radius, or --categories")


if __name__ == '__main__':
    main()
