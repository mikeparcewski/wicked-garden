"""resolve.py — the runtime resolution ladder for a peer's runnable command.

Absorbed from wicked-loom (Phase B — ECOSYSTEM-RATIONALIZATION.md §5a).

Ladder (highest priority first):
  1. WICKED_<PEER>_BIN env var — explicit override. Empty string is a
     deliberate kill-switch (returns None, resolution short-circuits cleanly).
  2. PATH — shutil.which(<package>).
  3. npx fallback — ["npx", "<package>"].

``<package>`` is the peer's npm_package for the runnable command, but the
version-probe binary can differ (see manifest.Peer.version_package). The env
override / kill-switch is keyed on the peer regardless of which binary we are
resolving — an explicit override (or kill-switch) governs the whole peer.

Returns a command as a list[str] (argv-ready) or None when unresolvable /
killed / unknown peer. Pure + deterministic: no process is spawned here.
"""

from __future__ import annotations

import os
import shutil

from loom import manifest


def _resolve_package(peer, package: str) -> "list[str] | None":
    if peer.env_var in os.environ:
        override = os.environ[peer.env_var].strip()
        if override == "":
            return None  # kill-switch
        return [override]

    on_path = shutil.which(package)
    if on_path:
        return [on_path]

    return ["npx", package]


def resolve(peer_name: str) -> "list[str] | None":
    peer = manifest.get(peer_name)
    if peer is None:
        return None
    return _resolve_package(peer, peer.npm_package)


def resolve_version_bin(peer_name: str) -> "list[str] | None":
    """Resolve the binary that answers the version probe.

    Same ladder as ``resolve``, but PATH/npx-resolves ``version_package``
    (e.g. ``wicked-brain-server``). The env override / kill-switch still
    applies, so ``WICKED_<PEER>_BIN=""`` silences the probe too.
    """
    peer = manifest.get(peer_name)
    if peer is None:
        return None
    return _resolve_package(peer, peer.version_package)
