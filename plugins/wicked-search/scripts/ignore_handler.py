"""Handle file ignoring based on .gitignore patterns and default exclusions."""

import logging
import os
import threading
from pathlib import Path
from typing import Dict, List


try:
    import pathspec

    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False


logger = logging.getLogger(__name__)

if not PATHSPEC_AVAILABLE:
    logger.warning("pathspec not available - gitignore support disabled")


# Default patterns to ignore
DEFAULT_IGNORES = [
    # Version control
    ".git/",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".svn/",
    ".hg/",
    # Python
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "build/",
    "develop-eggs/",
    "dist/",
    "downloads/",
    "eggs/",
    ".eggs/",
    "lib/",
    "lib64/",
    "parts/",
    "sdist/",
    "var/",
    "wheels/",
    "pip-wheel-metadata/",
    "share/python-wheels/",
    "*.egg-info/",
    "*.egg",
    ".pytest_cache/",
    ".coverage",
    "htmlcov/",
    ".tox/",
    ".nox/",
    ".hypothesis/",
    # Virtual environments
    ".env",
    ".venv",
    "env/",
    "venv/",
    "ENV/",
    "VENV/",
    "env.bak/",
    "venv.bak/",
    # IDEs
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "*~",
    ".project",
    ".classpath",
    ".settings/",
    # OS-specific
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "$RECYCLE.BIN/",
    "*.lnk",
    # Node
    "node_modules/",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    # Logs and databases
    "*.log",
    "*.sqlite",
    "*.db",
    # Compiled files
    "*.so",
    "*.dylib",
    "*.dll",
    "*.class",
    "*.o",
    "*.a",
    # Archives
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.rar",
    "*.7z",
    # Media files (usually don't need indexing)
    "*.mp3",
    "*.mp4",
    "*.avi",
    "*.mov",
    "*.wmv",
    "*.flv",
    "*.wav",
    "*.flac",
    # Large binary files
    "*.exe",
    "*.dmg",
    "*.iso",
    "*.msi",
    # Temporary files
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.backup",
    "*.old",
    ".~*",
    # Project specific
    "vector_db/",
    "*.lance",
]

# Cache for IgnoreHandler instances to avoid repeated instantiation
_ignore_handler_cache: Dict[str, "IgnoreHandler"] = {}
_cache_lock = threading.Lock()
MAX_CACHE_SIZE = 16  # Limit cache size to prevent memory issues


def get_ignore_handler(root_path: str, custom_ignores: List[str] | None = None) -> "IgnoreHandler":
    """Get or create an IgnoreHandler for the given root path.

    This function caches IgnoreHandler instances to avoid repeated instantiation
    and the expensive directory traversal that happens during initialization.

    Args:
        root_path: Root directory path
        custom_ignores: Additional patterns to ignore (not cached if provided)

    Returns:
        IgnoreHandler instance
    """
    # If custom ignores are provided, don't use cache (rare case)
    if custom_ignores:
        return IgnoreHandler(root_path, custom_ignores)

    resolved_path = str(Path(root_path).resolve())

    with _cache_lock:
        if resolved_path in _ignore_handler_cache:
            return _ignore_handler_cache[resolved_path]

        # Clean cache if it gets too large
        if len(_ignore_handler_cache) >= MAX_CACHE_SIZE:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(_ignore_handler_cache.keys())[: MAX_CACHE_SIZE // 2]
            for key in keys_to_remove:
                del _ignore_handler_cache[key]

        # Create new handler and cache it
        handler = IgnoreHandler(root_path)
        _ignore_handler_cache[resolved_path] = handler
        return handler


class IgnoreHandler:
    """Handles file ignoring based on .gitignore patterns and default exclusions."""

    def __init__(self, root_path: str, custom_ignores: List[str] | None = None):
        """Initialize the ignore handler.

        Args:
            root_path: Root directory path
            custom_ignores: Additional patterns to ignore
        """
        self.root_path = Path(root_path).resolve()
        self.custom_ignores = custom_ignores or []

        # Find the actual project root by looking for project indicators
        # This ensures we load .gitignore from the project root even if
        # the user is indexing a subdirectory
        self.project_root = self._find_project_root()

        if PATHSPEC_AVAILABLE:
            # Combine default and custom ignores
            all_ignores = DEFAULT_IGNORES + self.custom_ignores
            self.default_spec = pathspec.PathSpec.from_lines("gitwildmatch", all_ignores)
            self.gitignore_specs = self._load_gitignore_specs()
        else:
            self.default_spec = None  # type: ignore[assignment]
            self.gitignore_specs = {}  # type: ignore[assignment]
            # Fallback to simple pattern matching
            self.simple_patterns = DEFAULT_IGNORES + self.custom_ignores

    def _find_project_root(self) -> Path:
        """Find the project root by walking up from root_path.

        Looks for common project indicators like .git, pyproject.toml, package.json.
        This ensures we load .gitignore files from the actual project root.

        Returns:
            Path to project root (or root_path if no project root found)
        """
        current = self.root_path
        project_indicators = [".git", "pyproject.toml", "package.json", ".gitignore"]

        # Walk up the directory tree
        while current != current.parent:  # Stop at filesystem root
            # Check if this directory has project indicators
            for indicator in project_indicators:
                if (current / indicator).exists():
                    logger.debug("Found project root at %s (indicator: %s)", current, indicator)
                    return current
            current = current.parent

        # No project root found, use the specified root_path
        logger.debug("No project root found, using %s", self.root_path)
        return self.root_path

    def _load_gitignore_specs(self) -> Dict[str, "pathspec.PathSpec"]:
        """Load all .gitignore files in the directory tree.

        Starts from project_root to ensure we load .gitignore files from
        the actual project root, not just the specified indexing directory.

        Returns:
            Dictionary mapping directory paths to their gitignore specs
        """
        if not PATHSPEC_AVAILABLE:
            return {}

        specs = {}
        # Directories to skip during traversal for performance
        skip_dirs = {
            ".git",
            ".venv",
            "venv",
            "env",
            ".env",
            "node_modules",
            "__pycache__",
            "dist",
            "build",
            ".idea",
            ".vscode",
            ".pytest_cache",
            ".tox",
            ".eggs",
            "vector_db",
            ".serena",
        }

        # Start from project_root (which may be above root_path)
        # This ensures we load .gitignore from the project root
        for root, dirs, files in os.walk(self.project_root, topdown=True):
            # Prune directories we don't want to traverse
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            # Skip if this looks like a virtual environment (has pyvenv.cfg)
            if "pyvenv.cfg" in files:
                dirs[:] = []  # Don't traverse any subdirectories
                continue

            if ".gitignore" in files:
                gitignore_path = os.path.join(root, ".gitignore")
                try:
                    with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
                        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                        if lines:
                            key = str(Path(root).resolve())
                            specs[key] = pathspec.PathSpec.from_lines("gitwildmatch", lines)
                            # Use lazy logging to avoid spam
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("Loaded .gitignore from %s", gitignore_path)
                except Exception as e:
                    logger.warning("Failed to load .gitignore from %s: %s", gitignore_path, e)

        return specs

    def is_ignored(self, file_path: str) -> bool:
        """Check if a file should be ignored.

        Args:
            file_path: Path to check

        Returns:
            True if file should be ignored
        """
        resolved_path = Path(file_path).resolve()

        # Always ignore if path is outside root
        try:
            rel_path = resolved_path.relative_to(self.root_path)
        except ValueError:
            return True

        if PATHSPEC_AVAILABLE and self.default_spec:
            # Check against default and custom ignores
            if self.default_spec.match_file(str(rel_path)):
                return True

            # Check against .gitignore files in the hierarchy (recursive upwards)
            # Walk up to project_root (not just root_path) to check all applicable .gitignore files
            current_dir = resolved_path.parent
            project_root_resolved = self.project_root
            while True:
                key = str(current_dir)
                if key in self.gitignore_specs:
                    spec = self.gitignore_specs[key]
                    # Pathspec needs path relative to the .gitignore file
                    try:
                        rel_to_gitignore = resolved_path.relative_to(current_dir)
                        if spec.match_file(str(rel_to_gitignore)):
                            return True
                    except ValueError:
                        pass
                # Stop at project root (which may be above root_path)
                if current_dir == project_root_resolved:
                    break
                parent = current_dir.parent
                if parent == current_dir:  # Reached filesystem root
                    break
                current_dir = parent
        else:
            # Fallback to simple pattern matching
            str_path = str(rel_path)
            for pattern in self.simple_patterns:
                # Simple pattern matching
                if pattern.endswith("/"):
                    # Directory pattern
                    if f"/{pattern}" in f"/{str_path}/" or str_path.startswith(pattern):
                        return True
                elif "*" in pattern:
                    # Wildcard pattern (simple)
                    import fnmatch

                    if fnmatch.fnmatch(str_path, pattern) or fnmatch.fnmatch(resolved_path.name, pattern):
                        return True
                else:
                    # Exact match or suffix
                    if pattern in str_path or str_path.endswith(pattern) or resolved_path.name == pattern:
                        return True

        return False

    def filter_paths(self, paths: List[str]) -> List[str]:
        """Filter a list of paths, removing ignored ones.

        Args:
            paths: List of file paths

        Returns:
            Filtered list of paths
        """
        return [p for p in paths if not self.is_ignored(p)]

    def should_process_directory(self, dir_path: str) -> bool:
        """Check if a directory should be processed.

        Args:
            dir_path: Directory path to check

        Returns:
            True if directory should be processed
        """
        dir_path = Path(dir_path)  # type: ignore[assignment]

        # Check if directory name matches ignore patterns
        dir_name = dir_path.name  # type: ignore[attr-defined]
        for pattern in [
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            ".idea",
            ".vscode",
            "vector_db",
        ]:
            if dir_name == pattern:
                return False

        return not self.is_ignored(str(dir_path))
