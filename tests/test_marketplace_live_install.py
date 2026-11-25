"""Live Claude Code installs from both catalogs (garden#1562 round 2). Opt-in: WICKED_LIVE_CLAUDE=1.

These drive the real `claude` CLI in a throwaway HOME + CLAUDE_CONFIG_DIR, so they never touch a
user's Claude config. CI has no `claude` binary and no network budget for clones, so they skip
there; the structural half of the contract is tests/test_marketplace_release_ref.py.

- A LOCAL add (`claude plugin marketplace add <checkout>`, which is what wicked-installer
  `--source-root` runs) must install that checkout's tree: a marker written into a copy of this
  working tree must be in the installed plugin.
- The PUBLISHED add (`claude plugin marketplace add <release catalog URL>`) must install the
  release tag the catalog names. Point WICKED_RELEASE_MARKETPLACE_URL at a branch's raw file to
  check a PR before it reaches main.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLAUDE = shutil.which("claude")
RELEASE_URL = os.environ.get(
    "WICKED_RELEASE_MARKETPLACE_URL",
    "https://raw.githubusercontent.com/mikeparcewski/wicked-garden/main/.claude-plugin/release-marketplace.json",
)
pytestmark = pytest.mark.skipif(
    os.environ.get("WICKED_LIVE_CLAUDE") != "1" or CLAUDE is None,
    reason="live Claude Code install: set WICKED_LIVE_CLAUDE=1 with claude on PATH",
)


def _claude(home: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
    env.update(HOME=str(home), CLAUDE_CONFIG_DIR=str(home / "cfg"), CLAUDE_CODE_PLUGIN_PREFER_HTTPS="1")
    r = subprocess.run([CLAUDE, *args], cwd=home, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"claude {' '.join(args)} exited {r.returncode}: {r.stdout[-800:]} {r.stderr[-800:]}"


def _record(home: Path) -> dict:
    data = json.loads((home / "cfg" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    (record,) = data["plugins"]["wicked-garden@wicked-garden"]
    return record


def test_a_local_checkout_installs_its_own_tree(tmp_path):
    checkout = tmp_path / "checkout"
    shutil.copytree(REPO, checkout, ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "__pycache__"))
    marker = f"LIVE-MARKER-{uuid.uuid4().hex}.txt"
    (checkout / marker).write_text("this checkout\n", encoding="utf-8")
    home = tmp_path / "home"
    (home / "cfg").mkdir(parents=True)
    _claude(home, "plugin", "marketplace", "add", str(checkout))
    _claude(home, "plugin", "install", "wicked-garden@wicked-garden")
    installed = Path(_record(home)["installPath"])
    assert (installed / marker).is_file(), f"{installed} is not the checkout's tree (no {marker})"


def test_the_release_catalog_installs_the_tag_it_names(tmp_path):
    with urllib.request.urlopen(RELEASE_URL, timeout=30) as resp:  # noqa: S310 - fixed https URL
        catalog = json.loads(resp.read().decode("utf-8"))
    source = catalog["plugins"][0]["source"]
    ls = subprocess.run(["git", "ls-remote", f"https://github.com/{source['repo']}.git",
                         f"refs/tags/{source['ref']}", f"refs/tags/{source['ref']}^{{}}"],
                        capture_output=True, text=True, timeout=60, check=True).stdout.split("\n")
    shas = dict(reversed(line.split("\t")) for line in ls if line)
    tag_commit = shas.get(f"refs/tags/{source['ref']}^{{}}") or shas[f"refs/tags/{source['ref']}"]
    home = tmp_path / "home"
    (home / "cfg").mkdir(parents=True)
    _claude(home, "plugin", "marketplace", "add", RELEASE_URL)
    _claude(home, "plugin", "install", "wicked-garden@wicked-garden")
    record = _record(home)
    assert record["gitCommitSha"] == tag_commit, (record["gitCommitSha"], source["ref"], tag_commit)
    assert record["version"] == catalog["plugins"][0]["version"]
