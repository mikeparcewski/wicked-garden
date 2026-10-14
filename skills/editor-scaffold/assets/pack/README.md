# __EDITOR_TITLE__

An artifact editor plugin for wicked-studio (`__EDITOR_ID__` __EDITOR_VERSION__), packaged as a
`wicked-pack.json` spec-2 pack. It opens: __EDITOR_KINDS__.

- `wicked-pack.json` declares the editor: its id, the artifact kinds it opens, its sizes, every
  permission it asks for and why, and the sha256 of its one entry file.
- `editors/__EDITOR_ID__/index.html` is the whole editor: one self-contained HTML file speaking the
  `wicked.editor/2` protocol (and /1 to an older host) to studio's plugin host over a MessagePort. It
  runs in sandboxed frames with no network: the card in the run's thread, the options tabs in the host
  panel and full screen, all drawn from the `surfaces` its manifest declares.

## Check it

```
wicked-garden run scripts/editor/pin.py .            # re-pin the entry's sha256 after an edit
npx wicked-garden pack check .                       # the manifest and the entry
wicked-garden run scripts/editor/conformance.py --pack . --host-url <a wicked-crew daemon URL> --json
```

The conformance run drives studio's conformance host page in headless Chromium against this
editor: handshake, sizes, no network, permissions, typing never acts, key forwarding, strict
input, liveness, keyboard reach, theme, the pinned hash, and the three surfaces (the card, each
options tab, full screen and its modes). On a slow host, give it longer to load the page with
`--timeout <seconds>` (default 120).

## Install it

Through the `editor-plugin` workflow's install step, or by hand:

```
wicked-garden run scripts/editor/install.py --dir . --crew-url <the daemon URL>
```

It then shows in studio under Settings → Developer → Editor plugins, and opens in the editor dev host.
