"""Pass 2: Resolve cross-references and compute dependents.

This module performs the second pass of indexing, which:
1. Builds a symbol index from the JSONL output of pass 1
2. Resolves call targets to actual node IDs
3. Computes the reverse 'dependents' relationship
4. Rewrites the JSONL with resolved references
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from models import GraphNode, NodeType


class DependencyLinker:
    """Resolves call targets and computes dependents.

    Takes the raw JSONL output from pass 1 (with unresolved calls)
    and produces a linked JSONL with resolved target_ids and
    populated dependents arrays.
    """

    def __init__(self):
        # symbol_name -> [node_ids] for resolution
        self.symbol_index: Dict[str, List[str]] = defaultdict(list)
        # node_id -> GraphNode
        self.nodes: Dict[str, GraphNode] = {}
        # target_id -> set of caller_ids for dependents
        self.reverse_refs: Dict[str, Set[str]] = defaultdict(set)

    def link(self, index_path: Path) -> int:
        """Perform two-pass linking on an index file.

        1. Load all nodes, build symbol index
        2. Resolve calls and track dependents
        3. Propagate dependents back to nodes
        4. Rewrite index with resolved refs

        Args:
            index_path: Path to the JSONL index file.

        Returns:
            Count of resolved references.
        """
        # Pass 1: Load all nodes, build symbol index
        self._load_nodes(index_path)
        self._build_symbol_index()

        # Pass 2: Resolve calls and track dependents
        resolved = self._resolve_references()

        # Pass 3: Apply dependents to nodes
        self._apply_dependents()

        # Write updated index
        self._write_index(index_path)

        return resolved

    def _load_nodes(self, index_path: Path):
        """Load all nodes from JSONL into memory."""
        if not index_path.exists():
            return

        with open(index_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    node = GraphNode.model_validate_json(line)
                    self.nodes[node.id] = node
                except Exception as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}", file=sys.stderr)

    def _build_symbol_index(self):
        """Build name -> node_ids lookup for resolution."""
        for node_id, node in self.nodes.items():
            # Index functions, classes, methods by name
            if node.node_type not in (NodeType.FILE, NodeType.IMPORT):
                self.symbol_index[node.name].append(node_id)

    def _resolve_references(self) -> int:
        """Resolve call targets and inheritance, building reverse index."""
        resolved = 0

        for node_id, node in self.nodes.items():
            # Resolve function/method calls
            for call in node.calls:
                target_id = self._resolve_symbol(call.name, node.file)
                if target_id:
                    call.target_id = target_id
                    self.reverse_refs[target_id].add(node_id)
                    resolved += 1

            # Resolve base class inheritance
            for base in node.bases:
                # Handle qualified names (module.ClassName)
                base_name = base.rsplit('.', 1)[-1]
                target_id = self._resolve_symbol(base_name, node.file, prefer_class=True)
                if target_id:
                    self.reverse_refs[target_id].add(node_id)
                    resolved += 1

            # Resolve imports
            for imp in node.imports:
                # Try to find the imported module as a file node
                target_id = self._resolve_import(imp)
                if target_id:
                    self.reverse_refs[target_id].add(node_id)
                    resolved += 1

        return resolved

    def _resolve_symbol(
        self,
        name: str,
        caller_file: str,
        prefer_class: bool = False
    ) -> str | None:
        """Resolve a symbol name to a node ID.

        Args:
            name: The symbol name to resolve.
            caller_file: The file where the call occurs (for same-file preference).
            prefer_class: If True, prefer class/interface types.

        Returns:
            The resolved node ID, or None if not found.
        """
        candidates = self.symbol_index.get(name, [])
        if not candidates:
            return None

        # Filter by type if needed
        if prefer_class:
            class_candidates = [
                c for c in candidates
                if self.nodes[c].node_type in (NodeType.CLASS, NodeType.INTERFACE, NodeType.STRUCT)
            ]
            if class_candidates:
                candidates = class_candidates

        # Prefer same-file targets (local symbols)
        same_file = [c for c in candidates if self.nodes[c].file == caller_file]
        if same_file:
            return same_file[0]

        # Return first match
        return candidates[0]

    def _resolve_import(self, module_name: str) -> str | None:
        """Resolve an import to a file node ID.

        Args:
            module_name: The imported module name.

        Returns:
            The file node ID, or None if not found.
        """
        # Try exact file node match
        for node_id, node in self.nodes.items():
            if node.node_type == NodeType.FILE:
                # Match by stem (file.py -> file)
                file_stem = Path(node.file).stem
                if file_stem == module_name:
                    return node_id
                # Match by module path (src/utils/helpers.py -> src.utils.helpers)
                module_path = str(Path(node.file).with_suffix('')).replace('/', '.').replace('\\', '.')
                if module_path.endswith(module_name) or module_name.endswith(file_stem):
                    return node_id

        return None

    def _apply_dependents(self):
        """Apply collected reverse refs as dependents on each node."""
        for target_id, caller_ids in self.reverse_refs.items():
            if target_id in self.nodes:
                self.nodes[target_id].dependents = sorted(caller_ids)

    def _write_index(self, index_path: Path):
        """Write nodes back to JSONL (atomic)."""
        temp_path = index_path.with_suffix('.jsonl.tmp')

        with open(temp_path, 'w', encoding='utf-8') as f:
            for node in self.nodes.values():
                f.write(node.model_dump_json(by_alias=True) + '\n')

        # Atomic rename
        temp_path.rename(index_path)


def link_index(index_path: Path) -> int:
    """Convenience function to link an index file.

    Args:
        index_path: Path to the JSONL index.

    Returns:
        Number of resolved references.
    """
    linker = DependencyLinker()
    return linker.link(index_path)
