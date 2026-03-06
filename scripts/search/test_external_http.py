"""
pytest tests for external_indexer.py HTTP source + auth (E-15/E-16/E-17/E-24/E-25).

Run with:
    cd /Users/michael.parcewski/Projects/wicked-garden && uv run pytest scripts/search/test_external_http.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from io import BytesIO

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow importing external_indexer without package install
# ---------------------------------------------------------------------------

SEARCH_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SEARCH_DIR.parent

sys.path.insert(0, str(SEARCH_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from external_indexer import (
    ExternalSourceConfig,
    ExternalSourceRegistry,
    ExternalIndexer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    """Return a path to a temporary config file (does not exist yet)."""
    return tmp_path / "external-sources.json"


@pytest.fixture
def tmp_index_dir(tmp_path):
    """Return a temporary directory that acts as the wicked-search index dir."""
    idx = tmp_path / "wicked-search"
    idx.mkdir()
    return idx


@pytest.fixture
def registry(tmp_config):
    reg = ExternalSourceRegistry(str(tmp_config))
    reg.load_config()
    return reg


@pytest.fixture
def http_source():
    return ExternalSourceConfig(
        name="test-http",
        plugin="",
        fetch_command="",
        source_type="http",
        fetch_url_template="https://example.com/api/data",
        auth_env_var="MY_API_TOKEN",
    )


@pytest.fixture
def http_source_no_auth():
    return ExternalSourceConfig(
        name="test-http-no-auth",
        plugin="",
        fetch_command="",
        source_type="http",
        fetch_url_template="https://public.example.com/data",
        auth_env_var=None,
    )


@pytest.fixture
def mcp_source():
    return ExternalSourceConfig(
        name="test-mcp",
        plugin="mcp-confluence",
        fetch_command="get_space_pages",
        source_type="mcp",
    )


# ---------------------------------------------------------------------------
# E-15/E-16: Auth token scoped inside _fetch_http — not at module level
# ---------------------------------------------------------------------------

class TestAuthTokenScoping:
    """E-15/E-16 — Bearer token read inside _fetch_http, never stored at module level."""

    def test_bearer_header_sent_when_env_var_set(self, registry, http_source):
        """When MY_API_TOKEN is set, Authorization header is sent."""
        indexer = ExternalIndexer(registry)

        mock_response = MagicMock()
        mock_response.read.return_value = b"response body"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return mock_response

        env_patch = {"MY_API_TOKEN": "secret-token-123"}

        with patch.dict(os.environ, env_patch), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = indexer._fetch_http(http_source)

        assert result == "response body"
        assert len(captured_requests) == 1
        auth_header = captured_requests[0].get_header("Authorization")
        assert auth_header == "Bearer secret-token-123"

    def test_token_value_not_stored_on_module_or_indexer(self, registry, http_source):
        """The token value must not be saved as an attribute on ExternalIndexer."""
        indexer = ExternalIndexer(registry)
        env_patch = {"MY_API_TOKEN": "super-secret"}

        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch.dict(os.environ, env_patch), \
             patch("urllib.request.urlopen", return_value=mock_response):
            indexer._fetch_http(http_source)

        # The secret value must not appear in indexer's __dict__
        indexer_values = json.dumps(indexer.__dict__, default=str)
        assert "super-secret" not in indexer_values

    def test_token_not_present_in_log_calls(self, registry, http_source):
        """Ops log detail must never include the token value."""
        indexer = ExternalIndexer(registry)
        env_patch = {"MY_API_TOKEN": "confidential-abc"}

        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        logged_calls = []

        def capture_log(domain, level, event, ok=True, ms=None, detail=None):
            logged_calls.append({"event": event, "detail": detail})

        with patch.dict(os.environ, env_patch), \
             patch("urllib.request.urlopen", return_value=mock_response), \
             patch("external_indexer._ops_log", side_effect=capture_log):
            indexer._fetch_http(http_source)

        for entry in logged_calls:
            detail_str = json.dumps(entry.get("detail") or {})
            assert "confidential-abc" not in detail_str, (
                f"Token value leaked into log: {entry}"
            )


# ---------------------------------------------------------------------------
# E-17: Missing auth env var — graceful handling (no crash, no header sent)
# ---------------------------------------------------------------------------

class TestMissingAuthEnvVar:
    """E-17 — When auth_env_var is set but the env var is absent, proceed without auth."""

    def test_request_sent_without_auth_when_env_var_missing(self, registry, http_source):
        captured_requests = []
        mock_response = MagicMock()
        mock_response.read.return_value = b"public data"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return mock_response

        # Ensure MY_API_TOKEN is NOT in environ
        with patch.dict(os.environ, {}, clear=False), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            # Remove the key if it happens to be set
            env_without_token = {k: v for k, v in os.environ.items() if k != "MY_API_TOKEN"}
            with patch.dict(os.environ, env_without_token, clear=True):
                result = indexer_from_registry = ExternalIndexer(registry)
                result = indexer_from_registry._fetch_http(http_source)

        # Request should still have been made
        assert result == "public data"
        # No Authorization header
        auth = captured_requests[0].get_header("Authorization")
        assert auth is None

    def test_returns_none_when_url_missing(self, registry):
        """Source with no fetch_url_template returns None without raising."""
        source_no_url = ExternalSourceConfig(
            name="no-url",
            plugin="",
            fetch_command="",
            source_type="http",
            fetch_url_template=None,
        )
        indexer = ExternalIndexer(registry)
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = indexer._fetch_http(source_no_url)
        assert result is None
        mock_urlopen.assert_not_called()

    def test_returns_none_on_network_error(self, registry, http_source):
        """Network error returns None, does not raise."""
        indexer = ExternalIndexer(registry)
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            result = indexer._fetch_http(http_source)
        assert result is None

    def test_returns_none_on_timeout(self, registry, http_source):
        """Timeout returns None, does not raise."""
        import socket
        indexer = ExternalIndexer(registry)
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = indexer._fetch_http(http_source)
        assert result is None


# ---------------------------------------------------------------------------
# E-24/E-25: _load_external_results merges / skips external results
# ---------------------------------------------------------------------------

class TestLoadExternalResults:
    """E-24/E-25 — unified_search._load_external_results merges/skips entries."""

    def _write_index(self, index_path: Path, nodes: list) -> None:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w") as f:
            for node in nodes:
                f.write(json.dumps(node) + "\n")

    def _make_node(self, name: str, content: str, content_type: str = "document",
                   source_name: str = "test-src") -> dict:
        return {
            "id": f"external::test::{name}",
            "name": name,
            "type": "doc_page",
            "file": f"external://mcp/{name}",
            "line_start": 1,
            "line_end": 5,
            "calls": [],
            "imports": [],
            "bases": [],
            "imported_names": [],
            "dependents": [],
            "content": content,
            "domain": "doc",
            "metadata": {
                "source": "external",
                "source_name": source_name,
                "source_plugin": "mcp-test",
                "content_type": content_type,
                "doc_id": name,
            },
        }

    def test_e24_matching_nodes_returned(self, tmp_path):
        """E-24 — nodes matching query terms are merged into results."""
        # We need to patch the home directory so _load_external_results finds our index
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node("deployment-guide", "How to deploy the authentication service"),
            self._make_node("unrelated-doc", "Pizza recipes and cooking tips"),
        ]
        self._write_index(index_path, nodes)

        # Patch Path.home to point to tmp_path
        with patch.object(Path, "home", return_value=tmp_path):
            # Import the function fresh (it uses Path.home() at call time)
            sys.path.insert(0, str(SEARCH_DIR))
            import unified_search
            results = unified_search._load_external_results("authentication deploy")

        matching_names = [r["name"] for r in results]
        assert any("deployment-guide" in n for n in matching_names), (
            f"Expected deployment-guide in results, got: {matching_names}"
        )

    def test_e25_non_matching_nodes_skipped(self, tmp_path):
        """E-25 — nodes with no query term hits are excluded."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node("irrelevant", "completely unrelated content xyz"),
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication service")

        assert results == [], f"Expected no results, got: {results}"

    def test_domain_filter_code_excludes_documents(self, tmp_path):
        """domain_filter='code' must skip nodes with content_type='document'."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node("api-spec", "api endpoint authentication token", content_type="document"),
            self._make_node("auth-module", "def authenticate(token): pass", content_type="code"),
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication token", domain_filter="code")

        names = [r["name"] for r in results]
        assert not any("api-spec" in n for n in names), "Document node should be filtered out"
        assert any("auth-module" in n for n in names), "Code node should be included"

    def test_domain_filter_doc_excludes_code(self, tmp_path):
        """domain_filter='doc' must skip nodes with content_type='code'."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node("api-spec", "api endpoint documentation", content_type="document"),
            self._make_node("auth-module", "def api_endpoint(): return auth", content_type="code"),
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("api endpoint", domain_filter="doc")

        names = [r["name"] for r in results]
        assert any("api-spec" in n for n in names), "Document should be included"
        assert not any("auth-module" in n for n in names), "Code node should be filtered out"

    def test_returns_empty_list_when_no_index_file(self, tmp_path):
        """Returns [] when external/index.jsonl does not exist."""
        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("anything")
        assert results == []

    def test_results_ordered_by_score_descending(self, tmp_path):
        """Higher-scoring nodes appear first."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            # Low relevance: query term appears once
            self._make_node("low-doc", "authentication"),
            # High relevance: query term appears many times
            self._make_node("high-doc", "authentication authentication authentication authentication"),
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication", limit=10)

        assert len(results) >= 2
        assert results[0]["score"] >= results[1]["score"]

    def test_limit_respected(self, tmp_path):
        """limit parameter caps the number of results returned."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node(f"doc-{i}", "authentication service token") for i in range(20)
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication", limit=5)

        assert len(results) <= 5

    def test_malformed_jsonl_lines_skipped(self, tmp_path):
        """Corrupt JSONL lines are skipped without raising."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        good_node = self._make_node("good-doc", "authentication works well")
        with open(index_path, "w") as f:
            f.write("not valid json {{{\n")
            f.write(json.dumps(good_node) + "\n")
            f.write("\n")  # blank line

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication")

        names = [r["name"] for r in results]
        assert any("good-doc" in n for n in names)

    def test_result_includes_source_attribution(self, tmp_path):
        """Result dicts include source and source_name fields."""
        external_dir = tmp_path / ".something-wicked" / "wicked-search" / "external"
        index_path = external_dir / "index.jsonl"

        nodes = [
            self._make_node("my-doc", "important authentication content", source_name="my-confluence"),
        ]
        self._write_index(index_path, nodes)

        with patch.object(Path, "home", return_value=tmp_path):
            import unified_search
            results = unified_search._load_external_results("authentication")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "external"
        assert r["source_name"] == "my-confluence"
        assert "external: my-confluence" in r["name"]


# ---------------------------------------------------------------------------
# ExternalIndexer.refresh_stale — HTTP source integration
# ---------------------------------------------------------------------------

class TestRefreshStaleHTTP:
    """refresh_stale routes http sources through _fetch_http."""

    def test_http_source_fetched_during_refresh(self, tmp_config, tmp_index_dir):
        """Stale http source triggers _fetch_http and index_content."""
        registry = ExternalSourceRegistry(str(tmp_config))
        registry.load_config()

        src = ExternalSourceConfig(
            name="test-http",
            plugin="",
            fetch_command="",
            source_type="http",
            fetch_url_template="https://example.com/page",
            last_fetched=None,  # stale
        )
        registry.add_source(src)

        indexer = ExternalIndexer(registry, index_dir=str(tmp_index_dir))

        mock_response = MagicMock()
        mock_response.read.return_value = b"fetched content"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            results = indexer.refresh_stale(dry_run=False)

        assert len(results) == 1
        assert results[0]["source_type"] == "http"
        assert results[0]["indexed"] is True

    def test_http_source_dry_run_skips_fetch(self, tmp_config, tmp_index_dir):
        """dry_run=True for http source must not call _fetch_http."""
        registry = ExternalSourceRegistry(str(tmp_config))
        registry.load_config()

        src = ExternalSourceConfig(
            name="test-http-dry",
            plugin="",
            fetch_command="",
            source_type="http",
            fetch_url_template="https://example.com/data",
            last_fetched=None,
        )
        registry.add_source(src)

        indexer = ExternalIndexer(registry, index_dir=str(tmp_index_dir))

        with patch.object(indexer, "_fetch_http") as mock_fetch:
            results = indexer.refresh_stale(dry_run=True)

        mock_fetch.assert_not_called()
        assert len(results) == 1
        assert results[0]["stale"] is True

    def test_mcp_source_not_fetched_directly(self, tmp_config, tmp_index_dir):
        """MCP sources are reported but _fetch_http is never called for them."""
        registry = ExternalSourceRegistry(str(tmp_config))
        registry.load_config()

        src = ExternalSourceConfig(
            name="test-mcp",
            plugin="mcp-confluence",
            fetch_command="get_pages",
            source_type="mcp",
            last_fetched=None,
        )
        registry.add_source(src)

        indexer = ExternalIndexer(registry, index_dir=str(tmp_index_dir))

        with patch.object(indexer, "_fetch_http") as mock_fetch:
            results = indexer.refresh_stale(dry_run=False)

        mock_fetch.assert_not_called()
        assert len(results) == 1
        assert results[0]["source_type"] == "mcp"
        assert "plugin" in results[0]


# ---------------------------------------------------------------------------
# ExternalSourceConfig serialization — new fields round-trip
# ---------------------------------------------------------------------------

class TestExternalSourceConfigSerialization:
    """New fields source_type, auth_env_var, fetch_url_template survive round-trips."""

    def test_http_config_round_trips_through_registry(self, tmp_config):
        registry = ExternalSourceRegistry(str(tmp_config))
        registry.load_config()

        src = ExternalSourceConfig(
            name="rt-test",
            plugin="",
            fetch_command="",
            source_type="http",
            auth_env_var="SECRET_TOKEN",
            fetch_url_template="https://rt.example.com/data",
        )
        registry.add_source(src)

        # Reload from disk
        registry2 = ExternalSourceRegistry(str(tmp_config))
        registry2.load_config()
        loaded = registry2.get_source("rt-test")

        assert loaded is not None
        assert loaded.source_type == "http"
        assert loaded.auth_env_var == "SECRET_TOKEN"
        assert loaded.fetch_url_template == "https://rt.example.com/data"

    def test_auth_env_var_name_stored_not_value(self, tmp_config):
        """Only the env var NAME must be stored — never the secret value."""
        registry = ExternalSourceRegistry(str(tmp_config))
        registry.load_config()

        src = ExternalSourceConfig(
            name="secret-test",
            plugin="",
            fetch_command="",
            source_type="http",
            auth_env_var="MY_SECRET_KEY",
            fetch_url_template="https://example.com",
        )
        registry.add_source(src)

        raw_config = tmp_config.read_text()
        # The env var name should be there
        assert "MY_SECRET_KEY" in raw_config
        # A hypothetical secret value should never appear
        assert "actual_secret_value_xyz" not in raw_config

    def test_from_dict_backward_compat_missing_http_fields(self):
        """Old records without source_type/auth_env_var/fetch_url_template load cleanly."""
        old_record = {
            "name": "legacy-mcp",
            "plugin": "mcp-confluence",
            "fetch_command": "get_pages",
            # source_type, auth_env_var, fetch_url_template absent
        }
        src = ExternalSourceConfig.from_dict(old_record)
        assert src.source_type == "mcp"
        assert src.auth_env_var is None
        assert src.fetch_url_template is None
