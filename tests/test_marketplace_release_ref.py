"""Both marketplace installs deliver the tree they say they do (#1413, garden#1562 round 2).

Two catalogs, one per install path:

- `.claude-plugin/marketplace.json` is what `claude plugin marketplace add <dir>` reads from a
  local checkout (and from the default branch for a bare `owner/repo` add). Its entry is `"./"`,
  so a local add installs THAT checkout: wicked-installer `--source-root`, a candidate under
  certification, a developer testing an edit. Codex reads the same file from the npm copy.
- `.claude-plugin/release-marketplace.json` is the published catalog, added by URL
  (`claude plugin marketplace add <raw URL on main>`). Its entry is the release TAG
  (`{"source": "github", ..., "ref": "v<version>"}`), so a Claude Code user gets the tree npm
  ships under that version, not main's tree labelled as the release. A URL marketplace re-reads
  the file on refresh, so the ref moves with each release and `plugin update` follows it.

The version writers stamp both files and validate.py refuses drift.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node not on PATH")
LOCAL_MKT = Path(".claude-plugin") / "marketplace.json"
RELEASE_MKT = Path(".claude-plugin") / "release-marketplace.json"
RELEASE_URL = "https://raw.githubusercontent.com/mikeparcewski/wicked-garden/main/.claude-plugin/release-marketplace.json"

_spec = importlib.util.spec_from_file_location("wg_validate_mkt", REPO / "scripts" / "ci" / "validate.py")
_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate)


def _version() -> str:
    return json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def _entry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(p for p in data["plugins"] if p["name"] == "wicked-garden")


def test_local_marketplace_installs_the_checkout_itself():
    entry = _entry(REPO / LOCAL_MKT)
    assert entry["source"] == "./"
    assert entry["version"] == _version()


def test_release_marketplace_installs_the_release_tag():
    assert _entry(REPO / RELEASE_MKT)["source"] == {
        "source": "github", "repo": "mikeparcewski/wicked-garden", "ref": f"v{_version()}"}
    local = json.loads((REPO / LOCAL_MKT).read_text(encoding="utf-8"))
    release = json.loads((REPO / RELEASE_MKT).read_text(encoding="utf-8"))
    assert release["name"] == local["name"] == "wicked-garden"  # installed as wicked-garden@wicked-garden


def test_no_second_codex_catalog():
    """Codex reads `.claude-plugin/marketplace.json` ("./") again; the interim Codex file is gone."""
    assert not (REPO / ".agents" / "plugins" / "marketplace.json").exists()


def test_install_docs_add_the_release_catalog_by_url():
    for rel in ("README.md", "docs/getting-started.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert f"claude plugins marketplace add {RELEASE_URL}" in text, rel
        assert "claude plugins marketplace add mikeparcewski/wicked-garden\n" not in text, rel


def _tree(tmp_path: Path) -> Path:
    for rel in ("package.json", ".claude-plugin/plugin.json", str(LOCAL_MKT), str(RELEASE_MKT),
                ".codex-plugin/plugin.json"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    return tmp_path


def _assert_stamped(root: Path, version: str) -> None:
    local = json.loads((root / LOCAL_MKT).read_text())
    assert local["version"] == local["plugins"][0]["version"] == version
    assert local["plugins"][0]["source"] == "./"
    release = json.loads((root / RELEASE_MKT).read_text())
    assert release["version"] == release["plugins"][0]["version"] == version
    assert release["plugins"][0]["source"]["ref"] == f"v{version}"


@needs_node
def test_sync_plugin_version_stamps_both_catalogs(tmp_path):
    root = _tree(tmp_path)
    pkg = json.loads((root / "package.json").read_text())
    pkg["version"] = "99.1.0"
    (root / "package.json").write_text(json.dumps(pkg))
    subprocess.run([NODE, str(REPO / ".github" / "scripts" / "sync-plugin-version.mjs")],
                   cwd=root, check=True, capture_output=True, timeout=60)
    _assert_stamped(root, "99.1.0")
    assert _validate.marketplace_errors(root, "wicked-garden", "99.1.0") == []


def test_version_hook_stages_both_catalogs():
    hook = json.loads((REPO / "package.json").read_text(encoding="utf-8"))["scripts"]["version"]
    assert str(LOCAL_MKT.as_posix()) in hook and str(RELEASE_MKT.as_posix()) in hook


def test_release_py_stamps_both_catalogs(tmp_path):
    root = _tree(tmp_path)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import release; "
            "m = release.ReleaseManager(sys.argv[2]); m.update_marketplace_version('2.0.0'); "
            "m.update_other_version_anchors('2.0.0')")
    subprocess.run([sys.executable, "-c", code, str(REPO / ".claude" / "skills" / "releasing" / "scripts"), str(root)],
                   check=True, capture_output=True, timeout=60, cwd=root)
    _assert_stamped(root, "2.0.0")
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    plugin["version"] = "2.0.0"  # update_plugin_version's job; this test drives the other two writers
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(plugin))
    assert _validate.marketplace_errors(root, "wicked-garden", "2.0.0") == []


def test_release_py_tags_the_ref_the_marketplace_names():
    """The releasing skill tags v<version>, the tag the entry installs and release.yml's trigger."""
    text = (REPO / ".claude" / "skills" / "releasing" / "scripts" / "release.py").read_text(encoding="utf-8")
    assert 'tag_name = f"v{version}"' in text and 'tag_name = f"v{new_version}"' in text
    assert '-v{version}"' not in text and '-v{new_version}"' not in text


def test_validate_accepts_the_repo_as_it_is():
    assert _validate.marketplace_errors(REPO, "wicked-garden", _version()) == []


def _set(root: Path, rel: Path, top: dict | None = None, **changes) -> None:
    data = json.loads((root / rel).read_text())
    data["plugins"][0].update(changes)
    data.update(top or {})
    (root / rel).write_text(json.dumps(data))


@pytest.mark.parametrize("source, needle", [
    ("./", "release tag"),
    ({"source": "github", "repo": "mikeparcewski/wicked-garden"}, "release tag"),
    ({"source": "github", "repo": "mikeparcewski/wicked-garden", "ref": "v0.0.1"}, "'v0.0.1'"),
    ({"source": "github", "repo": "someone/else", "ref": "vX"}, "repo"),
])
def test_validate_refuses_a_release_entry_that_is_not_the_release_tag(tmp_path, source, needle):
    root = _tree(tmp_path)
    if isinstance(source, dict) and source.get("ref") == "vX":
        source = {**source, "ref": f"v{_version()}"}
    _set(root, RELEASE_MKT, source=source)
    errors = _validate.marketplace_errors(root, "wicked-garden", _version())
    assert errors and any(needle in e for e in errors), errors


def test_validate_refuses_a_local_catalog_that_leaves_the_checkout(tmp_path):
    """The W12: a github entry here makes a local add install the published tag, not the checkout."""
    root = _tree(tmp_path)
    _set(root, LOCAL_MKT, source={"source": "github", "repo": "mikeparcewski/wicked-garden", "ref": f"v{_version()}"})
    errors = _validate.marketplace_errors(root, "wicked-garden", _version())
    assert any(LOCAL_MKT.as_posix() in e and '"./"' in e for e in errors), errors


def test_validate_refuses_drift_a_renamed_catalog_or_a_missing_one(tmp_path):
    root = _tree(tmp_path)
    _set(root, RELEASE_MKT, version="0.0.1")
    assert any(RELEASE_MKT.as_posix() in e and "0.0.1" in e
               for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
    _set(root, RELEASE_MKT, version=_version(), top={"version": "0.0.2"})
    assert any("0.0.2" in e for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
    _set(root, RELEASE_MKT, top={"version": _version(), "name": "other"})
    assert any("name" in e and "other" in e for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
    (root / RELEASE_MKT).unlink()
    assert any("Missing" in e for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
