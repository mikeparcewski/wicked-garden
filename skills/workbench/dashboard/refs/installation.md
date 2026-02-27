# Workbench Server Installation

## Where the Code Lives

The workbench server is a standalone FastAPI application inside the plugin:

```
plugins/wicked-workbench/
└── server/                          # The server package
    ├── pyproject.toml               # Package: wicked-workbench-server
    ├── src/
    │   └── wicked_workbench_server/
    │       ├── __init__.py          # Entry point (main function)
    │       ├── __main__.py          # python -m support
    │       ├── app.py               # FastAPI app, routes, lifespan
    │       ├── auth/                # OAuth + local auth
    │       ├── acp/                 # ACP bridge (optional)
    │       ├── bridges/             # MCP bridge, Claude client
    │       └── data_gateway/        # Plugin data discovery + proxy router
    │           ├── discovery.py     # Scans plugins for wicked.json
    │           └── router.py        # /api/v1/data/* REST routes
    └── frontend/                    # React dashboard UI (optional)
```

**Important**: The package name (`wicked-workbench-server`) differs from the executable name (`wicked-workbench`). This matters for uvx invocations.

## Install Methods

### 1. uvx (recommended, no permanent install)

Run directly without installing — uvx creates a temporary environment:

```bash
uvx --from wicked-workbench-server wicked-workbench
```

The `--from` flag is required because the package name (`wicked-workbench-server`) differs from the executable (`wicked-workbench`).

### 2. pip install (permanent)

Install the package, then run:

```bash
pip install wicked-workbench-server
wicked-workbench
```

### 3. From local source (development)

From the plugin's server directory:

```bash
cd plugins/wicked-workbench/server
uv run wicked-workbench
```

Or install in editable mode:

```bash
cd plugins/wicked-workbench/server
pip install -e .
wicked-workbench
```

### 4. Via the Claude Code command

The `/wicked-garden:workbench:workbench start` command handles startup automatically:

```
/wicked-garden:workbench:workbench start
```

This checks if the server is already running, and starts it via uvx if not.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WICKED_WORKBENCH_PORT` | `18889` | Server port |
| `WICKED_WORKBENCH_HOST` | `127.0.0.1` | Bind address |
| `WICKED_PLUGINS_DIR` | (auto-detected) | Override plugin discovery directory |
| `DATABASE_URL` | SQLite (auto-created) | Database URL for auth |
| `SESSION_SECRET_KEY` | (default) | Session middleware secret |

### Plugin Discovery

The data gateway discovers plugins in two locations:

1. **Cache**: `~/.claude/plugins/cache/wicked-garden/{plugin}/{version}/`
2. **Local repo**: `{WICKED_PLUGINS_DIR}/../` (if set)

Plugins need a `wicked.json` with data sources AND a matching `api.py` script to appear in the gateway.

### Optional OAuth

For multi-user setups, configure OAuth providers:

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret |

## Verifying the Install

After starting, verify:

```bash
# Health check
curl http://localhost:18889/health
# Expected: {"status":"healthy","service":"wicked-workbench"}

# Data sources
curl http://localhost:18889/api/v1/data/plugins
# Expected: list of plugins with data sources

# Dashboard UI
open http://localhost:18889
```

## Troubleshooting

**"executable wicked-workbench-server was not found"**
You used `uvx wicked-workbench-server` — the executable name is `wicked-workbench`, not `wicked-workbench-server`. Use: `uvx --from wicked-workbench-server wicked-workbench`

**"Data Gateway ready with 0 data plugins"**
No plugins with `wicked.json` data sources were found. Set `WICKED_PLUGINS_DIR` to point to your plugins directory, or ensure plugins are in the cache at `~/.claude/plugins/cache/wicked-garden/`.

**Port already in use**
Another instance is running. Check with `curl http://localhost:18889/health` or stop with `pkill -f wicked-workbench`.

**Server starts but no data sources in UI**
Plugins must declare sources in `wicked.json` AND have a `scripts/api.py`. Empty `wicked.json` (like workbench itself) means no data exposed.
