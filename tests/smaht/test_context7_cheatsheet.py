"""Tests for _lookup_cheatsheet() in context7_adapter.py

Covers:
- Returns a ContextItem with relevance=0.85 when cheatsheet exists
- Returns None when the library is not found ({"found": false})
- Returns None on subprocess timeout
- Returns None when subprocess returns bad JSON
- Returns None on non-zero subprocess returncode
"""

import json
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup so we can import the adapters package directly
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
_SMAHT_DIR = _SCRIPTS_ROOT / "smaht"

sys.path.insert(0, str(_SCRIPTS_ROOT))
sys.path.insert(0, str(_SMAHT_DIR))

# We need _domain_store available before importing adapters (used at module level
# via get_local_path in context7_adapter).  Provide a minimal fake.

def _install_storage_stub():
    fake = types.ModuleType("_domain_store")
    import tempfile
    tmp = Path(tempfile.mkdtemp())

    def get_local_path(*parts):
        p = tmp.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    fake.get_local_path = get_local_path
    fake.DomainStore = MagicMock()
    sys.modules["_domain_store"] = fake
    return fake


_install_storage_stub()

# Import the adapters package. The adapters directory has __init__.py so it is
# a proper package.  We register it under the name "adapters" and exec __init__
# first — that defines ContextItem and _SCRIPTS_ROOT which context7_adapter
# imports via `from . import ...`.
import importlib.util as _ilu

_adapters_dir = _SMAHT_DIR / "adapters"

def _load_pkg_module(pkg_name, file_path, parent_pkg=None):
    spec = _ilu.spec_from_file_location(
        pkg_name,
        file_path,
        submodule_search_locations=[str(file_path.parent)],
    )
    mod = _ilu.module_from_spec(spec)
    mod.__package__ = parent_pkg or pkg_name
    sys.modules[pkg_name] = mod
    return spec, mod

# 1. Register package stub first so relative imports can find siblings
_pkg_spec, _adapters_pkg = _load_pkg_module("adapters", _adapters_dir / "__init__.py")

# 2. Stub out sub-modules that __init__ imports to avoid their side-effects
for _sub in ("cp_adapter", "context7_adapter"):
    _stub = types.ModuleType(f"adapters.{_sub}")
    _stub.__package__ = "adapters"
    sys.modules[f"adapters.{_sub}"] = _stub

# 3. Exec __init__ — this defines ContextItem, _SCRIPTS_ROOT, run_subprocess etc.
_pkg_spec.loader.exec_module(_adapters_pkg)

# 4. Now load context7_adapter properly (relative import `from . import ...` works
#    because sys.modules["adapters"] is fully populated)
_c7_spec = _ilu.spec_from_file_location(
    "adapters.context7_adapter",
    _adapters_dir / "context7_adapter.py",
    submodule_search_locations=[str(_adapters_dir)],
)
_c7_mod = _ilu.module_from_spec(_c7_spec)
_c7_mod.__package__ = "adapters"
sys.modules["adapters.context7_adapter"] = _c7_mod
_c7_spec.loader.exec_module(_c7_mod)

context7_adapter = _c7_mod
ContextItem = _adapters_pkg.ContextItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_process(returncode=0, stdout="", stderr=""):
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _cheatsheet_payload(**overrides):
    base = {
        "library": "react",
        "version_hint": "18.x",
        "key_apis": [
            {"name": "useState", "example": "const [s, setS] = useState(0)"},
            {"name": "useEffect"},
        ],
        "common_patterns": [{"name": "controlled input"}],
        "gotchas": ["Don't call hooks conditionally", "Avoid mutations in render"],
        "source_url": "https://react.dev",
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLookupCheatsheet:
    def test_returns_context_item_when_cheatsheet_exists(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(
            returncode=0,
            stdout=json.dumps(payload),
        )

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is not None
        assert isinstance(item, ContextItem)

    def test_relevance_is_0_85(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item.relevance == 0.85

    def test_source_is_cheatsheet(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item.source == "cheatsheet"

    def test_id_contains_library_name(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert "react" in item.id

    def test_title_includes_version_when_present(self):
        payload = _cheatsheet_payload(version_hint="18.x")
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert "18.x" in item.title

    def test_summary_includes_key_api_names(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert "useState" in item.summary

    def test_excerpt_includes_example_from_first_api(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert "useState" in item.excerpt

    def test_returns_none_when_found_is_false(self):
        not_found = json.dumps({"found": False})
        mock_result = _make_completed_process(returncode=0, stdout=not_found)

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("nonexistent-lib")

        assert item is None

    def test_returns_none_on_nonzero_returncode(self):
        mock_result = _make_completed_process(returncode=1, stdout="", stderr="error")

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is None

    def test_returns_none_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="python3", timeout=2.0)):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is None

    def test_returns_none_on_bad_json(self):
        mock_result = _make_completed_process(returncode=0, stdout="not-json{{{")

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is None

    def test_returns_none_on_generic_subprocess_exception(self):
        with patch("subprocess.run", side_effect=OSError("git not found")):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is None

    def test_metadata_contains_library(self):
        payload = _cheatsheet_payload()
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item.metadata["library"] == "react"

    def test_metadata_api_count(self):
        payload = _cheatsheet_payload()  # 2 key_apis
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item.metadata["api_count"] == 2

    def test_handles_empty_key_apis_gracefully(self):
        payload = _cheatsheet_payload(key_apis=[], common_patterns=[], gotchas=[])
        mock_result = _make_completed_process(returncode=0, stdout=json.dumps(payload))

        with patch("subprocess.run", return_value=mock_result):
            item = context7_adapter._lookup_cheatsheet("react")

        assert item is not None
        assert item.relevance == 0.85
