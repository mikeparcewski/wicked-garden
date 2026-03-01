#!/usr/bin/env python3
"""
Specialist Discovery - Find and load specialist plugin configurations.

Discovers specialist plugins by:
1. Scanning plugin directories for specialist.json files
2. Loading persona definitions
3. Mapping roles to available plugins
4. Validating specialist contracts

Features:
- In-memory caching with TTL
- Structured logging
- Graceful degradation
- Comprehensive error handling for malformed configurations

IMPORTANT: Avoid importing from smart_decisioning.py to prevent circular dependencies.
If integration is needed, smart_decisioning.py should import this module, not vice versa.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('wicked-crew.specialist-discovery')

# Cache configuration
_cache: Dict[str, Tuple[float, Dict[str, 'Specialist']]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class Persona:
    """A perspective/persona within a specialist."""
    name: str
    focus: str
    agent: Optional[str] = None
    dynamic: bool = False


@dataclass
class Enhancement:
    """How a specialist enhances a phase."""
    phase: str
    trigger: str
    response: str
    capabilities: List[str] = field(default_factory=list)


@dataclass
class Specialist:
    """A discovered specialist plugin."""
    name: str
    role: str
    description: str
    personas: List[Persona]
    enhances: List[Enhancement]
    plugin_path: Path
    hooks_subscribes: List[str] = field(default_factory=list)
    hooks_publishes: List[str] = field(default_factory=list)
    fallback_agent: Optional[str] = None  # Fallback agent when specialist unavailable


# Role categories for grouping specialists
ROLE_CATEGORIES = {
    "ideation": ["brainstorming", "exploration", "idea generation"],
    "business-strategy": ["planning", "roadmap", "prioritization"],
    "project-management": ["tracking", "reporting", "coordination"],
    "quality-engineering": ["testing", "quality gates", "risk assessment"],
    "devsecops": ["security", "deployment", "infrastructure"],
    "engineering": ["implementation", "architecture", "code quality"],
    "product": ["requirements", "user stories", "acceptance criteria"],
    "compliance": ["auditing", "policy enforcement", "documentation"],
    "research": ["analysis", "data exploration", "investigation"],
    "data-engineering": ["data pipelines", "data analysis", "data modeling"],
    "agentic-architecture": ["agent design", "agent orchestration", "agent safety"]
}


def _parse_single_specialist(spec_data: dict, personas_data: list,
                              enhances_data: list, hooks: dict,
                              specialist_json: Path) -> Optional[Specialist]:
    """Parse a single specialist entry from its component data."""
    # Validate required fields
    required_fields = ["name", "role", "description"]
    for fld in required_fields:
        if not spec_data.get(fld):
            logger.error(f"Missing required field '{fld}' in {specialist_json}")
            return None

    # Parse personas with validation
    personas = []
    if not isinstance(personas_data, list):
        logger.error(f"Invalid 'personas' format in {specialist_json}: must be array")
        return None

    for i, p in enumerate(personas_data):
        if not isinstance(p, dict):
            logger.warning(f"Skipping invalid persona {i} in {specialist_json}")
            continue
        personas.append(Persona(
            name=p.get("name", ""),
            focus=p.get("focus", ""),
            agent=p.get("agent"),
            dynamic=p.get("dynamic", False)
        ))

    # Parse enhancements with validation
    enhances = []
    if not isinstance(enhances_data, list):
        logger.warning(f"Invalid 'enhances' format in {specialist_json}: expected array, got {type(enhances_data).__name__}")
        enhances_data = []

    for i, e in enumerate(enhances_data):
        if isinstance(e, str):
            # Unified format: enhances is ["design", "build", "review"]
            enhances.append(Enhancement(
                phase=e,
                trigger=f"When {e} phase is active",
                response=f"Provide {e} phase expertise",
                capabilities=[]
            ))
        elif isinstance(e, dict):
            enhances.append(Enhancement(
                phase=e.get("phase", "*"),
                trigger=e.get("trigger", ""),
                response=e.get("response", ""),
                capabilities=e.get("capabilities", [])
            ))
        else:
            logger.warning(f"Skipping invalid enhancement {i} in {specialist_json}")

    if not isinstance(hooks, dict):
        hooks = {}

    # Parse fallback_agent if present
    fallback_agent = spec_data.get("fallback_agent")
    if fallback_agent and not isinstance(fallback_agent, str):
        fallback_agent = None

    specialist = Specialist(
        name=spec_data.get("name", ""),
        role=spec_data.get("role", ""),
        description=spec_data.get("description", ""),
        personas=personas,
        enhances=enhances,
        plugin_path=specialist_json.parent.parent,
        hooks_subscribes=sub if isinstance(sub := hooks.get("subscribes", []), list) else [],
        hooks_publishes=pub if isinstance(pub := hooks.get("publishes", []), list) else [],
        fallback_agent=fallback_agent
    )

    validation_issues = validate_specialist(specialist)
    if validation_issues:
        logger.warning(f"Specialist {specialist.name} has validation issues: {validation_issues}")

    return specialist


def load_specialist_file(specialist_json: Path) -> List[Specialist]:
    """
    Load specialist(s) from a specialist.json file.

    Supports two formats:
    - Unified (wicked-garden): {"plugin": "...", "specialists": [{...}, ...]}
      Each entry has name, role, description, personas, enhances as top-level keys.
    - Legacy (single plugin): {"specialist": {...}, "personas": [...], "enhances": [...]}

    Returns a list of parsed Specialist objects (empty list on failure).
    """
    try:
        with open(specialist_json) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in {specialist_json}: {e}")
        return []
    except IOError as e:
        logger.error(f"Failed to read {specialist_json}: {e}")
        return []

    if not isinstance(data, dict):
        logger.error(f"Invalid specialist.json format in {specialist_json}: root must be object")
        return []

    results = []

    try:
        # --- Unified format: "specialists" array ---
        specialists_array = data.get("specialists")
        if isinstance(specialists_array, list) and specialists_array:
            logger.debug(f"Parsing unified format with {len(specialists_array)} specialists")
            for entry in specialists_array:
                if not isinstance(entry, dict):
                    continue
                spec = _parse_single_specialist(
                    spec_data=entry,
                    personas_data=entry.get("personas", []),
                    enhances_data=entry.get("enhances", []),
                    hooks=entry.get("hooks", {}),
                    specialist_json=specialist_json,
                )
                if spec:
                    results.append(spec)
            return results

        # --- Legacy format: single "specialist" object ---
        spec_data = data.get("specialist", {})
        if spec_data and isinstance(spec_data, dict):
            spec = _parse_single_specialist(
                spec_data=spec_data,
                personas_data=data.get("personas", []),
                enhances_data=data.get("enhances", []),
                hooks=data.get("hooks", {}),
                specialist_json=specialist_json,
            )
            if spec:
                results.append(spec)
            return results

        logger.warning(f"No 'specialists' array or 'specialist' object in {specialist_json}")
        return []

    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Failed to parse specialist config from {specialist_json}: {e}")
        return []


def load_specialist(specialist_json: Path) -> Optional[Specialist]:
    """
    Load a single specialist from specialist.json (legacy interface).

    For files with multiple specialists (unified format), returns the first one.
    Prefer load_specialist_file() for full access to all specialists.
    """
    specs = load_specialist_file(specialist_json)
    return specs[0] if specs else None


def _get_cache_key(search_paths: List[Path]) -> str:
    """Generate cache key from search paths."""
    return ":".join(str(p) for p in sorted(search_paths))


def discover_specialists(
    search_paths: Optional[List[Path]] = None,
    use_cache: bool = True
) -> Dict[str, Specialist]:
    """
    Discover all specialist plugins in search paths.

    Args:
        search_paths: Directories to search for specialist plugins
        use_cache: Whether to use cached results (default: True)

    Returns:
        Dict mapping plugin name to Specialist object.
    """
    if search_paths is None:
        search_paths = get_default_search_paths()

    # Check cache
    cache_key = _get_cache_key(search_paths)
    if use_cache and cache_key in _cache:
        cached_time, cached_data = _cache[cache_key]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            logger.debug(f"Using cached specialist discovery ({len(cached_data)} specialists)")
            return cached_data

    logger.info(f"Discovering specialists in {len(search_paths)} search paths")
    start_time = time.time()
    specialists = {}

    for search_path in search_paths:
        if not search_path.exists():
            logger.debug(f"Search path does not exist: {search_path}")
            continue

        # Look for plugins
        for item in search_path.iterdir():
            if not item.is_dir():
                continue

            # Skip non-wicked plugins
            if not item.name.startswith("wicked-"):
                continue

            # Look for specialist.json in .claude-plugin directory
            specialist_json = item / ".claude-plugin" / "specialist.json"
            if specialist_json.exists():
                for spec in load_specialist_file(specialist_json):
                    specialists[spec.name] = spec
                    logger.debug(f"Found specialist: {spec.name} ({spec.role})")
                continue

            # Look in versioned directories (cache structure)
            for version_dir in item.iterdir():
                if version_dir.is_dir():
                    specialist_json = version_dir / ".claude-plugin" / "specialist.json"
                    if specialist_json.exists():
                        for spec in load_specialist_file(specialist_json):
                            specialists[spec.name] = spec
                            logger.debug(f"Found specialist: {spec.name} ({spec.role})")
                        break

    elapsed = time.time() - start_time
    logger.info(f"Discovery complete: {len(specialists)} specialists found in {elapsed:.2f}s")

    # Update cache
    _cache[cache_key] = (time.time(), specialists)

    return specialists


def clear_cache() -> None:
    """Clear the specialist discovery cache."""
    global _cache
    _cache = {}
    logger.info("Specialist discovery cache cleared")


def get_default_search_paths() -> List[Path]:
    """Get default paths to search for plugins."""
    paths = []
    home = Path.home()

    # Plugin cache directory
    cache_dir = home / ".claude" / "plugins" / "cache" / "wicked-garden"
    if cache_dir.exists():
        paths.append(cache_dir)

    # Local development directory
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        # Go up from specific plugin to plugins directory
        plugins_dir = Path(plugin_root).parent
        if plugins_dir.exists():
            paths.append(plugins_dir)

    # Development mode: use explicit path from environment variable
    # Set WICKED_DEV_PLUGINS_PATH to your local checkout for development
    dev_path = os.environ.get("WICKED_DEV_PLUGINS_PATH")
    if dev_path:
        dev_dir = Path(dev_path)
        if dev_dir.exists():
            paths.append(dev_dir)

    return paths


def get_specialists_by_role(specialists: Dict[str, Specialist]) -> Dict[str, List[Specialist]]:
    """Group specialists by their role."""
    by_role: Dict[str, List[Specialist]] = {}

    for spec in specialists.values():
        if spec.role not in by_role:
            by_role[spec.role] = []
        by_role[spec.role].append(spec)

    return by_role


def get_specialists_for_phase(
    specialists: Dict[str, Specialist],
    phase: str
) -> List[Specialist]:
    """Get specialists that enhance a specific phase."""
    result = []

    for spec in specialists.values():
        for enhancement in spec.enhances:
            if enhancement.phase in (phase, "*"):
                result.append(spec)
                break

    return result


def get_available_personas(
    specialists: Dict[str, Specialist]
) -> Dict[str, List[Persona]]:
    """Get all available personas grouped by specialist."""
    personas = {}

    for name, spec in specialists.items():
        if spec.personas:
            personas[name] = spec.personas

    return personas


def validate_specialist(specialist: Specialist) -> List[str]:
    """Validate a specialist configuration, return list of issues."""
    issues = []

    # Check required fields
    if not specialist.name:
        issues.append("Missing specialist name")
    if not specialist.role:
        issues.append("Missing specialist role")
    if specialist.role and specialist.role not in ROLE_CATEGORIES:
        issues.append(f"Unknown role: {specialist.role}")

    # Check personas
    if not specialist.personas:
        issues.append("No personas defined")
    for i, persona in enumerate(specialist.personas):
        if not persona.name:
            issues.append(f"Persona {i}: missing name")
        if not persona.focus:
            issues.append(f"Persona {i}: missing focus")

    # Check enhancements
    if not specialist.enhances:
        issues.append("No phase enhancements defined")
    for i, enhancement in enumerate(specialist.enhances):
        if not enhancement.trigger:
            issues.append(f"Enhancement {i}: missing trigger")
        if not enhancement.response:
            issues.append(f"Enhancement {i}: missing response")

    return issues


def main():
    """CLI interface for specialist discovery."""
    import argparse

    parser = argparse.ArgumentParser(description="Discover specialist plugins")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--role", help="Filter by role")
    parser.add_argument("--phase", help="Filter by phase enhancement")
    parser.add_argument("--validate", action="store_true", help="Validate specialists")
    parser.add_argument("--path", type=Path, action="append", help="Additional search path")

    args = parser.parse_args()

    search_paths = get_default_search_paths()
    if args.path:
        search_paths.extend(args.path)

    specialists = discover_specialists(search_paths)

    if args.role:
        specialists = {k: v for k, v in specialists.items() if v.role == args.role}

    if args.phase:
        phase_specs = get_specialists_for_phase(specialists, args.phase)
        specialists = {s.name: s for s in phase_specs}

    if args.validate:
        all_valid = True
        for name, spec in specialists.items():
            issues = validate_specialist(spec)
            if issues:
                all_valid = False
                print(f"\n{name}:")
                for issue in issues:
                    print(f"  - {issue}")
        if all_valid:
            print("All specialists valid")
        return

    if args.json:
        output = {}
        for name, spec in specialists.items():
            output[name] = {
                "name": spec.name,
                "role": spec.role,
                "description": spec.description,
                "personas": [{"name": p.name, "focus": p.focus} for p in spec.personas],
                "enhances": [e.phase for e in spec.enhances],
                "path": str(spec.plugin_path)
            }
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {len(specialists)} specialist(s):\n")
        for name, spec in specialists.items():
            print(f"  {name} ({spec.role})")
            print(f"    {spec.description}")
            print(f"    Personas: {', '.join(p.name for p in spec.personas)}")
            print(f"    Phases: {', '.join(e.phase for e in spec.enhances)}")
            print()


if __name__ == "__main__":
    main()
