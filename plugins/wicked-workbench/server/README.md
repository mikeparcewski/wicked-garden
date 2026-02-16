# Wicked Workbench Server

Plugin data gateway and dashboard server for wicked-garden. Discovers installed plugins, proxies data API requests, and serves the dashboard UI.

## Installation

```bash
pip install wicked-workbench-server
```

Or run directly with uvx:

```bash
uvx --from wicked-workbench-server wicked-workbench
```

## Usage

Start the server:

```bash
wicked-workbench
```

Then open http://localhost:18889 in your browser.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WICKED_WORKBENCH_PORT` | `18889` | Server port |
| `WICKED_WORKBENCH_HOST` | `127.0.0.1` | Server host |
| `WICKED_PLUGINS_DIR` | (auto-detected) | Plugins directory for data gateway discovery |
| `DATABASE_URL` | SQLite (auto-created) | Database for auth and persistence |

## API Endpoints

### Data Gateway

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/data/plugins` | GET | List all plugins with data sources |
| `/api/v1/data/plugins/{plugin}` | GET | Get a plugin's data source info |
| `/api/v1/data/{plugin}/{source}/{verb}` | GET | Proxy read request to plugin api.py |
| `/api/v1/data/{plugin}/{source}/{verb}/{id}` | GET | Proxy read with item ID |
| `/api/v1/data/{plugin}/{source}/create` | POST | Create a resource |
| `/api/v1/data/{plugin}/{source}/update/{id}` | PUT | Update a resource |
| `/api/v1/data/{plugin}/{source}/delete/{id}` | DELETE | Delete a resource |
| `/api/v1/data/refresh` | POST | Refresh plugin discovery |

### Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/plugins` | GET | List installed plugins with metadata |
| `/api/servers` | GET | Check MCP server status |

### ACP Bridge (optional)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/acp/status` | GET | ACP Bridge status |
| `/acp/commands` | GET | Available slash commands |
| `/acp/ws` | WebSocket | Browser connection for ACP sessions |

## How It Works

1. **Plugin Discovery**: Scans installed plugins for `wicked.json` data source declarations
2. **Data Gateway**: Proxies verb-based requests (list, get, search, stats, create, update, delete) to plugin `api.py` scripts
3. **Dashboard UI**: Serves a web interface showing discovered data sources
4. **ACP Bridge**: Optionally connects to Claude Code for interactive sessions (requires `claude-code-acp`)

## License

MIT
