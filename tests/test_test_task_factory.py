#!/usr/bin/env python3
"""
Unit tests for scripts/crew/test_task_factory.py

Covers all TC 2.x scenarios from the test strategy.
Run: python3 -m pytest tests/test_test_task_factory.py -v
  or: python3 tests/test_test_task_factory.py
"""

import json
import subprocess
import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.crew.test_task_factory import create_test_tasks

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestUIChangeType(unittest.TestCase):
    """TC 2.1 — UI Change Type Produces Single Visual Test Task [P1]"""

    def setUp(self):
        self.result = create_test_tasks(
            change_type="ui",
            impl_subject="Implement login form",
            project="my-project",
        )

    def test_exactly_one_test_task(self):
        self.assertEqual(len(self.result["test_tasks"]), 1)

    def test_subject_naming_convention(self):
        subject = self.result["test_tasks"][0]["subject"]
        self.assertEqual(subject, "Test: my-project - Implement login form (visual)")

    def test_metadata_test_type(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertEqual(metadata["test_type"], "ui")

    def test_evidence_required_contains_screenshot(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertIn("screenshot", metadata["evidence_required"])

    def test_assigned_to_acceptance_test_executor(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertEqual(metadata["assigned_to"], "acceptance-test-executor")

    def test_priority_is_p1(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertEqual(metadata["priority"], "P1")

    def test_initiative_is_project_name(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertEqual(metadata["initiative"], "my-project")


class TestAPIChangeType(unittest.TestCase):
    """TC 2.2 — API Change Type Produces Single Endpoint Test Task [P1]"""

    def setUp(self):
        self.result = create_test_tasks(
            change_type="api",
            impl_subject="Add auth endpoint",
            project="auth-service",
        )

    def test_exactly_one_test_task(self):
        self.assertEqual(len(self.result["test_tasks"]), 1)

    def test_subject_naming_convention(self):
        subject = self.result["test_tasks"][0]["subject"]
        self.assertEqual(subject, "Test: auth-service - Add auth endpoint (endpoint)")

    def test_metadata_test_type(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertEqual(metadata["test_type"], "api")

    def test_evidence_required_contains_request_payload(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertIn("request_payload", metadata["evidence_required"])

    def test_evidence_required_contains_response_payload(self):
        metadata = self.result["test_tasks"][0]["metadata"]
        self.assertIn("response_payload", metadata["evidence_required"])


class TestBothChangeType(unittest.TestCase):
    """TC 2.3 — Both Change Type Produces Two Test Tasks [P1]"""

    def setUp(self):
        self.result = create_test_tasks(
            change_type="both",
            impl_subject="Integrate payment flow",
            project="checkout",
        )

    def test_exactly_two_test_tasks(self):
        self.assertEqual(len(self.result["test_tasks"]), 2)

    def test_one_task_is_visual(self):
        subjects = [t["subject"] for t in self.result["test_tasks"]]
        self.assertTrue(any("(visual)" in s for s in subjects))

    def test_one_task_is_endpoint(self):
        subjects = [t["subject"] for t in self.result["test_tasks"]]
        self.assertTrue(any("(endpoint)" in s for s in subjects))

    def test_ui_task_has_correct_test_type(self):
        ui_tasks = [t for t in self.result["test_tasks"] if t["metadata"]["test_type"] == "ui"]
        self.assertEqual(len(ui_tasks), 1)

    def test_api_task_has_correct_test_type(self):
        api_tasks = [t for t in self.result["test_tasks"] if t["metadata"]["test_type"] == "api"]
        self.assertEqual(len(api_tasks), 1)

    def test_both_tasks_have_p1_priority(self):
        for task in self.result["test_tasks"]:
            self.assertEqual(task["metadata"]["priority"], "P1")

    def test_both_tasks_assigned_to_executor(self):
        for task in self.result["test_tasks"]:
            self.assertEqual(task["metadata"]["assigned_to"], "acceptance-test-executor")


class TestUnknownChangeType(unittest.TestCase):
    """TC 2.4 — Unknown Change Type Produces Empty Test Task List [P1]"""

    def setUp(self):
        self.result = create_test_tasks(
            change_type="unknown",
            impl_subject="Refactor utilities",
            project="core",
        )

    def test_empty_test_tasks_list(self):
        self.assertEqual(self.result["test_tasks"], [])

    def test_suppressed_flag(self):
        self.assertTrue(self.result.get("suppressed", False))

    def test_warning_message_present(self):
        self.assertIn("warning", self.result)
        self.assertIsInstance(self.result["warning"], str)
        self.assertTrue(len(self.result["warning"]) > 0)


class TestPhasePrefixStripping(unittest.TestCase):
    """TC 2.5 — Task Naming Convention: Phase Prefix Stripped [P2]"""

    def test_build_prefix_with_project_name_stripped(self):
        """'Build: my-project - Implement login form' → 'Implement login form'"""
        result = create_test_tasks(
            change_type="ui",
            impl_subject="Build: my-project - Implement login form",
            project="my-project",
        )
        subject = result["test_tasks"][0]["subject"]
        # Should not duplicate the "Build: my-project -" prefix
        self.assertNotIn("Build:", subject)
        self.assertNotIn("build:", subject.lower() + "x")  # check case-insensitive
        # Should be the clean version
        self.assertEqual(subject, "Test: my-project - Implement login form (visual)")

    def test_impl_prefix_stripped(self):
        """Alternate prefix 'Implement: task' → stripped"""
        result = create_test_tasks(
            change_type="ui",
            impl_subject="Implement: Add header component",
            project="ui-lib",
        )
        subject = result["test_tasks"][0]["subject"]
        self.assertNotIn("Implement:", subject)

    def test_no_prefix_is_no_op(self):
        """Subject without prefix is used as-is"""
        result = create_test_tasks(
            change_type="ui",
            impl_subject="Add header component",
            project="ui-lib",
        )
        subject = result["test_tasks"][0]["subject"]
        self.assertEqual(subject, "Test: ui-lib - Add header component (visual)")


class TestEvidenceOptionalFields(unittest.TestCase):
    """TC 2.6 — Evidence Optional Fields Present in Metadata [P2]"""

    def test_ui_has_visual_diff_optional(self):
        result = create_test_tasks(
            change_type="ui",
            impl_subject="Update card layout",
            project="ui-lib",
        )
        metadata = result["test_tasks"][0]["metadata"]
        self.assertIn("evidence_optional", metadata)
        self.assertIn("visual_diff", metadata["evidence_optional"])

    def test_api_has_response_timing_optional(self):
        result = create_test_tasks(
            change_type="api",
            impl_subject="Add search endpoint",
            project="search",
        )
        metadata = result["test_tasks"][0]["metadata"]
        self.assertIn("evidence_optional", metadata)
        self.assertIn("response_timing", metadata["evidence_optional"])


class TestAPITaskDescription(unittest.TestCase):
    """TC 2.7 — API Task Description Contains Evidence Instructions [P2]"""

    def test_api_description_mentions_http_request(self):
        result = create_test_tasks(
            change_type="api",
            impl_subject="Add search endpoint",
            project="search",
        )
        description = result["test_tasks"][0]["description"]
        self.assertIn("request", description.lower())

    def test_api_description_mentions_http_response(self):
        result = create_test_tasks(
            change_type="api",
            impl_subject="Add search endpoint",
            project="search",
        )
        description = result["test_tasks"][0]["description"]
        self.assertIn("response", description.lower())

    def test_api_description_mentions_http_body_or_headers(self):
        result = create_test_tasks(
            change_type="api",
            impl_subject="Add search endpoint",
            project="search",
        )
        description = result["test_tasks"][0]["description"]
        # Should contain guidance about HTTP request body/headers
        self.assertTrue(
            "body" in description.lower() or "header" in description.lower(),
            f"Description should mention body or headers: {description[:100]}"
        )

    def test_description_mentions_evidence_validation(self):
        result = create_test_tasks(
            change_type="api",
            impl_subject="Add search endpoint",
            project="search",
        )
        description = result["test_tasks"][0]["description"]
        # Should reference evidence validation
        self.assertIn("validate_test_evidence", description)


class TestCLIOutputIsValidJSON(unittest.TestCase):
    """TC 2.8 — Output Is Valid JSON [P1]"""

    def test_cli_ui_output_is_valid_json(self):
        """Run the CLI and parse stdout as JSON"""
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "scripts", "crew", "test_task_factory.py"),
                "--change-type", "ui",
                "--impl-subject", "X",
                "--project", "Y",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
        parsed = json.loads(result.stdout)  # Raises JSONDecodeError if invalid
        self.assertIn("test_tasks", parsed)
        self.assertIsInstance(parsed["test_tasks"], list)

    def test_cli_api_output_is_valid_json(self):
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "scripts", "crew", "test_task_factory.py"),
                "--change-type", "api",
                "--impl-subject", "Add endpoint",
                "--project", "myapp",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertIn("test_tasks", parsed)
        self.assertEqual(len(parsed["test_tasks"]), 1)

    def test_cli_unknown_output_is_valid_json(self):
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "scripts", "crew", "test_task_factory.py"),
                "--change-type", "unknown",
                "--impl-subject", "Refactor",
                "--project", "core",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["test_tasks"], [])
        self.assertIn("warning", parsed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
