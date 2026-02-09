"""Pydantic models for the JSONL reference graph.

This module defines the data structures for wicked-search's reference graph,
which stores code symbols and their relationships in a grep-friendly JSONL format.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Types of nodes in the reference graph."""
    FILE = "file"
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TRAIT = "trait"
    TYPE = "type"
    IMPORT = "import"
    DOC_SECTION = "doc_section"
    DOC_PAGE = "doc_page"


class CallRef(BaseModel):
    """A function/method call reference."""
    name: str                            # Called function name
    target_id: Optional[str] = None      # Resolved node ID (pass 2)
    line: int                            # Line number of call
    call_type: str = "function"          # "function" or "method"
    object_name: Optional[str] = None    # For method calls: obj.method()

    model_config = {"extra": "ignore"}


class GraphNode(BaseModel):
    """A node in the reference graph (one JSONL line).

    Each node represents a code symbol (function, class, etc.) or document
    section, along with its outgoing references (calls, imports, bases) and
    incoming references (dependents, computed in pass 2).
    """
    id: str                              # "path/file.py::ClassName.method"
    name: str                            # "method"
    node_type: NodeType = Field(alias="type")
    file: str                            # "path/file.py"
    line_start: int
    line_end: int

    # Outgoing edges (extracted in pass 1)
    calls: List[CallRef] = []            # Functions/methods this calls
    imports: List[str] = []              # Module imports
    bases: List[str] = []                # Parent classes (for classes)
    imported_names: List[str] = []       # For imports: specific names imported

    # Incoming edges (computed in pass 2)
    dependents: List[str] = []           # Node IDs that call/inherit/import this

    # Content for doc nodes and search
    content: Optional[str] = None        # Doc content or docstring

    # Domain: "code" or "doc"
    domain: str = "code"

    # Extensible metadata
    metadata: Dict[str, Any] = {}

    model_config = {
        "populate_by_name": True,
        "use_enum_values": True,
        "extra": "ignore",
    }


class FileMetadata(BaseModel):
    """Per-file metadata for staleness detection."""
    path: str
    mtime: float
    size: int
    indexed_at: str
    file_type: str  # "code" or "doc"
    node_count: int = 0

    model_config = {"extra": "ignore"}


class IndexMetadata(BaseModel):
    """Index metadata file (metadata.json)."""
    root_path: str
    created_at: str
    updated_at: str
    version: str = "2.0.0"
    file_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    files: Dict[str, FileMetadata] = {}

    model_config = {"extra": "ignore"}

    @classmethod
    def create(cls, root_path: str) -> "IndexMetadata":
        """Create a new index metadata instance."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            root_path=root_path,
            created_at=now,
            updated_at=now,
        )


# Type aliases for clarity
NodeId = str
SymbolName = str
