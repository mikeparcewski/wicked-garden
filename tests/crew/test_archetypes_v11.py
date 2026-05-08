"""Tests for scripts/crew/archetypes_v11.py — v11 work-shape archetype
detection + steering directives."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = str(_REPO_ROOT / "scripts")
_CREW = str(_REPO_ROOT / "scripts" / "crew")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)
if _CREW not in sys.path:
    sys.path.append(_CREW)

import archetypes_v11 as av  # noqa: E402


class TestCatalogShape(unittest.TestCase):
    """Lock the v11 catalog contract — 9 archetypes, all carrying the
    required fields. Adding a 10th is fine; dropping or renaming one is
    a breaking change that should fail this test loudly."""

    REQUIRED_KEYS = {
        "description", "phases", "produces", "hitl", "cost_band",
        "maturity", "signals", "next_archetypes", "min_complexity",
    }
    EXPECTED_NAMES = {
        "triage", "explore", "specify", "decide", "ship", "review",
        "incident", "build", "migrate",
    }

    def test_all_nine_archetypes_present(self):
        catalog = av.load_catalog()
        names = set(catalog.get("archetypes", {}).keys())
        self.assertEqual(self.EXPECTED_NAMES, names)

    def test_required_fields_on_every_archetype(self):
        catalog = av.load_catalog()
        for name, archetype in catalog["archetypes"].items():
            missing = self.REQUIRED_KEYS - set(archetype.keys())
            self.assertFalse(missing, f"{name} missing keys: {missing}")
            self.assertIsInstance(archetype["phases"], list)
            self.assertGreater(len(archetype["phases"]), 0,
                               f"{name} must declare at least one phase")


class TestDetectionPositive(unittest.TestCase):
    """Each archetype's positive case — phrases or signals fire it."""

    def test_build_fires_on_implement_phrase(self):
        matches = av.detect_archetypes("implement caching for the dashboard")
        names = [n for n, _, _ in matches]
        self.assertIn("build", names)

    def test_migrate_fires_on_schema_change_phrase(self):
        matches = av.detect_archetypes(
            "we need a schema change to drop the legacy_id column",
            signals={"reversibility_low": True, "state_complexity_high": True},
        )
        top = matches[0]
        self.assertEqual(top[0], "migrate")
        self.assertGreaterEqual(top[1], av.HIGH_CONFIDENCE)

    def test_incident_fires_on_outage_phrase(self):
        matches = av.detect_archetypes(
            "checkout is down — 5xx error rate spiking",
            signals={"production_impact": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("incident", names)

    def test_specify_fires_on_acceptance_criteria_phrase(self):
        matches = av.detect_archetypes(
            "write acceptance criteria for the export feature",
        )
        names = [n for n, _, _ in matches]
        self.assertIn("specify", names)

    def test_explore_fires_on_open_ended_phrasing(self):
        matches = av.detect_archetypes(
            "what should we do about the rate-limit story?",
            signals={"novelty_high": True, "ambiguity_high": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("explore", names)

    def test_decide_fires_on_x_or_y(self):
        matches = av.detect_archetypes(
            "should we use redis or memcached for the session store?",
            signals={"multiple_viable_options": True,
                     "reversibility_medium_or_low": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("decide", names)

    def test_ship_fires_on_rollout_phrase(self):
        matches = av.detect_archetypes(
            "kick off the canary rollout for the new pricing logic",
            signals={"blast_radius_high": True, "post_build": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("ship", names)

    def test_review_fires_on_review_phrase(self):
        matches = av.detect_archetypes(
            "code review the new auth middleware",
            signals={"independent_assessment_needed": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("review", names)


class TestDetectionTriageFallback(unittest.TestCase):
    """When nothing scores >= threshold, triage is the sole match."""

    def test_unknown_intent_returns_only_triage(self):
        matches = av.detect_archetypes("hmm")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], "triage")

    def test_triage_always_appended_when_other_matches_present(self):
        matches = av.detect_archetypes("implement caching")
        names = [n for n, _, _ in matches]
        # build matched -> triage still appended at end
        self.assertEqual(names[-1], "triage")
        self.assertGreater(len(matches), 1)


class TestDetectionMultiArchetype(unittest.TestCase):
    """Archetypes are NOT mutually exclusive — a schema-changing feature
    is build + migrate."""

    def test_schema_change_feature_returns_both_build_and_migrate(self):
        matches = av.detect_archetypes(
            "implement schema change to add a tenant_id column with backfill",
            signals={"state_complexity_high": True, "reversibility_low": True,
                     "code_change": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("build", names)
        self.assertIn("migrate", names)


class TestSignalScoring(unittest.TestCase):
    """Confirm that signal-only inputs (no phrase match) can still trip
    an archetype above threshold."""

    def test_signal_only_path_works(self):
        # No phrase like "deploy" / "rollout" but blast_radius signal alone
        matches = av.detect_archetypes(
            "ok",
            signals={"blast_radius_high": True, "post_build": True},
        )
        names = [n for n, _, _ in matches]
        self.assertIn("ship", names)

    def test_concordance_bonus_when_phrase_and_signal_both_match(self):
        # Phrase + signal yields higher score than phrase alone
        score_phrase_only = av._detect_one_archetype(
            "build",
            av.load_catalog()["archetypes"]["build"],
            "implement caching",
            {},
        )[0]
        score_phrase_and_signal = av._detect_one_archetype(
            "build",
            av.load_catalog()["archetypes"]["build"],
            "implement caching",
            {"code_change": True},
        )[0]
        self.assertGreater(score_phrase_and_signal, score_phrase_only)


class TestSteeringDirectives(unittest.TestCase):
    """Steering directives carry archetype metadata + strength keyed
    off score."""

    def test_directive_includes_phase_shape_and_next_action(self):
        matches = av.detect_archetypes("implement caching",
                                       signals={"code_change": True})
        directives = av.steering_directives(matches)
        build = next(d for d in directives if d["archetype"] == "build")
        self.assertEqual(build["phases"],
                         ["plan", "implement", "test", "review"])
        self.assertIn("plan", build["next_action"])
        self.assertIn("implement", build["next_action"])

    def test_high_score_yields_recommend_strength(self):
        matches = [("build", 0.85, ["x"]), ("triage", 1.0, ["always_on"])]
        directives = av.steering_directives(matches)
        build = next(d for d in directives if d["archetype"] == "build")
        self.assertEqual(build["strength"], "recommend")

    def test_medium_score_yields_suggest_strength(self):
        matches = [("build", 0.55, ["x"]), ("triage", 1.0, ["always_on"])]
        directives = av.steering_directives(matches)
        build = next(d for d in directives if d["archetype"] == "build")
        self.assertEqual(build["strength"], "suggest")

    def test_triage_only_sole_match_emits_directive(self):
        matches = [("triage", 1.0, ["fallback"])]
        directives = av.steering_directives(matches)
        self.assertEqual(len(directives), 1)
        self.assertEqual(directives[0]["archetype"], "triage")

    def test_triage_skipped_when_other_archetypes_match(self):
        matches = [("build", 0.85, ["x"]), ("triage", 1.0, ["always_on"])]
        directives = av.steering_directives(matches)
        names = [d["archetype"] for d in directives]
        self.assertIn("build", names)
        self.assertNotIn("triage", names)


class TestCLI(unittest.TestCase):
    """End-to-end CLI smoke."""

    def _run(self, *args, expect_returncode=0):
        path = _REPO_ROOT / "scripts" / "crew" / "archetypes_v11.py"
        result = subprocess.run(
            [sys.executable, str(path), *args],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, expect_returncode,
                         f"stdout={result.stdout!r} stderr={result.stderr!r}")
        return result

    def test_detect_outputs_matches(self):
        result = self._run("detect", "--prompt", "implement caching")
        payload = json.loads(result.stdout)
        names = [m["archetype"] for m in payload["matches"]]
        self.assertIn("build", names)

    def test_detect_with_steering_emits_directives(self):
        result = self._run("detect", "--prompt", "implement caching",
                           "--steering")
        payload = json.loads(result.stdout)
        self.assertIn("directives", payload)
        self.assertGreater(len(payload["directives"]), 0)

    def test_catalog_lists_all_archetypes(self):
        result = self._run("catalog")
        payload = json.loads(result.stdout)
        names = set(payload.get("archetypes", {}).keys())
        self.assertEqual(names, TestCatalogShape.EXPECTED_NAMES)


if __name__ == "__main__":
    unittest.main()
