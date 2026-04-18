#!/usr/bin/env python3
"""
scripts/qe/registry_store.py — Persist an artifact registry to DomainStore.

Reads a registry JSON file from disk and stores it in DomainStore("wicked-qe")
using local JSON storage.

This script is stdlib-only (no external deps) so it is safe to call from any
context, including agent steps that may not have uv available.

Usage:
    python3 registry_store.py --scenario-slug <slug> --registry-path <path>

Exit codes:
    0  — Registry stored successfully (or no-op on empty/invalid registry)
    1  — Unrecoverable error (file not found, parse error)

The script always exits 0 on DomainStore errors (fail-open pattern).
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persist a QE artifact registry to DomainStore"
    )
    parser.add_argument(
        "--scenario-slug",
        required=True,
        help="Scenario identifier slug (e.g. 'my-scenario-run-123')",
    )
    parser.add_argument(
        "--registry-path",
        required=True,
        help="Path to the registry JSON file written by the executor",
    )
    args = parser.parse_args()

    registry_file = Path(args.registry_path)
    if not registry_file.exists():
        print(
            f"[qe/registry_store] registry file not found: {registry_file}",
            file=sys.stderr,
        )
        return 1

    try:
        registry_data = json.loads(registry_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"[qe/registry_store] failed to parse registry file: {exc}",
            file=sys.stderr,
        )
        return 1

    if not isinstance(registry_data, dict):
        print(
            "[qe/registry_store] registry file must contain a JSON object",
            file=sys.stderr,
        )
        return 1

    # Inject scenario slug so lookups work without the caller needing to know it
    registry_data["scenario_slug"] = args.scenario_slug

    # Add scripts/ directory to path so _domain_store can be imported
    scripts_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(scripts_root))

    try:
        from _domain_store import DomainStore

        sm = DomainStore("wicked-qe")

        # Check for an existing record for this slug so we don't create duplicates
        all_registries = sm.list("registries", scenario_slug=args.scenario_slug)
        existing = [r for r in all_registries if r.get("scenario_slug") == args.scenario_slug]
        if existing:
            # Update the most recent record rather than accumulating duplicates
            record_id = existing[0].get("id") or existing[0].get("_id")
            if record_id:
                sm.update("registries", str(record_id), registry_data)
                print(
                    f"[qe/registry_store] updated registry for slug: {args.scenario_slug}",
                    file=sys.stderr,
                )
            else:
                # No usable ID — create a new record
                sm.create("registries", registry_data)
                print(
                    f"[qe/registry_store] created registry for slug: {args.scenario_slug}",
                    file=sys.stderr,
                )
        else:
            sm.create("registries", registry_data)
            print(
                f"[qe/registry_store] stored registry for slug: {args.scenario_slug}",
                file=sys.stderr,
            )
    except Exception as exc:
        # Fail open — the file-based registry written by the executor is still valid
        print(
            f"[qe/registry_store] DomainStore error (non-fatal): {exc}",
            file=sys.stderr,
        )

    # Emit scenario run event to wicked-bus (additive — fire-and-forget, fail-open).
    # Result is derived from registry completeness: no missing items = pass, else fail.
    try:
        from _bus import emit_event
        from _session import SessionState

        completeness = registry_data.get("completeness") or {}
        missing = completeness.get("missing") or []
        required_count = completeness.get("required_count") or 0
        captured_count = completeness.get("captured_count") or 0

        result = "pass" if not missing else "fail"
        # coverage_delta: ratio of captured-to-required as a simple proxy (0.0-1.0).
        # No prior-run comparison is available at this layer, so delta is reported
        # as the current completion ratio. Consumers that track diffs should compute
        # deltas from successive events.
        if required_count > 0:
            coverage_delta = round(captured_count / required_count, 3)
        else:
            coverage_delta = 0.0

        try:
            state = SessionState.load()
            chain_id = getattr(state, "active_chain_id", None) or ""
        except Exception:
            chain_id = ""

        emit_event(
            "wicked.scenario.run",
            {
                "scenario_id": args.scenario_slug,
                "result": result,
                "coverage_delta": coverage_delta,
            },
            chain_id=chain_id,
        )
    except Exception:
        pass  # fail open — bus emit must never break the caller

    return 0


if __name__ == "__main__":
    sys.exit(main())
