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
            'file': row['file_path'],
            'line_start': row['line_start'],
            'line_end': row['line_end'],
            'domain': row['domain'],
            'layer': row['layer'],
            'category': row['category'],
            'content': row['content'],
            'metadata': self._parse_metadata(row['metadata'])
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

    def find_references(self, symbol_id: str) -> List[Dict]:
        """Find bidirectional references for a symbol."""
        cursor = self.conn.cursor()

        # Outgoing refs (this symbol references others)
        cursor.execute("""
            SELECT s.*, r.ref_type, 'outgoing' as direction
            FROM symbol_refs r
            JOIN symbols s ON r.target_id = s.id
            WHERE r.source_id = ?
        """, (symbol_id,))

        outgoing = []
        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['ref_type'] = row['ref_type']
            result['direction'] = 'outgoing'
            outgoing.append(result)

        # Incoming refs (others reference this symbol)
        cursor.execute("""
            SELECT s.*, r.ref_type, 'incoming' as direction
            FROM symbol_refs r
            JOIN symbols s ON r.source_id = s.id
            WHERE r.target_id = ?
        """, (symbol_id,))

        incoming = []
        for row in cursor.fetchall():
            result = self._row_to_dict(row)
            result['ref_type'] = row['ref_type']
            result['direction'] = 'incoming'
            incoming.append(result)

        return {'outgoing': outgoing, 'incoming': incoming}

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

    def get_categories(self) -> Dict:
        """
        Get category statistics with cross-category relationships.

        Returns:
            {
                "categories": [{"name": "auth", "count": 45, "layers": {...}}, ...],
                "relationships": [{"from": "auth", "to": "user", "count": 12}, ...]
            }
        """
        cursor = self.conn.cursor()

        # Category stats
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
