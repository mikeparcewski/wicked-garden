#!/usr/bin/env python3
"""
scripts/qe/registry_lookup.py — Retrieve a QE artifact registry from StorageManager.

Looks up a registry by scenario slug in StorageManager("wicked-qe") and writes
the result to the given output path. Used as a fallback when the file-based
registry is missing (e.g. after a session restart or storage migration).

This script is stdlib-only (no external deps).

Usage:
    python3 registry_lookup.py --scenario-slug <slug> --output <path>

Exit codes:
    0  — Registry found and written to output path
    1  — Registry not found in StorageManager (or StorageManager error)
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve a QE artifact registry from StorageManager"
    )
    parser.add_argument(
        "--scenario-slug",
        required=True,
        help="Scenario identifier slug to look up",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path where the retrieved registry JSON will be written",
    )
    args = parser.parse_args()

    # Add scripts/ directory to path so _domain_store can be imported
    scripts_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(scripts_root))

    try:
        from _domain_store import DomainStore

        sm = DomainStore("wicked-qe")
        records = sm.list("registries", scenario_slug=args.scenario_slug)

        if not records:
            print(
                f"[qe/registry_lookup] no registry found for slug: {args.scenario_slug}",
                file=sys.stderr,
            )
            return 1

        # Use the most recent matching record
        registry_data = records[0]

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(registry_data, indent=2))

        print(
            f"[qe/registry_lookup] registry written to: {output_path}",
            file=sys.stderr,
        )
        return 0

    except Exception as exc:
        print(
            f"[qe/registry_lookup] StorageManager error: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
