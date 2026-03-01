#!/usr/bin/env python3
"""
Migration script: Convert old single-JSON format to new folder-based format.

Usage:
    python migrate.py              # Preview what would be migrated
    python migrate.py --execute    # Actually migrate
    python migrate.py --cleanup    # Remove old files after migration
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts root to path for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import get_local_path

# Paths
DATA_DIR = Path(os.environ.get(
    'WICKED_KANBAN_DATA_DIR',
    str(get_local_path("wicked-kanban"))
))
OLD_PROJECTS_DIR = DATA_DIR / 'projects'
BACKUP_DIR = DATA_DIR / 'backup_v1'


def get_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_old_format(project_path: Path) -> bool:
    """Check if a file is old single-JSON format."""
    return project_path.is_file() and project_path.suffix == '.json'


def is_new_format(project_path: Path) -> bool:
    """Check if a directory is new folder format."""
    return project_path.is_dir() and (project_path / 'project.json').exists()


def migrate_project(old_file: Path, execute: bool = False) -> dict:
    """Migrate a single project from old to new format."""
    result = {
        'old_path': str(old_file),
        'project_id': old_file.stem,
        'tasks': 0,
        'initiatives': 0,
        'status': 'preview'
    }

    try:
        old_data = json.loads(old_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, IOError) as e:
        result['status'] = f'error: {e}'
        return result

    project_id = old_data.get('id', old_file.stem)
    result['project_id'] = project_id
    result['project_name'] = old_data.get('name', 'Unknown')
    result['tasks'] = len(old_data.get('tasks', []))
    result['initiatives'] = len(old_data.get('initiatives', []))

    if not execute:
        return result

    # Create new directory structure
    new_dir = OLD_PROJECTS_DIR / project_id
    tasks_dir = new_dir / 'tasks'
    initiatives_dir = new_dir / 'initiatives'
    activity_dir = new_dir / 'activity'

    new_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(exist_ok=True)
    initiatives_dir.mkdir(exist_ok=True)
    activity_dir.mkdir(exist_ok=True)

    # Write project.json
    project_meta = {
        'id': project_id,
        'name': old_data.get('name', ''),
        'description': old_data.get('description'),
        'repo_path': old_data.get('metadata', {}).get('repo_path') if old_data.get('metadata') else None,
        'created_at': old_data.get('createdAt', get_utc_timestamp()),
        'created_by': old_data.get('createdBy', 'claude'),
        'archived': old_data.get('archived', False)
    }
    (new_dir / 'project.json').write_text(json.dumps(project_meta, indent=2))

    # Write swimlanes.json
    old_swimlanes = old_data.get('swimlanes', [])
    new_swimlanes = []
    swimlane_id_map = {}  # old_id -> new_id

    for sl in old_swimlanes:
        old_id = sl.get('id')
        # Normalize swimlane IDs
        name = sl.get('name', '')
        if name.lower() == 'to do':
            new_id = 'todo'
        elif name.lower() == 'in progress':
            new_id = 'in_progress'
        elif name.lower() == 'done':
            new_id = 'done'
        else:
            new_id = old_id

        swimlane_id_map[old_id] = new_id
        new_swimlanes.append({
            'id': new_id,
            'name': name,
            'order': sl.get('order', 0),
            'is_complete': sl.get('isComplete', False),
            'color': sl.get('color')
        })

    (new_dir / 'swimlanes.json').write_text(json.dumps(new_swimlanes, indent=2))

    # Build task index
    index = {'by_swimlane': {}, 'by_initiative': {}, 'all': []}

    # Migrate tasks
    for task in old_data.get('tasks', []):
        task_id = task.get('id')
        old_swimlane_id = task.get('swimlaneId', '')
        new_swimlane = swimlane_id_map.get(old_swimlane_id, 'todo')
        initiative_id = task.get('initiativeId')

        new_task = {
            'id': task_id,
            'name': task.get('name', ''),
            'description': task.get('description'),
            'swimlane': new_swimlane,
            'order': task.get('order', 0),
            'priority': task.get('priority', 'P2'),
            'initiative_id': initiative_id,
            'assigned_to': task.get('assignedTo'),
            'depends_on': task.get('dependsOn', []),
            'commits': task.get('commitHashes', []),
            'artifacts': task.get('artifacts', []),
            'metadata': task.get('metadata'),
            'created_at': get_utc_timestamp(),
            'created_by': task.get('createdBy', 'claude'),
            'updated_at': get_utc_timestamp()
        }

        (tasks_dir / f'{task_id}.json').write_text(json.dumps(new_task, indent=2))

        # Update index
        index['all'].append(task_id)
        index['by_swimlane'].setdefault(new_swimlane, []).append(task_id)
        if initiative_id:
            index['by_initiative'].setdefault(initiative_id, []).append(task_id)

    (tasks_dir / 'index.json').write_text(json.dumps(index, indent=2))

    # Migrate initiatives
    for initiative in old_data.get('initiatives', []):
        init_id = initiative.get('id')
        new_init = {
            'id': init_id,
            'name': initiative.get('name', ''),
            'goal': initiative.get('goal'),
            'status': initiative.get('status', 'active'),
            'start_date': initiative.get('startDate'),
            'end_date': initiative.get('endDate'),
            'created_at': initiative.get('createdAt', get_utc_timestamp()),
            'created_by': initiative.get('createdBy', 'claude')
        }
        (initiatives_dir / f'{init_id}.json').write_text(json.dumps(new_init, indent=2))

    # Write initial activity log
    activity_record = {
        'ts': get_utc_timestamp(),
        'type': 'migrated',
        'from_format': 'v1_single_json',
        'tasks_migrated': len(old_data.get('tasks', [])),
        'initiatives_migrated': len(old_data.get('initiatives', []))
    }
    activity_file = activity_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    with open(activity_file, 'a') as f:
        f.write(json.dumps(activity_record) + '\n')

    result['status'] = 'migrated'
    return result


def backup_old_files(old_files: list):
    """Backup old JSON files before migration."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for f in old_files:
        dest = BACKUP_DIR / f.name
        shutil.copy2(f, dest)
    print(f"Backed up {len(old_files)} files to {BACKUP_DIR}")


def cleanup_old_files(old_files: list):
    """Remove old JSON files after successful migration."""
    for f in old_files:
        f.unlink()
    print(f"Removed {len(old_files)} old project files")


def main():
    execute = '--execute' in sys.argv
    cleanup = '--cleanup' in sys.argv

    if not OLD_PROJECTS_DIR.exists():
        print(f"Projects directory not found: {OLD_PROJECTS_DIR}")
        return 1

    # Find old format files
    old_files = [f for f in OLD_PROJECTS_DIR.iterdir() if is_old_format(f)]

    if not old_files:
        print("No old format projects found to migrate.")
        return 0

    print(f"Found {len(old_files)} old format projects\n")

    if execute:
        backup_old_files(old_files)
        print()

    results = []
    for old_file in old_files:
        result = migrate_project(old_file, execute=execute)
        results.append(result)

        status_icon = '✓' if result['status'] == 'migrated' else ('○' if result['status'] == 'preview' else '✗')
        print(f"{status_icon} {result['project_id']}: {result.get('project_name', 'Unknown')}")
        print(f"   Tasks: {result['tasks']}, Initiatives: {result['initiatives']}")
        print(f"   Status: {result['status']}\n")

    if not execute:
        print("=" * 50)
        print("This was a preview. Run with --execute to migrate.")
        print("  python migrate.py --execute")
        return 0

    if cleanup and all(r['status'] == 'migrated' for r in results):
        cleanup_old_files(old_files)

    # Clear old sync state
    sync_file = DATA_DIR / 'todo_sync_state.json'
    if sync_file.exists():
        backup_sync = BACKUP_DIR / 'todo_sync_state.json'
        shutil.copy2(sync_file, backup_sync)
        sync_file.unlink()
        print("Cleared old sync state (backed up)")

    print("\n" + "=" * 50)
    print("Migration complete!")
    print(f"New format projects in: {OLD_PROJECTS_DIR}")
    print(f"Backups in: {BACKUP_DIR}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
