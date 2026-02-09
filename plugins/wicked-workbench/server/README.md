# Wicked Workbench Server

A2UI-powered dashboard server that combines UI components from wicked-garden plugins into unified, AI-generated interfaces.

## Installation

```bash
pip install wicked-workbench-server
```

Or run directly with uvx:

```bash
uvx wicked-workbench-server
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
| `WICKED_PLUGINS_DIR` | `~/.claude/plugins` | Plugins directory |
| `ANTHROPIC_API_KEY` | (optional) | Claude API key for `/api/generate` endpoint only |

> **Note**: The main workflow (Claude Code generates A2UI → workbench renders) does NOT require an API key. The key is only needed if using the `/api/generate` endpoint for server-side generation.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/catalogs` | GET | List available catalogs |
| `/api/catalogs/{id}` | GET | Get catalog details |
| `/api/prompt` | GET | Get current system prompt |
| `/api/generate` | POST | Generate A2UI from intent |
| `/api/data` | POST | Fetch data from MCP servers |
| `/api/servers` | GET | Check MCP server status |

## How It Works

1. **Plugin Discovery**: Scans installed wicked-garden plugins for `catalog.json` files
2. **Prompt Generation**: Converts catalogs into an AI system prompt (~1000 tokens)
3. **AI Generation**: Claude generates A2UI documents from user intent
4. **MCP Data Fetch**: Connects to plugin MCP servers for live data
5. **Rendering**: Displays components using registered implementations

## License

MIT
