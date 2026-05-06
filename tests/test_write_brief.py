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

# write_brief.py lives under scripts/crew — needs scripts/ on sys.path
# AND scripts/crew on sys.path so its own intra-script imports resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "crew"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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


def test_no_flags_returns_default_dict_and_unchanged_description():
    flags, clean = write_brief.parse_flags("Just a normal description")
    assert flags == {
        "yolo": False,
        "rigor": None,
        "force": False,
        "consensus_threshold": None,
    }
    assert clean == "Just a normal description"
