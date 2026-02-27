#!/usr/bin/env python3
"""Contract assertion runner — validates subprocess outputs against JSON schemas.

Discovers schemas in schemas/{plugin}/{script-name}.json relative to the plugin
root, runs the corresponding script with --health-check (if supported) or a
minimal invocation, and validates the output against the schema.

Failure classes:
  timeout   — script did not complete within 10s
  empty     — script produced 0 bytes or empty JSON
  malformed — output failed schema validation
  pass      — output validated successfully

Results are persisted via StorageManager("wicked-observability").

Usage:
    python3 assert_contracts.py
    python3 assert_contracts.py --plugin wicked-smaht
    python3 assert_contracts.py --json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve _storage from the parent scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _storage import StorageManager


# ── Constants ────────────────────────────────────────────────────────────────

PLUGIN_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = PLUGIN_ROOT / "schemas"
PLUGINS_ROOT = PLUGIN_ROOT.parent  # …/plugins/
TIMEOUT_SECONDS = 10

_sm = StorageManager("wicked-observability")


# ── Minimal JSON Schema validator ────────────────────────────────────────────
# Implements: required, type, enum, properties (recursive), items (array)
# Does NOT require the jsonschema package.

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
    "array": list,
    "object": dict,
}


def _validate(value, schema: dict, path: str = "$") -> list[dict]:
    """Return a list of violation dicts; empty means valid."""
    violations = []

    # type check
    expected_type = schema.get("type")
    if expected_type:
        # Python's bool is a subclass of int — reject bools for integer/number
        if expected_type in ("integer", "number") and isinstance(value, bool):
            violations.append({
                "field": path,
                "message": "type mismatch",
                "expected": expected_type,
                "actual": "boolean",
            })
            return violations
        py_type = _TYPE_MAP.get(expected_type)
        if py_type and not isinstance(value, py_type):
            # JSON integers satisfy "number"
            if not (expected_type == "number" and isinstance(value, (int, float))):
                actual = type(value).__name__
                violations.append({
                    "field": path,
                    "message": "type mismatch",
                    "expected": expected_type,
                    "actual": actual,
                })
                return violations  # no point checking sub-constraints on wrong type

    # enum check
    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        violations.append({
            "field": path,
            "message": "value not in enum",
            "expected": enum_values,
            "actual": value,
        })

    # object properties + required
    if isinstance(value, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                violations.append({
                    "field": f"{path}.{field}",
                    "message": "required field missing",
                    "expected": "present",
                    "actual": "null",
                })

        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in value:
                violations.extend(
                    _validate(value[prop_name], prop_schema, f"{path}.{prop_name}")
                )

    # array items
    if isinstance(value, list):
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(value):
                violations.extend(_validate(item, items_schema, f"{path}[{i}]"))

    return violations


def validate_against_schema(data, schema: dict) -> list[dict]:
    """Validate data against schema; return list of violations."""
    return _validate(data, schema)


# ── Schema discovery ─────────────────────────────────────────────────────────


def discover_schemas(plugin_filter: str | None = None) -> list[dict]:
    """
    Walk SCHEMAS_DIR and yield schema descriptor dicts:
      {plugin, script_name, schema_path, script_path | None}
    """
    if not SCHEMAS_DIR.exists():
        return []

    descriptors = []
    for schema_path in sorted(SCHEMAS_DIR.rglob("*.json")):
        # Expected layout: schemas/{plugin}/{script-name}.json
        parts = schema_path.relative_to(SCHEMAS_DIR).parts
        if len(parts) != 2:
            continue
        plugin_name, schema_file = parts
        script_name = schema_file[:-5]  # strip .json → e.g. "orchestrator"

        if plugin_filter and plugin_name != plugin_filter:
            continue

        script_path = _find_script(plugin_name, script_name)

        descriptors.append({
            "plugin": plugin_name,
            "script_name": script_name + ".py",
            "schema_path": schema_path,
            "script_path": script_path,
        })

    return descriptors


def _find_script(plugin_name: str, script_name: str) -> Path | None:
    """Locate the target script in the plugin's scripts/ directory."""
    candidate = PLUGINS_ROOT / plugin_name / "scripts" / f"{script_name}.py"
    if candidate.exists():
        return candidate

    # Also check scripts/v2/ sub-directory (wicked-smaht pattern)
    candidate_v2 = PLUGINS_ROOT / plugin_name / "scripts" / "v2" / f"{script_name}.py"
    if candidate_v2.exists():
        return candidate_v2

    return None


# ── Script invocation ────────────────────────────────────────────────────────


def _invoke_script(script_path: Path) -> tuple[str, float]:
    """
    Run script with --health-check; fall back to bare invocation if that flag
    causes a non-zero exit.

    Returns (stdout_text, duration_ms).
    Raises subprocess.TimeoutExpired on timeout.
    """
    start = datetime.now(timezone.utc).timestamp()

    def _run(extra_args: list[str]) -> subprocess.CompletedProcess:
        env = {**os.environ, "WICKED_TRACE_ACTIVE": "1"}
        return subprocess.run(
            [sys.executable, str(script_path)] + extra_args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )

    result = _run(["--health-check"])

    # If health-check flag is unrecognised (argparse exits 2) retry without it
    if result.returncode == 2 and "unrecognized arguments" in result.stderr:
        result = _run([])

    duration_ms = (datetime.now(timezone.utc).timestamp() - start) * 1000
    return result.stdout or "", round(duration_ms, 1)


# ── Assertion logic ──────────────────────────────────────────────────────────


def run_assertion(descriptor: dict) -> dict:
    """Run one contract assertion. Returns a result record."""
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    plugin = descriptor["plugin"]
    script_name = descriptor["script_name"]
    schema_path: Path = descriptor["schema_path"]
    script_path: Path | None = descriptor["script_path"]

    base = {
        "ts": ts,
        "plugin": plugin,
        "script": script_name,
        "result": "pass",
        "violations": [],
        "duration_ms": 0,
    }

    # Load schema
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        base["result"] = "malformed"
        base["violations"] = [{"field": "$", "message": f"could not load schema: {exc}",
                                "expected": "valid JSON schema", "actual": "error"}]
        return base

    if script_path is None:
        base["result"] = "malformed"
        base["violations"] = [{
            "field": "$",
            "message": f"script not found in {plugin}/scripts/",
            "expected": f"{script_name}",
            "actual": "missing",
        }]
        return base

    # Invoke
    try:
        stdout, duration_ms = _invoke_script(script_path)
    except subprocess.TimeoutExpired:
        base["result"] = "timeout"
        base["duration_ms"] = TIMEOUT_SECONDS * 1000
        return base

    base["duration_ms"] = round(duration_ms, 1)

    # Empty check
    if not stdout or not stdout.strip():
        base["result"] = "empty"
        base["violations"] = [{"field": "$", "message": "script produced no output",
                                "expected": "non-empty JSON", "actual": "empty"}]
        return base

    # Parse JSON
    try:
        data = json.loads(stdout.strip())
    except json.JSONDecodeError as exc:
        base["result"] = "malformed"
        base["violations"] = [{"field": "$", "message": f"invalid JSON: {exc}",
                                "expected": "valid JSON", "actual": stdout[:200]}]
        return base

    if data is None or (isinstance(data, (dict, list)) and not data
                        and schema.get("type") not in ("array", "null")):
        base["result"] = "empty"
        base["violations"] = [{"field": "$", "message": "script returned empty JSON",
                                "expected": "non-empty object", "actual": "empty"}]
        return base

    # Schema validation
    violations = validate_against_schema(data, schema)
    if violations:
        base["result"] = "malformed"
        base["violations"] = violations

    return base


# ── Output / storage ─────────────────────────────────────────────────────────


def append_result(record: dict) -> None:
    """Persist a single assertion result via StorageManager."""
    try:
        _sm.create("assertions", record)
    except Exception as exc:
        print(f"WARNING: Could not persist assertion result: {exc}", file=sys.stderr)


# ── Formatting ───────────────────────────────────────────────────────────────

_RESULT_ICONS = {
    "pass": "pass",
    "timeout": "TIMEOUT",
    "empty": "EMPTY",
    "malformed": "MALFORMED",
}


def _print_human(results: list[dict]) -> None:
    passed = sum(1 for r in results if r["result"] == "pass")
    failed = len(results) - passed

    for r in results:
        icon = _RESULT_ICONS.get(r["result"], r["result"].upper())
        label = f"[{icon}]"
        line = f"  {label:<12} {r['plugin']}/{r['script']}  ({r['duration_ms']:.0f}ms)"
        print(line)
        for v in r.get("violations", []):
            print(f"               {v['field']}: {v['message']}"
                  f"  (expected={v['expected']!r}, actual={v['actual']!r})")

    print()
    print(f"Results: {passed} passed, {failed} failed  ({len(results)} total)")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    # Fast-path: --health-check emits a sample assertion result for contract testing
    if "--health-check" in sys.argv:
        print(json.dumps([{
            "ts": datetime.now(timezone.utc).isoformat(),
            "plugin": "health-check",
            "script": "health-check.py",
            "result": "pass",
            "violations": [],
            "duration_ms": 0.0,
        }]))
        return

    parser = argparse.ArgumentParser(
        description="Contract assertion runner for wicked-garden plugins")
    parser.add_argument("--plugin", help="Only assert contracts for this plugin")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Emit JSON array to stdout instead of human-readable text")
    args = parser.parse_args()

    descriptors = discover_schemas(plugin_filter=args.plugin)
    if not descriptors:
        target = args.plugin or "any plugin"
        msg = f"No schemas found for {target} under {SCHEMAS_DIR}"
        if args.json_output:
            print(json.dumps({"error": msg, "data": [], "meta": {"total": 0}}))
        else:
            print(msg, file=sys.stderr)
        sys.exit(0)

    results = []
    for descriptor in descriptors:
        record = run_assertion(descriptor)
        append_result(record)
        results.append(record)

    if args.json_output:
        print(json.dumps(results, indent=2))
        return

    _print_human(results)

    # Exit 1 if any failure so CI scripts can detect problems
    if any(r["result"] != "pass" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
