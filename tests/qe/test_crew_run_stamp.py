"""QE ledger rows written inside a governed run carry `crew_run_id` (WT-G4, DES-walkthrough-proof §4.14).

wicked-crew's acceptance reader (`packages/crew/src/qe/ledger.ts`, `stampedCrewRun` + `attribute`) attributes a QE
run to a crew run `kind: 'stamped'` when the QE run's `runs` row, or any of its `verdicts`, carries a top-level
`crew_run_id` equal to the crew run's id in its canonical JSON (`<ledger root>/<table>/<id>.json`). Without a stamp
it can only INFER attribution from the run's lifetime. Garden's writers are the qe-runner (`runs` row,
`scripts/qe/runner/src/evidence.mjs`) and the gate (`verdicts` row, `scripts/qe/lib/gate.mjs`); both stamp from
`WICKED_RUN_ID`, the variable every governed seat gets.

The fixture drives both writers through their real surfaces against a ledger package: a stub that writes canonical
JSON the way wicked-ledger does (it keeps unknown keys at top level), or the real package when
WICKED_LEDGER_PKG_DIR points at an installed wicked-ledger. Then it reads the files with a port of crew's predicate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "scripts" / "qe" / "runner" / "src" / "evidence.mjs"
GATE = ROOT / "scripts" / "qe" / "lib" / "gate.mjs"

pytestmark = [
    pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH"),
    pytest.mark.skipif(sys.platform == "win32", reason="the fixture's fake wicked-bus is a POSIX script"),
]

# A CommonJS stand-in for wicked-ledger: the runner require()s it and the gate import()s it.
_STUB_INDEX = r"""
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
exports.createDomainStore = function createDomainStore({ root }) {
  const file = (t, id) => path.join(root, t, `${id}.json`);
  const read = (t, id) => { try { return JSON.parse(fs.readFileSync(file(t, id), "utf8")); } catch { return null; } };
  const write = (t, row) => { fs.mkdirSync(path.join(root, t), { recursive: true }); fs.writeFileSync(file(t, row.id), JSON.stringify(row)); return row; };
  return {
    create(t, rec) { const now = new Date().toISOString(); return write(t, { ...rec, id: rec.id ?? randomUUID(), created_at: now, updated_at: now, deleted: 0, deleted_at: null }); },
    get: read,
    list(t, where = {}) {
      const d = path.join(root, t);
      if (!fs.existsSync(d)) return [];
      return fs.readdirSync(d).map((f) => JSON.parse(fs.readFileSync(path.join(d, f), "utf8")))
        .filter((r) => Object.entries(where).every(([k, v]) => r[k] === v));
    },
    update(t, id, patch) { return write(t, { ...read(t, id), ...patch, id }); },
    close() {},
  };
};
"""
_STUB_MANIFEST = r"""
const fs = require("node:fs");
const path = require("node:path");
exports.buildManifest = function buildManifest({ runRecord, evidenceDir }) {
  const p = path.join(evidenceDir, "manifest.json");
  const manifest = { run_id: runRecord.id };
  fs.writeFileSync(p, JSON.stringify(manifest));
  return { path: p, manifest };
};
"""

# crew's predicate, ported: a QE run is `stamped` for crew run R when its run row or any verdict of it carries
# crew_run_id === R (packages/crew/src/qe/ledger.ts stampedCrewRun / attribute).
_CREW_READER = r"""
import fs from "node:fs";
import path from "node:path";
const [root, crewRunId] = process.argv.slice(1);  // with -e, argv[1] is the first argument
const rows = (t) => { const d = path.join(root, t); return fs.existsSync(d) ? fs.readdirSync(d).map((f) => JSON.parse(fs.readFileSync(path.join(d, f), "utf8"))) : []; };
const stamped = (rec) => (typeof rec?.crew_run_id === "string" && rec.crew_run_id !== "" ? rec.crew_run_id : null);
const runs = new Map(rows("runs").map((r) => [r.id, r]));
const out = {};
for (const v of rows("verdicts")) {
  const e = (out[v.run_id] ??= { stamped: false });
  if (stamped(v) === crewRunId) e.stamped = true;
}
for (const [id, e] of Object.entries(out)) if (stamped(runs.get(id)) === crewRunId) e.stamped = true;
console.log(JSON.stringify(Object.fromEntries(Object.entries(out).map(([id, e]) => [id, e.stamped ? { kind: "stamped", qeRunId: id } : { kind: "unstamped" }]))));
"""

_WRITE_RUN = r"""
const { writeEvidence } = await import(process.argv[1]);
const out = writeEvidence({
  spec: { spec_version: "1.0", scenario: { id: "g4-stamp", name: "g4 stamp", project: "g4" },
          target: { base_url: "http://127.0.0.1:1" }, steps: [{ action: "goto", path: "/" }], assertions: [] },
  captures: { wire: {}, websockets: [], wsFirstFrame: undefined, readbacks: {}, console: [] },
  assertionResults: [], stepLog: [{ index: 0, action: "goto", ok: true, started_at: "t", finished_at: "t" }],
  repoRoot: process.argv[2], claim: "PASS", claimReason: "fixture",
  startedAt: "2026-10-01T00:00:00.000Z", finishedAt: "2026-10-01T00:00:01.000Z",
});
console.log(JSON.stringify({ runId: out.runId }));
"""


def _repo(tmp_path: Path) -> tuple[Path, dict]:
    repo = tmp_path / "repo"
    pkg = repo / "node_modules" / "wicked-ledger"
    real = os.environ.get("WICKED_LEDGER_PKG_DIR")
    pkg.parent.mkdir(parents=True)
    if real:
        pkg.symlink_to(Path(real).resolve(), target_is_directory=True)
    else:
        pkg.mkdir()
        (pkg / "package.json").write_text(json.dumps({
            "name": "wicked-ledger", "version": "0.0.0-stub", "type": "commonjs",
            "exports": {".": "./index.js", "./manifest": "./manifest.js"},
        }))
        (pkg / "index.js").write_text(_STUB_INDEX)
        (pkg / "manifest.js").write_text(_STUB_MANIFEST)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    bus = bindir / "wicked-bus"
    bus.write_text("#!/bin/sh\nexit 0\n")
    bus.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("WICKED_RUN_ID", "WICKED_QE_LEDGER_DIR")}
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["NODE_PATH"] = str(repo / "node_modules")  # the runner require()s wicked-ledger from its own dir
    return repo, env


def _qe_run(repo: Path, env: dict) -> str:
    """The execute half (runner writes the runs row), then the accept half (gate writes the verdict)."""
    w = subprocess.run(["node", "--input-type=module", "-e", _WRITE_RUN, EVIDENCE.as_uri(), str(repo)],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    assert w.returncode == 0, w.stderr[-2000:]
    run_id = json.loads(w.stdout.strip().splitlines()[-1])["runId"]
    g = subprocess.run(["node", str(GATE), "--project-id", "g4", "--run-id", run_id, "--verdict", "PASS",
                        "--verdict-summary", "fixture pass"],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    assert g.returncode == 0, (g.stdout[-1000:], g.stderr[-2000:])
    return run_id


def _crew_reads(repo: Path, crew_run_id: str) -> dict:
    r = subprocess.run(["node", "--input-type=module", "-e", _CREW_READER, str(repo / ".wicked-qe"), crew_run_id],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _rows(repo: Path, table: str) -> list[dict]:
    d = repo / ".wicked-qe" / table
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def test_a_qe_run_inside_a_governed_run_is_attributed_stamped_by_crews_reader(tmp_path):
    repo, env = _repo(tmp_path)
    env["WICKED_RUN_ID"] = "crew-run-g4"
    run_id = _qe_run(repo, env)
    assert [r["crew_run_id"] for r in _rows(repo, "runs")] == ["crew-run-g4"]
    assert [v["crew_run_id"] for v in _rows(repo, "verdicts")] == ["crew-run-g4"]
    assert _crew_reads(repo, "crew-run-g4") == {run_id: {"kind": "stamped", "qeRunId": run_id}}
    # Another crew run's reader never claims it.
    assert _crew_reads(repo, "crew-run-other") == {run_id: {"kind": "unstamped"}}


def test_outside_a_governed_run_nothing_is_stamped(tmp_path):
    repo, env = _repo(tmp_path)
    run_id = _qe_run(repo, env)
    assert all("crew_run_id" not in r for r in _rows(repo, "runs") + _rows(repo, "verdicts"))
    assert _crew_reads(repo, "crew-run-g4") == {run_id: {"kind": "unstamped"}}


def test_the_accept_playbook_stamps_every_run_and_verdict_it_writes():
    """The accept trio's ledger writes are playbook code the agent runs: each create carries the stamp."""
    text = (ROOT / "skills" / "qe" / "refs" / "accept.md").read_text(encoding="utf-8")
    creates = [i for i in range(len(text)) if text.startswith("store.create('runs'", i)
               or text.startswith("store.create('verdicts'", i)]
    assert len(creates) == 2, creates
    for i in creates:
        block = text[i:text.index("});", i)]
        assert "...CREW_RUN" in block, block
    assert "const CREW_RUN = process.env.WICKED_RUN_ID ? { crew_run_id: process.env.WICKED_RUN_ID } : {};" in text
