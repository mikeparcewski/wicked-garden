"""
Wicked Workbench Server

FastAPI application serving the plugin data gateway and dashboard.
Discovers installed wicked-garden plugins and proxies data API requests.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import init_db, router as auth_router
from .bridges.mcp_bridge import MCPBridge
from .acp import router as acp_router, init_acp, cleanup_acp
from .data_gateway import router as data_gateway_router, init_gateway
from .render import router as render_router, init_render


# Global state
mcp_bridge: MCPBridge | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global mcp_bridge

    # Initialize database
    print("[Workbench] Initializing database...")
    init_db()

    # Initialize MCP bridge
    mcp_bridge = MCPBridge()

    # Initialize Plugin Data Gateway
    plugins_dir = os.environ.get("WICKED_PLUGINS_DIR")
    local_repo = Path(plugins_dir).parent if plugins_dir else None
    gateway_reg = init_gateway(local_repo=local_repo)
    print(f"[Workbench] Data Gateway ready with {len(gateway_reg.registry)} data plugins")

    # Initialize A2UI Render Pipeline
    init_render()
    print("[Workbench] A2UI Render Pipeline ready")

    # Initialize ACP bridge (optional - gracefully degrades if claude-code-acp not installed)
    try:
        await init_acp()
        print("[Workbench] ACP Bridge initialized")
    except Exception as e:
        print(f"[Workbench] ACP Bridge not available: {e}")
        print("[Workbench] Install with: npm install -g @zed-industries/claude-code-acp")

    yield

    # Cleanup
    await cleanup_acp()
    if mcp_bridge:
        await mcp_bridge.close()


app = FastAPI(
    title="Wicked Workbench",
    description="Plugin data gateway and dashboard for wicked-garden. Discovers plugins, proxies data API requests, and provides data model introspection.",
    version="0.2.0",
    lifespan=lifespan
)

# Session middleware for OAuth state management — no hardcoded default
_session_secret = os.environ.get("SESSION_SECRET_KEY", "")
if not _session_secret:
    import secrets as _secrets
    _session_secret = _secrets.token_urlsafe(32)
    import sys as _sys
    print(
        "[Workbench] WARNING: SESSION_SECRET_KEY not set. Using a random key "
        "(sessions will not persist across restarts).",
        file=_sys.stderr,
    )
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(acp_router)
app.include_router(data_gateway_router)
app.include_router(render_router)


# === API Endpoints ===

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "wicked-workbench"}


@app.get("/api/plugins")
async def discover_plugins():
    """Discover all installed wicked-garden plugins with their metadata.

    Scans ~/.claude/plugins/ for all plugin directories, loading plugin.json
    for metadata (name, version, description, commands, agents, skills).

    Returns a list of discovered plugins sorted by name.
    """
    plugins_base = Path.home() / ".claude" / "plugins"
    discovered = []

    if not plugins_base.exists():
        return []

    # Also check the cache directory structure
    cache_base = plugins_base / "cache"
    search_paths = []

    # Direct plugin installations
    for plugin_dir in sorted(plugins_base.iterdir()):
        if plugin_dir.is_dir() and plugin_dir.name.startswith("wicked-"):
            search_paths.append(plugin_dir)

    # Cached plugin installations (cache/wicked-garden/plugin-name/version/)
    wg_cache = cache_base / "wicked-garden" if cache_base.exists() else None
    if wg_cache and wg_cache.exists():
        for plugin_dir in sorted(wg_cache.iterdir()):
            if plugin_dir.is_dir() and plugin_dir.name.startswith("wicked-"):
                # Use latest version
                versions = sorted(plugin_dir.iterdir(), reverse=True)
                if versions:
                    search_paths.append(versions[0])

    for plugin_path in search_paths:
        plugin_json = plugin_path / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            continue

        try:
            with open(plugin_json) as f:
                info = json.load(f)

            plugin_name = info.get("name", plugin_path.name)

            # Extract command/agent/skill names from plugin.json
            commands = [c.get("name", "") for c in info.get("commands", []) if isinstance(c, dict)]
            agents = [a.get("name", "") for a in info.get("agents", []) if isinstance(a, dict)]
            skills = [s.get("name", "") for s in info.get("skills", []) if isinstance(s, dict)]

            discovered.append({
                "name": plugin_name,
                "info": {
                    "name": plugin_name,
                    "version": info.get("version", "0.0.0"),
                    "description": info.get("description", ""),
                    "commands": commands,
                    "agents": agents,
                    "skills": skills,
                },
            })

        except (json.JSONDecodeError, OSError) as e:
            print(f"[Workbench] Error loading plugin {plugin_path.name}: {e}")
            continue

    discovered.sort(key=lambda p: p["name"])

    return discovered


@app.get("/api/servers")
async def check_servers():
    """Check MCP server availability."""
    status = await mcp_bridge.check_servers()
    return {"servers": status}


# === Static Files & UI ===

# Serve static files if they exist
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the dashboard UI."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wicked Workbench</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        h1 { color: #7c3aed; margin-bottom: 8px; }
        .subtitle { color: #888; margin-bottom: 24px; }
        .info {
            background: #16213e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .info h3 { color: #7c3aed; margin-bottom: 8px; }
        .info code {
            background: #0f0f23;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .card {
            background: #16213e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 16px;
        }
        .card h4 { color: #7c3aed; margin-bottom: 8px; }
        .source {
            background: #0f0f23;
            border-radius: 4px;
            padding: 8px 12px;
            margin-top: 8px;
            font-size: 0.9rem;
        }
        .source .name { color: #a78bfa; font-weight: 600; }
        .source .caps { color: #888; font-size: 0.8rem; margin-top: 4px; }
        .cap {
            display: inline-block;
            background: #7c3aed22;
            color: #a78bfa;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75rem;
            margin-right: 4px;
        }
        .status { font-size: 0.875rem; color: #888; margin-top: 16px; }
        .healthy { color: #4ade80; }
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background: #7c3aed;
            color: white;
            cursor: pointer;
            margin-top: 12px;
        }
        button:hover { background: #6d28d9; }
        .empty { color: #666; font-style: italic; }
    </style>
</head>
<body>
    <h1>Wicked Workbench</h1>
    <p class="subtitle">Plugin Data Gateway &amp; Dashboard</p>

    <div class="info">
        <h3>Data API</h3>
        <p>Query any plugin's data via the gateway:</p>
        <p style="margin-top: 8px;">
            <code>GET /api/v1/data/plugins</code> &mdash; List all data sources<br>
            <code>GET /api/v1/data/{plugin}/{source}/{verb}</code> &mdash; Query data<br>
            <code>POST /api/v1/data/refresh</code> &mdash; Refresh discovery<br>
            <code>POST /api/render</code> &mdash; Submit A2UI document for rendering<br>
            <code>GET /api/render/surfaces</code> &mdash; List active surfaces
        </p>
    </div>

    <div id="health-status" class="status">Checking health...</div>

    <h3 style="margin-top: 24px; color: #7c3aed;">Data Sources</h3>
    <div id="plugins" class="grid">
        <p class="empty">Loading...</p>
    </div>

    <div class="status" id="status"></div>

    <script>
        async function loadHealth() {
            try {
                const r = await fetch('/health');
                const d = await r.json();
                document.getElementById('health-status').innerHTML =
                    '<span class="healthy">&#x2713;</span> ' + d.service + ' is ' + d.status;
            } catch (e) {
                document.getElementById('health-status').textContent = 'Health check failed';
            }
        }

        async function loadDataSources() {
            const container = document.getElementById('plugins');
            try {
                const r = await fetch('/api/v1/data/plugins');
                const d = await r.json();

                if (!d.plugins || d.plugins.length === 0) {
                    container.innerHTML = '<p class="empty">No data plugins discovered. Install plugins with wicked.json data declarations.</p>';
                    return;
                }

                container.innerHTML = d.plugins.map(p => `
                    <div class="card">
                        <h4>${p.name}</h4>
                        <div style="font-size:0.8rem;color:#888;">v${p.schema_version}</div>
                        ${p.sources.map(s => `
                            <div class="source">
                                <div class="name">${s.name}</div>
                                <div>${s.description || ''}</div>
                                <div class="caps">
                                    ${(s.capabilities || []).map(c => '<span class="cap">' + c + '</span>').join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `).join('');

                document.getElementById('status').textContent =
                    d.meta.total_plugins + ' plugins, ' + d.meta.total_sources + ' data sources';
            } catch (e) {
                container.innerHTML = '<p class="empty">Failed to load data sources: ' + e.message + '</p>';
            }
        }

        loadHealth();
        loadDataSources();
    </script>
</body>
</html>"""
