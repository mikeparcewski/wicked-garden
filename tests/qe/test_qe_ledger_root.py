"""The QE skill honours WICKED_QE_LEDGER_DIR as the ledger root (wicked-crew#951).

A governed wicked-crew run hands its QE unit the run's own ledger, outside the worktree, as
`WICKED_QE_LEDGER_DIR`. Before this, `qe accept` resolved `<cwd>/.wicked-qe`, which is the worktree.
The run's guard discarded the ledger (and the PASS in it), and delivery was refused. These tests run
the skill's own shell snippets (the preflight config check and setup's scaffold) with the variable
set, and pin the accept pipeline's root and evidence-dir lines plus the wicked-ledger pin that makes
`resolveLedgerRoot` honour the variable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "qe" / "SKILL.md"
ACCEPT = ROOT / "skills" / "qe" / "refs" / "accept.md"
SETUP = ROOT / "skills" / "qe" / "refs" / "setup.md"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"

posix_shell = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None, reason="the snippets are POSIX shell"
)


def _preflight(doc: Path) -> str:
    line = next(l for l in doc.read_text(encoding="utf-8").splitlines() if "ERR_NO_CONFIG" in l and l.startswith("if "))
    return line.split("  # <!--")[0]


def _run(cmd: str, cwd: Path, pin: Path | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "WICKED_QE_LEDGER_DIR"}
    if pin is not None:
        env["WICKED_QE_LEDGER_DIR"] = str(pin)
    return subprocess.run(["sh", "-c", cmd], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout


@posix_shell
@pytest.mark.parametrize("doc", [SKILL, ACCEPT], ids=["SKILL.md", "accept.md"])
def test_the_preflight_reads_the_pinned_root_exactly(doc: Path, tmp_path: Path) -> None:
    work = tmp_path / "worktree"
    (work / ".wicked-qe").mkdir(parents=True)
    (work / ".wicked-qe" / "config.json").write_text("{}")
    run_ledger = tmp_path / "evidence" / ".wicked-qe"
    run_ledger.mkdir(parents=True)
    check = _preflight(doc)
    # Pinned and the run ledger has no config: the worktree's config does NOT count.
    assert "ERR_NO_CONFIG" in _run(check, work, run_ledger)
    (run_ledger / "config.json").write_text("{}")
    assert "ERR_NO_CONFIG" not in _run(check, work, run_ledger)
    # Unpinned: the cwd dual-read is unchanged.
    assert "ERR_NO_CONFIG" not in _run(check, work, None)
    assert "ERR_NO_CONFIG" in _run(check, tmp_path, None)


@posix_shell
def test_setup_scaffolds_the_pinned_root_and_nothing_in_the_worktree(tmp_path: Path) -> None:
    text = SETUP.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, flags=re.S)
    mkdir = next(b for b in blocks if "os.makedirs" in b)
    assert "<same script>" not in mkdir, "the scaffold runs one real script on python3 or python"
    config = next(b for b in blocks if "config.json" in b and "python3 -c" in b)
    config = config.split(" 2>/dev/null ||")[0]  # the python3 arm; the `python` fallback is the same script
    if shutil.which("python3") is None:
        pytest.skip("python3 not on PATH")
    work = tmp_path / "worktree"
    work.mkdir()
    run_ledger = tmp_path / "evidence" / ".wicked-qe"
    _run(mkdir, work, run_ledger)
    _run(config, work, run_ledger)
    assert (run_ledger / "verdicts").is_dir() and (run_ledger / "evidence").is_dir()
    assert json.loads((run_ledger / "config.json").read_text())["version"] == "1.0"
    assert not (work / ".wicked-qe").exists(), "setup wrote into the worktree"
    # wicked-core#881: no shell write of the unexpanded variable (a governed fence refuses it)
    assert 'mkdir -p "$' not in text and "mkdir -p \"$" not in text


def test_accept_resolves_the_root_through_wicked_ledger_and_keeps_evidence_under_it() -> None:
    text = ACCEPT.read_text(encoding="utf-8")
    assert "const LEDGER_ROOT = resolveLedgerRoot(process.cwd());" in text
    assert "const EVIDENCE_DIR = join(LEDGER_ROOT, 'evidence', RUN_ID);" in text
    assert "${WICKED_DIR}/evidence" not in text, "a cwd-relative evidence dir targets the worktree"


def test_the_plugin_pins_a_wicked_ledger_whose_resolver_honours_the_variable() -> None:
    pin = json.loads(PLUGIN.read_text(encoding="utf-8"))["wicked_ledger_version"]
    major, minor = (int(x) for x in re.match(r"\^?(\d+)\.(\d+)", pin).groups())
    assert (major, minor) >= (0, 6), pin


LEDGER_PKG = ROOT / "scripts" / "qe" / "lib" / "ledger-pkg.mjs"

_RESOLVE = r"""
const { resolveLedgerModule } = await import(process.argv[1]);
const mod = await resolveLedgerModule(process.argv[2]);
console.log(JSON.stringify({ found: mod !== null, marker: mod?.MARKER ?? null }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_the_resolver_honours_wicked_ledger_pkg_dir_exactly(tmp_path: Path) -> None:
    """wicked-crew#951: a governed run hands its QE unit crew's own wicked-ledger as
    WICKED_LEDGER_PKG_DIR, so accept records with the package crew reads with — no install in the
    worktree. A pin is exact: unusable ⇒ null, never a fallback to another package."""
    pkg = tmp_path / "crew-ledger"
    pkg.mkdir()
    (pkg / "package.json").write_text(json.dumps({"name": "wicked-ledger", "type": "module", "exports": {".": "./index.mjs"}}))
    (pkg / "index.mjs").write_text("export const MARKER = 'crew-bundled';\n")
    repo = tmp_path / "worktree"
    repo.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "WICKED_LEDGER_PKG_DIR"}

    def run(pin: str | None) -> dict:
        e = dict(env)
        if pin is not None:
            e["WICKED_LEDGER_PKG_DIR"] = pin
        out = subprocess.run(
            ["node", "--input-type=module", "-e", _RESOLVE, LEDGER_PKG.as_uri(), str(repo)],
            env=e, capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out.strip().splitlines()[-1])

    assert run(str(pkg)) == {"found": True, "marker": "crew-bundled"}
    assert run(str(tmp_path / "nowhere"))["found"] is False


def test_accept_and_the_gate_load_wicked_ledger_through_the_one_resolver() -> None:
    accept = ACCEPT.read_text(encoding="utf-8")
    assert "pathToFileURL(joinPath(String.raw`{WT_LIB}`, 'ledger-pkg.mjs')).href" in accept
    assert "from 'wicked-ledger'" not in accept and 'from "wicked-ledger"' not in accept
    gate = (ROOT / "scripts" / "qe" / "lib" / "gate.mjs").read_text(encoding="utf-8")
    assert 'from "./ledger-pkg.mjs"' in gate and "async function resolveLedgerModule" not in gate
