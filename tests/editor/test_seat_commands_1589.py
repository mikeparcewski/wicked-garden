"""garden#1589: every wicked-garden command the editor scaffold hands a seat runs in a seat.

In a seat, ``wicked-garden`` on PATH is the launcher (``scripts/wicked-garden.mjs``), which knows
only its own verbs (``VERBS``). The npm installer entry (``install.mjs``) has more commands
(``pack``, ``install``, ``status``...), but a seat never runs it. The editor-scaffold skill, its pack
READMEs and ``scaffold.py``'s next steps told the worker to run ``npx wicked-garden pack check
<dir>``. The launcher refuses that (``unknown verb: pack``, exit 2), so the check never ran.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "scripts" / "wicked-garden.mjs"
SCAFFOLD = REPO / "scripts" / "editor" / "scaffold.py"
NODE = shutil.which("node")


def launcher_verbs() -> set[str]:
    m = re.search(r"export const VERBS = \[([^\]]*)\]", LAUNCHER.read_text(encoding="utf-8"))
    assert m, "the launcher's VERBS list moved"
    return set(re.findall(r'"([a-z-]+)"', m.group(1)))


def installer_only_commands() -> set[str]:
    """The commands ``install.mjs`` dispatches itself (its ``switch (opts.cmd)``), minus the
    launcher verbs it forwards to the launcher: what a seat's ``wicked-garden`` does not know."""
    src = (REPO / "install.mjs").read_text(encoding="utf-8")
    block = src[src.index("switch (opts.cmd) {"):]
    cases = set(re.findall(r'case "([a-z][a-z-]*)":', block))
    return cases - launcher_verbs()


# The command forms a skill hands a seat: `wicked-garden <verb> …` or `npx wicked-garden <verb> …`,
# in an inline code span or on a line of a fenced block.
_COMMAND = re.compile(r"^(?:\$\s*)?(?:npx\s+)?wicked-garden\s+([a-z][a-z-]*)\b")
_SPAN = re.compile(r"`([^`\n]+)`")


def commands_in(path: Path) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    fence = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        for text in ([line.strip()] if fence else _SPAN.findall(line)):
            m = _COMMAND.match(text.strip())
            if m:
                out.append((n, m.group(1), text.strip()))
    return out


SEAT_DOCS = sorted(
    [p for p in (REPO / "skills").rglob("*.md")]
    + [p for p in (REPO / "packs").rglob("README.md")]
)


def test_the_installer_only_commands_are_read_from_install_mjs():
    # The guard below is only as good as this set: `pack` must be in it.
    assert "pack" in installer_only_commands()
    assert not installer_only_commands() & launcher_verbs()


def test_no_skill_or_shipped_pack_names_an_installer_only_command_1589():
    bad = installer_only_commands()
    found = [
        f"{p.relative_to(REPO)}:{n}: {text}"
        for p in SEAT_DOCS
        for n, verb, text in commands_in(p)
        if verb in bad
    ]
    assert found == [], (
        "a seat's `wicked-garden` is the launcher (verbs: "
        + "|".join(sorted(launcher_verbs()))
        + "); name `wicked-garden run scripts/…` instead:\n" + "\n".join(found)
    )


@pytest.mark.parametrize("kind_args", [[], ["--kind", "run-plugin"]], ids=["editor", "run-plugin"])
def test_the_scaffolds_next_steps_use_launcher_verbs_1589(tmp_path, kind_args):
    out = tmp_path / "pack"
    ident = ["--id", "acme-spend", "--title", "Phase spend"] if kind_args else [
        "--id", "acme-json", "--title", "JSON viewer", "--kinds", "page,document"]
    done = subprocess.run(
        [sys.executable, str(SCAFFOLD), *kind_args, "--vendor", "acme", *ident, "--out", str(out)],
        capture_output=True, text=True, timeout=240,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    verbs = launcher_verbs()
    for step in ("pin", "check", "conformance"):
        argv = shlex.split(report[step])
        assert argv[0] == "wicked-garden" and argv[1] in verbs, f"{step}: {report[step]}"


@pytest.mark.skipif(NODE is None, reason="node not on PATH")
def test_the_scaffolds_check_step_runs_through_the_seat_launcher_1589(tmp_path):
    """The `check` step, run exactly as a seat runs it (the launcher), checks the new pack."""
    out = tmp_path / "pack"
    done = subprocess.run(
        [sys.executable, str(SCAFFOLD), "--vendor", "acme", "--id", "acme-json", "--title",
         "JSON viewer", "--kinds", "page,document", "--out", str(out)],
        capture_output=True, text=True, timeout=240,
    )
    assert done.returncode == 0, done.stderr
    argv = shlex.split(json.loads(done.stdout)["check"])
    assert argv[0] == "wicked-garden"
    ran = subprocess.run([NODE, str(LAUNCHER), *argv[1:]], capture_output=True, text=True, timeout=240)
    assert ran.returncode == 0, (ran.stdout, ran.stderr)
