"""Plugin data source discovery.

Scans for plugins with data sources declared in their wicked.json.
Uses same two-tier lookup as wicked-smaht: cache path first, local repo fallback.
"""
import json
import re
from pathlib import Path
from typing import Optional


_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def _semver_key(path: Path) -> tuple:
    """Extract semver tuple from path name for sorting."""
    m = _SEMVER_RE.match(path.name)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (0, 0, 0)


class PluginDataRegistry:
    """Discovers and caches plugin data source metadata."""

    def __init__(self):
        self.registry: dict = {}
        self._cache_base = Path.home() / ".claude" / "plugins" / "cache" / "wicked-garden"
        self._local_base: Optional[Path] = None

    def discover(self, local_repo: Optional[Path] = None):
        """Scan for plugins with data_sources declarations.

        Checks two locations:
        1. Cache: ~/.claude/plugins/cache/wicked-garden/{plugin}/{version}/
        2. Local repo: {local_repo}/plugins/{plugin}/ (if provided)
        """
        self._local_base = local_repo
        self.registry.clear()

        # Scan cache (highest version wins)
        if self._cache_base.exists():
            for plugin_dir in self._cache_base.iterdir():
                if not plugin_dir.is_dir() or not plugin_dir.name.startswith("wicked-"):
                    continue

                # Find highest version
                versions = [v for v in plugin_dir.iterdir() if v.is_dir() and _SEMVER_RE.match(v.name)]
                if not versions:
                    continue
                latest = max(versions, key=_semver_key)

                self._register_plugin(latest)

        # Scan local repo (overrides cache)
        if local_repo:
            plugins_dir = local_repo / "plugins"
            if plugins_dir.exists():
                for plugin_dir in plugins_dir.iterdir():
                    if plugin_dir.is_dir() and plugin_dir.name.startswith("wicked-"):
                        self._register_plugin(plugin_dir)

    def _register_plugin(self, plugin_root: Path):
        """Register a plugin's data sources from its wicked.json."""
        wj = plugin_root / "wicked.json"
        if not wj.exists():
            return

        try:
            data = json.loads(wj.read_text())
        except (json.JSONDecodeError, OSError):
            return

        sources = data.get("sources", [])
        if not sources:
            return

        api_script_rel = data.get("api_script", "scripts/api.py")
        api_script = plugin_root / api_script_rel
        if not api_script.exists():
            return

        # Get plugin name from plugin.json or directory name
        plugin_name = plugin_root.name
        pj = plugin_root / ".claude-plugin" / "plugin.json"
        if pj.exists():
            try:
                pj_data = json.loads(pj.read_text())
                plugin_name = pj_data.get("name", plugin_name)
            except (json.JSONDecodeError, OSError):
                pass

        schema = data.get("$schema", "wicked-data/1.0.0")
        schema_version = schema.split("/")[-1] if "/" in schema else "1.0.0"

        self.registry[plugin_name] = {
            "sources": {src["name"]: src for src in sources},
            "api_script": str(api_script),
            "schema_version": schema_version,
            "plugin_root": str(plugin_root),
        }

    def get_plugins(self) -> list:
        """List all plugins with data sources."""
        return [
            {
                "name": name,
                "schema_version": info["schema_version"],
                "sources": [
                    {
                        "name": src_name,
                        "description": src.get("description", ""),
                        "capabilities": src.get("capabilities", []),
                    }
                    for src_name, src in info["sources"].items()
                ],
            }
            for name, info in sorted(self.registry.items())
        ]

    def get_plugin(self, name: str) -> Optional[dict]:
        """Get a specific plugin's data source info."""
        return self.registry.get(name)

    def get_api_script(self, name: str) -> Optional[str]:
        """Get the path to a plugin's api.py script."""
        info = self.registry.get(name)
        return info["api_script"] if info else None

    def validate_request(self, plugin: str, source: str, verb: str) -> Optional[str]:
        """Validate a data request. Returns error message or None if valid."""
        info = self.registry.get(plugin)
        if not info:
            return f"Plugin '{plugin}' not found or has no data sources"

        src = info["sources"].get(source)
        if not src:
            return f"Source '{source}' not found in plugin '{plugin}'"

        caps = src.get("capabilities", [])
        if verb not in caps:
            return f"Verb '{verb}' not supported for source '{source}' (supported: {caps})"

        return None
