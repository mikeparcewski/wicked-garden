"""manifest.py — the wicked-* peer set: what each peer is and how to reach it.

Absorbed from wicked-loom (Phase B — ECOSYSTEM-RATIONALIZATION.md §5a).
Source of truth for peer names, version pins, install commands, and probe
commands.  Version pins are the MAJOR.MINOR floor (the ``^x.y`` in
plugin.json), compared by compose.py.  Install commands are headless
(npm/npx) — the ``/plugin install`` path is CC-UX sugar, not the only route.

Capability honesty (the never-fake contract)
---------------------------------------------
Each peer carries a declared capability ``status`` — ``wired`` | ``planned`` |
``experimental`` — distinct from runtime *reachability* (resolve + version-pin,
which compose.py reports as ok/drift/present/missing/error).  ``status`` answers
a different question: "is this peer's capability declared ready for the runtime
to depend on?"  The contract is absolute: **the runtime NEVER pretends a
non-``wired`` peer satisfies a gate.**  When a flow requires a peer that is
``planned``/``experimental`` (or unresolvable), the runner emits a precise
``capability-gap`` naming exactly which peer must be installed/wired — it never
silently proceeds and never fakes a pass.  Capability is *data*, never invented.

Peer status notes (post-rationalization):
  vault    — wired; binary ``wicked-vault`` (will be re-homed into wicked-qe;
             coordinate bin name update with the vault-absorption agent)
  testing  — wired; ``wicked-testing`` (wicked-qe rename pending; bin stays)
  brain    — DEPRECATED (bridge period: garden now exposes equivalent surfaces
             via wicked-memory + wicked-knowledge; use_loom check still passes)
  bus      — wired; ``wicked-bus`` (Rust rewrite in progress; CLI interface
             stays identical so no manifest change needed on Rust cutover)
"""

from __future__ import annotations

from dataclasses import dataclass

# The honest capability vocabulary (factory stack-registry parity).
#   wired        — capability declared ready; the runtime may depend on it.
#   planned      — known peer, capability not yet wired; never satisfies a gate.
#   experimental — present but not trusted for gating; treated like planned for
#                  the never-fake contract (a flow that requires it gets a gap).
STATUS_WIRED = "wired"
STATUS_PLANNED = "planned"
STATUS_EXPERIMENTAL = "experimental"
# The set of statuses the runtime trusts to satisfy a required-peer dependency.
# ONLY ``wired`` is trusted — this is the fail-closed half of the never-fake
# contract: anything else yields a capability-gap rather than a silent proceed.
WIRED_STATUSES = frozenset({STATUS_WIRED})


@dataclass(frozen=True)
class Peer:
    name: str
    npm_package: str
    env_var: str           # runtime override env var, e.g. WICKED_VAULT_BIN
    version_pin: str        # MAJOR.MINOR floor, e.g. "0.3"
    install_cmd: list       # headless install command
    probe_cmd: list         # command to print the installed version
    # The probe binary can legitimately differ from the install/run package:
    # e.g. brain installs/runs as `wicked-brain` but reports its version via
    # `wicked-brain-server`. Empty string means "same as npm_package".
    version_bin: str = ""
    # Declared capability readiness (the never-fake contract — see module
    # docstring). Distinct from runtime reachability. Defaults to "wired": every
    # peer shipped today is a wired capability. A non-"wired" peer NEVER
    # satisfies a required-peer dependency — the runner emits a capability-gap.
    status: str = STATUS_WIRED

    @property
    def version_package(self) -> str:
        """The binary that answers ``probe_cmd`` — falls back to npm_package."""
        return self.version_bin or self.npm_package

    @property
    def is_wired(self) -> bool:
        """True iff this peer's declared capability is trusted for gating.

        The fail-closed predicate behind the never-fake contract: a peer that is
        not ``wired`` (planned/experimental/anything unrecognised) is treated as
        a capability the runtime must NOT depend on yet.
        """
        return self.status in WIRED_STATUSES


# Peer registry — post-rationalization state.
# Notes:
#   - wicked-vault will be re-homed into wicked-qe; coordinate bin name with
#     the vault-absorption agent before the next release cut.
#   - wicked-brain is in the bridge-period deprecation path; marked
#     experimental so gates never depend on it for new work.
#   - wicked-bus Rust rewrite uses the same CLI interface; no manifest change.
PEERS: dict = {
    "vault": Peer(
        name="vault",
        npm_package="wicked-vault",
        env_var="WICKED_VAULT_BIN",
        version_pin="0.3",
        # Post-absorption: wicked-vault is now exposed via wicked-testing's
        # package.json bin field. Installing wicked-testing puts wicked-vault
        # on PATH — no separate vault install command is needed.
        install_cmd=["npx", "wicked-testing", "install"],
        probe_cmd=["wicked-vault", "--version"],
        status=STATUS_WIRED,
    ),
    "testing": Peer(
        name="testing",
        npm_package="wicked-testing",
        env_var="WICKED_TESTING_BIN",
        version_pin="0.3",
        install_cmd=["npx", "wicked-testing", "install"],
        probe_cmd=["wicked-testing", "--version"],
        status=STATUS_WIRED,
    ),
    "brain": Peer(
        name="brain",
        npm_package="wicked-brain",
        env_var="WICKED_BRAIN_BIN",
        version_pin="0.14",
        install_cmd=["npm", "install", "-g", "wicked-brain@latest"],
        probe_cmd=["wicked-brain-server", "--version"],
        # Version lives in the server binary, not the `wicked-brain` package.
        version_bin="wicked-brain-server",
        # DEPRECATED: bridge period — garden now exposes equivalent surfaces via
        # wicked-memory + wicked-knowledge (wicked-estate MCP). New work must not
        # depend on brain. Marked experimental so gates never require it.
        status=STATUS_EXPERIMENTAL,
    ),
    "bus": Peer(
        name="bus",
        npm_package="wicked-bus",
        env_var="WICKED_BUS_BIN",
        version_pin="2.0",
        install_cmd=["npm", "install", "-g", "wicked-bus@latest"],
        probe_cmd=["wicked-bus", "--version"],
        status=STATUS_WIRED,
    ),
}


def get(name: str) -> "Peer | None":
    """Return the Peer for ``name`` or None if unknown."""
    return PEERS.get(name)
