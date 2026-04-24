# Cold-Start Behavior — Docstring Addition Rationale

**File:** `scripts/crew/_task_reader.py` — module docstring, Performance section

**Council condition:** #611 — document cold-start behavior so operators understand
the ~63ms spike observed in the original `latency-smoke.txt`.

## Why this note exists

The original `latency-smoke.txt` recorded a first-call cold spike of ~63ms, which
exceeded the 50ms p99 SLO.  The council flagged this as unexplained.

The spike is real and intentional: the first HTTP request after daemon startup (or
restart) must open the SQLite connection, execute `PRAGMA journal_mode=WAL` and
`PRAGMA foreign_keys=ON`, prime the page cache, and establish the TCP connection via
`urllib.request`.  All of this happens inside the 45ms timeout window for the first
call, which means `WG_DAEMON_ENABLED=true` (default) will time out and fall back to
the direct file read on that first call.  Subsequent warm-path calls are ~1–3ms
median, well under the 50ms SLO.

## Operator impact by mode

| Mode | Cold-start behavior | Subsequent calls |
|------|--------------------|-|
| `false` (default) | No daemon involved — file read always | ~file read latency |
| `true` | First call times out → silent file-read fallback | ~1–3ms daemon path |
| `always` | First call times out → None returned (surfaces to caller) | ~1–3ms daemon path |

Operators enabling `always` mode should expect a single-request latency blip on
daemon restart before the warm path is re-established.  This is preferable to
reducing the 45ms timeout, which would increase false-timeout frequency on loaded
systems.

## Decision: do not reduce the 45ms timeout

The 45ms ceiling was chosen as 5× the observed p99 warm-path latency (~9ms from the
original smoke run).  Reducing it to, say, 20ms would cut the cold-start blip but
also increase the false-timeout rate on temporarily loaded loopback paths.  The
current value is the right trade-off for `WG_DAEMON_ENABLED=true` (fail-open) mode.
