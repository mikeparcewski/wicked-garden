"""Tests for scripts/crew/scope_delta.py — Issue #847.

Covers compute_scope_delta() and the CLI shim. The trigger doctrine
lives in skills/propose-process/refs/ambiguity.md trigger #7; this
suite enforces the numerical contract the doctrine references.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

# Ensure scripts/ is importable
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))

import scope_delta as sd  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_dict_passthrough(self):
        item = sd._normalize_item({"id": "i-1", "size": 5, "labels": ["bug"]})
        self.assertEqual(item, {"id": "i-1", "size": 5.0, "labels": ["bug"]})

    def test_string_becomes_id(self):
        item = sd._normalize_item("i-1")
        self.assertEqual(item, {"id": "i-1", "size": 1.0, "labels": []})

    def test_invalid_size_falls_back_to_one(self):
        item = sd._normalize_item({"id": "i-1", "size": "huge"})
        self.assertEqual(item["size"], 1.0)

    def test_unknown_shape_dropped(self):
        self.assertEqual(sd._normalize_item(42), {})
        self.assertEqual(sd._normalize_item(None), {})

    def test_labels_string_becomes_single_element_list(self):
        # Gemini PR #860 review: a bare string label must NOT be
        # decomposed by list("epic") into ['e','p','i','c'].
        item = sd._normalize_item({"id": "i-1", "size": 1, "labels": "epic"})
        self.assertEqual(item["labels"], ["epic"])

    def test_labels_non_iterable_defaults_to_empty(self):
        # Non-iterable labels (int, dict, etc.) must not crash with
        # TypeError — fall back to [].
        for bad in (42, 3.14, {"k": "v"}, True):
            item = sd._normalize_item({"id": "i-1", "size": 1, "labels": bad})
            self.assertEqual(item["labels"], [],
                             f"non-iterable labels {bad!r} should default to []")

    def test_labels_string_label_still_detects_epic(self):
        """End-to-end guard: a string-typed labels field with value 'epic'
        flows through normalization and still trips the epic-class trigger."""
        baseline = [{"id": "i-1", "size": 10}]
        proposed = baseline + [
            # NB: labels passed as bare string, not list — pre-fix this would
            # decompose into ['e','p','i','c'] and the epic trigger would
            # silently miss.
            {"id": "ep-1", "size": 1, "labels": "epic"},
        ]
        result = sd.compute_scope_delta(baseline, proposed)
        self.assertTrue(result["epic_or_project_added"])
        self.assertTrue(any(
            "epic-or-project-label" in t for t in result["triggers"]
        ))


class TestEpicLabelDetection(unittest.TestCase):
    def test_epic_match_case_insensitive(self):
        self.assertTrue(sd._has_epic_label(["EPIC"]))
        self.assertTrue(sd._has_epic_label(["epic"]))
        self.assertTrue(sd._has_epic_label(["project"]))

    def test_substring_does_not_match(self):
        # 'epic-feature' is not the bare 'epic' label
        self.assertFalse(sd._has_epic_label(["epic-feature"]))

    def test_no_labels_false(self):
        self.assertFalse(sd._has_epic_label([]))
        self.assertFalse(sd._has_epic_label(None))


class TestComputeScopeDeltaTriggers(unittest.TestCase):
    """The seventh ambiguity trigger fires whenever scope_delta returns a
    non-empty triggers list. These tests pin the threshold semantics."""

    def test_no_change_no_trigger(self):
        baseline = [{"id": "i-1", "size": 10}, {"id": "i-2", "size": 12}]
        result = sd.compute_scope_delta(baseline, baseline)
        self.assertEqual(result["triggers"], [])
        self.assertEqual(result["new_items"], [])

    def test_oversize_factor_trips_at_3x_median(self):
        # Median of 10/12/14 = 12.0; new item size 36 → 3.0x
        baseline = [
            {"id": "i-1", "size": 10},
            {"id": "i-2", "size": 12},
            {"id": "i-3", "size": 14},
        ]
        proposed = baseline + [{"id": "new-big", "size": 36}]
        result = sd.compute_scope_delta(baseline, proposed)
        self.assertAlmostEqual(result["oversize_factor"], 3.0)
        self.assertTrue(any("oversize-factor" in t for t in result["triggers"]))

    def test_oversize_factor_does_not_trip_below_3x(self):
        baseline = [{"id": "i-1", "size": 10}, {"id": "i-2", "size": 12}]
        proposed = baseline + [{"id": "new-mid", "size": 25}]  # ~2.27x
        result = sd.compute_scope_delta(baseline, proposed)
        self.assertLess(result["oversize_factor"], 3.0)
        self.assertFalse(any("oversize-factor" in t for t in result["triggers"]))

    def test_total_size_ratio_trips_at_2x(self):
        baseline = [{"id": "i-1", "size": 10}]
        # Two new items each size 5 brings total to 20 → 2.0x. Each new item
        # is 0.5x median (10) so oversize-factor will not also trip.
        proposed = baseline + [
            {"id": "n-1", "size": 5},
            {"id": "n-2", "size": 5},
        ]
        result = sd.compute_scope_delta(baseline, proposed)
        self.assertAlmostEqual(result["total_size_ratio"], 2.0)
        self.assertTrue(any("total-size-ratio" in t for t in result["triggers"]))

    def test_epic_label_trips_independently(self):
        baseline = [{"id": "i-1", "size": 10}]
        proposed = baseline + [{"id": "ep-1", "size": 1, "labels": ["epic"]}]
        result = sd.compute_scope_delta(baseline, proposed)
        # size is tiny, so oversize-factor + total-size-ratio do NOT trip
        self.assertTrue(result["epic_or_project_added"])
        self.assertTrue(any("epic-or-project-label" in t for t in result["triggers"]))

    def test_dogfood_scenario_jagan_ciq(self):
        """Issue #847 dogfood: baseline 24 normal-sized issues, plan
        absorbs a 1M-insertion sibling project. Verify the trigger fires
        even when the small items have label-only signal."""
        baseline = [{"id": f"i-{i}", "size": 100} for i in range(24)]
        # 1M-insertion absorbed item at scale 1_040_000
        proposed = baseline + [
            {"id": "jagan-ciq",
             "size": 1_040_000,
             "labels": ["epic", "project"]},
        ]
        result = sd.compute_scope_delta(baseline, proposed)
        # All three triggers should fire on this scenario
        trips = " ".join(result["triggers"])
        self.assertIn("oversize-factor", trips)
        self.assertIn("total-size-ratio", trips)
        self.assertIn("epic-or-project-label", trips)

    def test_baseline_empty_does_not_explode(self):
        """When baseline is empty (greenfield plan), oversize_factor and
        total_size_ratio are None — no division-by-zero — and the
        epic-label trigger still fires when applicable."""
        proposed = [{"id": "n-1", "size": 5, "labels": ["epic"]}]
        result = sd.compute_scope_delta([], proposed)
        self.assertIsNone(result["oversize_factor"])
        self.assertIsNone(result["total_size_ratio"])
        self.assertTrue(result["epic_or_project_added"])

    def test_overrideable_thresholds(self):
        baseline = [{"id": "i-1", "size": 10}]
        proposed = baseline + [{"id": "n-1", "size": 25}]  # 2.5x median
        # Default 3.0 → no trip
        self.assertFalse(any(
            "oversize-factor" in t
            for t in sd.compute_scope_delta(baseline, proposed)["triggers"]
        ))
        # Tighten to 2.0 → trips
        triggers = sd.compute_scope_delta(
            baseline, proposed, oversize_factor_trip=2.0
        )["triggers"]
        self.assertTrue(any("oversize-factor" in t for t in triggers))


class TestCLI(unittest.TestCase):
    """The CLI is the surface the propose-process facilitator agent
    invokes. Verify it reads/writes JSON cleanly and honors --exit-
    nonzero-on-trip."""

    def _run_cli(self, baseline, proposed, *extra_args, expect_returncode=0):
        scope_delta_path = _REPO_ROOT / "scripts" / "crew" / "scope_delta.py"
        # Pass via stdin: baseline first, then proposed via temp file
        import tempfile
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as base_fh:
            json.dump(baseline, base_fh)
            base_path = base_fh.name
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False
        ) as prop_fh:
            json.dump(proposed, prop_fh)
            prop_path = prop_fh.name
        cmd = [
            sys.executable, str(scope_delta_path),
            "--baseline", base_path,
            "--proposed", prop_path,
            *extra_args,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15
        )
        Path(base_path).unlink()
        Path(prop_path).unlink()
        self.assertEqual(
            result.returncode, expect_returncode,
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        return result

    def test_cli_outputs_json_with_triggers(self):
        baseline = [{"id": "i-1", "size": 10}, {"id": "i-2", "size": 12}]
        proposed = baseline + [{"id": "big", "size": 50}]
        result = self._run_cli(baseline, proposed)
        payload = json.loads(result.stdout)
        self.assertIn("triggers", payload)
        self.assertTrue(any(
            "oversize-factor" in t for t in payload["triggers"]
        ))

    def test_cli_exit_nonzero_on_trip(self):
        baseline = [{"id": "i-1", "size": 10}, {"id": "i-2", "size": 12}]
        proposed = baseline + [{"id": "big", "size": 50}]
        self._run_cli(
            baseline, proposed, "--exit-nonzero-on-trip",
            expect_returncode=1,
        )

    def test_cli_exit_zero_when_no_trip(self):
        baseline = [{"id": "i-1", "size": 10}, {"id": "i-2", "size": 12}]
        # Same plan — no triggers fire → exit 0 even with --exit-nonzero-on-trip
        self._run_cli(
            baseline, baseline, "--exit-nonzero-on-trip",
            expect_returncode=0,
        )


if __name__ == "__main__":
    unittest.main()
