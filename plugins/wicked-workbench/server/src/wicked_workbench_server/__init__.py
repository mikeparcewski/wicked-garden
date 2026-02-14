"""
Wicked Workbench Server

Plugin data gateway and dashboard for wicked-garden.
Discovers plugins, proxies data API requests, and provides data model introspection.
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


__all__ = ["main"]
__version__ = "0.2.0"
