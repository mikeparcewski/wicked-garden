"""Data Gateway REST API router.

Provides:
  GET  /api/v1/data/plugins                          — List all plugins with data sources
  GET  /api/v1/data/{plugin}                         — Get plugin data source info
  GET  /api/v1/data/{plugin}/{source}/{verb}         — Proxy read to plugin api.py
  GET  /api/v1/data/{plugin}/{source}/{verb}/{id}    — Proxy read with ID (for get)
  POST /api/v1/data/{plugin}/{source}/create         — Create a resource
  PUT  /api/v1/data/{plugin}/{source}/update/{id}    — Update a resource
  DELETE /api/v1/data/{plugin}/{source}/delete/{id}  — Delete a resource
  POST /api/v1/data/refresh                          — Refresh plugin discovery
"""
import asyncio
import json
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .discovery import PluginDataRegistry

router = APIRouter(prefix="/api/v1/data", tags=["data-gateway"])

READ_VERBS = {"list", "get", "search", "stats", "traverse", "hotspots"}
WRITE_VERBS = {"create", "update", "delete"}
VALID_VERBS = READ_VERBS | WRITE_VERBS

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


async def _run_subprocess(cmd, input_data=None, timeout=10.0):
    """Run a plugin api.py subprocess and return parsed JSON result."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_data), timeout=timeout
        )

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

        return json.loads(stdout.decode())

    except asyncio.TimeoutError:
        raise HTTPException(504, {"error": "Plugin API timeout (10s)", "code": "TIMEOUT"})
    except json.JSONDecodeError:
        raise HTTPException(500, {"error": "Invalid JSON from plugin API", "code": "INVALID_JSON"})


def _enrich_meta(result, plugin, source, verb=None, item_id=None):
    """Add gateway metadata to a plugin response."""
    if "meta" not in result:
        result["meta"] = {}
    result["meta"]["plugin"] = plugin
    result["meta"]["source"] = source
    if verb:
        result["meta"]["verb"] = verb
    if item_id:
        result["meta"]["item_id"] = item_id
    return result


# ==================== Read Routes ====================


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
    depth: Optional[int] = Query(None, ge=1, le=10),
    direction: Optional[str] = Query(None, pattern="^(both|in|out)$"),
    layer: Optional[str] = None,
    type: Optional[str] = None,
):
    """Proxy a read request to a plugin's api.py via subprocess."""
    reg = _get_registry()

    # Only allow read verbs on GET
    if verb not in READ_VERBS:
        raise HTTPException(400, {
            "error": f"Invalid read verb '{verb}'",
            "code": "INVALID_VERB",
            "valid_verbs": sorted(READ_VERBS),
            "hint": "Use POST/PUT/DELETE for write operations",
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
    if depth is not None:
        cmd.extend(["--depth", str(depth)])
    if direction:
        cmd.extend(["--direction", direction])
    if layer:
        cmd.extend(["--layer", layer])
    if type:
        cmd.extend(["--type", type])

    result = await _run_subprocess(cmd)
    return _enrich_meta(result, plugin, source)


# ==================== Write Routes ====================


@router.post("/{plugin}/{source}/create")
async def create_resource(plugin: str, source: str, request: Request):
    """Create a new resource via plugin api.py."""
    reg = _get_registry()
    verb = "create"

    error = reg.validate_request(plugin, source, verb)
    if error:
        status = 404 if "not found" in error.lower() else 403
        raise HTTPException(status, {"error": error, "code": "CAPABILITY_NOT_SUPPORTED"})

    body = await request.json()
    api_script = reg.get_api_script(plugin)
    cmd = [sys.executable, api_script, verb, source]
    input_data = json.dumps(body).encode()

    result = await _run_subprocess(cmd, input_data=input_data)
    return JSONResponse(
        content=_enrich_meta(result, plugin, source, verb=verb),
        status_code=201,
    )


@router.put("/{plugin}/{source}/update/{item_id}")
async def update_resource(plugin: str, source: str, item_id: str, request: Request):
    """Update an existing resource via plugin api.py."""
    reg = _get_registry()
    verb = "update"

    error = reg.validate_request(plugin, source, verb)
    if error:
        status = 404 if "not found" in error.lower() else 403
        raise HTTPException(status, {"error": error, "code": "CAPABILITY_NOT_SUPPORTED"})

    body = await request.json()
    api_script = reg.get_api_script(plugin)
    cmd = [sys.executable, api_script, verb, source, item_id]
    input_data = json.dumps(body).encode()

    result = await _run_subprocess(cmd, input_data=input_data)
    return _enrich_meta(result, plugin, source, verb=verb, item_id=item_id)


@router.delete("/{plugin}/{source}/delete/{item_id}")
async def delete_resource(plugin: str, source: str, item_id: str):
    """Delete a resource via plugin api.py."""
    reg = _get_registry()
    verb = "delete"

    error = reg.validate_request(plugin, source, verb)
    if error:
        status = 404 if "not found" in error.lower() else 403
        raise HTTPException(status, {"error": error, "code": "CAPABILITY_NOT_SUPPORTED"})

    api_script = reg.get_api_script(plugin)
    cmd = [sys.executable, api_script, verb, source, item_id]

    result = await _run_subprocess(cmd)
    return _enrich_meta(result, plugin, source, verb=verb, item_id=item_id)


# ==================== Management ====================


@router.post("/refresh")
async def refresh_registry():
    """Refresh plugin discovery."""
    reg = _get_registry()
    reg.discover(local_repo=reg._local_base)
    return {
        "status": "refreshed",
        "plugins": len(reg.registry),
    }
