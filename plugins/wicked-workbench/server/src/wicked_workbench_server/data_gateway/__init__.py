"""Plugin Data Gateway — discovers and proxies requests to plugin api.py scripts."""
from .discovery import PluginDataRegistry
from .router import router, init_gateway

__all__ = ["PluginDataRegistry", "router", "init_gateway"]
