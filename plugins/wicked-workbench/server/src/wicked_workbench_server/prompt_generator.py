"""
Prompt Generator

Generates AI system prompts from A2UI catalogs.
"""

from .catalog_loader import Catalog, ComponentDef, IntentDef


class PromptGenerator:
    """
    Generates AI system prompts for A2UI document generation.

    Converts catalog definitions into LLM-friendly instructions.
    """

    A2UI_FORMAT_SPEC = '''You generate A2UI documents - declarative JSON that describes UI without executable code.

## A2UI Format

An A2UI document is a JSON array of messages:

1. **createSurface** - Initialize a rendering surface
   `{ "createSurface": { "surfaceId": "unique-id", "catalogId": "catalog-name" } }`

2. **updateComponents** - Add/update components (flat list with ID references)
   `{ "updateComponents": { "surfaceId": "...", "components": [...] } }`

3. **updateDataModel** - Provide data for bindings
   `{ "updateDataModel": { "surfaceId": "...", "actorId": "agent", "updates": [...] } }`

## Component Structure

Each component has:
- `id`: unique string (one must be "root")
- `component`: type name from catalog
- `children`: array of child component IDs (for containers)
- Component-specific props

## Data Binding

- Path binding: `{ "path": "/some/path" }` - resolves from dataModel
- Interpolation: `"Hello ${/user/name}"` - embeds values in strings

## Base Components (all catalogs)

- **Column**: Vertical stack layout. Slots: children (any)
- **Row**: Horizontal stack layout. Slots: children (any)
- **Text**: Text display. Props: text (string), variant (heading|muted)
'''

    RULES = '''## Rules

1. Always output valid JSON array
2. First message must be `createSurface` with valid catalogId
3. Components must include a "root" component
4. Reference children by ID string, not inline objects
5. Use meaningful, unique IDs
6. Match props to catalog definitions
7. Use data bindings for dynamic values'''

    def __init__(self):
        self.catalogs: list[Catalog] = []

    def add_catalog(self, catalog: Catalog) -> None:
        """Add a catalog to the prompt."""
        self.catalogs.append(catalog)

    def generate_catalog_section(self, catalog: Catalog) -> str:
        """
        Generate prompt section for a single catalog.

        Args:
            catalog: The catalog to document

        Returns:
            Formatted prompt section
        """
        lines = []

        lines.append(f"### {catalog.id} catalog")
        if catalog.description:
            lines.append(catalog.description)
        lines.append("")

        # Components
        lines.append("**Components:**")
        for name, comp in catalog.components.items():
            lines.append(f"- **{name}**: {comp.description}")

            # Props
            if comp.props:
                prop_descs = []
                for prop_name, prop_def in comp.props.items():
                    prop_str = prop_name
                    if prop_def.required:
                        prop_str += " (required)"
                    if prop_def.enum:
                        prop_str += f": {' | '.join(prop_def.enum)}"
                    elif isinstance(prop_def.type, list):
                        prop_str += f": {' | '.join(prop_def.type)}"
                    else:
                        prop_str += f": {prop_def.type}"
                    prop_descs.append(prop_str)
                lines.append(f"  Props: {', '.join(prop_descs)}")

            # Slots
            if comp.slots:
                slot_descs = []
                for slot_name, slot_def in comp.slots.items():
                    accepts = ", ".join(slot_def.accepts) if slot_def.accepts else "any"
                    slot_descs.append(f"{slot_name} ({accepts})")
                lines.append(f"  Slots: {', '.join(slot_descs)}")

            lines.append("")

        # Intents
        if catalog.intents:
            lines.append("**Intents:**")
            for name, intent in catalog.intents.items():
                components = " + ".join(intent.suggestedComponents) if intent.suggestedComponents else ""
                lines.append(f'- "{name}" → {components}')
                lines.append(f"  {intent.description}")
            lines.append("")

        return "\n".join(lines)

    def generate_system_prompt(self, catalogs: list[Catalog] | None = None) -> str:
        """
        Generate complete system prompt from catalogs.

        Args:
            catalogs: List of catalogs to include. Uses added catalogs if None.

        Returns:
            Complete system prompt for A2UI generation
        """
        cats = catalogs or self.catalogs

        sections = [self.A2UI_FORMAT_SPEC]

        # Available catalogs
        sections.append("\n## Available Catalogs\n")
        catalog_ids = []
        for catalog in cats:
            sections.append(self.generate_catalog_section(catalog))
            catalog_ids.append(catalog.id)

        # Add workbench as combined catalog option
        if len(cats) > 1:
            sections.append(f"\n### workbench catalog")
            sections.append(f"Combined catalog with all components from: {', '.join(catalog_ids)}")
            sections.append("Use catalogId 'workbench' to access all components.\n")

        sections.append(self.RULES)

        return "\n".join(sections)

    def get_catalog_ids(self, catalogs: list[Catalog] | None = None) -> list[str]:
        """Get available catalog IDs."""
        cats = catalogs or self.catalogs
        ids = [c.id for c in cats]
        if len(cats) > 1:
            ids.append("workbench")
        return ids

    def estimate_tokens(self, prompt: str) -> int:
        """Rough token estimate (chars / 4)."""
        return len(prompt) // 4
