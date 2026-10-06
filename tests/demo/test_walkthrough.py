"""Walkthrough record tool tests (WT-G2, DES-walkthrough-proof §4.4-4.7).

Tests run against the fixture app under tests/demo/fixtures/ via a throwaway git repo
so every run gets a fresh, deterministic WICKED_TREE. wicked-ledger is installed into
a session-scoped tmp dir with npm --ignore-scripts and NODE_PATH is set for the tests
that validate manifest 2.1 with scenario_evidence.walkthrough.

Tests that need Playwright + ffmpeg are skipped without them (needs_recorder).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DEMO = ROOT / "scripts" / "demo"
FIXTURES = Path(__file__).parent / "fixtures"
WALKTHROUGH = SCRIPTS_DEMO / "walkthrough.mjs"
RUNNER_PKG = ROOT / "scripts" / "qe" / "runner" / "package.json"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _deps_installed() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import { DEPS_DIR } from './_playwright.mjs'; console.log(DEPS_DIR);"],
        cwd=SCRIPTS_DEMO, capture_output=True, text=True, timeout=30,
    )
    return out.returncode == 0 and (Path(out.stdout.strip()) / "node_modules" / "playwright").is_dir()


needs_recorder = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not _deps_installed(),
    reason="needs ffmpeg and the demo deps (wicked-garden run scripts/demo/setup.mjs)",
)

needs_vault = pytest.mark.skipif(
    shutil.which("wicked-vault") is None,
    reason="wicked-vault not installed (vault cross-check required for PASS/FAIL verdicts)",
)


def _ledger_version() -> str:
    try:
        pkg = json.loads(RUNNER_PKG.read_text())
        ver = pkg["dependencies"]["wicked-ledger"].lstrip("^~")
        return ver
    except Exception:
        return "0.4.0"


# ---- session-scoped ledger install -------------------------------------------

@pytest.fixture(scope="session")
def session_ledger(tmp_path_factory):
    """Install wicked-ledger once for the session; return NODE_PATH value (or skip)."""
    if shutil.which("npm") is None:
        pytest.skip("npm not installed")
    ledger_dir = tmp_path_factory.mktemp("ledger_modules", numbered=False)
    ver = _ledger_version()
    r = subprocess.run(
        ["npm", "install", "--prefix", str(ledger_dir), "--ignore-scripts",
         f"wicked-ledger@{ver}"],
        capture_output=True, text=True, timeout=180,
    )
    if r.returncode != 0:
        pytest.skip(f"npm install wicked-ledger failed: {r.stderr[-500:]}")
    node_modules = ledger_dir / "node_modules"
    existing = os.environ.get("NODE_PATH", "")
    return str(node_modules) + (os.pathsep + existing if existing else "")


# ---- git repo helpers ---------------------------------------------------------

def _make_tree(tmp: Path) -> tuple[Path, str]:
    """Create a throwaway git repo containing the fixture app and return (repo, tree SHA)."""
    repo = tmp / "repo"
    repo.mkdir()
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, env=env)
    for name in ("app.mjs", "probe.mjs"):
        shutil.copy(FIXTURES / name, repo / name)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True, env=env)
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         capture_output=True, text=True, check=True, env=env)
    return repo, out.stdout.strip()


def _wt_env(root: Path, tree: str, repo: Path,
             run_id: str = "run-1", step_id: str = "step-1", **extra) -> dict:
    return {
        **os.environ,
        "WICKED_EVIDENCE_ROOT": str(root),
        "WICKED_RUN_ID": run_id,
        "WICKED_RUN_UNIT": step_id,
        "WICKED_TREE": tree,
        "WICKED_WALKTHROUGH_JAIL": "1",
        "GIT_DIR": str(repo / ".git"),
        "GIT_WORK_TREE": str(repo),
        **extra,
    }


def _run_wt(argv: list[str], env: dict, cwd: Path | None = None,
            timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(WALKTHROUGH), *argv],
        capture_output=True, text=True, timeout=timeout,
        env=env, cwd=cwd or ROOT,
    )


def _make_minimal_storyline(repo: Path, tree: str,
                             port_placeholder: str = "${PORT}") -> Path:
    """Write a storyline.mjs into repo that uses the fixture app.mjs."""
    probe_path = str(repo / "probe.mjs").replace("\\", "/")
    sl = repo / "storyline.mjs"
    sl.write_text(
        f"""export default {{
  title: "Test Story",
  fixture: {{
    start: ["node", "app.mjs"],
    ready: "/ready",
    probes: {{
      check_run: ["node", "{probe_path}"],
    }},
  }},
  segments: [
    {{
      key: "01-chapter",
      title: "Chapter One",
      proves: ["p1"],
      checks: [
        {{ id: "guard_check", kind: "guard" }},
      ],
      async run(ctx) {{
        await ctx.hold(200);
        await ctx.check("guard_check");
      }},
    }},
  ],
}};
"""
    )
    return sl


def _make_two_chapter_storyline(repo: Path) -> Path:
    """Storyline whose first chapter is vault-verified PASS and second is vault-verified FAIL.

    01-passes carries a plain guard check (no foreign writes, no console errors) so the real
    vault's jq_pred verifier accepts it. 02-fails carries a guard check with an explicit
    `verify.params.expr = "false"`, so the real vault rejects it.
    """
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Ledger A/B Story",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    {
      key: "01-passes",
      title: "Chapter Passes",
      proves: ["p1"],
      checks: [{ id: "clean_guard", kind: "guard" }],
      async run(ctx) {
        await ctx.hold(200);
        await ctx.check("clean_guard");
      },
    },
    {
      key: "02-fails",
      title: "Chapter Fails",
      proves: ["p2"],
      checks: [{
        id: "false_guard",
        kind: "guard",
        verify: { kind: "jq_pred", params: { expr: "false" } },
      }],
      async run(ctx) {
        await ctx.hold(200);
        await ctx.check("false_guard");
      },
    },
  ],
};
""")
    return sl


# ---- helper: check seal in stdout -----------------------------------------------

def _parse_seal(stdout: str) -> dict:
    for line in stdout.splitlines():
        if line.startswith("WALKTHROUGH-SEAL "):
            return json.loads(line[len("WALKTHROUGH-SEAL "):])
    return {}


# ---- tests: no recorder needed ---------------------------------------------------

@needs_node
def test_missing_evidence_root_exits_nonzero(tmp_path):
    """WICKED_EVIDENCE_ROOT absent → exit non-zero, write nothing."""
    env = {**os.environ, "WICKED_WALKTHROUGH_JAIL": "1",
           "WICKED_RUN_ID": "r", "WICKED_RUN_UNIT": "s", "WICKED_TREE": "abc"}
    env.pop("WICKED_EVIDENCE_ROOT", None)
    out = _run_wt(["record"], env)
    assert out.returncode != 0, "should exit non-zero when WICKED_EVIDENCE_ROOT is unset"
    # Nothing written to a temp dir (there's no known path to write to)


@needs_node
def test_unjailed_writes_inconclusive_and_exits_0(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    env = {
        **os.environ,
        "WICKED_EVIDENCE_ROOT": str(root),
        "WICKED_RUN_ID": "run-1",
        "WICKED_RUN_UNIT": "step-1",
        "WICKED_TREE": "abc123",
    }
    env.pop("WICKED_WALKTHROUGH_JAIL", None)
    out = _run_wt(["record"], env)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE"
    assert result["cause"] == "unjailed_host"
    seal = _parse_seal(out.stdout)
    assert seal["overall"] == "INCONCLUSIVE"
    assert "bundle_sha" in seal


@needs_node
def test_unjailed_host_lists_all_storyline_chapters(tmp_path):
    """unjailed_host global cause must list every non-intro segment as INCONCLUSIVE."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Test",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "01-a", title: "A", proves: [], checks: [], async run(ctx) {} },
    { key: "02-b", title: "B", proves: [], checks: [], async run(ctx) {} },
  ],
};
""")
    env = {
        **os.environ,
        "WICKED_EVIDENCE_ROOT": str(root),
        "WICKED_RUN_ID": "run-1",
        "WICKED_RUN_UNIT": "step-1",
        "WICKED_TREE": tree,
        "GIT_DIR": str(repo / ".git"),
        "GIT_WORK_TREE": str(repo),
    }
    env.pop("WICKED_WALKTHROUGH_JAIL", None)
    out = _run_wt(["record", "--storyline", str(sl)], env)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["cause"] == "unjailed_host"
    keys = [c["key"] for c in result.get("chapters", [])]
    assert "01-a" in keys and "02-b" in keys, f"missing chapters in unjailed_host: {result}"
    for ch in result["chapters"]:
        assert ch["verdict"] == "INCONCLUSIVE"
    seal = _parse_seal(out.stdout)
    assert len(seal.get("chapters", [])) == 2, f"seal chapters wrong: {seal}"


@needs_node
def test_seal_action_outputs_bundle_sha(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "result.json").write_text('{"overall":"PASS"}')
    out = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout.strip())
    assert "bundle_sha" in data
    assert len(data["bundle_sha"]) == 64


@needs_node
def test_seal_recomputes_and_changes_when_any_file_changes(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    (root / "result.json").write_text('{"overall":"PASS"}')

    out1 = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert out1.returncode == 0, out1.stderr
    sha1 = json.loads(out1.stdout.strip())["bundle_sha"]

    (root / "extra.json").write_text('{"added":true}')

    out2 = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert out2.returncode == 0, out2.stderr
    sha2 = json.loads(out2.stdout.strip())["bundle_sha"]

    assert sha1 != sha2, "bundle_sha did not change after adding a file under root"


@needs_node
def test_seal_excludes_app_and_data_dirs(tmp_path):
    root = tmp_path / "evidence"
    (root / "app" / "src").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "result.json").write_text('{"overall":"PASS"}')

    out1 = _run_wt(["seal", "--root", str(root)], {**os.environ})
    sha1 = json.loads(out1.stdout.strip())["bundle_sha"]

    (root / "app" / "src" / "large_file.bin").write_bytes(b"\x00" * 1024)
    (root / "data" / "db.sqlite").write_bytes(b"\xff" * 512)

    out2 = _run_wt(["seal", "--root", str(root)], {**os.environ})
    sha2 = json.loads(out2.stdout.strip())["bundle_sha"]

    assert sha1 == sha2, "bundle_sha changed after adding files to app/ or data/"


@needs_node
def test_missing_env_vars_exit_nonzero(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    env = {**os.environ, "WICKED_WALKTHROUGH_JAIL": "1",
           "WICKED_EVIDENCE_ROOT": str(root)}
    for var in ("WICKED_RUN_ID", "WICKED_RUN_UNIT", "WICKED_TREE"):
        env.pop(var, None)
    out = _run_wt(["record"], env)
    assert out.returncode == 2, out.stdout + out.stderr


@needs_node
def test_storyline_refused_when_file_not_found(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(tmp_path / "nonexistent_storyline.mjs")], env)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE"
    assert result["cause"] == "storyline_refused"


@needs_node
def test_storyline_import_error_lists_all_chapters(tmp_path):
    """storyline_refused (import error) must list every segment from the file as INCONCLUSIVE."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    # A valid-looking file with segment keys but a syntax error so import() throws
    sl = repo / "bad_storyline.mjs"
    sl.write_text("""export default {
  title: "Bad",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "01-x", title: "X", proves: [], checks: [], async run(ctx) {} },
    { key: "02-y", title: "Y", proves: [], checks: [], async run(ctx) {} },
  ],
  __SYNTAX_ERROR__  // force import failure
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["cause"] == "storyline_refused"
    keys = [c["key"] for c in result.get("chapters", [])]
    assert "01-x" in keys and "02-y" in keys, f"missing chapters in storyline_refused: {result}"
    for ch in result["chapters"]:
        assert ch["verdict"] == "INCONCLUSIVE"


@needs_node
def test_contract_json_written_for_each_chapter(tmp_path):
    """Vault contract.json is written per chapter with canonical {kind, params.expr} verifier."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    contract = root / "vault" / "01-chapter" / "contract.json"
    assert contract.exists(), f"contract.json not written; exit={out.returncode} stderr={out.stderr[-500:]}"
    data = json.loads(contract.read_text())
    assert "required_evidence" in data
    re0 = data["required_evidence"][0]
    assert re0["claim_id"] == "guard_check"
    assert re0["required"] is True
    # Verifier must be canonical {kind, params} not a plain string
    assert isinstance(re0["verifier"], dict), f"verifier must be object, got {re0['verifier']!r}"
    assert re0["verifier"].get("kind") == "jq_pred", f"verifier kind must be jq_pred, got {re0['verifier']}"
    params = re0["verifier"].get("params", {})
    assert "expr" in params, f"verifier params must use 'expr' key (not 'pred'), got {params}"
    assert "pred" not in params, f"verifier params must NOT have 'pred' key, got {params}"
    assert isinstance(params["expr"], str) and params["expr"], "verifier params.expr must be a non-empty string"


@needs_node
def test_walkthrough_seal_line_printed_to_stdout(tmp_path):
    """WALKTHROUGH-SEAL line carries tree, storyline_sha, contract_shas, bundle_sha, overall, chapters."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    seal = _parse_seal(out.stdout)
    assert seal, f"no WALKTHROUGH-SEAL in stdout; stderr={out.stderr[-500:]}"
    assert seal["tree"] == tree
    assert "bundle_sha" in seal
    assert "chapters" in seal
    # storyline_sha: sha256 of the storyline file (64-char hex)
    assert isinstance(seal.get("storyline_sha"), str) and len(seal["storyline_sha"]) == 64, (
        f"storyline_sha must be a 64-char hex string, got {seal.get('storyline_sha')!r}"
    )
    # contract_shas: dict mapping chapter key → sha256 of its contract.json
    assert isinstance(seal.get("contract_shas"), dict), (
        f"contract_shas must be a dict, got {seal.get('contract_shas')!r}"
    )
    assert "01-chapter" in seal["contract_shas"], (
        f"contract_shas missing '01-chapter' key: {seal['contract_shas']}"
    )
    # every value is the real sha256 of that chapter's contract file, not a placeholder
    for key, sha in seal["contract_shas"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", sha or ""), f"contract_shas[{key!r}] is not a sha256: {sha!r}"
        contract_file = root / "vault" / key / "contract.json"
        assert contract_file.is_file(), f"no contract file for {key!r} at {contract_file}"
        assert sha == hashlib.sha256(contract_file.read_bytes()).hexdigest(), (
            f"contract_shas[{key!r}] does not match the sha256 of {contract_file}"
        )
    # storyline_sha is the sha256 of the copy under <root>
    assert seal["storyline_sha"] == hashlib.sha256((root / "storyline.mjs").read_bytes()).hexdigest()
    # overall: one of the three verdict strings
    assert seal.get("overall") in ("PASS", "FAIL", "INCONCLUSIVE"), (
        f"overall must be PASS/FAIL/INCONCLUSIVE, got {seal.get('overall')!r}"
    )


@needs_node
def test_global_inconclusive_cause_lists_every_chapter(tmp_path):
    """fixture_unavailable → every chapter listed as INCONCLUSIVE (global-cause invariant)."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Test",
  fixture: {{ start: ["node", "-e", "process.exit(1)"], ready: "/ready" }},
  segments: [
    {{ key: "01-a", title: "A", proves: [], checks: [], async run(ctx) {{}} }},
    {{ key: "02-b", title: "B", proves: [], checks: [], async run(ctx) {{}} }},
  ],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE"
    assert result.get("cause") == "fixture_unavailable", (
        f"expected cause=fixture_unavailable (node -e exit(1) fixture), got {result}"
    )
    # Both chapters must be listed and ALL must be INCONCLUSIVE
    keys = {c["key"] for c in result.get("chapters", [])}
    assert "01-a" in keys and "02-b" in keys, f"not all chapters listed: {result}"
    for ch in result["chapters"]:
        assert ch["verdict"] == "INCONCLUSIVE", f"chapter {ch['key']} should be INCONCLUSIVE: {ch}"
    # Seal line must include all chapters (never empty for a global cause)
    seal = _parse_seal(out.stdout)
    assert len(seal.get("chapters", [])) == 2, f"seal chapters empty or partial: {seal}"
    for ch in seal.get("chapters", []):
        assert ch["verdict"] == "INCONCLUSIVE", f"seal chapter {ch['key']} should be INCONCLUSIVE: {ch}"


@needs_node
def test_vault_verifier_error_causes_inconclusive(tmp_path):
    """verifier_status=error from vault cross-check (e.g. jq missing) → chapter INCONCLUSIVE."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)

    # Fake vault binary: declare-contract/record succeed, cross-check exits non-zero with ERROR JSON.
    # The binary receives --cwd <dir> before the command name, so we skip flag pairs.
    fake_vault = tmp_path / "fake-vault.mjs"
    fake_vault.write_text("""#!/usr/bin/env node
const args = process.argv.slice(2);
let cmd = null;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--cwd') { i++; continue; }
  if (!args[i].startsWith('-')) { cmd = args[i]; break; }
}
if (cmd === 'record') {
  process.stdout.write(JSON.stringify({id: "fake-err-1"}) + "\\n");
  process.exit(0);
}
if (cmd === 'cross-check') {
  process.stdout.write(JSON.stringify({
    overall: "ERROR",
    claims: [{ claim_id: "guard_check", verifier_status: "error" }]
  }) + "\\n");
  process.exit(1);
}
process.exit(0);
""")
    fake_vault.chmod(0o755)

    env = _wt_env(root, tree, repo, WICKED_VAULT_BIN=str(fake_vault))
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "INCONCLUSIVE", (
        f"verifier_status=error should produce INCONCLUSIVE, got {chapters}"
    )
    # crew's `checks[].passed` is null (not false) for an inconclusive check, and `detail` says why.
    (check,) = next(c for c in result["chapters"] if c["key"] == "01-chapter")["checks"]
    assert check["passed"] is None
    assert check["detail"] == "vault cross-check returned ERROR"


@needs_node
def test_artifact_path_escape_refuses_absolute_path(tmp_path):
    """Collector refuses artifact paths that escape DATA_DIR."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "bad_art", kind: "artifact", path: "/etc/passwd" }}],
    async run(ctx) {{ await ctx.check("bad_art"); }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    if (root / "result.json").exists():
        result = json.loads((root / "result.json").read_text())
        assert result["overall"] in ("INCONCLUSIVE", "FAIL"), result


@needs_node
def test_artifact_path_escape_refuses_dotdot(tmp_path):
    """Collector refuses artifact paths with ../ traversal."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "esc_art", kind: "artifact", path: "../secret.txt" }}],
    async run(ctx) {{ await ctx.check("esc_art"); }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    if (root / "result.json").exists():
        result = json.loads((root / "result.json").read_text())
        assert result["overall"] in ("INCONCLUSIVE", "FAIL"), result


@needs_node
def test_disk_cap_causes_inconclusive(tmp_path):
    """WICKED_WALKTHROUGH_DISK_CAP=1 → ALL chapters INCONCLUSIVE with cause disk_cap (global-cause invariant).
    Uses 2 chapters to verify both are INCONCLUSIVE even if one was already judged before the cap hit."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    # Two-chapter storyline: with cap=1 byte the cap is hit immediately, so both chapters
    # must be listed as INCONCLUSIVE from the global-cause helper.
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Disk Cap Test",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    {
      key: "01-a", title: "Chapter A", proves: [],
      checks: [{ id: "guard_a", kind: "guard" }],
      async run(ctx) { await ctx.hold(100); await ctx.check("guard_a"); },
    },
    {
      key: "02-b", title: "Chapter B", proves: [],
      checks: [{ id: "guard_b", kind: "guard" }],
      async run(ctx) { await ctx.hold(100); await ctx.check("guard_b"); },
    },
  ],
};
""")
    env = _wt_env(root, tree, repo, WICKED_WALKTHROUGH_DISK_CAP="1")
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE", result
    assert result.get("cause") == "disk_cap", result
    keys = {c["key"] for c in result.get("chapters", [])}
    assert "01-a" in keys and "02-b" in keys, f"not all chapters listed: {result}"
    for ch in result["chapters"]:
        assert ch["verdict"] == "INCONCLUSIVE", f"chapter {ch['key']} should be INCONCLUSIVE: {ch}"


# ---- tests: ledger + manifest (needs npm for wicked-ledger) ----------------------

@needs_recorder
@needs_vault
def test_manifest_21_validates_with_real_walkthrough_output(tmp_path, session_ledger):
    """Per-chapter manifests produced by walkthrough validate as wicked-ledger 2.1.0."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=90)
    assert out.returncode == 0, out.stderr

    # Find manifests produced by the tool
    manifests = list((root / "vault").rglob("manifest.json")) if (root / "vault").exists() else []
    assert manifests, (
        f"no manifests written — walkthrough must produce per-chapter manifests when wicked-ledger is available; "
        f"exit={out.returncode} stderr={out.stderr[-500:]}"
    )

    # Validate each manifest via node — write to a tmp file to avoid arg-passing issues
    for mf in manifests:
        check_script = f"""
import {{ createRequire }} from 'node:module';
import {{ readFileSync }} from 'node:fs';
const req = createRequire(import.meta.url);
const {{ validateManifest }} = req('wicked-ledger');
const m = JSON.parse(readFileSync({json.dumps(str(mf))}, 'utf8'));
const result = validateManifest(m);
if (!result.ok) {{
  console.error('validation failed:', JSON.stringify(result.violations));
  process.exit(1);
}}
if (!m.scenario_evidence || !m.scenario_evidence.walkthrough) {{
  console.error('missing scenario_evidence.walkthrough');
  process.exit(1);
}}
console.log('ok');
"""
        out2 = subprocess.run(
            ["node", "--input-type=module", "-e", check_script],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "NODE_PATH": session_ledger},
        )
        assert out2.returncode == 0, (
            f"manifest {mf} failed 2.1 validation: {out2.stderr}"
        )
        assert "ok" in out2.stdout

    # Assert scenario_evidence.walkthrough contract fields (not just schema presence)
    for mf in manifests:
        m = json.loads(mf.read_text())
        wt = m["scenario_evidence"]["walkthrough"]
        # proves[] is exactly the segment's plan step ids
        assert wt.get("proves") == ["p1"], (
            f"scenario_evidence.walkthrough.proves must equal the segment's proves ['p1'], got {wt.get('proves')!r}"
        )
        # failed_at_sec must be present (null when no failure, a number when failed)
        assert "failed_at_sec" in wt, "scenario_evidence.walkthrough must have failed_at_sec"
        assert wt["failed_at_sec"] is None or isinstance(wt["failed_at_sec"], (int, float)), (
            f"failed_at_sec must be null or a number, got {wt['failed_at_sec']!r}"
        )
        # checks[] must be a list; each item has id, kind, at_sec, evidence, vault_entry
        assert isinstance(wt.get("checks"), list), (
            f"scenario_evidence.walkthrough.checks must be a list, got {wt.get('checks')!r}"
        )
        for ch in wt["checks"]:
            for field in ("id", "kind", "at_sec", "evidence", "vault_entry"):
                assert field in ch, (
                    f"checks[] item missing '{field}': {ch}"
                )
            # the recorder ran, so every reached check has a timeline-clock instant
            assert isinstance(ch["at_sec"], (int, float)) and ch["at_sec"] >= 0, (
                f"checks[].at_sec must be a non-negative number from the recorder timeline, got {ch['at_sec']!r}"
            )
            assert isinstance(ch["evidence"], list) and ch["evidence"], (
                f"checks[].evidence must be a non-empty list, got {ch['evidence']!r}"
            )
            # the real vault recorded the claim, so the entry id is present
            assert ch["vault_entry"], f"checks[].vault_entry must be set when the vault recorded the claim: {ch}"


@needs_recorder
@needs_vault
def test_ledger_rows_carry_crew_run_id_step_id_tree_take(tmp_path, session_ledger):
    """Ledger rows written by walkthrough carry crew_run_id, step_id, tree, take."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    run_id, step_id = "run-ledger-1", "step-a"
    env = _wt_env(root, tree, repo, run_id=run_id, step_id=step_id,
                  NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=90)
    assert out.returncode == 0, out.stderr

    runs_dir = root / ".wicked-qe" / "runs"
    if not runs_dir.exists():
        pytest.fail(
            f"ledger not written — .wicked-qe/runs/ missing; "
            f"exit={out.returncode} stderr={out.stderr[-500:]}"
        )

    run_files = list(runs_dir.glob("*.json"))
    assert run_files, "no run JSON files written under .wicked-qe/runs/"
    run = json.loads(run_files[0].read_text())
    missing = []
    if not run.get("crew_run_id"): missing.append("crew_run_id")
    if not run.get("step_id"): missing.append("step_id")
    if not run.get("tree"): missing.append("tree")
    if not isinstance(run.get("take"), (int, float)): missing.append("take")
    assert not missing, f"missing fields in ledger run row: {missing}; row={run}"
    assert run["crew_run_id"] == run_id, f"wrong crew_run_id: {run['crew_run_id']}"
    assert run["step_id"] == step_id, f"wrong step_id: {run['step_id']}"
    assert run["tree"] == tree, f"wrong tree: {run['tree']}"


# ---- tests: verdicts and chapter outcomes ----------------------------------------

@needs_recorder
@needs_vault
def test_overall_verdict_is_fail_when_any_chapter_fails(tmp_path):
    """Real vault FAIL claim (locator for absent element) → chapter FAIL → overall FAIL."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Fail Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "loc_absent", kind: "locator", selector: "#never-exists-xyz" }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("loc_absent");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)

    if not (root / "result.json").exists():
        pytest.fail(f"result.json not written; exit={out.returncode} stderr={out.stderr[-500:]}")

    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "FAIL", (
        f"locator for absent element should FAIL via real vault, got {chapters}"
    )
    assert result["overall"] == "FAIL", (
        f"overall={result['overall']} despite FAIL chapter: {chapters}"
    )


@needs_recorder
@needs_vault
def test_never_reached_check_is_fail(tmp_path):
    """A declared check that seg.run() never calls → chapter FAIL (not INCONCLUSIVE)."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    # Guard check declared but never called
    sl.write_text(f"""export default {{
  title: "Never-reached",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "skipped_check", kind: "guard" }}],
    async run(ctx) {{
      await ctx.hold(100);
      // deliberately NOT calling ctx.check("skipped_check")
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert "01-chapter" in chapters, f"chapter missing from result: {result}"
    assert chapters["01-chapter"] == "FAIL", (
        f"never-reached check should produce FAIL, got {chapters['01-chapter']}"
    )
    assert result["overall"] == "FAIL"


@needs_recorder
@needs_vault
def test_guard_passes_when_no_foreign_writes_no_console_errors(tmp_path, session_ledger):
    """Guard check PASS when foreign_writes and console_errors are both empty."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    # guard passes when no writes or errors: chapter should be PASS
    assert chapters.get("01-chapter") == "PASS", (
        f"guard check should PASS, got {chapters}"
    )


@needs_recorder
@needs_vault
def test_guard_fails_when_foreign_write_detected(tmp_path):
    """Guard check FAIL when a foreign POST is attempted from the page and intercepted."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    # Trigger a POST to a non-fixture origin from the stage page.
    # armGuard intercepts all mutating requests to non-writable origins at the
    # browser-context level (not just the app iframe), so this is caught
    # synchronously via Playwright route interception.
    sl.write_text(f"""export default {{
  title: "Guard Fail Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "guard_block", kind: "guard" }}],
    async run(ctx) {{
      // POST to a non-fixture origin — armGuard intercepts and records as foreign_write
      await ctx.page.evaluate(() =>
        fetch('http://blocked-external.invalid/', {{ method: 'POST', signal: AbortSignal.timeout(50) }})
          .catch(() => {{}})
      );
      await ctx.hold(150);
      await ctx.check("guard_block");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    # foreign write intercepted → guard fails → chapter must be exactly FAIL
    assert chapters.get("01-chapter") == "FAIL", (
        f"guard should be exactly FAIL with intercepted foreign POST, got {chapters}"
    )
    # The capture file must exist since ctx.check ran
    claims_dir = root / "vault" / "01-chapter" / "claims"
    assert (claims_dir / "guard_block.json").exists(), "guard capture file not written"
    cap = json.loads((claims_dir / "guard_block.json").read_text())
    assert len(cap.get("foreign_writes", [])) > 0, (
        f"guard capture should have foreign_writes, got {cap}"
    )


@needs_recorder
@needs_vault
def test_probe_check_passes_on_exit_code_zero(tmp_path, session_ledger):
    """Probe check PASS when probe exits with code 0."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    probe_path = str(repo / "probe.mjs").replace("\\", "/")
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Probe Test",
  fixture: {{
    start: ["node", "app.mjs"],
    ready: "/ready",
    probes: {{ health: ["node", "{probe_path}"] }},
  }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "probe_check", kind: "probe", name: "health" }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("probe_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "PASS", (
        f"probe with exit_code=0 should PASS, got {chapters}"
    )
    # Verify capture file was written (recorder ran, so claims dir must exist)
    claims_dir = root / "vault" / "01-chapter" / "claims"
    capture_file = claims_dir / "probe_check.json"
    assert capture_file.exists(), "probe capture file not written"
    cap = json.loads(capture_file.read_text())
    assert cap["raw"]["exit_code"] == 0


@needs_recorder
@needs_vault
def test_artifact_check_passes_when_file_exists(tmp_path, session_ledger):
    """Artifact check PASS when the file exists under DATA_DIR."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    # POST /api/run writes DATA_DIR/run.json, then check it
    sl.write_text(f"""export default {{
  title: "Artifact Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "art_check", kind: "artifact", path: "run.json" }}],
    async run(ctx) {{
      // ctx.app is the frameLocator for the app iframe
      await ctx.app.locator('#go').click();
      await ctx.hold(400);
      await ctx.check("art_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "PASS", (
        f"artifact check should PASS when file exists, got {chapters}"
    )


@needs_recorder
@needs_vault
def test_join_check_passes_when_sources_present(tmp_path, session_ledger):
    """Join check PASS when all source IDs have values."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    probe_path = str(repo / "probe.mjs").replace("\\", "/")
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Join Test",
  fixture: {{
    start: ["node", "app.mjs"],
    ready: "/ready",
    probes: {{ health: ["node", "{probe_path}"] }},
  }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [
      {{ id: "probe_src", kind: "probe", name: "health" }},
      {{ id: "join_check", kind: "join", sources: ["probe_src"] }},
    ],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("probe_src");
      await ctx.check("join_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "PASS", (
        f"join check should PASS when source has value, got {chapters}"
    )


@needs_recorder
@needs_vault
def test_locator_check_fails_for_absent_element(tmp_path):
    """Locator check FAIL when the selector matches nothing."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Locator Fail Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "loc_check", kind: "locator", selector: "#never-exists-xyz" }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("loc_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "FAIL", (
        f"locator for absent element should FAIL, got {chapters}"
    )


@needs_recorder
@needs_vault
@pytest.mark.skipif(shutil.which("sqlite3") is None, reason="needs sqlite3")
def test_probe_sqlite_json_parse(tmp_path, session_ledger):
    """Probe with parse=sqlite-json parses sqlite3 JSON output correctly → PASS when sqlite3 present."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    # Use sqlite3 to query a trivial in-memory database; verify with params.expr (canonical)
    sl.write_text(f"""export default {{
  title: "SQLite Probe Test",
  fixture: {{
    start: ["node", "app.mjs"],
    ready: "/ready",
    probes: {{
      sqlite_probe: ["sqlite3", ":memory:", "-json", "SELECT 1 as val"],
    }},
  }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{
      id: "sqlite_check",
      kind: "probe",
      name: "sqlite_probe",
      parse: "sqlite-json",
      verify: {{ kind: "jq_pred", params: {{ expr: ".parsed[0].val == 1" }} }},
    }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("sqlite_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    # sqlite3 is present (skip guard above) and recorder ran → probe exit_code=0 → PASS
    assert chapters.get("01-chapter") == "PASS", (
        f"sqlite-json probe with sqlite3 present should PASS, got {chapters}"
    )


@needs_recorder
@needs_vault
def test_fail_chapter_manifest_validates_as_21(tmp_path, session_ledger):
    """A FAIL chapter's manifest still validates as wicked-ledger 2.1.0."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "FAIL Manifest Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "loc_fail", kind: "locator", selector: "#absent-xyz" }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("loc_fail");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr

    manifests = list((root / "vault").rglob("manifest.json")) if (root / "vault").exists() else []
    assert manifests, (
        f"no manifests written — walkthrough must produce per-chapter manifests when wicked-ledger is available; "
        f"exit={out.returncode} stderr={out.stderr[-500:]}"
    )

    for mf in manifests:
        mdata = json.loads(mf.read_text())
        if mdata.get("status") == "failed":
            check_script = f"""
import {{ createRequire }} from 'node:module';
import {{ readFileSync }} from 'node:fs';
const req = createRequire(import.meta.url);
const {{ validateManifest }} = req('wicked-ledger');
const m = JSON.parse(readFileSync({json.dumps(str(mf))}, 'utf8'));
const result = validateManifest(m);
if (!result.ok) {{
  console.error('FAIL manifest failed validation:', JSON.stringify(result.violations));
  process.exit(1);
}}
console.log('ok');
"""
            out2 = subprocess.run(
                ["node", "--input-type=module", "-e", check_script],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "NODE_PATH": session_ledger},
            )
            assert out2.returncode == 0, f"FAIL manifest rejected by validator: {out2.stderr}"
            assert "ok" in out2.stdout
            return  # found and validated a FAIL manifest

    pytest.fail(
        "no FAIL status manifest found to validate — the storyline uses an absent selector "
        "so at least one chapter should be FAIL and produce a FAIL manifest"
    )


@needs_node
def test_progress_json_exists_and_agrees_with_result_json(tmp_path):
    """progress.json must exist after any run and its overall/chapters must match result.json."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr

    assert (root / "result.json").exists(), "result.json not written"
    assert (root / "progress.json").exists(), "progress.json not written"

    result = json.loads((root / "result.json").read_text())
    progress = json.loads((root / "progress.json").read_text())

    assert progress["overall"] == result["overall"], (
        f"progress.overall={progress['overall']} != result.overall={result['overall']}"
    )
    result_keys = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    progress_keys = {c["key"]: c["verdict"] for c in progress.get("chapters", [])}
    assert result_keys == progress_keys, (
        f"progress chapters differ from result chapters:\nprogress={progress_keys}\nresult={result_keys}"
    )


@needs_recorder
@needs_vault
def test_console_error_before_first_check_makes_guard_fail(tmp_path):
    """A console.error emitted before ctx.check() fills consoleErrors → guard FAIL."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Console Error Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "guard_check", kind: "guard" }}],
    async run(ctx) {{
      // Emit a console.error before the guard check runs
      await ctx.page.evaluate(() => console.error("intentional test error"));
      await ctx.hold(100);
      await ctx.check("guard_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "FAIL", (
        f"console.error before guard check should produce FAIL, got {chapters}"
    )
    # Capture must record the error
    claims_dir = root / "vault" / "01-chapter" / "claims"
    cap = json.loads((claims_dir / "guard_check.json").read_text())
    assert len(cap.get("console_errors", [])) > 0, (
        f"guard capture should record the console.error, got {cap}"
    )


@needs_node
def test_repo_not_modified_by_walkthrough_run(tmp_path):
    """Walkthrough must not write any files into the garden repo (e.g. no vault leak).

    The garden repo has a tracked .wicked-vault/; without an anchor in <evidence>/vault/
    the vault CLI would resolve to that repo vault and write entries there.
    This test asserts git status is identical before and after, proving the anchor works.
    """
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)

    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout

    env = _wt_env(root, tree, repo)
    _run_wt(["record", "--storyline", str(sl)], env, timeout=60)

    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout

    assert before == after, (
        f"walkthrough run modified the garden repo.\n"
        f"Before:\n{before}\nAfter:\n{after}"
    )


@needs_node
def test_vault_entries_land_in_evidence_root_not_ancestor(tmp_path):
    """When WICKED_EVIDENCE_ROOT is inside a dir that has an ancestor .wicked-vault,
    entries must land in <root>/vault/.wicked-vault, not the ancestor vault.
    The ancestor vault.json must be byte-identical before and after the run.
    """
    # Create an ancestor dir that has its own .wicked-vault anchor
    ancestor = tmp_path / "ancestor"
    ancestor_vault_dir = ancestor / ".wicked-vault"
    ancestor_vault_dir.mkdir(parents=True)
    ancestor_vault_json = ancestor_vault_dir / "vault.json"
    ancestor_vault_json.write_text(
        json.dumps({"schema_version": 1, "store_mode": "in-repo", "payload_max_bytes": 1048576}, indent=2) + "\n"
    )
    vault_before = ancestor_vault_json.read_bytes()

    # Place the evidence root INSIDE the ancestor so --cwd traversal would find it
    root = ancestor / "run" / "root"
    root.mkdir(parents=True)
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)

    # Disable vault CLI to avoid any actual recording; we're testing anchor creation only
    env = _wt_env(root, tree, repo, WICKED_VAULT_BIN="")
    _run_wt(["record", "--storyline", str(sl)], env, timeout=60)

    # Ancestor vault.json must be byte-identical
    vault_after = ancestor_vault_json.read_bytes()
    assert vault_before == vault_after, (
        "ancestor .wicked-vault/vault.json was modified — walkthrough wrote into the ancestor vault"
    )

    # Evidence vault anchor must have been created in <root>/vault/.wicked-vault/
    local_anchor = root / "vault" / ".wicked-vault" / "vault.json"
    assert local_anchor.exists(), (
        f"evidence vault anchor not created at {local_anchor} — ancestor traversal may have occurred"
    )


@needs_recorder
@needs_vault
def test_locator_check_passes_for_present_element(tmp_path, session_ledger):
    """Locator check PASS when the selector matches an existing element."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Locator Pass Test",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready" }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{{ id: "loc_check", kind: "locator", selector: "#status" }}],
    async run(ctx) {{
      await ctx.hold(100);
      await ctx.check("loc_check");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "PASS", (
        f"locator for #status (present element) should PASS, got {chapters}"
    )
    # Capture should record inner_text
    claims_dir = root / "vault" / "01-chapter" / "claims"
    cap = json.loads((claims_dir / "loc_check.json").read_text())
    assert cap.get("inner_text") is not None, (
        f"locator capture should have inner_text, got {cap}"
    )


@needs_node
def test_fixture_reuse_symlinks_directory(tmp_path):
    """fixture.reuse dirs are symlinked from the repo into <root>/app/ at record time."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)

    # Create a directory in the repo to be reused
    reuse_dir = repo / "shared_assets"
    reuse_dir.mkdir()
    (reuse_dir / "data.txt").write_text("shared")

    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Reuse Test",
  fixture: {{
    start: ["node", "app.mjs"],
    ready: "/ready",
    reuse: ["shared_assets"],
  }},
  segments: [{{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [],
    async run(ctx) {{}},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    # cwd=repo so process.cwd() in walkthrough resolves fixture.reuse paths against the repo dir
    _run_wt(["record", "--storyline", str(sl)], env, timeout=60, cwd=repo)

    # The symlink must exist at <root>/app/shared_assets
    symlink_path = root / "app" / "shared_assets"
    assert symlink_path.exists() or symlink_path.is_symlink(), (
        f"fixture.reuse dir 'shared_assets' not symlinked at {symlink_path}"
    )
    assert symlink_path.is_symlink(), (
        f"expected a symlink at {symlink_path}, got a regular dir"
    )


# ---- regressions: fail-closed proof machinery ------------------------------------

@needs_recorder
def test_vault_unavailable_chapter_is_inconclusive_never_pass(tmp_path):
    """With vault kill-switched, a chapter whose guard would pass locally is INCONCLUSIVE (fail closed).

    Regression for the deleted local-verifier fallback: vault unavailable must never produce PASS.
    """
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)  # guard check, no foreign writes → would PASS locally
    env = _wt_env(root, tree, repo, WICKED_VAULT_BIN="")  # kill-switch vault
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    for key, verdict in chapters.items():
        assert verdict != "PASS", (
            f"vault unavailable must never produce PASS for chapter {key!r}, got {verdict!r}"
        )
    assert result["overall"] != "PASS", (
        f"overall must not be PASS when vault is unavailable: {result}"
    )


@needs_recorder
@needs_vault
def test_false_custom_verify_expr_fails_via_real_vault(tmp_path):
    """Custom verify expr=false → FAIL via real vault's jq_pred evaluation, not local fallback."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "False Expr Test",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [{
    key: "01-chapter", title: "Chapter One", proves: [],
    checks: [{
      id: "always_false",
      kind: "guard",
      verify: { kind: "jq_pred", params: { expr: "false" } },
    }],
    async run(ctx) { await ctx.hold(100); await ctx.check("always_false"); },
  }],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "FAIL", (
        f"custom verify expr=false must produce FAIL via real vault, got {chapters}"
    )


@needs_recorder
def test_missing_jq_causes_inconclusive(tmp_path):
    """Real vault with jq absent from PATH → jq_pred evaluation ERROR → chapter INCONCLUSIVE."""
    vault_bin = shutil.which("wicked-vault")
    if vault_bin is None:
        pytest.skip("wicked-vault not installed")
    node_bin = shutil.which("node")
    if node_bin is None:
        pytest.skip("node not installed")
    jq_bin = shutil.which("jq")
    if jq_bin is None:
        pytest.skip("jq not installed (can't construct missing-jq PATH)")

    # Build tmp_bin with node and wicked-vault only (no jq).
    from pathlib import Path as _P
    tmp_bin = tmp_path / "bin"
    tmp_bin.mkdir()
    (tmp_bin / "node").symlink_to(_P(node_bin).resolve())
    (tmp_bin / "wicked-vault").symlink_to(_P(vault_bin).resolve())

    # Build a PATH that has tmp_bin first and excludes the directory containing jq.
    jq_dir = str(_P(jq_bin).parent.resolve())
    path_dirs = [str(tmp_bin)]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and str(_P(d).resolve()) != jq_dir:
            path_dirs.append(d)
    restricted_path = os.pathsep.join(path_dirs)

    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)  # guard check with jq_pred verifier

    env = _wt_env(root, tree, repo, WICKED_VAULT_BIN=str(tmp_bin / "wicked-vault"))
    env["PATH"] = restricted_path

    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result.get("chapters", [])}
    assert chapters.get("01-chapter") == "INCONCLUSIVE", (
        f"missing jq must cause vault ERROR → chapter INCONCLUSIVE, got {chapters}"
    )


@needs_recorder
@needs_vault
def test_ledger_unavailable_causes_inconclusive(tmp_path, session_ledger):
    """wicked-ledger unresolvable → the PASS chapter becomes INCONCLUSIVE, the FAIL chapter stays FAIL.

    Paired A/B against the SAME storyline so the only variable is the ledger:

      * control run (real wicked-ledger on NODE_PATH) — 01-passes is vault-verified PASS,
        02-fails is vault-verified FAIL;
      * blocked run (require('wicked-ledger') made to throw) — 01-passes must become
        INCONCLUSIVE, because "ledger absence must not silently pass"; 02-fails must STAY
        FAIL, because a vault-verified failure is already certain and does not need an audit.

    Asserting both directions makes the test regression-inert-proof: deleting the ledger
    fail-closed path turns 01-passes into PASS, and blanket-downgrading every chapter turns
    02-fails into INCONCLUSIVE. Either mutation fails this test.

    The blocker patches Module._resolveFilename via NODE_OPTIONS=--require, because the tool
    resolves the ledger with createRequire (CJS) from its own module URL — NODE_PATH alone
    would NOT shadow a node_modules dir above the script.
    """
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_two_chapter_storyline(repo)

    # ---- control: real ledger present, real vault available -------------------
    control_root = tmp_path / "control"
    control_root.mkdir()
    control_env = _wt_env(control_root, tree, repo, NODE_PATH=session_ledger)
    control_out = _run_wt(["record", "--storyline", str(sl)], control_env, timeout=120)
    assert control_out.returncode == 0, control_out.stderr
    control = {c["key"]: c["verdict"]
               for c in json.loads((control_root / "result.json").read_text())["chapters"]}
    assert control.get("01-passes") == "PASS", (
        f"control run must vault-verify 01-passes as PASS, got {control}"
    )
    assert control.get("02-fails") == "FAIL", (
        f"control run must vault-verify 02-fails as FAIL, got {control}"
    )

    # ---- blocked: require('wicked-ledger') throws, real vault still available --
    blocker = tmp_path / "block_ledger.cjs"
    blocker.write_text(
        'const Module = require("node:module");\n'
        'const orig = Module._resolveFilename;\n'
        'Module._resolveFilename = function (request, ...rest) {\n'
        '  if (request === "wicked-ledger" || request.startsWith("wicked-ledger/")) {\n'
        '    const e = new Error("Cannot find module \'wicked-ledger\'");\n'
        '    e.code = "MODULE_NOT_FOUND";\n'
        '    throw e;\n'
        '  }\n'
        '  return orig.call(this, request, ...rest);\n'
        '};\n'
    )
    env = _wt_env(root, tree, repo)
    env["NODE_PATH"] = str(tmp_path / "empty_modules")
    existing_node_options = env.get("NODE_OPTIONS", "")
    env["NODE_OPTIONS"] = "--require " + str(blocker) + (
        " " + existing_node_options if existing_node_options else "")

    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result["chapters"]}

    assert chapters.get("01-passes") == "INCONCLUSIVE", (
        "a vault-verified PASS chapter must become INCONCLUSIVE when wicked-ledger is "
        f"unresolvable — ledger absence must not silently pass. Got {chapters}"
    )
    assert chapters.get("02-fails") == "FAIL", (
        "a vault-verified FAIL is certain without a ledger and must NOT be blanket-downgraded "
        f"to INCONCLUSIVE. Got {chapters}"
    )
    assert result["overall"] == "FAIL", (
        f"overall must stay FAIL (FAIL dominates INCONCLUSIVE), got {result['overall']!r}"
    )


@needs_recorder
@needs_vault
def test_ledger_store_broken_downgrades_pass_to_inconclusive(tmp_path, session_ledger):
    """wicked-ledger resolves but its store cannot be written -> PASS becomes INCONCLUSIVE.

    The ledger root <root>/.wicked-qe is pre-created as a FILE, so createDomainStore (or the
    first row write) throws. The vault stays available, so 01-passes would otherwise be a
    vault-verified PASS and 02-fails a vault-verified FAIL. Without its ledger rows the PASS
    is not proven (fail closed); the FAIL stays FAIL.
    """
    repo, tree = _make_tree(tmp_path)
    sl = _make_two_chapter_storyline(repo)

    root = tmp_path / "evidence"
    root.mkdir()
    (root / ".wicked-qe").write_text("not a directory\n")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    chapters = {c["key"]: c["verdict"] for c in result["chapters"]}
    assert chapters.get("01-passes") == "INCONCLUSIVE", (
        f"a PASS whose ledger rows could not be written must be INCONCLUSIVE, got {chapters}"
    )
    assert chapters.get("02-fails") == "FAIL", f"a vault-verified FAIL stays FAIL, got {chapters}"
    assert result["overall"] == "FAIL", result


def _fake_vault(tmp_path: Path, record_exit: int, cross_check: dict, cross_exit: int) -> Path:
    """A fake wicked-vault CLI: declare-contract succeeds, record exits `record_exit`,
    cross-check prints `cross_check` and exits `cross_exit`."""
    fv = tmp_path / "fake-vault-2.mjs"
    fv.write_text("""#!/usr/bin/env node
const args = process.argv.slice(2);
let cmd = null;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--cwd') { i++; continue; }
  if (!args[i].startsWith('-')) { cmd = args[i]; break; }
}
if (cmd === 'record') {
  if (%d !== 0) process.exit(%d);
  process.stdout.write(JSON.stringify({id: "fake-1"}) + "\\n");
  process.exit(0);
}
if (cmd === 'cross-check') {
  process.stdout.write(%s + "\\n");
  process.exit(%d);
}
process.exit(0);
""" % (record_exit, record_exit, json.dumps(json.dumps(cross_check)), cross_exit))
    fv.chmod(0o755)
    return fv


@needs_node
def test_unsafe_identifiers_refuse_the_storyline(tmp_path):
    """A segment key or check id that could escape <root> refuses the storyline; nothing is recorded."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Unsafe",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "../../escape", proves: ["p1"], checks: [{ id: "g", kind: "guard" }],
      async run(ctx) { await ctx.check("g"); } },
    { key: "02-ok", proves: ["p2"], checks: [{ id: "../x", kind: "guard" }],
      async run(ctx) { await ctx.check("../x"); } },
  ],
};
""")
    out = _run_wt(["record", "--storyline", str(sl)], _wt_env(root, tree, repo), timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["cause"] == "storyline_refused", result
    assert [c["verdict"] for c in result["chapters"]] == ["INCONCLUSIVE", "INCONCLUSIVE"], result
    assert not (tmp_path / "escape").exists()
    # only the pre-created vault anchor; no chapter contract or capture was written
    vault_entries = [p.name for p in (root / "vault").iterdir()] if (root / "vault").exists() else []
    assert vault_entries in ([], [".wicked-vault"]), vault_entries


@needs_node
def test_vault_pass_without_this_runs_record_is_not_pass(tmp_path):
    """The vault says PASS but this run's record call failed: the PASS is not ours -> INCONCLUSIVE."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = _make_minimal_storyline(repo, tree)
    fv = _fake_vault(tmp_path, record_exit=1,
                     cross_check={"overall": "PASS", "claims": [{"claim_id": "guard_check", "result": "PASS"}]},
                     cross_exit=0)
    out = _run_wt(["record", "--storyline", str(sl)], _wt_env(root, tree, repo, WICKED_VAULT_BIN=str(fv)), timeout=60)
    assert out.returncode == 0, out.stderr
    chapters = {c["key"]: c["verdict"] for c in json.loads((root / "result.json").read_text())["chapters"]}
    assert chapters.get("01-chapter") == "INCONCLUSIVE", chapters


@needs_node
def test_vault_error_with_no_checks_is_not_pass(tmp_path):
    """A chapter with no checks is judged by the vault's overall: ERROR is INCONCLUSIVE, never PASS."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "No checks",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "01-empty", proves: ["p1"], checks: [], async run(ctx) { await ctx.hold(100); } },
  ],
};
""")
    fv = _fake_vault(tmp_path, record_exit=0, cross_check={"overall": "ERROR", "claims": []}, cross_exit=1)
    out = _run_wt(["record", "--storyline", str(sl)], _wt_env(root, tree, repo, WICKED_VAULT_BIN=str(fv)), timeout=60)
    assert out.returncode == 0, out.stderr
    chapters = {c["key"]: c["verdict"] for c in json.loads((root / "result.json").read_text())["chapters"]}
    assert chapters.get("01-empty") == "INCONCLUSIVE", chapters


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


# ---- wicked-garden#1208: the proof root crew's walkthrough view reads ---------------------------
#
# crew `packages/crew/src/api/recording.ts` (WT-W1) reads from the proof root: `chapters.json` (the
# planned list), `progress.json` `{state: starting_app|recording|judging, chapter?}` while the tool
# runs, `result.json` chapters with title/takes/failed_frame/proves/legs/checks[{id, kind, sentence,
# passed, at_sec, evidence[], vault_entry, detail}] and a top-level `tree`, the segments under
# `demo-video/segments/<key>/segment.mp4`, and the stitched take `demo-video/demo.mp4` with
# `demo-video/poster.jpg` + `demo-video/chapters.md`. crew's acceptance (WT-W2) recomputes the seal
# as sha256 over the sorted (UTF-8 byte order) lines "<sha256 hex>  <posix relative path>\n" of every
# regular file under the root except top-level app/ and data/.

def _crew_bundle_sha(root: Path) -> str:
    """crew's `computeBundleSha` (packages/crew/src/qe/walkthrough-acceptance.ts), in Python — including
    its refusals: a link or a non-regular entry outside top-level app/ and data/ is an error, not a skip."""
    files: list[str] = []

    def walk(d: Path, rel: str) -> None:
        with os.scandir(d) as it:                      # a directory that cannot be read raises, as crew's does
            for e in sorted(it, key=lambda e: e.name):
                r = e.name if rel == "" else f"{rel}/{e.name}"
                if rel == "" and e.name in ("app", "data"):
                    continue                           # pruned before descent, as crew prunes
                if e.is_symlink():
                    raise ValueError(f"the proof root holds a link at {r}")
                if e.is_dir(follow_symlinks=False):
                    walk(Path(e.path), r)
                elif e.is_file(follow_symlinks=False):
                    files.append(r)
                else:
                    raise ValueError(f"the proof root holds a non-regular entry at {r}")

    walk(root, "")
    files.sort(key=lambda r: r.encode("utf-8"))
    outer = hashlib.sha256()
    for rel in files:
        inner = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        outer.update(f"{inner}  {rel}\n".encode("utf-8"))
    return outer.hexdigest()


@needs_node
def test_seal_form_is_the_one_crew_recomputes(tmp_path):
    """`seal --root` must equal crew's recompute byte for byte, or every live take is denied as
    'walkthrough evidence changed after it was sealed'."""
    root = tmp_path / "evidence"
    (root / "capture").mkdir(parents=True)
    (root / "demo-video" / "segments" / "01-a").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "data").mkdir()
    (root / "result.json").write_text('{"overall":"PASS"}')
    (root / "capture" / "c1.png").write_bytes(b"\x89PNG\r\n")
    (root / "capture" / "Zed.json").write_text("{}")          # 'Z' sorts before 'c' in byte order
    (root / "capture" / "é.json").write_text("{}")            # non-ASCII: byte order, not locale order
    (root / "demo-video" / "segments" / "01-a" / "segment.mp4").write_bytes(b"mp4")
    (root / "app" / "ignored.js").write_text("1")
    (root / "data" / "db.sqlite").write_bytes(b"\x00")

    out = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip())["bundle_sha"] == _crew_bundle_sha(root)


@needs_node
def test_chapters_json_is_written_before_the_app_starts(tmp_path):
    """The planned chapter list (crew's `chapters.json`: key, title, blurb, tags) exists even when
    the fixture never comes up, so the view can show the chapters while the tool runs."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Never Starts",
  fixture: { start: ["definitely-not-a-binary-xyz-1208"], ready: "/ready" },
  segments: [
    { key: "01-first", title: "First chapter", blurb: "What it proves", tags: ["pay"], proves: ["build"],
      checks: [{ id: "g", kind: "guard" }], async run(ctx) { await ctx.check("g"); } },
    { key: "02-second", title: "Second chapter", proves: [],
      checks: [{ id: "g2", kind: "guard" }], async run(ctx) { await ctx.check("g2"); } },
  ],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=90)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["cause"] == "fixture_unavailable"
    chapters_path = root / "chapters.json"
    assert chapters_path.exists(), "chapters.json (the planned list) was not written"
    chapters = json.loads(chapters_path.read_text())
    assert chapters == [
        {"key": "01-first", "title": "First chapter", "blurb": "What it proves", "tags": ["pay"], "resets": []},
        {"key": "02-second", "title": "Second chapter", "blurb": "", "tags": [], "resets": []},
    ]
    # A refusal still carries the planned titles in result.json (crew falls back to the key otherwise).
    assert [c["title"] for c in result["chapters"]] == ["First chapter", "Second chapter"]


@needs_node
def test_segment_key_rule_matches_the_demo_recorder_and_crew(tmp_path):
    """record.mjs and crew's reader accept `^[a-z0-9][a-z0-9-]*$` only; a key outside it would be
    dropped by the view silently, so the tool refuses the storyline and says which key."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Bad Key",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "Chapter_One", title: "One", checks: [{ id: "g", kind: "guard" }], async run(ctx) { await ctx.check("g"); } },
  ],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=60)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE"
    assert result["cause"] == "storyline_refused"
    assert "Chapter_One" in result["reason"]
    assert not (root / "app").exists(), "refused before the tree was materialised"


@needs_recorder
def test_progress_json_names_the_chapter_being_recorded(tmp_path):
    """While a chapter records, progress.json reads {state: 'recording', chapter, index, total};
    the storyline copies what it sees mid-take so the test can read it afterwards."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""import fs from "node:fs";
import path from "node:path";
export default {
  title: "Progress Story",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    { key: "01-chapter", title: "Chapter One", proves: ["build"],
      checks: [{ id: "g", kind: "guard" }],
      async run(ctx) {
        const root = process.env.WICKED_EVIDENCE_ROOT;
        fs.copyFileSync(path.join(root, "progress.json"), path.join(root, "data", "progress-seen.json"));
        await ctx.hold(100);
        await ctx.check("g");
      } },
  ],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=120)
    assert out.returncode == 0, out.stderr
    seen_path = root / "data" / "progress-seen.json"
    assert seen_path.exists(), f"the storyline never ran; stderr={out.stderr[-500:]}"
    seen = json.loads(seen_path.read_text())
    assert seen == {"state": "recording", "chapter": "01-chapter", "index": 1, "total": 1}


@needs_recorder
@needs_vault
def test_result_json_and_demo_video_are_what_crews_view_reads(tmp_path, session_ledger):
    """Two chapters (PASS, then a vault-verified FAIL): result.json carries the tree, titles, takes,
    the checks with sentence/passed/detail and root-relative evidence paths, the failing chapter's
    failed_at_sec + failed_frame; the segments and the stitched take sit under demo-video/; and
    the seal equals crew's recompute over the finished root."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Rich Result",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [
    {
      key: "01-passes", title: "Chapter Passes", blurb: "The clean one", proves: ["build"],
      legs: [{ leg: "provider", claim_level: "machinery-verified", reason: "the provider is a sink" }],
      checks: [{ id: "clean_guard", kind: "guard", sentence: "Nothing else was written" }],
      async run(ctx) { await ctx.hold(200); await ctx.check("clean_guard"); },
    },
    {
      key: "02-fails", title: "Chapter Fails", proves: ["test"],
      checks: [{ id: "false_guard", kind: "guard", sentence: "This one must fail",
                 verify: { kind: "jq_pred", params: { expr: "false" } } }],
      async run(ctx) { await ctx.hold(200); await ctx.check("false_guard"); },
    },
  ],
};
""")
    env = _wt_env(root, tree, repo, NODE_PATH=session_ledger)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=180)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "FAIL", result
    assert result["tree"] == tree
    by_key = {c["key"]: c for c in result["chapters"]}

    passed = by_key["01-passes"]
    assert passed["verdict"] == "PASS"
    assert passed["title"] == "Chapter Passes"
    assert passed["takes"] == 1
    assert passed["proves"] == ["build"]
    assert passed["legs"] == [{"leg": "provider", "claim_level": "machinery-verified", "reason": "the provider is a sink"}]
    assert passed["failed_at_sec"] is None and passed["failed_frame"] is None
    (check,) = passed["checks"]
    assert check["id"] == "clean_guard" and check["kind"] == "guard"
    assert check["sentence"] == "Nothing else was written"
    assert check["passed"] is True
    assert isinstance(check["at_sec"], (int, float))
    assert isinstance(check["evidence"], list) and all(isinstance(e, str) for e in check["evidence"])
    assert check["vault_entry"], "the vault recorded the claim, so the entry id is set"

    failed = by_key["02-fails"]
    assert failed["verdict"] == "FAIL"
    assert failed["title"] == "Chapter Fails"
    (fcheck,) = failed["checks"]
    assert fcheck["passed"] is False
    assert fcheck["sentence"] == "This one must fail"
    assert isinstance(fcheck["detail"], str) and fcheck["detail"]
    # DES §4.5: failed_at_sec is the earliest at_sec among the failing checks.
    assert failed["failed_at_sec"] == fcheck["at_sec"]
    assert failed["failed_frame"], "a failing chapter names its failing frame"
    frame = root / failed["failed_frame"]
    assert frame.is_file() and frame.stat().st_size > 0 and frame.suffix in (".jpg", ".png")
    assert not Path(failed["failed_frame"]).is_absolute()

    # The segments where crew looks for them, and the stitched take with its markers and poster.
    assert (root / "demo-video" / "segments" / "01-passes" / "segment.mp4").is_file()
    assert (root / "demo-video" / "segments" / "02-fails" / "segment.mp4").is_file()
    demo = root / "demo-video" / "demo.mp4"
    assert demo.is_file() and demo.stat().st_size > 0
    assert (root / "demo-video" / "poster.jpg").is_file()
    rows = [l for l in (root / "demo-video" / "chapters.md").read_text().splitlines() if re.match(r"^\|\s*\d+:\d{2}\s*\|", l)]
    assert [re.sub(r"^\|\s*\d+:\d{2}\s*\|\s*(.+?)\s*\|\s*$", r"\1", r) for r in rows] == ["Chapter Passes", "Chapter Fails"]
    assert not (root / "segments").exists(), "segments moved under demo-video/"

    # The seal covers the finished root (video included) in crew's form.
    seal = _parse_seal(out.stdout)
    assert seal["bundle_sha"] == _crew_bundle_sha(root)
    assert seal["chapters"] == [{"key": "01-passes", "verdict": "PASS"}, {"key": "02-fails", "verdict": "FAIL"}]


@needs_node
def test_seal_refuses_a_root_crew_would_refuse(tmp_path):
    """A link anywhere outside app/ and data/ makes the root unsealable on crew's side; the tool
    claims no seal for it either (exit 1, the link named) instead of hashing around it."""
    root = tmp_path / "evidence"
    (root / "capture").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "result.json").write_text('{"overall":"PASS"}')
    (root / "capture" / "c1.png").write_bytes(b"png")
    (root / "app" / "node_modules").symlink_to(tmp_path)          # under app/: ignored, as crew ignores it
    ok = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout.strip())["bundle_sha"] == _crew_bundle_sha(root)

    (root / "capture" / "link.png").symlink_to(root / "capture" / "c1.png")
    with pytest.raises(ValueError):
        _crew_bundle_sha(root)
    out = _run_wt(["seal", "--root", str(root)], {**os.environ})
    assert out.returncode == 1
    assert out.stdout.strip() == ""
    assert "capture/link.png" in out.stderr


@needs_node
def test_record_on_an_unsealable_root_is_inconclusive_with_a_null_seal(tmp_path):
    """`record` reaching the seal step on a root holding a link: result.json and progress.json say
    INCONCLUSIVE(unsealable_root) for every chapter and the seal line carries bundle_sha: null, which
    crew's acceptance reads as 'not sealed' and denies — never a seal that cannot be recomputed."""
    root = tmp_path / "evidence"
    (root / "capture").mkdir(parents=True)
    (root / "capture" / "planted.png").symlink_to(FIXTURES / "app.mjs")
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Unsealable",
  fixture: { start: ["definitely-not-a-binary-xyz-1208"], ready: "/ready" },
  segments: [{ key: "01-first", title: "First", checks: [{ id: "g", kind: "guard" }], async run(ctx) { await ctx.check("g"); } }],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=90)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    assert result["overall"] == "INCONCLUSIVE"
    assert result["cause"] == "unsealable_root"
    assert "capture/planted.png" in result["reason"]
    assert [(c["key"], c["verdict"]) for c in result["chapters"]] == [("01-first", "INCONCLUSIVE")]
    progress = json.loads((root / "progress.json").read_text())
    assert progress["overall"] == "INCONCLUSIVE" and progress["cause"] == "unsealable_root"
    seal = _parse_seal(out.stdout)
    assert seal["bundle_sha"] is None
    assert seal["overall"] == "INCONCLUSIVE" and seal["cause"] == "unsealable_root"
    assert seal["chapters"] == [{"key": "01-first", "verdict": "INCONCLUSIVE"}]
    assert "capture/planted.png" in out.stderr


@needs_node
def test_progress_json_reads_starting_app_before_the_fixture_is_up(tmp_path):
    """Between the storyline loading and the app answering, progress.json is {state: 'starting_app'};
    the storyline's own ready() hook copies what it sees at that moment, then refuses the fixture."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""import fs from "node:fs";
import path from "node:path";
export default {
  title: "Starting",
  fixture: {
    start: ["node", "app.mjs"],
    ready: async () => {
      const root = process.env.WICKED_EVIDENCE_ROOT;
      fs.copyFileSync(path.join(root, "progress.json"), path.join(root, "data", "progress-at-ready.json"));
      throw new Error("stop here: the test only wants the running state");
    },
  },
  segments: [{ key: "01-first", title: "First", checks: [{ id: "g", kind: "guard" }], async run(ctx) { await ctx.check("g"); } }],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=90)
    assert out.returncode == 0, out.stderr
    assert json.loads((root / "result.json").read_text())["cause"] == "fixture_unavailable"
    assert json.loads((root / "data" / "progress-at-ready.json").read_text()) == {"state": "starting_app"}


@needs_recorder
@needs_vault
def test_a_failed_take_is_published_where_crew_reads_the_chapter_as_recorded(tmp_path):
    """The storyline throws mid-chapter: the recorder keeps the take under failed-1/ and the tool
    publishes it at demo-video/segments/<key>/segment.mp4 (crew's `recorded` path), the chapter is FAIL
    (its check never ran), failed_at_sec comes from failure.json, a frame is cut from the take, and the
    take is in the stitched video."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    sl = repo / "storyline.mjs"
    sl.write_text("""export default {
  title: "Thrown Take",
  fixture: { start: ["node", "app.mjs"], ready: "/ready" },
  segments: [{
    key: "01-throws", title: "Chapter Throws", proves: ["build"],
    checks: [{ id: "never", kind: "guard", sentence: "Reached only if the app got there" }],
    async run(ctx) { await ctx.hold(300); throw new Error("the app never got there"); },
  }],
};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=180)
    assert out.returncode == 0, out.stderr
    seg = root / "demo-video" / "segments" / "01-throws"
    assert (seg / "failed-1" / "failure.json").is_file()
    assert (seg / "failed-1" / "segment.mp4").is_file(), "the recorder kept no video for the failed take"
    assert (seg / "segment.mp4").is_file(), "the kept take is not published at crew's recorded path"
    assert not (seg / "segment.mp4").is_symlink()
    assert json.loads((seg / "guard.json").read_text())["failed"] is True
    result = json.loads((root / "result.json").read_text())
    (chapter,) = result["chapters"]
    assert chapter["verdict"] == "FAIL" and result["overall"] == "FAIL"
    (check,) = chapter["checks"]
    assert check["passed"] is False and check["at_sec"] is None
    assert check["detail"].startswith("never reached")
    failure = json.loads((seg / "failed-1" / "failure.json").read_text())
    assert chapter["failed_at_sec"] == failure["failed_at_sec"]
    assert chapter["failed_frame"] == "demo-video/segments/01-throws/failed-frame.jpg"
    assert (root / chapter["failed_frame"]).stat().st_size > 0
    assert (root / "demo-video" / "demo.mp4").stat().st_size > 0
    assert "| Chapter Throws |" in (root / "demo-video" / "chapters.md").read_text()
    assert _parse_seal(out.stdout)["bundle_sha"] == _crew_bundle_sha(root)


@needs_recorder
@needs_vault
def test_failed_at_sec_is_the_earliest_failing_check_and_the_frame_is_the_on_screen_ones(tmp_path):
    """Two failing checks in one chapter: a guard (fails first) and an on-screen locator (fails later,
    carries a frame). failed_at_sec is the guard's at_sec (the earliest), failed_frame is the locator's
    captured frame (the earliest failing on-screen check), a passing probe lists its parsed file, and
    every evidence path resolves under the root."""
    root = tmp_path / "evidence"
    root.mkdir()
    repo, tree = _make_tree(tmp_path)
    probe_path = str(repo / "probe.mjs").replace("\\", "/")
    sl = repo / "storyline.mjs"
    sl.write_text(f"""export default {{
  title: "Two Failures",
  fixture: {{ start: ["node", "app.mjs"], ready: "/ready", probes: {{ check_run: ["node", "{probe_path}"] }} }},
  segments: [{{
    key: "01-two", title: "Two Failures", proves: ["build"],
    checks: [
      {{ id: "loc_later", kind: "locator", selector: "#never-exists-later", sentence: "Fails last, on screen" }},
      {{ id: "loc_absent", kind: "locator", selector: "#never-exists-xyz", sentence: "Fails later, on screen" }},
      {{ id: "probe_ok", kind: "probe", name: "check_run", sentence: "The probe answers" }},
      {{ id: "false_guard", kind: "guard", sentence: "Fails first", verify: {{ kind: "jq_pred", params: {{ expr: "false" }} }} }},
    ],
    // Declared in the reverse of the order they run: the earliest failure is the LAST declared check.
    async run(ctx) {{
      await ctx.hold(200);
      await ctx.check("false_guard");
      await ctx.check("probe_ok");
      await ctx.hold(1200);
      await ctx.check("loc_absent");
      await ctx.hold(1200);
      await ctx.check("loc_later");
    }},
  }}],
}};
""")
    env = _wt_env(root, tree, repo)
    out = _run_wt(["record", "--storyline", str(sl)], env, timeout=180)
    assert out.returncode == 0, out.stderr
    result = json.loads((root / "result.json").read_text())
    (chapter,) = result["chapters"]
    checks = {c["id"]: c for c in chapter["checks"]}
    assert checks["false_guard"]["passed"] is False
    assert checks["loc_absent"]["passed"] is False
    assert checks["probe_ok"]["passed"] is True, checks["probe_ok"]
    assert checks["loc_later"]["passed"] is False
    assert checks["false_guard"]["at_sec"] < checks["loc_absent"]["at_sec"] < checks["loc_later"]["at_sec"]
    # The minimum, not the first declared (loc_later) nor the first on-screen one by declaration.
    assert chapter["failed_at_sec"] == checks["false_guard"]["at_sec"]
    # The EARLIEST failing on-screen check's frame, not the first declared on-screen failure's.
    assert chapter["failed_frame"] == "capture/loc_absent.png"
    assert checks["loc_absent"]["evidence"] == ["capture/loc_absent.png"]
    assert checks["loc_later"]["evidence"] == ["capture/loc_later.png"]
    assert checks["probe_ok"]["evidence"] == ["capture/probe_ok.parsed.json"]
    for c in checks.values():
        for e in c["evidence"]:
            assert not Path(e).is_absolute() and (root / e).is_file(), e
    assert chapter["verdict"] == "FAIL"
