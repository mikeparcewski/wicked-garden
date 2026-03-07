#!/usr/bin/env python3
"""
Integration tests for validate_test_evidence() in scripts/crew/evidence.py

Covers all TC 3.x scenarios from the test strategy.
Run: python3 -m pytest tests/test_evidence_validation.py -v
  or: python3 tests/test_evidence_validation.py
"""

import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.crew.evidence import validate_evidence, validate_test_evidence


class TestUITestEvidence(unittest.TestCase):
    """TC 3.1-3.2 — UI test evidence validation"""

    def test_3_1_ui_with_screenshot_valid(self):
        """TC 3.1 — UI task with screenshot: valid"""
        artifacts = [
            {
                "type": "image",
                "path": "phases/test/evidence/screenshot.png",
                "name": "screenshot-login",
            }
        ]
        result = validate_test_evidence(artifacts, "ui")
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])
        self.assertIn("screenshot", result["present"])

    def test_3_2_ui_missing_screenshot_invalid(self):
        """TC 3.2 — UI task with no artifacts: invalid"""
        result = validate_test_evidence([], "ui")
        self.assertFalse(result["valid"])
        self.assertIn("screenshot", result["missing"])
        self.assertEqual(result["present"], [])

    def test_ui_with_screenshot_type_literal(self):
        """Screenshot type using 'screenshot' string (alternate accepted type)"""
        artifacts = [{"type": "screenshot", "name": "my-screenshot"}]
        result = validate_test_evidence(artifacts, "ui")
        self.assertTrue(result["valid"])
        self.assertIn("screenshot", result["present"])


class TestAPITestEvidence(unittest.TestCase):
    """TC 3.3-3.4 — API test evidence validation"""

    def test_3_3_api_with_both_payloads_valid(self):
        """TC 3.3 — API task with request + response: valid"""
        artifacts = [
            {
                "type": "api_request",
                "content": '{"method":"POST","url":"/api/login"}',
                "name": "api-request",
            },
            {
                "type": "api_response",
                "content": '{"status":200,"body":{}}',
                "name": "api-response",
            },
        ]
        result = validate_test_evidence(artifacts, "api")
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])
        self.assertIn("request_payload", result["present"])
        self.assertIn("response_payload", result["present"])

    def test_3_4_api_missing_response_invalid(self):
        """TC 3.4 — API task with only request: invalid (missing response)"""
        artifacts = [
            {
                "type": "api_request",
                "content": '{"method":"POST","url":"/api/login"}',
                "name": "api-request",
            }
        ]
        result = validate_test_evidence(artifacts, "api")
        self.assertFalse(result["valid"])
        self.assertIn("response_payload", result["missing"])
        self.assertIn("request_payload", result["present"])

    def test_api_missing_request_invalid(self):
        """API task with only response: invalid (missing request)"""
        artifacts = [
            {
                "type": "api_response",
                "content": '{"status":200}',
                "name": "api-response",
            }
        ]
        result = validate_test_evidence(artifacts, "api")
        self.assertFalse(result["valid"])
        self.assertIn("request_payload", result["missing"])
        self.assertIn("response_payload", result["present"])

    def test_api_missing_both_payloads_invalid(self):
        """API task with no artifacts: invalid (missing both)"""
        result = validate_test_evidence([], "api")
        self.assertFalse(result["valid"])
        self.assertIn("request_payload", result["missing"])
        self.assertIn("response_payload", result["missing"])

    def test_api_with_request_type_alias(self):
        """'request' as artifact type satisfies request_payload requirement"""
        artifacts = [
            {"type": "request", "content": "{}", "name": "req"},
            {"type": "response", "content": "{}", "name": "resp"},
        ]
        result = validate_test_evidence(artifacts, "api")
        self.assertTrue(result["valid"])


class TestIntegrationTestEvidence(unittest.TestCase):
    """TC 3.5-3.6 — Integration (both) test evidence validation"""

    def test_3_5_integration_with_all_evidence_valid(self):
        """TC 3.5 — Integration task with screenshot + request + response: valid"""
        artifacts = [
            {
                "type": "image",
                "path": "phases/test/evidence/screenshot.png",
                "name": "screenshot",
            },
            {
                "type": "api_request",
                "content": '{"method":"GET","url":"/api/items"}',
                "name": "request",
            },
            {
                "type": "api_response",
                "content": '{"status":200}',
                "name": "response",
            },
        ]
        result = validate_test_evidence(artifacts, "both")
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])
        self.assertIn("screenshot", result["present"])
        self.assertIn("request_payload", result["present"])
        self.assertIn("response_payload", result["present"])

    def test_3_6_integration_ui_only_invalid(self):
        """TC 3.6 — Integration task with only screenshot: invalid (missing API)"""
        artifacts = [
            {
                "type": "image",
                "path": "phases/test/evidence/screenshot.png",
                "name": "screenshot",
            }
        ]
        result = validate_test_evidence(artifacts, "both")
        self.assertFalse(result["valid"])
        self.assertIn("request_payload", result["missing"])
        self.assertIn("response_payload", result["missing"])
        self.assertIn("screenshot", result["present"])

    def test_integration_api_only_invalid(self):
        """Integration task with only API artifacts: invalid (missing screenshot)"""
        artifacts = [
            {"type": "api_request", "content": "{}", "name": "req"},
            {"type": "api_response", "content": "{}", "name": "resp"},
        ]
        result = validate_test_evidence(artifacts, "both")
        self.assertFalse(result["valid"])
        self.assertIn("screenshot", result["missing"])
        self.assertIn("request_payload", result["present"])
        self.assertIn("response_payload", result["present"])

    def test_integration_no_artifacts_invalid(self):
        """Integration task with no artifacts: all three missing"""
        result = validate_test_evidence([], "both")
        self.assertFalse(result["valid"])
        self.assertIn("screenshot", result["missing"])
        self.assertIn("request_payload", result["missing"])
        self.assertIn("response_payload", result["missing"])


class TestArtifactTypeMatching(unittest.TestCase):
    """TC 3.7-3.8 — Artifact type matching edge cases"""

    def test_3_7_wrong_type_does_not_satisfy_screenshot(self):
        """TC 3.7 — 'document' type does not satisfy screenshot requirement"""
        artifacts = [
            {"type": "document", "path": "notes.txt", "name": "notes"}
        ]
        result = validate_test_evidence(artifacts, "ui")
        self.assertFalse(result["valid"])
        self.assertIn("screenshot", result["missing"])
        self.assertEqual(result["present"], [])

    def test_3_8_optional_evidence_does_not_block_validity(self):
        """TC 3.8 — visual_diff is optional; absence does not block UI validity"""
        # Only screenshot present, no visual_diff
        artifacts = [{"type": "image", "path": "screenshot.png", "name": "screenshot"}]
        result = validate_test_evidence(artifacts, "ui")
        self.assertTrue(result["valid"])
        # visual_diff is NOT in missing (it's optional)
        self.assertNotIn("visual_diff", result["missing"])

    def test_wrong_type_for_api_request(self):
        """'document' type does not satisfy request_payload"""
        artifacts = [
            {"type": "document", "content": "{}", "name": "doc"},
            {"type": "api_response", "content": "{}", "name": "resp"},
        ]
        result = validate_test_evidence(artifacts, "api")
        self.assertFalse(result["valid"])
        self.assertIn("request_payload", result["missing"])
        self.assertIn("response_payload", result["present"])

    def test_type_matching_is_case_insensitive(self):
        """Artifact types should be compared case-insensitively"""
        artifacts = [{"type": "IMAGE", "path": "screenshot.png", "name": "screenshot"}]
        result = validate_test_evidence(artifacts, "ui")
        # The implementation lowercases artifact types before matching
        self.assertTrue(result["valid"])


class TestExistingAPIUnchanged(unittest.TestCase):
    """TC 3.9 — Validate existing evidence.py API is unchanged [P2]"""

    def test_3_9_validate_evidence_still_works(self):
        """The original validate_evidence() function is unchanged"""
        task_description = "- Test: foo — PASS\n- File: src/foo.py — modified"
        result = validate_evidence(task_description, complexity_score=2)
        self.assertIsInstance(result, dict)
        self.assertIn("valid", result)
        self.assertIn("missing", result)
        self.assertIn("warnings", result)
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])

    def test_validate_evidence_medium_complexity(self):
        """Medium complexity requires verification too"""
        task_description = (
            "- Test: foo — PASS\n"
            "- File: src/foo.py — modified\n"
            "- Verification: curl returns 200"
        )
        result = validate_evidence(task_description, complexity_score=3)
        self.assertTrue(result["valid"])

    def test_validate_evidence_missing_field(self):
        """Missing test results → invalid"""
        result = validate_evidence("Some description without test results", complexity_score=2)
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["missing"]) > 0)

    def test_validate_test_evidence_does_not_affect_validate_evidence(self):
        """Calling validate_test_evidence does not affect validate_evidence behavior"""
        # Call the new function
        validate_test_evidence([{"type": "image", "path": "x.png", "name": "ss"}], "ui")
        # Original function still works correctly
        result = validate_evidence("- Test: bar — PASS\n- File: bar.py — created", 1)
        self.assertTrue(result["valid"])


class TestUnknownTestType(unittest.TestCase):
    """Edge case: unknown test_type argument"""

    def test_unknown_test_type_returns_invalid(self):
        result = validate_test_evidence([], "integration_test")
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["missing"]) > 0)
        self.assertIn("Unknown test_type", result["missing"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
