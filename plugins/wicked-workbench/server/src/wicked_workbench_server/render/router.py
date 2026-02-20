"""A2UI Render REST API router.

Provides:
  POST /api/render                  — Submit an A2UI document for rendering
  GET  /api/render/surfaces         — List all active surfaces
  GET  /api/render/surfaces/{id}    — Get a specific surface's components
  DELETE /api/render/surfaces/{id}  — Delete a surface
"""
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .surfaces import SurfaceStore

router = APIRouter(prefix="/api/render", tags=["render"])

_store: Optional[SurfaceStore] = None


def init_render() -> SurfaceStore:
    """Initialize the render surface store."""
    global _store
    _store = SurfaceStore()
    return _store


def _get_store() -> SurfaceStore:
    """Get the singleton store."""
    if _store is None:
        raise HTTPException(500, {"error": "Render pipeline not initialized", "code": "NOT_INITIALIZED"})
    return _store


@router.post("")
async def render_document(request: Request):
    """Accept an A2UI document and render it.

    Request body:
    {
        "document": [
            {"createSurface": {"surfaceId": "dashboard", "catalogId": "workbench"}},
            {"updateComponents": {"surfaceId": "dashboard", "components": [...]}}
        ],
        "title": "My Dashboard",      // optional
        "fetch_data": false            // optional: if true, resolve data bindings
    }

    Returns the affected surface IDs and a URL to view the rendered dashboard.
    """
    store = _get_store()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, {"error": "Invalid JSON body", "code": "INVALID_JSON"})

    document = body.get("document")
    if not document:
        raise HTTPException(400, {
            "error": "Missing 'document' field",
            "code": "MISSING_DOCUMENT",
            "hint": "Provide an A2UI document array with createSurface and updateComponents messages",
        })

    if not isinstance(document, list):
        raise HTTPException(400, {
            "error": "'document' must be an array of A2UI messages",
            "code": "INVALID_DOCUMENT",
        })

    # Validate document messages
    valid_keys = {"createSurface", "updateComponents", "updateDataModel"}
    for i, msg in enumerate(document):
        if not isinstance(msg, dict):
            raise HTTPException(400, {
                "error": f"Document message at index {i} must be an object",
                "code": "INVALID_MESSAGE",
            })
        msg_keys = set(msg.keys())
        if not msg_keys & valid_keys:
            raise HTTPException(400, {
                "error": f"Document message at index {i} has no valid A2UI key",
                "code": "INVALID_MESSAGE",
                "valid_keys": sorted(valid_keys),
            })

    # Process the document
    affected = store.process_document(document)

    # Build response
    host = os.environ.get("WICKED_WORKBENCH_HOST", "127.0.0.1")
    port = os.environ.get("WICKED_WORKBENCH_PORT", "18889")
    base_url = f"http://{host}:{port}"

    surfaces = []
    for sid in affected:
        surface = store.get(sid)
        if surface:
            surfaces.append({
                "surfaceId": sid,
                "componentCount": len(surface.components),
                "url": f"{base_url}/#/surface/{sid}",
            })

    return JSONResponse(
        content={
            "status": "rendered",
            "surfaces": surfaces,
            "dashboard_url": f"{base_url}",
            "meta": {
                "surfaces_affected": len(affected),
                "total_surfaces": len(store.list_all()),
            },
        },
        status_code=201,
    )


@router.get("/surfaces")
async def list_surfaces():
    """List all active surfaces."""
    store = _get_store()
    surfaces = store.list_all()
    return {
        "surfaces": surfaces,
        "meta": {
            "total": len(surfaces),
        },
    }


@router.get("/surfaces/{surface_id}")
async def get_surface(surface_id: str):
    """Get a specific surface's component tree."""
    store = _get_store()
    surface = store.get(surface_id)

    if not surface:
        raise HTTPException(404, {
            "error": f"Surface '{surface_id}' not found",
            "code": "SURFACE_NOT_FOUND",
        })

    return surface.to_dict()


@router.delete("/surfaces/{surface_id}")
async def delete_surface(surface_id: str):
    """Delete a surface."""
    store = _get_store()
    if store.delete(surface_id):
        return {"status": "deleted", "surfaceId": surface_id}

    raise HTTPException(404, {
        "error": f"Surface '{surface_id}' not found",
        "code": "SURFACE_NOT_FOUND",
    })
