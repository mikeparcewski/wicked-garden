#!/usr/bin/env python3
"""
tests/smaht/test_adapter_registry.py

Unit tests for AdapterRegistry and timed_query (Task 4.2).

AC coverage: AC-1.1, AC-1.3, AC-1.5, AC-2.1, AC-2.2, AC-2.3, AC-3.1, AC-3.4, AC-3.5
Scenario coverage: S-REG-1..5, S-TQ-1..7, Gap G-1, G-2

Tests use stdlib unittest + unittest.mock. Async tests use asyncio.run() in test
methods (no pytest-asyncio dependency), matching the existing test suite pattern.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_V2_DIR = _REPO_ROOT / "scripts" / "smaht" / "v2"
_ADAPTERS_DIR = _REPO_ROOT / "scripts" / "smaht"

sys.path.insert(0, str(_V2_DIR))
sys.path.insert(0, str(_ADAPTERS_DIR))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# AdapterRegistry tests
# ---------------------------------------------------------------------------

class TestAdapterRegistryLoad(unittest.TestCase):
    """S-REG-1..5: Registry loading, available(), get()."""

    def _make_registry_with_all_loaded(self):
        """Return an AdapterRegistry instance with all 5 adapters mocked as loaded."""
        from adapter_registry import AdapterRegistry

        mock_modules = {name: MagicMock() for name in AdapterRegistry.KNOWN_ADAPTERS}

        def fake_import(name, fromlist=None, **kwargs):
            # Map module path back to adapter name
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return mock_modules[adapter_name]
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()

        return registry, mock_modules

    def test_registry_loads_all_five_adapters(self):
        """S-REG-1: All 5 adapters load successfully — available() returns all 5 names."""
        from adapter_registry import AdapterRegistry

        mock_modules = {name: MagicMock() for name in AdapterRegistry.KNOWN_ADAPTERS}

        def fake_import(name, fromlist=None, **kwargs):
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return mock_modules[adapter_name]
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()

        available = registry.available()
        self.assertEqual(set(available), set(AdapterRegistry.KNOWN_ADAPTERS.keys()))
        self.assertEqual(len(available), 5)

    def test_registry_graceful_degradation_on_single_import_error(self):
        """S-REG-2 / AC-3.4: One adapter import fails — remaining 4 load. Missing absent from get()."""
        from adapter_registry import AdapterRegistry

        mock_modules = {name: MagicMock() for name in AdapterRegistry.KNOWN_ADAPTERS}
        failing_name = "context7"
        failing_path = AdapterRegistry.KNOWN_ADAPTERS[failing_name]

        def fake_import(name, fromlist=None, **kwargs):
            if name == failing_path:
                raise ImportError("context7 dependency missing")
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return mock_modules[adapter_name]
            raise ImportError(f"Unexpected import: {name}")

        import io
        with patch("builtins.__import__", side_effect=fake_import):
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                registry = AdapterRegistry()
                stderr_output = mock_stderr.getvalue()

        # 4 remaining adapters loaded
        available = registry.available()
        self.assertEqual(len(available), 4)
        self.assertNotIn(failing_name, available)

        # get() silently omits missing
        result = registry.get([failing_name])
        self.assertEqual(result, {})

        # Other adapters unaffected
        domain_result = registry.get(["domain"])
        self.assertIn("domain", domain_result)

        # Warning logged to stderr
        self.assertIn(failing_name, stderr_output)

    def test_registry_graceful_degradation_all_fail(self):
        """S-REG-3: All adapters fail — registry is empty, no exception raised."""
        from adapter_registry import AdapterRegistry

        def fake_import(name, fromlist=None, **kwargs):
            for module_path in AdapterRegistry.KNOWN_ADAPTERS.values():
                if name == module_path:
                    raise ImportError("all broken")
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()  # Must not raise

        self.assertEqual(registry.available(), [])
        self.assertEqual(registry.get(["domain"]), {})

    def test_get_returns_requested_subset(self):
        """S-REG-4 partial: get() returns only the requested names from those loaded."""
        from adapter_registry import AdapterRegistry

        mock_modules = {name: MagicMock() for name in AdapterRegistry.KNOWN_ADAPTERS}

        def fake_import(name, fromlist=None, **kwargs):
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return mock_modules[adapter_name]
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()

        result = registry.get(["domain", "context7"])
        self.assertEqual(set(result.keys()), {"domain", "context7"})

    def test_get_omits_unknown_names(self):
        """S-REG-4: get() with unknown/missing name returns only known loaded adapters."""
        from adapter_registry import AdapterRegistry

        mock_modules = {name: MagicMock() for name in AdapterRegistry.KNOWN_ADAPTERS}

        def fake_import(name, fromlist=None, **kwargs):
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return mock_modules[adapter_name]
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()

        result = registry.get(["domain", "nonexistent_adapter"])
        self.assertEqual(set(result.keys()), {"domain"})

    def test_get_with_empty_list(self):
        """S-REG-5: get([]) returns {} with no error."""
        from adapter_registry import AdapterRegistry

        def fake_import(name, fromlist=None, **kwargs):
            for adapter_name, module_path in AdapterRegistry.KNOWN_ADAPTERS.items():
                if name == module_path:
                    return MagicMock()
            raise ImportError(f"Unexpected import: {name}")

        with patch("builtins.__import__", side_effect=fake_import):
            registry = AdapterRegistry()

        result = registry.get([])
        self.assertEqual(result, {})

    def test_known_adapters_is_class_constant(self):
        """Gap G-4: KNOWN_ADAPTERS is accessible without instantiation."""
        from adapter_registry import AdapterRegistry

        # Access as class attribute (not instance attribute)
        adapters = AdapterRegistry.KNOWN_ADAPTERS
        self.assertIsInstance(adapters, dict)
        self.assertEqual(len(adapters), 5)
        self.assertIn("domain", adapters)
        self.assertIn("mem", adapters)
        self.assertIn("context7", adapters)
        self.assertIn("tools", adapters)
        self.assertIn("delegation", adapters)


# ---------------------------------------------------------------------------
# timed_query tests
# ---------------------------------------------------------------------------

class TestTimedQueryCacheMiss(unittest.TestCase):
    """S-TQ-1 / AC-1.1 / AC-2.1: Cache miss — adapter called, timing recorded, result cached."""

    def test_cache_miss_calls_adapter_and_records_timing(self):
        """Adapter called once, call_count=1, total_ms>0, result in call_cache."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[{"title": "result1"}])

        call_cache = {}
        timing_acc = {}

        result = asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="domain",
            prompt="test prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset(),
        ))

        mock_mod.query.assert_awaited_once_with("test prompt")
        self.assertEqual(timing_acc["domain"]["call_count"], 1)
        self.assertGreater(timing_acc["domain"]["total_ms"], 0)
        self.assertEqual(timing_acc["domain"]["cache_hits"], 0)
        self.assertEqual(timing_acc["domain"]["failures"], 0)
        self.assertIn("domain", call_cache)
        self.assertEqual(result, [{"title": "result1"}])

    def test_cache_miss_result_stored_in_call_cache(self):
        """Cache miss stores result in call_cache for subsequent deduplication."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[{"title": "cached"}])

        call_cache = {}
        timing_acc = {}

        asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="domain",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset(),
        ))

        self.assertEqual(call_cache["domain"], [{"title": "cached"}])


class TestTimedQueryCacheHit(unittest.TestCase):
    """S-TQ-2 / AC-1.1 / AC-2.2: Cache hit — adapter NOT called, cache_hits incremented."""

    def test_cache_hit_skips_adapter_call(self):
        """Pre-populated call_cache: adapter query NOT called, cache_hits=1."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock()

        cached_data = [{"title": "cached result"}]
        call_cache = {"domain": cached_data}
        timing_acc = {}

        result = asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="domain",
            prompt="any prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset(),
        ))

        mock_mod.query.assert_not_awaited()
        self.assertEqual(timing_acc["domain"]["cache_hits"], 1)
        self.assertEqual(timing_acc["domain"].get("call_count", 0), 0)
        self.assertEqual(timing_acc["domain"].get("total_ms", 0), 0)
        self.assertEqual(result, cached_data)

    def test_cache_hit_does_not_update_total_ms(self):
        """AC-2.2: Cache hit increments cache_hits but total_ms stays at 0 (not accumulated)."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock()

        call_cache = {"domain": ["something"]}
        timing_acc = {}

        asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="domain",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset(),
        ))

        self.assertEqual(timing_acc["domain"]["cache_hits"], 1)
        # total_ms is initialized to 0 by setdefault but never incremented on cache hit
        self.assertEqual(timing_acc["domain"].get("total_ms", 0), 0)


class TestTimedQueryMemBypass(unittest.TestCase):
    """S-TQ-3 / AC-1.3: mem adapter bypassed — always called, NOT written to cache."""

    def test_mem_bypass_calls_adapter_despite_cache_entry(self):
        """cache_bypass=frozenset({'mem'}) forces fresh query even when call_cache has entry."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        fresh_result = [{"title": "fresh result"}]
        mock_mod.query = AsyncMock(return_value=fresh_result)

        stale_entry = [{"title": "stale cached result"}]
        call_cache = {"mem": stale_entry}
        timing_acc = {}

        result = asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="mem",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset({"mem"}),
        ))

        mock_mod.query.assert_awaited_once_with("prompt")
        self.assertEqual(result, fresh_result)

    def test_mem_bypass_does_not_write_to_call_cache(self):
        """Gap G-2: mem result is NOT written to call_cache after query (always-fresh design)."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[{"title": "fresh"}])

        call_cache = {}
        timing_acc = {}

        asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="mem",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset({"mem"}),
        ))

        # mem result must NOT be stored in call_cache
        self.assertNotIn("mem", call_cache)

    def test_mem_bypass_two_calls_both_invoke_adapter(self):
        """Gap G-2: Two calls for mem → two adapter query() invocations (no caching)."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[{"title": "result"}])

        call_cache = {}
        timing_acc = {}

        asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="mem",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset({"mem"}),
        ))
        asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="mem",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=call_cache,
            cache_bypass=frozenset({"mem"}),
        ))

        self.assertEqual(mock_mod.query.await_count, 2)


class TestTimedQueryFailure(unittest.TestCase):
    """S-TQ-4 / S-TQ-5 / AC-1.5 / AC-2.3: Failure — recorded in timing, exception re-raised."""

    def test_exception_reraises_and_records_failure(self):
        """S-TQ-4 / AC-2.3: Exception re-raised, failures=1, total_ms not incremented."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(side_effect=Exception("adapter crash"))

        call_cache = {}
        timing_acc = {}

        with self.assertRaises(Exception) as ctx:
            asyncio.run(timed_query(
                adapter_mod=mock_mod,
                name="domain",
                prompt="prompt",
                timeout=1.0,
                timing_accumulator=timing_acc,
                call_cache=call_cache,
                cache_bypass=frozenset(),
            ))

        self.assertEqual(str(ctx.exception), "adapter crash")
        self.assertEqual(timing_acc["domain"]["failures"], 1)
        self.assertEqual(timing_acc["domain"].get("total_ms", 0), 0)
        self.assertEqual(timing_acc["domain"].get("call_count", 0), 0)
        self.assertNotIn("domain", call_cache)

    def test_timeout_error_records_failure(self):
        """S-TQ-5 / AC-2.3: asyncio.TimeoutError treated as failure."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(side_effect=asyncio.TimeoutError())

        timing_acc = {}

        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(timed_query(
                adapter_mod=mock_mod,
                name="context7",
                prompt="prompt",
                timeout=0.001,
                timing_accumulator=timing_acc,
                call_cache={},
                cache_bypass=frozenset(),
            ))

        self.assertEqual(timing_acc["context7"]["failures"], 1)
        self.assertEqual(timing_acc["context7"].get("total_ms", 0), 0)


class TestTimedQueryNoCacheMode(unittest.TestCase):
    """S-TQ-6 / Gap G-1: call_cache=None — no caching, adapter always called."""

    def test_none_call_cache_always_calls_adapter(self):
        """Gap G-1 / S-TQ-6: call_cache=None guard — adapter called, no TypeError."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[{"title": "result"}])

        timing_acc = {}

        result = asyncio.run(timed_query(
            adapter_mod=mock_mod,
            name="domain",
            prompt="prompt",
            timeout=1.0,
            timing_accumulator=timing_acc,
            call_cache=None,
            cache_bypass=frozenset(),
        ))

        mock_mod.query.assert_awaited_once()
        self.assertEqual(timing_acc["domain"]["call_count"], 1)
        self.assertGreater(timing_acc["domain"]["total_ms"], 0)

    def test_none_call_cache_second_call_hits_adapter_again(self):
        """call_cache=None: second call also hits adapter (no cache to deduplicate)."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=[])

        timing_acc = {}

        asyncio.run(timed_query(
            adapter_mod=mock_mod, name="domain", prompt="p1",
            timeout=1.0, timing_accumulator=timing_acc,
            call_cache=None, cache_bypass=frozenset(),
        ))
        asyncio.run(timed_query(
            adapter_mod=mock_mod, name="domain", prompt="p2",
            timeout=1.0, timing_accumulator=timing_acc,
            call_cache=None, cache_bypass=frozenset(),
        ))

        self.assertEqual(mock_mod.query.await_count, 2)
        self.assertEqual(timing_acc["domain"]["call_count"], 2)


class TestTimedQueryAccumulation(unittest.TestCase):
    """S-TQ-7: Accumulated timing across multiple calls to same timing_accumulator."""

    def test_accumulates_across_different_adapters(self):
        """Same timing_acc dict accumulates entries for different adapter names."""
        from adapter_registry import timed_query

        mock_domain = MagicMock()
        mock_domain.query = AsyncMock(return_value=[])
        mock_context7 = MagicMock()
        mock_context7.query = AsyncMock(return_value=[])

        call_cache = {}
        timing_acc = {}

        asyncio.run(timed_query(
            mock_domain, "domain", "p1", 1.0, timing_acc, call_cache, frozenset()
        ))
        asyncio.run(timed_query(
            mock_context7, "context7", "p2", 1.0, timing_acc, call_cache, frozenset()
        ))

        self.assertIn("domain", timing_acc)
        self.assertIn("context7", timing_acc)
        self.assertEqual(timing_acc["domain"]["call_count"], 1)
        self.assertEqual(timing_acc["context7"]["call_count"], 1)

    def test_cache_hit_after_miss_accumulates_correctly(self):
        """S-TQ-7 partial: call_count=1, cache_hits=1 after miss then hit."""
        from adapter_registry import timed_query

        mock_mod = MagicMock()
        mock_mod.query = AsyncMock(return_value=["item"])

        call_cache = {}
        timing_acc = {}

        # First call: cache miss
        asyncio.run(timed_query(
            mock_mod, "domain", "prompt", 1.0, timing_acc, call_cache, frozenset()
        ))
        # Second call: cache hit (call_cache["domain"] is now populated)
        asyncio.run(timed_query(
            mock_mod, "domain", "prompt", 1.0, timing_acc, call_cache, frozenset()
        ))

        self.assertEqual(timing_acc["domain"]["call_count"], 1)
        self.assertEqual(timing_acc["domain"]["cache_hits"], 1)
        self.assertEqual(mock_mod.query.await_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
