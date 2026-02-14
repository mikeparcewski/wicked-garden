"""Data Gateway REST API router.

Provides:
  GET /api/v1/data/plugins          — List all plugins with data sources
  GET /api/v1/data/{plugin}         — Get plugin data source info
  GET /api/v1/data/{plugin}/{source}/{verb}      — Proxy to plugin api.py
  GET /api/v1/data/{plugin}/{source}/{verb}/{id} — Proxy with ID (for get)
  POST /api/v1/data/refresh         — Refresh plugin discovery
"""
import asyncio
import json
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .discovery import PluginDataRegistry

router = APIRouter(prefix="/api/v1/data", tags=["data-gateway"])

VALID_VERBS = {"list", "get", "search", "stats"}

_registry: Optional[PluginDataRegistry] = None


def init_gateway(local_repo=None):
    """Initialize the data gateway registry."""
    global _registry
    _registry = PluginDataRegistry()
    _registry.discover(local_repo=local_repo)
    return _registry


def _get_registry() -> PluginDataRegistry:
    """Get the singleton registry."""
    if _registry is None:
        raise HTTPException(500, {"error": "Data gateway not initialized", "code": "NOT_INITIALIZED"})
    return _registry


@router.get("/plugins")
async def list_plugins():
    """List all plugins with data sources."""
    reg = _get_registry()
    plugins = reg.get_plugins()
    return {
        "plugins": plugins,
        "meta": {
            "total_plugins": len(plugins),
            "total_sources": sum(len(p["sources"]) for p in plugins),
            "schema_version": "1.0.0",
        },
    }


@router.get("/plugins/{plugin}")
async def get_plugin(plugin: str):
    """Get a specific plugin's data source info."""
    reg = _get_registry()
    info = reg.get_plugin(plugin)
    if not info:
        raise HTTPException(404, {
            "error": "Plugin not found or has no data sources",
            "code": "PLUGIN_NOT_FOUND",
            "plugin": plugin,
        })
    return {
        "plugin": plugin,
        "schema_version": info["schema_version"],
        "sources": [
            {
                "name": name,
                "description": src.get("description", ""),
                "capabilities": src.get("capabilities", []),
            }
            for name, src in info["sources"].items()
        ],
    }


@router.get("/{plugin}/{source}/{verb}")
@router.get("/{plugin}/{source}/{verb}/{item_id}")
async def proxy_data_request(
    plugin: str,
    source: str,
    verb: str,
    item_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    query: Optional[str] = None,
    project: Optional[str] = None,
    filter: Optional[str] = None,
):
    """Proxy a data request to a plugin's api.py via subprocess."""
    reg = _get_registry()

    # Validate verb
    if verb not in VALID_VERBS:
        raise HTTPException(400, {
            "error": f"Invalid verb '{verb}'",
            "code": "INVALID_VERB",
            "valid_verbs": sorted(VALID_VERBS),
        })

    # Validate request
    error = reg.validate_request(plugin, source, verb)
    if error:
        status = 404 if "not found" in error.lower() else 400
        raise HTTPException(status, {"error": error, "code": "INVALID_REQUEST"})

    if verb == "get" and not item_id:
        raise HTTPException(400, {"error": "ID required for get verb", "code": "MISSING_ID"})

    # Build command
    api_script = reg.get_api_script(plugin)
    cmd = [sys.executable, api_script, verb, source]

    if verb == "get" and item_id:
        cmd.append(item_id)

    cmd.extend(["--limit", str(limit)])
    cmd.extend(["--offset", str(offset)])
    if query:
        cmd.extend(["--query", query])
    if project:
        cmd.extend(["--project", project])
    if filter:
        cmd.extend(["--filter", filter])

    # Run subprocess
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

        if proc.returncode != 0:
            try:
                error_data = json.loads(stderr.decode())
                raise HTTPException(400, error_data)
            except json.JSONDecodeError:
                raise HTTPException(500, {
                    "error": "Plugin API returned non-zero exit",
                    "code": "PLUGIN_ERROR",
                    "stderr": stderr.decode()[:500],
                })

        result = json.loads(stdout.decode())

        # Enrich meta with gateway info
        if "meta" not in result:
            result["meta"] = {}
        result["meta"]["plugin"] = plugin
        result["meta"]["source"] = source

        return result

    except asyncio.TimeoutError:
        raise HTTPException(504, {
            "error": "Plugin API timeout (10s)",
            "code": "TIMEOUT",
            "plugin": plugin,
        })
    except json.JSONDecodeError:
        raise HTTPException(500, {
            "error": "Invalid JSON from plugin API",
            "code": "INVALID_JSON",
            "plugin": plugin,
        })


@router.post("/refresh")
async def refresh_registry():
    """Refresh plugin discovery."""
    reg = _get_registry()
    reg.discover(local_repo=reg._local_base)
    return {
        "status": "refreshed",
        "plugins": len(reg.registry),
    }
