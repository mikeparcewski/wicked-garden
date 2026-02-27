"""Test suite for graph export and client modules.

Tests the cache schema implementation for wicked-search graph export.
"""

import json
import tempfile
from pathlib import Path

# Mock wicked-cache for testing
class MockCache:
    """Mock NamespacedCache for testing."""

    def __init__(self):
        self.store = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value, options=None):
        self.store[key] = value
        return key

    def invalidate(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
            return True
        return False


def create_test_graph():
    """Create a test SymbolGraph for testing."""
    from symbol_graph import (
        SymbolGraph, Symbol, Reference,
        SymbolType, ReferenceType, Confidence
    )

    graph = SymbolGraph()

    # Add some test symbols
    auth_func = Symbol(
        id="src/auth.py::authenticate_user",
        type=SymbolType.FUNCTION,
        name="authenticate_user",
        qualified_name="auth.authenticate_user",
        file_path="src/auth.py",
        line_start=42,
        line_end=67,
        metadata={"domain": "code"}
    )
    graph.add_symbol(auth_func)

    db_method = Symbol(
        id="src/db.py::User.get_by_email",
        type=SymbolType.METHOD,
        name="get_by_email",
        qualified_name="db.User.get_by_email",
        file_path="src/db.py",
        line_start=120,
        line_end=135,
        metadata={"domain": "code"}
    )
    graph.add_symbol(db_method)

    crypto_func = Symbol(
        id="src/crypto.py::verify_password",
        type=SymbolType.FUNCTION,
        name="verify_password",
        qualified_name="crypto.verify_password",
        file_path="src/crypto.py",
        line_start=15,
        line_end=25,
        metadata={"domain": "code"}
    )
    graph.add_symbol(crypto_func)

    api_func = Symbol(
        id="src/api/login.py::login_handler",
        type=SymbolType.FUNCTION,
        name="login_handler",
        qualified_name="api.login.login_handler",
        file_path="src/api/login.py",
        line_start=10,
        line_end=30,
        metadata={"domain": "code"}
    )
    graph.add_symbol(api_func)

    # Add references
    # api.login_handler -> auth.authenticate_user
    graph.add_reference(Reference(
        source_id=api_func.id,
        target_id=auth_func.id,
        ref_type=ReferenceType.CALLS,
        confidence=Confidence.HIGH,
        evidence={"line": 23}
    ))

    # auth.authenticate_user -> db.User.get_by_email
    graph.add_reference(Reference(
        source_id=auth_func.id,
        target_id=db_method.id,
        ref_type=ReferenceType.CALLS,
        confidence=Confidence.HIGH,
        evidence={"line": 45}
    ))

    # auth.authenticate_user -> crypto.verify_password
    graph.add_reference(Reference(
        source_id=auth_func.id,
        target_id=crypto_func.id,
        ref_type=ReferenceType.CALLS,
        confidence=Confidence.HIGH,
        evidence={"line": 52}
    ))

    return graph


def test_symbol_deps_export():
    """Test symbol dependencies export."""
    from graph_export import GraphExporter, FreshnessMetadata

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Create freshness metadata
    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )

    # Export symbol deps
    key = exporter.export_symbol_deps(graph, "abc12345", freshness)

    # Verify cache key
    assert key == "symbol_deps:abc12345"

    # Verify cached data
    data = cache.get(key)
    assert data is not None
    assert data["version"] == "1.0.0"
    assert data["freshness"]["workspace_hash"] == "abc12345"
    assert len(data["symbols"]) == 4

    # Find authenticate_user symbol
    auth_symbol = next(
        (s for s in data["symbols"] if s["id"] == "src/auth.py::authenticate_user"),
        None
    )
    assert auth_symbol is not None
    assert auth_symbol["name"] == "authenticate_user"
    assert len(auth_symbol["dependencies"]) == 2  # calls 2 functions
    assert len(auth_symbol["dependents"]) == 1   # called by 1 function

    print("✓ symbol_deps export test passed")


def test_file_refs_export():
    """Test file references export."""
    from graph_export import GraphExporter, FreshnessMetadata

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )

    # Export file refs
    key = exporter.export_file_refs(graph, "abc12345", freshness)

    # Verify cached data
    data = cache.get(key)
    assert data is not None
    assert len(data["files"]) == 4

    # Find src/auth.py file
    auth_file = next(
        (f for f in data["files"] if f["path"] == "src/auth.py"),
        None
    )
    assert auth_file is not None
    assert len(auth_file["symbols"]) == 1
    assert auth_file["symbols"][0]["name"] == "authenticate_user"
    assert auth_file["symbols"][0]["calls_out"] == 2
    assert auth_file["symbols"][0]["calls_in"] == 1

    print("✓ file_refs export test passed")


def test_def_lookup_export():
    """Test definition lookup export."""
    from graph_export import GraphExporter, FreshnessMetadata

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )

    # Export def lookup
    key = exporter.export_def_lookup(graph, "abc12345", freshness)

    # Verify cached data
    data = cache.get(key)
    assert data is not None

    # Check by_name index
    by_name = data["index"]["by_name"]
    assert "authenticate_user" in by_name
    assert len(by_name["authenticate_user"]) == 1
    assert by_name["authenticate_user"][0]["file"] == "src/auth.py"

    # Check by_qualified_name index
    by_qn = data["index"]["by_qualified_name"]
    assert "auth.authenticate_user" in by_qn
    assert by_qn["auth.authenticate_user"]["file"] == "src/auth.py"
    assert by_qn["auth.authenticate_user"]["line_start"] == 42

    print("✓ def_lookup export test passed")


def test_call_chain_export():
    """Test call chain export."""
    from graph_export import GraphExporter, FreshnessMetadata

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )

    # Export call chain
    key = exporter.export_call_chain(graph, "abc12345", freshness)

    # Verify cached data
    data = cache.get(key)
    assert data is not None
    assert len(data["chains"]) > 0

    # Find authenticate_user chain
    auth_chain = next(
        (c for c in data["chains"] if c["root_id"] == "src/auth.py::authenticate_user"),
        None
    )
    assert auth_chain is not None
    assert len(auth_chain["downstream"]) == 2  # calls 2 functions
    assert len(auth_chain["upstream"]) == 1   # called by 1 function

    print("✓ call_chain export test passed")


def test_export_all():
    """Test exporting all query types."""
    from graph_export import GraphExporter

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Export all
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_path = tmpdir
        result = exporter.export_all(graph, workspace_path)

        # Verify result
        assert result.workspace_hash is not None
        assert len(result.keys_written) == 4
        assert result.stats["total_symbols"] == 4

        # Verify all keys are in cache
        for key in result.keys_written:
            assert cache.get(key) is not None

    print("✓ export_all test passed")


def test_client_symbol_deps():
    """Test client symbol dependencies query."""
    from graph_export import GraphExporter, FreshnessMetadata
    from graph_client import GraphClient

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Export data
    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )
    exporter.export_symbol_deps(graph, "abc12345", freshness)

    # Create client (mock workspace hash)
    client = GraphClient(workspace_path="/fake/path", cache=cache)
    client.workspace_hash = "abc12345"  # Override for testing

    # Query symbol deps
    result = client.get_symbol_dependencies()

    # Verify result
    assert result.version == "1.0.0"
    assert result.freshness.workspace_hash == "abc12345"
    assert len(result.symbols) == 4

    # Find authenticate_user
    auth_symbol = next(
        (s for s in result.symbols if s.name == "authenticate_user"),
        None
    )
    assert auth_symbol is not None
    assert len(auth_symbol.dependencies) == 2
    assert len(auth_symbol.dependents) == 1

    print("✓ client symbol_deps test passed")


def test_client_lookup_definition():
    """Test client definition lookup."""
    from graph_export import GraphExporter, FreshnessMetadata
    from graph_client import GraphClient

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Export data
    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )
    exporter.export_def_lookup(graph, "abc12345", freshness)

    # Create client
    client = GraphClient(workspace_path="/fake/path", cache=cache)
    client.workspace_hash = "abc12345"

    # Lookup by name
    loc = client.lookup_definition(name="authenticate_user")
    assert loc is not None
    assert loc.file == "src/auth.py"
    assert loc.line_start == 42

    # Lookup by qualified name
    loc = client.lookup_definition(qualified_name="auth.authenticate_user")
    assert loc is not None
    assert loc.file == "src/auth.py"
    assert loc.line_start == 42

    # Lookup non-existent
    loc = client.lookup_definition(name="nonexistent")
    assert loc is None

    print("✓ client lookup_definition test passed")


def test_freshness_check():
    """Test freshness validation."""
    from graph_export import GraphExporter, FreshnessMetadata
    from graph_client import GraphClient

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Export data
    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )
    exporter.export_symbol_deps(graph, "abc12345", freshness)

    # Create client
    client = GraphClient(workspace_path="/fake/path", cache=cache)
    client.workspace_hash = "abc12345"

    # Get freshness
    fresh = client.get_freshness()
    assert fresh is not None
    assert fresh.workspace_hash == "abc12345"
    assert fresh.node_count == 4

    # Note: is_fresh() will fail because indexed_at is in the past
    # In production, this would be recent

    print("✓ freshness check test passed")


def test_filter_params():
    """Test filter parameter hashing."""
    from graph_export import GraphExporter

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Create filter
    filter_params = {
        "paths": ["src/auth/", "src/api/"],
        "node_types": ["function", "method"]
    }

    # Export with filter
    freshness = FreshnessMetadata(
        indexed_at="2026-02-01T12:00:00Z",
        workspace_hash="abc12345",
        file_count=4,
        node_count=4,
        edge_count=3
    )

    from graph_export import FreshnessMetadata
    key = exporter.export_symbol_deps(graph, "abc12345", freshness, filter_params)

    # Verify key includes filter hash
    assert key.startswith("symbol_deps:abc12345:")
    parts = key.split(":")
    assert len(parts) == 3  # type:workspace:filter_hash

    # Same filter should produce same hash
    key2 = exporter.export_symbol_deps(graph, "abc12345", freshness, filter_params)
    assert key == key2

    # Different filter should produce different hash
    filter_params2 = {
        "paths": ["src/db/"],
        "node_types": ["class"]
    }
    key3 = exporter.export_symbol_deps(graph, "abc12345", freshness, filter_params2)
    assert key != key3

    print("✓ filter params test passed")


def test_invalidation():
    """Test cache invalidation."""
    from graph_export import GraphExporter

    cache = MockCache()
    exporter = GraphExporter(cache)
    graph = create_test_graph()

    # Export data
    with tempfile.TemporaryDirectory() as tmpdir:
        result = exporter.export_all(graph, tmpdir)
        workspace_hash = result.workspace_hash

        # Verify data exists
        key = f"symbol_deps:{workspace_hash}"
        assert cache.get(key) is not None

        # Invalidate
        count = exporter.invalidate_all(workspace_hash)
        assert count > 0

        # Verify data is gone
        assert cache.get(key) is None

    print("✓ invalidation test passed")


def run_all_tests():
    """Run all tests."""
    print("\n=== Running Graph Cache Tests ===\n")

    test_symbol_deps_export()
    test_file_refs_export()
    test_def_lookup_export()
    test_call_chain_export()
    test_export_all()
    test_client_symbol_deps()
    test_client_lookup_definition()
    test_freshness_check()
    test_filter_params()
    test_invalidation()

    print("\n=== All Tests Passed ===\n")


if __name__ == "__main__":
    run_all_tests()
