#!/usr/bin/env python3
"""
Unit tests for wicked-smaht v2 Router.

Tests:
- Intent detection patterns
- Confidence scoring
- Path decision logic
- Entity extraction
- Escalation triggers
"""

import sys
from pathlib import Path

# Add v2 to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "v2"))

import pytest
from router import Router, IntentType, PathDecision


class TestIntentDetection:
    """Test intent detection patterns."""

    def test_debugging_intent(self):
        router = Router()
        decision = router.route("There's a bug in the parser")
        assert decision.analysis.intent_type == IntentType.DEBUGGING

    def test_debugging_intent_error(self):
        router = Router()
        decision = router.route("I'm getting an error when running tests")
        assert decision.analysis.intent_type == IntentType.DEBUGGING

    def test_planning_intent(self):
        router = Router()
        decision = router.route("Let's design the authentication system")
        assert decision.analysis.intent_type == IntentType.PLANNING

    def test_research_intent(self):
        router = Router()
        decision = router.route("What is the purpose of this function?")
        assert decision.analysis.intent_type == IntentType.RESEARCH

    def test_implementation_intent(self):
        router = Router()
        decision = router.route("Add a new feature to handle caching")
        assert decision.analysis.intent_type == IntentType.IMPLEMENTATION

    def test_review_intent(self):
        router = Router()
        decision = router.route("Review this PR for any issues")
        assert decision.analysis.intent_type == IntentType.REVIEW

    def test_general_intent_fallback(self):
        router = Router()
        decision = router.route("hello")
        assert decision.analysis.intent_type == IntentType.GENERAL


class TestConfidenceScoring:
    """Test confidence score calculations."""

    def test_high_confidence_clear_intent(self):
        router = Router()
        decision = router.route("Fix the bug in parser.py")
        assert decision.analysis.confidence > 0.7

    def test_low_confidence_vague_prompt(self):
        router = Router()
        decision = router.route("hmm")
        assert decision.analysis.confidence < 0.5

    def test_multiple_keywords_boost_confidence(self):
        router = Router()
        decision = router.route("Debug and fix the failing test with the error")
        assert decision.analysis.confidence > 0.7


class TestPathDecision:
    """Test fast vs slow path routing."""

    def test_fast_path_simple_clear_request(self):
        # Pre-populate session topics so it's not "novel"
        # Use multiple keywords to boost confidence above 0.7
        router = Router(session_topics=["cache", "search"])
        decision = router.route("Search and find cache documentation")
        # Short, clear, familiar topic, high confidence - should be fast
        assert decision.analysis.confidence > 0.7, f"Confidence {decision.analysis.confidence} too low"
        assert decision.path == PathDecision.FAST, f"Got {decision.path} with reason: {decision.reason}"

    def test_slow_path_planning_request(self):
        router = Router()
        decision = router.route("Let's design a new caching strategy with trade-offs")
        assert decision.path == PathDecision.SLOW
        assert "planning" in decision.reason.lower()

    def test_slow_path_long_prompt(self):
        router = Router()
        long_prompt = " ".join(["word"] * 250)  # 250 words
        decision = router.route(long_prompt)
        assert decision.path == PathDecision.SLOW
        assert "long" in decision.reason.lower() or "word" in decision.reason.lower()

    def test_slow_path_history_reference(self):
        router = Router()
        decision = router.route("Like we discussed earlier, let's do that thing")
        assert decision.path == PathDecision.SLOW
        assert "history" in decision.reason.lower()

    def test_slow_path_compound_request(self):
        router = Router()
        decision = router.route("First add caching, and then update the tests, and also fix the docs")
        assert decision.path == PathDecision.SLOW
        assert "compound" in decision.reason.lower()


class TestEntityExtraction:
    """Test entity extraction from prompts."""

    def test_extract_file_names(self):
        router = Router()
        decision = router.route("Look at parser.py and test_parser.py")
        assert "parser.py" in decision.analysis.entities
        assert "test_parser.py" in decision.analysis.entities

    def test_extract_paths(self):
        router = Router()
        decision = router.route("Check src/components/Button.tsx")
        entities = decision.analysis.entities
        # Should extract the path
        assert any("src/" in e or "Button.tsx" in e for e in entities)

    def test_extract_class_names(self):
        router = Router()
        decision = router.route("The CacheManager class needs updating")
        assert "CacheManager" in decision.analysis.entities


class TestEscalationTriggers:
    """Test escalation trigger detection."""

    def test_escalate_low_confidence(self):
        router = Router()
        decision = router.route("maybe something")
        if decision.analysis.confidence < 0.5:
            assert decision.path == PathDecision.SLOW

    def test_escalate_many_entities(self):
        router = Router()
        decision = router.route(
            "Check parser.py, lexer.py, ast.py, visitor.py, compiler.py, and runtime.py"
        )
        assert decision.analysis.entity_count >= 5
        # Many entities should trigger slow path
        assert decision.path == PathDecision.SLOW

    def test_escalate_novel_topic(self):
        router = Router(session_topics=["cache", "parser", "utils"])
        decision = router.route("Let's work on the auth.py module")
        # Novel topic (auth not in session)
        assert decision.analysis.is_novel


class TestSessionTopics:
    """Test session topic tracking for novelty detection."""

    def test_update_session_topics(self):
        router = Router()
        decision = router.route("Working on cache.py")
        router.update_session_topics(decision.analysis.entities)

        # Now cache.py should not be novel
        decision2 = router.route("More work on cache.py")
        assert not decision2.analysis.is_novel

    def test_novel_detection_with_existing_topics(self):
        router = Router(session_topics=["cache.py", "parser.py", "utils.py"])
        decision = router.route("Let's check auth.py")
        assert decision.analysis.is_novel


class TestCompetingIntentThreshold:
    """Test competing intent threshold change (>=1 → >=3)."""

    def test_competing_3_escalates_slow(self):
        router = Router()
        # "debug design explain build review" has 4-5 competing intents
        decision = router.route("debug design explain build review")
        assert decision.path == PathDecision.SLOW

    def test_competing_1_stays_fast(self):
        # A prompt with ~1 competing intent should NOT escalate
        router = Router(session_topics=["tests", "code", "cache"])
        decision = router.route("Fix the failing test")
        # Should be fast (debugging, high confidence, 0-1 competing)
        if decision.analysis.competing_intents <= 2:
            assert decision.path == PathDecision.FAST

    def test_real_prompt_dual_intent_fast(self):
        # "implement and test" has 2 intents but shouldn't escalate
        router = Router(session_topics=["feature", "tests", "code"])
        decision = router.route("Add the feature")
        assert decision.analysis.competing_intents < 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
