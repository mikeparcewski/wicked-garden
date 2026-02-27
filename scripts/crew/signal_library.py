#!/usr/bin/env python3
"""
Semantic Signal Detection for wicked-crew using ChromaDB.

Provides embedding-based signal matching as an optional enhancement
to keyword-based detection. Falls back gracefully if ChromaDB is
not installed.

Storage:
- Default signals: scripts/data/default_signals.jsonl
- User signals: ~/.something-wicked/wicked-crew/signals/*.jsonl

Usage:
  signal_library.py detect "project description text"
  signal_library.py save --category security --text "example signal" [--weight 1.0]
  signal_library.py list [--category NAME] [--source default|user]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Lazy-loaded module-level library instance
_library_instance = None

USER_SIGNALS_DIR = Path.home() / ".something-wicked" / "wicked-crew" / "signals"
DEFAULT_SIGNALS_PATH = Path(__file__).parent / "data" / "default_signals.jsonl"


class SignalLibrary:
    """In-memory semantic signal library using ChromaDB."""

    def __init__(self):
        self._collection = None
        self._client = None
        self._loaded = False
        self._entries: List[Dict] = []  # Track all loaded entries for list command

    def _ensure_loaded(self):
        """Lazy initialization — only load ChromaDB when first needed."""
        if self._loaded:
            return
        try:
            import chromadb
            self._client = chromadb.Client()
            self._collection = self._client.create_collection(
                name="signal_library",
                metadata={"hnsw:space": "cosine"},
            )
            self._load_defaults()
            self._load_user_libraries()
            self._loaded = True
        except ImportError:
            self._collection = None
            self._loaded = True  # Mark loaded even without ChromaDB

    def _load_jsonl(self, path: Path, source: str) -> int:
        """Load signal definitions from a JSONL file. Returns count loaded."""
        if not path.exists() or not self._collection:
            return 0

        count = 0
        with open(path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_id = f"{source}_{i}"
                self._collection.add(
                    documents=[entry["text"]],
                    metadatas=[{
                        "category": entry["category"],
                        "weight": entry.get("weight", 1.0),
                        "source": source,
                    }],
                    ids=[entry_id],
                )
                self._entries.append({**entry, "source": source, "id": entry_id})
                count += 1

        return count

    def _load_defaults(self):
        """Load from scripts/data/default_signals.jsonl."""
        self._load_jsonl(DEFAULT_SIGNALS_PATH, source="default")

    def _load_user_libraries(self):
        """Load from ~/.something-wicked/wicked-crew/signals/*.jsonl."""
        if USER_SIGNALS_DIR.exists():
            for jsonl_file in sorted(USER_SIGNALS_DIR.glob("*.jsonl")):
                self._load_jsonl(jsonl_file, source=jsonl_file.stem)

    def detect(self, text: str, top_k: int = 5) -> Dict[str, float]:
        """Query semantic similarity per signal category.

        Returns Dict[category, confidence] where confidence is
        max weighted similarity score among top-K matches for that category.
        """
        self._ensure_loaded()
        if not self._collection or self._collection.count() == 0:
            return {}

        n_results = min(top_k * 12, self._collection.count())  # 12 categories
        results = self._collection.query(
            query_texts=[text],
            n_results=n_results,
        )

        category_scores: Dict[str, float] = {}
        if results and results.get("distances"):
            for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
                cat = meta["category"]
                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                similarity = 1.0 - (dist / 2.0)
                weight = meta.get("weight", 1.0)
                score = similarity * weight
                if cat not in category_scores or score > category_scores[cat]:
                    category_scores[cat] = round(score, 3)

        return category_scores

    def list_entries(
        self, category: Optional[str] = None, source: Optional[str] = None
    ) -> List[Dict]:
        """List loaded signal entries with optional filters."""
        self._ensure_loaded()
        entries = self._entries
        if category:
            entries = [e for e in entries if e["category"] == category]
        if source:
            entries = [e for e in entries if e["source"] == source]
        return entries

    @property
    def available(self) -> bool:
        """Whether ChromaDB is available."""
        self._ensure_loaded()
        return self._collection is not None


def get_library() -> SignalLibrary:
    """Get or create the module-level signal library instance."""
    global _library_instance
    if _library_instance is None:
        _library_instance = SignalLibrary()
    return _library_instance


def save_user_signal(category: str, text: str, weight: float = 1.0,
                     library_name: str = "custom") -> str:
    """Append a signal definition to a user library file."""
    USER_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    target = USER_SIGNALS_DIR / f"{library_name}.jsonl"

    entry = {"category": category, "text": text, "weight": weight}
    with open(target, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Invalidate cached library instance so next detect() picks up new entry
    global _library_instance
    _library_instance = None

    return str(target)


def main():
    parser = argparse.ArgumentParser(description="Semantic signal detection for wicked-crew")
    sub = parser.add_subparsers(dest="command")

    # detect
    det = sub.add_parser("detect", help="Detect signals in text")
    det.add_argument("text", help="Text to analyze")
    det.add_argument("--json", action="store_true")
    det.add_argument("--top-k", type=int, default=5)

    # save
    sav = sub.add_parser("save", help="Save a signal to user library")
    sav.add_argument("--category", required=True)
    sav.add_argument("--text", required=True)
    sav.add_argument("--weight", type=float, default=1.0)
    sav.add_argument("--library", default="custom", help="Library name (default: custom)")

    # list
    lst = sub.add_parser("list", help="List loaded signals")
    lst.add_argument("--category", help="Filter by category")
    lst.add_argument("--source", help="Filter by source (default, user, or library name)")
    lst.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "detect":
        lib = get_library()
        if not lib.available:
            print("ChromaDB not installed. Install with: pip install chromadb", file=sys.stderr)
            print("{}")
            return

        scores = lib.detect(args.text, top_k=args.top_k)
        if args.json:
            print(json.dumps(scores, indent=2))
        else:
            if scores:
                for cat, score in sorted(scores.items(), key=lambda x: -x[1]):
                    print(f"  {cat}: {score:.1%}")
            else:
                print("No signals detected.")

    elif args.command == "save":
        path = save_user_signal(args.category, args.text, args.weight, args.library)
        print(f"Signal saved to {path}")

    elif args.command == "list":
        lib = get_library()
        entries = lib.list_entries(
            category=getattr(args, "category", None),
            source=getattr(args, "source", None),
        )

        if getattr(args, "json", False):
            print(json.dumps(entries, indent=2))
        else:
            for entry in entries:
                print(f"  [{entry['source']}] {entry['category']}: "
                      f"{entry['text'][:60]}... (w={entry.get('weight', 1.0)})")
            print(f"\n{len(entries)} signals loaded.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
