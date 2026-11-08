# __PLUGIN_TITLE__

A run plugin ("phase plugin") for wicked-studio (`__PLUGIN_ID__` __PLUGIN_VERSION__), packaged as a
`wicked-pack.json` spec-2 pack. It renders a section in a job's Details panel from the run topics
the operator's install consent grants: `__PLUGIN_TOPICS__`.

- `wicked-pack.json` declares the plugin under `plugins[]`: its id, version, protocol `[3]`,
  `inline: "run-thread"`, `observe[]` (each topic pattern with its `why`), `panels[]`, `samples`,
  and the sha256 of its entry file.
- `plugins/__PLUGIN_ID__/index.html` is the whole plugin: one self-contained HTML file speaking
  `wicked.editor/3` over the `MessagePort` transferred with `host.hello`.
- `samples/events.ndjson` holds sample `CoreEvent` rows the conformance feed carries alongside the
  standard `RUN_TOPICS` events.

## Check it

```
wicked-garden run scripts/editor/pin.py .            # re-pin the entry's sha256 after an edit
npx wicked-garden pack check .                       # the manifest, entry, topics, panels, samples
wicked-garden run scripts/editor/conformance.py --pack . --host-url <a wicked-crew daemon URL> --json
```

## Install it

```
wicked-garden run scripts/editor/install.py --dir . --plan --json
wicked-garden run scripts/editor/install.py --dir . --crew-url <the daemon URL>
```
