#!/usr/bin/env python3
"""tests/smaht/test_propose_skills.py — unit tests for the session-mined skill builder MVP (#677).

Covers:

* The 3 detectors (repeated tool sequence, repeated prompt template,
  repeated bash shape) — each with a synthetic 3-session fixture.
* The deduplication step (overlapping patterns → only the longest survives).
* The privacy scrub (absolute paths normalized to ``~/...``).
* The privacy session-skip token heuristic.
* End-to-end ``analyze()`` behavior on temp session files.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from smaht import propose_skills as ps  # noqa: E402  — sys.path set up above


# ---------------------------------------------------------------------------
# Synthetic fixture helpers — keep tests deterministic and stdlib-only.
# ---------------------------------------------------------------------------


def _make_session(path: str, *, prompts: list[str], tool_calls: list[dict]) -> dict:
    """Build the structured session digest that detectors consume."""
    return {"path": path, "user_prompts": prompts, "tool_calls": tool_calls}


def _tc(name: str, **input_kwargs) -> dict:
    return {"name": name, "input": input_kwargs}


# ---------------------------------------------------------------------------
# Detector 1 — repeated tool sequence
# ---------------------------------------------------------------------------


class TestRepeatedToolSequenceDetector(unittest.TestCase):
    def test_three_sessions_share_three_tuple_sequence(self):
        """Same Read → Edit → Bash sequence in 3 sessions surfaces as a tool-sequence candidate."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=["fix the failing test in module foo bar baz"],
                tool_calls=[
                    _tc("Read", file_path="/x/foo.py"),
                    _tc("Edit", file_path="/x/foo.py"),
                    _tc("Bash", command="pytest tests/foo"),
                ],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_sequences(sessions)
        seqs = {tuple(c["key"]) for c in out}
        self.assertIn(("Read", "Edit", "Bash"), seqs)
        # The 3-tuple should appear with frequency >= MIN_FREQUENCY (3)
        match = [c for c in out if tuple(c["key"]) == ("Read", "Edit", "Bash")][0]
        self.assertGreaterEqual(match["frequency"], 3)
        self.assertEqual(match["sessions"], 3)
        self.assertEqual(match["kind"], "tool-sequence")

    def test_homogeneous_sequence_is_filtered(self):
        """Bash → Bash → Bash is noise — filter out sequences of a single tool."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[],
                tool_calls=[
                    _tc("Bash", command="echo a"),
                    _tc("Bash", command="echo b"),
                    _tc("Bash", command="echo c"),
                ],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_sequences(sessions)
        # All sequences here are homogeneous Bash-only — none should surface.
        homogeneous = [c for c in out if len(set(c["names"])) == 1]
        self.assertEqual(homogeneous, [])

    def test_below_min_frequency_is_dropped(self):
        """Sequence appearing in only 2 sessions does not surface."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[],
                tool_calls=[
                    _tc("Glob", pattern="**/*.py"),
                    _tc("Grep", pattern="TODO"),
                ],
            )
            for i in range(2)
        ]
        out = ps.detect_repeated_sequences(sessions)
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# Detector 2 — repeated prompt template
# ---------------------------------------------------------------------------


class TestRepeatedPromptTemplateDetector(unittest.TestCase):
    def test_three_sessions_share_prompt_prefix(self):
        """Three sessions whose first 5 normalized words match → 1 prompt-template candidate."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[f"create a release notes draft for v{i}.0.0"],
                tool_calls=[],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_prompt_templates(sessions)
        prefixes = {c["key"] for c in out}
        # Normalized: "create a release notes draft"
        self.assertIn("create a release notes draft", prefixes)
        match = [c for c in out if c["key"] == "create a release notes draft"][0]
        self.assertEqual(match["frequency"], 3)
        self.assertEqual(match["sessions"], 3)
        self.assertEqual(match["kind"], "prompt-template")

    def test_claude_code_system_envelope_is_skipped(self):
        """Prompts wrapped in <local-command-...> or <command-name> tags are system messages, not user input."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[
                    "<local-command-caveat>Caveat: messages below were generated by the user</local-command-caveat>"
                ],
                tool_calls=[],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_prompt_templates(sessions)
        self.assertEqual(out, [])

    def test_generic_continuation_is_skipped(self):
        """Generic continuations like 'yes do it' are not counted as templates."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=["yes please continue with that plan"],
                tool_calls=[],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_prompt_templates(sessions)
        # First word "yes" is in the generic blocklist → prefix rejected.
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# Detector 3 — repeated bash command shape
# ---------------------------------------------------------------------------


class TestRepeatedBashShapeDetector(unittest.TestCase):
    def test_three_sessions_share_gh_pr_shape(self):
        """Three sessions all running `gh pr ...` → 1 bash-shape candidate keyed ('gh','pr')."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[],
                tool_calls=[
                    _tc("Bash", command=f"gh pr create --title 'release v{i}'"),
                ],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_bash_shapes(sessions)
        shapes = {tuple(c["key"]) for c in out}
        self.assertIn(("gh", "pr"), shapes)
        match = [c for c in out if tuple(c["key"]) == ("gh", "pr")][0]
        self.assertEqual(match["frequency"], 3)
        self.assertEqual(match["kind"], "bash-shape")

    def test_generic_first_token_is_skipped(self):
        """Plain `ls -la` should not surface (ls is in the generic blocklist)."""
        sessions = [
            _make_session(
                f"/sessions/sess-{i}.jsonl",
                prompts=[],
                tool_calls=[_tc("Bash", command="ls -la /tmp")],
            )
            for i in range(3)
        ]
        out = ps.detect_repeated_bash_shapes(sessions)
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDedupeCandidates(unittest.TestCase):
    def test_subsequence_dropped_when_supersequence_at_least_as_frequent(self):
        """3-tuple subsumes the 2-tuple it contains when frequency is >=."""
        candidates = [
            {
                "kind": "tool-sequence",
                "key": ("Read", "Edit"),
                "names": ["Read", "Edit"],
                "frequency": 3,
                "sessions": 3,
                "example": "Read → Edit",
            },
            {
                "kind": "tool-sequence",
                "key": ("Read", "Edit", "Bash"),
                "names": ["Read", "Edit", "Bash"],
                "frequency": 3,
                "sessions": 3,
                "example": "Read → Edit → Bash",
            },
        ]
        out = ps.dedupe_candidates(candidates)
        keys = {tuple(c["key"]) for c in out if c["kind"] == "tool-sequence"}
        self.assertNotIn(("Read", "Edit"), keys)
        self.assertIn(("Read", "Edit", "Bash"), keys)

    def test_subsequence_kept_when_strictly_more_frequent(self):
        """If the short pattern appears more often than its longer parent, keep it."""
        candidates = [
            {
                "kind": "tool-sequence",
                "key": ("Read", "Edit"),
                "names": ["Read", "Edit"],
                "frequency": 10,
                "sessions": 5,
                "example": "Read → Edit",
            },
            {
                "kind": "tool-sequence",
                "key": ("Read", "Edit", "Bash"),
                "names": ["Read", "Edit", "Bash"],
                "frequency": 3,
                "sessions": 3,
                "example": "Read → Edit → Bash",
            },
        ]
        out = ps.dedupe_candidates(candidates)
        keys = {tuple(c["key"]) for c in out if c["kind"] == "tool-sequence"}
        self.assertIn(("Read", "Edit"), keys)
        self.assertIn(("Read", "Edit", "Bash"), keys)

    def test_non_sequence_candidates_pass_through(self):
        """Prompt-template and bash-shape candidates are never dropped by dedupe."""
        candidates = [
            {
                "kind": "prompt-template",
                "key": "create a release notes draft",
                "frequency": 3,
                "sessions": 3,
                "example": "create a release notes draft for v1",
            },
            {
                "kind": "bash-shape",
                "key": ("gh", "pr"),
                "names": ["gh", "pr"],
                "frequency": 3,
                "sessions": 3,
                "example": "gh pr create",
            },
        ]
        out = ps.dedupe_candidates(candidates)
        self.assertEqual(len(out), 2)


# ---------------------------------------------------------------------------
# Privacy scrub
# ---------------------------------------------------------------------------


class TestPrivacyScrub(unittest.TestCase):
    def test_absolute_home_path_normalized_to_tilde(self):
        """An absolute path under $HOME is rewritten to the ~/... form."""
        text = "Read /Users/alice/Projects/foo/bar.py for me"
        scrubbed = ps.scrub_path(text, home="/Users/alice")
        self.assertIn("~/Projects/foo/bar.py", scrubbed)
        self.assertNotIn("/Users/alice/", scrubbed)

    def test_scrub_is_idempotent(self):
        """Scrubbing an already-scrubbed string does not mangle it."""
        text = "open ~/Projects/foo/bar.py"
        self.assertEqual(ps.scrub_path(text, home="/Users/alice"), text)

    def test_session_with_secret_token_is_skipped(self):
        """A session whose user prompt mentions 'secret' is flagged private."""
        prompts = ["please check the secret rotation script"]
        self.assertTrue(ps.session_is_private(prompts))

    def test_session_with_private_token_is_skipped(self):
        prompts = ["this is a private codebase"]
        self.assertTrue(ps.session_is_private(prompts))

    def test_clean_session_is_not_private(self):
        prompts = ["create a release notes draft for v1"]
        self.assertFalse(ps.session_is_private(prompts))


# ---------------------------------------------------------------------------
# End-to-end smoke test — write fake session jsonl files and run analyze().
# ---------------------------------------------------------------------------


class TestAnalyzeEndToEnd(unittest.TestCase):
    def _write_session(self, dir_path: Path, sess_id: str, lines: list[dict]) -> Path:
        f = dir_path / f"{sess_id}.jsonl"
        f.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
        return f

    def _user_msg(self, text: str) -> dict:
        return {"type": "user", "message": {"content": text}}

    def _assistant_msg(self, tool_uses: list[dict]) -> dict:
        return {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": tu["name"], "input": tu.get("input", {})}
                    for tu in tool_uses
                ],
            },
        }

    def test_analyze_produces_candidates_from_three_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = "test-proj"
            project_dir = root / project
            project_dir.mkdir()
            for i in range(3):
                self._write_session(
                    project_dir,
                    f"sess-{i}",
                    [
                        self._user_msg(f"create a release notes draft for v{i}.0"),
                        self._assistant_msg(
                            [
                                {"name": "Read", "input": {"file_path": "/x/foo.py"}},
                                {"name": "Edit", "input": {"file_path": "/x/foo.py"}},
                                {"name": "Bash", "input": {"command": f"gh pr create --title v{i}"}},
                            ]
                        ),
                    ],
                )
            result = ps.analyze(sessions_root=root, project=project, limit=10)
            self.assertEqual(result["sessions_scanned"], 3)
            self.assertEqual(result["sessions_skipped"], 0)
            kinds = {c["kind"] for c in result["candidates"]}
            self.assertIn("tool-sequence", kinds)
            self.assertIn("prompt-template", kinds)
            self.assertIn("bash-shape", kinds)

    def test_analyze_skips_private_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = "test-proj"
            project_dir = root / project
            project_dir.mkdir()
            self._write_session(
                project_dir,
                "sess-priv",
                [
                    self._user_msg("the secret service token is rotating"),
                    self._assistant_msg([{"name": "Read", "input": {}}]),
                ],
            )
            result = ps.analyze(sessions_root=root, project=project, limit=10)
            self.assertEqual(result["sessions_scanned"], 0)
            self.assertEqual(result["sessions_skipped"], 1)

    def test_render_report_includes_summary_and_candidates(self):
        report = ps.render_report(
            project="test-proj",
            sessions_scanned=3,
            sessions_skipped=0,
            candidates=[
                {
                    "kind": "tool-sequence",
                    "key": ("Read", "Edit", "Bash"),
                    "names": ["Read", "Edit", "Bash"],
                    "frequency": 3,
                    "sessions": 3,
                    "example": "Read → Edit → Bash",
                }
            ],
            timestamp="2026-04-26T00:00:00Z",
        )
        self.assertIn("# Session-mined skill proposals", report)
        self.assertIn("Sessions scanned**: 3", report)
        self.assertIn("/wg-scaffold skill", report)
        self.assertIn("Read → Edit → Bash", report)

    def test_render_report_handles_empty_candidates(self):
        report = ps.render_report(
            project="test-proj",
            sessions_scanned=0,
            sessions_skipped=0,
            candidates=[],
            timestamp="2026-04-26T00:00:00Z",
        )
        self.assertIn("No repetitive patterns met the minimum-frequency threshold.", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
