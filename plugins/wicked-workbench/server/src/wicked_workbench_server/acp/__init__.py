"""ACP Bridge module for wicked-workbench server.

This module manages communication between browser clients and the claude-code-acp
subprocess via WebSocket and JSON-RPC.
"""

from .acp_manager import ACPManager
from .acp_bridge import ACPBridge
from .routes import router, init_acp, cleanup_acp

__all__ = [
    "ACPManager",
    "ACPBridge",
    "router",
    "init_acp",
    "cleanup_acp",
]
