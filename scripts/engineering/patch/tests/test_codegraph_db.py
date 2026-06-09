"""Tests for codegraph_db — the adapter that revives wicked-patch by translating
codegraph's SQLite into the symbol-graph schema patch's --db expects.

Built against a temp codegraph-shaped DB (no codegraph/peers needed), asserting
the patch-side schema (symbols + refs/symbol_calls/symbol_imports + metadata) is
populated and that metadata is valid JSON (PropagationEngine json.loads it).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import codegraph_db as cgdb  # noqa: E402


def _codegraph_shaped_db(path: str):
    c = sqlite3.connect(path)
    c.executescript(
        """
        CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, qualified_name TEXT,
          file_path TEXT, language TEXT, start_line INT, end_line INT, start_column INT,
          end_column INT, docstring TEXT, signature TEXT);
        CREATE TABLE edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, target TEXT,
          kind TEXT, metadata TEXT, line INT, col INT, provenance TEXT);
        """
    )
    c.execute("INSERT INTO nodes (id,kind,name,file_path,start_line,end_line,signature) "
              "VALUES ('function:a','function','add','src/calc.py',1,2,'def add(a, b)')")
    c.execute("INSERT INTO nodes (id,kind,name,file_path,start_line,end_line,signature) "
              "VALUES ('function:b','function','main','src/app.py',5,9,NULL)")
    c.execute("INSERT INTO edges (source,target,kind) VALUES ('function:b','function:a','calls')")
    c.execute("INSERT INTO edges (source,target,kind) VALUES ('function:b','function:a','references')")
    c.execute("INSERT INTO edges (source,target,kind) VALUES ('function:b','import:x','imports')")
    c.commit()
    c.close()


class CodegraphDbAdapterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cg = str(Path(self._tmp.name) / "codegraph.db")
        self.out = str(Path(self._tmp.name) / "patch-symbols.db")
        _codegraph_shaped_db(self.cg)

    def tearDown(self):
        self._tmp.cleanup()

    def test_translates_nodes_and_edges(self):
        counts = cgdb.build_patch_db(Path(self.cg), Path(self.out))
        self.assertEqual(counts["symbols"], 2)
        self.assertEqual(counts["symbol_calls"], 1)
        self.assertEqual(counts["symbol_refs"], 1)
        self.assertEqual(counts["symbol_imports"], 1)
        self.assertEqual(counts["refs"], 3)

    def test_symbols_schema_matches_patch_expectations(self):
        cgdb.build_patch_db(Path(self.cg), Path(self.out))
        c = sqlite3.connect(self.out)
        cols = {r[1] for r in c.execute("pragma table_info(symbols)")}
        self.assertTrue({"id", "name", "type", "file_path", "line_start", "line_end",
                         "metadata", "layer"} <= cols)
        # _resolve_symbol_id does: SELECT id FROM symbols WHERE id LIKE ?
        row = c.execute("SELECT id FROM symbols WHERE id LIKE ? LIMIT 1", ("function:a",)).fetchone()
        self.assertIsNotNone(row)
        c.close()

    def test_metadata_is_valid_json(self):
        # PropagationEngine does json.loads(metadata or "{}") — a raw signature
        # string would crash it. Confirm it's JSON (or NULL).
        cgdb.build_patch_db(Path(self.cg), Path(self.out))
        c = sqlite3.connect(self.out)
        for (meta,) in c.execute("SELECT metadata FROM symbols"):
            json.loads(meta or "{}")  # must not raise
        c.close()

    def test_idempotent_rebuild(self):
        a = cgdb.build_patch_db(Path(self.cg), Path(self.out))
        b = cgdb.build_patch_db(Path(self.cg), Path(self.out))  # rebuilds from scratch
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
