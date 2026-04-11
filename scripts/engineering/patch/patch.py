#!/usr/bin/env python3
"""
wicked-patch CLI - Language-agnostic code generation and change propagation.

Generates patches for code changes and propagates them across all affected files.
Symbol resolution uses wicked-brain's symbols/dependents API. Patch generation
(add-field, rename, remove) additionally requires --db for symbol-level graph traversal.

Usage:
    # Plan what would be affected (brain-backed, no --db needed)
    patch plan SYMBOL_ID --change add_field

    # Plan with full symbol graph (requires local DB)
    patch plan SYMBOL_ID --change add_field --db symbols.db

    # Add a field to an entity/class
    patch add-field SYMBOL_ID --name email --type String --column EMAIL --db symbols.db

    # Rename a field across all usages
    patch rename SYMBOL_ID --old status --new providerStatus --db symbols.db

    # Remove a field everywhere
    patch remove SYMBOL_ID --field deprecated_field --db symbols.db

    # Apply generated patches
    patch apply patches.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add patch dir for local imports (generators, safety) and scripts root for shared modules (_brain_port)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # scripts/ — for _brain_port
sys.path.insert(0, str(Path(__file__).parent))                # scripts/engineering/patch/

from generators import (
    ChangeSpec,
    ChangeType,
    FieldSpec,
    PatchSet,
    GeneratorRegistry,
)
from generators.propagation_engine import PropagationEngine, PropagationPlan
from safety import (
    run_safety_checks,
    TransactionalApplicator,
    SafetyError,
    GitSafetyChecker,
    FreshnessChecker,
)


def _parse_version(v: str) -> tuple:
    """Parse semver string to comparable tuple."""
    import re
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def _brain_api(action: str, params: dict, port: Optional[int] = None) -> dict:
    """Call wicked-brain API. Returns empty dict on failure.

    Port is auto-discovered from project brain configs unless overridden.
    """
    import urllib.request
    if port is None:
        try:
            from _brain_port import resolve_port
            port = resolve_port()
        except ImportError:
            print("warning: _brain_port not found, falling back to port 4242", file=sys.stderr)
            port = 4242
    try:
        payload = json.dumps({"action": action, "params": params}).encode()
        req = urllib.request.Request(
            f"http://localhost:{port}/api",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def _resolve_symbol_id(symbol_id: str, db_path: Optional[Path]) -> str:
    """Resolve a partial symbol name to a full ID.

    Tries brain's symbols API first (returns file_path::Name when LSP data
    is available), then falls back to local SQLite if db_path is provided.
    """
    if not symbol_id or symbol_id.startswith("/") or "::" in symbol_id:
        return symbol_id

    # Try brain symbols API — fetch up to 10 to find one with a real file_path
    # (FTS results often have file_path=null for chunk-indexed entries; LSP-indexed
    # entries have the actual path and appear later in the result list)
    result = _brain_api("symbols", {"name": symbol_id, "limit": 10})
    for r in result.get("results", []):
        if r.get("file_path"):
            return r["id"]  # format: "file_path::SymbolName"

    # SQLite fallback
    if db_path:
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM symbols WHERE id LIKE ? LIMIT 1",
                (f"%/{symbol_id}",),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return row["id"]
        except Exception:
            pass

    return symbol_id


def _require_db(args_db: Optional[str]) -> Optional[Path]:
    """Resolve db_path from --db flag or return None with an informative error."""
    if args_db:
        p = Path(args_db)
        if not p.exists():
            print(f"Error: Database not found at {p}", file=sys.stderr)
            return None
        return p

    print(
        "Error: patch generation requires a local symbol database.\n"
        "  Pass --db <path-to-symbol.db> to use a local SQLite symbol graph.\n"
        "  The 'plan' command works without --db using wicked-brain's symbol API.",
        file=sys.stderr,
    )
    return None


def _assess_risk(plan: PropagationPlan, change_type: str = "") -> dict:
    """Assess risk level, confidence, and breaking change potential."""
    total = len(plan.all_affected)
    files = len(plan.files_affected)
    upstream = len(plan.upstream_impacts)

    # Determine risk level
    risk_reason = None
    if change_type == "remove_field":
        # Field removal is always a breaking change — even if no internal
        # references are found, external consumers (APIs, serialization,
        # database tools) may depend on the field.
        risk_level = "HIGH"
        if upstream == 0 and total <= 1:
            risk_reason = "no_internal_refs"
    elif change_type == "rename_field":
        if upstream > 10 or files > 6:
            risk_level = "HIGH"
        elif upstream > 0 or files > 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        # Orphaned field rename is as risky as removal — external consumers
        # may depend on the old name via APIs, serialization, or DB schemas.
        if upstream == 0 and total <= 1:
            risk_level = "HIGH"
            risk_reason = "no_internal_refs"
    elif change_type == "add_field":
        risk_level = "LOW"
    else:
        if total > 10 or files > 4:
            risk_level = "HIGH"
        elif total > 5 or files > 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

    # Determine confidence
    if total > 0 and files > 0:
        confidence = "HIGH"
    elif total > 0:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Detect breaking changes — removal is always breaking regardless of
    # internal references; renames break when upstream consumers exist.
    if change_type == "remove_field":
        breaking = True
    else:
        breaking = change_type == "rename_field" and upstream > 0

    # Check for test files in impacts
    test_refs = sum(
        1 for s in plan.all_affected
        if s.file_path and ("test" in s.file_path.lower() or "spec" in s.file_path.lower())
    )

    return {
        "risk_level": risk_level,
        "confidence": confidence,
        "breaking": breaking,
        "test_coverage": "GOOD" if test_refs > 0 else "NONE",
        "test_refs": test_refs,
        "risk_reason": risk_reason,
    }


def format_plan(plan: PropagationPlan, change_type: str = "") -> str:
    """Format a propagation plan for display."""
    risk = _assess_risk(plan, change_type)

    lines = [
        "=" * 60,
        "PROPAGATION PLAN",
        "=" * 60,
        "",
        f"Source: {plan.source_symbol.name}",
        f"  Type: {plan.source_symbol.type}",
        f"  File: {plan.source_symbol.file_path}",
        f"  Line: {plan.source_symbol.line_start}",
        "",
    ]

    if plan.direct_impacts:
        lines.append(f"Direct Impacts ({len(plan.direct_impacts)}):")
        for s in plan.direct_impacts[:10]:
            lines.append(f"  - {s.name} ({s.type}) @ {Path(s.file_path).name if s.file_path else 'N/A'}")
        if len(plan.direct_impacts) > 10:
            lines.append(f"  ... and {len(plan.direct_impacts) - 10} more")
        lines.append("")

    if plan.upstream_impacts:
        lines.append(f"Upstream Impacts ({len(plan.upstream_impacts)}):")
        for s in plan.upstream_impacts[:10]:
            lines.append(f"  - {s.name} ({s.type}) @ {Path(s.file_path).name if s.file_path else 'N/A'}")
        if len(plan.upstream_impacts) > 10:
            lines.append(f"  ... and {len(plan.upstream_impacts) - 10} more")
        lines.append("")

    if plan.downstream_impacts:
        lines.append(f"Downstream Impacts ({len(plan.downstream_impacts)}):")
        for s in plan.downstream_impacts[:10]:
            lines.append(f"  - {s.name} ({s.type}) @ {Path(s.file_path).name if s.file_path else 'N/A'}")
        if len(plan.downstream_impacts) > 10:
            lines.append(f"  ... and {len(plan.downstream_impacts) - 10} more")
        lines.append("")

    # Risk assessment section
    lines.append("-" * 60)
    lines.append("Risk Assessment:")
    lines.append(f"  Risk level: {risk['risk_level']}")
    lines.append(f"  Confidence: {risk['confidence']}")
    if risk["breaking"]:
        lines.append(f"  Breaking change: YES (affects {len(plan.upstream_impacts)} upstream dependencies)")
    else:
        lines.append(f"  Breaking change: NO")
    lines.append(f"  Test coverage: {risk['test_coverage']} ({risk['test_refs']} test references found)")
    if risk.get("risk_reason") == "no_internal_refs":
        lines.append("  WARNING: Field has no internal references — may be used by external API clients or database tools")
        lines.append("  Audit API contracts and external integrations before proceeding")
    lines.append("")

    lines.extend([
        "-" * 60,
        f"Total: {len(plan.all_affected)} symbols in {len(plan.files_affected)} files",
        "=" * 60,
    ])

    return "\n".join(lines)


def format_patches(patch_set: PatchSet, verbose: bool = False) -> str:
    """Format a patch set for display."""
    lines = [
        "=" * 60,
        "GENERATED PATCHES",
        "=" * 60,
        "",
        patch_set.summary(),
        "",
    ]

    if patch_set.errors:
        lines.append("ERRORS:")
        for err in patch_set.errors:
            lines.append(f"  ✗ {err}")
        lines.append("")

    if patch_set.warnings:
        lines.append("WARNINGS:")
        for warn in patch_set.warnings:
            lines.append(f"  ⚠ {warn}")
        lines.append("")

    lines.append("PATCHES:")
    for file_path, patches in patch_set.patches_by_file().items():
        lines.append(f"\n  {file_path}")
        for patch in patches:
            lines.append(f"    [{patch.line_start}-{patch.line_end}] {patch.description}")
            if verbose:
                if patch.old_content:
                    for old_line in patch.old_content.split("\n")[:3]:
                        lines.append(f"      - {old_line}")
                if patch.new_content:
                    for new_line in patch.new_content.split("\n")[:5]:
                        lines.append(f"      + {new_line}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def _cmd_plan_brain(args) -> int:
    """Show a brain-backed propagation plan (file-level, no local DB needed)."""
    # Strip path prefix if user passed a full symbol ID
    symbol_name = args.symbol_id.split("::")[-1] if "::" in args.symbol_id else args.symbol_id

    sym_result = _brain_api("symbols", {"name": symbol_name, "limit": 5})
    symbols = sym_result.get("results", [])

    dep_result = _brain_api("dependents", {"name": symbol_name})
    dep_files = dep_result.get("files", [])

    if not symbols and not dep_files:
        print(f"Error: '{symbol_name}' not found in brain index.", file=sys.stderr)
        print("Index the codebase first, or pass --db <symbol.db> for local SQLite planning.", file=sys.stderr)
        return 1

    source = symbols[0] if symbols else {"name": symbol_name, "type": "unknown", "file_path": None}
    change_type = args.change if args.change else "modify_field"

    print("=" * 60)
    print("PROPAGATION PLAN  [brain-backed, file-level]")
    print("=" * 60)
    print()
    print(f"Source: {source.get('name', symbol_name)}")
    print(f"  Type: {source.get('type', 'unknown')}")
    file_path = source.get("file_path")
    print(f"  File: {file_path or '(chunk-indexed — run ingest with LSP for exact location)'}")
    print()

    if dep_files:
        print(f"Dependent Files ({len(dep_files)}):")
        for f in dep_files[:15]:
            print(f"  - {f}")
        if len(dep_files) > 15:
            print(f"  ... and {len(dep_files) - 15} more")
    else:
        print("No dependent files found in brain index.")
    print()
    print("Note: Pass --db <symbol.db> for symbol-level graph traversal and patch generation.")
    print("=" * 60)

    if args.json:
        print("\n" + json.dumps({
            "source": {
                "name": source.get("name", symbol_name),
                "type": source.get("type", "unknown"),
                "file": file_path,
            },
            "change_type": change_type,
            "files_affected": dep_files,
            "planning_source": "brain",
        }, indent=2))

    return 0


def cmd_plan(args):
    """Show propagation plan without generating patches."""
    if not args.db:
        return _cmd_plan_brain(args)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return 1

    resolved_id = _resolve_symbol_id(args.symbol_id, db_path)

    engine = PropagationEngine(db_path)
    try:
        change_type = ChangeType(args.change) if args.change else ChangeType.MODIFY_FIELD
        change_spec = ChangeSpec(
            change_type=change_type,
            target_symbol_id=resolved_id,
        )

        plan = engine.plan_propagation(change_spec, max_depth=args.depth)
        print(format_plan(plan, change_type=change_type.value))

        if args.json:
            risk = _assess_risk(plan, change_type.value)
            plan_dict = {
                "source": {
                    "id": plan.source_symbol.id,
                    "name": plan.source_symbol.name,
                    "type": plan.source_symbol.type,
                    "file": plan.source_symbol.file_path,
                },
                "impacts": {
                    "direct": len(plan.direct_impacts),
                    "upstream": len(plan.upstream_impacts),
                    "downstream": len(plan.downstream_impacts),
                },
                "files_affected": list(plan.files_affected),
                "risk_assessment": risk,
            }
            print("\n" + json.dumps(plan_dict, indent=2))

        return 0

    finally:
        engine.close()


def cmd_add_field(args):
    """Add a field and propagate to all affected files."""
    db_path = _require_db(args.db)
    if db_path is None:
        return 1

    resolved_id = _resolve_symbol_id(args.symbol_id, db_path)

    engine = PropagationEngine(db_path)
    try:
        field_spec = FieldSpec(
            name=args.name,
            type=args.type,
            nullable=not args.required,
            column_name=args.column,
            label=args.label,
            validation={"required": True} if args.required else {},
        )

        change_spec = ChangeSpec(
            change_type=ChangeType.ADD_FIELD,
            target_symbol_id=resolved_id,
            field_spec=field_spec,
        )

        patch_set = engine.generate_patches(change_spec, max_depth=args.depth)
        print(format_patches(patch_set, verbose=args.verbose))

        if patch_set.has_errors:
            return 1

        # Save patches to file
        if args.output:
            save_patches(patch_set, args.output)
            print(f"\nPatches saved to {args.output}")

        # Apply if requested
        if args.apply:
            return apply_patches_interactive(
                patch_set, db_path,
                force=getattr(args, 'force', False),
                skip_git=getattr(args, 'skip_git', False),
            )

        return 0

    finally:
        engine.close()


def cmd_rename(args):
    """Rename a field across all usages."""
    db_path = _require_db(args.db)
    if db_path is None:
        return 1

    resolved_id = _resolve_symbol_id(args.symbol_id, db_path)

    engine = PropagationEngine(db_path)
    try:
        change_spec = ChangeSpec(
            change_type=ChangeType.RENAME_FIELD,
            target_symbol_id=resolved_id,
            old_name=args.old,
            new_name=args.new,
        )

        patch_set = engine.generate_patches(change_spec, max_depth=args.depth)
        print(format_patches(patch_set, verbose=args.verbose))

        if args.output:
            save_patches(patch_set, args.output)
            print(f"\nPatches saved to {args.output}")

        if args.apply and not patch_set.has_errors:
            return apply_patches_interactive(
                patch_set, db_path,
                force=getattr(args, 'force', False),
                skip_git=getattr(args, 'skip_git', False),
            )

        return 0 if not patch_set.has_errors else 1

    finally:
        engine.close()


def cmd_remove(args):
    """Remove a field and all its usages."""
    db_path = _require_db(args.db)
    if db_path is None:
        return 1

    resolved_id = _resolve_symbol_id(args.symbol_id, db_path)

    engine = PropagationEngine(db_path)
    try:
        change_spec = ChangeSpec(
            change_type=ChangeType.REMOVE_FIELD,
            target_symbol_id=resolved_id,
            old_name=args.field,
        )

        patch_set = engine.generate_patches(change_spec, max_depth=args.depth)
        print(format_patches(patch_set, verbose=args.verbose))

        if args.output:
            save_patches(patch_set, args.output)

        if args.apply and not patch_set.has_errors:
            print("\n⚠️  WARNING: This will DELETE code!")
            return apply_patches_interactive(
                patch_set, db_path,
                force=getattr(args, 'force', False),
                skip_git=getattr(args, 'skip_git', False),
            )

        return 0 if not patch_set.has_errors else 1

    finally:
        engine.close()


def cmd_apply(args):
    """Apply patches from a saved file."""
    patches_file = Path(args.patches_file)
    if not patches_file.exists():
        print(f"Error: Patches file not found: {patches_file}", file=sys.stderr)
        return 1

    with open(patches_file) as f:
        data = json.load(f)

    print(f"Loaded {len(data.get('patches', []))} patches from {patches_file}")
    print(f"Files affected: {len(data.get('files_affected', []))}")

    if args.dry_run:
        print("\nDry run - no changes made")
        return 0

    # Reconstruct patches
    from generators import Patch, PatchSet, ChangeSpec, ChangeType
    patches = [
        Patch(
            file_path=p['file'],
            line_start=p['line_start'],
            line_end=p['line_end'],
            old_content=p['old'],
            new_content=p['new'],
            description=p['description'],
            confidence=p.get('confidence', 'high'),
        )
        for p in data.get('patches', [])
    ]

    patch_set = PatchSet(
        change_spec=ChangeSpec(
            change_type=ChangeType(data.get('change_type', 'modify_field')),
            target_symbol_id=data.get('target', ''),
        ),
        patches=patches,
    )

    db_path = Path(args.db) if args.db else None

    return apply_patches_interactive(
        patch_set, db_path,
        force=getattr(args, 'force', False),
        skip_git=getattr(args, 'skip_git', False),
    )


def cmd_generators(args):
    """List available generators."""
    print("Available Generators:\n")
    print(f"{'Extension':<12} {'Generator':<12} {'Symbol Types'}")
    print("-" * 60)
    for ext in sorted(GeneratorRegistry.supported_extensions()):
        gen = GeneratorRegistry.list_generators().get(ext)
        if gen:
            types = ", ".join(sorted(gen.symbol_types))
            print(f"{ext:<12} {gen.name:<12} {types}")


def save_patches(patch_set: PatchSet, output_path: str):
    """Save patches to a JSON file, with a companion manifest.json."""
    data = patch_set.to_dict()
    data['generated_at'] = datetime.now().isoformat()
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Generate manifest.json alongside patches file
    output_dir = Path(output_path).parent
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "patches_file": Path(output_path).name,
        "generated_at": data['generated_at'],
        "change_type": data.get('change_type', ''),
        "target": data.get('target', ''),
        "files_affected": data.get('files_affected', []),
        "patch_count": len(data.get('patches', [])),
        "has_errors": patch_set.has_errors,
        "warnings": patch_set.warnings or [],
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def apply_patches_interactive(
    patch_set: PatchSet,
    db_path: Optional[Path],
    force: bool = False,
    skip_git: bool = False,
) -> int:
    """
    Interactively apply patches with safety checks.

    Args:
        patch_set: Patches to apply
        db_path: Path to symbol database for freshness check, or None to skip it
        force: Skip freshness check
        skip_git: Skip git clean check
    """
    if not patch_set.patches:
        print("\nNo patches to apply.")
        return 0

    files = list(patch_set.files_affected)

    # Run safety checks
    print("\nRunning safety checks...")
    passed, results = run_safety_checks(
        files=files,
        db_path=db_path,
        force=force,
        skip_git=skip_git,
    )

    for result in results:
        if result.passed:
            print(f"  ✓ {result.message}")
        else:
            print(f"  ✗ {result.message}")

    if not passed:
        print("\nSafety checks failed. Use --force to bypass freshness check.")
        return 1

    # Confirm
    confirm = input(f"\nApply {len(patch_set.patches)} patches to {len(files)} files? [y/N] ")
    if confirm.lower() != 'y':
        print("\nAborted.")
        return 0

    # Apply with transactional safety
    print("\nApplying patches...")
    applicator = TransactionalApplicator(patch_set.patches)
    result = applicator.apply()

    if result.success:
        print(f"\n✓ Applied {len(result.files_modified)} files successfully")
        return 0
    else:
        print(f"\n✗ Failed: {result.error}")
        if result.rolled_back:
            print("  All changes have been rolled back.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="wicked-patch: Language-agnostic code generation and change propagation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show what would be affected
  patch plan "path/Entity.java::EntityName" --change add_field

  # Add a new field
  patch add-field "path/Entity.java::EntityName" --name email --type String

  # Rename a field everywhere
  patch rename "path/Entity.java::EntityName" --old status --new state

  # Save patches for review
  patch add-field SYMBOL --name foo --type String --output patches.json

  # Apply saved patches
  patch apply patches.json
""",
    )

    parser.add_argument("--db", help="Path to symbol database (required until wicked-brain#23 lands)")
    parser.add_argument("--version", action="version", version="wicked-patch 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # plan
    plan_p = subparsers.add_parser("plan", help="Show propagation plan")
    plan_p.add_argument("symbol_id", help="Symbol ID to analyze")
    plan_p.add_argument("--change", help="Change type (add_field, rename_field, etc.)")
    plan_p.add_argument("--depth", type=int, default=5, help="Max traversal depth")
    plan_p.add_argument("--json", action="store_true", help="Output JSON")

    # add-field
    add_p = subparsers.add_parser("add-field", help="Add a field")
    add_p.add_argument("symbol_id", help="Target symbol ID")
    add_p.add_argument("--name", required=True, help="Field name")
    add_p.add_argument("--type", required=True, help="Field type")
    add_p.add_argument("--column", help="Database column name")
    add_p.add_argument("--label", help="UI label")
    add_p.add_argument("--required", action="store_true", help="Field is required")
    add_p.add_argument("--depth", type=int, default=5, help="Propagation depth")
    add_p.add_argument("--output", "-o", help="Save patches to file")
    add_p.add_argument("--apply", action="store_true", help="Apply patches")
    add_p.add_argument("--force", action="store_true", help="Skip freshness check")
    add_p.add_argument("--skip-git", action="store_true", help="Skip git clean check")
    add_p.add_argument("--verbose", "-v", action="store_true", help="Show diffs")

    # rename
    rename_p = subparsers.add_parser("rename", help="Rename a field")
    rename_p.add_argument("symbol_id", help="Target symbol ID")
    rename_p.add_argument("--old", required=True, help="Current name")
    rename_p.add_argument("--new", required=True, help="New name")
    rename_p.add_argument("--depth", type=int, default=5)
    rename_p.add_argument("--output", "-o", help="Save patches to file")
    rename_p.add_argument("--apply", action="store_true")
    rename_p.add_argument("--force", action="store_true", help="Skip freshness check")
    rename_p.add_argument("--skip-git", action="store_true", help="Skip git clean check")
    rename_p.add_argument("--verbose", "-v", action="store_true")

    # remove
    remove_p = subparsers.add_parser("remove", help="Remove a field")
    remove_p.add_argument("symbol_id", help="Target symbol ID")
    remove_p.add_argument("--field", required=True, help="Field name to remove")
    remove_p.add_argument("--depth", type=int, default=5)
    remove_p.add_argument("--output", "-o", help="Save patches to file")
    remove_p.add_argument("--apply", action="store_true")
    remove_p.add_argument("--force", action="store_true", help="Skip freshness check")
    remove_p.add_argument("--skip-git", action="store_true", help="Skip git clean check")
    remove_p.add_argument("--verbose", "-v", action="store_true")

    # apply
    apply_p = subparsers.add_parser("apply", help="Apply patches from file")
    apply_p.add_argument("patches_file", help="Patches JSON file")
    apply_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    apply_p.add_argument("--force", action="store_true", help="Skip freshness check")
    apply_p.add_argument("--skip-git", action="store_true", help="Skip git clean check")

    # generators
    gen_p = subparsers.add_parser("generators", help="List available generators")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "plan": cmd_plan,
        "add-field": cmd_add_field,
        "rename": cmd_rename,
        "remove": cmd_remove,
        "apply": cmd_apply,
        "generators": cmd_generators,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
