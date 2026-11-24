"""The marketplace install delivers the release it is labelled as (#1413).

`claude plugin marketplace add mikeparcewski/wicked-garden` reads `.claude-plugin/marketplace.json`
from the default branch. With `"source": "./"` Claude Code installed main's tree and cached it under
the release version, so a Claude Code user and an npm user of one version ran different skill text.
The entry now names the release tag (`{"source": "github", ..., "ref": "v<version>"}`), the two
version writers stamp it, and validate.py refuses drift.

Codex does not take a github source (it lists no plugin for one). It reads
`.agents/plugins/marketplace.json` before `.claude-plugin/marketplace.json`, so that file keeps
Codex on the local root it was given (the npm copy, which IS the release).
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
CLAUDE_MKT = Path(".claude-plugin") / "marketplace.json"
CODEX_MKT = Path(".agents") / "plugins" / "marketplace.json"

_spec = importlib.util.spec_from_file_location("wg_validate_mkt", REPO / "scripts" / "ci" / "validate.py")
_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate)


def _version() -> str:
    return json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def _entry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(p for p in data["plugins"] if p["name"] == "wicked-garden")


def test_claude_marketplace_installs_the_release_tag():
    assert _entry(REPO / CLAUDE_MKT)["source"] == {
        "source": "github", "repo": "mikeparcewski/wicked-garden", "ref": f"v{_version()}"}


def test_codex_marketplace_keeps_the_local_root():
    entry = _entry(REPO / CODEX_MKT)
    assert entry["source"] == "./"
    assert entry["version"] == _version()


def _tree(tmp_path: Path) -> Path:
    for rel in ("package.json", ".claude-plugin/plugin.json", str(CLAUDE_MKT), str(CODEX_MKT),
                ".codex-plugin/plugin.json"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    return tmp_path


@needs_node
def test_sync_plugin_version_stamps_the_tag_and_the_codex_marketplace(tmp_path):
    root = _tree(tmp_path)
    pkg = json.loads((root / "package.json").read_text())
    pkg["version"] = "99.1.0"
    (root / "package.json").write_text(json.dumps(pkg))
    subprocess.run([NODE, str(REPO / ".github" / "scripts" / "sync-plugin-version.mjs")],
                   cwd=root, check=True, capture_output=True, timeout=60)
    claude = json.loads((root / CLAUDE_MKT).read_text())
    assert claude["version"] == claude["plugins"][0]["version"] == "99.1.0"
    assert claude["plugins"][0]["source"]["ref"] == "v99.1.0"
    codex = json.loads((root / CODEX_MKT).read_text())
    assert codex["version"] == codex["plugins"][0]["version"] == "99.1.0"
    assert codex["plugins"][0]["source"] == "./"
    assert _validate.marketplace_errors(root, "wicked-garden", "99.1.0") == []


def test_release_py_stamps_the_tag_and_the_codex_marketplace(tmp_path):
    root = _tree(tmp_path)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import release; "
            "m = release.ReleaseManager(sys.argv[2]); m.update_marketplace_version('2.0.0'); "
            "m.update_other_version_anchors('2.0.0')")
    subprocess.run([sys.executable, "-c", code, str(REPO / ".claude" / "skills" / "releasing" / "scripts"), str(root)],
                   check=True, capture_output=True, timeout=60, cwd=root)
    claude = json.loads((root / CLAUDE_MKT).read_text())
    assert claude["version"] == claude["plugins"][0]["version"] == "2.0.0"
    assert claude["plugins"][0]["source"]["ref"] == "v2.0.0"
    codex = json.loads((root / CODEX_MKT).read_text())
    assert codex["version"] == codex["plugins"][0]["version"] == "2.0.0"
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


def _set(root: Path, rel: Path, **changes) -> None:
    data = json.loads((root / rel).read_text())
    data["plugins"][0].update(changes)
    (root / rel).write_text(json.dumps(data))


@pytest.mark.parametrize("source, needle", [
    ("./", "release tag"),
    ({"source": "github", "repo": "mikeparcewski/wicked-garden"}, "release tag"),
    ({"source": "github", "repo": "mikeparcewski/wicked-garden", "ref": "v0.0.1"}, "'v0.0.1'"),
    ({"source": "github", "repo": "someone/else", "ref": "vX"}, "repo"),
])
def test_validate_refuses_a_claude_entry_that_is_not_the_release_tag(tmp_path, source, needle):
    root = _tree(tmp_path)
    if isinstance(source, dict) and source.get("ref") == "vX":
        source = {**source, "ref": f"v{_version()}"}
    _set(root, CLAUDE_MKT, source=source)
    errors = _validate.marketplace_errors(root, "wicked-garden", _version())
    assert errors and any(needle in e for e in errors), errors


def test_validate_refuses_a_codex_marketplace_that_drifts_or_is_missing(tmp_path):
    root = _tree(tmp_path)
    _set(root, CODEX_MKT, version="0.0.1")
    assert any(str(CODEX_MKT.as_posix()) in e and "0.0.1" in e
               for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
    _set(root, CODEX_MKT, version=_version(), source={"source": "github", "repo": "x/y", "ref": "v1"})
    assert any("./" in e for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
    (root / CODEX_MKT).unlink()
    assert any("Missing" in e for e in _validate.marketplace_errors(root, "wicked-garden", _version()))
