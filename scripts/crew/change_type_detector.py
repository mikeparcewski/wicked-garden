#!/usr/bin/env python3
"""
Change-Type Detector — wicked-crew QE integration.

Classifies file paths into change types (ui, api, both, unknown) using a two-pass
algorithm: extension matching first, then path-segment matching for ambiguous cases.

Usage:
    python3 change_type_detector.py --files path/to/file1.tsx path/to/file2.py
    python3 change_type_detector.py --files lib/client.ts --task-description "Add request handler"
    python3 change_type_detector.py --json --files src/components/Button.tsx

Output:
    JSON with change_type (ui|api|both|unknown), ui_files, api_files,
    ambiguous_files, confidence, and reasoning.

Performance:
    Pure regex matching against file path strings. No I/O beyond argument parsing.
    Expected runtime < 10ms for any realistic task file list.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Extension classification tables
# ---------------------------------------------------------------------------

# Pass 1: Extensions that unambiguously classify as UI
UI_EXTENSIONS = frozenset([
    ".tsx", ".jsx", ".vue", ".svelte",
    ".html", ".htm",
    ".css", ".scss", ".sass", ".less",
])

# Pass 1: Extensions that need path confirmation for API (backend languages)
# These alone are ambiguous — they need path-segment context to be called API
API_CONFIRMING_EXTENSIONS = frozenset([
    ".py", ".rb", ".go", ".java", ".kt", ".rs", ".cs",
    ".php", ".scala", ".clj", ".ex", ".exs",
])

# Pass 1: Ambiguous extensions — require Pass 2 path-segment matching
AMBIGUOUS_EXTENSIONS = frozenset([".ts", ".js", ".mjs", ".cjs"])

# ---------------------------------------------------------------------------
# Path-segment classification tables
# ---------------------------------------------------------------------------

# Pass 2: Path segments that indicate UI code
UI_PATH_SEGMENTS = frozenset([
    "components", "pages", "views", "layouts", "templates",
    "ui", "frontend", "client", "public", "static",
    "styles", "assets", "icons", "images", "fonts",
    "src/app",  # Note: Next.js src/app is ambiguous but still UI-leaning
    "stories",  # Storybook stories = UI
])

# Pass 2: Path segments that indicate API code
API_PATH_SEGMENTS = frozenset([
    "api", "routes", "controllers", "handlers", "endpoints",
    "server", "backend", "services", "graphql", "rest", "grpc",
    "middleware", "resolvers", "mutations", "queries",
])

# ---------------------------------------------------------------------------
# Task description keyword tables (for ambiguous file resolution)
# ---------------------------------------------------------------------------

# Keywords from smart_decisioning.py signal library — API signals
API_KEYWORDS = frozenset([
    "api", "endpoint", "route", "handler", "controller",
    "request", "response", "payload", "schema", "contract",
    "webhook", "rest", "graphql", "grpc", "rpc",
    "http", "get", "post", "put", "patch", "delete",
    "service", "middleware", "resolver", "mutation", "query",
    "server-side", "backend",
])

# Keywords from smart_decisioning.py signal library — UI signals
UI_KEYWORDS = frozenset([
    "component", "render", "view", "page", "style",
    "layout", "visual", "ui", "form", "button",
    "modal", "dialog", "menu", "nav", "navigation",
    "frontend", "client-side", "browser", "display",
    "css", "scss", "animation", "transition", "theme",
    "accessibility", "a11y", "wcag",
])


# ---------------------------------------------------------------------------
# Core classification logic
# ---------------------------------------------------------------------------

def _get_extension(filepath: str) -> str:
    """Return the lowercase file extension including the dot."""
    return Path(filepath).suffix.lower()


def _get_path_segments(filepath: str) -> List[str]:
    """Return all path segments as lowercase strings."""
    # Normalize separators and split
    normalized = filepath.replace("\\", "/").lower()
    parts = normalized.split("/")
    return [p for p in parts if p]


def _matches_ui_path(segments: List[str]) -> bool:
    """Return True if any path segment indicates UI code."""
    for seg in segments:
        if seg in UI_PATH_SEGMENTS:
            return True
        # Also check multi-segment patterns like "src/app"
        for ui_seg in UI_PATH_SEGMENTS:
            if "/" in ui_seg:
                if ui_seg in "/".join(segments):
                    return True
    return False


def _matches_api_path(segments: List[str]) -> bool:
    """Return True if any path segment indicates API code."""
    for seg in segments:
        if seg in API_PATH_SEGMENTS:
            return True
    return False


def _resolve_via_task_description(
    task_description: str,
) -> Optional[str]:
    """
    Resolve ambiguous file using task description keyword matching.

    Returns: "ui", "api", or None (if both or neither match)
    """
    if not task_description:
        return None

    desc_lower = task_description.lower()
    # Tokenize on non-alphanumeric characters to match whole words
    words = set(re.split(r"[^a-z0-9]+", desc_lower))

    has_api = bool(words & API_KEYWORDS)
    has_ui = bool(words & UI_KEYWORDS)

    if has_api and not has_ui:
        return "api"
    if has_ui and not has_api:
        return "ui"
    # Both or neither → caller decides (conservative fallback: "both")
    return None


def classify_file(
    filepath: str,
    task_description: str = "",
) -> Tuple[str, str]:
    """
    Classify a single file as ui, api, or ambiguous.

    Returns: (classification, reasoning)
    """
    ext = _get_extension(filepath)
    segments = _get_path_segments(filepath)

    # --- Pass 1: Extension matching ---
    if ext in UI_EXTENSIONS:
        # UI extensions are unambiguous by extension alone
        # EXCEPT if we have a .tsx/.jsx file with strong API path segments
        # (e.g., Next.js API routes: pages/api/handler.ts → api beats tsx)
        if _matches_api_path(segments) and not _matches_ui_path(segments):
            # Strong API path context overrides UI extension
            resolved = _resolve_via_task_description(task_description)
            if resolved == "api":
                return ("api", f"UI extension {ext} overridden by API path segments and API task description keywords")
            # Otherwise keep UI — extension is still a strong signal
        return ("ui", f"UI extension: {ext}")

    if ext in API_CONFIRMING_EXTENSIONS:
        # Backend language + API path segment = strong API signal
        if _matches_api_path(segments):
            return ("api", f"API-confirming extension {ext} with API path segment")
        if _matches_ui_path(segments):
            # Backend file in UI directory? Unusual but classify as both
            return ("ambiguous", f"API-confirming extension {ext} in UI path — treat as both")
        # Backend language with no path match — classify as API (heuristic)
        return ("api", f"API-confirming extension {ext} (no path match, defaulting to API)")

    if ext in AMBIGUOUS_EXTENSIONS:
        # --- Pass 2: Path-segment matching for .ts/.js ---
        is_ui_path = _matches_ui_path(segments)
        is_api_path = _matches_api_path(segments)

        if is_ui_path and not is_api_path:
            return ("ui", f"Ambiguous extension {ext} resolved via UI path segment")
        if is_api_path and not is_ui_path:
            return ("api", f"Ambiguous extension {ext} resolved via API path segment")
        if is_ui_path and is_api_path:
            # Both path signals — use task description as tiebreaker
            resolved = _resolve_via_task_description(task_description)
            if resolved:
                return (resolved, f"Ambiguous extension {ext} with both path signals; task description resolved to {resolved}")
            return ("ambiguous", f"Ambiguous extension {ext} matches both UI and API path segments")

        # No path signal — use task description
        resolved = _resolve_via_task_description(task_description)
        if resolved:
            return (resolved, f"Ambiguous extension {ext} resolved via task description keywords ({resolved})")
        # No path, no task description signal → ambiguous (conservative: "both")
        return ("ambiguous", f"Ambiguous extension {ext} with no path or description signal — conservative fallback")

    # Extension not in any known set (e.g., .md, .yaml, .json, .sh, Makefile)
    # Check path segments as a last resort
    is_ui_path = _matches_ui_path(segments)
    is_api_path = _matches_api_path(segments)

    if is_ui_path and not is_api_path:
        return ("ui", f"Unknown extension {ext} in UI path")
    if is_api_path and not is_ui_path:
        return ("api", f"Unknown extension {ext} in API path")
    if is_ui_path and is_api_path:
        return ("ambiguous", f"Unknown extension {ext} in both UI and API paths")

    # Completely unrecognized — neither extension nor path signal matches
    return ("unrecognized", f"Unrecognized extension {ext} with no UI or API path signals")


def detect_change_type(
    files: List[str],
    task_description: str = "",
) -> Dict:
    """
    Classify a list of file paths and determine the overall change type.

    Args:
        files: List of file path strings (relative or absolute)
        task_description: Optional task description for ambiguous file resolution

    Returns:
        dict with change_type, ui_files, api_files, ambiguous_files,
        confidence (0.0-1.0), and reasoning string
    """
    if not files:
        return {
            "change_type": "unknown",
            "ui_files": [],
            "api_files": [],
            "ambiguous_files": [],
            "confidence": 1.0,
            "reasoning": "No files provided — cannot determine change type",
        }

    ui_files: List[str] = []
    api_files: List[str] = []
    ambiguous_files: List[str] = []
    unrecognized_files: List[str] = []
    reasoning_lines: List[str] = []

    for filepath in files:
        classification, reason = classify_file(filepath, task_description)
        reasoning_lines.append(f"{filepath}: {reason}")

        if classification == "ui":
            ui_files.append(filepath)
        elif classification == "api":
            api_files.append(filepath)
        elif classification == "ambiguous":
            ambiguous_files.append(filepath)
        else:
            # unrecognized — treat as neither (like docs, config)
            unrecognized_files.append(filepath)

    # --- Determine overall change_type ---
    has_ui = bool(ui_files)
    has_api = bool(api_files)
    has_ambiguous = bool(ambiguous_files)

    if has_ambiguous:
        # Ambiguous files that resolved to "ambiguous" make the whole result "both"
        # (conservative over-inclusive fallback per architecture doc)
        has_ui = True
        has_api = True

    if has_ui and has_api:
        change_type = "both"
        confidence = 0.9 if not has_ambiguous else 0.7
    elif has_ui:
        change_type = "ui"
        confidence = 1.0
    elif has_api:
        change_type = "api"
        confidence = 1.0
    elif unrecognized_files:
        # Only unrecognized files (docs, config, etc.) — no test tasks needed
        change_type = "unknown"
        confidence = 0.8
        reasoning_lines.append(
            "All files are unrecognized types (docs, config, etc.) — "
            "no UI or API changes detected"
        )
    else:
        change_type = "unknown"
        confidence = 1.0
        reasoning_lines.append("No files could be classified as UI or API")

    return {
        "change_type": change_type,
        "ui_files": ui_files,
        "api_files": api_files,
        "ambiguous_files": ambiguous_files,
        "confidence": confidence,
        "reasoning": "; ".join(reasoning_lines),
    }


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify file paths into change types (ui|api|both|unknown) for QE integration"
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="File paths to classify (space-separated)",
    )
    parser.add_argument(
        "--task-description",
        default="",
        help="Task description for resolving ambiguous files via keyword matching",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (default: human-readable)",
    )
    parser.add_argument(
        "--perf",
        action="store_true",
        help="Include timing measurement in output",
    )

    args = parser.parse_args()

    start = time.perf_counter()
    result = detect_change_type(
        files=args.files or [],
        task_description=args.task_description,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    if args.perf:
        result["elapsed_ms"] = round(elapsed_ms, 3)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Change type: {result['change_type']}")
        print(f"Confidence:  {result['confidence']:.0%}")
        if result["ui_files"]:
            print(f"UI files:    {', '.join(result['ui_files'])}")
        if result["api_files"]:
            print(f"API files:   {', '.join(result['api_files'])}")
        if result["ambiguous_files"]:
            print(f"Ambiguous:   {', '.join(result['ambiguous_files'])}")
        print(f"Reasoning:   {result['reasoning']}")
        if args.perf:
            print(f"Elapsed:     {elapsed_ms:.3f}ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
