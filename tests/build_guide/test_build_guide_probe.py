"""probe.py: finds `wicked-core floor probe`, runs it, summarizes what IT wrote, or says it is unavailable."""

from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from bg_helpers import FIXTURES, GUIDES, run_script

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="stub executables are POSIX scripts")

UNAVAILABLE = "probe unavailable: the guide is unverified, so the floor will not use it for exclusion"

STUB = textwrap.dedent('''\
    #!PYTHON
    import json, sys
    args = sys.argv[1:]
    if args[:2] != ["floor", "probe"]:
        sys.exit(2)
    if "--help" in args:
        print("usage: wicked-core floor probe --repo <dir> --guide <file> [--check <name>]")
        sys.exit(0)
    guide_path = args[args.index("--guide") + 1]
    guide = json.load(open(guide_path))
    for check in guide["checks"]:
        check["verified"] = {"baseSha": "0" * 40, "runnerVersion": "tinyrun 0.3.1", "at": "2026-10-23T00:00:00Z",
                             "results": {"run": "pass", "mutation": "pass", "deselect": "fail: exit 3"}}
    json.dump(guide, open(guide_path, "w"), indent=2)
    sys.exit(1)
    ''')
NO_PROBE = "#!PYTHON\nimport sys\nprint('error: unknown command floor', file=sys.stderr)\nsys.exit(2)\n"
# wicked-core#1066's CLI: an incomplete `floor probe` prints its usage and exits 2.
USAGE_ONLY = ("#!PYTHON\nimport sys\nprint('usage: wicked-core floor probe --repo <dir> --guide <file> "
              "[--check <name>]', file=sys.stderr)\nsys.exit(2)\n")


def _stub(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "wicked-core"
    path.write_text(body.replace("PYTHON", sys.executable), encoding="utf-8")
    path.chmod(0o755)
    return path


def _env_without_core(tmp_path: Path) -> dict:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "WICKED_CORE_BIN"}
    env["PATH"] = str(empty)
    return env


def test_no_wicked_core_is_unavailable_and_says_the_guide_is_unverified(tmp_path):
    code, report = run_script("probe", "--repo", str(FIXTURES / "tinyrun-repo"), "--guide",
                              str(GUIDES / "tinyrun-text.json"), env=_env_without_core(tmp_path))
    assert code == 3
    assert report == {"probe": "unavailable", "guide": "unverified", "message": UNAVAILABLE,
                      "reason": "wicked-core is not installed (set WICKED_CORE_BIN or put it on PATH)"}


def test_a_wicked_core_without_floor_probe_is_unavailable(tmp_path):
    env = {**_env_without_core(tmp_path), "WICKED_CORE_BIN": str(_stub(tmp_path, NO_PROBE))}
    code, report = run_script("probe", "--repo", str(FIXTURES / "tinyrun-repo"), "--guide",
                              str(GUIDES / "tinyrun-text.json"), env=env)
    assert code == 3
    assert report["message"] == UNAVAILABLE
    assert "has no floor probe" in report["reason"]


def test_the_probe_writes_verified_and_the_wrapper_only_reports_it(tmp_path):
    guide = tmp_path / "build-guide.json"
    shutil.copyfile(GUIDES / "tinyrun-text.json", guide)
    env = {**_env_without_core(tmp_path), "WICKED_CORE_BIN": str(_stub(tmp_path, STUB))}
    code, report = run_script("probe", "--repo", str(FIXTURES / "tinyrun-repo"), "--guide", str(guide), env=env)
    assert code == 1, "the probe's own exit code is passed through"
    assert report["probe"] == "ran"
    assert report["checks"][0]["verified"]["results"]["deselect"] == "fail: exit 3"
    assert "| test | deselect | fail: exit 3 |" in report["markdown"]
    written = json.loads(guide.read_text(encoding="utf-8"))
    assert written["checks"][0]["verified"]["runnerVersion"] == "tinyrun 0.3.1"


def test_a_usage_answer_means_the_probe_exists(tmp_path):
    env = {**_env_without_core(tmp_path), "WICKED_CORE_BIN": str(_stub(tmp_path, USAGE_ONLY))}
    code, report = run_script("probe", "--repo", str(FIXTURES / "tinyrun-repo"), "--guide",
                              str(GUIDES / "tinyrun-text.json"), env=env)
    assert report["probe"] == "ran", report
    assert code == 2, "the stub's usage exit code is passed through"
