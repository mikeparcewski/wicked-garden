"""
Wicked Workbench Server

A2UI-powered dashboard server that combines UI components from wicked-garden plugins
into unified, AI-generated interfaces.
"""

import os


def main():
    """Entry point for the wicked-workbench command."""
    import uvicorn
    from .app import app

    port = int(os.environ.get("WICKED_WORKBENCH_PORT", 18889))
    host = os.environ.get("WICKED_WORKBENCH_HOST", "127.0.0.1")

    print(f"Starting Wicked Workbench at http://{host}:{port}")
    print(f"Dashboard UI: http://{host}:{port}/")
    print(f"API docs: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


from .app import app
from .catalog_loader import CatalogLoader
from .prompt_generator import PromptGenerator
from .bridges import MCPBridge, MCPClient

__all__ = ["main", "app", "CatalogLoader", "PromptGenerator", "MCPBridge", "MCPClient"]
__version__ = "0.2.0"
