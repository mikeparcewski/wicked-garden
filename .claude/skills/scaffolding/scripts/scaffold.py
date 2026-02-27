#!/usr/bin/env python3
"""
Component scaffolding tool for the wicked-garden unified plugin.

Generates skills, agents, commands, and hooks within domain directories.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Path to this script's directory
SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

# Valid domains in the unified plugin
VALID_DOMAINS = [
    "crew", "smaht", "mem", "search", "jam", "kanban",
    "engineering", "product", "platform", "qe", "data", "delivery", "agentic",
    "startah", "workbench", "scenarios", "patch", "observability",
]


# Validation patterns
NAMESPACE_PATTERN = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
RESERVED_PREFIXES = ['claude-code-', 'anthropic-', 'official-', 'agent-skills']


def validate_name(name: str, component_type: str = "component") -> tuple[bool, Optional[str]]:
    """
    Validate a component name.

    Args:
        name: Component name to validate
        component_type: Type of component (for error messages)

    Returns:
        Tuple of (is_valid, error_message)
    """
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
    """
    Render a template file with variables.

    Args:
        template_path: Path to template file
        variables: Dictionary of variable names to values

    Returns:
        Rendered template content
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    content = template_path.read_text()

    # Replace all {{variable}} patterns
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content


def prompt_user(message: str, default: Optional[str] = None, required: bool = True) -> str:
    """
    Prompt user for input.

    Args:
        message: Prompt message
        default: Default value if user presses enter
        required: Whether input is required

    Returns:
        User's input or default value
    """
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
    """
    Scaffold a new skill in a domain.

    Args:
        name: Skill name (kebab-case)
        domain: Domain name (e.g., crew, qe, engineering)
        description: Brief description
        use_when: Usage trigger description

    Returns:
        Path to created skill directory
    """
    # Validate names
    valid, error = validate_name(name, "Skill")
    if not valid:
        raise ValueError(error)

    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    # Create skill directory
    skill_dir = PROJECT_ROOT / "skills" / domain / name
    if skill_dir.exists():
        raise FileExistsError(f"Skill already exists: {skill_dir}")

    print(f"Creating skill: {name} in domain {domain}")

    skill_dir.mkdir(parents=True)

    # Template variables
    variables = {
        "name": name,
        "title": title_case(name),
        "description": description,
        "use_when": use_when
    }

    # Create SKILL.md
    skill_template = TEMPLATES_DIR / "skill" / "SKILL.md"
    skill_content = render_template(skill_template, variables)
    (skill_dir / "SKILL.md").write_text(skill_content)

    print(f"  Created SKILL.md")
    print(f"\nSkill created: {skill_dir}")
    print(f"Namespace: wicked-garden:{domain}:{name}")
    return skill_dir


def scaffold_agent(
    name: str,
    domain: str,
    description: str,
    expertise: str,
    tools: List[str]
) -> Path:
    """
    Scaffold a new agent in a domain.

    Args:
        name: Agent name (kebab-case)
        domain: Domain name (e.g., crew, platform, engineering)
        description: Brief description
        expertise: Domain of expertise
        tools: List of tool names

    Returns:
        Path to created agent file
    """
    # Validate names
    valid, error = validate_name(name, "Agent")
    if not valid:
        raise ValueError(error)

    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    # Create agents/domain directory if needed
    agents_dir = PROJECT_ROOT / "agents" / domain
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Create agent file
    agent_file = agents_dir / f"{name}.md"
    if agent_file.exists():
        raise FileExistsError(f"Agent already exists: {agent_file}")

    print(f"Creating agent: {name} in domain {domain}")

    # Template variables
    tools_str = ', '.join(f'"{tool}"' for tool in tools)
    variables = {
        "name": name,
        "description": description,
        "domain": expertise,
        "tools": tools_str,
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
        "communication_2": "Transparent about limitations and blockers"
    }

    # Create agent.md
    agent_template = TEMPLATES_DIR / "agent" / "agent.md"
    agent_content = render_template(agent_template, variables)
    agent_file.write_text(agent_content)

    print(f"  Created {name}.md")
    print(f"\nAgent created: {agent_file}")
    print(f"Subagent type: wicked-garden:{domain}/{name}")
    return agent_file


def scaffold_command(
    name: str,
    domain: str,
    description: str,
) -> Path:
    """
    Scaffold a new command in a domain.

    Args:
        name: Command name (kebab-case)
        domain: Domain name (e.g., crew, qe, engineering)
        description: Brief description

    Returns:
        Path to created command file
    """
    # Validate names
    valid, error = validate_name(name, "Command")
    if not valid:
        raise ValueError(error)

    valid, error = validate_domain(domain)
    if not valid:
        raise ValueError(error)

    # Create commands/domain directory if needed
    commands_dir = PROJECT_ROOT / "commands" / domain
    commands_dir.mkdir(parents=True, exist_ok=True)

    # Create command file
    command_file = commands_dir / f"{name}.md"
    if command_file.exists():
        raise FileExistsError(f"Command already exists: {command_file}")

    print(f"Creating command: {name} in domain {domain}")

    # Check for matching agents to decide template
    agents_dir = PROJECT_ROOT / "agents" / domain
    has_agents = agents_dir.exists() and any(agents_dir.glob("*.md"))

    if has_agents:
        template_path = TEMPLATES_DIR / "plugin" / "command-with-agent.md"
    else:
        template_path = TEMPLATES_DIR / "plugin" / "command.md"

    variables = {
        "name": name,
        "command_name": name,
        "plugin_name": f"wicked-garden:{domain}",
        "description": description,
        "Name": title_case(name),
    }

    if template_path.exists():
        content = render_template(template_path, variables)
    else:
        content = f"""---
description: {description}
---

# /wicked-garden:{domain}:{name}

{description}

## Process

1. Parse arguments from $ARGUMENTS
2. Execute the command logic
3. Return results

"""

    command_file.write_text(content)

    print(f"  Created {name}.md")
    print(f"\nCommand created: {command_file}")
    print(f"Namespace: wicked-garden:{domain}:{name}")
    return command_file


def scaffold_hook(
    event: str,
    script_name: str,
    description: str,
    matcher: str = "*"
) -> Path:
    """
    Scaffold a new hook in the unified plugin.

    Args:
        event: Hook event (PreToolUse, PostToolUse, etc.)
        script_name: Script file name (without .py)
        description: Brief description
        matcher: Tool matcher pattern

    Returns:
        Path to created hooks directory
    """
    # Valid events
    valid_events = [
        "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
        "SubagentStop", "SessionStart", "SessionEnd", "PreCompact", "Notification"
    ]
    if event not in valid_events:
        raise ValueError(f"Invalid event: {event}. Must be one of: {', '.join(valid_events)}")

    # Create hooks directory if needed
    hooks_dir = PROJECT_ROOT / "hooks"
    scripts_dir = hooks_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating hook: {event}")

    # Template variables
    variables = {
        "description": description,
        "event": event,
        "matcher": matcher,
        "script_name": script_name,
        "plugin_name": "wicked-garden"
    }

    # Create or update hooks.json
    hooks_json_path = hooks_dir / "hooks.json"
    if hooks_json_path.exists():
        # Update existing hooks.json
        hooks_data = json.loads(hooks_json_path.read_text())
        if event not in hooks_data.get("hooks", {}):
            hooks_data["hooks"][event] = []

        # Add new hook entry
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
        # Create new hooks.json
        hooks_template = TEMPLATES_DIR / "hook" / "hooks.json"
        hooks_content = render_template(hooks_template, variables)
        hooks_json_path.write_text(hooks_content)
        print(f"  Created hooks/hooks.json")

    # Create hook script
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


def interactive_agent():
    """Interactive agent creation."""
    print("\n=== Agent Scaffold ===\n")

    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = prompt_user("Domain")
    valid, error = validate_domain(domain)
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Agent name (kebab-case)")
    valid, error = validate_name(name, "Agent")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")
    expertise = prompt_user("Area of expertise")
    tools_str = prompt_user("Tools (comma-separated)", default="Read,Write,Bash")
    tools = [tool.strip() for tool in tools_str.split(',')]

    scaffold_agent(name, domain, description, expertise, tools)


def interactive_command():
    """Interactive command creation."""
    print("\n=== Command Scaffold ===\n")

    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = prompt_user("Domain")
    valid, error = validate_domain(domain)
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Command name (kebab-case)")
    valid, error = validate_name(name, "Command")
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
        description="Scaffold domain components for the wicked-garden plugin",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Component type')

    # Skill subcommand
    skill_parser = subparsers.add_parser('skill', help='Scaffold a skill')
    skill_parser.add_argument('--name', required=False, help='Skill name')
    skill_parser.add_argument('--domain', required=False, help='Domain name')
    skill_parser.add_argument('--description', required=False, help='Description')
    skill_parser.add_argument('--use-when', required=False, help='Usage trigger')

    # Agent subcommand
    agent_parser = subparsers.add_parser('agent', help='Scaffold an agent')
    agent_parser.add_argument('--name', required=False, help='Agent name')
    agent_parser.add_argument('--domain', required=False, help='Domain name')
    agent_parser.add_argument('--description', required=False, help='Description')
    agent_parser.add_argument('--expertise', required=False, help='Area of expertise')
    agent_parser.add_argument('--tools', default='Read,Write,Bash', help='Comma-separated tool list')

    # Command subcommand
    command_parser = subparsers.add_parser('command', help='Scaffold a command')
    command_parser.add_argument('--name', required=False, help='Command name')
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

        elif args.command == 'agent':
            if not args.name or not args.domain:
                interactive_agent()
            else:
                tools = [tool.strip() for tool in args.tools.split(',')]
                scaffold_agent(args.name, args.domain, args.description, args.expertise or args.domain, tools)

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
            print("\n=== Component Scaffold (wicked-garden) ===\n")
            print("Component types:")
            print("  1. Skill")
            print("  2. Agent")
            print("  3. Command")
            print("  4. Hook")

            choice = prompt_user("\nSelect type (1-4)")

            if choice == '1':
                interactive_skill()
            elif choice == '2':
                interactive_agent()
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
