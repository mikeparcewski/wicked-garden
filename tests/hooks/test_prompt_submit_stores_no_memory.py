"""A UserPromptSubmit run never writes memory.

The hook used to save the first two prompts of every session as raw WORKING
memory (title "Session goal (turn N)"), bypassing the approve queue. That put
raw prompts, task-notification text and local paths into recall for every user,
and the entries ranked first. The path is deleted; this pins that a prompt run
makes no estate write of any kind, however many turns it runs.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[2]
_HOOKS = _REPO / "hooks" / "scripts"
_SCRIPTS = _REPO / "scripts"
for p in (str(_HOOKS), str(_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import prompt_submit as ps  # noqa: E402

_WRITES = ("memory.capture", "proposal.submit", "memory.store", "knowledge.write")


class PromptSubmitStoresNoMemory(unittest.TestCase):
    def test_the_session_goal_path_is_gone(self):
        self.assertFalse(hasattr(ps, "_capture_session_goal"))

    def test_turns_one_to_three_write_nothing(self):
        home = tempfile.mkdtemp(prefix="wg-nomem-home-")
        tmp = tempfile.mkdtemp(prefix="wg-nomem-tmp-")
        cfg = Path(home) / ".something-wicked" / "wicked-garden"
        cfg.mkdir(parents=True)
        (cfg / "config.json").write_text(json.dumps({"setup_complete": True}), encoding="utf-8")
        sid = f"nomem-{uuid.uuid4().hex}"
        env = {"HOME": home, "USERPROFILE": home, "TMPDIR": tmp, "TEMP": tmp, "TMP": tmp,
               "CLAUDE_SESSION_ID": sid, "CLAUDE_PLUGIN_ROOT": str(_REPO),
               "WICKED_CONTEXT_BACKEND": "estate", "WG_DAEMON_ENABLED": "false"}
        import _context_backend
        import _estate_client
        calls = []

        def fake_call(tool, arguments=None, *a, **kw):
            calls.append(tool)
            return None

        captured = []
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(_estate_client, "call", fake_call), \
                mock.patch.object(_estate_client, "call_raw", lambda tool, *a, **kw: calls.append(tool)), \
                mock.patch.object(_context_backend, "capture_memory",
                                  lambda *a, **kw: captured.append((a, kw))):
            for turn in range(3):
                prompt = f"implement the export path for the settings page, turn {turn}, with tests"
                payload = json.dumps({"prompt": prompt, "session_id": sid})
                with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
                        mock.patch.object(sys, "stdout", io.StringIO()):
                    try:
                        ps.main()
                    except SystemExit:
                        pass
        self.assertEqual(captured, [], "the prompt hook called capture_memory")
        self.assertEqual([c for c in calls if c in _WRITES], [], "the prompt hook wrote to estate")


if __name__ == "__main__":
    unittest.main()
