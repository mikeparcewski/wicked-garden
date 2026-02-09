#!/usr/bin/env python3
"""
Component scaffolding tool for Something Wicked marketplace.

Generates plugins, skills, agents, and hooks with proper structure.
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


def scaffold_plugin(
    name: str,
    description: str,
    author: str = "Something Wicked Community",
    with_commands: bool = False,
    with_skills: bool = False,
    with_agents: bool = False,
    with_hooks: bool = False
) -> Path:
    """
    Scaffold a new plugin.

    Args:
        name: Plugin name (kebab-case)
        description: Brief description
        author: Author name
        with_commands: Create example command
        with_skills: Create example skill
        with_agents: Create example agent
        with_hooks: Create example hooks

    Returns:
        Path to created plugin directory
    """
    # Validate name
    valid, error = validate_name(name, "Plugin")
    if not valid:
        raise ValueError(error)

    # Create plugin directory
    plugin_dir = PROJECT_ROOT / "plugins" / name
    if plugin_dir.exists():
        raise FileExistsError(f"Plugin already exists: {plugin_dir}")

    print(f"Creating plugin: {name}")

    # Create directory structure
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    if with_commands:
        (plugin_dir / "commands").mkdir()
    if with_skills:
        (plugin_dir / "skills").mkdir()
    if with_agents:
        (plugin_dir / "agents").mkdir()
    if with_hooks:
        (plugin_dir / "hooks" / "scripts").mkdir(parents=True)
    (plugin_dir / "scripts").mkdir()

    # Template variables
    variables = {
        "name": name,
        "Name": title_case(name),
        "NAME": upper_case(name),
        "description": description,
        "author": author
    }

    # Create plugin.json
    plugin_json_template = TEMPLATES_DIR / "plugin" / "plugin.json"
    plugin_json_content = render_template(plugin_json_template, variables)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(plugin_json_content)
    print(f"  ✓ Created .claude-plugin/plugin.json")

    # Create README.md
    readme_template = TEMPLATES_DIR / "plugin" / "README.md"
    readme_content = render_template(readme_template, variables)
    (plugin_dir / "README.md").write_text(readme_content)
    print(f"  ✓ Created README.md")

    # Create .gitignore
    gitignore_template = TEMPLATES_DIR / "plugin" / "gitignore"
    gitignore_content = gitignore_template.read_text()
    (plugin_dir / ".gitignore").write_text(gitignore_content)
    print(f"  ✓ Created .gitignore")

    # Create example command
    if with_commands:
        command_vars = {
            **variables,
            "command_name": "example",
            "plugin_name": name
        }
        command_template = TEMPLATES_DIR / "plugin" / "command.md"
        command_content = render_template(command_template, command_vars)
        (plugin_dir / "commands" / "example.md").write_text(command_content)
        print(f"  ✓ Created commands/example.md")

    # Create example skill
    if with_skills:
        skill_dir = plugin_dir / "skills" / "example-skill"
        skill_dir.mkdir(parents=True)
        skill_vars = {
            "name": "example-skill",
            "title": "Example Skill",
            "description": "Example skill for demonstration",
            "use_when": "you need an example"
        }
        skill_template = TEMPLATES_DIR / "skill" / "SKILL.md"
        skill_content = render_template(skill_template, skill_vars)
        (skill_dir / "SKILL.md").write_text(skill_content)
        print(f"  ✓ Created skills/example-skill/SKILL.md")

    # Create example agent
    if with_agents:
        agent_vars = {
            "name": "example-agent",
            "description": "Example agent for demonstration",
            "domain": "example domain",
            "tools": "\"Read\", \"Write\", \"Bash\"",
            "capability_1": "Capability 1",
            "capability_2": "Capability 2",
            "capability_3": "Capability 3",
            "step_1": "Step 1",
            "step_2": "Step 2",
            "step_3": "Step 3",
            "standard_1": "Standard 1",
            "standard_2": "Standard 2",
            "standard_3": "Standard 3",
            "constraint_1": "Constraint 1",
            "constraint_2": "Constraint 2",
            "constraint_3": "Constraint 3",
            "communication_1": "Communication style 1",
            "communication_2": "Communication style 2"
        }
        agent_template = TEMPLATES_DIR / "agent" / "agent.md"
        agent_content = render_template(agent_template, agent_vars)
        (plugin_dir / "agents" / "example-agent.md").write_text(agent_content)
        print(f"  ✓ Created agents/example-agent.md")

    # Create example hooks
    if with_hooks:
        hook_vars = {
            "description": "Example hooks",
            "event": "PreToolUse",
            "matcher": "Write|Edit|Bash",
            "script_name": "example-hook",
            "plugin_name": name
        }
        hooks_template = TEMPLATES_DIR / "hook" / "hooks.json"
        hooks_content = render_template(hooks_template, hook_vars)
        (plugin_dir / "hooks" / "hooks.json").write_text(hooks_content)
        print(f"  ✓ Created hooks/hooks.json")

        script_template = TEMPLATES_DIR / "hook" / "script.py"
        script_content = render_template(script_template, hook_vars)
        script_path = plugin_dir / "hooks" / "scripts" / "example-hook.py"
        script_path.write_text(script_content)
        script_path.chmod(0o755)
        print(f"  ✓ Created hooks/scripts/example-hook.py")

    print(f"\n✓ Plugin created: {plugin_dir}")
    return plugin_dir


def scaffold_skill(
    name: str,
    plugin: str,
    description: str,
    use_when: str
) -> Path:
    """
    Scaffold a new skill in an existing plugin.

    Args:
        name: Skill name (kebab-case)
        plugin: Plugin name
        description: Brief description
        use_when: Usage trigger description

    Returns:
        Path to created skill directory
    """
    # Validate names
    valid, error = validate_name(name, "Skill")
    if not valid:
        raise ValueError(error)

    valid, error = validate_name(plugin, "Plugin")
    if not valid:
        raise ValueError(error)

    # Check plugin exists
    plugin_dir = PROJECT_ROOT / "plugins" / plugin
    if not plugin_dir.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin}")

    # Create skill directory
    skill_dir = plugin_dir / "skills" / name
    if skill_dir.exists():
        raise FileExistsError(f"Skill already exists: {skill_dir}")

    print(f"Creating skill: {name} in {plugin}")

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

    print(f"  ✓ Created SKILL.md")
    print(f"\n✓ Skill created: {skill_dir}")
    return skill_dir


def scaffold_agent(
    name: str,
    plugin: str,
    description: str,
    domain: str,
    tools: List[str]
) -> Path:
    """
    Scaffold a new agent in an existing plugin.

    Args:
        name: Agent name (kebab-case)
        plugin: Plugin name
        description: Brief description
        domain: Domain of expertise
        tools: List of tool names

    Returns:
        Path to created agent file
    """
    # Validate names
    valid, error = validate_name(name, "Agent")
    if not valid:
        raise ValueError(error)

    valid, error = validate_name(plugin, "Plugin")
    if not valid:
        raise ValueError(error)

    # Check plugin exists
    plugin_dir = PROJECT_ROOT / "plugins" / plugin
    if not plugin_dir.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin}")

    # Create agents directory if needed
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # Create agent file
    agent_file = agents_dir / f"{name}.md"
    if agent_file.exists():
        raise FileExistsError(f"Agent already exists: {agent_file}")

    print(f"Creating agent: {name} in {plugin}")

    # Template variables
    tools_str = ', '.join(f'"{tool}"' for tool in tools)
    variables = {
        "name": name,
        "description": description,
        "domain": domain,
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

    print(f"  ✓ Created {name}.md")
    print(f"\n✓ Agent created: {agent_file}")
    return agent_file


def scaffold_hook(
    event: str,
    plugin: str,
    script_name: str,
    description: str,
    matcher: str = "*"
) -> Path:
    """
    Scaffold a new hook in an existing plugin.

    Args:
        event: Hook event (PreToolUse, PostToolUse, etc.)
        plugin: Plugin name
        script_name: Script file name (without .py)
        description: Brief description
        matcher: Tool matcher pattern

    Returns:
        Path to created hooks directory
    """
    # Validate plugin name
    valid, error = validate_name(plugin, "Plugin")
    if not valid:
        raise ValueError(error)

    # Check plugin exists
    plugin_dir = PROJECT_ROOT / "plugins" / plugin
    if not plugin_dir.exists():
        raise FileNotFoundError(f"Plugin not found: {plugin}")

    # Valid events
    valid_events = [
        "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop",
        "SubagentStop", "SessionStart", "SessionEnd", "PreCompact", "Notification"
    ]
    if event not in valid_events:
        raise ValueError(f"Invalid event: {event}. Must be one of: {', '.join(valid_events)}")

    # Create hooks directory if needed
    hooks_dir = plugin_dir / "hooks"
    scripts_dir = hooks_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating hook: {event} in {plugin}")

    # Template variables
    variables = {
        "description": description,
        "event": event,
        "matcher": matcher,
        "script_name": script_name,
        "plugin_name": plugin
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
        print(f"  ✓ Updated hooks/hooks.json")
    else:
        # Create new hooks.json
        hooks_template = TEMPLATES_DIR / "hook" / "hooks.json"
        hooks_content = render_template(hooks_template, variables)
        hooks_json_path.write_text(hooks_content)
        print(f"  ✓ Created hooks/hooks.json")

    # Create hook script
    script_template = TEMPLATES_DIR / "hook" / "script.py"
    script_content = render_template(script_template, variables)
    script_path = scripts_dir / f"{script_name}.py"
    script_path.write_text(script_content)
    script_path.chmod(0o755)
    print(f"  ✓ Created hooks/scripts/{script_name}.py")

    print(f"\n✓ Hook created: {hooks_dir}")
    return hooks_dir


def interactive_plugin():
    """Interactive plugin creation."""
    print("\n=== Plugin Scaffold ===\n")

    name = prompt_user("Plugin name (kebab-case)")
    valid, error = validate_name(name, "Plugin")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")
    author = prompt_user("Author", default="Something Wicked Community")

    with_commands = prompt_user("Include example command? (y/n)", default="n").lower() == 'y'
    with_skills = prompt_user("Include example skill? (y/n)", default="n").lower() == 'y'
    with_agents = prompt_user("Include example agent? (y/n)", default="n").lower() == 'y'
    with_hooks = prompt_user("Include example hooks? (y/n)", default="n").lower() == 'y'

    scaffold_plugin(name, description, author, with_commands, with_skills, with_agents, with_hooks)


def interactive_skill():
    """Interactive skill creation."""
    print("\n=== Skill Scaffold ===\n")

    plugin = prompt_user("Plugin name")
    valid, error = validate_name(plugin, "Plugin")
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

    scaffold_skill(name, plugin, description, use_when)


def interactive_agent():
    """Interactive agent creation."""
    print("\n=== Agent Scaffold ===\n")

    plugin = prompt_user("Plugin name")
    valid, error = validate_name(plugin, "Plugin")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    name = prompt_user("Agent name (kebab-case)")
    valid, error = validate_name(name, "Agent")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

    description = prompt_user("Description")
    domain = prompt_user("Domain of expertise")
    tools_str = prompt_user("Tools (comma-separated)", default="Read,Write,Bash")
    tools = [tool.strip() for tool in tools_str.split(',')]

    scaffold_agent(name, plugin, description, domain, tools)


def interactive_hook():
    """Interactive hook creation."""
    print("\n=== Hook Scaffold ===\n")

    plugin = prompt_user("Plugin name")
    valid, error = validate_name(plugin, "Plugin")
    if not valid:
        print(f"Error: {error}")
        sys.exit(1)

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

    scaffold_hook(event, plugin, script_name, description, matcher)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scaffold marketplace components",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Component type')

    # Plugin subcommand
    plugin_parser = subparsers.add_parser('plugin', help='Scaffold a plugin')
    plugin_parser.add_argument('--name', required=False, help='Plugin name')
    plugin_parser.add_argument('--description', required=False, help='Description')
    plugin_parser.add_argument('--author', default='Something Wicked Community', help='Author name')
    plugin_parser.add_argument('--with-commands', action='store_true', help='Include example command')
    plugin_parser.add_argument('--with-skills', action='store_true', help='Include example skill')
    plugin_parser.add_argument('--with-agents', action='store_true', help='Include example agent')
    plugin_parser.add_argument('--with-hooks', action='store_true', help='Include example hooks')

    # Skill subcommand
    skill_parser = subparsers.add_parser('skill', help='Scaffold a skill')
    skill_parser.add_argument('--name', required=False, help='Skill name')
    skill_parser.add_argument('--plugin', required=False, help='Plugin name')
    skill_parser.add_argument('--description', required=False, help='Description')
    skill_parser.add_argument('--use-when', required=False, help='Usage trigger')

    # Agent subcommand
    agent_parser = subparsers.add_parser('agent', help='Scaffold an agent')
    agent_parser.add_argument('--name', required=False, help='Agent name')
    agent_parser.add_argument('--plugin', required=False, help='Plugin name')
    agent_parser.add_argument('--description', required=False, help='Description')
    agent_parser.add_argument('--domain', required=False, help='Domain of expertise')
    agent_parser.add_argument('--tools', default='Read,Write,Bash', help='Comma-separated tool list')

    # Hook subcommand
    hook_parser = subparsers.add_parser('hook', help='Scaffold a hook')
    hook_parser.add_argument('--event', required=False, help='Hook event')
    hook_parser.add_argument('--plugin', required=False, help='Plugin name')
    hook_parser.add_argument('--script', required=False, help='Script name')
    hook_parser.add_argument('--description', required=False, help='Description')
    hook_parser.add_argument('--matcher', default='*', help='Tool matcher pattern')

    args = parser.parse_args()

    try:
        if args.command == 'plugin':
            if not args.name:
                interactive_plugin()
            else:
                scaffold_plugin(
                    args.name, args.description, args.author,
                    args.with_commands, args.with_skills, args.with_agents, args.with_hooks
                )

        elif args.command == 'skill':
            if not args.name or not args.plugin:
                interactive_skill()
            else:
                scaffold_skill(args.name, args.plugin, args.description, args.use_when)

        elif args.command == 'agent':
            if not args.name or not args.plugin:
                interactive_agent()
            else:
                tools = [tool.strip() for tool in args.tools.split(',')]
                scaffold_agent(args.name, args.plugin, args.description, args.domain, tools)

        elif args.command == 'hook':
            if not args.event or not args.plugin or not args.script:
                interactive_hook()
            else:
                scaffold_hook(args.event, args.plugin, args.script, args.description, args.matcher)

        else:
            # Interactive mode - choose component type
            print("\n=== Component Scaffold ===\n")
            print("Component types:")
            print("  1. Plugin")
            print("  2. Skill")
            print("  3. Agent")
            print("  4. Hook")

            choice = prompt_user("\nSelect type (1-4)")

            if choice == '1':
                interactive_plugin()
            elif choice == '2':
                interactive_skill()
            elif choice == '3':
                interactive_agent()
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
