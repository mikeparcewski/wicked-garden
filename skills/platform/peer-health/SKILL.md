---
name: wicked-garden-platform-peer-health
description: |
  Run a health check on all wicked-* peer tools (wicked-vault, wicked-testing,
  wicked-brain, wicked-bus). Reports reachability, version vs. pin, and
  declared capability status for each peer. The replacement for
  `npx wicked-loom doctor` after Phase B absorption — peer-resolution now runs
  in-process via scripts/loom/, no external wicked-loom needed.

  Use when: "peer health", "check the wicked peers", "is wicked-vault
  reachable", "loom doctor", "peer version drift", "capability gap", or any
  former /wicked-garden:platform:peer-health invocation.
phase_relevance: ["build", "review", "operate", "bootstrap"]
archetype_relevance: ["*"]
---

# Peer Health

Check reachability and version health of wicked-* peer tools.

## Arguments

- `--peer <name>` — check a single peer (vault, testing, brain, bus)
- `--strict` — exit non-zero if any peer has capability-gap (status != wired)
- `--json` — emit raw JSON rows instead of the formatted table

## Instructions

Run the internal loom doctor via the absorbed scripts/loom/compose module.
No external wicked-loom process is needed — this runs in-process.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, os, json
sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'scripts'))
from loom import compose, manifest

peer_arg = None
import argparse
p = argparse.ArgumentParser()
p.add_argument('--peer', default=None)
p.add_argument('--strict', action='store_true')
p.add_argument('--json', dest='as_json', action='store_true')
try:
    args = p.parse_args()
except SystemExit:
    args = p.parse_args([])

if args.peer:
    rows = [compose.check_peer(args.peer)]
else:
    rows = compose.check_all()

if args.as_json:
    print(json.dumps(rows, indent=2))
else:
    # Human-readable table
    print()
    print(f'  {\"PEER\":<16} {\"STATUS\":<10} {\"VERSION\":<12} {\"CAPABILITY\":<14} PIN')
    print('  ' + '-'*62)
    for r in rows:
        peer_name = r.get('peer', '?')
        status = r.get('status', '?')
        version = r.get('installed', '-')
        cap = r.get('capability', '-') or '-'
        cap_ok = r.get('capability_ok', False)
        pin = r.get('pin', '-') or '-'
        icon = '  ' if r.get('ok') else '!'
        cap_icon = '' if cap_ok else ' (gap)'
        print(f'{icon} {peer_name:<16} {status:<10} {version:<12} {cap:<14}{cap_ok and \"\" or \" (!gap)\"}  ^{pin}')
    print()

if args.strict:
    gaps = [r['peer'] for r in rows if not r.get('capability_ok')]
    if gaps:
        print(f'STRICT: capability gaps on: {', '.join(gaps)}')
        sys.exit(1)
" $ARGUMENTS
```

## Status reference

| Status | Meaning | Action |
|---|---|---|
| `ok` | Resolved, version meets pin | None needed |
| `drift` | Resolved, version below pin | Update peer |
| `present` | Resolved + responds, version unreadable | WARN — update or check CLI |
| `missing` | Not found anywhere | Install the peer |
| `error` | Probe raised (binary vanished, OS error) | Reinstall |

## Capability status

`capability` is distinct from reachability. A peer can be `ok` (reachable)
but `experimental` or `planned` (not trusted for gating). The gate only
trusts `wired` peers — anything else yields a `capability-gap` verdict.

**wicked-brain** is currently `STATUS_EXPERIMENTAL` (bridge/deprecation period):
garden exposes equivalent surfaces via wicked-estate MCP. New work must not
declare brain as a required gate peer.

## Usage examples

```
peer-health                    # all peers, formatted table
peer-health --peer vault       # single peer
peer-health --strict           # non-zero exit on any capability gap
peer-health --json             # raw JSON rows
```
