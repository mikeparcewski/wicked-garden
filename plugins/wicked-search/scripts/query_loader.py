"""Query file loader for tree-sitter queries."""

from pathlib import Path
from typing import Dict, List, Optional


class QueryLoader:
    """Loads tree-sitter query files for different languages."""

    def __init__(self, queries_dir: Optional[Path] = None):
        """Initialize the query loader.

        Args:
            queries_dir: Directory containing query files. If None, uses default location.
        """
        if queries_dir is None:
            # Default to queries directory next to this file
            self.queries_dir = Path(__file__).parent / "queries"
        else:
            self.queries_dir = Path(queries_dir)

        self._query_cache: Dict[str, str] = {}

    def load_query(self, language: str) -> Optional[str]:
        """Load a tree-sitter query file for the specified language.

        Args:
            language: Programming language name (e.g., 'python', 'javascript')

        Returns:
            Query string or None if not found
        """
        # Check cache first
        if language in self._query_cache:
            return self._query_cache[language]

        # Try to load from file
        query_file = self.queries_dir / f"{language}.scm"

        if not query_file.exists():
            return None

        try:
            query_content = query_file.read_text(encoding='utf-8')
            self._query_cache[language] = query_content
            return query_content
        except Exception:
            return None

    def has_query(self, language: str) -> bool:
        """Check if a query file exists for the specified language."""
        query_file = self.queries_dir / f"{language}.scm"
        return query_file.exists()

    def get_available_languages(self) -> List[str]:
        """Get list of languages with available query files."""
        if not self.queries_dir.exists():
            return []

        languages = []
        for query_file in self.queries_dir.glob("*.scm"):
            languages.append(query_file.stem)

        return sorted(languages)


# Global query loader instance
_query_loader: Optional[QueryLoader] = None


def get_query_loader() -> QueryLoader:
    """Get the global query loader instance."""
    global _query_loader
    if _query_loader is None:
        _query_loader = QueryLoader()
    return _query_loader
