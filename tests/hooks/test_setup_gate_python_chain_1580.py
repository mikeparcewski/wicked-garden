"""garden#1580 — the setup gate must block through the hooks.json fallback chain.

hooks.json runs every hook as
``python3 invoke.py <hook> || python invoke.py <hook> || py -3 invoke.py <hook>``.
A non-zero exit from the first interpreter runs the next one. On a host with
only ``python3`` (default macOS with Homebrew Python), a gate that signals by
exit 2 is turned into exit 127 by the missing ``python`` and ``py``. Claude Code
reads 127 as a non-blocking hook error and the prompt goes through.

The gate signals through JSON on stdout instead (``decision: block``, exit 0),
the way the other hook entries do, so the chain never runs a fallback.

These tests run the real hooks.json command string under ``sh`` with a PATH
that holds ``python3`` only, in an isolated HOME / TMPDIR.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SH = shutil.which("sh")


def _prompt_submit_command() -> str:
    hooks = json.loads((_REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    entries = hooks["hooks"]["UserPromptSubmit"]
    commands = [h["command"] for e in entries for h in e["hooks"] if "prompt_submit" in h["command"]]
    assert len(commands) == 1, commands
    return commands[0]


def _python3_only_path(root: Path) -> str:
    """A PATH dir with a `python3` that runs this interpreter, and no `python` or `py`."""
    bindir = root / "bin"
    bindir.mkdir()
    shim = bindir / "python3"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return str(bindir)


def _run_hook(prompt: str, setup_complete: bool):
    root = Path(tempfile.mkdtemp(prefix="wg-1580-"))
    home = root / "home"
    tmp = root / "tmp"
    home.mkdir()
    tmp.mkdir()
    if setup_complete:
        cfg = home / ".something-wicked" / "wicked-garden"
        cfg.mkdir(parents=True)
        (cfg / "config.json").write_text(json.dumps({"setup_complete": True}), encoding="utf-8")
    sid = f"t1580-{uuid.uuid4().hex}"
    env = {
        "PATH": _python3_only_path(root),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "TMPDIR": str(tmp),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "CLAUDE_SESSION_ID": sid,
        "CLAUDE_PLUGIN_ROOT": str(_REPO),
        "WICKED_CONTEXT_BACKEND": "off",
        "WG_DAEMON_ENABLED": "false",
    }
    r = subprocess.run(
        [_SH, "-c", _prompt_submit_command()],
        input=json.dumps({"prompt": prompt, "session_id": sid, "hook_event_name": "UserPromptSubmit"}),
        capture_output=True, text=True, env=env, cwd=str(root), timeout=60,
    )
    shutil.rmtree(root, ignore_errors=True)
    return r


def _last_json(stdout: str) -> dict:
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    assert lines, "the hook wrote nothing to stdout"
    return json.loads(lines[-1])


@unittest.skipIf(_SH is None or os.name == "nt", "needs a POSIX sh (the Claude Code hook shell)")
class SetupGateThroughTheChain(unittest.TestCase):
    def test_no_setup_blocks_with_json_and_no_fallback_runs(self):
        r = _run_hook("show me all open tasks", setup_complete=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("not found", r.stderr)
        out = _last_json(r.stdout)
        self.assertEqual(out.get("decision"), "block", r.stdout)
        self.assertIn("requires setup before first use", out.get("reason", ""))
        self.assertIn("wicked-garden setup", out.get("reason", ""))

    def test_setup_command_passes_without_setup(self):
        r = _run_hook("/wicked-garden:setup", setup_complete=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("not found", r.stderr)
        self.assertNotEqual(_last_json(r.stdout).get("decision"), "block", r.stdout)

    def test_after_setup_a_prompt_is_not_blocked(self):
        r = _run_hook("show me all open tasks", setup_complete=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("not found", r.stderr)
        self.assertNotEqual(_last_json(r.stdout).get("decision"), "block", r.stdout)


if __name__ == "__main__":
    unittest.main()
