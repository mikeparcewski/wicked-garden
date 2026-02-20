"""In-memory surface store for A2UI documents.

Surfaces hold the current component tree state. Claude POSTs an A2UI document
via /api/render, which creates/updates surfaces. The frontend fetches surfaces
via GET /api/render/{surfaceId} to render the component tree.
"""
import time
from typing import Optional


class Surface:
    """A single rendered surface holding an A2UI component tree."""

    __slots__ = ("surface_id", "catalog_id", "components", "created_at", "updated_at")

    def __init__(self, surface_id: str, catalog_id: Optional[str] = None):
        self.surface_id = surface_id
        self.catalog_id = catalog_id
        self.components: list[dict] = []
        self.created_at = time.time()
        self.updated_at = self.created_at

    def update_components(self, components: list[dict]):
        """Replace the component tree."""
        self.components = components
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "surfaceId": self.surface_id,
            "catalogId": self.catalog_id,
            "components": self.components,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class SurfaceStore:
    """In-memory store for active surfaces."""

    def __init__(self):
        self._surfaces: dict[str, Surface] = {}

    def get(self, surface_id: str) -> Optional[Surface]:
        return self._surfaces.get(surface_id)

    def list_all(self) -> list[dict]:
        return [s.to_dict() for s in self._surfaces.values()]

    def process_document(self, document: list[dict]) -> list[str]:
        """Process an A2UI document (list of messages) and return affected surface IDs."""
        affected = []

        for msg in document:
            if "createSurface" in msg:
                payload = msg["createSurface"]
                sid = payload["surfaceId"]
                catalog_id = payload.get("catalogId")
                self._surfaces[sid] = Surface(sid, catalog_id)
                affected.append(sid)

            elif "updateComponents" in msg:
                payload = msg["updateComponents"]
                sid = payload["surfaceId"]
                components = payload.get("components", [])
                surface = self._surfaces.get(sid)
                if not surface:
                    # Auto-create surface if it doesn't exist
                    surface = Surface(sid)
                    self._surfaces[sid] = surface
                surface.update_components(components)
                if sid not in affected:
                    affected.append(sid)

            elif "updateDataModel" in msg:
                payload = msg["updateDataModel"]
                sid = payload["surfaceId"]
                # Data model updates are handled client-side;
                # store them so the frontend can apply them
                surface = self._surfaces.get(sid)
                if surface:
                    if sid not in affected:
                        affected.append(sid)

        return affected

    def delete(self, surface_id: str) -> bool:
        if surface_id in self._surfaces:
            del self._surfaces[surface_id]
            return True
        return False

    def clear(self):
        self._surfaces.clear()
