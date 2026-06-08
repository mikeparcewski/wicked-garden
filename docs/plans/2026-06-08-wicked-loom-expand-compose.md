# wicked-loom — Expand Phase, Plan A (compose skeleton) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `wicked-loom` standalone package with its `compose` surface — peer manifest, the runtime resolution ladder, version-check, and install orchestration — publishable as `wicked-loom@0.1.0` and runnable as `npx wicked-loom`, with garden untouched.

**Architecture:** An **npm package** whose `bin` is a thin Node shim (`bin/loom.mjs`) that execs `python3` on a bundled Python module (`python/loom/`). The Python core holds all logic (CLI dispatch + compose). This matches garden's existing `npx wicked-*` consumption + resolution ladder while reusing garden's Python resolver code. **Compose only** — gate/flow/conduct is Plan B (do not build it here; YAGNI).

**Tech Stack:** Python 3.9+ (stdlib only — no third-party deps, mirroring garden's hook discipline), `pytest` for tests, a ~30-line Node ESM shim, `npm` packaging.

**Decisions locked for this plan (override in review):**
- Distribution: npm package + Node bin shim → bundled Python. (Alt: pip/pipx.)
- Scope: compose surface only — `loom resolve`, `loom doctor`, `loom compose install`. Conduct = Plan B.
- Target repo dir for execution: `~/Projects/wicked-loom` (a NEW git repo, sibling to wicked-garden). Adjust paths if you place it elsewhere.

**Source material to port (read these in wicked-garden before Task 3+):**
- `scripts/_integration_resolver.py`, `scripts/_capability_resolver.py` — the resolution ladder + kill-switch.
- `scripts/qe/vault_gate.py` (the `_resolve_vault` portion only) — the `WICKED_VAULT_BIN → config → PATH → node_modules → npx` ladder, verbatim pattern.
- `docs/required-peers.md` + `.claude-plugin/plugin.json` — the peer set, version pins (`testing ^0.3`, `vault ^0.3`, `brain ^0.14`, `bus ^2.0`) and install commands.

**Bulletproof standards:** R1–R6 (no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions) and T1–T6 (determinism, no sleep-based sync, isolation, single-assertion focus, descriptive names, provenance). The resolution ladder must be deterministic and fully mockable — never hit the network or real `npx` in a unit test.

---

## File Structure

```
wicked-loom/
├── package.json                 # npm metadata + bin: { "loom": "bin/loom.mjs" }
├── bin/loom.mjs                 # Node ESM shim → spawns python3 on python/loom
├── python/loom/
│   ├── __init__.py              # version constant
│   ├── __main__.py              # `python3 -m loom` entry → cli.main(argv)
│   ├── cli.py                   # arg dispatch: resolve | doctor | compose
│   ├── manifest.py              # Peer dataclass + PEERS registry (the peer set)
│   ├── resolve.py               # the runtime resolution ladder + kill-switch
│   └── compose.py               # version-check + install orchestration
├── tests/
│   ├── test_manifest.py
│   ├── test_resolve.py
│   ├── test_compose.py
│   └── test_cli.py
├── .gitignore
└── README.md
```

Responsibilities: `manifest` = *what the peers are* (data). `resolve` = *find a peer's runnable command* (the ladder). `compose` = *check versions + install* (actions, built on resolve+manifest). `cli` = *argument dispatch only* (no logic). `bin/loom.mjs` = *launch python3* (no logic). One responsibility per file; `cli` and the shim stay logic-free so the Python modules are unit-testable without a process boundary.

---

## Task 1: Repo + package skeleton

**Files:**
- Create: `~/Projects/wicked-loom/package.json`
- Create: `~/Projects/wicked-loom/.gitignore`
- Create: `~/Projects/wicked-loom/python/loom/__init__.py`

- [ ] **Step 1: Init the repo**

```bash
mkdir -p ~/Projects/wicked-loom/python/loom ~/Projects/wicked-loom/bin ~/Projects/wicked-loom/tests
cd ~/Projects/wicked-loom && git init
```

- [ ] **Step 2: Write `package.json`**

```json
{
  "name": "wicked-loom",
  "version": "0.1.0",
  "description": "Local-first orchestration runtime for agent ecosystems: resolves, version-checks, and installs the wicked-* peer set (compose). Conduct (gate/flow) ships separately.",
  "bin": { "loom": "bin/loom.mjs" },
  "files": ["bin/", "python/", "README.md"],
  "type": "module",
  "engines": { "node": ">=18" },
  "license": "MIT",
  "repository": "https://github.com/mikeparcewski/wicked-loom",
  "keywords": ["orchestration", "agents", "local-first", "compose", "wicked"]
}
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
node_modules/
.pytest_cache/
```

- [ ] **Step 4: Write `python/loom/__init__.py`**

```python
"""wicked-loom — orchestration runtime (compose surface)."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add package.json .gitignore python/loom/__init__.py
git commit -m "chore: wicked-loom package skeleton"
```

---

## Task 2: Node bin shim (launch python3)

**Files:**
- Create: `~/Projects/wicked-loom/bin/loom.mjs`
- Test: `~/Projects/wicked-loom/tests/test_cli.py` (the shim is smoke-tested via the CLI task; here we only assert it exists + is wired)

- [ ] **Step 1: Write the shim**

```javascript
#!/usr/bin/env node
// Thin launcher: find python3 and exec `python3 -m loom <args>` with python/ on PYTHONPATH.
// All logic lives in the Python module; this file only bridges npx → python3.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const pyRoot = join(here, "..", "python");

function findPython() {
  for (const cand of ["python3", "python", "py"]) {
    const r = spawnSync(cand, ["--version"], { stdio: "ignore" });
    if (r.status === 0) return cand;
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error("[wicked-loom] python3 is required but was not found on PATH.");
  process.exit(127);
}

const env = { ...process.env, PYTHONPATH: pyRoot + (process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : "") };
const res = spawnSync(python, ["-m", "loom", ...process.argv.slice(2)], { stdio: "inherit", env });
process.exit(res.status === null ? 1 : res.status);
```

- [ ] **Step 2: Make it executable + smoke it (will fail until `__main__` exists)**

Run: `chmod +x ~/Projects/wicked-loom/bin/loom.mjs && node ~/Projects/wicked-loom/bin/loom.mjs --help`
Expected: a Python error (`No module named loom.__main__`) — proves the shim finds python3 and dispatches. (Green after Task 6.)

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/wicked-loom
git add bin/loom.mjs
git commit -m "feat: node bin shim launches bundled python"
```

---

## Task 3: Peer manifest

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/manifest.py`
- Test: `~/Projects/wicked-loom/tests/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
from loom import manifest


def test_known_peers_present():
    assert set(manifest.PEERS) == {"vault", "testing", "brain", "bus"}


def test_each_peer_has_required_fields():
    for name, peer in manifest.PEERS.items():
        assert peer.name == name
        assert peer.npm_package.startswith("wicked-")
        assert peer.env_var.startswith("WICKED_") and peer.env_var.endswith("_BIN")
        assert peer.version_pin  # non-empty
        assert isinstance(peer.install_cmd, list) and peer.install_cmd
        assert isinstance(peer.probe_cmd, list) and peer.probe_cmd


def test_vault_pins_match_garden():
    assert manifest.PEERS["vault"].version_pin == "0.3"
    assert manifest.PEERS["vault"].env_var == "WICKED_VAULT_BIN"


def test_get_unknown_peer_returns_none():
    assert manifest.get("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.manifest'`

- [ ] **Step 3: Write `manifest.py`**

```python
"""manifest.py — the wicked-* peer set: what each peer is and how to reach it.

Source of truth ported from wicked-garden docs/required-peers.md + plugin.json.
Version pins are the MAJOR.MINOR floor (the `^x.y` in plugin.json), compared by
compose.py. Install commands are headless (npm/npx) — the `/plugin install`
path is CC-UX sugar, not the only route.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Peer:
    name: str
    npm_package: str
    env_var: str           # runtime override env var, e.g. WICKED_VAULT_BIN
    version_pin: str        # MAJOR.MINOR floor, e.g. "0.3"
    install_cmd: list[str]  # headless install command
    probe_cmd: list[str]    # command to print the installed version


PEERS: dict[str, Peer] = {
    "vault": Peer(
        name="vault",
        npm_package="wicked-vault",
        env_var="WICKED_VAULT_BIN",
        version_pin="0.3",
        install_cmd=["npx", "wicked-vault-install"],
        probe_cmd=["wicked-vault", "--version"],
    ),
    "testing": Peer(
        name="testing",
        npm_package="wicked-testing",
        env_var="WICKED_TESTING_BIN",
        version_pin="0.3",
        install_cmd=["npx", "wicked-testing", "install"],
        probe_cmd=["wicked-testing", "--version"],
    ),
    "brain": Peer(
        name="brain",
        npm_package="wicked-brain",
        env_var="WICKED_BRAIN_BIN",
        version_pin="0.14",
        install_cmd=["npm", "install", "-g", "wicked-brain@latest"],
        probe_cmd=["wicked-brain-server", "--version"],
    ),
    "bus": Peer(
        name="bus",
        npm_package="wicked-bus",
        env_var="WICKED_BUS_BIN",
        version_pin="2.0",
        install_cmd=["npm", "install", "-g", "wicked-bus@latest"],
        probe_cmd=["wicked-bus", "--version"],
    ),
}


def get(name: str) -> "Peer | None":
    """Return the Peer for ``name`` or None if unknown."""
    return PEERS.get(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_manifest.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/manifest.py tests/test_manifest.py
git commit -m "feat: peer manifest (vault/testing/brain/bus)"
```

---

## Task 4: Resolution ladder

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/resolve.py`
- Test: `~/Projects/wicked-loom/tests/test_resolve.py`

The ladder, ported from `vault_gate.py`: `WICKED_<PEER>_BIN` env → `PATH` (shutil.which) → `npx <package>` fallback. Empty env var (`WICKED_VAULT_BIN=""`) is the **kill-switch** → returns None. (Garden also checks a config file + node_modules; omitted in 0.1 as YAGNI — add when a consumer needs them.)

- [ ] **Step 1: Write the failing test**

```python
import shutil
from unittest.mock import patch

from loom import resolve


def test_env_var_override_wins(monkeypatch):
    monkeypatch.setenv("WICKED_VAULT_BIN", "/opt/custom/vault")
    assert resolve.resolve("vault") == ["/opt/custom/vault"]


def test_empty_env_var_is_killswitch(monkeypatch):
    monkeypatch.setenv("WICKED_VAULT_BIN", "")
    assert resolve.resolve("vault") is None


def test_path_lookup_when_no_env(monkeypatch):
    monkeypatch.delenv("WICKED_VAULT_BIN", raising=False)
    with patch.object(shutil, "which", return_value="/usr/local/bin/wicked-vault"):
        assert resolve.resolve("vault") == ["/usr/local/bin/wicked-vault"]


def test_npx_fallback_when_not_on_path(monkeypatch):
    monkeypatch.delenv("WICKED_VAULT_BIN", raising=False)
    with patch.object(shutil, "which", return_value=None):
        assert resolve.resolve("vault") == ["npx", "wicked-vault"]


def test_unknown_peer_returns_none():
    assert resolve.resolve("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_resolve.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.resolve'`

- [ ] **Step 3: Write `resolve.py`**

```python
"""resolve.py — the runtime resolution ladder for a peer's runnable command.

Ladder (highest priority first):
  1. WICKED_<PEER>_BIN env var — explicit override. Empty string is a
     deliberate kill-switch (returns None, resolution short-circuits cleanly).
  2. PATH — shutil.which(<npm_package>).
  3. npx fallback — ["npx", "<npm_package>"].

Returns a command as a list[str] (argv-ready) or None when unresolvable /
killed / unknown peer. Pure + deterministic: no process is spawned here.
"""

from __future__ import annotations

import os
import shutil

from loom import manifest


def resolve(peer_name: str) -> "list[str] | None":
    peer = manifest.get(peer_name)
    if peer is None:
        return None

    if peer.env_var in os.environ:
        override = os.environ[peer.env_var].strip()
        if override == "":
            return None  # kill-switch
        return [override]

    on_path = shutil.which(peer.npm_package)
    if on_path:
        return [on_path]

    return ["npx", peer.npm_package]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_resolve.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/resolve.py tests/test_resolve.py
git commit -m "feat: peer resolution ladder + kill-switch"
```

---

## Task 5: Version-check + install orchestration

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/compose.py`
- Test: `~/Projects/wicked-loom/tests/test_compose.py`

`check_peer` resolves the peer, runs its `probe_cmd`, parses a semver-ish version, and compares MAJOR.MINOR against the pin. `install_peer` runs the headless `install_cmd`. Both return structured dicts; neither raises (R4 — surface errors as data). A subprocess runner is injected so tests never spawn real processes (T1/T3).

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from loom import compose


def _runner(stdout="", code=0):
    def run(cmd, timeout=None):
        return compose.RunResult(returncode=code, stdout=stdout, stderr="")
    return run


def test_check_peer_satisfied_when_version_meets_pin():
    with patch.object(compose, "resolve", return_value=["wicked-vault"]):
        r = compose.check_peer("vault", run=_runner(stdout="wicked-vault 0.3.2\n"))
    assert r["status"] == "ok"
    assert r["installed"] == "0.3.2"
    assert r["pin"] == "0.3"


def test_check_peer_below_pin_is_drift():
    with patch.object(compose, "resolve", return_value=["wicked-vault"]):
        r = compose.check_peer("vault", run=_runner(stdout="0.2.9"))
    assert r["status"] == "drift"


def test_check_peer_unresolvable_is_missing():
    with patch.object(compose, "resolve", return_value=None):
        r = compose.check_peer("vault", run=_runner())
    assert r["status"] == "missing"


def test_check_peer_probe_failure_is_error():
    with patch.object(compose, "resolve", return_value=["wicked-vault"]):
        r = compose.check_peer("vault", run=_runner(code=1))
    assert r["status"] == "error"


def test_install_peer_runs_install_cmd_and_reports():
    calls = []

    def run(cmd, timeout=None):
        calls.append(cmd)
        return compose.RunResult(returncode=0, stdout="ok", stderr="")

    r = compose.install_peer("vault", run=run)
    assert calls == [["npx", "wicked-vault-install"]]
    assert r["status"] == "installed"


def test_install_unknown_peer_is_error():
    r = compose.install_peer("nope", run=_runner())
    assert r["status"] == "error"


def test_check_all_returns_one_row_per_peer():
    with patch.object(compose, "resolve", return_value=["x"]):
        rows = compose.check_all(run=_runner(stdout="9.9.9"))
    assert {row["peer"] for row in rows} == {"vault", "testing", "brain", "bus"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_compose.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.compose'`

- [ ] **Step 3: Write `compose.py`**

```python
"""compose.py — version-check + install orchestration over the peer set.

check_peer:  resolve → probe → parse version → compare MAJOR.MINOR to the pin.
install_peer: run the peer's headless install command.
check_all:   one check_peer row per known peer.

Subprocess execution is injected (the ``run`` parameter) so callers (and tests)
control side effects. Nothing here raises — failures are returned as status
rows ("ok" | "drift" | "missing" | "error" | "installed" | "install-failed").
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable

from loom import manifest
from loom.resolve import resolve

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., RunResult]


def _default_run(cmd: list[str], timeout: int = 30) -> RunResult:
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
    pv = _parse_version(pin) or pin
    if iv is None:
        return False
    ip = [int(x) for x in iv.split(".")]
    pp = [int(x) for x in (_parse_version(pin) or "0.0.0").split(".")]
    # Compare MAJOR.MINOR floor.
    return (ip[0], ip[1]) >= (pp[0], pp[1])


def check_peer(name: str, run: Runner = _default_run) -> dict:
    peer = manifest.get(name)
    if peer is None:
        return {"peer": name, "status": "error", "detail": "unknown peer"}

    cmd = resolve(name)
    if cmd is None:
        return {"peer": name, "status": "missing", "pin": peer.version_pin}

    try:
        result = run(cmd[:1] + peer.probe_cmd[1:] if cmd[0] == peer.probe_cmd[0]
                     else cmd + peer.probe_cmd[1:])
    except Exception as e:  # noqa: BLE001 — surface as data, never crash (R4)
        return {"peer": name, "status": "error", "detail": str(e), "pin": peer.version_pin}

    if result.returncode != 0:
        return {"peer": name, "status": "error", "detail": result.stderr.strip(),
                "pin": peer.version_pin}

    installed = _parse_version(result.stdout)
    if installed is None:
        return {"peer": name, "status": "error", "detail": "unparseable version",
                "pin": peer.version_pin}

    status = "ok" if _meets_pin(installed, peer.version_pin) else "drift"
    return {"peer": name, "status": status, "installed": installed, "pin": peer.version_pin}


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


def check_all(run: Runner = _default_run) -> list[dict]:
    return [check_peer(name, run=run) for name in manifest.PEERS]
```

> Note for the implementer: the `check_peer` `run(...)` argument constructs the probe command from the resolved command + the probe's trailing args. Keep it simple — if `resolve` returned `["npx", "wicked-vault"]`, the probe is `["npx", "wicked-vault", "--version"]`; if it returned `["/usr/local/bin/wicked-vault"]`, the probe is `["/usr/local/bin/wicked-vault", "--version"]`. The expression above does exactly that; if it reads awkwardly, refactor to an explicit `_probe_command(cmd, peer)` helper with its own test — but keep behavior identical.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_compose.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/compose.py tests/test_compose.py
git commit -m "feat: compose version-check + install orchestration"
```

---

## Task 6: CLI dispatch + `__main__`

**Files:**
- Create: `~/Projects/wicked-loom/python/loom/cli.py`
- Create: `~/Projects/wicked-loom/python/loom/__main__.py`
- Test: `~/Projects/wicked-loom/tests/test_cli.py`

`cli.main(argv)` dispatches `resolve <peer>`, `doctor`, `compose install [--peer X]` and prints JSON to stdout, returning an exit code. Logic stays in resolve/compose; cli only parses args + formats output (R6 — no god function).

- [ ] **Step 1: Write the failing test**

```python
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

from loom import cli


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


def test_resolve_prints_command():
    with patch("loom.cli.resolve", return_value=["npx", "wicked-vault"]):
        code, out = _run(["resolve", "vault"])
    assert code == 0
    assert json.loads(out)["command"] == ["npx", "wicked-vault"]


def test_resolve_unresolvable_exits_nonzero():
    with patch("loom.cli.resolve", return_value=None):
        code, out = _run(["resolve", "vault"])
    assert code == 1
    assert json.loads(out)["command"] is None


def test_doctor_prints_all_rows():
    rows = [{"peer": "vault", "status": "ok"}]
    with patch("loom.cli.check_all", return_value=rows):
        code, out = _run(["doctor"])
    assert code == 0
    assert json.loads(out)["peers"] == rows


def test_doctor_exits_nonzero_on_missing_peer():
    rows = [{"peer": "vault", "status": "missing"}]
    with patch("loom.cli.check_all", return_value=rows):
        code, _ = _run(["doctor"])
    assert code == 1


def test_compose_install_targets_one_peer():
    with patch("loom.cli.install_peer", return_value={"peer": "vault", "status": "installed"}) as m:
        code, out = _run(["compose", "install", "--peer", "vault"])
    assert code == 0
    m.assert_called_once_with("vault")
    assert json.loads(out)["results"][0]["status"] == "installed"


def test_unknown_command_exits_two():
    code, _ = _run(["frobnicate"])
    assert code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loom.cli'`

- [ ] **Step 3: Write `cli.py`**

```python
"""cli.py — argument dispatch + JSON output for the compose surface.

Commands:
  loom resolve <peer>              -> {"peer","command"}            exit 0/1
  loom doctor                      -> {"peers":[check rows]}        exit 0/1
  loom compose install [--peer X]  -> {"results":[install rows]}    exit 0/1

No business logic lives here — only parsing + formatting.
"""

from __future__ import annotations

import json
import sys

from loom import manifest
from loom.compose import check_all, install_peer
from loom.resolve import resolve


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")


def _cmd_resolve(args: list[str]) -> int:
    if not args:
        _emit({"error": "usage: loom resolve <peer>"})
        return 2
    cmd = resolve(args[0])
    _emit({"peer": args[0], "command": cmd})
    return 0 if cmd is not None else 1


def _cmd_doctor(_args: list[str]) -> int:
    rows = check_all()
    _emit({"peers": rows})
    return 0 if all(r.get("status") == "ok" for r in rows) else 1


def _cmd_compose(args: list[str]) -> int:
    if not args or args[0] != "install":
        _emit({"error": "usage: loom compose install [--peer <name>]"})
        return 2
    target = None
    if "--peer" in args:
        i = args.index("--peer")
        if i + 1 < len(args):
            target = args[i + 1]
    names = [target] if target else list(manifest.PEERS)
    results = [install_peer(n) for n in names]
    _emit({"results": results})
    return 0 if all(r.get("status") == "installed" for r in results) else 1


_DISPATCH = {"resolve": _cmd_resolve, "doctor": _cmd_doctor, "compose": _cmd_compose}


def main(argv: "list[str] | None" = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _emit({"commands": list(_DISPATCH)})
        return 0
    handler = _DISPATCH.get(argv[0])
    if handler is None:
        _emit({"error": f"unknown command: {argv[0]}", "commands": list(_DISPATCH)})
        return 2
    return handler(argv[1:])
```

- [ ] **Step 4: Write `__main__.py`**

```python
"""`python3 -m loom` entry point."""

import sys

from loom.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest tests/test_cli.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Smoke the full path through the Node shim**

Run: `cd ~/Projects/wicked-loom && node bin/loom.mjs doctor`
Expected: a JSON line `{"peers": [...]}` with one row per peer (statuses depend on what's installed locally; the point is the shim → python3 → cli path works end-to-end).

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/wicked-loom
git add python/loom/cli.py python/loom/__main__.py tests/test_cli.py
git commit -m "feat: compose CLI (resolve/doctor/compose install) + __main__"
```

---

## Task 7: README + full suite + publish-readiness

**Files:**
- Create: `~/Projects/wicked-loom/README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# wicked-loom

Local-first orchestration runtime for agent ecosystems. **0.1 ships the
`compose` surface** — it resolves, version-checks, and installs the `wicked-*`
peer set. Conduct (gate/flow) ships separately.

## Use

    npx wicked-loom doctor                      # check every peer
    npx wicked-loom resolve vault               # print vault's runnable command
    npx wicked-loom compose install --peer bus  # install one peer

Requires `python3` on PATH (the npm package launches a bundled Python core).

## Resolution ladder

For each peer: `WICKED_<PEER>_BIN` env (empty = kill-switch) → `PATH` →
`npx <package>`.

## Peers

vault · testing · brain · bus — pins mirror wicked-garden's `required-peers`.
```

- [ ] **Step 2: Run the full suite**

Run: `cd ~/Projects/wicked-loom && PYTHONPATH=python python3 -m pytest -v`
Expected: PASS — 22 tests (4 manifest + 5 resolve + 7 compose + 6 cli).

- [ ] **Step 3: Dry-run the npm package contents**

Run: `cd ~/Projects/wicked-loom && npm pack --dry-run`
Expected: the tarball lists `bin/`, `python/`, `README.md`, `package.json` — and NOT `tests/` or `__pycache__/`.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/wicked-loom
git add README.md
git commit -m "docs: README + publish-readiness"
```

- [ ] **Step 5: STOP — publish is a human-gated outward action**

Do **not** run `npm publish` autonomously. Report to the operator that `wicked-loom@0.1.0` is publish-ready (suite green, `npm pack` clean) and let them publish + create the GitHub repo. Garden integration (the resolve cutover) is a later plan.

---

## Self-Review

**Spec coverage (Plan A scope = compose):**
- COMPOSE: declare (manifest, Task 3) · resolve ladder + kill-switch (Task 4) · version-check + install (Task 5) · CLI surface `resolve`/`doctor`/`compose install` (Task 6). ✓ matches spec §4.1 / §4.3.
- D5 (npm + python via subprocess): package.json bin → Node shim → python3 (Tasks 1–2, 6). ✓
- Standalone-usable by a non-garden consumer (success criterion #1): `npx wicked-loom doctor` works with zero garden present. ✓
- **Deferred (correctly out of scope for Plan A):** conduct/gate/flow/park (§4.2), bus event contract (§4.3 #2/#3), the archetype→flow seam (§3.1), garden cutover (§7 step 2). These belong to Plan B + the cutover plan. No gap — intentional decomposition.

**Placeholder scan:** No TBD/TODO; every code step has complete code; the one prose note (Task 5 probe-command construction) shows the exact expression + the refactor option with identical behavior. ✓

**Type consistency:** `Peer` fields (`name`, `npm_package`, `env_var`, `version_pin`, `install_cmd`, `probe_cmd`) are used identically in manifest/resolve/compose/cli. `resolve()` returns `list[str] | None` everywhere. `RunResult(returncode, stdout, stderr)` consistent across compose + tests. `check_peer`/`install_peer`/`check_all` signatures match their cli call sites. Status vocabulary (`ok`/`drift`/`missing`/`error`/`installed`/`install-failed`) consistent. ✓

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.

Note: execution happens in a **new repo** (`~/Projects/wicked-loom`), not in wicked-garden.
