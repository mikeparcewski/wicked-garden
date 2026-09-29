"""The validator's walk is scoped to the checkout it was asked about (#1180).

History: at the deliver gate of run `b7084e9d` an operator ran `scripts/ci/validate.py` inside a
governed-run worktree and got exit 1 with 5 errors. All 5 were pytest's deliberately-malformed JSON
fixtures and scratch under `tmp/` — files belonging to another checkout and to tests that are SUPPOSED
to contain invalid input. The mechanism was check 8's `root.glob("**/*.json")`, which descends into
gitignored scratch (`tmp/` held 11,518 files after that run) and into nested checkouts, because
governed-run worktrees are created inside the repo. Every operator who ran the validator there had to
rule the failure out by hand, and the obvious wrong move was to "fix" the fixtures.

So: the file list comes from git's own view of the tree (`ls-files --cached --others
--exclude-standard`), and the root is selectable with `--root`. These tests build the failing tree
from the incident — a tracked good file, ignored scratch, and a nested checkout, each holding invalid
JSON — and assert the validator judges only what belongs to the tree. `test_a_plain_glob_is_the_defect`
pins that the pre-fix walk DOES pick the foreign files up, so this suite fails if anyone reinstates it.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("wg_validate", _REPO / "scripts" / "ci" / "validate.py")
_validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate)
json_files_to_check = _validate.json_files_to_check
resolve_root = _validate.resolve_root


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd, check=True, capture_output=True,
        env={"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


@pytest.fixture
def incident_tree(tmp_path: Path) -> Path:
    """A checkout shaped like the one the incident happened in."""
    root = tmp_path / "repo"
    (root / "tmp").mkdir(parents=True)
    (root / "wicked-worktrees" / "run-b7084e9d").mkdir(parents=True)
    (root / ".gitignore").write_text("tmp/\n")
    (root / "good.json").write_text(json.dumps({"ok": True}))
    (root / "tmp" / "debris.json").write_text("{ scratch, not json")
    (root / "wicked-worktrees" / "run-b7084e9d" / "fixture.json").write_text("{ deliberately malformed")
    _git(root, "init", "-q", ".")
    # A nested checkout, exactly as a governed run leaves one inside the repo. (`git add -A` would
    # itself fail 128 on a nested repo with no commit, so the outer add names its paths.)
    _git(root / "wicked-worktrees" / "run-b7084e9d", "init", "-q", ".")
    _git(root, "add", "--", ".gitignore", "good.json")
    return root


def _rels(root: Path) -> set[str]:
    files, warning = json_files_to_check(root)
    assert warning is None, warning
    return {p.relative_to(root).as_posix() for p in files}


def test_a_plain_glob_is_the_defect(incident_tree: Path) -> None:
    """The pre-fix walk reports both foreign files — the failure a correct tree cannot avoid."""
    bad = []
    for path in sorted(incident_tree.glob("**/*.json")):
        parts = path.relative_to(incident_tree).parts
        if any(p in (".git", "node_modules", "__pycache__", ".venv") for p in parts):
            continue
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError:
            bad.append(path.relative_to(incident_tree).as_posix())
    assert bad == ["tmp/debris.json", "wicked-worktrees/run-b7084e9d/fixture.json"]


def test_gitignored_scratch_is_not_validated(incident_tree: Path) -> None:
    assert "tmp/debris.json" not in _rels(incident_tree)


def test_a_nested_checkout_is_not_walked(incident_tree: Path) -> None:
    assert not any(r.startswith("wicked-worktrees/") for r in _rels(incident_tree))


def test_the_checkouts_own_files_are_validated(incident_tree: Path) -> None:
    assert "good.json" in _rels(incident_tree)


def test_a_new_unignored_file_is_validated(incident_tree: Path) -> None:
    """An added-but-not-yet-committed JSON file is still judged — the guard must not go blind on a
    work in progress."""
    (incident_tree / "fresh.json").write_text("{ broken")
    assert "fresh.json" in _rels(incident_tree)


def test_a_non_git_tree_falls_back_and_says_so(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{}")
    files, warning = json_files_to_check(tmp_path)
    assert [p.name for p in files] == ["a.json"]
    assert warning is not None and "git work tree" in warning


def test_root_defaults_to_this_checkout() -> None:
    assert resolve_root([]) == _REPO


def test_root_argument_selects_the_tree(tmp_path: Path) -> None:
    assert resolve_root(["--root", str(tmp_path)]) == tmp_path.resolve()
    assert resolve_root([f"--root={tmp_path}"]) == tmp_path.resolve()


def test_root_rejects_a_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        resolve_root(["--root", str(tmp_path / "nope")])


def test_unknown_argument_is_refused() -> None:
    with pytest.raises(SystemExit):
        resolve_root(["--stricter"])


def test_the_live_tree_is_clean() -> None:
    """The repo this test runs in has no invalid JSON of its own."""
    files, warning = json_files_to_check(_REPO)
    assert warning is None, warning
    broken = []
    for path in files:
        try:
            json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            broken.append((path.relative_to(_REPO).as_posix(), str(exc)[:80]))
    assert broken == []
