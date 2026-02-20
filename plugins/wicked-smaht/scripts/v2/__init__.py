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
- memory_promoter.py: Session-to-memory promotion pipeline
- briefing.py: Output formatting
"""

__version__ = "2.1.0"
