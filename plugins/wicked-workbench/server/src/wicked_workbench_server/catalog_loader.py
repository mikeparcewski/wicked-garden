"""
Catalog Loader

Discovers and loads A2UI component catalogs from wicked-garden plugins.
"""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ComponentProp(BaseModel):
    """Component property definition."""
    type: str | list[str]
    description: str
    required: bool = False
    default: Any = None
    enum: list[str] | None = None


class ComponentSlot(BaseModel):
    """Component slot definition."""
    role: str
    description: str
    accepts: list[str] | None = None


class ComponentDef(BaseModel):
    """Component definition."""
    description: str
    category: str | None = None
    props: dict[str, ComponentProp] = {}
    slots: dict[str, ComponentSlot] = {}
    examples: list[dict] = []


class IntentDef(BaseModel):
    """Intent definition."""
    description: str
    suggestedComponents: list[str] = []
    suggestedFilter: dict | None = None
    requiredData: list[str] = []


class RendererDef(BaseModel):
    """Renderer definition."""
    type: str  # esm, web-component, remote
    path: str
    exports: str | None = None


class Catalog(BaseModel):
    """A2UI component catalog."""
    catalogId: str
    version: str
    description: str = ""
    components: dict[str, ComponentDef]
    intents: dict[str, IntentDef] = {}
    renderer: RendererDef | None = None

    @property
    def id(self) -> str:
        return self.catalogId


class CatalogLoader:
    """
    Discovers and loads A2UI catalogs from plugins.

    Scans plugin directories for .claude-plugin/catalog.json files.
    """

    def __init__(self, plugins_dir: str | None = None):
        """
        Initialize the catalog loader.

        Args:
            plugins_dir: Directory containing plugins. Defaults to ~/.claude/plugins
        """
        if plugins_dir:
            self.plugins_dir = Path(plugins_dir)
        else:
            # Default Claude Code plugins location
            self.plugins_dir = Path.home() / ".claude" / "plugins"

        self.catalogs: dict[str, Catalog] = {}

    def discover(self) -> list[Catalog]:
        """
        Discover all catalogs from installed plugins.

        Returns:
            List of loaded catalogs
        """
        discovered = []

        if not self.plugins_dir.exists():
            print(f"[CatalogLoader] Plugins directory not found: {self.plugins_dir}")
            return discovered

        # Scan for plugin directories
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            catalog_path = plugin_dir / ".claude-plugin" / "catalog.json"
            if catalog_path.exists():
                try:
                    catalog = self.load_catalog(catalog_path)
                    self.catalogs[catalog.id] = catalog
                    discovered.append(catalog)
                    print(f"[CatalogLoader] Loaded: {catalog.id} v{catalog.version} ({len(catalog.components)} components)")
                except Exception as e:
                    print(f"[CatalogLoader] Failed to load {plugin_dir.name}: {e}")

        return discovered

    def load_catalog(self, path: Path) -> Catalog:
        """
        Load a single catalog from a JSON file.

        Args:
            path: Path to catalog.json

        Returns:
            Loaded catalog
        """
        with open(path) as f:
            data = json.load(f)

        return Catalog(**data)

    def load_from_json(self, data: dict) -> Catalog:
        """
        Load a catalog from a dictionary.

        Args:
            data: Catalog data

        Returns:
            Loaded catalog
        """
        catalog = Catalog(**data)
        self.catalogs[catalog.id] = catalog
        return catalog

    def get_catalog(self, catalog_id: str) -> Catalog | None:
        """Get a loaded catalog by ID."""
        return self.catalogs.get(catalog_id)

    def get_all_catalogs(self) -> list[Catalog]:
        """Get all loaded catalogs."""
        return list(self.catalogs.values())

    def get_merged_catalog(self, catalog_id: str = "workbench") -> Catalog:
        """
        Create a merged catalog from all loaded catalogs.

        Args:
            catalog_id: ID for the merged catalog

        Returns:
            Merged catalog containing all components and intents
        """
        merged_components: dict[str, ComponentDef] = {}
        merged_intents: dict[str, IntentDef] = {}

        for catalog in self.catalogs.values():
            # Add components (no prefix, assume unique names)
            for name, comp in catalog.components.items():
                merged_components[name] = comp

            # Add intents with catalog prefix
            for name, intent in catalog.intents.items():
                prefixed_name = f"{catalog.id}:{name}"
                merged_intents[prefixed_name] = intent

        return Catalog(
            catalogId=catalog_id,
            version="1.0.0",
            description=f"Combined catalog from: {', '.join(self.catalogs.keys())}",
            components=merged_components,
            intents=merged_intents
        )
