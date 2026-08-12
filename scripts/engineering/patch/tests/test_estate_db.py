"""Tests for estate_db — the adapter that feeds wicked-patch by translating a
wicked-estate SQLite store into the symbol-graph schema patch's --db expects
(ADR 0005, retarget inventory entry A3).

The primary fixture is `fixtures/estate_store.sql`: a dump of a REAL store built
by `wicked-estate index` (v0.14.4) over `fixtures/estate_repo/` — the schema and
row shapes are authentic, not hand-faked. A live test additionally runs the real
binary when it is on PATH (skipped otherwise, e.g. in CI).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import estate_db  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_STORE_SQL = _FIXTURES / "estate_store.sql"
_FIXTURE_REPO = _FIXTURES / "estate_repo"

# Counts for fixtures/estate_store.sql (12 nodes / 13 edges; see the dump header).
_EXPECTED = {
    "symbols": 12,
    "refs": 13,
    "symbol_refs": 0,
    "symbol_calls": 4,
    "symbol_imports": 1,
    "symbol_bases": 0,
}


def _estate_store_from_dump(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(_STORE_SQL.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


class EstateDbAdapterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = str(Path(self._tmp.name) / "estate.db")
        self.out = str(Path(self._tmp.name) / "patch-symbols.db")
        _estate_store_from_dump(self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def _build(self):
        return estate_db.build_patch_db(Path(self.store), Path(self.out))

    def test_translates_nodes_and_edges(self):
        counts = self._build()
        self.assertEqual(counts, _EXPECTED)

    def test_symbols_schema_matches_patch_expectations(self):
        self._build()
        c = sqlite3.connect(self.out)
        cols = {r[1] for r in c.execute("pragma table_info(symbols)")}
        self.assertTrue({"id", "name", "type", "file_path", "line_start", "line_end",
                         "metadata", "layer"} <= cols)
        # symbol_bases is queried by PropagationEngine (tolerated missing, but we ship it)
        base_cols = {r[1] for r in c.execute("pragma table_info(symbol_bases)")}
        self.assertEqual(base_cols, {"symbol_id", "base_id"})
        c.close()

    def test_patch_native_id_scheme(self):
        """Estate SCIP-style syms translate to the patch family's file::Name ids
        (File nodes: the bare path) — the scheme patch.py documents and the
        PropagationEngine's '::'-keyed cross-language discovery expects."""
        self._build()
        c = sqlite3.connect(self.out)
        ids = {row[0] for row in c.execute("SELECT id FROM symbols")}
        self.assertIn("src/app.py::Order", ids)
        self.assertIn("src/calc.py::add", ids)
        self.assertIn("src/calc.py", ids)  # File node keeps the bare path
        # No raw estate sym leaks into node ids
        self.assertFalse([i for i in ids if " . " in i], "estate syms must be translated")
        # The estate sym is preserved in metadata for traceability
        (meta,) = c.execute(
            "SELECT metadata FROM symbols WHERE id = 'src/app.py::Order'"
        ).fetchone()
        self.assertEqual(json.loads(meta)["estate_symbol"],
                         "ts-python . . . src/app/Order#")
        c.close()

    def test_edges_reference_translated_ids(self):
        self._build()
        c = sqlite3.connect(self.out)
        calls = set(c.execute("SELECT symbol_id, target_id FROM symbol_calls"))
        self.assertIn(("src/app.py::total", "src/calc.py::add"), calls)
        self.assertIn(("src/calc.py::multiply", "src/calc.py::add"), calls)
        imports = set(c.execute("SELECT symbol_id, target_id FROM symbol_imports"))
        self.assertIn(("src/app.py", "src/app.py::calc"), imports)
        # every edge kind lands in refs (contains included), decoded to plain strings
        ref_types = {row[0] for row in c.execute("SELECT DISTINCT ref_type FROM refs")}
        self.assertEqual(ref_types, {"contains", "calls", "imports"})
        c.close()

    def test_lines_are_one_based(self):
        """Estate spans are 0-based tree-sitter rows; the patch contract
        (generators/base.py) is 1-based inclusive — verify against the real file."""
        self._build()
        c = sqlite3.connect(self.out)
        line_start, line_end = c.execute(
            "SELECT line_start, line_end FROM symbols WHERE id = 'src/calc.py::add'"
        ).fetchone()
        c.close()
        source_lines = (_FIXTURE_REPO / "src" / "calc.py").read_text().splitlines()
        self.assertEqual(source_lines[line_start - 1].strip(), "def add(a, b):",
                         "line_start must be the 1-based line of the def")
        self.assertGreaterEqual(line_end, line_start)

    def test_metadata_is_valid_json(self):
        # PropagationEngine does json.loads(metadata or "{}") — must be JSON or NULL.
        self._build()
        c = sqlite3.connect(self.out)
        for (meta,) in c.execute("SELECT metadata FROM symbols"):
            json.loads(meta or "{}")  # must not raise
        c.close()

    def test_other_edge_kind_decodes_to_inner_string(self):
        """EdgeKind::Other(String) serializes as {"other":"<kind>"} (estate edge.rs,
        serde external tagging) — injected edges must surface under their real kind."""
        c = sqlite3.connect(self.store)
        c.execute(
            "INSERT INTO edges (source,target,kind,confidence,file,data,evidence_count)"
            " VALUES (2, 3, '{\"other\":\"emits\"}', 0.9, 'src/calc.py', '{}', 0)"
        )
        c.commit()
        c.close()
        counts = self._build()
        self.assertEqual(counts["refs"], _EXPECTED["refs"] + 1)
        c = sqlite3.connect(self.out)
        row = c.execute("SELECT source_id, target_id FROM refs WHERE ref_type='emits'").fetchone()
        c.close()
        self.assertIsNotNone(row, "Other(\"emits\") must decode to ref_type 'emits'")

    def test_id_collisions_disambiguate_deterministically(self):
        """Two nodes with the same file+name (e.g. overloads) must not collapse:
        the later sym (estate-sym order) gets a #2 suffix, stable across rebuilds."""
        c = sqlite3.connect(self.store)
        c.execute("INSERT INTO symbols (sym) VALUES ('zz-test . . . src/app/Order(dup)#')")
        sid = c.execute(
            "SELECT sid FROM symbols WHERE sym = 'zz-test . . . src/app/Order(dup)#'"
        ).fetchone()[0]
        dup_node = {
            "symbol": "zz-test . . . src/app/Order(dup)#",
            "kind": "class", "name": "Order", "language": "python",
            "location": {"file": "src/app.py",
                         "span": {"start_byte": 0, "end_byte": 0, "start_line": 30,
                                  "start_col": 0, "end_line": 32, "end_col": 0}},
            "metadata": {},
        }
        c.execute(
            "INSERT INTO nodes (symbol,name,kind,language,file,data) VALUES (?,?,?,?,?,?)",
            (sid, "Order", '"class"', "python", "src/app.py", json.dumps(dup_node)),
        )
        c.commit()
        c.close()
        first = self._build()
        conn = sqlite3.connect(self.out)
        rows = dict(conn.execute(
            "SELECT id, metadata FROM symbols WHERE id LIKE 'src/app.py::Order%'"
        ))
        conn.close()
        self.assertEqual(set(rows), {"src/app.py::Order", "src/app.py::Order#2"})
        # 'ts-python …' sorts before 'zz-test …' → the original keeps the base id
        self.assertEqual(json.loads(rows["src/app.py::Order"])["estate_symbol"],
                         "ts-python . . . src/app/Order#")
        self.assertEqual(self._build(), first, "disambiguation must be deterministic")

    def test_schema_probe_rejects_brain_era_codegraph_db(self):
        legacy = str(Path(self._tmp.name) / "codegraph.db")
        c = sqlite3.connect(legacy)
        c.executescript(
            """
            CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT,
              file_path TEXT, start_line INT, end_line INT, signature TEXT);
            CREATE TABLE edges (source TEXT, target TEXT, kind TEXT);
            """
        )
        c.close()
        with self.assertRaises(estate_db.EstateSchemaError) as ctx:
            estate_db.build_patch_db(Path(legacy), Path(self.out))
        msg = str(ctx.exception)
        self.assertIn("codegraph", msg)
        self.assertIn("wicked-estate index", msg)

    def test_schema_probe_rejects_arbitrary_sqlite(self):
        other = str(Path(self._tmp.name) / "other.db")
        sqlite3.connect(other).close()
        with self.assertRaises(estate_db.EstateSchemaError) as ctx:
            estate_db.build_patch_db(Path(other), Path(self.out))
        msg = str(ctx.exception)
        self.assertIn("missing table 'nodes'", msg)
        self.assertIn("schema.sql", msg, "the error must name the estate contract")

    def test_missing_store_raises_with_build_hint(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            estate_db.build_patch_db(Path(self._tmp.name) / "nope.db", Path(self.out))
        self.assertIn("wicked-estate index", str(ctx.exception))

    def test_idempotent_rebuild(self):
        a = self._build()
        b = self._build()  # rebuilds from scratch
        self.assertEqual(a, b)

    def test_resolve_estate_db_precedence(self):
        cwd = os.getcwd()
        env_before = os.environ.get(estate_db.ESTATE_DB_ENV)
        try:
            os.chdir(self._tmp.name)
            os.environ.pop(estate_db.ESTATE_DB_ENV, None)
            # explicit flag wins
            self.assertEqual(estate_db.resolve_estate_db("x.db"), Path("x.db"))
            # env var next
            os.environ[estate_db.ESTATE_DB_ENV] = "env.db"
            self.assertEqual(estate_db.resolve_estate_db(None), Path("env.db"))
            os.environ.pop(estate_db.ESTATE_DB_ENV)
            # then the first existing conventional path
            Path(".wicked-estate").mkdir()
            Path(".wicked-estate/graph.db").touch()
            self.assertEqual(estate_db.resolve_estate_db(None),
                             Path(".wicked-estate/graph.db"))
            Path(".codegraph").mkdir()
            Path(".codegraph/estate.db").touch()
            self.assertEqual(estate_db.resolve_estate_db(None),
                             Path(".codegraph/estate.db"))
        finally:
            os.chdir(cwd)
            if env_before is None:
                os.environ.pop(estate_db.ESTATE_DB_ENV, None)
            else:
                os.environ[estate_db.ESTATE_DB_ENV] = env_before


@unittest.skipUnless(shutil.which("wicked-estate"),
                     "wicked-estate binary not on PATH (dump fixture covers CI)")
class EstateDbLiveIndexTests(unittest.TestCase):
    """Cross-check the checked-in dump against a store built by the REAL binary."""

    def test_live_index_translates_like_the_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "estate.db"
            out = Path(tmp) / "patch-symbols.db"
            subprocess.run(
                ["wicked-estate", "index", str(_FIXTURE_REPO), "--db", str(store)],
                check=True, capture_output=True, text=True, timeout=120,
            )
            counts = estate_db.build_patch_db(store, out)
            # Tolerate a newer estate emitting MORE than the pinned dump, never less.
            for key, expected in _EXPECTED.items():
                self.assertGreaterEqual(counts[key], expected,
                                        f"live index regressed {key}")
            c = sqlite3.connect(str(out))
            ids = {row[0] for row in c.execute("SELECT id FROM symbols")}
            c.close()
            self.assertLessEqual({"src/calc.py::add", "src/app.py::Order",
                                  "src/util.ts::Order"}, ids)


if __name__ == "__main__":
    unittest.main()
