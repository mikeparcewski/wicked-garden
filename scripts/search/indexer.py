"""Parallel indexer with streaming JSONL writes.

This module provides multi-threaded file parsing with streaming output,
enabling efficient indexing of large codebases without holding the entire
graph in memory.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Callable, List, Optional

from models import GraphNode


class StreamingWriter:
    """Thread-safe streaming JSONL writer.

    Writes GraphNode objects to a JSONL file as they are parsed,
    using a queue to decouple parsing from writing.
    """

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.temp_path = output_path.with_suffix('.jsonl.tmp')
        self.queue: Queue[Optional[GraphNode]] = Queue()
        self.node_count = 0
        self._thread: Optional[Thread] = None
        self._error: Optional[Exception] = None

    def start(self):
        """Start the writer thread."""
        self._thread = Thread(target=self._write_loop, daemon=True)
        self._thread.start()

    def write(self, node: GraphNode):
        """Queue a node for writing (thread-safe)."""
        self.queue.put(node)

    def finish(self) -> int:
        """Signal completion and wait for writer to finish.

        Returns:
            Total number of nodes written.
        """
        self.queue.put(None)  # Sentinel
        if self._thread:
            self._thread.join()

        if self._error:
            raise self._error

        # Atomic rename
        if self.temp_path.exists():
            self.temp_path.rename(self.output_path)

        return self.node_count

    def _write_loop(self):
        """Writer loop - runs in separate thread."""
        try:
            with open(self.temp_path, 'w', encoding='utf-8') as f:
                while True:
                    node = self.queue.get()
                    if node is None:
                        break
                    f.write(node.model_dump_json(by_alias=True) + '\n')
                    self.node_count += 1
        except Exception as e:
            self._error = e
            print(f"Writer error: {e}", file=sys.stderr)


class ParallelIndexer:
    """Parallel file indexer with streaming output.

    Parses files in parallel using a thread pool, streaming results
    to a JSONL file as they complete.
    """

    def __init__(
        self,
        parse_fn: Callable[[Path], List[GraphNode]],
        max_workers: Optional[int] = None
    ):
        """Initialize the parallel indexer.

        Args:
            parse_fn: Function that takes a file path and returns a list of GraphNodes.
            max_workers: Maximum number of worker threads. Defaults to min(4, cpu_count).
        """
        self.parse_fn = parse_fn
        self.max_workers = max_workers or min(4, (os.cpu_count() or 1))

    def index_files(
        self,
        files: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> int:
        """Index files in parallel with streaming writes.

        Args:
            files: List of file paths to index.
            output_path: Path to write the JSONL output.
            progress_callback: Optional callback(completed, total) for progress.

        Returns:
            Total number of nodes written.
        """
        if not files:
            # Create empty file
            output_path.write_text('')
            return 0

        writer = StreamingWriter(output_path)
        writer.start()

        total = len(files)
        completed = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._safe_parse, f): f
                for f in files
            }

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    nodes = future.result()
                    for node in nodes:
                        writer.write(node)
                except Exception as e:
                    print(f"Warning: Failed to index {file_path}: {e}", file=sys.stderr)
                    failed += 1

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        node_count = writer.finish()

        if failed > 0:
            print(f"Indexing complete: {node_count} nodes, {failed} failed files", file=sys.stderr)

        return node_count

    def _safe_parse(self, path: Path) -> List[GraphNode]:
        """Parse with exception handling."""
        try:
            return self.parse_fn(path)
        except Exception as e:
            print(f"Warning: Parse error {path}: {e}", file=sys.stderr)
            return []


def index_files_sequential(
    files: List[Path],
    parse_fn: Callable[[Path], List[GraphNode]],
    output_path: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> int:
    """Sequential indexing fallback (for debugging or small file counts).

    Args:
        files: List of file paths to index.
        parse_fn: Function to parse a file into GraphNodes.
        output_path: Path to write the JSONL output.
        progress_callback: Optional progress callback.

    Returns:
        Total number of nodes written.
    """
    node_count = 0
    total = len(files)

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, path in enumerate(files):
            try:
                nodes = parse_fn(path)
                for node in nodes:
                    f.write(node.model_dump_json(by_alias=True) + '\n')
                    node_count += 1
            except Exception as e:
                print(f"Warning: Failed to index {path}: {e}", file=sys.stderr)

            if progress_callback:
                progress_callback(i + 1, total)

    return node_count
