---
description: View or set the operational log verbosity level for this session
---

# /wicked-garden:platform:debug

View or set the operational log verbosity level (`normal`, `verbose`, or `debug`).

Instructions:
- Extract the argument from `$ARGUMENTS` (optional: one of `normal`, `verbose`, `debug`)
- Let `LEVEL_ARG` be the trimmed argument (empty string if none provided)
- Run the following inline Python, substituting `${CLAUDE_PLUGIN_ROOT}` and the extracted level:

```bash
python3 -c "
import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve() / 'scripts'))
from _session import SessionState

level = '${LEVEL_ARG}'

state = SessionState.load()
env_level = os.environ.get('WICKED_LOG_LEVEL', '')

if not level:
    effective = env_level or state.log_level or 'normal'
    source = 'env var' if env_level else ('session state' if state.log_level else 'default')
    print(f'Log level: {effective} (source: {source})')
    if env_level:
        print(f'Note: WICKED_LOG_LEVEL={env_level} overrides session state.')
else:
    valid = {'normal', 'verbose', 'debug'}
    if level not in valid:
        print(f'Error: invalid level {level!r}. Must be one of: normal, verbose, debug')
        sys.exit(1)
    state.update(log_level=level)
    print(f'Log level set to: {level}')
    print(f'This takes effect immediately for the current session.')
    if env_level and env_level != level:
        print(f'Warning: WICKED_LOG_LEVEL={env_level} will override this setting.')

import re
raw_id = os.environ.get('CLAUDE_SESSION_ID', '')
if raw_id:
    safe_id = re.sub(r'[^a-zA-Z0-9\-_]', '_', raw_id) or 'unknown'
    tmpdir = os.environ.get('TMPDIR', '/tmp')
    log_path = Path(tmpdir) / f'wicked-ops-{safe_id}.jsonl'
    print(f'Ops log file: {log_path}')

# PostToolUse latency profiling (Issue #312)
print()
print('--- PostToolUse Hook Latency ---')
total_ms = state.post_tool_total_ms or 0
call_count = state.post_tool_call_count or 0
handler_ms = state.post_tool_handler_ms or {}

if call_count == 0:
    print('No PostToolUse invocations recorded yet.')
else:
    avg_ms = total_ms / call_count if call_count else 0
    print(f'Total invocations: {call_count}')
    print(f'Cumulative time:   {total_ms} ms')
    print(f'Average per call:  {avg_ms:.1f} ms')
    if handler_ms:
        print()
        print('Per-handler breakdown (cumulative ms):')
        for h in sorted(handler_ms.keys(), key=lambda k: handler_ms[k], reverse=True):
            print(f'  {h:30s} {handler_ms[h]:>6d} ms')
"
```

- Display the output to the user
- If the level argument is invalid, the script prints an error and exits with code 1 — surface that error to the user
