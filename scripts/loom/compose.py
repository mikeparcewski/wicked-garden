"""compose.py — version-check + install orchestration over the peer set.

Absorbed from wicked-loom (Phase B — ECOSYSTEM-RATIONALIZATION.md §5a).

check_peer:  resolve -> probe -> parse version -> compare MAJOR.MINOR to the pin.
install_peer: run the peer's headless install command.
check_all:   one check_peer row per known peer.

Subprocess execution is injected (the ``run`` parameter) so callers (and tests)
control side effects. Nothing here raises — failures are returned as status
rows ("ok" | "drift" | "present" | "missing" | "error" | "installed"
| "install-failed").

Status semantics (no cry-wolf — see R4 "never raise, surface as data"):
  ok       — resolved, probe ran, version parsed, version >= pin.
  drift    — resolved, probe ran, version parsed, version <  pin.
  present  — resolved AND the probe binary RAN (we got a RunResult, not an
             exception), but its version could not be determined: a non-zero
             exit (older CLIs print help/usage when given ``--version``) or
             unparseable output. The peer is healthy/responding; we just can't
             read its version. This is WARN-level, NOT an error — reporting a
             responding peer as "error" was a false alarm (cry-wolf). The
             ``ok`` flag on the row is True so health probes don't fail hard.
  missing  — unresolvable: no binary on PATH / npx / env override (kill-switch).
  error    — reserved for genuine faults: unknown peer, or the probe attempt
             RAISED (binary vanished, OS error). A responding-but-unparseable
             peer is NEVER "error".

``status`` above is runtime REACHABILITY (can we run it / does its version meet
the pin). Every row ALSO carries the peer's declared CAPABILITY readiness under
a separate ``capability`` key (``wired``/``planned``/``experimental`` from
manifest.Peer.status) plus ``capability_ok``. The two are deliberately distinct:
a peer can be perfectly reachable (status ``ok``) yet not wired as a capability
(``capability`` ``planned``) — doctor must answer "reachable but not wired yet"
distinctly from "missing/drift". Overloading the reachability ``status`` key
would break doctor's exit logic, so the capability lives on its own key.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from loom import manifest
from loom.manifest import Peer
from loom.resolve import resolve_version_bin

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., RunResult]


def _default_run(cmd: list, timeout: int = 30) -> RunResult:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return RunResult(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def _parse_version(text: str) -> "str | None":
    m = _VERSION_RE.search(text or "")
    if not m:
        return None
    major, minor, patch = m.group(1), m.group(2), m.group(3) or "0"
    return f"{major}.{minor}.{patch}"


def _meets_pin(installed: str, pin: str) -> bool:
    iv = _parse_version(installed)
    pv = _parse_version(pin)
    if iv is None or pv is None:
        return False
    ip = [int(x) for x in iv.split(".")]
    pp = [int(x) for x in pv.split(".")]
    return (ip[0], ip[1]) >= (pp[0], pp[1])  # MAJOR.MINOR floor


def _probe_command(version_cmd: list, peer: Peer) -> list:
    """The version-probe argv: the resolved version binary + the probe's
    trailing args.

    The version binary can differ from the runnable package — brain runs as
    ``wicked-brain`` but reports its version via ``wicked-brain-server`` — so
    we resolve ``peer.version_package`` (not npm_package) here.
    """
    return version_cmd + peer.probe_cmd[1:]


def _stamp_capability(row: dict, peer: "Peer | None") -> dict:
    """Add the peer's declared capability readiness to a reachability row.

    ``capability`` is the manifest's honest status (wired/planned/experimental)
    — orthogonal to the row's ``status`` (reachability). ``capability_ok`` mirrors
    the never-fake predicate (``True`` only for ``wired``). For an unknown peer
    (no manifest entry) there is no declared capability, so both are None/False.
    Doctor surfaces these so "reachable but not wired" reads distinctly from
    "missing/drift". This NEVER changes the reachability ``status`` or ``ok`` keys
    — the capability is purely additive (no cry-wolf, no exit-logic change).
    """
    if peer is None:
        row["capability"] = None
        row["capability_ok"] = False
    else:
        row["capability"] = peer.status
        row["capability_ok"] = peer.is_wired
    return row


def check_peer(name: str, run: Runner = _default_run) -> dict:
    peer = manifest.get(name)
    return _stamp_capability(_check_peer_reachability(name, peer, run=run), peer)


def _check_peer_reachability(name: str, peer: "Peer | None",
                             run: Runner = _default_run) -> dict:
    if peer is None:
        return {"peer": name, "status": "error", "ok": False, "detail": "unknown peer"}

    version_cmd = resolve_version_bin(name)
    if version_cmd is None:
        # Genuinely unresolvable — no binary anywhere. Legitimately not-ok.
        return {"peer": name, "status": "missing", "ok": False, "pin": peer.version_pin}

    try:
        result = run(_probe_command(version_cmd, peer))
    except Exception as e:  # noqa: BLE001 — surface as data, never crash (R4)
        # The probe itself RAISED (binary vanished mid-call, OS error). This is
        # the only path that means "absent/unrunnable" once resolution succeeded
        # — a genuine error, not cry-wolf.
        return {"peer": name, "status": "error", "ok": False,
                "detail": str(e), "pin": peer.version_pin}

    # From here the binary resolved AND produced a RunResult: the peer is
    # PRESENT and RESPONDING. Prefer stdout for the version, but tolerate older
    # CLIs that print it to stderr.
    installed = _parse_version(result.stdout) or _parse_version(result.stderr)

    if installed is not None:
        status = "ok" if _meets_pin(installed, peer.version_pin) else "drift"
        return {"peer": name, "status": status, "ok": status == "ok",
                "installed": installed, "pin": peer.version_pin}

    # Present + responding, but version unknown: a non-zero exit (older buses
    # print help/usage JSON for an unrecognized ``--version``) OR parseable-free
    # output. The peer is healthy — do NOT raise a hard "error" (the cry-wolf
    # finding). Surface it as WARN-level "present" with ok=True so doctor/health
    # probes don't treat a responding peer as a failure.
    detail = (
        "probe exited %d; version not reported (older CLI may print help "
        "for --version)" % result.returncode
        if result.returncode != 0
        else "version not reported by probe output"
    )
    return {"peer": name, "status": "present", "ok": True,
            "detail": detail, "pin": peer.version_pin}


def install_peer(name: str, run: Runner = _default_run) -> dict:
    peer = manifest.get(name)
    if peer is None:
        return {"peer": name, "status": "error", "detail": "unknown peer"}
    try:
        result = run(peer.install_cmd, timeout=300)
    except Exception as e:  # noqa: BLE001
        return {"peer": name, "status": "install-failed", "detail": str(e)}
    if result.returncode != 0:
        return {"peer": name, "status": "install-failed", "detail": result.stderr.strip()}
    return {"peer": name, "status": "installed"}


def check_all(run: Runner = _default_run) -> list:
    return [check_peer(name, run=run) for name in manifest.PEERS]
