"""
Safety module for wicked-patch.

Provides safety validations before applying patches:
1. Git clean working tree check
2. Transactional patch application with rollback
3. Symbol graph freshness gate
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

BACKUP_SUFFIX = ".wicked-backup"


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.passed


class SafetyError(Exception):
    """Raised when a safety check fails."""
    pass


class GitSafetyChecker:
    """Check git repository state for safety."""

    @staticmethod
    def check_git_clean(path: Path) -> SafetyCheckResult:
        """
        Check if the git working tree is clean.

        Args:
            path: Path to check (file or directory)

        Returns:
            SafetyCheckResult with pass/fail and details
        """
        # Find git root
        git_root = GitSafetyChecker._find_git_root(path)
        if not git_root:
            return SafetyCheckResult(
                passed=False,
                message="Not a git repository. wicked-patch requires git for safety.",
                details={"path": str(path)}
            )

        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=git_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return SafetyCheckResult(
                    passed=False,
                    message=f"Git status failed: {result.stderr}",
                    details={"returncode": result.returncode}
                )

            if result.stdout.strip():
                # There are uncommitted changes
                changed_files = result.stdout.strip().split("\n")
                return SafetyCheckResult(
                    passed=False,
                    message=f"Working tree has {len(changed_files)} uncommitted changes. Commit or stash first.",
                    details={
                        "changed_files": changed_files[:10],  # Limit to first 10
                        "total_changes": len(changed_files)
                    }
                )

            return SafetyCheckResult(
                passed=True,
                message="Git working tree is clean",
                details={"git_root": str(git_root)}
            )

        except subprocess.TimeoutExpired:
            return SafetyCheckResult(
                passed=False,
                message="Git status timed out",
            )
        except FileNotFoundError:
            return SafetyCheckResult(
                passed=False,
                message="Git not found. Install git to use wicked-patch.",
            )

    @staticmethod
    def _find_git_root(path: Path) -> Optional[Path]:
        """Find the git repository root."""
        current = path.resolve()
        if current.is_file():
            current = current.parent

        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent

        return None


class FreshnessChecker:
    """Check symbol graph freshness."""

    DEFAULT_MAX_AGE_HOURS = 24

    @staticmethod
    def check_freshness(
        db_path: Path,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS
    ) -> SafetyCheckResult:
        """
        Check if the symbol graph is fresh enough.

        Args:
            db_path: Path to the wicked-search database
            max_age_hours: Maximum age in hours before considered stale

        Returns:
            SafetyCheckResult with pass/fail and age details
        """
        if not db_path.exists():
            return SafetyCheckResult(
                passed=False,
                message=f"Symbol database not found: {db_path}",
                details={"db_path": str(db_path)}
            )

        try:
            # Try to get index timestamp from database metadata
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check for metadata table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
            )
            if not cursor.fetchone():
                # No metadata table, fall back to file modification time
                index_time = datetime.fromtimestamp(db_path.stat().st_mtime)
            else:
                # Try to get indexed_at from metadata
                cursor.execute(
                    "SELECT value FROM metadata WHERE key = 'indexed_at'"
                )
                row = cursor.fetchone()
                if row:
                    index_time = datetime.fromisoformat(row[0])
                else:
                    index_time = datetime.fromtimestamp(db_path.stat().st_mtime)

            conn.close()

            # Calculate age
            age = datetime.now() - index_time
            age_hours = age.total_seconds() / 3600

            if age_hours > max_age_hours:
                return SafetyCheckResult(
                    passed=False,
                    message=f"Symbol graph is stale ({age_hours:.1f}h old). "
                            f"Run /wicked-search:index or use --force",
                    details={
                        "index_time": index_time.isoformat(),
                        "age_hours": age_hours,
                        "max_age_hours": max_age_hours
                    }
                )

            return SafetyCheckResult(
                passed=True,
                message=f"Symbol graph is fresh ({age_hours:.1f}h old)",
                details={
                    "index_time": index_time.isoformat(),
                    "age_hours": age_hours
                }
            )

        except Exception as e:
            return SafetyCheckResult(
                passed=False,
                message=f"Failed to check graph freshness: {e}",
                details={"error": str(e)}
            )


@dataclass
class ApplyResult:
    """Result of patch application."""
    success: bool
    files_modified: List[str]
    files_failed: List[str]
    error: Optional[str] = None
    rolled_back: bool = False


class TransactionalApplicator:
    """
    Apply patches transactionally with rollback on failure.

    Uses file-level backups to ensure atomicity:
    1. Backup all files before modification
    2. Apply all patches
    3. On failure: restore all backups
    4. On success: delete all backups
    """

    def __init__(self, patches: List["Patch"]):
        """
        Initialize with patches to apply.

        Args:
            patches: List of Patch objects to apply
        """
        self.patches = patches
        self.backups: Dict[str, Path] = {}  # original_path -> backup_path

    def apply(self, dry_run: bool = False) -> ApplyResult:
        """
        Apply all patches transactionally.

        Args:
            dry_run: If True, only validate without applying

        Returns:
            ApplyResult with success/failure details
        """
        if dry_run:
            return self._dry_run()

        files_modified = []
        files_failed = []

        try:
            # Step 1: Create backups
            self._create_backups()

            # Step 2: Group patches by file
            patches_by_file = self._group_by_file()

            # Step 3: Apply patches to each file
            for file_path, file_patches in patches_by_file.items():
                try:
                    self._apply_file_patches(file_path, file_patches)
                    files_modified.append(file_path)
                except Exception as e:
                    files_failed.append(file_path)
                    raise SafetyError(f"Failed to patch {file_path}: {e}")

            # Step 4: Success - clean up backups
            self._cleanup_backups()

            return ApplyResult(
                success=True,
                files_modified=files_modified,
                files_failed=[],
                error=None,
                rolled_back=False
            )

        except Exception as e:
            # Step 3b: Failure - restore backups
            logger.error(f"Patch application failed: {e}")
            self._restore_backups()

            return ApplyResult(
                success=False,
                files_modified=[],
                files_failed=files_failed,
                error=str(e),
                rolled_back=True
            )

    def _dry_run(self) -> ApplyResult:
        """Validate patches without applying."""
        files = set()
        for patch in self.patches:
            if patch.file_path:
                files.add(patch.file_path)
                if not Path(patch.file_path).exists():
                    return ApplyResult(
                        success=False,
                        files_modified=[],
                        files_failed=[patch.file_path],
                        error=f"File not found: {patch.file_path}"
                    )

        return ApplyResult(
            success=True,
            files_modified=list(files),
            files_failed=[],
            error=None
        )

    def _create_backups(self):
        """Create backup copies of all files to be modified."""
        files_to_backup = set(p.file_path for p in self.patches if p.file_path)

        for file_path in files_to_backup:
            path = Path(file_path)
            if path.exists():
                backup_path = path.with_suffix(path.suffix + BACKUP_SUFFIX)
                shutil.copy2(path, backup_path)
                self.backups[file_path] = backup_path
                logger.debug(f"Backed up {file_path} -> {backup_path}")

    def _restore_backups(self):
        """Restore all backed up files."""
        for original_path, backup_path in self.backups.items():
            if backup_path.exists():
                shutil.copy2(backup_path, original_path)
                backup_path.unlink()
                logger.info(f"Restored {original_path} from backup")

        self.backups.clear()

    def _cleanup_backups(self):
        """Delete all backup files after successful application."""
        for backup_path in self.backups.values():
            if backup_path.exists():
                backup_path.unlink()
                logger.debug(f"Cleaned up backup {backup_path}")

        self.backups.clear()

    def _group_by_file(self) -> Dict[str, List["Patch"]]:
        """Group patches by file path."""
        by_file: Dict[str, List] = {}
        for patch in self.patches:
            if patch.file_path:
                if patch.file_path not in by_file:
                    by_file[patch.file_path] = []
                by_file[patch.file_path].append(patch)

        # Sort patches within each file by line number (descending)
        # Apply from bottom to top to preserve line numbers
        for patches in by_file.values():
            patches.sort(key=lambda p: p.line_start, reverse=True)

        return by_file

    def _apply_file_patches(self, file_path: str, patches: List["Patch"]):
        """Apply patches to a single file."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")

        for patch in patches:
            lines = self._apply_patch(lines, patch)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _apply_patch(self, lines: List[str], patch: "Patch") -> List[str]:
        """Apply a single patch to lines."""
        if patch.line_start > patch.line_end:
            # Insertion: insert new content after line_start
            new_lines = patch.new_content.split("\n") if patch.new_content else []
            return lines[:patch.line_start] + new_lines + lines[patch.line_start:]
        elif not patch.new_content.strip():
            # Deletion: remove lines
            return lines[:patch.line_start - 1] + lines[patch.line_end:]
        else:
            # Replacement: replace lines
            new_lines = patch.new_content.split("\n")
            return lines[:patch.line_start - 1] + new_lines + lines[patch.line_end:]


def run_safety_checks(
    files: List[str],
    db_path: Path,
    force: bool = False,
    skip_git: bool = False,
    max_age_hours: int = 24,
) -> Tuple[bool, List[SafetyCheckResult]]:
    """
    Run all safety checks.

    Args:
        files: List of files that will be modified
        db_path: Path to symbol database
        force: If True, allow stale graph
        skip_git: If True, skip git clean check
        max_age_hours: Maximum graph age

    Returns:
        Tuple of (all_passed, list of results)
    """
    results = []

    # Git clean check
    if not skip_git and files:
        git_result = GitSafetyChecker.check_git_clean(Path(files[0]))
        results.append(git_result)
        if not git_result.passed:
            return False, results

    # Freshness check
    if not force:
        freshness_result = FreshnessChecker.check_freshness(db_path, max_age_hours)
        results.append(freshness_result)
        if not freshness_result.passed:
            return False, results

    return True, results
