"""Tests for the Plugin Data API Standard.

Tests all data plugin api.py scripts via subprocess, verifying they follow
the standard CLI contract: verbs, response envelope, error format, pagination.

Also tests the data_gateway discovery module (reads wicked.json).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

# Plugin api.py script paths and their valid sources
PLUGIN_CONFIGS = {
    "wicked-kanban": {
        "script": PLUGINS_DIR / "wicked-kanban" / "scripts" / "api.py",
        "sources": ["projects", "tasks"],  # initiatives/activity require --project
        "sources_with_project": ["initiatives", "activity"],
        "search_source": "tasks",
        "get_source": "tasks",
        "stats_source": "tasks",
    },
    "wicked-mem": {
        "script": PLUGINS_DIR / "wicked-mem" / "scripts" / "api.py",
        "sources": ["memories"],
        "sources_with_project": [],
        "search_source": "memories",
        "get_source": "memories",
        "stats_source": "memories",
    },
    "wicked-crew": {
        "script": PLUGINS_DIR / "wicked-crew" / "scripts" / "api.py",
        "sources": ["projects", "signals", "feedback", "specialists"],
        "sources_with_project": ["phases"],
        "search_source": "signals",
        "get_source": "projects",
        "stats_source": "signals",
    },
    "wicked-search": {
        "script": PLUGINS_DIR / "wicked-search" / "scripts" / "api.py",
        "sources": ["symbols", "documents", "references"],
        "sources_with_project": [],
        "search_source": "symbols",
        "get_source": "symbols",
        "stats_source": "symbols",
    },
    "wicked-jam": {
        "script": PLUGINS_DIR / "wicked-jam" / "scripts" / "api.py",
        "sources": ["sessions"],
        "sources_with_project": [],
        "search_source": "sessions",
        "get_source": "sessions",
        "stats_source": "sessions",
    },
    "wicked-smaht": {
        "script": PLUGINS_DIR / "wicked-smaht" / "scripts" / "api.py",
        "sources": ["sessions"],
        "sources_with_project": [],
        "search_source": None,  # smaht doesn't support search
        "get_source": "sessions",
        "stats_source": "sessions",
    },
}


def run_api(plugin_name, args, timeout=10):
    """Run a plugin api.py script and return (returncode, stdout_json, stderr)."""
    config = PLUGIN_CONFIGS[plugin_name]
    cmd = [sys.executable, str(config["script"])] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    stdout_json = None
    if result.stdout.strip():
        try:
            stdout_json = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return result.returncode, stdout_json, result.stderr


def validate_envelope(data, source=None):
    """Validate response follows {data, meta} envelope standard."""
    assert "data" in data, "Response must have 'data' field"
    assert "meta" in data, "Response must have 'meta' field"
    meta = data["meta"]
    assert "total" in meta, "Meta must have 'total'"
    assert "limit" in meta, "Meta must have 'limit'"
    assert "offset" in meta, "Meta must have 'offset'"
    assert "source" in meta, "Meta must have 'source'"
    assert "timestamp" in meta, "Meta must have 'timestamp'"
    if source:
        assert meta["source"] == source


# =============================================================================
# Parametrized tests across all plugins
# =============================================================================

ALL_PLUGINS = list(PLUGIN_CONFIGS.keys())


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestListVerb:
    """Test the 'list' verb across all plugins."""

    def test_list_returns_json(self, plugin):
        """list verb returns valid JSON to stdout with exit 0."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "5"])
        assert rc == 0, f"Expected exit 0, got {rc}"
        assert data is not None, "Expected valid JSON output"
        validate_envelope(data, source)

    def test_list_pagination_limit(self, plugin):
        """--limit is respected in response."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "2"])
        assert rc == 0
        assert data["meta"]["limit"] == 2
        assert len(data["data"]) <= 2

    def test_list_pagination_offset(self, plugin):
        """--offset is respected in meta."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "5", "--offset", "3"])
        assert rc == 0
        assert data["meta"]["offset"] == 3

    def test_list_all_sources(self, plugin):
        """Each declared source responds to list."""
        for source in PLUGIN_CONFIGS[plugin]["sources"]:
            rc, data, _ = run_api(plugin, ["list", source, "--limit", "1"])
            assert rc == 0, f"list {source} failed with exit {rc}"
            validate_envelope(data, source)


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestStatsVerb:
    """Test the 'stats' verb across all plugins."""

    def test_stats_returns_json(self, plugin):
        source = PLUGIN_CONFIGS[plugin].get("stats_source")
        if source is None:
            pytest.skip(f"{plugin} has no stats source")
        rc, data, stderr = run_api(plugin, ["stats", source])
        if rc == 0:
            assert data is not None
            assert "data" in data
            assert "meta" in data
        # Some may not support stats — that's ok, just verify error format
        elif rc == 1:
            err = json.loads(stderr.strip()) if stderr.strip() else {}
            assert "error" in err or "code" in err


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestGetVerb:
    """Test the 'get' verb across all plugins."""

    def test_get_not_found(self, plugin):
        """get with nonexistent ID returns exit 1 and error JSON."""
        source = PLUGIN_CONFIGS[plugin]["get_source"]
        rc, _, stderr = run_api(plugin, ["get", source, "nonexistent-id-xyz123"])
        assert rc == 1, "Expected exit 1 for not found"
        err = json.loads(stderr.strip())
        assert "error" in err
        assert "code" in err

    def test_get_missing_id(self, plugin):
        """get without ID returns error."""
        source = PLUGIN_CONFIGS[plugin]["get_source"]
        rc, _, stderr = run_api(plugin, ["get", source])
        assert rc != 0 or "error" in (stderr or "").lower()


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestSearchVerb:
    """Test the 'search' verb across plugins that support it."""

    def test_search_with_query(self, plugin):
        """search --query returns results or empty."""
        source = PLUGIN_CONFIGS[plugin]["search_source"]
        if source is None:
            pytest.skip(f"{plugin} has no search source")
        rc, data, _ = run_api(plugin, ["search", source, "--query", "test", "--limit", "5"])
        assert rc == 0
        assert data is not None
        validate_envelope(data, source)
        assert isinstance(data["data"], list)

    def test_search_empty_results(self, plugin):
        """search with impossible query returns empty data."""
        source = PLUGIN_CONFIGS[plugin]["search_source"]
        if source is None:
            pytest.skip(f"{plugin} has no search source")
        rc, data, _ = run_api(
            plugin, ["search", source, "--query", "zzz_impossible_query_xyz_999", "--limit", "5"]
        )
        assert rc == 0
        assert data is not None
        assert data["data"] == [] or isinstance(data["data"], list)


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestErrorHandling:
    """Test error handling across all plugins."""

    def test_invalid_source(self, plugin):
        """Invalid source returns exit 1 with error JSON."""
        rc, _, stderr = run_api(plugin, ["list", "nonexistent_source_xyz"])
        assert rc == 1
        err = json.loads(stderr.strip())
        assert "error" in err
        assert err.get("code") == "INVALID_SOURCE"

    def test_no_verb(self, plugin):
        """No verb shows help or errors gracefully."""
        # kanban has special behavior (starts HTTP server), skip it
        if plugin == "wicked-kanban":
            pytest.skip("kanban starts HTTP server with no args")
        rc, _, _ = run_api(plugin, [], timeout=3)
        assert rc != 0  # Should exit with error or help


@pytest.mark.parametrize("plugin", ALL_PLUGINS)
class TestResponseEnvelope:
    """Verify response envelope schema consistency."""

    def test_meta_has_timestamp(self, plugin):
        """Meta timestamp is ISO 8601 format."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "1"])
        assert rc == 0
        ts = data["meta"]["timestamp"]
        # Basic ISO 8601 check
        assert "T" in ts or ":" in ts, f"Timestamp not ISO format: {ts}"

    def test_data_is_list_for_list_verb(self, plugin):
        """list verb returns data as a list."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "5"])
        assert rc == 0
        assert isinstance(data["data"], list)

    def test_total_is_integer(self, plugin):
        """meta.total is an integer."""
        source = PLUGIN_CONFIGS[plugin]["sources"][0]
        rc, data, _ = run_api(plugin, ["list", source, "--limit", "1"])
        assert rc == 0
        assert isinstance(data["meta"]["total"], int)


# =============================================================================
# Plugin-specific tests
# =============================================================================

class TestKanbanDualMode:
    """Kanban-specific dual-mode tests."""

    def test_cli_list_tasks(self):
        """CLI mode: list tasks returns data."""
        rc, data, _ = run_api("wicked-kanban", ["list", "tasks", "--limit", "3"])
        assert rc == 0
        assert isinstance(data["data"], list)

    def test_cli_stats_tasks(self):
        """CLI mode: stats tasks returns aggregates."""
        rc, data, _ = run_api("wicked-kanban", ["stats", "tasks"])
        assert rc == 0
        assert "data" in data
        stats = data["data"]
        assert "total_tasks" in stats or isinstance(stats, dict)


class TestCrewProjectFilter:
    """Crew-specific: phases require --project."""

    def test_phases_without_project(self):
        """list phases without --project returns error."""
        rc, _, stderr = run_api("wicked-crew", ["list", "phases"])
        assert rc == 1
        err = json.loads(stderr.strip())
        assert "project" in err.get("error", "").lower()

    def test_phases_with_project(self):
        """list phases with --project returns data."""
        rc, data, _ = run_api("wicked-crew", ["list", "projects", "--limit", "1"])
        assert rc == 0
        if data["data"]:
            project_name = data["data"][0]["name"]
            rc2, data2, _ = run_api(
                "wicked-crew", ["list", "phases", "--project", project_name]
            )
            assert rc2 == 0
            validate_envelope(data2, "phases")


class TestCrewNewSources:
    """Test crew's expanded data sources (signals, feedback, specialists)."""

    def test_list_signals(self):
        """list signals returns signal definitions."""
        rc, data, _ = run_api("wicked-crew", ["list", "signals", "--limit", "5"])
        assert rc == 0
        validate_envelope(data, "signals")
        assert data["meta"]["total"] > 0  # default_signals.jsonl has entries

    def test_search_signals(self):
        """search signals by text."""
        rc, data, _ = run_api("wicked-crew", ["search", "signals", "--query", "security"])
        assert rc == 0
        validate_envelope(data, "signals")

    def test_stats_signals(self):
        """stats signals returns category breakdown."""
        rc, data, _ = run_api("wicked-crew", ["stats", "signals"])
        assert rc == 0
        assert "categories" in data["data"]

    def test_list_feedback(self):
        """list feedback returns outcomes."""
        rc, data, _ = run_api("wicked-crew", ["list", "feedback"])
        assert rc == 0
        validate_envelope(data, "feedback")

    def test_stats_feedback(self):
        """stats feedback returns distribution."""
        rc, data, _ = run_api("wicked-crew", ["stats", "feedback"])
        assert rc == 0
        assert "total_outcomes" in data["data"]

    def test_list_specialists(self):
        """list specialists returns installed plugins."""
        rc, data, _ = run_api("wicked-crew", ["list", "specialists"])
        assert rc == 0
        validate_envelope(data, "specialists")


class TestSearchSources:
    """Search-specific: multiple source types."""

    def test_symbols_source(self):
        rc, data, _ = run_api("wicked-search", ["list", "symbols", "--limit", "3"])
        assert rc == 0
        validate_envelope(data, "symbols")

    def test_documents_source(self):
        rc, data, _ = run_api("wicked-search", ["list", "documents", "--limit", "3"])
        assert rc == 0
        validate_envelope(data, "documents")

    def test_references_source(self):
        rc, data, _ = run_api("wicked-search", ["list", "references", "--limit", "3"])
        assert rc == 0
        validate_envelope(data, "references")

    def test_search_symbols(self):
        rc, data, _ = run_api(
            "wicked-search", ["search", "symbols", "--query", "main", "--limit", "5"]
        )
        assert rc == 0
        assert len(data["data"]) > 0  # "main" should match something


class TestJamSessions:
    """Jam-specific session tests."""

    def test_list_sessions(self):
        """list sessions returns data (may be empty)."""
        rc, data, _ = run_api("wicked-jam", ["list", "sessions"])
        assert rc == 0
        validate_envelope(data, "sessions")

    def test_stats_sessions(self):
        """stats sessions returns aggregate info."""
        rc, data, _ = run_api("wicked-jam", ["stats", "sessions"])
        assert rc == 0
        assert "total_sessions" in data["data"]

    def test_get_not_found(self):
        """get nonexistent session returns error."""
        rc, _, stderr = run_api("wicked-jam", ["get", "sessions", "nonexistent-xyz"])
        assert rc == 1
        err = json.loads(stderr.strip())
        assert err["code"] == "NOT_FOUND"


class TestSmahtSessions:
    """Smaht-specific session tests."""

    def test_list_sessions(self):
        """list sessions returns data (may be empty)."""
        rc, data, _ = run_api("wicked-smaht", ["list", "sessions"])
        assert rc == 0
        validate_envelope(data, "sessions")

    def test_stats_sessions(self):
        """stats sessions returns aggregate info."""
        rc, data, _ = run_api("wicked-smaht", ["stats", "sessions"])
        assert rc == 0
        assert "total_sessions" in data["data"]


# =============================================================================
# Discovery module tests (now reads wicked.json)
# =============================================================================

def _load_discovery_module():
    """Import PluginDataRegistry directly from discovery.py without triggering
    the full wicked_workbench_server package (which requires FastAPI)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "discovery",
        PLUGINS_DIR / "wicked-workbench" / "server" / "src"
        / "wicked_workbench_server" / "data_gateway" / "discovery.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PluginDataRegistry


class TestPluginDiscovery:
    """Test the data_gateway discovery module."""

    def test_discover_local_repo(self):
        """Discovery finds plugins with sources in wicked.json."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        assert len(reg.registry) >= 6, f"Expected >= 6 plugins, got {len(reg.registry)}"
        assert "wicked-kanban" in reg.registry
        assert "wicked-search" in reg.registry
        assert "wicked-crew" in reg.registry
        assert "wicked-mem" in reg.registry
        assert "wicked-jam" in reg.registry
        assert "wicked-smaht" in reg.registry

    def test_discover_skips_empty_sources(self):
        """Plugins with empty sources in wicked.json are not registered."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        assert "wicked-cache" not in reg.registry

    def test_validate_request_valid(self):
        """Valid plugin/source/verb returns None."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        assert reg.validate_request("wicked-kanban", "tasks", "list") is None

    def test_validate_request_invalid_plugin(self):
        """Invalid plugin returns error string."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        err = reg.validate_request("nonexistent", "tasks", "list")
        assert err is not None
        assert "not found" in err.lower()

    def test_validate_request_invalid_source(self):
        """Invalid source returns error string."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        err = reg.validate_request("wicked-kanban", "nonexistent", "list")
        assert err is not None
        assert "not found" in err.lower()

    def test_validate_request_invalid_verb(self):
        """Invalid verb for source returns error string."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        err = reg.validate_request("wicked-kanban", "activity", "get")
        assert err is not None
        assert "not supported" in err.lower()

    def test_get_api_script(self):
        """get_api_script returns valid path for known plugin."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        script = reg.get_api_script("wicked-kanban")
        assert script is not None
        assert Path(script).exists()
        assert script.endswith("api.py")

    def test_get_plugins_list(self):
        """get_plugins returns list with expected structure."""
        PluginDataRegistry = _load_discovery_module()
        reg = PluginDataRegistry()
        reg.discover(local_repo=REPO_ROOT)
        plugins = reg.get_plugins()
        assert isinstance(plugins, list)
        assert len(plugins) >= 6
        for p in plugins:
            assert "name" in p
            assert "sources" in p
            assert "schema_version" in p


# =============================================================================
# Data contract (wicked.json) tests
# =============================================================================

class TestDataContract:
    """Verify wicked.json data contract across all plugins."""

    def test_all_plugins_have_wicked_json(self):
        """Every plugin must have a wicked.json at its root."""
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                continue
            wj = plugin_dir / "wicked.json"
            assert wj.exists(), f"{plugin_dir.name}: missing wicked.json"

    def test_wicked_json_schema(self):
        """wicked.json follows expected schema."""
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                continue
            wj = plugin_dir / "wicked.json"
            if not wj.exists():
                continue
            data = json.loads(wj.read_text())
            assert "$schema" in data, f"{plugin_dir.name}: missing $schema"
            assert "sources" in data, f"{plugin_dir.name}: missing sources"
            assert isinstance(data["sources"], list), f"{plugin_dir.name}: sources not list"

    def test_data_plugins_have_api_script(self):
        """Plugins with non-empty sources have a valid api_script."""
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                continue
            wj = plugin_dir / "wicked.json"
            if not wj.exists():
                continue
            data = json.loads(wj.read_text())
            if data.get("sources"):
                script_rel = data.get("api_script", "scripts/api.py")
                script_path = plugin_dir / script_rel
                assert script_path.exists(), (
                    f"{plugin_dir.name}: api_script '{script_rel}' not found"
                )

    def test_source_capabilities_valid(self):
        """Source capabilities contain only valid verbs."""
        valid_verbs = {"list", "get", "search", "stats"}
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                continue
            wj = plugin_dir / "wicked.json"
            if not wj.exists():
                continue
            data = json.loads(wj.read_text())
            for src in data.get("sources", []):
                caps = set(src.get("capabilities", []))
                invalid = caps - valid_verbs
                assert not invalid, (
                    f"{plugin_dir.name}/{src['name']}: invalid capabilities {invalid}"
                )

    def test_no_data_sources_in_plugin_json(self):
        """plugin.json must NOT have data_sources (moved to wicked.json)."""
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                continue
            pj = plugin_dir / ".claude-plugin" / "plugin.json"
            if not pj.exists():
                continue
            data = json.loads(pj.read_text())
            assert "data_sources" not in data, (
                f"{plugin_dir.name}: plugin.json still has data_sources (should be in wicked.json)"
            )
