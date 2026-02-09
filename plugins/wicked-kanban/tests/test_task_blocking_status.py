"""
Test suite for task dependency blocking status feature.

Tests the get_task_blocking_status method to ensure:
- Tasks are blocked by incomplete dependencies
- Completed dependencies don't block tasks
- Tasks with no dependencies are not blocked
- Missing dependency tasks are handled gracefully
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from kanban import KanbanStore


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for kanban data and clean up after test."""
    # Arrange: Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="wicked_kanban_test_")
    original_env = os.environ.get('WICKED_KANBAN_DATA_DIR')

    # Set environment variable to use temp directory
    os.environ['WICKED_KANBAN_DATA_DIR'] = temp_dir

    yield temp_dir

    # Teardown: Clean up temp directory and restore environment
    if original_env:
        os.environ['WICKED_KANBAN_DATA_DIR'] = original_env
    else:
        os.environ.pop('WICKED_KANBAN_DATA_DIR', None)

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def store(temp_data_dir):
    """Create a fresh KanbanStore instance for each test."""
    return KanbanStore()


@pytest.fixture
def project(store):
    """Create a test project with default swimlanes."""
    return store.create_project(
        name="Test Project",
        description="Project for dependency testing"
    )


class TestTaskBlockingStatus:
    """Test suite for task dependency blocking status detection."""

    def test_dep_001_task_blocked_by_incomplete_dependency(self, store, project):
        """
        DEP-001: Task blocking status detects incomplete dependencies.

        Given: Task A exists in "todo" swimlane (incomplete)
        When: Task B is created with depends_on=[task_A_id]
        Then: Task B's blocking status shows it is blocked by Task A
        """
        # Arrange: Create task A in "todo" swimlane
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Prerequisite",
            swimlane="todo",
            description="This task must be completed first"
        )

        # Arrange: Create task B that depends on task A
        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Dependent",
            swimlane="todo",
            depends_on=[task_a["id"]],
            description="This task depends on Task A"
        )

        # Act: Check blocking status of task B
        blocking_status = store.get_task_blocking_status(project["id"], task_b["id"])

        # Assert: Task B is blocked by Task A
        assert blocking_status["is_blocked"] is True, \
            "Task B should be blocked when dependency is incomplete"
        assert len(blocking_status["blocking_tasks"]) == 1, \
            "Should have exactly one blocking task"

        blocking_task = blocking_status["blocking_tasks"][0]
        assert blocking_task["task_id"] == task_a["id"], \
            "Blocking task ID should match Task A"
        assert blocking_task["task_name"] == task_a["name"], \
            "Blocking task name should match Task A"
        assert blocking_task["swimlane"] == "todo", \
            "Blocking task should be in 'todo' swimlane"
        assert blocking_task["priority"] == task_a["priority"], \
            "Blocking task priority should be preserved"

    def test_dep_002_task_not_blocked_by_completed_dependency(self, store, project):
        """
        DEP-002: Task blocking status ignores completed dependencies.

        Given: Task A exists in "done" swimlane (complete)
        When: Task B is created with depends_on=[task_A_id]
        Then: Task B's blocking status shows it is NOT blocked
        """
        # Arrange: Create task A in "todo" first
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Completed Prerequisite",
            swimlane="todo",
            description="This task will be completed"
        )

        # Arrange: Move task A to "done" swimlane (marking it complete)
        store.update_task(
            project_id=project["id"],
            task_id=task_a["id"],
            swimlane="done"
        )

        # Arrange: Create task B that depends on completed task A
        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Should Not Be Blocked",
            swimlane="todo",
            depends_on=[task_a["id"]],
            description="This task depends on completed Task A"
        )

        # Act: Check blocking status of task B
        blocking_status = store.get_task_blocking_status(project["id"], task_b["id"])

        # Assert: Task B is NOT blocked since Task A is complete
        assert blocking_status["is_blocked"] is False, \
            "Task B should NOT be blocked when dependency is complete"
        assert len(blocking_status["blocking_tasks"]) == 0, \
            "Should have no blocking tasks when dependencies are complete"

    def test_dep_003_task_with_no_dependencies_not_blocked(self, store, project):
        """
        DEP-003: Task blocking status returns empty for no dependencies.

        Given: No dependency tasks exist
        When: Task is created with no dependencies
        Then: Blocking status shows is_blocked: false, blocking_tasks: []
        """
        # Arrange: Create task with no dependencies
        task = store.create_task(
            project_id=project["id"],
            name="Independent Task",
            swimlane="todo",
            description="This task has no dependencies"
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task["id"])

        # Assert: Task is not blocked
        assert blocking_status["is_blocked"] is False, \
            "Task with no dependencies should not be blocked"
        assert blocking_status["blocking_tasks"] == [], \
            "Blocking tasks list should be empty"
        assert isinstance(blocking_status["blocking_tasks"], list), \
            "blocking_tasks should be a list, not None"

    def test_dep_004_task_blocked_by_multiple_incomplete_dependencies(self, store, project):
        """
        Additional test: Task blocked by multiple incomplete dependencies.

        Given: Tasks A and B exist in "todo" and "in_progress" swimlanes
        When: Task C depends on both A and B
        Then: Task C is blocked and shows both blocking tasks
        """
        # Arrange: Create task A in "todo"
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - First Dependency",
            swimlane="todo",
            priority="P0"
        )

        # Arrange: Create task B in "in_progress"
        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Second Dependency",
            swimlane="in_progress",
            priority="P1"
        )

        # Arrange: Create task C that depends on both A and B
        task_c = store.create_task(
            project_id=project["id"],
            name="Task C - Multiple Dependencies",
            swimlane="todo",
            depends_on=[task_a["id"], task_b["id"]]
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task_c["id"])

        # Assert: Task C is blocked by both A and B
        assert blocking_status["is_blocked"] is True, \
            "Task should be blocked when any dependency is incomplete"
        assert len(blocking_status["blocking_tasks"]) == 2, \
            "Should show all incomplete dependencies"

        blocking_ids = {bt["task_id"] for bt in blocking_status["blocking_tasks"]}
        assert blocking_ids == {task_a["id"], task_b["id"]}, \
            "Should include both incomplete dependency tasks"

    def test_dep_005_task_blocking_handles_missing_dependency(self, store, project):
        """
        DEP-005: Task blocking handles missing dependency tasks.

        Given: A task has depends_on with a nonexistent task ID
        When: Blocking status is checked
        Then: Missing dependencies are silently ignored (current behavior - bug to fix)
        """
        # Arrange: Create task with dependency on nonexistent task
        task = store.create_task(
            project_id=project["id"],
            name="Task with Missing Dependency",
            swimlane="todo",
            depends_on=["nonexistent-task-id-12345"]
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task["id"])

        # Assert: Currently silently ignores missing dependencies
        # NOTE: This is a known bug - missing dependencies should potentially be reported
        assert blocking_status["is_blocked"] is False, \
            "Current behavior: missing dependencies are ignored"
        assert blocking_status["blocking_tasks"] == [], \
            "Current behavior: no blocking tasks when dependency doesn't exist"

    def test_dep_006_task_partially_blocked_by_mixed_dependencies(self, store, project):
        """
        Additional test: Task with mix of complete and incomplete dependencies.

        Given: Task A is complete, Task B is incomplete
        When: Task C depends on both A and B
        Then: Task C is blocked only by B
        """
        # Arrange: Create and complete task A
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Complete",
            swimlane="done"
        )

        # Arrange: Create incomplete task B
        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Incomplete",
            swimlane="in_progress",
            priority="P0"
        )

        # Arrange: Create task C depending on both
        task_c = store.create_task(
            project_id=project["id"],
            name="Task C - Mixed Dependencies",
            swimlane="todo",
            depends_on=[task_a["id"], task_b["id"]]
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task_c["id"])

        # Assert: Only blocked by incomplete task B
        assert blocking_status["is_blocked"] is True
        assert len(blocking_status["blocking_tasks"]) == 1
        assert blocking_status["blocking_tasks"][0]["task_id"] == task_b["id"]

    def test_dep_007_get_task_with_status_includes_blocking_details(self, store, project):
        """
        Additional test: get_task_with_status method includes blocking details.

        Given: Task B depends on incomplete Task A
        When: get_task_with_status is called for Task B
        Then: Task object includes is_blocked and blocking_details
        """
        # Arrange: Create dependency chain
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Blocker",
            swimlane="in_progress"
        )

        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Blocked",
            swimlane="todo",
            depends_on=[task_a["id"]]
        )

        # Act: Get task with status
        task_with_status = store.get_task_with_status(project["id"], task_b["id"])

        # Assert: Task includes blocking information
        assert task_with_status is not None
        assert "is_blocked" in task_with_status
        assert "blocking_details" in task_with_status
        assert task_with_status["is_blocked"] is True
        assert len(task_with_status["blocking_details"]) == 1
        assert task_with_status["blocking_details"][0]["task_id"] == task_a["id"]

    def test_dep_008_empty_depends_on_list_not_blocked(self, store, project):
        """
        Edge case: Task with explicit empty depends_on list.

        Given: Task created with depends_on=[]
        When: Blocking status is checked
        Then: Task is not blocked
        """
        # Arrange: Create task with explicit empty dependencies
        task = store.create_task(
            project_id=project["id"],
            name="Task with Empty Dependencies",
            swimlane="todo",
            depends_on=[]
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task["id"])

        # Assert: Not blocked
        assert blocking_status["is_blocked"] is False
        assert blocking_status["blocking_tasks"] == []

    def test_dep_009_nonexistent_task_returns_not_blocked(self, store, project):
        """
        Edge case: Checking blocking status for nonexistent task.

        Given: Task ID does not exist
        When: get_task_blocking_status is called
        Then: Returns is_blocked: false (safe default)
        """
        # Arrange: Use nonexistent task ID
        nonexistent_task_id = "does-not-exist-12345"

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(
            project["id"],
            nonexistent_task_id
        )

        # Assert: Returns safe default
        assert blocking_status["is_blocked"] is False
        assert blocking_status["blocking_tasks"] == []

    def test_dep_010_custom_complete_swimlane_unblocks_tasks(self, store, project):
        """
        Additional test: Custom swimlane marked as complete unblocks dependencies.

        Given: Custom swimlane "verified" marked as is_complete: true
        When: Task A is in "verified" and Task B depends on A
        Then: Task B is not blocked
        """
        # Arrange: Create custom complete swimlane
        custom_swimlane = store.create_swimlane(
            project_id=project["id"],
            name="Verified",
            id="verified",
            is_complete=True,
            order=3
        )

        # Arrange: Create task A in custom complete swimlane
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - In Verified",
            swimlane="verified"
        )

        # Arrange: Create task B depending on task A
        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Should Not Be Blocked",
            swimlane="todo",
            depends_on=[task_a["id"]]
        )

        # Act: Check blocking status
        blocking_status = store.get_task_blocking_status(project["id"], task_b["id"])

        # Assert: Not blocked by task in custom complete swimlane
        assert blocking_status["is_blocked"] is False
        assert blocking_status["blocking_tasks"] == []


class TestTaskBlockingStatusIntegration:
    """Integration tests for task blocking status with real workflows."""

    def test_workflow_dependency_chain_resolution(self, store, project):
        """
        Integration test: Three-task dependency chain completes correctly.

        Given: Task C depends on B, B depends on A
        When: Tasks complete in order A -> B -> C
        Then: Blocking status updates correctly at each step
        """
        # Arrange: Create dependency chain A -> B -> C
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Foundation",
            swimlane="todo"
        )

        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Middle",
            swimlane="todo",
            depends_on=[task_a["id"]]
        )

        task_c = store.create_task(
            project_id=project["id"],
            name="Task C - Final",
            swimlane="todo",
            depends_on=[task_b["id"]]
        )

        # Assert: Initial state - all blocked except A
        status_a = store.get_task_blocking_status(project["id"], task_a["id"])
        status_b = store.get_task_blocking_status(project["id"], task_b["id"])
        status_c = store.get_task_blocking_status(project["id"], task_c["id"])

        assert status_a["is_blocked"] is False
        assert status_b["is_blocked"] is True
        assert status_c["is_blocked"] is True

        # Act: Complete task A
        store.update_task(project["id"], task_a["id"], swimlane="done")

        # Assert: B is unblocked, C still blocked
        status_b = store.get_task_blocking_status(project["id"], task_b["id"])
        status_c = store.get_task_blocking_status(project["id"], task_c["id"])

        assert status_b["is_blocked"] is False
        assert status_c["is_blocked"] is True

        # Act: Complete task B
        store.update_task(project["id"], task_b["id"], swimlane="done")

        # Assert: C is now unblocked
        status_c = store.get_task_blocking_status(project["id"], task_c["id"])

        assert status_c["is_blocked"] is False

    def test_workflow_updating_dependencies_changes_blocking_status(self, store, project):
        """
        Integration test: Updating task dependencies changes blocking status.

        Given: Task B initially has no dependencies
        When: depends_on is updated to include incomplete Task A
        Then: Task B becomes blocked
        """
        # Arrange: Create two independent tasks
        task_a = store.create_task(
            project_id=project["id"],
            name="Task A - Incomplete",
            swimlane="in_progress"
        )

        task_b = store.create_task(
            project_id=project["id"],
            name="Task B - Initially Independent",
            swimlane="todo"
        )

        # Assert: Initially not blocked
        status_initial = store.get_task_blocking_status(project["id"], task_b["id"])
        assert status_initial["is_blocked"] is False

        # Act: Update task B to depend on task A
        store.update_task(
            project_id=project["id"],
            task_id=task_b["id"],
            depends_on=[task_a["id"]]
        )

        # Assert: Now blocked by task A
        status_updated = store.get_task_blocking_status(project["id"], task_b["id"])
        assert status_updated["is_blocked"] is True
        assert len(status_updated["blocking_tasks"]) == 1
        assert status_updated["blocking_tasks"][0]["task_id"] == task_a["id"]
