"""
Shared utilities for language adapters.

Provides common naming conventions and helper functions used across
multiple ORM adapters.
"""

import re
from typing import Optional


class NamingUtils:
    """Shared naming convention utilities."""

    # Pre-compiled patterns for better performance
    _CAMEL_PATTERN1 = re.compile('(.)([A-Z][a-z]+)')
    _CAMEL_PATTERN2 = re.compile('([a-z0-9])([A-Z])')

    @classmethod
    def to_snake_case(cls, name: str) -> str:
        """
        Convert CamelCase to snake_case.

        Examples:
            UserAccount -> user_account
            HTTPServer -> http_server
            XMLParser -> xml_parser
        """
        if not name:
            return ""
        s1 = cls._CAMEL_PATTERN1.sub(r'\1_\2', name)
        return cls._CAMEL_PATTERN2.sub(r'\1_\2', s1).lower()

    @classmethod
    def pluralize(cls, name: str) -> str:
        """
        Simple English pluralization for table names.

        Note: This is a simplified version. Rails uses more sophisticated
        inflection rules. This handles common cases.

        Examples:
            user -> users
            category -> categories
            status -> statuses
            person -> persons (not 'people')
        """
        if not name:
            return ""

        if name.endswith('y') and len(name) > 1 and name[-2] not in 'aeiou':
            return name[:-1] + 'ies'
        elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return name + 'es'
        else:
            return name + 's'

    @classmethod
    def tableize(cls, class_name: str) -> str:
        """
        Convert class name to table name (snake_case + plural).

        Examples:
            UserAccount -> user_accounts
            Category -> categories
            Status -> statuses
        """
        return cls.pluralize(cls.to_snake_case(class_name))


def safe_text(content: str, node, default: str = "") -> str:
    """
    Safely extract text from a tree-sitter node.

    Args:
        content: Source file content
        node: Tree-sitter node (may be None)
        default: Default value if extraction fails

    Returns:
        Extracted text or default
    """
    if node is None:
        return default
    try:
        start = node.start_byte
        end = node.end_byte
        if 0 <= start < end <= len(content):
            return content[start:end]
    except (AttributeError, TypeError):
        pass
    return default


def safe_line(content: str, node, default: int = 0) -> int:
    """
    Safely extract line number from a tree-sitter node.

    Args:
        content: Source file content (unused, for consistency)
        node: Tree-sitter node (may be None)
        default: Default value if extraction fails

    Returns:
        Line number (1-indexed) or default
    """
    if node is None:
        return default
    try:
        return node.start_point[0] + 1
    except (AttributeError, TypeError, IndexError):
        return default


def safe_match_group(match, group: int, default: str = "") -> str:
    """
    Safely extract a group from a regex match.

    Args:
        match: Regex match object (may be None)
        group: Group index
        default: Default value if extraction fails

    Returns:
        Group text or default
    """
    if match is None:
        return default
    try:
        result = match.group(group)
        return result if result is not None else default
    except (IndexError, AttributeError):
        return default
