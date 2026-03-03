"""Incremental single-file index updates.

This module provides efficient updates when only one or a few files change,
avoiding full re-indexing by:
1. Removing old nodes for the changed file
2. Parsing the new content
3. Updating cross-references affected by the change
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Set

from models import GraphNode, NodeType


class IncrementalUpdater:
    """Updates index for changed files without full rebuild.

    Performs targeted updates by:
    1. Removing old nodes for changed files
    2. Parsing new content
    3. Resolving references within affected scope
    4. Updating dependents for affected symbols
    """

    def __init__(self, parse_fn: Callable[[Path], List[GraphNode]]):
        """Initialize the updater.

        Args:
            parse_fn: Function to parse a file into GraphNodes.
        """
        self.parse_fn = parse_fn

    def update_file(self, file_path: Path, index_path: Path) -> int:
        """Update index for a single changed file.

        Args:
            file_path: Path to the changed file.
            index_path: Path to the JSONL index.

        Returns:
            Number of nodes in the updated file.
        """
        file_str = str(file_path)

        # 1. Parse new file content
        try:
            new_nodes = self.parse_fn(file_path)
        except Exception as e:
            print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
            new_nodes = []

        new_ids = {n.id for n in new_nodes}

        # 2. Load existing index, filter out this file's nodes
        all_nodes: List[GraphNode] = []
        old_ids: Set[str] = set()
        affected_targets: Set[str] = set()

        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        node = GraphNode.model_validate_json(line)
                    except Exception:
                        continue

                    if node.file == file_str:
                        # Track what old nodes called (for dependent cleanup)
                        old_ids.add(node.id)
                        for call in node.calls:
                            if call.target_id:
                                affected_targets.add(call.target_id)
                    else:
                        # Clean up dependents that referenced old nodes
                        node.dependents = [
                            d for d in node.dependents
                            if d not in old_ids
                        ]
                        all_nodes.append(node)

        # 3. Add new nodes
        all_nodes.extend(new_nodes)

        # 4. Rebuild symbol index for resolution
        symbol_index: Dict[str, List[str]] = defaultdict(list)
        for node in all_nodes:
            if node.node_type not in (NodeType.FILE, NodeType.IMPORT):
                symbol_index[node.name].append(node.id)

        # 5. Build lookup by ID
        nodes_by_id = {n.id: n for n in all_nodes}

        # 6. Resolve calls in new nodes and update dependents
        for node in new_nodes:
            for call in node.calls:
                candidates = symbol_index.get(call.name, [])
                if candidates:
                    # Prefer same file
                    target = next(
                        (c for c in candidates if nodes_by_id[c].file == file_str),
                        candidates[0]
                    )
                    call.target_id = target
                    # Add to target's dependents
                    if target in nodes_by_id:
                        if node.id not in nodes_by_id[target].dependents:
                            nodes_by_id[target].dependents.append(node.id)
                            nodes_by_id[target].dependents.sort()

        # 7. Atomic write
        temp_path = index_path.with_suffix('.jsonl.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            for node in all_nodes:
                f.write(node.model_dump_json(by_alias=True) + '\n')
        temp_path.rename(index_path)

        return len(new_nodes)

    def update_files(
        self,
        file_paths: List[Path],
        index_path: Path
    ) -> int:
        """Update index for multiple changed files.

        More efficient than calling update_file repeatedly when
        multiple files change together.

        Args:
            file_paths: List of changed file paths.
            index_path: Path to the JSONL index.

        Returns:
            Total number of nodes in updated files.
        """
        if not file_paths:
            return 0

        if len(file_paths) == 1:
            return self.update_file(file_paths[0], index_path)

        file_strs = {str(p) for p in file_paths}

        # 1. Parse all new files
        new_nodes: List[GraphNode] = []
        for file_path in file_paths:
            try:
                nodes = self.parse_fn(file_path)
                new_nodes.extend(nodes)
            except Exception as e:
                print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)

        new_ids = {n.id for n in new_nodes}

        # 2. Load existing, filter out changed files
        all_nodes: List[GraphNode] = []
        old_ids: Set[str] = set()

        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        node = GraphNode.model_validate_json(line)
                    except Exception:
                        continue

                    if node.file in file_strs:
                        old_ids.add(node.id)
                    else:
                        node.dependents = [
                            d for d in node.dependents
                            if d not in old_ids
                        ]
                        all_nodes.append(node)

        # 3. Add new nodes
        all_nodes.extend(new_nodes)

        # 4-6. Resolve references (same as single file)
        symbol_index: Dict[str, List[str]] = defaultdict(list)
        for node in all_nodes:
            if node.node_type not in (NodeType.FILE, NodeType.IMPORT):
                symbol_index[node.name].append(node.id)

        nodes_by_id = {n.id: n for n in all_nodes}

        for node in new_nodes:
            for call in node.calls:
                candidates = symbol_index.get(call.name, [])
                if candidates:
                    target = next(
                        (c for c in candidates if nodes_by_id[c].file == node.file),
                        candidates[0]
                    )
                    call.target_id = target
                    if target in nodes_by_id:
                        if node.id not in nodes_by_id[target].dependents:
                            nodes_by_id[target].dependents.append(node.id)
                            nodes_by_id[target].dependents.sort()

        # 7. Atomic write
        temp_path = index_path.with_suffix('.jsonl.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            for node in all_nodes:
                f.write(node.model_dump_json(by_alias=True) + '\n')
        temp_path.rename(index_path)

        return len(new_nodes)

    def remove_file(self, file_path: Path, index_path: Path) -> int:
        """Remove a deleted file from the index.

        Args:
            file_path: Path to the deleted file.
            index_path: Path to the JSONL index.

        Returns:
            Number of nodes removed.
        """
        if not index_path.exists():
            return 0

        file_str = str(file_path)
        remaining_nodes: List[GraphNode] = []
        removed_ids: Set[str] = set()
        removed_count = 0

        # First pass: identify removed nodes
        with open(index_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    node = GraphNode.model_validate_json(line)
                except Exception:
                    continue

                if node.file == file_str:
                    removed_ids.add(node.id)
                    removed_count += 1
                else:
                    remaining_nodes.append(node)

        if removed_count == 0:
            return 0

        # Clean up dependents referencing removed nodes
        for node in remaining_nodes:
            node.dependents = [d for d in node.dependents if d not in removed_ids]

        # Write updated index
        temp_path = index_path.with_suffix('.jsonl.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            for node in remaining_nodes:
                f.write(node.model_dump_json(by_alias=True) + '\n')
        temp_path.rename(index_path)

        return removed_count
