"""
MCP Bridge

Connects to plugin MCP servers to fetch live data for A2UI documents.
"""

import asyncio
from typing import Any

import httpx


class MCPClient:
    """
    Simple MCP client for HTTP-based MCP servers.

    Connects to plugin servers like wicked-kanban-server.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        """
        Initialize MCP client.

        Args:
            base_url: Server base URL (e.g., http://localhost:18888)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def call(self, method: str, params: dict | None = None) -> Any:
        """
        Call an MCP method.

        Args:
            method: Method name (e.g., 'get_tasks', 'recall')
            params: Method parameters

        Returns:
            Method result
        """
        client = await self._get_client()

        # Try REST-style endpoint first
        url = f"{self.base_url}/api/{method}"
        try:
            if params:
                response = await client.post(url, json=params)
            else:
                response = await client.get(url)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Try MCP JSON-RPC style
                return await self._call_jsonrpc(method, params)
            else:
                response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[MCPClient] HTTP error calling {method}: {e}")
            raise

    async def _call_jsonrpc(self, method: str, params: dict | None = None) -> Any:
        """Call using JSON-RPC protocol."""
        client = await self._get_client()
        url = f"{self.base_url}/mcp"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        response = await client.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        if "error" in result:
            raise Exception(f"MCP error: {result['error']}")
        return result.get("result")

    async def health_check(self) -> bool:
        """Check if server is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class MCPBridge:
    """
    Bridge to multiple MCP servers.

    Manages connections to plugin servers and routes data requests.
    """

    # Default plugin server ports
    DEFAULT_SERVERS = {
        "kanban": "http://localhost:18888",
        "memory": "http://localhost:18890",  # If wicked-mem has a server
    }

    def __init__(self, servers: dict[str, str] | None = None):
        """
        Initialize the MCP bridge.

        Args:
            servers: Map of server names to URLs. Uses defaults if not provided.
        """
        self.server_urls = servers or self.DEFAULT_SERVERS.copy()
        self.clients: dict[str, MCPClient] = {}

    def get_client(self, server: str) -> MCPClient | None:
        """Get or create a client for a server."""
        if server not in self.server_urls:
            return None

        if server not in self.clients:
            self.clients[server] = MCPClient(self.server_urls[server])

        return self.clients[server]

    async def call(self, server: str, method: str, params: dict | None = None) -> Any:
        """
        Call a method on a specific server.

        Args:
            server: Server name (e.g., 'kanban', 'memory')
            method: Method name
            params: Method parameters

        Returns:
            Method result
        """
        client = self.get_client(server)
        if not client:
            raise ValueError(f"Unknown server: {server}")

        return await client.call(method, params)

    async def fetch_for_document(self, data_needs: list[str]) -> dict[str, Any]:
        """
        Fetch data based on document needs.

        Analyzes what data types are needed and fetches from appropriate servers.

        Args:
            data_needs: List of data types needed (e.g., ['tasks', 'memories', 'stats'])

        Returns:
            Dictionary of fetched data
        """
        data: dict[str, Any] = {}
        tasks = []

        if "tasks" in data_needs:
            tasks.append(self._fetch_tasks(data))
        if "memories" in data_needs:
            tasks.append(self._fetch_memories(data))
        if "stats" in data_needs:
            tasks.append(self._fetch_stats(data))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return data

    async def _fetch_tasks(self, data: dict) -> None:
        """Fetch tasks from kanban server."""
        try:
            client = self.get_client("kanban")
            if client and await client.health_check():
                # Try different endpoints
                try:
                    result = await client.call("tasks")
                    data["tasks"] = result if isinstance(result, list) else result.get("tasks", [])
                except Exception:
                    # Try projects endpoint
                    projects = await client.call("projects")
                    if projects:
                        project_id = projects[0].get("id") if isinstance(projects, list) else None
                        if project_id:
                            tasks_result = await client.call(f"projects/{project_id}/tasks")
                            data["tasks"] = tasks_result if isinstance(tasks_result, list) else []
        except Exception as e:
            print(f"[MCPBridge] Failed to fetch tasks: {e}")
            data["tasks"] = []

    async def _fetch_memories(self, data: dict) -> None:
        """Fetch memories from memory server."""
        try:
            client = self.get_client("memory")
            if client and await client.health_check():
                result = await client.call("recall", {"limit": 10})
                data["memories"] = result if isinstance(result, list) else result.get("memories", [])
        except Exception as e:
            print(f"[MCPBridge] Failed to fetch memories: {e}")
            data["memories"] = []

    async def _fetch_stats(self, data: dict) -> None:
        """Fetch stats from kanban server."""
        try:
            client = self.get_client("kanban")
            if client and await client.health_check():
                result = await client.call("stats")
                data["stats"] = result if isinstance(result, dict) else {}
        except Exception as e:
            print(f"[MCPBridge] Failed to fetch stats: {e}")
            data["stats"] = {}

    async def check_servers(self) -> dict[str, bool]:
        """Check which servers are available."""
        results = {}
        for name in self.server_urls:
            client = self.get_client(name)
            if client:
                results[name] = await client.health_check()
            else:
                results[name] = False
        return results

    async def close(self):
        """Close all clients."""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
