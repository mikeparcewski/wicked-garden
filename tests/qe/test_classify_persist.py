"""Tests for scripts/classify/persist.py — v11 LLM-classifier persist path."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "classify"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import persist as p  # noqa: E402


class _FakeState:
    """Minimal stand-in for SessionState. Records updates."""
    def __init__(self):
        self.intent = None
        self.intent_explicit = False
        self.archetypes_v11 = None
        self.signals_v11 = None
        self.classified_at = None
        self.updates = []

    def update(self, **kw):
        self.updates.append(kw)
        for k, v in kw.items():
            setattr(self, k, v)

    def save(self):
        pass


class TestNormalize(unittest.TestCase):
    def test_drops_unknown_intent(self):
        out = p._normalize({"intent": "xxx"})
        self.assertNotIn("intent", out)

    def test_keeps_valid_intent(self):
        for intent in p.VALID_INTENTS:
            out = p._normalize({"intent": intent})
            self.assertEqual(out["intent"], intent)

    def test_drops_unknown_archetype(self):
        out = p._normalize({
            "archetypes": [{"name": "not-a-thing", "score": 0.9}],
        })
        self.assertEqual(out["archetypes"], [])

    def test_clamps_score_range(self):
        out = p._normalize({
            "archetypes": [{"name": "build", "score": 1.5}],
        })
        self.assertEqual(out["archetypes"][0]["score"], 1.0)
        out2 = p._normalize({
            "archetypes": [{"name": "build", "score": -0.3}],
        })
        self.assertEqual(out2["archetypes"][0]["score"], 0.0)

    def test_caps_top_archetypes(self):
        out = p._normalize({
            "archetypes": [
                {"name": n, "score": 0.5} for n in
                ("build", "migrate", "ship", "review", "incident", "decide")
            ],
        })
        self.assertEqual(len(out["archetypes"]), 5)

    def test_drops_unknown_signals(self):
        out = p._normalize({
            "signals": {"blast_radius_high": True, "fake_signal": True},
        })
        self.assertEqual(out["signals"],
                         {"blast_radius_high": True})

    def test_drops_non_bool_signals(self):
        out = p._normalize({
            "signals": {"blast_radius_high": "yes"},
        })
        self.assertEqual(out["signals"], {})

    def test_caps_evidence_per_archetype(self):
        out = p._normalize({
            "archetypes": [{
                "name": "build", "score": 0.5,
                "evidence": [f"reason-{i}" for i in range(20)],
            }],
        })
        self.assertEqual(len(out["archetypes"][0]["evidence"]), 5)


class TestPersist(unittest.TestCase):
    def test_persist_writes_to_session_state(self):
        fake = _FakeState()
        # The persist() function does a local `from _session import
        # SessionState`. We patch that import path so the real load is
        # intercepted.
        import _session  # type: ignore
        with patch.object(_session.SessionState, "load",
                          classmethod(lambda cls: fake)):
            normalized = p.persist({
                "intent": "feature",
                "archetypes": [{"name": "build", "score": 0.85}],
                "signals": {"code_change": True},
            })
        self.assertEqual(fake.intent, "feature")
        self.assertFalse(fake.intent_explicit)
        self.assertEqual(fake.archetypes_v11,
                         [{"name": "build", "score": 0.85, "evidence": []}])
        self.assertEqual(fake.signals_v11, {"code_change": True})
        self.assertIsNotNone(fake.classified_at)
        self.assertEqual(normalized["intent"], "feature")

    def test_persist_skips_intent_when_invalid(self):
        fake = _FakeState()
        import _session  # type: ignore
        with patch.object(_session.SessionState, "load",
                          classmethod(lambda cls: fake)):
            p.persist({"archetypes": [{"name": "build", "score": 0.5}]})
        self.assertIsNone(fake.intent)


if __name__ == "__main__":
    unittest.main()
