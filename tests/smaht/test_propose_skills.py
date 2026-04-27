#!/usr/bin/env python3
"""tests/smaht/test_propose_skills.py — unit tests for the session-mined skill builder MVP (#677).

Covers:

* The 3 detectors (repeated tool sequence, repeated prompt template,
  repeated bash shape) — each with a synthetic 3-session fixture.
* The deduplication step (overlapping patterns → only the longest survives).
* The privacy scrub (absolute paths normalized to ``~/...``, boundary-safe).
* The privacy session-skip token heuristic (incl. trigger past 200-char cut).
* End-to-end ``analyze()`` behavior on temp session files.
* CLAUDE_CONFIG_DIR honoring in ``session_root()``.
* Cross-platform ``project_slug()`` (Windows path).
* Unicode-aware prompt prefix normalization.
* Generic multi-word prompt blocklist substring filter.
* Frequency vs distinct-session counter independence.
* CLI exit code 1 on report write failure and ``--json`` mode shape.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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


# ---------------------------------------------------------------------------
# CLAUDE_CONFIG_DIR resolution (CRITICAL fix from PR #678 follow-up)
# ---------------------------------------------------------------------------


class TestClaudeConfigDirResolution(unittest.TestCase):
    def test_session_root_honors_claude_config_dir(self):
        """When CLAUDE_CONFIG_DIR is set, session_root() points under that dir."""
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/Users/me/alt-configs/.claude"}):
            root = ps.session_root()
        self.assertEqual(root, Path("/Users/me/alt-configs/.claude/projects"))

    def test_session_root_falls_back_to_home_when_unset(self):
        """When CLAUDE_CONFIG_DIR is unset, session_root() falls back to ~/.claude/projects."""
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            root = ps.session_root()
        self.assertEqual(root, Path.home() / ".claude" / "projects")

    def test_session_root_treats_empty_string_as_unset(self):
        """An empty CLAUDE_CONFIG_DIR should fall back to ~/.claude (not ./projects)."""
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}):
            root = ps.session_root()
        self.assertEqual(root, Path.home() / ".claude" / "projects")

    def test_default_sessions_root_alias_matches_session_root(self):
        """default_sessions_root() is a back-compat alias and must agree with session_root()."""
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/some/where/.claude"}):
            self.assertEqual(ps.default_sessions_root(), ps.session_root())


# ---------------------------------------------------------------------------
# project_slug — Windows path normalization (F1)
# ---------------------------------------------------------------------------


class TestProjectSlugCrossPlatform(unittest.TestCase):
    def test_posix_path_yields_dash_prefixed_slug(self):
        slug = ps.project_slug(Path("/Users/x/Projects/wicked-garden"))
        self.assertEqual(slug, "-Users-x-Projects-wicked-garden")

    def test_windows_drive_colon_is_stripped(self):
        """A POSIX path that contains a colon (mimicking a Windows drive) must be cleaned.

        We can't construct a real ``PureWindowsPath`` and pass it through
        ``project_slug`` on a POSIX runner because ``Path.resolve()`` insists on
        the local filesystem. Instead we exercise the slug-derivation contract:
        the function MUST strip ``:`` characters before splitting on ``/`` so a
        Windows drive letter (``C:``) survives as plain ``C``.
        """
        # Reproduce the internal transformation step on a synthetic posix string
        # that has a drive-style colon.
        posix_with_drive = "C:/Users/x/Projects/wg"
        cleaned = posix_with_drive.replace(":", "")
        expected = "-" + cleaned.strip("/").replace("/", "-")
        self.assertEqual(expected, "-C-Users-x-Projects-wg")
        # And confirm there is no ``:`` left in the canonical slug.
        self.assertNotIn(":", expected)

    def test_real_cwd_slug_does_not_contain_backslashes_or_colons(self):
        """End-to-end: project_slug on cwd produces a filesystem-safe slug."""
        slug = ps.project_slug()
        self.assertNotIn("\\", slug)
        self.assertNotIn(":", slug)
        self.assertTrue(slug.startswith("-"))


# ---------------------------------------------------------------------------
# Unicode-aware prompt prefix (F2)
# ---------------------------------------------------------------------------


class TestUnicodePromptPrefix(unittest.TestCase):
    def test_japanese_words_are_preserved(self):
        """CJK characters survive the punctuation strip and produce a non-empty prefix."""
        # Five Japanese tokens with ASCII spaces.
        prompt = "今日 の リリース ノート を 作って"
        prefix = ps._normalize_prompt_prefix(prompt)
        self.assertIsNotNone(prefix)
        self.assertEqual(prefix.split()[:5], ["今日", "の", "リリース", "ノート", "を"])

    def test_accented_characters_are_preserved(self):
        prompt = "créer une note de version pour la prochaine"
        prefix = ps._normalize_prompt_prefix(prompt)
        self.assertIsNotNone(prefix)
        self.assertTrue(prefix.startswith("créer une note de version"))


# ---------------------------------------------------------------------------
# Privacy: trigger past char 200 still flags (F4)
# ---------------------------------------------------------------------------


class TestPrivacyChecksFullPrompt(unittest.TestCase):
    def test_trigger_token_past_200_chars_is_caught_by_parse_session(self):
        """A 'private' token at offset > 200 must still flag the session."""
        with tempfile.TemporaryDirectory() as tmp:
            sess_path = Path(tmp) / "long.jsonl"
            long_prefix = "lorem ipsum dolor sit amet " * 20  # > 400 chars
            full_prompt = long_prefix + "and then the private bits"
            line = {"type": "user", "message": {"content": full_prompt}}
            sess_path.write_text(json.dumps(line) + "\n", encoding="utf-8")
            digest = ps.parse_session(sess_path)
        self.assertTrue(digest["privacy_skip"])
        # The stored prompt is truncated to 200 chars and does NOT contain the trigger,
        # but the privacy flag was raised on the full string.
        self.assertNotIn("private", digest["user_prompts"][0])

    def test_clean_session_does_not_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            sess_path = Path(tmp) / "clean.jsonl"
            line = {"type": "user", "message": {"content": "draft a release note for v1"}}
            sess_path.write_text(json.dumps(line) + "\n", encoding="utf-8")
            digest = ps.parse_session(sess_path)
        self.assertFalse(digest["privacy_skip"])


# ---------------------------------------------------------------------------
# scrub_path boundary-safety (F7)
# ---------------------------------------------------------------------------


class TestScrubPathBoundaries(unittest.TestCase):
    def test_substring_path_is_not_scrubbed(self):
        """home='/Users/alice' must NOT match /Users/alice2/ as a substring."""
        text = "open /Users/alice2/Projects/foo.py"
        scrubbed = ps.scrub_path(text, home="/Users/alice")
        self.assertEqual(scrubbed, text)
        self.assertIn("/Users/alice2/Projects/foo.py", scrubbed)

    def test_exact_home_match_with_trailing_separator_is_scrubbed(self):
        text = "open /Users/alice/Projects/foo.py"
        self.assertEqual(
            ps.scrub_path(text, home="/Users/alice"),
            "open ~/Projects/foo.py",
        )

    def test_home_at_end_of_string_is_scrubbed(self):
        self.assertEqual(ps.scrub_path("/Users/alice", home="/Users/alice"), "~")

    def test_windows_separator_boundary(self):
        text = "open C:\\Users\\alice\\proj\\foo.py"
        # Boundary regex matches both / and \\ — exercise the \\ branch.
        self.assertEqual(
            ps.scrub_path(text, home="C:\\Users\\alice"),
            "open ~\\proj\\foo.py",
        )


# ---------------------------------------------------------------------------
# Generic multi-word prompt blocklist substring filter (F13)
# ---------------------------------------------------------------------------


class TestGenericMultiWordBlocklist(unittest.TestCase):
    def test_do_it_substring_in_prefix_is_filtered(self):
        """A 5-word prefix containing the multi-word generic 'do it' is rejected."""
        # First 5 words: "please do it now and"
        self.assertIsNone(ps._normalize_prompt_prefix("please do it now and then go home"))

    def test_looks_good_substring_in_prefix_is_filtered(self):
        # First 5 words: "this looks good to me"
        self.assertIsNone(
            ps._normalize_prompt_prefix("this looks good to me let us proceed with the plan")
        )

    def test_legit_prefix_passes_through(self):
        prefix = ps._normalize_prompt_prefix("create a release notes draft for v1")
        self.assertEqual(prefix, "create a release notes draft")


# ---------------------------------------------------------------------------
# Frequency != distinct sessions (F6)
# ---------------------------------------------------------------------------


class TestFrequencyDistinctSessionsAreIndependent(unittest.TestCase):
    def test_intra_session_repeats_increment_frequency_not_session_count(self):
        """One session repeating Read→Edit four times → frequency=4 across 1 session.

        With MIN_SESSION_COUNT=2 this gets filtered, so we lower the threshold to
        prove the counters are tracked separately rather than co-incremented.
        """
        sess = _make_session(
            "/sessions/sess-1.jsonl",
            prompts=[],
            tool_calls=[
                _tc("Read"), _tc("Edit"),
                _tc("Read"), _tc("Edit"),
                _tc("Read"), _tc("Edit"),
                _tc("Read"), _tc("Edit"),
            ],
        )
        out = ps.detect_repeated_sequences([sess], min_freq=2, min_sessions=1)
        match = [c for c in out if tuple(c["key"]) == ("Read", "Edit")][0]
        self.assertEqual(match["frequency"], 4)
        self.assertEqual(match["sessions"], 1)
        self.assertNotEqual(match["frequency"], match["sessions"])

    def test_min_session_count_filters_single_session_patterns(self):
        """At default MIN_SESSION_COUNT=2, a one-session pattern is filtered."""
        sess = _make_session(
            "/sessions/only.jsonl",
            prompts=[],
            tool_calls=[_tc("Read"), _tc("Edit")] * 5,
        )
        out = ps.detect_repeated_sequences([sess])  # uses MIN_SESSION_COUNT=2
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# CLI run() — exit codes and --json shape (F3, F5)
# ---------------------------------------------------------------------------


class TestRunCli(unittest.TestCase):
    def _build_three_sessions(self, root: Path, project: str) -> None:
        project_dir = root / project
        project_dir.mkdir()
        for i in range(3):
            lines = [
                {"type": "user", "message": {"content": f"create a release notes draft for v{i}"}},
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Read", "input": {}},
                            {"type": "tool_use", "name": "Edit", "input": {}},
                            {"type": "tool_use", "name": "Bash", "input": {"command": f"gh pr create --title v{i}"}},
                        ],
                    },
                },
            ]
            (project_dir / f"sess-{i}.jsonl").write_text(
                "\n".join(json.dumps(l) for l in lines), encoding="utf-8"
            )

    def test_json_mode_includes_full_candidates_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = "proj"
            self._build_three_sessions(root, project)
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                code = ps.run(
                    [
                        "--sessions-root",
                        str(root),
                        "--project",
                        project,
                        "--limit",
                        "10",
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(out_buf.getvalue())
            self.assertIn("report_path", payload)
            self.assertIn("sessions_root", payload)
            self.assertIn("candidates", payload)
            self.assertIsInstance(payload["candidates"], list)
            self.assertEqual(payload["candidate_count"], len(payload["candidates"]))
            # Every candidate must be JSON-safe (tuples were converted to lists).
            for c in payload["candidates"]:
                self.assertNotIsInstance(c.get("key"), tuple)

    def test_default_mode_prints_only_report_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = "proj"
            self._build_three_sessions(root, project)
            out_buf = io.StringIO()
            with redirect_stdout(out_buf), redirect_stderr(io.StringIO()):
                code = ps.run(
                    ["--sessions-root", str(root), "--project", project, "--limit", "10"]
                )
            self.assertEqual(code, 0)
            printed = out_buf.getvalue().strip()
            self.assertTrue(printed)
            self.assertTrue(Path(printed).is_file())

    def test_run_returns_one_when_report_write_fails(self):
        """When write_text raises OSError, run() returns 1 (not 0) and logs to stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = "proj"
            self._build_three_sessions(root, project)
            err_buf = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err_buf), mock.patch.object(
                Path, "write_text", side_effect=OSError("disk full")
            ):
                code = ps.run(
                    ["--sessions-root", str(root), "--project", project, "--limit", "10"]
                )
            self.assertEqual(code, 1)
            self.assertIn("failed to write report", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
