"""tests/test_write_brief.py — slug + flag parsing for the v10 Phase 2A
slim-skill-body shape.

Provenance: brainstorm session 02 (slim skill body shape) proposed
extracting `commands/crew/start.md`'s slug algorithm + flag parsing
into `scripts/crew/write_brief.py` so the command body could shrink
from 304 lines to a Pattern B shape. These tests cover the pure
functions that live in that script — slug generation and flag parsing.

Project-shell creation and brief composition involve subprocess calls
(`phase_manager.py`) and filesystem writes; those are intentionally
not unit-tested here. They are exercised by the existing crew scenario
suite (scenarios/crew/) that runs end-to-end.

T1: deterministic — pure functions, no I/O
T3: isolated — each test passes its own input
T4: single focus per test
T5: descriptive names spell out input + expected outcome
T6: docstrings cite the design record
"""

import sys
from pathlib import Path

# conftest.py keeps `scripts/` at sys.path[0]. Append `scripts/crew/` (do NOT
# insert at 0) so write_brief.py can be imported by name without shadowing
# scripts/ — same pattern as the rest of the repo's test suite (avoids the
# scripts/crew/crew.py-shadowing-the-crew-package bug).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CREW_DIR = _REPO_ROOT / "scripts" / "crew"
if str(_CREW_DIR) not in sys.path:
    sys.path.append(str(_CREW_DIR))

import write_brief  # noqa: E402


# ---------------------------------------------------------------------------
# generate_slug — three-stage theme-aware algorithm
# ---------------------------------------------------------------------------

def test_implement_oauth_routes_to_feat_theme():
    """Brainstorm session 02: 'implement' is a feat signal; concept
    extraction kebab-cases the remaining nouns; truncation respects
    the 64-char word boundary."""
    slug, theme = write_brief.generate_slug("Implement OAuth flow with session tokens")
    assert theme == "feat"
    assert slug.startswith("feat-")
    assert "oauth" in slug
    assert "session" in slug
    assert len(slug) <= 64


def test_fix_bug_routes_to_fix_theme():
    """'bug' / 'fix' / 'broken' are fix-theme signals."""
    slug, theme = write_brief.generate_slug("fix the bug in the login flow")
    assert theme == "fix"
    assert slug.startswith("fix-")
    assert "login" in slug


def test_issue_number_pattern_routes_to_issue_theme():
    """`#NNN` token is a stronger issue signal than the surrounding words —
    issue theme wins even when 'fix' is also present."""
    slug, theme = write_brief.generate_slug("address the bug in #813")
    assert theme == "issue"
    assert slug.startswith("issue-")


def test_refactor_keyword_routes_to_refactor_theme():
    slug, theme = write_brief.generate_slug("refactor the phase manager")
    assert theme == "refactor"
    assert slug.startswith("refactor-")


def test_docs_keyword_routes_to_docs_theme():
    slug, theme = write_brief.generate_slug("update the README and changelog")
    assert theme == "docs"
    assert slug.startswith("docs-")


def test_no_theme_match_falls_back_to_kebab_case():
    """When no theme keyword matches, the slug is plain kebab-case of
    the description — no prefix."""
    slug, theme = write_brief.generate_slug("rotate the api key")
    assert theme == ""
    assert "-" in slug  # at least some kebab structure
    assert slug == slug.lower()  # always lowercased


def test_stop_words_excluded_from_concepts():
    """'the', 'a', 'with', etc. are stop words — they don't appear
    in the concept tokens."""
    slug, _ = write_brief.generate_slug("Implement the new auth flow with the api")
    # No bare 'the', 'with', 'a', 'an' as a concept fragment.
    parts = slug.split("-")
    assert "the" not in parts
    assert "with" not in parts


def test_slug_truncated_on_word_boundary():
    """Long descriptions truncate without splitting a word mid-token."""
    long_desc = "Implement " + " ".join([f"keyword{i}" for i in range(20)])
    slug, _ = write_brief.generate_slug(long_desc)
    assert len(slug) <= 64
    # If truncated, the last char must not be a hanging partial token.
    # Verify: no slug ends with a half-word followed by truncation.
    assert not slug.endswith("-")


def test_empty_description_returns_empty_slug():
    """Defensive — empty input doesn't crash; returns empty slug + theme."""
    slug, theme = write_brief.generate_slug("")
    assert slug == ""
    assert theme == ""


def test_whitespace_only_description_returns_empty_slug():
    slug, theme = write_brief.generate_slug("   \n\t  ")
    assert slug == ""
    assert theme == ""


# ---------------------------------------------------------------------------
# parse_flags — v6 orthogonal axes
# ---------------------------------------------------------------------------

def test_yolo_flag_parsed_and_stripped():
    flags, clean = write_brief.parse_flags("Build the auth feature --yolo")
    assert flags["yolo"] is True
    assert "--yolo" not in clean


def test_just_finish_aliases_yolo():
    """`--just-finish` is documented as an alias for `--yolo`."""
    flags, clean = write_brief.parse_flags("Build the feature --just-finish")
    assert flags["yolo"] is True
    assert "--just-finish" not in clean


def test_rigor_equals_form_parsed():
    flags, clean = write_brief.parse_flags("Build the feature --rigor=full")
    assert flags["rigor"] == "full"
    assert "--rigor" not in clean


def test_rigor_space_form_parsed():
    """`--rigor full` (separate token) is also accepted."""
    flags, clean = write_brief.parse_flags("Build the feature --rigor full")
    assert flags["rigor"] == "full"
    assert "--rigor" not in clean
    assert " full" not in clean  # value also stripped


def test_invalid_rigor_value_is_left_in_description():
    """`--rigor=turbo` is not a known value — leave it in the
    description so the slug doesn't accidentally absorb a flag-shaped
    token but the user still sees their typo surface as a slug."""
    flags, clean = write_brief.parse_flags("Build it --rigor=turbo")
    assert flags["rigor"] is None
    assert "--rigor=turbo" in clean


def test_force_flag_parsed():
    flags, clean = write_brief.parse_flags("Refactor the module --force")
    assert flags["force"] is True
    assert "--force" not in clean


def test_consensus_threshold_equals_form():
    flags, clean = write_brief.parse_flags("Plan it --consensus-threshold=3")
    assert flags["consensus_threshold"] == 3


def test_consensus_threshold_space_form():
    flags, clean = write_brief.parse_flags("Plan it --consensus-threshold 4")
    assert flags["consensus_threshold"] == 4


def test_unknown_flag_left_in_description():
    """Unrecognised --flag tokens are NOT treated as flags — they stay
    in the description so the user's literal text isn't silently
    swallowed (e.g. 'implement --turbo flag' should describe a
    `--turbo` flag, not parse one)."""
    flags, clean = write_brief.parse_flags("implement --turbo flag")
    assert flags["yolo"] is False
    assert flags["rigor"] is None
    assert "--turbo" in clean


def test_multiple_flags_all_parsed():
    flags, clean = write_brief.parse_flags(
        "Build the auth feature --yolo --rigor=full --force --consensus-threshold=2"
    )
    assert flags["yolo"] is True
    assert flags["rigor"] == "full"
    assert flags["force"] is True
    assert flags["consensus_threshold"] == 2
    # All flag tokens removed; clean description is just the work text.
    assert clean.strip() == "Build the auth feature"


# ---------------------------------------------------------------------------
# Regression tests — review feedback on PR #815
# ---------------------------------------------------------------------------

def test_flag_stripping_preserves_literal_word_in_description():
    """PR #815 review (gemini high): the previous implementation used
    global re.sub with bare token text, so 'Implement full feature
    --rigor full' would strip BOTH the flag value `full` (correct) AND
    the literal word 'full' from the description (data corruption). The
    fix tracks token indices and removes only the flag tokens. The
    literal 'full' must remain in the cleaned description."""
    flags, clean = write_brief.parse_flags(
        "Implement full feature --rigor full"
    )
    assert flags["rigor"] == "full"
    assert clean == "Implement full feature"
    assert "--rigor" not in clean


def test_theme_detection_word_boundary_protects_short_keyword_add():
    """PR #815 review (gemini medium / copilot): substring matching on
    'add' would falsely match inside 'address'. Use word-boundary
    regex so only the standalone word triggers the feat theme."""
    # 'address' contains 'add' but is not a feat signal in isolation.
    _slug, theme = write_brief.generate_slug("update the address book schema")
    assert theme != "feat"


def test_theme_detection_word_boundary_protects_short_keyword_fix():
    """PR #815 review (gemini medium): 'fix' inside 'suffix', 'prefix'
    must NOT trigger the fix theme."""
    _slug, theme = write_brief.generate_slug("update the file suffix logic")
    assert theme != "fix"


def test_theme_keyword_stripping_word_boundary_preserves_debug():
    """PR #815 review (gemini medium): when fix theme matches via 'bug',
    keyword stripping must not also drop substrings of unrelated words.
    'fix the debug counter' should detect fix theme, strip 'fix', but
    PRESERVE 'debug' (which contains 'bug') so concept extraction sees
    'debug' as a slug concept."""
    slug, theme = write_brief.generate_slug("fix the debug counter")
    assert theme == "fix"
    assert "debug" in slug


def test_brief_template_handles_curly_braces_in_user_description(tmp_path):
    """PR #815 review (gemini high): user-controlled text inserted into
    _BRIEF_TEMPLATE via .format() must escape curly braces or .format()
    raises KeyError. This drives write_crew_brief end-to-end with a
    brace-bearing description and asserts no exception."""
    project_dir = tmp_path / "test-project-curly"
    brief_path = write_brief.write_crew_brief(
        project_dir,
        command="crew:start",
        slug="feat-curly-braces",
        theme_prefix="feat",
        description="render {x} as {y} JSON",  # literal braces in user input
        flags={
            "yolo": False, "rigor": None, "force": False,
            "consensus_threshold": None,
        },
        resolution=None,
        conflicting_slug=None,
    )
    body = brief_path.read_text(encoding="utf-8")
    # Doubled braces collapse to single in the rendered output, so the
    # literal text round-trips faithfully.
    assert "{x}" in body
    assert "{y}" in body


def test_parse_json_block_handles_pretty_printed_full_object():
    """PR #815 review (copilot): _phase_manager and find_active_project
    used to parse `last_line` of pretty-printed JSON, where the last
    line is `}`. _parse_json_block must parse the FULL stdout."""
    pretty = '{\n  "project": null,\n  "project_dir": null\n}'
    parsed = write_brief._parse_json_block(pretty)
    assert parsed == {"project": None, "project_dir": None}


def test_parse_json_block_tolerates_prelude():
    """_parse_json_block tolerates optional non-JSON prelude lines."""
    with_prelude = (
        "[some log line]\n"
        '{\n  "slug": "my-proj",\n  "project_dir": "/tmp/foo"\n}'
    )
    parsed = write_brief._parse_json_block(with_prelude)
    assert parsed == {"slug": "my-proj", "project_dir": "/tmp/foo"}


def test_parse_json_block_returns_empty_dict_on_garbage():
    """Defensive: unparseable input → empty dict, never raise."""
    assert write_brief._parse_json_block("not json") == {}
    assert write_brief._parse_json_block("") == {}


def test_no_flags_returns_default_dict_and_unchanged_description():
    flags, clean = write_brief.parse_flags("Just a normal description")
    assert flags == {
        "yolo": False,
        "rigor": None,
        "force": False,
        "consensus_threshold": None,
    }
    assert clean == "Just a normal description"
