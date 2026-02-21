#!/usr/bin/env python3
"""
wicked-search: Unified code and document search with cross-reference detection.

Commands:
  index <path>           Build/rebuild index for code + docs
  search <query>         Search across everything
  code <query>           Search code only
  docs <query>           Search docs only
  refs <symbol>          Find where symbol is referenced/documented
  impl <doc-section>     Find code that implements a doc section
  graph <entity>         Show relationships for an entity
  stats                  Show index statistics
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import process, fuzz

# Import new JSONL-based modules
try:
    from models import GraphNode as JsonlGraphNode, CallRef, NodeType, IndexMetadata
    from models import FileMetadata as JsonlFileMetadata
    from indexer import ParallelIndexer
    from linker import DependencyLinker
    from updater import IncrementalUpdater
    HAS_JSONL_MODULES = True
except ImportError:
    HAS_JSONL_MODULES = False
    JsonlFileMetadata = None

# Import Symbol Graph modules (Ohio team merge)
try:
    from symbol_graph import SymbolGraph, Symbol, Reference, SymbolType, ReferenceType, Confidence
    from parsers import JspParser, HtmlFrontendParser
    from linkers import LinkerRegistry, list_linkers
    HAS_SYMBOL_GRAPH = True
except ImportError:
    HAS_SYMBOL_GRAPH = False
    SymbolGraph = None
    JspParser = None
    HtmlFrontendParser = None
    LinkerRegistry = None

# Import language adapters for ORM support
try:
    from adapters import (
        AdapterRegistry, LanguageAdapter,
        JavaAdapter, PythonAdapter, TypeScriptAdapter,
        PrismaAdapter, RubyAdapter, CSharpAdapter, GoAdapter,
    )
    HAS_ADAPTERS = True
except ImportError:
    HAS_ADAPTERS = False
    AdapterRegistry = None





# Try to import kreuzberg for document extraction
try:
    import kreuzberg
    HAS_KREUZBERG = True
except ImportError:
    HAS_KREUZBERG = False
    print("Warning: kreuzberg not installed. Document extraction disabled.", file=sys.stderr)

# Try to import tree-sitter for code parsing
try:
    import tree_sitter as ts
    from tree_sitter_language_pack import get_parser, get_language
    HAS_TREESITTER = True
except ImportError:
    HAS_TREESITTER = False
    ts = None
    print("Warning: tree-sitter not installed. Code parsing disabled.", file=sys.stderr)

# Import query loader for tree-sitter queries
try:
    from query_loader import get_query_loader
    HAS_QUERIES = True
except ImportError:
    HAS_QUERIES = False
    get_query_loader = None


# =============================================================================
# Configuration
# =============================================================================

def get_index_dir(project: str = None) -> Path:
    """
    Get the index storage directory.

    If project is specified, returns ~/.something-wicked/wicked-search/projects/{project}/
    Otherwise, returns ~/.something-wicked/wicked-search/ (backward compatible)
    """
    home = Path.home()
    base_dir = home / ".something-wicked" / "wicked-search"

    if project:
        # Validate project name
        if not project or len(project) > 64:
            raise ValueError(f"Invalid project name: {project}")
        if not all(c.isalnum() or c == '-' for c in project):
            raise ValueError(f"Project name must be alphanumeric + hyphens: {project}")
        index_dir = base_dir / "projects" / project
    else:
        index_dir = base_dir

    index_dir.mkdir(parents=True, exist_ok=True)
    return index_dir


def get_extracted_dir(project: str = None) -> Path:
    """Get the directory for extracted document text."""
    extracted_dir = get_index_dir(project) / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    return extracted_dir


# Import ignore handler for gitignore support
try:
    from ignore_handler import get_ignore_handler, IgnoreHandler
    HAS_IGNORE_HANDLER = True
except ImportError:
    HAS_IGNORE_HANDLER = False
    get_ignore_handler = None  # type: ignore
    IgnoreHandler = None  # type: ignore

# Document extensions (for kreuzberg extraction - binary docs)
DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".odt", ".odp", ".ods", ".rtf", ".epub",
}

# Text-based docs (read directly)
TEXT_DOC_EXTENSIONS = {
    ".md", ".markdown", ".rst", ".txt", ".html", ".htm",
}


# =============================================================================
# Document Extraction
# =============================================================================

class DocumentExtractor:
    """Extract text from documents using Kreuzberg or direct reading."""

    # Text-based formats we can read directly (preserves formatting)
    TEXT_FORMATS = {".md", ".markdown", ".txt", ".rst", ".html", ".htm"}

    def __init__(self):
        # Kreuzberg is optional for text formats
        pass

    async def extract(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract text and structure from a document.

        Returns:
            Tuple of (full_text, list_of_sections)
        """
        try:
            suffix = path.suffix.lower()

            # For text-based formats, read directly to preserve formatting
            if suffix in self.TEXT_FORMATS:
                text = path.read_text(encoding='utf-8', errors='replace')
            elif HAS_KREUZBERG:
                # Use Kreuzberg for binary formats (PDF, Word, etc.)
                result = await kreuzberg.extract_file(str(path))
                text = result.content if hasattr(result, 'content') else str(result)
            else:
                print(f"Warning: kreuzberg not installed, skipping binary file {path}", file=sys.stderr)
                return "", []

            # Parse sections from the text (headings, paragraphs)
            sections = self._parse_sections(text, str(path))

            return text, sections

        except Exception as e:
            print(f"Warning: Failed to extract {path}: {e}", file=sys.stderr)
            return "", []

    def _parse_sections(self, text: str, file_path: str) -> List[Dict[str, Any]]:
        """Parse text into sections based on headings."""
        sections = []
        lines = text.split('\n')

        current_section = None
        current_content = []
        line_start = 0

        # Simple heading detection (markdown-style or ALL CAPS)
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$|^([A-Z][A-Z0-9\s]{5,})$')

        for i, line in enumerate(lines):
            match = heading_pattern.match(line.strip())
            if match:
                # Save previous section
                if current_section:
                    sections.append({
                        "name": current_section,
                        "content": '\n'.join(current_content).strip(),
                        "line_start": line_start,
                        "line_end": i - 1,
                        "type": "doc_section"
                    })

                # Start new section
                if match.group(1):  # Markdown heading
                    level = len(match.group(1))
                    current_section = match.group(2).strip()
                else:  # ALL CAPS heading
                    current_section = match.group(3).strip()

                current_content = []
                line_start = i
            else:
                current_content.append(line)

        # Save final section
        if current_section:
            sections.append({
                "name": current_section,
                "content": '\n'.join(current_content).strip(),
                "line_start": line_start,
                "line_end": len(lines) - 1,
                "type": "doc_section"
            })
        elif current_content:
            # No headings found - treat whole doc as one section
            sections.append({
                "name": Path(file_path).stem,
                "content": '\n'.join(current_content).strip(),
                "line_start": 0,
                "line_end": len(lines) - 1,
                "type": "doc_page"
            })

        return sections


# =============================================================================
# Code Parsing (simplified - uses tree-sitter)
# =============================================================================

class CodeParser:
    """Parse code files to extract symbols using tree-sitter queries."""

    # Language detection by extension
    LANG_MAP = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".java": "java",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
        ".cs": "c_sharp", ".go": "go", ".rs": "rust", ".rb": "ruby",
        ".php": "php", ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
        ".sql": "sql", ".xml": "xml", ".html": "html", ".htm": "html",
        ".xhtml": "html", ".svg": "xml", ".xsd": "xml", ".xsl": "xml",
        # Note: .jsp/.jspx use custom _parse_jsp() method, not tree-sitter
    }

    def __init__(self):
        if not HAS_TREESITTER:
            raise ImportError("tree-sitter is required for code parsing")
        self._parsers = {}
        self._query_loader = get_query_loader() if HAS_QUERIES else None

    def _get_parser(self, ext: str):
        """Get or create parser for extension."""
        if ext not in self._parsers:
            lang = self.LANG_MAP.get(ext)
            if lang:
                try:
                    self._parsers[ext] = get_parser(lang)
                except Exception:
                    return None
        return self._parsers.get(ext)

    def parse(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parse a code file to extract symbols.

        Returns:
            Tuple of (source_code, list_of_symbols)
        """
        ext = path.suffix.lower()
        lang = self.LANG_MAP.get(ext)
        parser = self._get_parser(ext)

        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"Warning: Failed to read {path}: {e}", file=sys.stderr)
            return "", []

        # Special handling for JSP files - extract JSP-specific constructs
        if ext in ('.jsp', '.jspx'):
            return content, self._parse_jsp(content, str(path))

        if not parser:
            # Fallback: extract basic patterns via regex
            return content, self._regex_extract(content, str(path))

        try:
            tree = parser.parse(content.encode())

            # Try query-based extraction first (more precise)
            if self._query_loader and lang and self._query_loader.has_query(lang):
                symbols = self._extract_with_query(tree, content, lang, str(path))
                if symbols:
                    return content, symbols

            # Fall back to AST walking
            symbols = self._extract_symbols(tree.root_node, content, str(path))
            return content, symbols
        except Exception as e:
            print(f"Warning: Failed to parse {path}: {e}", file=sys.stderr)
            return content, self._regex_extract(content, str(path))

    def _extract_with_query(self, tree, content: str, language: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract symbols using tree-sitter queries (more precise than AST walking)."""
        if not self._query_loader or not ts:
            return []

        query_text = self._query_loader.load_query(language)
        if not query_text:
            return []

        try:
            ts_language = get_language(language)
            query = ts.Query(ts_language, query_text)
            cursor = ts.QueryCursor(query)
            matches = cursor.matches(tree.root_node)

            content_bytes = content.encode('utf-8')
            symbols = []
            seen_nodes = set()

            # Track name captures and calls for later association
            name_captures = {}  # (start, end) -> name
            calls_by_container: Dict[tuple, List[Dict[str, Any]]] = {}
            class_bases: Dict[tuple, List[str]] = {}

            # Convert matches to list for multiple passes
            matches_list = list(matches)

            # First pass: collect names, calls, and bases
            for _pattern_idx, captures_dict in matches_list:
                for capture_name, nodes in captures_dict.items():
                    # Collect name captures (.name for symbols, .module for imports)
                    if '.name' in capture_name or capture_name == 'import.module':
                        for node in nodes:
                            name_text = content_bytes[node.start_byte:node.end_byte].decode('utf-8')
                            # Store for parent nodes
                            current = node.parent
                            for _ in range(3):
                                if current:
                                    pos_key = (current.start_byte, current.end_byte)
                                    if pos_key not in name_captures:
                                        name_captures[pos_key] = name_text
                                    current = current.parent
                                else:
                                    break

                    # Collect calls - match any capture with 'call' in it
                    # Query captures may be: call, call.function, call.method, call.object, etc.
                    if capture_name.startswith('call'):
                        # Only process the main call capture or method capture
                        if capture_name in ('call', 'call.method', 'call.function'):
                            for node in nodes:
                                call_info = self._extract_call_from_node(node, content_bytes, capture_name)
                                if call_info:
                                    container_key = self._find_container_key(node)
                                    if container_key not in calls_by_container:
                                        calls_by_container[container_key] = []
                                    calls_by_container[container_key].append(call_info)

                    # Collect class bases (handles .base, .bases, .extends, .implements)
                    if any(x in capture_name for x in ['.base', '.bases', '.extends', '.implements']):
                        for node in nodes:
                            base_name = content_bytes[node.start_byte:node.end_byte].decode('utf-8').strip()
                            if base_name:
                                # Walk up to find the class definition node
                                class_node = node.parent
                                while class_node and class_node.type not in ('class_definition', 'class_declaration'):
                                    class_node = class_node.parent
                                if class_node:
                                    class_key = (class_node.start_byte, class_node.end_byte)
                                    if class_key not in class_bases:
                                        class_bases[class_key] = []
                                    if base_name not in class_bases[class_key]:
                                        class_bases[class_key].append(base_name)

            # Second pass: extract definitions
            for _pattern_idx, captures_dict in matches_list:
                for capture_name, nodes in captures_dict.items():
                    # Only process definition captures
                    if not ('.def' in capture_name or capture_name in ['import', 'import.from']):
                        continue

                    for node in nodes:
                        node_key = (node.start_byte, node.end_byte)
                        if node_key in seen_nodes:
                            continue
                        seen_nodes.add(node_key)

                        # Get name from captures
                        name = name_captures.get(node_key)
                        if not name:
                            # Try extracting from node
                            name = self._get_symbol_name(node, content)

                        # Determine element type from capture name
                        elem_type = self._get_element_type_from_capture(capture_name)
                        if not elem_type or not name:
                            continue

                        sym = {
                            "name": name,
                            "type": elem_type,
                            "line_start": node.start_point[0] + 1,
                            "line_end": node.end_point[0] + 1,
                        }

                        # Add calls (deduplicated by name)
                        if node_key in calls_by_container:
                            seen_calls = set()
                            unique_calls = []
                            for c in calls_by_container[node_key]:
                                if c['name'] not in seen_calls:
                                    seen_calls.add(c['name'])
                                    unique_calls.append(c)
                            sym["calls"] = unique_calls

                        # Add bases for classes
                        if node_key in class_bases:
                            sym["bases"] = class_bases[node_key]

                        # Handle imports specially
                        if elem_type == "import":
                            sym["module_path"] = name
                            # Extract imported names if this is a from-import
                            if capture_name == 'import.from':
                                imported = self._extract_import_names(node, content_bytes)
                                if imported:
                                    sym["imported_names"] = imported
                            elif name and '.' in name:
                                # For Java-style imports (import x.y.Z): last component is the imported name
                                imported_name = name.rsplit('.', 1)[-1]
                                if imported_name and imported_name != '*':
                                    sym["imported_names"] = [imported_name]

                        symbols.append(sym)

            return sorted(symbols, key=lambda x: x.get("line_start", 0))

        except Exception as e:
            print(f"Warning: Query extraction failed for {language}: {e}", file=sys.stderr)
            return []

    def _get_element_type_from_capture(self, capture_name: str) -> Optional[str]:
        """Map capture name to element type."""
        if 'import' in capture_name:
            return "import"
        if 'code_function' in capture_name:
            return "function"
        if 'code_method' in capture_name:
            return "method"
        if 'code_class' in capture_name:
            return "class"
        if 'code_interface' in capture_name:
            return "interface"
        if 'code_struct' in capture_name:
            return "struct"
        if 'code_enum' in capture_name:
            return "enum"
        if 'code_type' in capture_name:
            return "type"
        if 'code_trait' in capture_name:
            return "trait"
        return None

    def _extract_call_from_node(self, node, content_bytes: bytes, capture_name: str) -> Optional[Dict[str, Any]]:
        """Extract call info from a call node.

        Handles different capture types:
        - 'call': The full (call ...) node - need to extract function name from children
        - 'call.function': The identifier node containing function name
        - 'call.method': The full call node for method calls
        """
        try:
            line = content_bytes[:node.start_byte].count(b'\n') + 1

            if capture_name == 'call.function':
                # The node IS the function identifier
                name = content_bytes[node.start_byte:node.end_byte].decode('utf-8')
                return {"name": name, "type": "function", "line": line}

            elif capture_name == 'call.method':
                # Method call - find object and method from the call node
                for child in node.children:
                    if child.type in ('attribute', 'member_expression', 'selector_expression', 'field_expression'):
                        method_name = None
                        obj_name = None
                        for sub in child.children:
                            if sub.type in ('identifier', 'property_identifier', 'field_identifier'):
                                # Last identifier is usually the method name
                                method_name = content_bytes[sub.start_byte:sub.end_byte].decode('utf-8')
                            elif sub.type == 'identifier' and obj_name is None:
                                obj_name = content_bytes[sub.start_byte:sub.end_byte].decode('utf-8')
                        if method_name:
                            return {"name": method_name, "object": obj_name or "", "type": "method", "line": line}
                # Fallback: try to get method name from attribute node
                text = content_bytes[node.start_byte:node.end_byte].decode('utf-8')
                if '.' in text:
                    method_name = text.split('(')[0].split('.')[-1]
                    return {"name": method_name, "type": "method", "line": line}

            else:  # capture_name == 'call'
                # Full call node - extract function name from children
                for child in node.children:
                    if child.type == 'identifier':
                        name = content_bytes[child.start_byte:child.end_byte].decode('utf-8')
                        return {"name": name, "type": "function", "line": line}
                    elif child.type in ('attribute', 'member_expression'):
                        # Method call pattern
                        method_name = None
                        for sub in child.children:
                            if sub.type in ('identifier', 'property_identifier'):
                                method_name = content_bytes[sub.start_byte:sub.end_byte].decode('utf-8')
                        if method_name:
                            return {"name": method_name, "type": "method", "line": line}
            return None
        except Exception:
            return None

    def _extract_bases_from_node(self, node, content_bytes: bytes) -> List[str]:
        """Extract base class names from a bases/superclasses node."""
        bases = []
        try:
            for child in node.children:
                if child.type in ('identifier', 'type_identifier'):
                    bases.append(content_bytes[child.start_byte:child.end_byte].decode('utf-8'))
                elif child.type == 'attribute':
                    bases.append(content_bytes[child.start_byte:child.end_byte].decode('utf-8'))
        except Exception:
            pass
        return bases

    def _extract_import_names(self, node, content_bytes: bytes) -> List[str]:
        """Extract imported symbol names from an import node."""
        names = []
        try:
            text = content_bytes[node.start_byte:node.end_byte].decode('utf-8')
            # Python: from X import Y, Z
            from_match = re.search(r'import\s+(.+)', text)
            if from_match:
                imported = from_match.group(1)
                for name in re.findall(r'(\w+)(?:\s+as\s+\w+)?', imported):
                    names.append(name)
        except Exception:
            pass
        return names

    def _find_container_key(self, node) -> tuple:
        """Find containing function/class for a node."""
        current = node.parent
        while current:
            if current.type in ('function_definition', 'class_definition', 'method_definition',
                               'function_declaration', 'class_declaration', 'method_declaration'):
                return (current.start_byte, current.end_byte)
            current = current.parent
        return (0, 0)

    def _extract_symbols(self, node, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract symbols from AST with relationships (calls, inheritance, defines)."""
        symbols = []
        source_bytes = source.encode('utf-8')

        # Common symbol types across languages
        symbol_types = {
            'function_definition': 'function',
            'function_declaration': 'function',
            'method_definition': 'method',
            'class_definition': 'class',
            'class_declaration': 'class',
            'interface_declaration': 'interface',
            'struct_definition': 'struct',
            'enum_definition': 'enum',
        }

        # Import statement types
        import_types = {
            'import_statement',          # Python: import foo
            'import_from_statement',     # Python: from foo import bar
            'import_declaration',        # JS/TS: import x from 'y'
            'use_declaration',           # Rust: use std::io
            'using_directive',           # C#: using System
        }

        # Call types
        call_types = {'call', 'call_expression'}

        # Track calls by containing function/class
        calls_by_container: Dict[tuple, List[Dict[str, Any]]] = {}
        # Track class bases for inheritance
        class_bases: Dict[tuple, List[str]] = {}

        def get_container_key(n) -> tuple:
            """Find containing function/class for a node."""
            current = n.parent
            while current:
                if current.type in ('function_definition', 'class_definition', 'method_definition'):
                    return (current.start_byte, current.end_byte)
                current = current.parent
            return (0, 0)  # Module level

        def extract_call_info(n) -> Optional[Dict[str, Any]]:
            """Extract function/method call information."""
            try:
                # Get function being called
                func_node = n.child_by_field_name('function')
                if not func_node:
                    for child in n.children:
                        if child.type in ('identifier', 'attribute'):
                            func_node = child
                            break
                if not func_node:
                    return None

                if func_node.type == 'identifier':
                    # Simple call: foo()
                    call_name = source_bytes[func_node.start_byte:func_node.end_byte].decode('utf-8')
                    return {"name": call_name, "type": "function", "line": n.start_point[0] + 1}
                elif func_node.type == 'attribute':
                    # Method call: obj.method()
                    obj_node = func_node.child_by_field_name('object')
                    attr_node = func_node.child_by_field_name('attribute')
                    if attr_node:
                        method_name = source_bytes[attr_node.start_byte:attr_node.end_byte].decode('utf-8')
                        obj_name = source_bytes[obj_node.start_byte:obj_node.end_byte].decode('utf-8') if obj_node else ""
                        return {"name": method_name, "object": obj_name, "type": "method", "line": n.start_point[0] + 1}
                return None
            except Exception:
                return None

        def extract_class_bases(n) -> List[str]:
            """Extract base classes from class definition."""
            bases = []
            # Look for superclasses/argument_list
            for child in n.children:
                if child.type in ('argument_list', 'superclasses'):
                    for base_child in child.children:
                        if base_child.type == 'identifier':
                            bases.append(source_bytes[base_child.start_byte:base_child.end_byte].decode('utf-8'))
                        elif base_child.type == 'attribute':
                            bases.append(source_bytes[base_child.start_byte:base_child.end_byte].decode('utf-8'))
            return bases

        def walk(n):
            node_key = (n.start_byte, n.end_byte)

            if n.type in symbol_types:
                name = self._get_symbol_name(n, source)
                if name:
                    sym = {
                        "name": name,
                        "type": symbol_types[n.type],
                        "line_start": n.start_point[0] + 1,
                        "line_end": n.end_point[0] + 1,
                    }
                    # Add calls made by this symbol (deduplicated)
                    if node_key in calls_by_container:
                        seen_calls = set()
                        unique_calls = []
                        for c in calls_by_container[node_key]:
                            if c['name'] not in seen_calls:
                                seen_calls.add(c['name'])
                                unique_calls.append(c)
                        sym["calls"] = unique_calls
                    # Add base classes for class definitions
                    if n.type in ('class_definition', 'class_declaration'):
                        bases = extract_class_bases(n)
                        if bases:
                            sym["bases"] = bases
                    symbols.append(sym)

            # Handle imports
            elif n.type in import_types:
                import_info = self._extract_import(n, source)
                if import_info:
                    symbols.append({
                        "name": import_info['module'],
                        "type": "import",
                        "line_start": n.start_point[0] + 1,
                        "line_end": n.end_point[0] + 1,
                        "imported_names": import_info.get('names', []),
                        "module_path": import_info['module'],  # Full module path for resolution
                    })

            # Handle calls (collect for later association with containers)
            elif n.type in call_types:
                call_info = extract_call_info(n)
                if call_info:
                    container_key = get_container_key(n)
                    if container_key not in calls_by_container:
                        calls_by_container[container_key] = []
                    calls_by_container[container_key].append(call_info)

            for child in n.children:
                walk(child)

        # First pass: collect calls
        def collect_calls(n):
            if n.type in call_types:
                call_info = extract_call_info(n)
                if call_info:
                    container_key = get_container_key(n)
                    if container_key not in calls_by_container:
                        calls_by_container[container_key] = []
                    calls_by_container[container_key].append(call_info)
            for child in n.children:
                collect_calls(child)

        collect_calls(node)

        # Second pass: extract symbols with calls attached
        def extract(n):
            node_key = (n.start_byte, n.end_byte)

            if n.type in symbol_types:
                name = self._get_symbol_name(n, source)
                if name:
                    sym = {
                        "name": name,
                        "type": symbol_types[n.type],
                        "line_start": n.start_point[0] + 1,
                        "line_end": n.end_point[0] + 1,
                    }
                    # Add calls made by this symbol (deduplicated)
                    if node_key in calls_by_container:
                        seen_calls = set()
                        unique_calls = []
                        for c in calls_by_container[node_key]:
                            if c['name'] not in seen_calls:
                                seen_calls.add(c['name'])
                                unique_calls.append(c)
                        sym["calls"] = unique_calls
                    # Add base classes for class definitions
                    if n.type in ('class_definition', 'class_declaration'):
                        bases = extract_class_bases(n)
                        if bases:
                            sym["bases"] = bases
                    symbols.append(sym)

            elif n.type in import_types:
                import_info = self._extract_import(n, source)
                if import_info:
                    symbols.append({
                        "name": import_info['module'],
                        "type": "import",
                        "line_start": n.start_point[0] + 1,
                        "line_end": n.end_point[0] + 1,
                        "imported_names": import_info.get('names', []),
                        "module_path": import_info['module'],
                    })

            for child in n.children:
                extract(child)

        extract(node)
        return symbols

    def _extract_import(self, node, source: str) -> Optional[Dict[str, Any]]:
        """Extract import details from an import AST node."""
        text = source[node.start_byte:node.end_byte]

        # Python: from X import Y or import X
        if 'from' in text or 'import' in text:
            # from module import name1, name2
            from_match = re.match(r'from\s+([\w.]+)\s+import\s+(.+)', text)
            if from_match:
                module = from_match.group(1)
                names = [n.strip().split(' as ')[0] for n in from_match.group(2).split(',')]
                return {"module": module, "names": names}

            # import module or import module as alias
            import_match = re.match(r'import\s+([\w.]+)', text)
            if import_match:
                return {"module": import_match.group(1), "names": []}

        return None

    def _get_symbol_name(self, node, source: str) -> Optional[str]:
        """Extract symbol name from AST node."""
        # Try to find 'name' or 'identifier' child
        for child in node.children:
            if child.type in ('name', 'identifier', 'property_identifier'):
                return source[child.start_byte:child.end_byte]
        return None

    def _regex_extract(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback regex-based symbol extraction."""
        symbols = []
        lines = content.split('\n')

        # Common patterns
        patterns = [
            (r'^(?:def|function|func)\s+(\w+)', 'function'),
            (r'^class\s+(\w+)', 'class'),
            (r'^interface\s+(\w+)', 'interface'),
            (r'^struct\s+(\w+)', 'struct'),
        ]

        # Import patterns
        import_patterns = [
            # Python: from X import Y, Z
            (r'^from\s+([\w.]+)\s+import\s+(.+)', lambda m: {
                "name": m.group(1),
                "type": "import",
                "imported_names": [n.strip().split(' as ')[0] for n in m.group(2).split(',')],
            }),
            # Python: import X
            (r'^import\s+([\w.]+)', lambda m: {
                "name": m.group(1),
                "type": "import",
                "imported_names": [],
            }),
            # JS/TS: import { X } from 'Y'
            (r'^import\s+\{([^}]+)\}\s+from\s+[\'"]([^\'"]+)[\'"]', lambda m: {
                "name": m.group(2),
                "type": "import",
                "imported_names": [n.strip().split(' as ')[0] for n in m.group(1).split(',')],
            }),
            # JS/TS: import X from 'Y'
            (r'^import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]', lambda m: {
                "name": m.group(2),
                "type": "import",
                "imported_names": [m.group(1)],
            }),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check symbol patterns
            for pattern, sym_type in patterns:
                match = re.match(pattern, stripped)
                if match:
                    symbols.append({
                        "name": match.group(1),
                        "type": sym_type,
                        "line_start": i + 1,
                        "line_end": i + 1,
                    })
                    break

            # Check import patterns
            for pattern, extractor in import_patterns:
                match = re.match(pattern, stripped)
                if match:
                    import_sym = extractor(match)
                    import_sym["line_start"] = i + 1
                    import_sym["line_end"] = i + 1
                    symbols.append(import_sym)
                    break

        return symbols

    def _parse_jsp(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse JSP files to extract JSP-specific constructs.

        Extracts:
        - Page directives (<%@ page ... %>)
        - Taglib directives (<%@ taglib ... %>)
        - Include directives (<%@ include ... %>)
        - JSP declarations (<%! ... %>)
        - JSP expressions (<%= ... %>)
        - JSP scriptlets (<% ... %>)
        - JSP standard actions (<jsp:...>)
        - Custom tags (<prefix:tagname>)
        - HTML elements with id/name attributes
        """
        symbols = []
        lines = content.split('\n')

        # Track line positions for multiline constructs
        def find_line(pos: int) -> int:
            """Find line number for byte position."""
            line_num = 1
            current_pos = 0
            for line in lines:
                if current_pos + len(line) >= pos:
                    return line_num
                current_pos += len(line) + 1  # +1 for newline
                line_num += 1
            return line_num

        # JSP Directive patterns: <%@ directive attr="value" %>
        directive_pattern = re.compile(
            r'<%@\s*(page|taglib|include|tag|attribute|variable)\s+([^%>]+)%>',
            re.IGNORECASE | re.DOTALL
        )
        for match in directive_pattern.finditer(content):
            directive_type = match.group(1).lower()
            attrs = match.group(2)
            line = find_line(match.start())

            # Extract key attributes
            name = directive_type
            if directive_type == 'taglib':
                # Extract prefix and uri
                prefix_match = re.search(r'prefix\s*=\s*["\']([^"\']+)["\']', attrs)
                uri_match = re.search(r'uri\s*=\s*["\']([^"\']+)["\']', attrs)
                if prefix_match:
                    name = f"taglib:{prefix_match.group(1)}"
            elif directive_type == 'include':
                file_match = re.search(r'file\s*=\s*["\']([^"\']+)["\']', attrs)
                if file_match:
                    name = f"include:{file_match.group(1)}"
            elif directive_type == 'page':
                # Extract import statements
                import_match = re.search(r'import\s*=\s*["\']([^"\']+)["\']', attrs)
                if import_match:
                    for imp in import_match.group(1).split(','):
                        symbols.append({
                            "name": imp.strip(),
                            "type": "import",
                            "line_start": line,
                            "line_end": line,
                        })

            symbols.append({
                "name": name,
                "type": "directive",
                "line_start": line,
                "line_end": line,
            })

        # JSP Declarations: <%! ... %> - class-level code
        decl_pattern = re.compile(r'<%!\s*(.*?)\s*%>', re.DOTALL)
        for match in decl_pattern.finditer(content):
            code = match.group(1)
            line = find_line(match.start())

            # Extract method/variable declarations from Java code
            # Method pattern
            method_pattern = re.compile(
                r'(?:public|private|protected)?\s*(?:static\s+)?'
                r'(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
            )
            for m in method_pattern.finditer(code):
                symbols.append({
                    "name": m.group(1),
                    "type": "method",
                    "line_start": line,
                    "line_end": line,
                })

            # Variable pattern
            var_pattern = re.compile(
                r'(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?'
                r'(\w+(?:<[^>]+>)?)\s+(\w+)\s*[=;]'
            )
            for m in var_pattern.finditer(code):
                symbols.append({
                    "name": m.group(2),
                    "type": "variable",
                    "line_start": line,
                    "line_end": line,
                })

        # JSP Standard Actions: <jsp:useBean>, <jsp:include>, etc.
        jsp_action_pattern = re.compile(
            r'<jsp:(\w+)\s+([^>]*)(?:/>|>)',
            re.IGNORECASE
        )
        for match in jsp_action_pattern.finditer(content):
            action = match.group(1).lower()
            attrs = match.group(2)
            line = find_line(match.start())

            name = f"jsp:{action}"
            # Extract id for useBean
            if action == 'usebean':
                id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs)
                if id_match:
                    name = id_match.group(1)
                    symbols.append({
                        "name": name,
                        "type": "bean",
                        "line_start": line,
                        "line_end": line,
                    })
                    continue

            symbols.append({
                "name": name,
                "type": "action",
                "line_start": line,
                "line_end": line,
            })

        # Custom tag usage: <prefix:tagname ...>
        # Skip jsp: prefix (already handled) and html tags
        custom_tag_pattern = re.compile(
            r'<(\w+):(\w+)\s*([^>]*)(?:/>|>)',
            re.IGNORECASE
        )
        for match in custom_tag_pattern.finditer(content):
            prefix = match.group(1).lower()
            tagname = match.group(2)
            line = find_line(match.start())

            if prefix not in ('jsp', 'html', 'head', 'body', 'meta'):
                symbols.append({
                    "name": f"{prefix}:{tagname}",
                    "type": "tag",
                    "line_start": line,
                    "line_end": line,
                })

        # HTML elements with id attribute (for navigation/reference)
        id_pattern = re.compile(
            r'<(\w+)[^>]*\s+id\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        for match in id_pattern.finditer(content):
            element = match.group(1)
            element_id = match.group(2)
            line = find_line(match.start())

            symbols.append({
                "name": element_id,
                "type": "element",
                "line_start": line,
                "line_end": line,
            })

        # Form elements with name attribute
        name_pattern = re.compile(
            r'<(input|select|textarea|button|form)[^>]*\s+name\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        for match in name_pattern.finditer(content):
            element = match.group(1)
            element_name = match.group(2)
            line = find_line(match.start())

            symbols.append({
                "name": element_name,
                "type": "form_field",
                "line_start": line,
                "line_end": line,
            })

        return symbols


# =============================================================================
# Main Index Class
# =============================================================================

class UnifiedSearchIndex:
    """Main class managing the unified code + doc index (JSONL-only)."""

    def __init__(self, root_path: Path, project: str = None):
        self.root_path = root_path.resolve()
        self.project = project
        self._index_metadata: Optional[IndexMetadata] = None

        self.doc_extractor = DocumentExtractor() if HAS_KREUZBERG else None
        self.code_parser = CodeParser() if HAS_TREESITTER else None

    def _path_hash(self) -> str:
        """Generate hash for index filename."""
        return hashlib.md5(str(self.root_path).encode()).hexdigest()[:12]

    def _load_index_metadata(self) -> Optional[IndexMetadata]:
        """Load index metadata from disk."""
        if self._index_metadata is not None:
            return self._index_metadata

        meta_path = self._get_metadata_path()
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                self._index_metadata = IndexMetadata.model_validate_json(f.read())
            return self._index_metadata
        except Exception:
            return None

    def _is_stale(self, path: Path) -> bool:
        """Check if file has changed since indexed."""
        metadata = self._load_index_metadata()
        if metadata is None:
            return True

        path_str = str(path)
        if path_str not in metadata.files:
            return True

        file_meta = metadata.files[path_str]
        try:
            stat = path.stat()
            return stat.st_mtime != file_meta.mtime or stat.st_size != file_meta.size
        except FileNotFoundError:
            return True

    def _get_ignore_handler(self) -> Optional[Any]:
        """Get ignore handler for gitignore-aware file filtering."""
        if HAS_IGNORE_HANDLER and get_ignore_handler:
            return get_ignore_handler(str(self.root_path))
        return None

    def _find_files(self) -> Tuple[List[Path], List[Path]]:
        """Find all indexable files with smart classification.

        - Uses ignore_handler for gitignore filtering (hierarchical)
        - Classifies by extension (doc vs code)
        - Unknown extensions go to code (tree-sitter will try, then text fallback)
        """
        code_files = []
        doc_files = []
        ignore_handler = self._get_ignore_handler()

        # Single pass through all files
        for f in self.root_path.rglob("*"):
            if not f.is_file():
                continue

            # Use ignore handler if available
            if ignore_handler and ignore_handler.is_ignored(str(f)):
                continue

            ext = f.suffix.lower()

            # Classify: doc extensions go to doc, everything else to code
            if ext in DOC_EXTENSIONS or ext in TEXT_DOC_EXTENSIONS:
                doc_files.append(f)
            else:
                # Try to parse as code - tree-sitter will handle or skip
                code_files.append(f)

        return code_files, doc_files

    # =========================================================================
    # JSONL-based indexing (parallel, streaming)
    # =========================================================================

    def _get_jsonl_index_path(self) -> Path:
        """Get path for JSONL index file."""
        return get_index_dir(self.project) / f"{self._path_hash()}.jsonl"

    def _get_metadata_path(self) -> Path:
        """Get path for index metadata file."""
        return get_index_dir(self.project) / f"{self._path_hash()}_meta.json"

    def _parse_file_to_nodes(self, path: Path) -> List["JsonlGraphNode"]:
        """Parse a single file into JSONL GraphNode objects.

        Tries tree-sitter parsing first, falls back to regex extraction.
        Always creates at least a file node for indexable files.
        """
        if not HAS_JSONL_MODULES:
            return []

        file_str = str(path)
        nodes = []
        content = ""
        symbols = []

        # Try to read and parse the file
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            # Can't read file at all - skip it
            return []

        # Try code parsing if available
        if self.code_parser:
            try:
                content, symbols = self.code_parser.parse(path)
            except Exception:
                # Parser failed - continue with just the file node
                pass

        # Always add a file node (even if no symbols extracted)
        file_node = JsonlGraphNode(
            id=file_str,
            name=path.name,
            node_type=NodeType.FILE,
            file=file_str,
            line_start=1,
            line_end=content.count('\n') + 1 if content else 1,
            domain="code",
        )
        nodes.append(file_node)

        # Add symbol nodes
        for sym in symbols:
            sym_type = sym.get('type', 'function')
            if sym_type == 'import':
                node_type = NodeType.IMPORT
            elif sym_type == 'class':
                node_type = NodeType.CLASS
            elif sym_type == 'method':
                node_type = NodeType.METHOD
            elif sym_type == 'interface':
                node_type = NodeType.INTERFACE
            elif sym_type == 'struct':
                node_type = NodeType.STRUCT
            elif sym_type == 'enum':
                node_type = NodeType.ENUM
            else:
                node_type = NodeType.FUNCTION

            node_id = f"{file_str}::{sym['name']}"

            # Convert calls to CallRef objects
            calls = []
            for call_info in sym.get('calls', []):
                calls.append(CallRef(
                    name=call_info.get('name', ''),
                    line=call_info.get('line', 0),
                    call_type=call_info.get('type', 'function'),
                    object_name=call_info.get('object'),
                ))

            node = JsonlGraphNode(
                id=node_id,
                name=sym['name'],
                node_type=node_type,
                file=file_str,
                line_start=sym.get('line_start', 0),
                line_end=sym.get('line_end', 0),
                calls=calls,
                bases=sym.get('bases', []),
                imports=sym.get('imported_names', []) if sym_type == 'import' else [],
                imported_names=sym.get('imported_names', []),
                domain="code",
            )
            nodes.append(node)

        return nodes

    def _parse_doc_to_nodes(self, path: Path) -> List["JsonlGraphNode"]:
        """Parse a document file into JSONL GraphNode objects.

        For text-based docs (md, txt, rst), reads directly.
        For binary docs (pdf, docx), uses kreuzberg if available.
        """
        if not HAS_JSONL_MODULES:
            return []

        file_str = str(path)
        ext = path.suffix.lower()
        text = ""
        sections = []

        try:
            # Text-based docs - read directly
            if ext in TEXT_DOC_EXTENSIONS:
                text = path.read_text(encoding='utf-8', errors='replace')
                # Parse sections from markdown/text
                if self.doc_extractor:
                    sections = self.doc_extractor._parse_sections(text, file_str)
            # Binary docs - use kreuzberg if available
            elif ext in DOC_EXTENSIONS and self.doc_extractor and HAS_KREUZBERG:
                import asyncio
                text, sections = asyncio.run(self.doc_extractor.extract(path))
            else:
                # Try reading as text anyway
                try:
                    text = path.read_text(encoding='utf-8', errors='replace')
                    if self.doc_extractor:
                        sections = self.doc_extractor._parse_sections(text, file_str)
                except Exception:
                    return []
        except Exception as e:
            print(f"Warning: Failed to parse doc {path}: {e}", file=sys.stderr)
            return []

        if not text:
            return []

        file_str = str(path)
        nodes = []

        # Add file node
        file_node = JsonlGraphNode(
            id=file_str,
            name=path.name,
            node_type=NodeType.FILE,
            file=file_str,
            line_start=1,
            line_end=text.count('\n') + 1,
            domain="doc",
        )
        nodes.append(file_node)

        # Add section nodes
        for section in sections:
            section_type = section.get('type', 'doc_section')
            if section_type == 'doc_page':
                node_type = NodeType.DOC_PAGE
            else:
                node_type = NodeType.DOC_SECTION

            node_id = f"{file_str}::{section['name']}"

            node = JsonlGraphNode(
                id=node_id,
                name=section['name'],
                node_type=node_type,
                file=file_str,
                line_start=section.get('line_start', 0),
                line_end=section.get('line_end', 0),
                domain="doc",
                content=section.get('content', ''),
            )
            nodes.append(node)

        return nodes

    async def build_index_jsonl(self, force: bool = False) -> Dict[str, Any]:
        """Build index using JSONL format with parallel processing.

        This is the new, faster indexing path that:
        1. Parses files in parallel using a thread pool
        2. Streams nodes to JSONL as they complete
        3. Runs a linking pass to resolve cross-references
        """
        if not HAS_JSONL_MODULES:
            raise RuntimeError("JSONL modules not available")

        jsonl_path = self._get_jsonl_index_path()
        meta_path = self._get_metadata_path()

        code_files, doc_files = self._find_files()

        stats = {
            "code_files": 0,
            "doc_files": 0,
            "code_symbols": 0,
            "doc_sections": 0,
            "cross_refs": 0,
            "skipped": 0,
            "failed": 0,
            "parallel": True,
        }

        jsonl_path = self._get_jsonl_index_path()
        meta_path = self._get_metadata_path()

        # Check for stale files (unless force)
        if not force:
            stale_files = [f for f in code_files if self._is_stale(f)]
            stale_docs = [f for f in doc_files if self._is_stale(f)] if doc_files else []
            if not stale_files and not stale_docs and jsonl_path.exists():
                # Nothing changed — return existing stats
                existing_metadata = self._load_index_metadata()
                if existing_metadata:
                    stats["code_files"] = existing_metadata.file_count
                    stats["code_symbols"] = existing_metadata.node_count
                    stats["cross_refs"] = existing_metadata.edge_count
                    stats["skipped"] = len(code_files)
                    return stats
            # Some files changed — re-index all files to maintain JSONL consistency
            stats["skipped"] = 0

        # Pass 1a: Parallel code extraction
        if code_files:
            def progress(done, total):
                if done % 100 == 0 or done == total:
                    print(f"  Indexed {done}/{total} code files...", file=sys.stderr)

            indexer = ParallelIndexer(self._parse_file_to_nodes)
            node_count = indexer.index_files(code_files, jsonl_path, progress)
            stats["code_symbols"] = node_count
            stats["code_files"] = len(code_files)

        # Pass 1b: Document extraction (append to JSONL)
        if doc_files and self.doc_extractor:
            print(f"  Processing {len(doc_files)} documents...", file=sys.stderr)
            doc_node_count = 0

            # Append mode - open existing JSONL and add doc nodes
            with open(jsonl_path, 'a', encoding='utf-8') as f:
                for i, path in enumerate(doc_files):
                    try:
                        nodes = self._parse_doc_to_nodes(path)
                        for node in nodes:
                            f.write(node.model_dump_json(by_alias=True) + '\n')
                            doc_node_count += 1
                    except Exception as e:
                        print(f"Warning: Failed to index doc {path}: {e}", file=sys.stderr)
                        stats["failed"] += 1

                    if (i + 1) % 10 == 0 or i + 1 == len(doc_files):
                        print(f"  Indexed {i + 1}/{len(doc_files)} docs...", file=sys.stderr)

            stats["doc_files"] = len(doc_files)
            stats["doc_sections"] = doc_node_count

        # Pass 2: Link dependencies
        if jsonl_path.exists():
            linker = DependencyLinker()
            stats["cross_refs"] = linker.link(jsonl_path)

        # Update metadata
        metadata = IndexMetadata.create(str(self.root_path))
        metadata.file_count = len(code_files)
        metadata.node_count = stats["code_symbols"]
        metadata.edge_count = stats["cross_refs"]

        # Save file metadata for staleness detection
        for path in code_files:
            try:
                stat = path.stat()
                from models import FileMetadata as JsonlFileMetadata
                metadata.files[str(path)] = JsonlFileMetadata(
                    path=str(path),
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    indexed_at=datetime.now(timezone.utc).isoformat(),
                    file_type="code",
                )
            except Exception:
                pass

        # Write metadata
        with open(meta_path, 'w') as f:
            f.write(metadata.model_dump_json(indent=2))

        return stats

    # =========================================================================
    # Symbol Graph Indexing (JSP/HTML/Entity support)
    # =========================================================================

    def _extract_docstring(self, file_path: str, line_start: int) -> Optional[str]:
        """
        Extract first docstring or comment from source file around symbol's line_start.

        Returns the first meaningful docstring/comment found, or None.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            # Look backward from line_start to find docstring
            # Python: triple quotes """..."""
            # Java/JS/TS: /** ... */ or // comments
            start_idx = max(0, line_start - 10)  # Look up to 10 lines back
            end_idx = min(len(lines), line_start + 3)  # Look up to 3 lines forward

            # Check for Python docstring
            for i in range(start_idx, end_idx):
                line = lines[i].strip()
                if line.startswith('"""') or line.startswith("'''"):
                    # Single-line docstring
                    if line.count('"""') >= 2 or line.count("'''") >= 2:
                        return line.strip('"\' ')
                    # Multi-line docstring
                    doc_lines = [line.strip('"\' ')]
                    for j in range(i + 1, min(len(lines), i + 20)):
                        next_line = lines[j].strip()
                        if next_line.endswith('"""') or next_line.endswith("'''"):
                            doc_lines.append(next_line.strip('"\' '))
                            break
                        doc_lines.append(next_line)
                    return ' '.join(doc_lines).strip()

            # Check for JavaDoc /** ... */
            for i in range(start_idx, end_idx):
                line = lines[i].strip()
                if line.startswith('/**'):
                    doc_lines = []
                    for j in range(i, min(len(lines), i + 20)):
                        doc_line = lines[j].strip()
                        # Remove comment markers
                        doc_line = doc_line.lstrip('/*').rstrip('*/').lstrip('*').strip()
                        if doc_line:
                            doc_lines.append(doc_line)
                        if '*/' in lines[j]:
                            break
                    return ' '.join(doc_lines).strip()

            # Check for single-line // comments
            for i in range(start_idx, line_start + 1):
                line = lines[i].strip()
                if line.startswith('//'):
                    return line.lstrip('/').strip()

        except Exception:
            pass

        return None

    def _infer_symbol_type(self, symbol: "Symbol") -> str:
        """
        Infer symbol type category using deterministic rules.

        Returns one of: test, configuration, data-model, controller, service, utility, general
        """
        path_lower = symbol.file_path.lower()
        name = symbol.name
        sym_type = symbol.type.value if hasattr(symbol.type, 'value') else str(symbol.type)

        # Test detection
        if ('test/' in path_lower or 'spec/' in path_lower or
            name.startswith('test_') or name.startswith('Test')):
            return "test"

        # Configuration detection
        if ('config/' in path_lower or 'Config' in name or 'Settings' in name):
            return "configuration"

        # Data model detection (class types in model/entity/schema dirs)
        if sym_type.lower() in ('class', 'entity', 'interface'):
            if any(x in path_lower for x in ['model/', 'entity/', 'schema/']):
                return "data-model"

        # Controller detection (class names ending with Controller/Handler/Router)
        if sym_type.lower() in ('class', 'controller'):
            if any(name.endswith(suffix) for suffix in ['Controller', 'Handler', 'Router']):
                return "controller"

        # Service detection (class names ending with Service/Manager/Provider)
        if sym_type.lower() in ('class', 'service'):
            if any(name.endswith(suffix) for suffix in ['Service', 'Manager', 'Provider']):
                return "service"

        # Utility detection
        if any(x in path_lower for x in ['util/', 'helper/', 'lib/']):
            return "utility"

        return "general"

    def _extract_domains(self, file_path: str) -> List[str]:
        """
        Extract domain tags from directory path.

        Returns list of domain keywords found in path (auth, api, db, cache, etc.)
        """
        # Domain keywords to match
        domain_keywords = {
            'auth', 'api', 'db', 'database', 'cache', 'queue', 'email',
            'payment', 'user', 'admin', 'search', 'config', 'notification',
            'billing', 'analytics', 'report', 'export', 'import'
        }

        # Skip generic directory names
        skip_dirs = {'src', 'lib', 'main', 'java', 'python', 'scripts', 'test', 'tests'}

        # Extract path components
        path = Path(file_path)
        parts = [p.lower() for p in path.parts]

        domains = []
        for part in parts:
            # Check for exact match
            if part in domain_keywords:
                domains.append(part)
            # Check for substring match (e.g., 'authentication' contains 'auth')
            elif not part in skip_dirs:
                for keyword in domain_keywords:
                    if keyword in part and part not in skip_dirs:
                        domains.append(keyword)
                        break

        return list(set(domains))  # Remove duplicates

    def _enrich_symbol(self, symbol: "Symbol") -> "Symbol":
        """
        Add enrichment fields to a symbol: inferred_type, description, domains.

        Args:
            symbol: Symbol instance from adapter parsing

        Returns:
            Symbol with enrichment fields populated
        """
        # Infer type category
        symbol.inferred_type = self._infer_symbol_type(symbol)

        # Extract description from source
        if symbol.file_path and symbol.line_start:
            symbol.description = self._extract_docstring(symbol.file_path, symbol.line_start)

        # Extract domain tags from path
        if symbol.file_path:
            symbol.domains = self._extract_domains(symbol.file_path)

        return symbol

    def build_symbol_graph(self, resolve: bool = True) -> Optional["SymbolGraph"]:
        """
        Build a Symbol Graph from Java, JSP, HTML, and code files.

        This uses the new specialized parsers for enhanced extraction:
        - Java: Entities, Controllers, Services (via tree-sitter with annotations)
        - JSP: EL expressions, Spring forms, JSTL, includes
        - HTML: React, Vue, Angular components and bindings

        Args:
            resolve: Run linkers to resolve cross-references

        Returns:
            SymbolGraph instance or None if modules unavailable
        """
        if not HAS_SYMBOL_GRAPH:
            print("Error: Symbol Graph modules not available", file=sys.stderr)
            return None

        graph = SymbolGraph()

        # Find files
        code_files, doc_files = self._find_files()

        # Track stats per adapter
        stats = {"symbols": 0, "errors": 0, "files_by_adapter": {}}

        print(f"Building Symbol Graph for {len(code_files)} files...", file=sys.stderr)

        for path in code_files:
            try:
                content = path.read_text(encoding='utf-8', errors='replace')
                file_path = str(path)
                symbols = []

                # Use adapter registry for all parsing
                if HAS_ADAPTERS and AdapterRegistry:
                    adapter = AdapterRegistry.get_adapter(file_path, self.code_parser)
                    if adapter:
                        symbols = adapter.parse(content, file_path)
                        # Track files per adapter
                        adapter_name = adapter.name
                        stats["files_by_adapter"][adapter_name] = \
                            stats["files_by_adapter"].get(adapter_name, 0) + 1

                # Add symbols to graph (with enrichment)
                for sym in symbols:
                    # Enrich symbol with inferred_type, description, domains
                    enriched_sym = self._enrich_symbol(sym)
                    graph.add_symbol(enriched_sym)
                    stats["symbols"] += 1

            except Exception as e:
                print(f"Warning: Failed to parse {path}: {e}", file=sys.stderr)
                stats["errors"] += 1

        # Build parsing stats summary
        parsed_parts = []
        adapter_display_names = {
            'java': 'Java', 'python': 'Python', 'typescript': 'TypeScript',
            'prisma': 'Prisma', 'ruby': 'Ruby', 'csharp': 'C#', 'go': 'Go',
            'jsp': 'JSP', 'html': 'HTML', 'vue': 'Vue',
        }
        for adapter_name, count in sorted(stats["files_by_adapter"].items()):
            display = adapter_display_names.get(adapter_name, adapter_name.title())
            parsed_parts.append(f"{count} {display}")
        print(f"  Parsed: {', '.join(parsed_parts) or 'no'} files", file=sys.stderr)
        print(f"  Extracted: {stats['symbols']} symbols", file=sys.stderr)

        # Run linkers to resolve cross-references
        if resolve:
            linker_results = self._run_linkers(graph)
            total_refs = sum(linker_results.values())
            print(f"  Resolved: {total_refs} references", file=sys.stderr)

        return graph

    def _run_linkers(self, graph: "SymbolGraph") -> Dict[str, int]:
        """
        Run all registered linkers on the graph.

        Args:
            graph: Symbol graph to process

        Returns:
            Dict of linker name -> references created
        """
        if not HAS_SYMBOL_GRAPH or not LinkerRegistry:
            return {}

        registry = LinkerRegistry(graph)
        registry.discover()
        return registry.run_all()

    def _get_symbol_graph_path(self) -> Path:
        """Get path for Symbol Graph JSON export."""
        return get_index_dir(self.project) / f"{self._path_hash()}_graph.json"

    def _get_symbol_db_path(self) -> Path:
        """Get path for Symbol Graph SQLite export."""
        return get_index_dir(self.project) / f"{self._path_hash()}_graph.db"

    def _get_unified_db_path(self) -> Path:
        """Get path for Unified SQLite database."""
        return get_index_dir(self.project) / "unified.db"

    def _get_unified_engine(self):
        """Get UnifiedQueryEngine, fall back to None if unavailable."""
        db_path = self._get_unified_db_path()
        if db_path.exists():
            try:
                from query_builder import UnifiedQueryEngine
                return UnifiedQueryEngine(str(db_path))
            except (ImportError, Exception):
                return None
        return None



    def blast_radius_graph(
        self,
        symbol: str,
        depth: int = 2,
        edge_types: Optional[str] = None,
        direction: str = "both"
    ) -> Dict[str, Any]:
        """
        Compute blast radius using Symbol Graph SQLite database.

        Enables cross-layer data lineage:
        - Java: entities, controllers, services, DAOs
        - JSP: pages, EL expressions, form bindings
        - HTML/Frontend: components, props, data bindings
        - Database: tables, columns

        Args:
            symbol: Symbol name or qualified name to analyze
            depth: Traversal depth
            edge_types: Comma-separated edge types (maps_to, binds_to, calls, etc)
            direction: "downstream", "upstream", or "both"

        Returns:
            Dict with lineage information
        """
        db_path = self._get_symbol_db_path()
        if not db_path.exists():
            return {
                "error": f"Symbol Graph database not found. Run: index --export-db",
                "suggestions": [],
            }

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Parse edge types filter
        allowed_types = None
        if edge_types:
            allowed_types = set(t.strip().lower() for t in edge_types.split(","))

        # Find the symbol (try exact match, then qualified name, then fuzzy)
        cursor = conn.cursor()

        # Try exact ID match
        cursor.execute(
            "SELECT id, name, qualified_name, type FROM symbols WHERE id = ? OR qualified_name = ?",
            (symbol, symbol)
        )
        row = cursor.fetchone()

        if not row:
            # Try name match
            cursor.execute(
                "SELECT id, name, qualified_name, type FROM symbols WHERE name = ?",
                (symbol,)
            )
            row = cursor.fetchone()

        if not row:
            # Fuzzy search for suggestions
            cursor.execute(
                """SELECT name, type, qualified_name,
                   (100 - LENGTH(name) + LENGTH(?)) as score
                   FROM symbols
                   WHERE name LIKE ? OR qualified_name LIKE ?
                   ORDER BY score DESC
                   LIMIT 5""",
                (symbol, f"%{symbol}%", f"%{symbol}%")
            )
            suggestions = [
                {"name": r["name"], "type": r["type"], "qualified_name": r["qualified_name"], "score": r["score"]}
                for r in cursor.fetchall()
            ]
            conn.close()
            return {
                "error": f"Symbol '{symbol}' not found in graph",
                "suggestions": suggestions,
            }

        start_id = row["id"]
        start_name = row["qualified_name"] or row["name"]
        start_type = row["type"]

        # Build lineage results
        upstream: List[Dict] = []  # What references this (dependents)
        downstream: List[Dict] = []  # What this references (dependencies)

        # Upstream traversal (what uses this symbol)
        if direction in ("upstream", "both"):
            visited = set()
            queue = [(start_id, 0)]

            while queue:
                current_id, current_depth = queue.pop(0)
                if current_id in visited or current_depth >= depth:
                    continue
                visited.add(current_id)

                # Find references where this symbol is the target
                cursor.execute(
                    """SELECT r.source_id, r.ref_type, r.confidence,
                              s.name, s.qualified_name, s.type as symbol_type
                       FROM refs r
                       JOIN symbols s ON r.source_id = s.id
                       WHERE r.target_id = ?""",
                    (current_id,)
                )
                for ref in cursor.fetchall():
                    ref_type = ref["ref_type"]
                    if allowed_types and ref_type not in allowed_types:
                        continue

                    upstream.append({
                        "symbol": ref["qualified_name"] or ref["name"],
                        "type": ref["symbol_type"],
                        "ref_type": ref_type,
                        "confidence": ref["confidence"],
                        "depth": current_depth + 1,
                    })

                    if ref["source_id"] not in visited:
                        queue.append((ref["source_id"], current_depth + 1))

        # Downstream traversal (what this symbol uses/maps to)
        if direction in ("downstream", "both"):
            visited = set()
            queue = [(start_id, 0)]

            while queue:
                current_id, current_depth = queue.pop(0)
                if current_id in visited or current_depth >= depth:
                    continue
                visited.add(current_id)

                # Find references where this symbol is the source
                cursor.execute(
                    """SELECT r.target_id, r.ref_type, r.confidence,
                              s.name, s.qualified_name, s.type as symbol_type
                       FROM refs r
                       JOIN symbols s ON r.target_id = s.id
                       WHERE r.source_id = ?""",
                    (current_id,)
                )
                for ref in cursor.fetchall():
                    ref_type = ref["ref_type"]
                    if allowed_types and ref_type not in allowed_types:
                        continue

                    downstream.append({
                        "symbol": ref["qualified_name"] or ref["name"],
                        "type": ref["symbol_type"],
                        "ref_type": ref_type,
                        "confidence": ref["confidence"],
                        "depth": current_depth + 1,
                    })

                    if ref["target_id"] not in visited:
                        queue.append((ref["target_id"], current_depth + 1))

        conn.close()

        return {
            "symbol": start_name,
            "symbol_type": start_type,
            "upstream": upstream,
            "downstream": downstream,
            "edge_types_filter": edge_types,
            "direction": direction,
            "depth": depth,
        }

    async def ensure_fresh(self, verbose: bool = True) -> bool:
        """
        Ensure JSONL index and unified DB exist, building if necessary.

        Args:
            verbose: Print progress messages.

        Returns:
            True if index was rebuilt, False if already fresh
        """
        if not HAS_JSONL_MODULES:
            print("Error: JSONL modules not available", file=sys.stderr)
            return False

        jsonl_path = self._get_jsonl_index_path()
        unified_db_path = self._get_unified_db_path()
        rebuilt = False

        if not jsonl_path.exists():
            if verbose:
                print("No index found. Building index...", file=sys.stderr)
            await self.build_index_jsonl(force=True)
            rebuilt = True

        # Ensure unified DB exists (migration from JSONL → SQLite)
        if not unified_db_path.exists() and jsonl_path.exists():
            if verbose:
                print("Building unified database...", file=sys.stderr)
            self._run_migration()
            rebuilt = True

        return rebuilt

    def _run_migration(self, verbose: bool = True):
        """Run JSONL → unified SQLite migration."""
        migration_script = Path(__file__).parent / "migration.py"
        unified_db_path = self._get_unified_db_path()

        # Find graph DB if it exists
        graph_dbs = list(get_index_dir(self.project).glob("*_graph.db"))

        cmd = [
            sys.executable, str(migration_script),
            "--jsonl-dir", str(get_index_dir(self.project)),
            "--output", str(unified_db_path),
        ]
        if graph_dbs:
            cmd.extend(["--existing-db", str(graph_dbs[0])])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                if verbose:
                    report = json.loads(result.stdout)
                    print(f"  Unified DB: {report['stats']['symbols_total']} symbols, "
                          f"{report['stats']['refs_total']} refs")
            else:
                print(f"Warning: Unified DB build failed: {result.stderr[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Unified DB build failed: {str(e)[:200]}", file=sys.stderr)

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        engine = self._get_unified_engine()
        if engine:
            stats = engine.get_stats()
            stats["root_path"] = str(self.root_path)
            stats["format"] = "unified_sqlite"
            return stats

        return {"error": "No unified database found. Run /wicked-search:index first.", "format": "none"}


# =============================================================================
# CLI
# =============================================================================

def format_results(results: List[Dict[str, Any]], title: str = "Results") -> str:
    """Format search results for display."""
    if not results:
        return f"No {title.lower()} found."

    lines = [f"\n{title} ({len(results)}):"]
    lines.append("-" * 60)

    for r in results:
        domain = r.get('domain', 'unknown')
        sym_type = r.get('type', 'unknown')
        name = r.get('name', 'unknown')
        file_path = r.get('file_path', '')
        line = r.get('line_start', '')
        score = r.get('score', 0)

        location = f"{file_path}:{line}" if line else file_path
        lines.append(f"  [{domain}:{sym_type}] {name}")
        lines.append(f"    Location: {location}")
        if score:
            lines.append(f"    Score: {score:.1f}")
        lines.append("")

    return "\n".join(lines)


class HelpOnErrorParser(argparse.ArgumentParser):
    """ArgumentParser that shows help on any error."""

    def error(self, message: str):
        """Print help message on error instead of just the error."""
        sys.stderr.write(f"Error: {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)


async def main():
    parser = HelpOnErrorParser(
        description="Unified code and document search"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # index
    index_parser = subparsers.add_parser("index", help="Build/rebuild index")
    index_parser.add_argument("path", help="Path to index")
    index_parser.add_argument("--force", "-f", action="store_true", help="Force full rebuild")
    index_parser.add_argument("--export-graph", action="store_true",
                             help="Also export Symbol Graph (JSP/HTML) to JSON")
    index_parser.add_argument("--export-db", action="store_true",
                             help="Also export Symbol Graph to SQLite database")
    index_parser.add_argument("--no-resolve", action="store_true",
                             help="Skip linker resolution (faster, less detail)")
    index_parser.add_argument("--export-cache", action="store_true",
                             help="Export graph to wicked-cache for cross-plugin access")
    index_parser.add_argument("--skip-graph", action="store_true",
                             help="Skip Symbol Graph + linker pipeline (JSONL only, faster)")
    index_parser.add_argument("--project", help="Project name for multi-project isolation")

    # search
    search_parser = subparsers.add_parser("search", help="Search everything")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--path", "-p", default=".", help="Project path")
    search_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    search_parser.add_argument("--layer", help="Filter by architectural layer (backend, frontend, database, view)")
    search_parser.add_argument("--type", help="Filter by symbol type (e.g., CLASS, FUNCTION, METHOD, TABLE)")
    search_parser.add_argument("--project", help="Project name for multi-project isolation")

    # code
    code_parser = subparsers.add_parser("code", help="Search code only")
    code_parser.add_argument("query", help="Search query")
    code_parser.add_argument("--path", "-p", default=".", help="Project path")
    code_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")
    code_parser.add_argument("--layer", help="Filter by architectural layer (backend, frontend, database, view)")
    code_parser.add_argument("--type", help="Filter by symbol type (e.g., CLASS, FUNCTION, METHOD, TABLE)")
    code_parser.add_argument("--project", help="Project name for multi-project isolation")

    # docs
    docs_parser = subparsers.add_parser("docs", help="Search docs only")
    docs_parser.add_argument("query", help="Search query")
    docs_parser.add_argument("--path", "-p", default=".", help="Project path")
    docs_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results")

    # refs
    refs_parser = subparsers.add_parser("refs", help="Find references")
    refs_parser.add_argument("symbol", help="Symbol name")
    refs_parser.add_argument("--path", "-p", default=".", help="Project path")

    # impl
    impl_parser = subparsers.add_parser("impl", help="Find implementations")
    impl_parser.add_argument("section", help="Doc section name")
    impl_parser.add_argument("--path", "-p", default=".", help="Project path")

    # blast-radius
    blast_parser = subparsers.add_parser("blast-radius", help="Analyze dependencies and dependents")
    blast_parser.add_argument("symbol", help="Symbol name to analyze")
    blast_parser.add_argument("--depth", "-d", type=int, default=2, help="Traversal depth (default 2)")
    blast_parser.add_argument("--path", "-p", default=".", help="Project path")
    blast_parser.add_argument("--edge-types", "-e", type=str,
                             help="Comma-separated edge types to follow (calls,binds_to,maps_to,imports,etc)")
    blast_parser.add_argument("--direction", choices=["downstream", "upstream", "both"],
                             default="both", help="Traversal direction (default: both)")
    blast_parser.add_argument("--use-graph", "-g", action="store_true",
                             help="Use Symbol Graph for cross-layer lineage (Java/JSP/HTML/DB)")
    blast_parser.add_argument("--format", choices=["flat", "graph"], default="flat",
                             help="Output format: flat (default, human-readable) or graph (JSON with nodes/edges)")
    blast_parser.add_argument("--project", help="Project name for multi-project isolation")

    # db-path
    dbpath_parser = subparsers.add_parser("db-path", help="Show database file path")
    dbpath_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--path", "-p", default=".", help="Project path")
    stats_parser.add_argument("--group-by", help="Group statistics by field (e.g., 'layer', 'type')")
    stats_parser.add_argument("--project", help="Project name for multi-project isolation")

    # scout (no index required)
    scout_parser = subparsers.add_parser("scout", help="Quick pattern reconnaissance (no index needed)")
    scout_parser.add_argument("pattern", help="Pattern type: api, test, config, auth, db, error-handling, logging, validation, test-patterns")
    scout_parser.add_argument("--path", "-p", default=".", help="Directory to scout")

    # graph (Symbol Graph specific)
    graph_parser = subparsers.add_parser("graph", help="Build and query Symbol Graph")
    graph_parser.add_argument("--path", "-p", default=".", help="Project path")
    graph_parser.add_argument("--export-json", "-j", type=str, help="Export to JSON file")
    graph_parser.add_argument("--export-db", "-d", type=str, help="Export to SQLite file")
    graph_parser.add_argument("--no-resolve", action="store_true",
                             help="Skip linker resolution")
    graph_parser.add_argument("--list-linkers", action="store_true",
                             help="List available linkers")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Handle db-path (no project path needed)
    if args.command == "db-path":
        index_dir = get_index_dir()
        unified_db = index_dir / "unified.db"
        db_path = str(unified_db)
        exists = unified_db.exists()
        if getattr(args, 'json', False):
            print(json.dumps({"db_path": db_path, "exists": exists}))
        else:
            print(f"DB path: {db_path}")
            print(f"Exists: {exists}")
        return

    # Get project path
    project_path = Path(args.path if hasattr(args, 'path') else '.').resolve()

    # Get project name if specified
    project_name = getattr(args, 'project', None)

    # Create index
    index = UnifiedSearchIndex(project_path, project_name)

    if args.command == "index":
        project_path = Path(args.path).resolve()
        index = UnifiedSearchIndex(project_path, project_name)
        print(f"Indexing {project_path}...")

        if not HAS_JSONL_MODULES:
            print("Error: JSONL modules not available", file=sys.stderr)
            return

        stats = await index.build_index_jsonl(force=args.force)

        print(f"\nIndexing complete:")
        print(f"  Code files: {stats['code_files']}")
        print(f"  Doc files: {stats['doc_files']}")
        print(f"  Code symbols: {stats['code_symbols']}")
        print(f"  Doc sections: {stats['doc_sections']}")
        print(f"  Cross-references: {stats['cross_refs']}")
        print(f"  Mode: parallel (JSONL)")
        if stats['skipped']:
            print(f"  Skipped (unchanged): {stats['skipped']}")
        if stats['failed']:
            print(f"  Failed: {stats['failed']}")

        # Build Symbol Graph with linkers (default: on, skip with --skip-graph)
        build_graph = not getattr(args, 'skip_graph', False)
        if build_graph and HAS_SYMBOL_GRAPH:
            print("\nBuilding Symbol Graph + running linkers...")
            graph = index.build_symbol_graph(resolve=not args.no_resolve)

            if graph:
                graph_stats = graph.stats()
                print(f"  Symbol Graph: {graph_stats.get('total_symbols', 0)} symbols, "
                      f"{graph_stats.get('total_references', 0)} references")

                # Always export JSON graph (default behavior)
                graph_path = index._get_symbol_graph_path()
                graph.export_json(graph_path)
                print(f"  Exported JSON: {graph_path}")

                if args.export_db:
                    db_path = index._get_symbol_db_path()
                    graph.export_sqlite(db_path)
                    print(f"  Exported SQLite: {db_path}")

                # Export to wicked-cache if requested
                if args.export_cache:
                    try:
                        from graph_export import GraphExporter
                        # Try to import wicked-cache
                        try:
                            import sys as _sys
                            cache_path = Path(__file__).parent.parent.parent / "wicked-startah" / "scripts"
                            if cache_path.exists():
                                _sys.path.insert(0, str(cache_path))
                            from cache import namespace
                            cache = namespace("wicked-search")

                            exporter = GraphExporter(cache)
                            # Invalidate old cache first
                            workspace_hash = exporter._hash_workspace(str(project_path))
                            invalidated = exporter.invalidate_all(workspace_hash)
                            if invalidated:
                                print(f"  Invalidated {invalidated} old cache entries")

                            # Export all query types
                            result = exporter.export_all(graph, str(project_path))
                            print(f"  Exported to cache: {len(result.keys_written)} entries")
                            print(f"    Workspace hash: {result.workspace_hash}")
                        except ImportError as ie:
                            print(f"  Warning: wicked-cache not available: {ie}", file=sys.stderr)
                    except ImportError:
                        print("  Warning: graph_export module not available", file=sys.stderr)
        elif build_graph and not HAS_SYMBOL_GRAPH:
            print("Note: Symbol Graph modules not available, JSONL index only", file=sys.stderr)

        # Auto-build unified SQLite database
        print("\nBuilding unified database...")
        index._run_migration()

    elif args.command == "graph":
        # Symbol Graph specific command
        if not HAS_SYMBOL_GRAPH:
            print("Error: Symbol Graph modules not available", file=sys.stderr)
            print("Install with: pip install -e .[graph]", file=sys.stderr)
            return

        if args.list_linkers:
            print("Available linkers:")
            for name in list_linkers():
                print(f"  - {name}")
            return

        print(f"Building Symbol Graph for {project_path}...")
        graph = index.build_symbol_graph(resolve=not args.no_resolve)

        if graph:
            # Show stats
            graph_stats = graph.stats()
            print(f"\nSymbol Graph Statistics:")
            print(f"  Total symbols: {graph_stats.get('total_symbols', 0)}")
            print(f"  Total references: {graph_stats.get('total_references', 0)}")

            # Show symbol type breakdown
            print("\n  By symbol type:")
            for key, value in sorted(graph_stats.items()):
                if key.startswith("symbols_") and value > 0:
                    sym_type = key.replace("symbols_", "")
                    print(f"    {sym_type}: {value}")

            # Show reference type breakdown
            print("\n  By reference type:")
            for key, value in sorted(graph_stats.items()):
                if key.startswith("references_") and value > 0:
                    ref_type = key.replace("references_", "")
                    print(f"    {ref_type}: {value}")

            # Export if requested
            if args.export_json:
                graph.export_json(Path(args.export_json))
                print(f"\n  Exported JSON: {args.export_json}")

            if args.export_db:
                graph.export_sqlite(Path(args.export_db))
                print(f"  Exported SQLite: {args.export_db}")

    elif args.command == "scout":
        # Scout: quick pattern reconnaissance without indexing
        scout_path = Path(args.path).resolve()
        if not scout_path.exists():
            print(f"Error: Path {scout_path} does not exist", file=sys.stderr)
            return

        # Define pattern configs: pattern_name -> list of (label, regex, description)
        SCOUT_PATTERNS = {
            "api": [
                ("API Routes", r'@(app\.(get|post|put|delete|patch)|router\.(get|post|put|delete|patch)|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)', "Route decorators/annotations"),
                ("API Endpoints", r'(app\.route|@api_view|@action|url\(|path\(|Route\()', "Endpoint definitions"),
                ("REST Handlers", r'(def (get|post|put|delete|patch|list|create|update|destroy)\(|async def (get|post|put|delete)\()', "HTTP method handlers"),
            ],
            "test": [
                ("Test Classes", r'class\s+Test\w+', "Test class definitions"),
                ("Test Functions", r'(def\s+test_\w+|it\s*\(|describe\s*\(|test\s*\()', "Test function/block definitions"),
                ("Assertions", r'(assert\w*\(|expect\(|should\.|assertEqual|assertTrue|assertFalse|assertRaises)', "Assertion statements"),
                ("Mocks", r'(Mock\(|mock\.|patch\(|@patch|jest\.fn|sinon\.stub|vi\.fn)', "Mock/stub usage"),
            ],
            "config": [
                ("Config Files", r'(\.env|\.ini|\.yaml|\.yml|\.toml|\.cfg|config\.\w+)', "Configuration files (filename match)"),
                ("Environment Variables", r'(os\.environ|process\.env|getenv\(|ENV\[)', "Environment variable access"),
                ("Settings Classes", r'(class\s+\w*(Config|Settings|Options)\b|DATABASES\s*=|INSTALLED_APPS)', "Settings/config definitions"),
            ],
            "auth": [
                ("Authentication", r'(authenticate|login|logout|sign_in|sign_out|JWT|Bearer|OAuth|token)', "Auth-related code"),
                ("Authorization", r'(authorize|permission|role|access_control|@login_required|IsAuthenticated|has_perm)', "Authorization checks"),
                ("Credentials", r'(password|credential|secret|api_key|auth_token)', "Credential handling"),
            ],
            "db": [
                ("Database Queries", r'(SELECT\s+|INSERT\s+INTO|UPDATE\s+|DELETE\s+FROM|CREATE\s+TABLE)', "SQL statements"),
                ("ORM Models", r'(class\s+\w+\(.*Model\)|db\.Column|models\.\w+Field|@Entity|@Table)', "ORM model definitions"),
                ("Migrations", r'(migrate|migration|CreateModel|AddField|AlterField|RunSQL)', "Migration code"),
            ],
            "error-handling": [
                ("Try/Catch Blocks", r'(try\s*:|try\s*\{|catch\s*\(|except\s+)', "Exception handling blocks"),
                ("Throw/Raise", r'(raise\s+\w+|throw\s+new|throw\s+\w+)', "Error raising statements"),
                ("Error Types", r'(Error|Exception|ValueError|TypeError|RuntimeError|IOError|KeyError|AttributeError|IndexError)\b', "Error/exception type references"),
            ],
            "logging": [
                ("Logger Imports", r'(import\s+logging|require.*log|from\s+\w+\s+import.*[Ll]ogger)', "Logger imports"),
                ("Logger Calls", r'(logger\.\w+\(|log\.\w+\(|console\.\w+\(|logging\.\w+\()', "Logging method calls"),
                ("Log Levels", r'\.(debug|info|warning|warn|error|critical|fatal)\(', "Log level usage"),
            ],
            "validation": [
                ("Validation Models", r'(class\s+\w+\(.*(?:BaseModel|Schema|Validator|Form)\)|@validates|@validator)', "Validation class definitions"),
                ("Type Checks", r'(isinstance\(|typeof\s+|is_valid\(|validate\(|@field_validator)', "Type/validation checks"),
                ("Input Sanitization", r'(sanitize|escape|clean|strip_tags|bleach|html\.escape)', "Input sanitization"),
            ],
            "test-patterns": [
                ("Test Classes/Functions", r'(class\s+Test\w+|def\s+test_\w+|describe\s*\(|it\s*\()', "Test definitions"),
                ("Test Methods", r'def\s+test_\w+\s*\(', "Test method definitions"),
                ("Assertions", r'(self\.assert\w+|assert\s+|expect\(|should\.|\.to\w*\()', "Assertion patterns"),
                ("Mocks/Stubs", r'(@patch|Mock\(|mock\.|MagicMock|jest\.fn|sinon|vi\.fn|stub\()', "Mock/stub patterns"),
            ],
        }

        pattern_type = args.pattern.lower()
        if pattern_type not in SCOUT_PATTERNS:
            print(f"Unknown pattern type: '{pattern_type}'")
            print(f"Available patterns: {', '.join(sorted(SCOUT_PATTERNS.keys()))}")
            return

        patterns = SCOUT_PATTERNS[pattern_type]

        # Collect code files (skip binary, hidden, vendor, node_modules)
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor', 'dist', 'build', '.tox'}
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', '.rs', '.cs', '.php',
                          '.c', '.cpp', '.h', '.hpp', '.swift', '.kt', '.scala', '.sh', '.bash',
                          '.yaml', '.yml', '.json', '.toml', '.ini', '.cfg', '.env', '.md', '.txt'}

        files = []
        for root, dirs, filenames in os.walk(str(scout_path)):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            for fname in filenames:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in code_extensions:
                    files.append(fpath)

        if not files:
            print(f"No code files found in {scout_path}")
            return

        # Scan files for patterns
        results = {}
        total_matches = 0
        files_with_matches = set()

        for label, regex, _desc in patterns:
            results[label] = []
            compiled = re.compile(regex, re.IGNORECASE)

            for fpath in files:
                try:
                    content = fpath.read_text(encoding='utf-8', errors='replace')
                    lines = content.split('\n')
                    file_matches = []
                    for i, line in enumerate(lines, 1):
                        if compiled.search(line):
                            file_matches.append((i, line.strip()))
                    if file_matches:
                        rel_path = str(fpath.relative_to(scout_path))
                        results[label].append({
                            'file': rel_path,
                            'matches': file_matches,
                            'count': len(file_matches),
                        })
                        total_matches += len(file_matches)
                        files_with_matches.add(rel_path)
                except Exception:
                    continue

        # Format output
        print(f"\n## Scout: {pattern_type}")
        print()

        for label, regex, _desc in patterns:
            section_results = results.get(label, [])
            if not section_results:
                continue

            section_total = sum(r['count'] for r in section_results)
            print(f"### {label}")
            for r in section_results:
                if r['count'] == 1:
                    line_num, line_text = r['matches'][0]
                    print(f"{r['file']}:{line_num} ({line_text[:60]})")
                else:
                    print(f"{r['file']} ({r['count']} matches)")
                    for line_num, line_text in r['matches'][:5]:
                        print(f"  :{line_num} {line_text[:70]}")
                    if r['count'] > 5:
                        print(f"  ... and {r['count'] - 5} more")
            print()

        print(f"Summary: {total_matches} {pattern_type} patterns across {len(files_with_matches)} files")

    elif args.command in ("search", "code", "docs", "refs", "impl", "blast-radius", "stats"):
        # Auto-ensure fresh index (builds if missing)
        await index.ensure_fresh(verbose=True)

        # Load unified engine (v2.0: sole backend)
        engine = index._get_unified_engine()
        if not engine:
            print("Error: No unified database found. Run /wicked-search:index first.", file=sys.stderr)
            return

        if args.command == "search":
            results = engine.search_all(args.query, limit=args.limit * 10, offset=0)

            # Apply layer/type filters
            if hasattr(args, 'layer') and args.layer:
                results = [r for r in results if r.get("layer", "").lower() == args.layer.lower()]
            if hasattr(args, 'type') and args.type:
                results = [r for r in results if r.get("type", "").upper() == args.type.upper()]

            # Apply limit after filtering
            results = results[:args.limit]
            print(format_results(results, "Search Results"))

        elif args.command == "code":
            results = engine.search_code(args.query, limit=args.limit * 10)

            # Apply layer/type filters
            if hasattr(args, 'layer') and args.layer:
                results = [r for r in results if r.get("layer", "").lower() == args.layer.lower()]
            if hasattr(args, 'type') and args.type:
                results = [r for r in results if r.get("type", "").upper() == args.type.upper()]

            # Apply limit after filtering
            results = results[:args.limit]
            print(format_results(results, "Code Results"))

        elif args.command == "docs":
            results = engine.search_docs(args.query, limit=args.limit)
            print(format_results(results, "Document Results"))

        elif args.command == "refs":
            # Resolve symbol name to ID: try exact ID first, then search by name
            symbol_input = args.symbol
            symbol_id = symbol_input
            sym = engine.get_symbol(symbol_input)
            if not sym:
                # Not a direct ID — search by name to resolve
                candidates = engine.search_code(symbol_input, limit=5)
                if not candidates:
                    candidates = engine.search_all(symbol_input, limit=5)
                if candidates:
                    symbol_id = candidates[0]['id']
                # else: pass through and let find_references return empty

            raw_refs = engine.find_references(symbol_id)
            # Adapt engine format {incoming, outgoing} to display format
            # Migration stores ref_types as: calls, imports, extends, depends_on, documents
            refs = {}
            for r in raw_refs.get('incoming', []):
                rt = r.get('ref_type', 'unknown')
                key_map = {'calls': 'called_by', 'imports': 'imported_by', 'extends': 'inherited_by',
                           'depends_on': 'depended_on_by', 'documents': 'documented_in'}
                key = key_map.get(rt, f'{rt}_by')
                refs.setdefault(key, []).append(r)
            for r in raw_refs.get('outgoing', []):
                rt = r.get('ref_type', 'unknown')
                key_map = {'calls': 'calls', 'imports': 'imports', 'extends': 'inherits',
                           'depends_on': 'depends_on', 'documents': 'documents'}
                key = key_map.get(rt, rt)
                refs.setdefault(key, []).append(r)

            # Handle not found with suggestions
            if refs.get('error'):
                print(f"\n{refs['error']}")
                if refs.get('suggestions'):
                    print("\nDid you mean one of these?")
                    for s in refs['suggestions'][:5]:
                        print(f"  - {s['name']} ({s['type']}) - score: {s['score']:.0f}")
                return

            print(f"\nReferences for: {args.symbol}")
            print("-" * 60)

            # Documentation references
            if refs.get('documented_in'):
                print("\nDocumented in:")
                for r in refs['documented_in']:
                    print(f"  - {r.get('name', '?')} ({r.get('file_path', '?')})")

            # Incoming relationships (what uses this symbol)
            if refs.get('inherited_by'):
                print("\nInherited by:")
                for r in refs['inherited_by']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')}) in {r.get('file_path', '?')}")

            if refs.get('called_by'):
                print("\nCalled by:")
                for r in refs['called_by']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')}) in {r.get('file_path', '?')}")

            if refs.get('imported_by'):
                print("\nImported by:")
                for r in refs['imported_by']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            if refs.get('depended_on_by'):
                print("\nDepended on by:")
                for r in refs['depended_on_by']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            # Outgoing relationships (what this symbol uses)
            if refs.get('inherits'):
                print("\nInherits from:")
                for r in refs['inherits']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            if refs.get('calls'):
                print("\nCalls:")
                for r in refs['calls']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            if refs.get('imports'):
                print("\nImports:")
                for r in refs['imports']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            if refs.get('depends_on'):
                print("\nDepends on:")
                for r in refs['depends_on']:
                    print(f"  - {r.get('name', '?')} ({r.get('type', '?')})")

            # Check if no refs found
            has_refs = any(refs.get(k) for k in refs.keys())
            if not has_refs:
                print("  No references found")

        elif args.command == "impl":
            # Find the doc section
            matches = engine.search_docs(args.section, limit=5)
            if not matches:
                print(f"Doc section '{args.section}' not found")
                return

            # Try all matching doc sections to find implementations
            implementations = []
            seen_ids = set()

            for match in matches:
                node_id = match['id']
                refs = engine.find_references(node_id)

                # Check outgoing refs (doc section → code symbols via 'documents' refs)
                for r in refs.get('outgoing', []):
                    if r.get('ref_type') == 'documents' and r.get('id') not in seen_ids:
                        # Filter to code symbols only (not files/imports)
                        if r.get('type', '') not in ('file', 'import'):
                            implementations.append(r)
                            seen_ids.add(r.get('id'))

                # Also check incoming refs (backward compat: code → doc references)
                for r in refs.get('incoming', []):
                    if r.get('id') not in seen_ids:
                        if r.get('domain', '') == 'code' and r.get('type', '') not in ('file', 'import'):
                            implementations.append(r)
                            seen_ids.add(r.get('id'))

            print(f"\nImplementations of: {args.section}")
            print("-" * 60)

            if implementations:
                for impl in implementations:
                    print(f"  - {impl['name']} ({impl['type']}) in {impl['file_path']}")
            else:
                print("  No implementations found")

        elif args.command == "blast-radius":
            # Parse edge types if provided
            edge_types_str = getattr(args, 'edge_types', None)
            direction = getattr(args, 'direction', 'both')
            use_graph = getattr(args, 'use_graph', False)

            output_format = getattr(args, 'format', 'flat')

            if use_graph:
                # Use Symbol Graph SQLite for cross-layer lineage (Java/JSP/HTML/DB)
                result = index.blast_radius_graph(
                    args.symbol,
                    depth=args.depth,
                    edge_types=edge_types_str,
                    direction=direction
                )

                if output_format == 'graph':
                    # Output raw graph result as JSON for programmatic consumption
                    print(json.dumps(result, indent=2))
                    return

                if result.get('error'):
                    print(f"\n{result['error']}")
                    if result.get('suggestions'):
                        print("\nDid you mean one of these?")
                        for s in result['suggestions'][:5]:
                            name = s.get('qualified_name') or s.get('name', '?')
                            print(f"  - {name} ({s.get('type', '?')})")
                    return

                print(f"\nData Lineage for: {result['symbol']} ({result['symbol_type']})")
                if edge_types_str:
                    print(f"Edge types: {edge_types_str}")
                print(f"Direction: {direction}, Depth: {args.depth}")
                print("-" * 70)

                # Group by reference type for cleaner output
                if direction in ("downstream", "both") and result.get('downstream'):
                    print(f"\n▼ Downstream ({len(result['downstream'])} refs):")
                    by_type: Dict[str, List] = {}
                    for ref in result['downstream']:
                        rt = ref['ref_type']
                        if rt not in by_type:
                            by_type[rt] = []
                        by_type[rt].append(ref)

                    for ref_type, refs in sorted(by_type.items()):
                        print(f"  [{ref_type.upper()}]")
                        for ref in refs[:10]:
                            conf = ref.get('confidence', '?')
                            print(f"    → {ref['symbol']} ({ref['type']}) [{conf}]")
                        if len(refs) > 10:
                            print(f"    ... and {len(refs) - 10} more")

                if direction in ("upstream", "both") and result.get('upstream'):
                    print(f"\n▲ Upstream ({len(result['upstream'])} refs):")
                    by_type: Dict[str, List] = {}
                    for ref in result['upstream']:
                        rt = ref['ref_type']
                        if rt not in by_type:
                            by_type[rt] = []
                        by_type[rt].append(ref)

                    for ref_type, refs in sorted(by_type.items()):
                        print(f"  [{ref_type.upper()}]")
                        for ref in refs[:10]:
                            conf = ref.get('confidence', '?')
                            print(f"    ← {ref['symbol']} ({ref['type']}) [{conf}]")
                        if len(refs) > 10:
                            print(f"    ... and {len(refs) - 10} more")

                if not result.get('downstream') and not result.get('upstream'):
                    print("  No lineage found")

            else:
                # Resolve symbol name to ID for blast_radius / traverse
                symbol_input = args.symbol
                symbol_id = symbol_input
                sym = engine.get_symbol(symbol_input)
                if not sym:
                    candidates = engine.search_code(symbol_input, limit=5)
                    if not candidates:
                        candidates = engine.search_all(symbol_input, limit=5)
                    if candidates:
                        symbol_id = candidates[0]['id']
                    else:
                        print(f"\nSymbol '{symbol_input}' not found")
                        return

                if output_format == 'graph':
                    # Map blast-radius direction to traverse direction
                    traverse_direction = direction
                    if direction == 'downstream':
                        traverse_direction = 'outgoing'
                    elif direction == 'upstream':
                        traverse_direction = 'incoming'
                    # 'both' maps directly

                    result = engine.traverse(
                        symbol_id,
                        depth=args.depth,
                        direction=traverse_direction
                    )
                    print(json.dumps(result, indent=2))
                    return

                result = engine.blast_radius(
                    symbol_id,
                    max_depth=args.depth
                )

                print(f"\nBlast Radius for: {args.symbol}")
                if edge_types_str:
                    print(f"Edge types: {edge_types_str}")
                print(f"Direction: {direction}")
                print("-" * 60)
                print(f"  Total affected: {result.get('total_affected', 0)}")

                by_depth = result.get('by_depth', {})
                if by_depth:
                    for depth_level in sorted(by_depth.keys()):
                        symbols = by_depth[depth_level]
                        label = "Root" if depth_level == 0 else f"Depth {depth_level}"
                        print(f"\n  {label}: {len(symbols)} symbol(s)")
                        for sym in symbols[:20]:
                            name = sym.get('name', sym.get('id', '?'))
                            stype = sym.get('type', '?')
                            fpath = sym.get('file_path', '?')
                            print(f"    - {name} ({stype}) in {fpath}")
                        if len(symbols) > 20:
                            print(f"    ... and {len(symbols) - 20} more")
                else:
                    print("  No dependencies or dependents found")

        elif args.command == "stats":
            stats = index.get_stats()
            total_symbols = stats.get('total_symbols', 0)
            total_refs = stats.get('total_refs', 0)
            print(f"\nIndex Statistics for: {stats.get('root_path', str(project_path))}")
            print("-" * 60)
            print(f"  Format: {stats.get('format', 'unknown')}")
            print(f"  Total symbols: {total_symbols}")
            print(f"  Total refs: {total_refs}")
            if stats.get('by_domain'):
                print(f"  Code symbols: {stats['by_domain'].get('code', 0)}")
                print(f"  Doc sections: {stats['by_domain'].get('doc', 0)}")
                print(f"\n  By domain: {stats['by_domain']}")
            if stats.get('by_ref_type'):
                print(f"\n  By ref type: {stats['by_ref_type']}")
            if stats.get('lineage_paths'):
                print(f"  Lineage paths: {stats['lineage_paths']}")
            if stats.get('services'):
                print(f"  Services: {stats['services']}")

            # Handle --group-by option
            if hasattr(args, 'group_by') and args.group_by:
                group_by = args.group_by.lower()
                if group_by in ('layer', 'type'):
                    if group_by == 'layer' and stats.get('by_layer'):
                        print(f"\n  Grouped by layer:")
                        total = total_symbols or 1
                        for key, count in sorted(stats['by_layer'].items()):
                            percentage = (count / total * 100) if total > 0 else 0
                            print(f"    {key}: {count} ({percentage:.1f}%)")
                    elif group_by == 'type' and stats.get('by_type'):
                        print(f"\n  Grouped by type:")
                        total = total_symbols or 1
                        for key, count in sorted(stats['by_type'].items()):
                            percentage = (count / total * 100) if total > 0 else 0
                            print(f"    {key}: {count} ({percentage:.1f}%)")
                    else:
                        print(f"\n  No {group_by} breakdown available in stats")
                else:
                    print(f"\n  Warning: Unsupported group-by field '{args.group_by}'. Use 'layer' or 'type'.")


if __name__ == "__main__":
    asyncio.run(main())
