"""
wicked-smaht v2: Tiered Hybrid Context Management

Architecture:
- Fast Path: Pattern-based, <1s, no LLM
- Slow Path: Subagent-powered, 2-4s, full reasoning

Components:
- router.py: Decides fast vs slow path
- fast_path.py: Pattern-based assembly
- slow_path.py: Subagent invocation
- history_condenser.py: Progressive compression
- fact_extractor.py: Structured fact extraction (facts.jsonl)
- lane_tracker.py: Multi-lane parallel work tracking
- briefing.py: Output formatting

Cross-session memory promotion is handled by the wicked-brain auto-memorize
subscriber: stop.py emits `wicked.fact.extracted` events on wicked-bus, and
brain's own subscriber applies the promotion policy and writes memories. No
wicked-garden-side promoter pipeline lives here anymore.
"""

__version__ = "2.1.0"
