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
import _graph_nodes as gn  # noqa: E402
import inject_all as iall  # noqa: E402
import inject_capability_edges as ice  # noqa: E402
import inject_dispatch_edges as idis  # noqa: E402
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
    """Create a db with codegraph's REAL nodes/edges schema (incl. its NOT NULL
    columns), so self-noding INSERTs are exercised exactly as against a live graph."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, "
        "qualified_name TEXT NOT NULL, file_path TEXT NOT NULL, language TEXT NOT NULL, "
        "start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, start_column INTEGER NOT NULL, "
        "end_column INTEGER NOT NULL, docstring TEXT, signature TEXT, visibility TEXT, "
        "is_exported INTEGER, is_async INTEGER, is_static INTEGER, is_abstract INTEGER, "
        "decorators TEXT, type_parameters TEXT, updated_at INTEGER NOT NULL)"
    )
    conn.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, "
                 "target TEXT NOT NULL, kind TEXT NOT NULL, metadata TEXT, line INT, col INT, "
                 "provenance TEXT)")
    for rel in file_relpaths:
        conn.execute(
            "INSERT INTO nodes (id, kind, name, qualified_name, file_path, language, "
            "start_line, end_line, start_column, end_column, updated_at) "
            "VALUES (?, 'file', ?, ?, ?, 'python', 1, 1, 0, 0, 0)",
            (f"file:{rel}", rel, rel, rel))
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


class InjectDispatchEdgesTests(unittest.TestCase):
    """command→agent dispatch edges (provenance='injected:dispatch').

    A command names its subagent through a `subagent_type` string handle; the
    command file never references the agent's file or any symbol — so grep/static
    call-graphs can't link them. The extractor resolves the handle to the agent
    file and materializes the edge."""

    def test_dispatches_resolve_handles_to_existing_agent_files(self):
        dispatches = idis._dispatches()
        self.assertTrue(dispatches, "no command→agent dispatches resolved from commands/")
        cmd_rel, agent_rel, handle = dispatches[0]
        self.assertTrue(cmd_rel.startswith("commands/") and cmd_rel.endswith(".md"))
        self.assertTrue(agent_rel.startswith("agents/") and agent_rel.endswith(".md"))
        self.assertTrue(handle.startswith("wicked-garden:"))
        self.assertTrue((_REPO / agent_rel).exists(), "resolved agent file must exist")

    def test_handle_resolution_skips_non_agent_references(self):
        # A `wicked-garden:<domain>:<name>` handle that names a command/skill (not an
        # agent) resolves to no agents/... file → None (so its edge is never created).
        self.assertIsNone(idis._agent_relpath_for("wicked-garden:search:lineage"))
        # A real agent handle resolves to its file.
        self.assertEqual(
            idis._agent_relpath_for("wicked-garden:platform:security-engineer"),
            "agents/platform/security-engineer.md",
        )

    def test_injects_command_to_agent_edge(self):
        dispatches = idis._dispatches()
        if not dispatches:
            self.skipTest("no resolvable command→agent dispatch")
        cmd_rel, agent_rel, handle = dispatches[0]
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [cmd_rel, agent_rel])
            stats = idis.inject(Path(dbp))
            self.assertGreaterEqual(stats["edges_added"], 1)
            conn = sqlite3.connect(dbp)
            row = conn.execute(
                "SELECT source, target, provenance FROM edges "
                "WHERE provenance='injected:dispatch'"
            ).fetchone()
            conn.close()
            self.assertIsNotNone(row, "no injected:dispatch edge created")
            self.assertEqual(row[0], f"file:{cmd_rel}")
            self.assertEqual(row[1], f"file:{agent_rel}")

    def test_self_nodes_md_files_when_absent_issue_916(self):
        # codegraph indexes CODE, not the .md command/agent files — so in a real
        # graph NEITHER node exists. The extractor must self-node both and still
        # create the edge. The old behavior (skip when the node was absent) left the
        # entire command→agent layer empty for this markdown-defined plugin (#916).
        dispatches = idis._dispatches()
        if not dispatches:
            self.skipTest("no resolvable command→agent dispatch")
        cmd_rel, agent_rel, _handle = dispatches[0]
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [])  # empty graph — no .md nodes, as codegraph leaves it
            stats = idis.inject(Path(dbp))
            self.assertGreaterEqual(stats["edges_added"], 1)
            self.assertEqual(stats["skipped"], 0)
            conn = sqlite3.connect(dbp)
            edge = conn.execute(
                "SELECT 1 FROM edges WHERE provenance='injected:dispatch' "
                "AND source=? AND target=?", (f"file:{cmd_rel}", f"file:{agent_rel}")
            ).fetchone()
            src_node = conn.execute("SELECT 1 FROM nodes WHERE id=?", (f"file:{cmd_rel}",)).fetchone()
            tgt_node = conn.execute("SELECT 1 FROM nodes WHERE id=?", (f"file:{agent_rel}",)).fetchone()
            conn.close()
            self.assertIsNotNone(edge, "dispatch edge not created from self-noded .md files")
            self.assertIsNotNone(src_node, "command .md was not self-noded")
            self.assertIsNotNone(tgt_node, "agent .md was not self-noded")

    def test_inject_is_idempotent(self):
        dispatches = idis._dispatches()
        rels = {c for c, _, _ in dispatches} | {a for _, a, _ in dispatches}
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, sorted(rels))
            n1 = idis.inject(Path(dbp))["edges_added"]
            n2 = idis.inject(Path(dbp))["edges_added"]
            self.assertEqual(n1, n2)  # re-run replaces, does not duplicate
            conn = sqlite3.connect(dbp)
            total = conn.execute(
                "SELECT count(*) FROM edges WHERE provenance='injected:dispatch'"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(total, n2)


class InjectCapabilityEdgesTests(unittest.TestCase):
    """agent→capability edges (provenance='injected:capability').

    An agent declares the capabilities it needs via `tool-capabilities:`; each is
    defined in CAPABILITY_REGISTRY. The agent markdown never references the registry
    module — the link is a YAML string keyed against a Python dict. The extractor
    materializes a synthetic `capability:<name>` node + the agent→capability edge."""

    def test_declared_capabilities_subset_of_registry(self):
        pairs = ice._agent_capabilities()
        self.assertTrue(pairs, "no agent→capability pairs resolved from agents/")
        known = ice._registry_capabilities()
        self.assertTrue(known, "CAPABILITY_REGISTRY did not import")
        for _agent, cap in pairs:
            # Only registry-defined capabilities are emitted (no fabrication).
            self.assertIn(cap, known)

    def test_skips_capability_absent_from_registry(self):
        # A `tool-capabilities` block listing an unknown cap yields no pair — the
        # extractor never fabricates a node for a capability the registry doesn't define.
        fm = "name: x\ntool-capabilities:\n  - security-scanning\n  - totally-made-up-cap\n"
        known = ice._registry_capabilities()
        declared = ice._declared_capabilities(fm)
        self.assertIn("totally-made-up-cap", declared)  # parsed...
        self.assertNotIn("totally-made-up-cap", known)  # ...but not in the registry

    def test_injects_agent_to_capability_edge_and_node(self):
        pairs = ice._agent_capabilities()
        if not pairs:
            self.skipTest("no resolvable agent→capability pair")
        agent_rel, cap = pairs[0]
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [agent_rel])
            stats = ice.inject(Path(dbp))
            self.assertGreaterEqual(stats["edges_added"], 1)
            conn = sqlite3.connect(dbp)
            edge = conn.execute(
                "SELECT source, target, provenance FROM edges "
                "WHERE provenance='injected:capability'"
            ).fetchone()
            node = conn.execute(
                "SELECT id, kind FROM nodes WHERE id = ?", (f"capability:{cap}",)
            ).fetchone()
            conn.close()
            self.assertIsNotNone(edge, "no injected:capability edge created")
            self.assertEqual(edge[0], f"file:{agent_rel}")
            self.assertEqual(edge[1], f"capability:{cap}")
            self.assertIsNotNone(node, "synthetic capability node not created")
            self.assertEqual(node[1], "capability")

    def test_self_nodes_agent_and_capability_when_absent_issue_916(self):
        # The agent .md isn't a codegraph node (codegraph indexes code, not markdown).
        # The extractor must self-node the agent file AND create the synthetic
        # capability node, then wire the edge. The old behavior skipped everything,
        # leaving the agent→capability layer empty (#916).
        pairs = ice._agent_capabilities()
        if not pairs:
            self.skipTest("no resolvable agent→capability pair")
        agent_rel, cap = pairs[0]
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [])  # empty graph
            stats = ice.inject(Path(dbp))
            self.assertGreaterEqual(stats["edges_added"], 1)
            self.assertEqual(stats["skipped"], 0)
            conn = sqlite3.connect(dbp)
            edge = conn.execute(
                "SELECT 1 FROM edges WHERE provenance='injected:capability' "
                "AND source=? AND target=?", (f"file:{agent_rel}", f"capability:{cap}")
            ).fetchone()
            anode = conn.execute("SELECT 1 FROM nodes WHERE id=?", (f"file:{agent_rel}",)).fetchone()
            cnode = conn.execute("SELECT kind FROM nodes WHERE id=?", (f"capability:{cap}",)).fetchone()
            conn.close()
            self.assertIsNotNone(edge, "capability edge not created from self-noded agent .md")
            self.assertIsNotNone(anode, "agent .md was not self-noded")
            self.assertIsNotNone(cnode, "synthetic capability node not created")
            self.assertEqual(cnode[0], "capability")

    def test_inject_is_idempotent(self):
        pairs = ice._agent_capabilities()
        rels = sorted({a for a, _ in pairs})
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, rels)
            n1 = ice.inject(Path(dbp))["edges_added"]
            n2 = ice.inject(Path(dbp))["edges_added"]
            self.assertEqual(n1, n2)  # re-run replaces edges, does not duplicate
            conn = sqlite3.connect(dbp)
            edges = conn.execute(
                "SELECT count(*) FROM edges WHERE provenance='injected:capability'"
            ).fetchone()[0]
            cnodes = conn.execute(
                "SELECT count(*) FROM nodes WHERE kind='capability'"
            ).fetchone()[0]
            distinct_caps = conn.execute(
                "SELECT count(DISTINCT target) FROM edges "
                "WHERE provenance='injected:capability'"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(edges, n2)
            self.assertEqual(cnodes, distinct_caps)  # one node per referenced cap, no dupes


class GraphNodeHelperTests(unittest.TestCase):
    """The self-noding helpers populate every NOT NULL column and are idempotent."""

    def test_ensure_file_node_satisfies_schema_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [])  # real schema, no rows
            conn = sqlite3.connect(dbp)
            nid1 = gn.ensure_file_node(conn, "commands/x/y.md")
            nid2 = gn.ensure_file_node(conn, "commands/x/y.md")  # idempotent
            conn.commit()
            self.assertEqual(nid1, nid2)
            row = conn.execute(
                "SELECT kind, language, file_path FROM nodes WHERE id=?", (nid1,)
            ).fetchone()
            count = conn.execute("SELECT count(*) FROM nodes WHERE id=?", (nid1,)).fetchone()[0]
            conn.close()
            self.assertEqual(count, 1)
            self.assertEqual(row[0], "file")
            self.assertEqual(row[1], "markdown")  # .md self-nodes carry markdown language

    def test_ensure_virtual_node_satisfies_schema(self):
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, [])
            conn = sqlite3.connect(dbp)
            nid = gn.ensure_virtual_node(conn, "capability:foo", "capability", "foo")
            conn.commit()
            row = conn.execute("SELECT kind, name FROM nodes WHERE id=?", (nid,)).fetchone()
            conn.close()
            self.assertEqual(row, ("capability", "foo"))


class InjectAllTests(unittest.TestCase):
    """The orchestrator runs every extractor and sums the injected edges."""

    def test_runs_all_extractors_and_totals(self):
        dispatches = idis._dispatches()
        pairs = ice._agent_capabilities()
        rels = sorted({c for c, _, _ in dispatches} | {a for _, a, _ in dispatches}
                      | {a for a, _ in pairs})
        with tempfile.TemporaryDirectory() as d:
            dbp = str(Path(d) / "cg.db")
            _codegraph_shaped_db(dbp, rels)
            out = iall.inject_all(Path(dbp))
            self.assertIn("bus", out)
            self.assertIn("dispatch", out)
            self.assertIn("capability", out)
            expected = sum(out[k]["edges_added"] for k in ("bus", "dispatch", "capability"))
            self.assertEqual(out["total_injected_edges"], expected)
            # the markdown layers must contribute (the #916 fix) when dispatches/pairs exist
            if dispatches:
                self.assertGreaterEqual(out["dispatch"]["edges_added"], 1)
            if pairs:
                self.assertGreaterEqual(out["capability"]["edges_added"], 1)


if __name__ == "__main__":
    unittest.main()
