"""garden#1589: every wicked-garden command the editor scaffold hands a seat runs in a seat.

In a seat, ``wicked-garden`` on PATH is the launcher (``scripts/wicked-garden.mjs``), which knows
only its own verbs (``VERBS``). The npm installer entry (``install.mjs``) has more commands
(``pack``, ``install``, ``status``...), but a seat never runs it. The editor-scaffold skill, its pack
READMEs and ``scaffold.py``'s next steps told the worker to run ``npx wicked-garden pack check
<dir>``. The launcher refuses that (``unknown verb: pack``, exit 2), so the check never ran.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "scripts" / "wicked-garden.mjs"
INSTALLER = REPO / "install.mjs"
SCAFFOLD = REPO / "scripts" / "editor" / "scaffold.py"
NODE = shutil.which("node")

# The two scaffold kinds, with the arguments each needs.
KINDS = {
    "editor": ["--vendor", "acme", "--id", "acme-json", "--title", "JSON viewer", "--kinds", "page,document"],
    "run-plugin": ["--kind", "run-plugin", "--vendor", "acme", "--id", "acme-spend", "--title", "Phase spend"],
}


def launcher_verbs() -> set[str]:
    m = re.search(r"export const VERBS = \[([^\]]*)\]", LAUNCHER.read_text(encoding="utf-8"))
    assert m, "the launcher's VERBS list moved"
    return set(re.findall(r'"([a-z-]+)"', m.group(1)))


def installer_only_commands() -> set[str]:
    """The commands ``install.mjs`` dispatches itself (its ``switch (opts.cmd)``), minus the
    launcher verbs it forwards to the launcher: what a seat's ``wicked-garden`` does not know."""
    src = INSTALLER.read_text(encoding="utf-8")
    block = src[src.index("switch (opts.cmd) {"):]
    cases = set(re.findall(r'case "([a-z][a-z-]*)":', block))
    return cases - launcher_verbs()


# A `wicked-garden <verb>` invocation anywhere in a command: at its start, after shell chaining
# (`&&`, `;`, `|`, a subshell), and after `npx` with or without its own flags.
_COMMAND = re.compile(r"(?:^|[\s;&|(])(?:npx\s+(?:-\S+\s+)*)?wicked-garden\s+([a-z][a-z-]*)\b")
_FENCE = re.compile(r"^\s*```.*?^\s*```[^\n]*$", re.M | re.S)
# An inline code span may wrap onto the next line (Markdown allows it; this repo does it).
_SPAN = re.compile(r"`([^`]+)`")


def commands_in(text: str) -> list[tuple[str, str]]:
    """(verb, command) for every wicked-garden invocation in a fenced block or an inline span."""
    found: list[tuple[str, str]] = []
    pieces = [m.group(0) for m in _FENCE.finditer(text)]
    pieces += _SPAN.findall(_FENCE.sub("", text))
    for piece in pieces:
        flat = " ".join(piece.split())
        found += [(m.group(1), flat) for m in _COMMAND.finditer(flat)]
    return found


SEAT_DOCS = sorted(
    [p for p in (REPO / "skills").rglob("*.md")]
    + [p for p in (REPO / "packs").rglob("README.md")]
)


def test_the_installer_only_commands_are_read_from_install_mjs():
    # The guard below is only as good as this set: `pack` must be in it.
    assert "pack" in installer_only_commands()
    assert not installer_only_commands() & launcher_verbs()


@pytest.mark.parametrize("text", [
    "`npx wicked-garden pack check .`",
    "Then `npx wicked-garden\n  pack check <dir>`.",
    "`cd my-pack && wicked-garden pack check .`",
    "`npx --no wicked-garden pack check .`",
    "```\nwicked-garden root && wicked-garden pack check .\n```",
])
def test_the_guard_sees_every_command_form(text):
    assert ("pack" in {v for v, _ in commands_in(text)}), text


def test_no_skill_or_shipped_pack_names_an_installer_only_command_1589():
    bad = installer_only_commands()
    found = [
        f"{p.relative_to(REPO)}: {cmd}"
        for p in SEAT_DOCS
        for verb, cmd in commands_in(p.read_text(encoding="utf-8"))
        if verb in bad
    ]
    assert found == [], (
        "a seat's `wicked-garden` is the launcher (verbs: "
        + "|".join(sorted(launcher_verbs()))
        + "); name `wicked-garden run scripts/…` instead:\n" + "\n".join(found)
    )


def test_the_session_brief_names_a_floors_probe_a_seat_can_run_1589():
    """The SessionStart note on a pack's peer floors names its full probe; a seat must be able to run it."""
    src = (REPO / "hooks" / "scripts" / "bootstrap.py").read_text(encoding="utf-8")
    probe = re.search(r'"\\n  Full probe: ([^"]+)"', src)
    assert probe, "the floors note moved"
    argv = shlex.split(probe.group(1))
    assert argv[:3] == ["wicked-garden", "run", "scripts/_pack_registry.py"] and argv[3] == "floors", argv


def _seat_env() -> dict[str, str]:
    # The launcher prefers WICKED_GARDEN_ROOT, then CLAUDE_PLUGIN_ROOT, over its own checkout: drop both
    # so the command runs THIS checkout's checker, not an installed plugin's.
    return {k: v for k, v in os.environ.items() if k not in ("WICKED_GARDEN_ROOT", "CLAUDE_PLUGIN_ROOT")}


def _scaffold(kind: str, out: Path, cwd: Path) -> dict:
    done = subprocess.run([sys.executable, str(SCAFFOLD), *KINDS[kind], "--out", str(out)],
                          capture_output=True, text=True, timeout=240, cwd=cwd, env=_seat_env())
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_scaffolds_next_steps_use_launcher_verbs_1589(tmp_path, kind):
    report = _scaffold(kind, tmp_path / "pack", tmp_path)
    verbs = launcher_verbs()
    for step in ("pin", "check", "conformance"):
        argv = shlex.split(report[step])
        assert argv[0] == "wicked-garden" and argv[1] in verbs, f"{step}: {report[step]}"
    # The check step is the pack checker, on the pack just written.
    assert shlex.split(report["check"]) == ["wicked-garden", "run", "scripts/pack/check.py", str(tmp_path / "pack")]


def _run_check(entry: Path, argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(entry), *argv[1:]], capture_output=True, text=True, timeout=240,
                          cwd=cwd, env=_seat_env())


@pytest.mark.skipif(NODE is None, reason="node not on PATH")
@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("entry", [LAUNCHER, INSTALLER], ids=["seat-launcher", "host-npm-entry"])
def test_the_scaffolds_check_step_checks_the_pack_in_a_seat_and_on_a_host_1589(tmp_path, kind, entry):
    """The `check` step, run as a seat runs it (the launcher) and as a host runs it (the npm entry),
    from another directory with a relative pack path: it passes the new pack and fails a broken one."""
    work = tmp_path / "work"
    work.mkdir()
    report = _scaffold(kind, Path("pack"), work)  # a relative --out, as a seat in its worktree writes it
    argv = shlex.split(report["check"])
    assert argv[0] == "wicked-garden" and argv[-1] == "pack"
    ok = _run_check(entry, argv, work)
    assert ok.returncode == 0, (ok.stdout, ok.stderr)
    # The step really checks: the entry changed without a re-pin fails it.
    manifest = json.loads((work / "pack" / "wicked-pack.json").read_text(encoding="utf-8"))
    item = (manifest.get("editors") or manifest.get("plugins"))[0]
    entry_file = work / "pack" / item["entry"]
    entry_file.write_text(entry_file.read_text(encoding="utf-8") + "\n<!-- changed -->\n", encoding="utf-8")
    bad = _run_check(entry, argv, work)
    assert bad.returncode != 0, (bad.stdout, bad.stderr)
