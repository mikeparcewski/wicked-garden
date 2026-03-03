#!/usr/bin/env python3
"""
Migrate wicked-garden local JSON file tree to SQLite.

Scans ~/.something-wicked/wicked-garden/local/{domain}/{source}/*.json
and INSERT OR IGNORE each record into SqliteStore.

Also handles flat files at local/{domain}/{id}.json — source becomes "default".
Safe to run multiple times — idempotent.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger("_migrate_local")

_DEFAULT_DB = "~/.something-wicked/wicked-garden/wicked-garden.db"
_DEFAULT_ROOT = "~/.something-wicked/wicked-garden/local"


def _load_sqlite_store():
    spec = importlib.util.spec_from_file_location(
        "_sqlite_store", Path(__file__).parent / "_sqlite_store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SqliteStore


def _migrate_file(store, json_file: Path, domain: str, source: str, stats: dict, dry_run: bool) -> None:
    record_id = json_file.stem
    stats["scanned"] += 1
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"expected dict, got {type(data).__name__}")
        logger.debug("migrate %s/%s/%s from %s", domain, source, record_id, json_file)
        if dry_run:
            stats["inserted"] += 1
            return
        if store.get(domain, source, record_id) is not None:
            logger.debug("skip %s/%s/%s — already in DB", domain, source, record_id)
            stats["skipped"] += 1
        else:
            store.create(domain, source, record_id, data)
            stats["inserted"] += 1
    except Exception as exc:
        logger.warning("skip %s: %s", json_file, exc)
        stats["errors"] += 1


def migrate(db_path: str, local_root: str, dry_run: bool = False) -> dict:
    """
    Walk local_root and insert every JSON record into SqliteStore.

    Nested layout: local/{domain}/{source}/{id}.json
    Flat layout:   local/{domain}/{id}.json  → source="default"

    Returns: {"scanned": N, "inserted": N, "skipped": N, "errors": N}
    """
    SqliteStore = _load_sqlite_store()
    store = SqliteStore(str(db_path))
    stats = {"scanned": 0, "inserted": 0, "skipped": 0, "errors": 0}

    root = Path(local_root)
    if not root.exists():
        logger.warning("local root does not exist: %s", root)
        return stats

    for domain_dir in sorted(root.iterdir()):
        if not domain_dir.is_dir():
            continue
        domain = domain_dir.name
        logger.debug("domain: %s", domain)

        for child in sorted(domain_dir.iterdir()):
            if child.is_dir():
                # Nested: domain/source/id.json
                source = child.name
                for json_file in sorted(child.glob("*.json")):
                    _migrate_file(store, json_file, domain, source, stats, dry_run)
            elif child.suffix == ".json":
                # Flat: domain/id.json → source="default"
                _migrate_file(store, child, domain, "default", stats, dry_run)

    store.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate wicked-garden local JSON files into SQLite.")
    parser.add_argument("--db", default=_DEFAULT_DB, help="Path to SQLite database (default: %(default)s)")
    parser.add_argument("--root", default=_DEFAULT_ROOT, help="Path to local JSON root (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="Scan and count without writing to DB")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser()
    local_root = str(Path(args.root).expanduser())

    if args.dry_run:
        logger.info("DRY RUN — no writes will occur")

    stats = migrate(str(db_path), local_root, args.dry_run)
    print(json.dumps(stats, indent=2))
