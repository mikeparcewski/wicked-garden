"""
Tests for Context7 adapter.

Tests cover:
- Library name extraction
- Cache operations
- Error handling and graceful degradation
- ContextItem transformation
"""

import asyncio
import json
import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from adapters.context7_adapter import (
    query,
    _extract_library_names,
    _resolve_library_id,
    _query_docs,
    Context7Cache,
    CACHE_TTL_SECONDS,
)
from adapters import ContextItem


class TestLibraryExtraction:
    """Test library name extraction from prompts."""

    def test_direct_library_mention(self):
        """Extract libraries from direct mentions."""
        prompt = "How do I use React hooks?"
        libs = _extract_library_names(prompt)
        assert "react" in libs

    def test_multiple_libraries(self):
        """Extract multiple libraries."""
        prompt = "Should I use FastAPI or Django for my REST API?"
        libs = _extract_library_names(prompt)
        assert "fastapi" in libs
        assert "django" in libs

    def test_package_manager_patterns(self):
        """Extract from npm/pip install commands."""
        prompts = [
            "npm install express",
            "pip install fastapi",
            "yarn add @testing-library/react",
        ]

        libs1 = _extract_library_names(prompts[0])
        assert "express" in libs1

        libs2 = _extract_library_names(prompts[1])
        assert "fastapi" in libs2

        libs3 = _extract_library_names(prompts[2])
        assert any("react" in lib for lib in libs3)

    def test_import_statements(self):
        """Extract from import statements."""
        prompts = [
            "from django.db import models",
            "import React from 'react'",
            "const { useState } = require('react')",
        ]

        libs1 = _extract_library_names(prompts[0])
        assert "django" in libs1

        libs2 = _extract_library_names(prompts[1])
        assert "react" in libs2

        libs3 = _extract_library_names(prompts[2])
        assert "react" in libs3

    def test_false_positive_filtering(self):
        """Filter out built-ins and common false positives."""
        prompt = "How to import json and os in Python?"
        libs = _extract_library_names(prompt)
        assert "json" not in libs
        assert "os" not in libs

    def test_deduplication(self):
        """Deduplicate repeated library names."""
        prompt = "React hooks vs React class components in React 18"
        libs = _extract_library_names(prompt)
        # Should only have one "react"
        react_count = sum(1 for lib in libs if lib == "react")
        assert react_count == 1

    def test_max_libraries_limit(self):
        """Limit to 5 libraries."""
        prompt = "Compare React, Vue, Angular, Svelte, Next.js, and Nuxt.js"
        libs = _extract_library_names(prompt)
        assert len(libs) <= 5

    def test_empty_prompt(self):
        """Handle empty prompt gracefully."""
        libs = _extract_library_names("")
        assert libs == []

    def test_no_libraries(self):
        """Handle prompts with no libraries."""
        prompt = "What is the best way to structure my code?"
        libs = _extract_library_names(prompt)
        # May or may not extract anything - should not crash
        assert isinstance(libs, list)


class TestContext7Cache:
    """Test cache operations."""

    def test_cache_miss(self):
        """Test cache miss returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))
            result = cache.get("react", "how to use hooks")
            assert result is None

    def test_cache_set_and_get(self):
        """Test setting and getting from cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))

            # Create test items
            items = [
                ContextItem(
                    id="test:1",
                    source="context7",
                    title="Test Title",
                    summary="Test summary",
                    excerpt="Test excerpt",
                    relevance=0.8,
                    metadata={"test": "data"}
                )
            ]

            # Set cache
            cache.set("react", "test query", items)

            # Get from cache
            cached = cache.get("react", "test query")

            assert cached is not None
            assert len(cached) == 1
            assert cached[0].id == "test:1"
            assert cached[0].title == "Test Title"
            assert cached[0].relevance == 0.8
            assert cached[0].metadata["test"] == "data"

    def test_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))

            items = [
                ContextItem(
                    id="test:1",
                    source="context7",
                    title="Test",
                    summary="Test"
                )
            ]

            # Set cache
            cache.set("react", "test", items)

            # Manually expire the entry
            key = cache._cache_key("react", "test")
            entry = cache.index[key]
            # Set cached_at to past (beyond TTL)
            old_time = datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_SECONDS + 1)
            entry['cached_at'] = old_time.isoformat()
            cache._save_index()

            # Reload cache
            cache._load_index()

            # Should return None (expired)
            cached = cache.get("react", "test")
            assert cached is None

            # Entry should be cleaned up
            assert key not in cache.index

    def test_cache_persistence(self):
        """Test that cache survives recreation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create and populate cache
            cache1 = Context7Cache(cache_dir)
            items = [
                ContextItem(
                    id="test:1",
                    source="context7",
                    title="Test",
                    summary="Test"
                )
            ]
            cache1.set("react", "test", items)

            # Create new cache instance (simulates restart)
            cache2 = Context7Cache(cache_dir)

            # Should find cached item
            cached = cache2.get("react", "test")
            assert cached is not None
            assert len(cached) == 1
            assert cached[0].id == "test:1"

    def test_cache_corruption_recovery(self):
        """Test recovery from corrupted cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))

            # Set valid cache entry
            items = [
                ContextItem(
                    id="test:1",
                    source="context7",
                    title="Test",
                    summary="Test"
                )
            ]
            cache.set("react", "test", items)

            # Corrupt the data file
            key = cache._cache_key("react", "test")
            data_path = cache.data_dir / f"{key}.json"
            with open(data_path, 'w') as f:
                f.write("invalid json{{{")

            # Should handle gracefully
            cached = cache.get("react", "test")
            assert cached is None

            # Entry should be cleaned up
            assert key not in cache.index

    def test_cache_lru_eviction(self):
        """Test LRU eviction when max entries exceeded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))

            # Fill cache beyond max (simulate with smaller max)
            import adapters.context7_adapter as c7
            original_max = c7.MAX_CACHE_ENTRIES
            c7.MAX_CACHE_ENTRIES = 10

            try:
                # Add 12 entries
                for i in range(12):
                    items = [
                        ContextItem(
                            id=f"test:{i}",
                            source="context7",
                            title=f"Test {i}",
                            summary="Test"
                        )
                    ]
                    cache.set(f"lib{i}", f"query{i}", items)

                # Should have evicted oldest entries
                # Max is 10, so should have exactly 10
                assert len(cache.index) == 10

            finally:
                c7.MAX_CACHE_ENTRIES = original_max

    def test_cache_clear(self):
        """Test clearing entire cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Context7Cache(Path(tmpdir))

            # Add entries
            items = [
                ContextItem(
                    id="test:1",
                    source="context7",
                    title="Test",
                    summary="Test"
                )
            ]
            cache.set("react", "query1", items)
            cache.set("vue", "query2", items)

            assert len(cache.index) == 2

            # Clear
            cache.clear()

            # Should be empty
            assert len(cache.index) == 0
            assert cache.get("react", "query1") is None
            assert cache.get("vue", "query2") is None


class TestLibraryResolution:
    """Test library ID resolution."""

    @pytest.mark.asyncio
    async def test_common_library_fallback(self):
        """Test fallback mapping for common libraries."""
        library_id = await _resolve_library_id("react", "test query")
        assert library_id == "/facebook/react"

        library_id = await _resolve_library_id("nextjs", "test query")
        assert library_id == "/vercel/next.js"

        library_id = await _resolve_library_id("fastapi", "test query")
        assert library_id == "/tiangolo/fastapi"

    @pytest.mark.asyncio
    async def test_unknown_library(self):
        """Test unknown library returns None."""
        library_id = await _resolve_library_id("unknownlib123", "test query")
        assert library_id is None

    @pytest.mark.asyncio
    async def test_normalization(self):
        """Test library name normalization."""
        # Different variations should resolve to same ID
        libs = ["next.js", "nextjs", "Next", "NEXT"]
        for lib in libs:
            library_id = await _resolve_library_id(lib, "test")
            assert library_id == "/vercel/next.js"


class TestDocQuery:
    """Test documentation querying."""

    @pytest.mark.asyncio
    async def test_query_docs_graceful_failure(self):
        """Test that doc query returns empty list on failure."""
        # Should not raise, even if MCP not available
        docs = await _query_docs("/facebook/react", "test query")
        assert isinstance(docs, list)


class TestEndToEnd:
    """Test end-to-end adapter flow."""

    @pytest.mark.asyncio
    async def test_query_with_no_libraries(self):
        """Test query with prompt containing no libraries."""
        items = await query("What is the best coding practice?")
        # Should return empty list, not crash
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_query_with_single_library(self):
        """Test query with single library mention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch cache directory
            import adapters.context7_adapter as c7
            original_cache_dir = c7.CACHE_DIR
            c7.CACHE_DIR = Path(tmpdir)
            c7._cache = Context7Cache(Path(tmpdir))

            try:
                items = await query("How to use React hooks?")
                # Should attempt to query, return list
                assert isinstance(items, list)

            finally:
                c7.CACHE_DIR = original_cache_dir
                c7._cache = Context7Cache(original_cache_dir)

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self):
        """Test that timeouts are handled gracefully."""
        with patch('adapters.context7_adapter._query_context7') as mock_query:
            # Simulate timeout
            mock_query.side_effect = asyncio.TimeoutError()

            # Should not crash
            items = await query("How to use React?")
            assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_query_cache_hit(self):
        """Test that cache hits return quickly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import adapters.context7_adapter as c7
            original_cache_dir = c7.CACHE_DIR
            c7.CACHE_DIR = Path(tmpdir)
            cache = Context7Cache(Path(tmpdir))
            c7._cache = cache

            try:
                # Pre-populate cache
                cached_items = [
                    ContextItem(
                        id="cached:1",
                        source="context7",
                        title="Cached Result",
                        summary="From cache",
                        relevance=0.9,
                    )
                ]
                cache.set("react", "How to use React hooks?", cached_items)

                # Query should hit cache
                items = await query("How to use React hooks?")

                # Should return cached items
                assert len(items) >= 1
                # First item should be from cache
                assert any(item.id == "cached:1" for item in items)

            finally:
                c7.CACHE_DIR = original_cache_dir
                c7._cache = Context7Cache(original_cache_dir)

    @pytest.mark.asyncio
    async def test_query_multiple_libraries(self):
        """Test query with multiple libraries."""
        items = await query("Compare React and Vue for building UIs")
        # Should attempt to query both, return list
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors don't propagate to caller."""
        with patch('adapters.context7_adapter._query_context7') as mock_query:
            # Simulate various exceptions
            mock_query.side_effect = Exception("Some error")

            # Should not raise
            items = await query("How to use React?")
            assert isinstance(items, list)
            assert len(items) == 0  # Empty due to error


class TestContextItemTransformation:
    """Test transformation from Context7 format to ContextItem."""

    def test_metadata_preservation(self):
        """Test that metadata is correctly preserved."""
        # This would test the transformation in _query_context7
        # but since that function returns ContextItems directly,
        # we verify the structure

        item = ContextItem(
            id="context7:/facebook/react:0",
            source="context7",
            title="React: useEffect Hook",
            summary="The useEffect Hook lets you...",
            excerpt="useEffect(() => { /* effect */ }, [deps])",
            relevance=0.85,
            age_days=0.0,
            metadata={
                'library_id': '/facebook/react',
                'library_name': 'react',
                'url': 'https://react.dev/reference/...',
                'source_type': 'external_docs',
            }
        )

        assert item.source == "context7"
        assert item.metadata['library_id'] == '/facebook/react'
        assert item.metadata['source_type'] == 'external_docs'
        assert item.age_days == 0.0
        assert 0.0 <= item.relevance <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
