#!/usr/bin/env python3
"""
Component scaffolding tool for the wicked-garden unified plugin.

Skills-only layout: the plugin ships skills and hooks. The former commands/
and agents/ trees were absorbed into skills/ —

  * a former COMMAND is now an ACTION of a consolidated per-domain router
    skill at skills/{domain}/SKILL.md (there is no commands/ tree);
  * a former AGENT is now a standalone context:fork WORKER skill at
    skills/{domain}-{role}/SKILL.md, dispatched via Skill(skill="…").

So this tool scaffolds: skills (sub-skills / standalone), workers (context:fork),
and hooks. The `agent` and `command` subcommands are kept as thin
back-compat aliases that route to the skills-only equivalents.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Path to this script's directory.
# This file lives at <repo>/.claude/skills/scaffolding/scripts/scaffold.py, so
# the repo root (where skills/ and hooks/ live) is four parents up. Components
# are scaffolded into the repo root, not into .claude/.
SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent


def _discover_domains() -> list[str]:
    """Discover valid domains for the skills-only layout.

    Canonical source is ``.claude-plugin/components.json`` "domains". Falls
    back to the top-level directories under skills/ (excluding the
    ``{domain}-{role}`` fork-worker dirs) if the manifest is unavailable.
    """
    components = PROJECT_ROOT / ".claude-plugin" / "components.json"
    try:
        data = json.loads(components.read_text(encoding="utf-8"))
        domains = data.get("domains")
        if isinstance(domains, list) and domains:
            return sorted(str(d) for d in domains)
    except (OSError, json.JSONDecodeError):
        pass
    # Fallback: skills/ top-level dirs that are NOT fork-worker dirs.
    skills_dir = PROJECT_ROOT / "skills"
    if skills_dir.is_dir():
        return sorted(
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and "-" not in d.name
        )
    return []


# Valid domains — discovered from the manifest / skills tree at import time
VALID_DOMAINS = _discover_domains()


# Validation patterns
NAMESPACE_PATTERN = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
RESERVED_PREFIXES = ['claude-code-', 'anthropic-', 'official-', 'agent-skills']


def validate_name(name: str, component_type: str = "component") -> tuple[bool, Optional[str]]:
    """Validate a component name (kebab-case, <=64 chars, no reserved prefix)."""
    if not name:
        return False, f"{component_type} name cannot be empty"

    if len(name) > 64:
        return False, f"{component_type} name too long (max 64 chars): {len(name)}"

    if not NAMESPACE_PATTERN.match(name):
        return False, f"{component_type} name must be kebab-case (lowercase, numbers, hyphens): {name}"

    for prefix in RESERVED_PREFIXES:
        if name.startswith(prefix):
            return False, f"{component_type} name cannot start with reserved prefix: {prefix}"

    return True, None


def validate_domain(domain: str) -> tuple[bool, Optional[str]]:
    """Validate that a domain name is valid."""
    if not domain:
        return False, "Domain cannot be empty"
    if domain not in VALID_DOMAINS:
        return False, f"Invalid domain: {domain}. Must be one of: {', '.join(VALID_DOMAINS)}"
    return True, None


def title_case(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return ' '.join(word.capitalize() for word in name.split('-'))


def upper_case(name: str) -> str:
    """Convert kebab-case to UPPER_CASE."""
    return name.replace('-', '_').upper()


def render_template(template_path: Path, variables: Dict[str, str]) -> str:
    """Render a template file, replacing every ``{{variable}}`` occurrence."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    content = template_path.read_text()
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def prompt_user(message: str, default: Optional[str] = None, required: bool = True) -> str:
    """Prompt user for input, honouring an optional default."""
    suffix = f" [{default}]" if default else ""
    prompt = f"{message}{suffix}: "

    while True:
        value = input(prompt).strip()

        if not value and default:
            return default

        if not value and required:
            print("This field is required. Please enter a value.")
            continue

        return value


def scaffold_skill(
    name: str,
    domain: str,
    description: str,
    use_when: str
) -> Path:
    """Scaffold a new sub-skill under a domain: skills/{domain}/{name}/SKILL.md."""
    valid, error = validate_name(name, "Skill")
    if not valid:
        raise ValueError(error)

    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    skill_dir = PROJECT_ROOT / "skills" / domain / name
    if skill_dir.exists():
        raise FileExistsError(f"Skill already exists: {skill_dir}")

    print(f"Creating skill: {name} in domain {domain}")

    skill_dir.mkdir(parents=True)

    variables = {
        "name": name,
        "title": title_case(name),
        "description": description,
        "use_when": use_when,
    }

    skill_template = TEMPLATES_DIR / "skill" / "SKILL.md"
    skill_content = render_template(skill_template, variables)
    (skill_dir / "SKILL.md").write_text(skill_content)

    print(f"  Created SKILL.md")
    print(f"\nSkill created: {skill_dir}")
    print(f"Skill id: {name} (routed by the {domain} domain skill)")
    return skill_dir


def scaffold_worker(
    name: str,
    domain: str,
    description: str,
    expertise: str,
    tools: List[str]
) -> Path:
    """Scaffold a context:fork WORKER skill (the former "agent").

    Writes skills/{domain}-{name}/SKILL.md with ``context: fork`` frontmatter
    and the dash-qualified skill name ``wicked-garden-{domain}-{name}``, which
    is the identifier callers dispatch via Skill(skill="…").
    """
    valid, error = validate_name(name, "Worker")
    if not valid:
        raise ValueError(error)

    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    # Fork workers are top-level skills named skills/{domain}-{role}/
    worker_dir = PROJECT_ROOT / "skills" / f"{domain}-{name}"
    if worker_dir.exists():
        raise FileExistsError(f"Worker skill already exists: {worker_dir}")

    print(f"Creating fork worker skill: {name} in domain {domain}")
    worker_dir.mkdir(parents=True)

    skill_name = f"wicked-garden-{domain}-{name}"
    tools_str = ', '.join(f'"{tool}"' for tool in tools)
    variables = {
        "skill_name": skill_name,
        "name": name,
        "title": title_case(name),
        "description": description,
        "domain": expertise,
        "tools": tools_str,
        "color": "blue",
        "namespace": f"wicked-garden:{domain}",
        "entity": name,
        "capability_1": "Analyze requirements and context",
        "capability_2": "Design solutions following best practices",
        "capability_3": "Implement with quality and precision",
        "step_1": "Understand the task and requirements",
        "step_2": "Research patterns and best practices",
        "step_3": "Implement and verify the solution",
        "standard_1": "Code follows established patterns",
        "standard_2": "Solution meets all requirements",
        "standard_3": "Changes are well-tested and documented",
        "constraint_1": "No scope creep - stay focused on requirements",
        "constraint_2": "No over-engineering - keep it simple",
        "constraint_3": "No assumptions - ask when unclear",
        "communication_1": "Clear and concise explanations",
        "communication_2": "Transparent about limitations and blockers",
    }

    worker_template = TEMPLATES_DIR / "agent" / "agent.md"
    worker_content = render_template(worker_template, variables)
    (worker_dir / "SKILL.md").write_text(worker_content)

    print(f"  Created SKILL.md")
    print(f"\nWorker skill created: {worker_dir / 'SKILL.md'}")
    print(f"Dispatch via: Skill(skill=\"{skill_name}\")")
    return worker_dir


def scaffold_command(
    name: str,
    domain: str,
    description: str,
) -> Path | None:
    """The command component type is RETIRED (skills-only layout).

    Former commands are now ACTIONS of the consolidated per-domain router
    skill at skills/{domain}/SKILL.md. This helper does not create a
    commands/ file; it prints guidance for adding the action instead.
    """
    valid, error = validate_name(name, "Action")
    if not valid:
        raise ValueError(error)
    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    router = PROJECT_ROOT / "skills" / domain / "SKILL.md"
    print(f"Commands are retired in the skills-only layout.")
    print(
        f"Add '{name}' as an ACTION of the {domain} domain skill instead:\n"
        f"  - Router skill: skills/{domain}/SKILL.md\n"
        f"    (add a row to its Action router table + an inline section or a\n"
        f"     refs/{name}.md playbook, and — if it dispatches to a worker —\n"
        f"     Skill(skill=\"wicked-garden-{domain}-<worker>\"))."
    )
    if not router.exists():
        print(
            f"\nThe {domain} router skill does not exist yet. Scaffold it first:\n"
            f"  scaffold.py skill --name {domain} --domain {domain} "
            f"--description \"{domain} domain router\" --use-when \"{domain} work\""
        )
    # See templates/plugin/command-with-agent.md for a copy-paste action stub.
    return None


def scaffold_hook(
    event: str,
    script_name: str,
    description: str,
    matcher: str = "*"
) -> Path:
    """Scaffold a new hook in the unified plugin."""
    valid_events = [
        "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
        "SubagentStop", "SessionStart", "SessionEnd", "PreCompact", "Notification"
    ]
    if event not in valid_events:
        raise ValueError(f"Invalid event: {event}. Must be one of: {', '.join(valid_events)}")

    hooks_dir = PROJECT_ROOT / "hooks"
    scripts_dir = hooks_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating hook: {event}")

    variables = {
        "description": description,
        "event": event,
        "matcher": matcher,
        "script_name": script_name,
        "plugin_name": "wicked-garden"
    }

    hooks_json_path = hooks_dir / "hooks.json"
    if hooks_json_path.exists():
        hooks_data = json.loads(hooks_json_path.read_text())
        if event not in hooks_data.get("hooks", {}):
            hooks_data["hooks"][event] = []

        new_hook = {
            "matcher": matcher,
            "hooks": [
                {
                    "type": "command",
                    "command": f"python ${{CLAUDE_PLUGIN_ROOT}}/hooks/scripts/{script_name}.py",
                    "timeout": 10
                }
            ]
        }
        hooks_data["hooks"][event].append(new_hook)

        hooks_json_path.write_text(json.dumps(hooks_data, indent=2))
        print(f"  Updated hooks/hooks.json")
    else:
        hooks_template = TEMPLATES_DIR / "hook" / "hooks.json"
        hooks_content = render_template(hooks_template, variables)
        hooks_json_path.write_text(hooks_content)
        print(f"  Created hooks/hooks.json")

    script_template = TEMPLATES_DIR / "hook" / "script.py"
    script_content = render_template(script_template, variables)
    script_path = scripts_dir / f"{script_name}.py"
    script_path.write_text(script_content)
    script_path.chmod(0o755)
    print(f"  Created hooks/scripts/{script_name}.py")

    print(f"\nHook created: {hooks_dir}")
    return hooks_dir


def interactive_skill():
    """Interactive skill creation."""
    print("\n=== Skill Scaffold ===\n")

    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = prompt_user("Domain")
    valid, error = validate_domain(domain)
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Skill name (kebab-case)")
    valid, error = validate_name(name, "Skill")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")
    use_when = prompt_user("Use when (trigger conditions)")

    scaffold_skill(name, domain, description, use_when)


def interactive_worker():
    """Interactive fork-worker (context:fork) skill creation."""
    print("\n=== Worker Skill Scaffold (context:fork) ===\n")

    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = prompt_user("Domain")
    valid, error = validate_domain(domain)
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Worker name (kebab-case, the role)")
    valid, error = validate_name(name, "Worker")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")
    expertise = prompt_user("Area of expertise")
    tools_str = prompt_user("Tools (comma-separated)", default="Read,Write,Bash")
    tools = [tool.strip() for tool in tools_str.split(',')]

    scaffold_worker(name, domain, description, expertise, tools)


def interactive_command():
    """Interactive command — retired; prints skills-only guidance."""
    print("\n=== Action Scaffold (commands are retired) ===\n")

    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = prompt_user("Domain")
    valid, error = validate_domain(domain)
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Action name (kebab-case)")
    valid, error = validate_name(name, "Action")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")

    scaffold_command(name, domain, description)


def interactive_hook():
    """Interactive hook creation."""
    print("\n=== Hook Scaffold ===\n")

    valid_events = [
        "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
        "SubagentStop", "SessionStart", "SessionEnd", "PreCompact", "Notification"
    ]
    print(f"\nValid events: {', '.join(valid_events)}")
    event = prompt_user("Event")
    if event not in valid_events:
        print(f"Error: Invalid event. Must be one of: {', '.join(valid_events)}")
        sys.exit(1)

    script_name = prompt_user("Script name (without .py)")
    description = prompt_user("Description")
    matcher = prompt_user("Tool matcher pattern", default="*")

    scaffold_hook(event, script_name, description, matcher)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scaffold components for the wicked-garden plugin (skills-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Component type')

    # Skill subcommand
    skill_parser = subparsers.add_parser('skill', help='Scaffold a (sub-)skill')
    skill_parser.add_argument('--name', required=False, help='Skill name')
    skill_parser.add_argument('--domain', required=False, help='Domain name')
    skill_parser.add_argument('--description', required=False, help='Description')
    skill_parser.add_argument('--use-when', required=False, help='Usage trigger')

    # Worker subcommand (context:fork) — `agent` kept as a back-compat alias
    for verb in ('worker', 'agent'):
        wp = subparsers.add_parser(
            verb,
            help='Scaffold a context:fork worker skill (former agent)'
        )
        wp.add_argument('--name', required=False, help='Worker name (role)')
        wp.add_argument('--domain', required=False, help='Domain name')
        wp.add_argument('--description', required=False, help='Description')
        wp.add_argument('--expertise', required=False, help='Area of expertise')
        wp.add_argument('--tools', default='Read,Write,Bash', help='Comma-separated tool list')

    # Command subcommand — retired; prints skills-only guidance
    command_parser = subparsers.add_parser(
        'command', help='RETIRED — former commands are now domain-skill actions'
    )
    command_parser.add_argument('--name', required=False, help='Action name')
    command_parser.add_argument('--domain', required=False, help='Domain name')
    command_parser.add_argument('--description', required=False, help='Description')

    # Hook subcommand
    hook_parser = subparsers.add_parser('hook', help='Scaffold a hook')
    hook_parser.add_argument('--event', required=False, help='Hook event')
    hook_parser.add_argument('--script', required=False, help='Script name')
    hook_parser.add_argument('--description', required=False, help='Description')
    hook_parser.add_argument('--matcher', default='*', help='Tool matcher pattern')

    args = parser.parse_args()

    try:
        if args.command == 'skill':
            if not args.name or not args.domain:
                interactive_skill()
            else:
                scaffold_skill(args.name, args.domain, args.description, args.use_when)

        elif args.command in ('worker', 'agent'):
            if not args.name or not args.domain:
                interactive_worker()
            else:
                tools = [tool.strip() for tool in args.tools.split(',')]
                scaffold_worker(args.name, args.domain, args.description, args.expertise or args.domain, tools)

        elif args.command == 'command':
            if not args.name or not args.domain:
                interactive_command()
            else:
                scaffold_command(args.name, args.domain, args.description)

        elif args.command == 'hook':
            if not args.event or not args.script:
                interactive_hook()
            else:
                scaffold_hook(args.event, args.script, args.description, args.matcher)

        else:
            # Interactive mode - choose component type
            print("\n=== Component Scaffold (wicked-garden, skills-only) ===\n")
            print("Component types:")
            print("  1. Skill (sub-skill / standalone)")
            print("  2. Worker skill (context:fork — former agent)")
            print("  3. Action (former command — folded into the domain skill)")
            print("  4. Hook")

            choice = prompt_user("\nSelect type (1-4)")

            if choice == '1':
                interactive_skill()
            elif choice == '2':
                interactive_worker()
            elif choice == '3':
                interactive_command()
            elif choice == '4':
                interactive_hook()
            else:
                print("Invalid choice")
                sys.exit(1)

    except (ValueError, FileNotFoundError, FileExistsError) as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled")
        sys.exit(0)


if __name__ == "__main__":
    main()
