#!/usr/bin/env python3
"""
crew/steering_tail.py — Reference debug subscriber for the wicked.steer.* family.

Streams steering events from wicked-bus and prints each as one-line JSON to
stdout. Intended for live debugging during the steering detector epic build-out.

This is a *reference* subscriber. It does not act on events — it just shows
that the wiring works end-to-end. The actual behavior subscribers
(``crew:rigor-escalator``, ``wicked-testing:qe-engager``, audit log) ship in
later PRs.

Usage::

    python3 scripts/crew/steering_tail.py
    python3 scripts/crew/steering_tail.py --severity=escalated
    python3 scripts/crew/steering_tail.py --severity=advised
    python3 scripts/crew/steering_tail.py --detector=sensitive-path
    python3 scripts/crew/steering_tail.py --from-cursor=<cursor_id>

Exit codes:
    0  — clean exit (SIGINT or stream end)
    1  — wicked-bus not installed / unreachable
    2  — invalid CLI arguments

The tail invokes the ``wicked-bus subscribe`` CLI as a subprocess (matching how
``scripts/_bus.py`` integrates) and parses NDJSON. Each event is filtered
locally so the script can apply detector-name filters that the bus filter
syntax doesn't natively express.
"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
from typing import Optional

_FILTER = "wicked.steer.*@wicked-garden"
_VALID_SEVERITY = ("all", "escalated", "advised")
_DETECTOR_SUBDOMAIN_PREFIX = "crew.detector."
# Subscriber identity — `wicked-bus subscribe` requires a non-null plugin name
# to register a cursor. Each `--from-cursor` invocation reuses the existing
# cursor; without `--from-cursor` we register a fresh one under this plugin.
_SUBSCRIBER_PLUGIN = "wicked-garden:steering-tail"


#: Probe timeout for the wicked-bus reachability check (seconds). Mirrors the
#: 5s budget used by ``scripts/_bus.py:_EMIT_TIMEOUT_SECONDS`` so the probe
#: matches what the rest of the plugin considers "fast" for the bus.
_BUS_PROBE_TIMEOUT_SECONDS = 5.0


def _resolve_bus_command() -> Optional[list]:
    """Find the wicked-bus binary or fall back to npx. Returns argv prefix.

    Mirrors the resolution in ``scripts/_bus.py:_resolve_binary`` — including
    the actual reachability probe (``wicked-bus status --json``) for the npx
    path so we don't treat "npx exists" as "wicked-bus reachable" (npx will
    download the package on first use, which can hang for tens of seconds).
    """
    direct = shutil.which("wicked-bus")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx is None:
        return None
    # npx is on PATH — confirm wicked-bus is actually installed/reachable by
    # running a fast status probe. If this hangs/fails, treat the bus as
    # unreachable rather than letting `subscribe` block on a package install.
    try:
        result = subprocess.run(
            [npx, "wicked-bus", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=_BUS_PROBE_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return [npx, "wicked-bus"]


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="steering_tail",
        description=(
            "Tail wicked.steer.* events from wicked-bus. Prints one JSON "
            "object per line. SIGINT (Ctrl-C) for clean exit."
        ),
    )
    parser.add_argument(
        "--severity",
        choices=_VALID_SEVERITY,
        default="all",
        help=(
            "Filter by severity. 'escalated' = wicked.steer.escalated only, "
            "'advised' = wicked.steer.advised only, 'all' (default) = both."
        ),
    )
    parser.add_argument(
        "--detector",
        default=None,
        help=(
            "Filter by detector name. Matches subdomain "
            f"'{_DETECTOR_SUBDOMAIN_PREFIX}<name>'. "
            "Example: --detector=sensitive-path"
        ),
    )
    parser.add_argument(
        "--from-cursor",
        default=None,
        help=(
            "Resume from a known cursor id. Optional — without this the bus "
            "registers a fresh subscription and tails from latest."
        ),
    )
    return parser.parse_args(argv)


def _matches(event: dict, severity: str, detector: Optional[str]) -> bool:
    """Return True if event passes the local filter set."""
    event_type = event.get("event_type", "")

    if severity == "escalated" and event_type != "wicked.steer.escalated":
        return False
    if severity == "advised" and event_type != "wicked.steer.advised":
        return False

    if detector is not None:
        expected = f"{_DETECTOR_SUBDOMAIN_PREFIX}{detector}"
        if event.get("subdomain") != expected:
            return False

    return True


def _print_event(event: dict) -> None:
    """Emit one event as a single-line JSON record."""
    sys.stdout.write(json.dumps(event, default=str, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _build_subscribe_cmd(bus_cmd: list, cursor: Optional[str]) -> list:
    """Build the wicked-bus subscribe argv.

    `wicked-bus subscribe` requires a `--plugin` value to register a new
    cursor. When `--from-cursor` is supplied we still pass `--plugin` so the
    bus can resolve the subscription consistently.
    """
    cmd = list(bus_cmd) + [
        "subscribe",
        "--plugin", _SUBSCRIBER_PLUGIN,
        "--filter", _FILTER,
    ]
    if cursor:
        cmd += ["--cursor-id", cursor]
    return cmd


def _stream(args: argparse.Namespace) -> int:
    bus_cmd = _resolve_bus_command()
    if not bus_cmd:
        sys.stderr.write(
            "error: wicked-bus is not installed. "
            "Install via 'npm install -g wicked-bus' or ensure 'npx' is on PATH.\n"
        )
        return 1

    cmd = _build_subscribe_cmd(bus_cmd, args.from_cursor)

    # Clean SIGINT — let the child terminate, then exit 0.
    def _on_sigint(signum, frame):  # noqa: ARG001 — signal API
        # Subprocess is in the same process group; default behavior will
        # propagate SIGINT. We just exit cleanly when the loop unwinds.
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _on_sigint)

    try:
        # IMPORTANT: stream stderr directly to our stderr instead of buffering
        # to a PIPE. The subscribe child can write enough to stderr to fill the
        # OS pipe buffer; if we only drain stderr at exit, the child blocks
        # mid-stream and the tail appears to hang. Routing it straight through
        # also gives the user live error visibility.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write(
            f"error: failed to launch wicked-bus subscribe: {' '.join(cmd)!r}\n"
        )
        return 1

    try:
        assert proc.stdout is not None  # for type checkers
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Forward malformed lines to stderr so the user can see them
                # without contaminating the JSON-line stdout stream.
                sys.stderr.write(f"warn: skipping non-JSON line: {line!r}\n")
                continue

            if not isinstance(event, dict):
                continue

            if _matches(event, args.severity, args.detector):
                _print_event(event)
    except KeyboardInterrupt:
        # Clean exit path — terminate child if still running.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 0
    finally:
        # Ensure the child is fully reaped before we read returncode. proc.poll()
        # alone can return None for a process that has just exited but hasn't
        # been waited on yet, masking a non-zero exit. wait(timeout=2) blocks
        # briefly for the reap; if the child somehow refuses to exit we kill
        # it so we don't leave an orphan around.
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass  # last-resort: caller will see returncode=None below

    return proc.returncode if proc.returncode is not None else 0


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    return _stream(args)


if __name__ == "__main__":
    sys.exit(main())
