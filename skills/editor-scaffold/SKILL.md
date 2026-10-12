---
name: wicked-garden-editor-scaffold
description: |
  Build an artifact editor plugin for wicked-studio: scaffold a
  wicked-pack.json spec-2 pack with one self-contained HTML editor speaking
  wicked.editor/1, ask only for the permissions it needs, re-pin its hash,
  run the conformance cases in headless Chromium against studio's own
  plugin host, then install it into a wicked-crew daemon's editors.

  Use when: "build an editor plugin", "make a custom editor", "an editor for
  this artifact kind", "scaffold an editor", "check my editor plugin",
  "run the editor conformance", "install this editor plugin", studio
  Settings → Developer → "Create an editor plugin", or a phase of the
  `editor-plugin` workflow. NOT for granting an editor's permissions
  (studio Settings does that) or for editing a document (studio's built-in
  editors do that).
metadata:
  role: router
  phases: "*"
  archetypes: "build"
---

# Editor scaffold

Scaffold → write the editor → pin → conformance → install. The editor you build runs in
studio's **plugin host** (DES-EDITOR-PLUGINS-001): one sandboxed frame with no network and no
same-origin access, one MessagePort, and every request checked against the grants the operator
allowed. The editor never learns a URL, an id or a path, and it can never send, approve, launch,
deliver or remember anything; those stay host actions behind a human click.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## 1. Scaffold

```
wicked-garden run scripts/editor/scaffold.py --vendor <vendor> --id <vendor>-<name> --title "<plain words>" --kinds <kind[,kind]> [--permissions <id[,id]>] --out <dir>
```

- **The pack** is `wicked-pack.json` spec 2 with one `editors[]` entry, plus
  `editors/<id>/index.html` (the whole editor: ONE file, every script and style inline) and a
  README. `--out` may be a repo root or a subdirectory; every file it would write must be absent
  (it refuses naming the first collision and writes nothing).
- **Names**: the vendor and the id are kebab-case; the id starts with `<vendor>-`. `wicked` and
  `wicked-*` are reserved for the editors that ship inside studio and are refused in every pack.
- **Kinds** are the artifact kinds it opens (`^[a-z][a-z0-9-]{1,40}$`): `page`, `document`,
  `deck`, `demo-video`, `walkthrough`, `rfp-response`, `mcp-server` (an MCP inspector: see
  *Kind mcp-server*), or a kind of your own.
- **Permissions** default to `artifact.read,selection.chip,ui.fullscreen`. Ask for no more than the
  editor uses (see *Permissions*). `network.media` is refused: a pack editor has no network.
- It prints JSON with the pack path, the editor's sha256 and the next commands.
- **Manual alternative:** copy `assets/pack/` into `<dir>`, rename `editors/__EDITOR_ID__` to
  your id, replace `__EDITOR_ID__`, `__EDITOR_VERSION__`, `__EDITOR_TITLE__` and
  `__EDITOR_KINDS__`, and write `wicked-pack.json` by hand in the shape above.

## 2. Write the editor: the contract

The template's plumbing is what the conformance run checks; keep it and put your editor in
`render()` and the handlers marked YOUR EDITOR.

- **Handshake**: post ONE `plugin.ready {editor, version, protocol:[1]}` to `parent`; take the
  first `host.hello` that carries a port; from then on every message rides that port.
- **Requests** (`{p:'wicked.editor', v:1, type, id, payload}`) get one reply `{re, ok, payload |
  error}`. `artifact.read` → `{version, content}` where `content` is `{type:'html', html}`,
  `{type:'demo', …}`, `{type:'walkthrough', view}` or `{type:'rfp', requirements, answers}`.
  Render content with `textContent` or `DOMParser` — never as live markup.
- **Writes** (`version.write {base, ops, summary}`) carry text and colours only: `{op:'text',
  anchor, value, before}`, `{op:'style', anchor, style:{background?, color?}}`, `{op:'remove',
  anchor}`. A `stale` or `head_moved` reply is shown to the user, never retried silently.
- **Events you answer**: `host.ping` within 2 s; `host.size` (inline / pane / full — the same
  frame, never a reload or a re-read); `host.theme`; `artifact.changed` (re-read unless `by` is
  `this-editor`). Ignore any unknown `type`; a malformed message is dropped, never a crash.
- **Keys**: forward only `Escape`, `Mod+K`, the navigation chords `Alt+J/K/P/G/B/T/U` and `Alt+/`,
  and Tab at the edges, as `ui.key` (never `Alt+A`, `Alt+R`, `Alt+X` or `Alt+N`: the host drops a
  decision chord, and three drops tear the editor down);
  the FIRST printable key goes to the composer as ONE `ui.typed {grapheme}`; Backspace and
  Delete never remove anything. A key never approves, deletes or sends.
- **No network, no animation by default**, every control reachable by keyboard with a visible
  focus ring, `prefers-reduced-motion` honoured.
- After every edit of the entry, **re-pin** its hash (the host refuses a changed bundle, and a
  grant is keyed by that hash): `wicked-garden run scripts/editor/pin.py <dir>`. Then
  `npx wicked-garden pack check <dir>`.

## 3. Conformance

```
wicked-garden run scripts/editor/conformance.py --pack <dir> [--host-url <crew URL> | --studio-dist <dir>] --json
```

Runs each editor in headless Chromium inside studio's own conformance host page, proxied from
the daemon (`--host-url`, else `$WICKED_CREW_URL` — never a typed port) or served from a studio
`dist`. It serves the candidate's entry on the bundle route itself (hash-checked, no network) and
runs: 0 manifest (`pack check`), 1 handshake, 2 sizes, 3 no network, 4 permissions withdrawn,
5 typing never acts, 6 key forwarding, 8 strict input, 9 liveness, 10 keyboard reach, 11 theme,
12 the pinned hash. Its report lists the gaps it cannot see (case 7, a scripted edit, is your
editor's own UI; axe is not run; WebRTC is invisible to request interception). Exit 0 all
passed, 1 a case failed (named in the report), 3 no headless browser — **fail closed**: never
call an editor conformant without the run. **Manual alternative:** none; report the editor as
not verified.

## 4. Install (`install`)

```
wicked-garden run scripts/editor/install.py (--from-run | --dir <dir>) [--target daemon|daemon-off] [--dry-run] [--crew-url <origin>] [--json]
wicked-garden run scripts/editor/install.py --uninstall <pack name> [--crew-url <origin>]
```

Idempotent by the pack's `name`: stage into `~/.wicked/editors/<name>/current/` (a program-owned
place; the copy it replaces is kept in `previous/`), then `POST /api/v1/editors` on the daemon,
which re-runs `pack check` **and the conformance run itself** before it records the editor in its
registry. A refusal rolls the staged copy back and exits 1. `--target daemon` (the default)
installs it on; `daemon-off` installs it turned off. `--dry-run` writes nothing and prints the
one JSON plan line the install's consent gate shows. Each choice id carries a digest of the planned
manifest: approving it installs that pack only, and a pack changed since (another permission, version
or hash) is refused, so the operator is asked again. After install the editor is listed in studio
**Settings → Developer → Editor plugins** and opens in the editor dev host.

## Permissions

| Permission | Lets the editor | Third-party default |
|---|---|---|
| `artifact.read` | read the artifact it opens | allowed |
| `selection.chip` | point at parts in the message box | allowed |
| `checks.contribute` | add its own notes (never a verdict) | allowed |
| `ui.fullscreen` | go full screen (the host's container) | allowed |
| `artifact.write` | change it, as versions you can undo | asks |
| `composer.draft` | suggest a message (the operator sends it) | asks |
| `checks.read`, `sources.read`, `media.read`, `artifact.export` | see checks, sources, media; download | asks |
| `mcp.session` | start and talk to the MCP servers you connect it to | granted only by its install consent |

The operator's grants are decided by steering (deny dominates) and keyed by
`editor:<id>@<version>#<sha256>/<permission>`: a new version or a changed entry asks again.
No rule allows `mcp.session`. The install plan says "This plugin can start and talk to MCP servers"
with the build's token, and approving the install writes that one token. It is never a write grant.

## Kind `mcp-server`

An MCP inspector: the host connects to the server and the editor sends `mcp.request {method, params?}`
(`tools/call` only from a click; 60 s) and renders the `mcp.state` and `mcp.log` events. A write
tool on a registered server answers `write_not_granted` (403) until a human enables it on the MCP
tools page. A server re-saved since the connect answers `server_changed` (409): reconnect. The full
contract (methods, errors, events, conformance) is in `refs/mcp-server.md`; read it before you build one.

## In a governed run

You are in one when a wicked-crew phase directive or the `wicked-garden-governed-worker`
skill was handed to you (`WICKED_RUN_ID` is set). Follow `wicked-garden-governed-worker`, and:

- **scope**: settle the editor's id and title, the kinds it opens, what it shows and lets the
  user do, the permissions that needs (each with its plain-words why), and the target directory
  (the root of a near-empty repo, or a subdirectory such as `editors-pack/` of an existing one).
  Read `GET $WICKED_CREW_URL/api/v1/editors` and pick an id no installed editor holds.
- **design**: the contract table — each host → plugin message it handles, each plugin → host
  request it makes with the permission it needs, its sizes, keys, theme and focus behaviour —
  checked against section 2 (and `refs/mcp-server.md` for kind `mcp-server`). Name every deviation.
- **build**: scaffold (section 1), write the editor, re-pin, `pack check`, and run the
  conformance (section 3); put its JSON in your output. A failed case is a finding to fix.
- **test**: run the conformance against the delivered tree yourself; a failed case, or no
  browser, is a FAIL with the case named.
- **security-review**: grants requested vs used (every permission the manifest asks for has a
  request in the code that needs it; nothing unused), no network or outside reference, content
  rendered as text, no message beyond the protocol, keys and typing per section 2.
- **install-plan / install**: Tool phases run `install.py --from-run --dry-run --json`, the
  operator's consent gate offers its choices with their files, then `install.py --from-run
  --target <the approved choice>`. Do not install, register or serve the editor yourself.
