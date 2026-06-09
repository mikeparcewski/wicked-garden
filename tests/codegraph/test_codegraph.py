"""Tests for the codegraph peer shim + the injected-edge extractor.

The shim (`_codegraph.resolve_codegraph`) mirrors `_loom.resolve_loom`: env →
config → PATH → node_modules → npx, with an empty `WICKED_CODEGRAPH_BIN` as the
kill-switch. The extractor (`scripts/codegraph/inject_edges.py`) materializes the
bus producer→consumer edges grep + the static graph miss; we test it against a
temp SQLite shaped like codegraph's, so it needs neither codegraph nor peers.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "scripts", _REPO / "scripts" / "codegraph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _codegraph as cg  # noqa: E402
import inject_edges as ie  # noqa: E402


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("WICKED_CODEGRAPH_BIN")
        os.environ.pop("WICKED_CODEGRAPH_BIN", None)

    def tearDown(self):
        os.environ.pop("WICKED_CODEGRAPH_BIN", None)
        if self._saved is not None:
            os.environ["WICKED_CODEGRAPH_BIN"] = self._saved

    def test_env_override_wins(self):
        os.environ["WICKED_CODEGRAPH_BIN"] = "/opt/custom/codegraph"
        self.assertEqual(cg.resolve_codegraph(), ["/opt/custom/codegraph"])

    def test_empty_env_is_killswitch(self):
        os.environ["WICKED_CODEGRAPH_BIN"] = ""
        self.assertIsNone(cg.resolve_codegraph())

    def test_mjs_override_invoked_via_node(self):
        os.environ["WICKED_CODEGRAPH_BIN"] = "/some/codegraph.mjs"
        self.assertEqual(cg.resolve_codegraph(), ["node", "/some/codegraph.mjs"])

    def test_npx_fallback_when_not_on_path(self):
        import shutil
        with patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertEqual(cg.resolve_codegraph(),
                             ["npx", "-y", "@colbymchenry/codegraph"])

    def test_available_excludes_npx(self):
        import shutil
        with patch.object(shutil, "which",
                          side_effect=lambda b: "/usr/bin/npx" if b == "npx" else None):
            self.assertFalse(cg.codegraph_available())

    def test_db_path(self):
        self.assertEqual(cg.db_path(Path("/x")), Path("/x/.codegraph/codegraph.db"))


def _codegraph_shaped_db(path: str, file_relpaths):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT, file_path TEXT)")
    conn.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, "
                 "target TEXT, kind TEXT, metadata TEXT, line INT, col INT, provenance TEXT)")
    for rel in file_relpaths:
        conn.execute("INSERT INTO nodes (id, kind, name, file_path) VALUES (?,?,?,?)",
                     (f"file:{rel}", "file", rel, rel))
    conn.commit()
    conn.close()


class InjectEdgesTests(unittest.TestCase):
    def test_consumers_parsed_from_registry(self):
        consumers = ie._consumers()
        self.assertTrue(consumers, "no bus consumers parsed from _bus_consumers.json")
        ev, mod = consumers[0]
        self.assertTrue(ev.startswith("wicked.") or ev.startswith("wg."))
        self.assertTrue(mod.endswith(".py"))

    def test_injects_producer_to_consumer_edge(self):
        # Use a real (event, consumer-module) from the registry and a real producer
        # that references that event string, both present as file nodes in the db.
        consumers = ie._consumers()
        events = {e for e, _ in consumers}
        producers = ie._producers_for(events)
        # pick an event that has both a producer and a consumer module that exists
        chosen = None
        for ev, mod in consumers:
            prods = {p for p in producers.get(ev, set()) if (_REPO / mod).exists()
                     and (_REPO / p).exists()}
            if prods and (_REPO / mod).exists():
                chosen = (ev, mod, sorted(prods)[0])
                break
        if chosen is None:
            self.skipTest("no event with both a real producer file and an existing consumer module")
        ev, mod, prod = chosen

        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [mod, prod])
            stats = ie.inject(Path(dbp))
            self.assertGreaterEqual(stats["edges_added"], 1)
            conn = sqlite3.connect(dbp)
            row = conn.execute(
                "SELECT source, target, provenance FROM edges WHERE provenance='injected:bus'"
            ).fetchone()
            conn.close()
            self.assertIsNotNone(row, "no injected:bus edge created")
            self.assertEqual(row[0], f"file:{prod}")
            self.assertEqual(row[1], f"file:{mod}")

    def test_inject_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            # nodes for every consumer module + every producer, so edges are created
            consumers = ie._consumers()
            events = {e for e, _ in consumers}
            producers = ie._producers_for(events)
            rels = {m for _, m in consumers} | {p for s in producers.values() for p in s}
            _codegraph_shaped_db(dbp, sorted(rels))
            n1 = ie.inject(Path(dbp))["edges_added"]
            n2 = ie.inject(Path(dbp))["edges_added"]
            self.assertEqual(n1, n2)  # re-run replaces, does not duplicate
            conn = sqlite3.connect(dbp)
            total = conn.execute(
                "SELECT count(*) FROM edges WHERE provenance='injected:bus'").fetchone()[0]
            conn.close()
            self.assertEqual(total, n2)


if __name__ == "__main__":
    unittest.main()
