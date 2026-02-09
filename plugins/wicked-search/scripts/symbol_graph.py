"""
Symbol Graph model for wicked-search.

Unified representation of code symbols and their relationships across all layers:
- Backend (Java entities, controllers, services, DAOs)
- JSP/Templates (pages, EL expressions, form bindings)
- HTML/Frontend (components, data bindings, form fields)
- Database (tables, columns)

Based on Ohio team's extraction infrastructure, merged into wicked-search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import json
import sqlite3
from pathlib import Path


class SymbolType(str, Enum):
    """Types of symbols across all layers."""

    # Backend (Java)
    ENTITY = "entity"
    ENTITY_FIELD = "entity_field"
    CONTROLLER = "controller"
    CONTROLLER_METHOD = "controller_method"
    SERVICE = "service"
    SERVICE_METHOD = "service_method"
    DAO = "dao"
    DAO_METHOD = "dao_method"

    # Database
    TABLE = "table"
    COLUMN = "column"

    # JSP/Templates
    JSP_PAGE = "jsp_page"
    JSP_INCLUDE = "jsp_include"
    EL_EXPRESSION = "el_expression"
    FORM_BINDING = "form_binding"
    JSTL_VARIABLE = "jstl_variable"
    TAGLIB = "taglib"

    # HTML/Frontend
    HTML_PAGE = "html_page"
    COMPONENT = "component"
    COMPONENT_PROP = "component_prop"
    FORM_FIELD = "form_field"
    DATA_BINDING = "data_binding"
    EVENT_HANDLER = "event_handler"
    SLOT = "slot"
    ROUTE = "route"

    # Generic (from existing models.py)
    FILE = "file"
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM_TYPE = "enum"
    TRAIT = "trait"
    TYPE = "type"
    IMPORT = "import"
    DOC_SECTION = "doc_section"
    DOC_PAGE = "doc_page"


class ReferenceType(str, Enum):
    """Types of relationships between symbols."""

    # File relationships
    INCLUDES = "includes"           # JSP/HTML includes another file
    IMPORTS = "imports"             # Module import

    # Data binding relationships
    BINDS_TO = "binds_to"           # EL/binding to data source
    MAPS_TO = "maps_to"             # Entity field to column

    # Method relationships
    CALLS = "calls"                 # Method invocation
    INJECTS = "injects"             # Dependency injection (@Autowired)

    # Controller relationships
    HANDLES = "handles"             # Controller handles URL
    RETURNS_VIEW = "returns_view"   # Controller returns view name
    USES_MODEL = "uses_model"       # Controller uses model attribute

    # Component relationships
    RENDERS = "renders"             # Component renders child
    EMITS = "emits"                 # Component emits event
    RECEIVES_PROP = "receives_prop" # Component receives prop

    # Class relationships
    EXTENDS = "extends"             # Class inheritance
    IMPLEMENTS = "implements"       # Interface implementation


class Confidence(str, Enum):
    """Confidence level for inferred relationships."""
    HIGH = "high"           # Direct annotation/explicit mapping
    MEDIUM = "medium"       # Naming convention match
    LOW = "low"             # Single weak indicator
    INFERRED = "inferred"   # Guessed from context


@dataclass
class Symbol:
    """
    A symbol in the codebase.

    Can represent: class, method, field, JSP page, component, column, etc.
    """
    id: str                             # Unique ID: "path/file.java::ClassName.field"
    type: SymbolType                    # Symbol type
    name: str                           # Simple name
    qualified_name: str                 # Fully qualified name
    file_path: str                      # Source file
    line_start: int                     # Starting line
    line_end: Optional[int] = None      # Ending line
    metadata: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None         # Human-readable label for data dictionary

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Symbol):
            return False
        return self.id == other.id

    def get_layer(self) -> str:
        """Get architectural layer for this symbol."""
        layer_map = {
            # Backend
            SymbolType.ENTITY: "backend",
            SymbolType.ENTITY_FIELD: "backend",
            SymbolType.CONTROLLER: "backend",
            SymbolType.CONTROLLER_METHOD: "backend",
            SymbolType.SERVICE: "backend",
            SymbolType.SERVICE_METHOD: "backend",
            SymbolType.DAO: "backend",
            SymbolType.DAO_METHOD: "backend",
            SymbolType.CLASS: "backend",
            SymbolType.METHOD: "backend",
            SymbolType.FUNCTION: "backend",

            # Database
            SymbolType.TABLE: "database",
            SymbolType.COLUMN: "database",

            # View/Template
            SymbolType.JSP_PAGE: "view",
            SymbolType.JSP_INCLUDE: "view",
            SymbolType.EL_EXPRESSION: "view",
            SymbolType.FORM_BINDING: "view",
            SymbolType.JSTL_VARIABLE: "view",
            SymbolType.TAGLIB: "view",

            # Frontend
            SymbolType.HTML_PAGE: "frontend",
            SymbolType.COMPONENT: "frontend",
            SymbolType.COMPONENT_PROP: "frontend",
            SymbolType.FORM_FIELD: "frontend",
            SymbolType.DATA_BINDING: "frontend",
            SymbolType.EVENT_HANDLER: "frontend",
            SymbolType.ROUTE: "frontend",
        }
        return layer_map.get(self.type, "unknown")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "label": self.label,
            "layer": self.get_layer(),
            "metadata": self.metadata,
        }


@dataclass
class Reference:
    """
    A directional relationship between two symbols.
    """
    source_id: str                      # Source symbol ID
    target_id: str                      # Target symbol ID
    ref_type: ReferenceType             # Relationship type
    confidence: Confidence              # Confidence level
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.source_id, self.target_id, self.ref_type.value))

    def __eq__(self, other):
        if not isinstance(other, Reference):
            return False
        return (self.source_id == other.source_id and
                self.target_id == other.target_id and
                self.ref_type == other.ref_type)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "ref_type": self.ref_type.value if isinstance(self.ref_type, Enum) else self.ref_type,
            "confidence": self.confidence.value if isinstance(self.confidence, Enum) else self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class SymbolGraph:
    """
    Unified symbol graph with fast lookup indexes.

    Provides:
    - Symbol storage with multiple lookup indexes
    - Reference tracking (both directions)
    - Transitive reference traversal (for blast radius)
    - Export to JSON, SQLite, CSV
    """
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    references: List[Reference] = field(default_factory=list)

    # Indexes for fast lookup
    by_type: Dict[SymbolType, List[str]] = field(default_factory=dict)
    by_name: Dict[str, List[str]] = field(default_factory=dict)
    by_file: Dict[str, List[str]] = field(default_factory=dict)
    by_qualified_name: Dict[str, str] = field(default_factory=dict)

    # Reference indexes
    outgoing_refs: Dict[str, List[Reference]] = field(default_factory=dict)
    incoming_refs: Dict[str, List[Reference]] = field(default_factory=dict)

    def add_symbol(self, symbol: Symbol) -> None:
        """Add symbol and update all indexes."""
        self.symbols[symbol.id] = symbol

        # Type index
        sym_type = symbol.type if isinstance(symbol.type, SymbolType) else SymbolType(symbol.type)
        if sym_type not in self.by_type:
            self.by_type[sym_type] = []
        self.by_type[sym_type].append(symbol.id)

        # Name index (case-insensitive)
        name_key = symbol.name.lower()
        if name_key not in self.by_name:
            self.by_name[name_key] = []
        self.by_name[name_key].append(symbol.id)

        # File index
        if symbol.file_path:
            if symbol.file_path not in self.by_file:
                self.by_file[symbol.file_path] = []
            self.by_file[symbol.file_path].append(symbol.id)

        # Qualified name index
        if symbol.qualified_name:
            self.by_qualified_name[symbol.qualified_name.lower()] = symbol.id

    def add_reference(self, ref: Reference) -> None:
        """Add reference and update indexes."""
        # Avoid duplicates
        if ref in self.references:
            return

        self.references.append(ref)

        # Outgoing refs index
        if ref.source_id not in self.outgoing_refs:
            self.outgoing_refs[ref.source_id] = []
        self.outgoing_refs[ref.source_id].append(ref)

        # Incoming refs index
        if ref.target_id not in self.incoming_refs:
            self.incoming_refs[ref.target_id] = []
        self.incoming_refs[ref.target_id].append(ref)

    def get_symbol(self, symbol_id: str) -> Optional[Symbol]:
        """Get symbol by ID."""
        return self.symbols.get(symbol_id)

    def find_by_type(self, symbol_type: SymbolType) -> List[Symbol]:
        """Get all symbols of a type."""
        ids = self.by_type.get(symbol_type, [])
        return [self.symbols[sid] for sid in ids if sid in self.symbols]

    def find_by_name(self, name: str, type_filter: Optional[SymbolType] = None) -> List[Symbol]:
        """Find symbols by name with optional type filter."""
        ids = self.by_name.get(name.lower(), [])
        symbols = [self.symbols[sid] for sid in ids if sid in self.symbols]
        if type_filter:
            symbols = [s for s in symbols if s.type == type_filter]
        return symbols

    def find_by_qualified_name(self, qualified_name: str) -> Optional[Symbol]:
        """Find symbol by fully qualified name."""
        symbol_id = self.by_qualified_name.get(qualified_name.lower())
        return self.symbols.get(symbol_id) if symbol_id else None

    def find_by_file(self, file_path: str) -> List[Symbol]:
        """Get all symbols in a file."""
        ids = self.by_file.get(file_path, [])
        return [self.symbols[sid] for sid in ids if sid in self.symbols]

    def get_references_from(self, symbol_id: str,
                           ref_type: Optional[ReferenceType] = None) -> List[Reference]:
        """Get outgoing references from a symbol."""
        refs = self.outgoing_refs.get(symbol_id, [])
        if ref_type:
            refs = [r for r in refs if r.ref_type == ref_type]
        return refs

    def get_references_to(self, symbol_id: str,
                         ref_type: Optional[ReferenceType] = None) -> List[Reference]:
        """Get incoming references to a symbol."""
        refs = self.incoming_refs.get(symbol_id, [])
        if ref_type:
            refs = [r for r in refs if r.ref_type == ref_type]
        return refs

    def get_transitive_refs(self, symbol_id: str,
                           ref_types: Optional[Set[ReferenceType]] = None,
                           max_depth: int = 10) -> Set[str]:
        """
        Get all symbols transitively reachable from a symbol.

        Useful for blast radius analysis.
        """
        visited = set()
        queue = [(symbol_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth >= max_depth:
                continue
            visited.add(current)

            refs = self.outgoing_refs.get(current, [])
            if ref_types:
                refs = [r for r in refs if r.ref_type in ref_types]

            for ref in refs:
                if ref.target_id not in visited:
                    queue.append((ref.target_id, depth + 1))

        visited.discard(symbol_id)
        return visited

    def get_transitive_refs_reverse(self, symbol_id: str,
                                    ref_types: Optional[Set[ReferenceType]] = None,
                                    max_depth: int = 10) -> Set[str]:
        """
        Get all symbols that transitively reference this symbol (upstream).

        Follows incoming references backwards for reverse blast radius analysis.
        Useful for data lineage: "What depends on this column?"

        Args:
            symbol_id: Starting symbol ID
            ref_types: Optional set of reference types to follow
            max_depth: Maximum traversal depth

        Returns:
            Set of symbol IDs that depend on the starting symbol
        """
        visited = set()
        queue = [(symbol_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth >= max_depth:
                continue
            visited.add(current)

            # Use incoming_refs instead of outgoing_refs
            refs = self.incoming_refs.get(current, [])
            if ref_types:
                refs = [r for r in refs if r.ref_type in ref_types]

            for ref in refs:
                if ref.source_id not in visited:
                    queue.append((ref.source_id, depth + 1))

        visited.discard(symbol_id)
        return visited

    def get_blast_radius(self, symbol_id: str,
                         ref_types: Optional[Set[ReferenceType]] = None,
                         max_depth: int = 10,
                         direction: str = "both") -> Dict[str, Set[str]]:
        """
        Get full blast radius with both upstream and downstream analysis.

        Args:
            symbol_id: Starting symbol ID
            ref_types: Optional set of reference types to follow
            max_depth: Maximum traversal depth
            direction: "downstream" (outgoing), "upstream" (incoming), or "both"

        Returns:
            Dict with 'downstream' and/or 'upstream' symbol ID sets
        """
        result = {}

        if direction in ("downstream", "both"):
            result["downstream"] = self.get_transitive_refs(
                symbol_id, ref_types, max_depth
            )

        if direction in ("upstream", "both"):
            result["upstream"] = self.get_transitive_refs_reverse(
                symbol_id, ref_types, max_depth
            )

        return result

    # =========================================================================
    # Label Query Methods
    # =========================================================================

    def get_by_label(self, label: str) -> List[Symbol]:
        """Find all symbols with matching label (case-insensitive)."""
        label_lower = label.lower()
        return [s for s in self.symbols.values()
                if s.label and s.label.lower() == label_lower]

    def search_by_label(self, label_pattern: str) -> List[Symbol]:
        """Find symbols with labels containing the pattern (case-insensitive)."""
        pattern_lower = label_pattern.lower()
        return [s for s in self.symbols.values()
                if s.label and pattern_lower in s.label.lower()]

    def get_labeled(self) -> List[Symbol]:
        """Get all symbols that have labels."""
        return [s for s in self.symbols.values() if s.label]

    def get_unlabeled_forms(self) -> List[Symbol]:
        """Find form fields missing labels (accessibility check)."""
        return [s for s in self.symbols.values()
                if s.type in (SymbolType.FORM_BINDING, SymbolType.FORM_FIELD)
                and not s.label]

    def stats(self) -> Dict[str, int]:
        """Get statistics about the graph."""
        stats = {
            "total_symbols": len(self.symbols),
            "total_references": len(self.references),
        }

        # Count by symbol type
        for sym_type in SymbolType:
            count = len(self.by_type.get(sym_type, []))
            if count > 0:
                stats[f"symbols_{sym_type.value}"] = count

        # Count by reference type
        for ref_type in ReferenceType:
            count = sum(1 for r in self.references if r.ref_type == ref_type)
            if count > 0:
                stats[f"references_{ref_type.value}"] = count

        # Count by confidence
        for conf in Confidence:
            count = sum(1 for r in self.references if r.confidence == conf)
            if count > 0:
                stats[f"confidence_{conf.value}"] = count

        return stats

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_json(self, output_path: Path) -> None:
        """Export symbol graph to JSON file."""
        data = {
            "metadata": {
                "total_symbols": len(self.symbols),
                "total_references": len(self.references),
                "statistics": self.stats(),
            },
            "symbols": [s.to_dict() for s in self.symbols.values()],
            "references": [r.to_dict() for r in self.references],
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def export_sqlite(self, output_path: Path) -> None:
        """Export symbol graph to SQLite database."""
        # Remove existing file
        if output_path.exists():
            output_path.unlink()

        conn = sqlite3.connect(str(output_path))
        cursor = conn.cursor()

        # Create tables
        cursor.executescript("""
            CREATE TABLE symbols (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name TEXT,
                file_path TEXT,
                line_start INTEGER,
                line_end INTEGER,
                label TEXT,
                layer TEXT,
                metadata TEXT
            );

            CREATE TABLE refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                confidence TEXT,
                evidence TEXT,
                FOREIGN KEY (source_id) REFERENCES symbols(id),
                FOREIGN KEY (target_id) REFERENCES symbols(id)
            );

            CREATE INDEX idx_symbols_type ON symbols(type);
            CREATE INDEX idx_symbols_file ON symbols(file_path);
            CREATE INDEX idx_symbols_name ON symbols(name);
            CREATE INDEX idx_symbols_label ON symbols(label);
            CREATE INDEX idx_refs_source ON refs(source_id);
            CREATE INDEX idx_refs_target ON refs(target_id);
            CREATE INDEX idx_refs_type ON refs(ref_type);

            -- Reasoning extension tables (for lineage, impact, service-map)

            -- Derived references (computed from analysis)
            CREATE TABLE IF NOT EXISTS derived_refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                derivation_method TEXT,
                evidence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES symbols(id),
                FOREIGN KEY (target_id) REFERENCES symbols(id)
            );

            -- Precomputed lineage paths (source → sink traces)
            CREATE TABLE IF NOT EXISTS lineage_paths (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                sink_id TEXT NOT NULL,
                path_nodes TEXT,
                path_length INTEGER,
                min_confidence TEXT,
                is_complete INTEGER DEFAULT 0,
                gaps TEXT,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES symbols(id),
                FOREIGN KEY (sink_id) REFERENCES symbols(id)
            );

            -- Service map nodes (inferred from code/infra)
            CREATE TABLE IF NOT EXISTS service_nodes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                technology TEXT,
                metadata TEXT,
                inferred_from TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Service connections
            CREATE TABLE IF NOT EXISTS service_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_service_id TEXT NOT NULL,
                target_service_id TEXT NOT NULL,
                connection_type TEXT,
                protocol TEXT,
                evidence TEXT,
                confidence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_service_id) REFERENCES service_nodes(id),
                FOREIGN KEY (target_service_id) REFERENCES service_nodes(id)
            );

            -- Indexes for reasoning tables
            CREATE INDEX IF NOT EXISTS idx_derived_refs_source ON derived_refs(source_id);
            CREATE INDEX IF NOT EXISTS idx_derived_refs_target ON derived_refs(target_id);
            CREATE INDEX IF NOT EXISTS idx_derived_refs_type ON derived_refs(ref_type);
            CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage_paths(source_id);
            CREATE INDEX IF NOT EXISTS idx_lineage_sink ON lineage_paths(sink_id);
            CREATE INDEX IF NOT EXISTS idx_lineage_complete ON lineage_paths(is_complete);
            CREATE INDEX IF NOT EXISTS idx_service_nodes_type ON service_nodes(type);
            CREATE INDEX IF NOT EXISTS idx_service_conn_source ON service_connections(source_service_id);
            CREATE INDEX IF NOT EXISTS idx_service_conn_target ON service_connections(target_service_id);
        """)

        # Insert symbols
        for symbol in self.symbols.values():
            cursor.execute("""
                INSERT INTO symbols (id, type, name, qualified_name, file_path,
                                    line_start, line_end, label, layer, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol.id,
                symbol.type.value if isinstance(symbol.type, Enum) else symbol.type,
                symbol.name,
                symbol.qualified_name,
                symbol.file_path,
                symbol.line_start,
                symbol.line_end,
                symbol.label,
                symbol.get_layer(),
                json.dumps(symbol.metadata),
            ))

        # Insert references
        for ref in self.references:
            cursor.execute("""
                INSERT INTO refs (source_id, target_id, ref_type, confidence, evidence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                ref.source_id,
                ref.target_id,
                ref.ref_type.value if isinstance(ref.ref_type, Enum) else ref.ref_type,
                ref.confidence.value if isinstance(ref.confidence, Enum) else ref.confidence,
                json.dumps(ref.evidence),
            ))

        conn.commit()
        conn.close()

    def export_csv(self, output_dir: Path) -> None:
        """Export symbol graph to CSV files."""
        import csv

        output_dir.mkdir(parents=True, exist_ok=True)

        # Symbols CSV
        with open(output_dir / "symbols.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'type', 'name', 'qualified_name', 'file_path',
                           'line_start', 'line_end', 'layer'])
            for s in self.symbols.values():
                writer.writerow([
                    s.id,
                    s.type.value if isinstance(s.type, Enum) else s.type,
                    s.name,
                    s.qualified_name,
                    s.file_path,
                    s.line_start,
                    s.line_end,
                    s.get_layer(),
                ])

        # References CSV
        with open(output_dir / "references.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['source_id', 'target_id', 'ref_type', 'confidence'])
            for r in self.references:
                writer.writerow([
                    r.source_id,
                    r.target_id,
                    r.ref_type.value if isinstance(r.ref_type, Enum) else r.ref_type,
                    r.confidence.value if isinstance(r.confidence, Enum) else r.confidence,
                ])


def migrate_database(db_path: Path) -> bool:
    """
    Migrate existing database to include reasoning extension tables.

    Safe to call multiple times - uses IF NOT EXISTS.

    Args:
        db_path: Path to existing SQLite database

    Returns:
        True if migration succeeded, False otherwise
    """
    if not db_path.exists():
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Add reasoning extension tables
        cursor.executescript("""
            -- Derived references (computed from analysis)
            CREATE TABLE IF NOT EXISTS derived_refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                ref_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                derivation_method TEXT,
                evidence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES symbols(id),
                FOREIGN KEY (target_id) REFERENCES symbols(id)
            );

            -- Precomputed lineage paths (source → sink traces)
            CREATE TABLE IF NOT EXISTS lineage_paths (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                sink_id TEXT NOT NULL,
                path_nodes TEXT,
                path_length INTEGER,
                min_confidence TEXT,
                is_complete INTEGER DEFAULT 0,
                gaps TEXT,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES symbols(id),
                FOREIGN KEY (sink_id) REFERENCES symbols(id)
            );

            -- Service map nodes (inferred from code/infra)
            CREATE TABLE IF NOT EXISTS service_nodes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                technology TEXT,
                metadata TEXT,
                inferred_from TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Service connections
            CREATE TABLE IF NOT EXISTS service_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_service_id TEXT NOT NULL,
                target_service_id TEXT NOT NULL,
                connection_type TEXT,
                protocol TEXT,
                evidence TEXT,
                confidence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_service_id) REFERENCES service_nodes(id),
                FOREIGN KEY (target_service_id) REFERENCES service_nodes(id)
            );

            -- Indexes for reasoning tables
            CREATE INDEX IF NOT EXISTS idx_derived_refs_source ON derived_refs(source_id);
            CREATE INDEX IF NOT EXISTS idx_derived_refs_target ON derived_refs(target_id);
            CREATE INDEX IF NOT EXISTS idx_derived_refs_type ON derived_refs(ref_type);
            CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage_paths(source_id);
            CREATE INDEX IF NOT EXISTS idx_lineage_sink ON lineage_paths(sink_id);
            CREATE INDEX IF NOT EXISTS idx_lineage_complete ON lineage_paths(is_complete);
            CREATE INDEX IF NOT EXISTS idx_service_nodes_type ON service_nodes(type);
            CREATE INDEX IF NOT EXISTS idx_service_conn_source ON service_connections(source_service_id);
            CREATE INDEX IF NOT EXISTS idx_service_conn_target ON service_connections(target_service_id);
        """)
        conn.commit()
        return True
    except Exception as e:
        print(f"Migration error: {e}")
        return False
    finally:
        conn.close()
