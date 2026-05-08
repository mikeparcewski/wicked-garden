"""tests/calibration/test_corpus_recall.py — Corpus-driven calibration.

Runs the v11 archetype detector against the prompt corpus and asserts:
  - Recall ≥ 0.85: the detector returns the primary archetype for at least
    85% of the corpus.
  - Precision ≥ 0.80: when the detector returns archetypes, at least 80%
    are the primary or in the may_also set.
  - Per-archetype recall ≥ 0.70: no single archetype is silently broken.

This catches calibration regressions when phrase lists change.
"""

from __future__ import annotations

import sys
import unittest
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew",
           _REPO_ROOT / "tests" / "calibration"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import archetypes_v11 as av  # noqa: E402
from corpus import CORPUS  # noqa: E402


class TestCorpusRecall(unittest.TestCase):
    """Detector recall + precision on the calibration corpus."""

    def setUp(self):
        self.results = []
        for case in CORPUS:
            matches = av.detect_archetypes(
                case["prompt"], signals=case.get("signals", {}),
            )
            detected = [m[0] for m in matches]  # archetype names
            self.results.append({
                "prompt": case["prompt"],
                "primary": case["primary"],
                "may_also": case.get("may_also", []),
                "detected": detected,
            })

    def test_overall_recall_at_least_85_percent(self):
        """Detector returns the primary archetype on ≥ 85% of corpus."""
        hits = sum(
            1 for r in self.results
            if r["primary"] in r["detected"]
        )
        recall = hits / len(self.results)
        misses = [
            r for r in self.results if r["primary"] not in r["detected"]
        ]
        self.assertGreaterEqual(
            recall, 0.85,
            f"Recall {recall:.2f} below threshold (0.85). Misses:\n"
            + "\n".join(
                f"  PROMPT: {m['prompt']!r}\n  EXPECTED: {m['primary']}, "
                f"DETECTED: {m['detected']}"
                for m in misses[:10]
            ),
        )

    def test_overall_precision_at_least_80_percent(self):
        """Of all detected archetypes (excluding triage), ≥ 80% are
        in either primary or may_also for the prompt."""
        total = 0
        correct = 0
        false_positives = []
        for r in self.results:
            valid = {r["primary"]} | set(r["may_also"])
            for d in r["detected"]:
                if d == "triage":
                    continue  # triage is always-on; doesn't count for precision
                total += 1
                if d in valid:
                    correct += 1
                else:
                    false_positives.append(
                        f"  PROMPT: {r['prompt']!r}\n  FALSE POSITIVE: {d} "
                        f"(expected primary={r['primary']}, may_also={r['may_also']})"
                    )
        if total == 0:
            self.skipTest("No non-triage detections in corpus.")
        precision = correct / total
        self.assertGreaterEqual(
            precision, 0.80,
            f"Precision {precision:.2f} below threshold (0.80). "
            f"First false positives:\n" + "\n".join(false_positives[:10])
        )

    def test_per_archetype_recall_minimum(self):
        """No single archetype has < 0.70 recall on the corpus.
        Catches the case where overall recall is high because some
        archetypes dominate the corpus."""
        by_primary = defaultdict(lambda: {"hits": 0, "total": 0})
        for r in self.results:
            by_primary[r["primary"]]["total"] += 1
            if r["primary"] in r["detected"]:
                by_primary[r["primary"]]["hits"] += 1

        weak = {}
        for archetype, stats in by_primary.items():
            if stats["total"] < 3:
                continue  # not enough samples to judge
            recall = stats["hits"] / stats["total"]
            if recall < 0.70:
                weak[archetype] = {
                    "recall": recall,
                    "hits": stats["hits"],
                    "total": stats["total"],
                }
        self.assertEqual(
            weak, {},
            f"Per-archetype recall below 0.70:\n" + "\n".join(
                f"  {arch}: {s['hits']}/{s['total']} = {s['recall']:.2f}"
                for arch, s in weak.items()
            ),
        )


class TestCorpusReport(unittest.TestCase):
    """Diagnostic — prints calibration report when run with -s."""

    def test_print_full_report(self):
        results = []
        for case in CORPUS:
            matches = av.detect_archetypes(
                case["prompt"], signals=case.get("signals", {}),
            )
            detected = [(m[0], m[1]) for m in matches]
            primary_hit = case["primary"] in [m[0] for m in matches]
            results.append({
                "prompt": case["prompt"],
                "expected": case["primary"],
                "detected": detected,
                "hit": primary_hit,
            })

        # The test passes regardless — this is for diagnostics.
        # Run with: pytest -s tests/calibration/test_corpus_recall.py::TestCorpusReport
        misses = [r for r in results if not r["hit"]]
        if misses:
            print("\n\n=== Calibration misses ===")
            for r in misses:
                print(f"  EXPECTED: {r['expected']}")
                print(f"  PROMPT:   {r['prompt']!r}")
                print(f"  DETECTED: {r['detected']}")
                print()


if __name__ == "__main__":
    unittest.main()
