# Editor plugin packs that ship with wicked-garden

Each directory is a `wicked-pack.json` spec-2 pack built with the editor-plugin builder
(the `wicked-garden-editor-scaffold` skill), the same way the `editor-plugin` workflow builds any plugin.
None of them uses the reserved `wicked` vendor: that prefix belongs to the editors bundled inside studio.

| Pack | Opens | What it is |
|---|---|---|
| `garden-mcp-inspector` | `mcp-server` | The MCP inspector: list a server's tools, resources and prompts, call them, and read the JSON-RPC log. The host connects the server and draws Connect, Restart and the call line. |

## How it was made

```
wicked-garden run scripts/editor/scaffold.py --vendor garden --id garden-mcp-inspector --title "MCP inspector" \
  --kinds mcp-server --permissions artifact.read,mcp.session,ui.fullscreen --surfaces <its surfaces JSON> \
  --out packs/garden-mcp-inspector
```

Then the inspector went into the entry's YOUR EDITOR part, and `pin.py` re-pinned the hash. `tests/editor/test_garden_packs.py`
re-runs that scaffold with the pack's own declaration and requires everything but the entry's hash to match.

## Install one

```
wicked-garden run scripts/editor/install.py --dir "$(wicked-garden path packs/garden-mcp-inspector)" --crew-url <the daemon URL>
```

The daemon re-runs `pack check` and the conformance cases before it lists the editor. Installing grants
`mcp.session` for this build only, and studio's MCP inspector page then opens it.
